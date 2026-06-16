#!/usr/bin/env python3
"""Generate targeted manual-review priority videos from the stock × reach matrix.

This is an additive derived step. It does not mutate raw baseline files.

Selection logic:
- Focus on P0/P1 projects from project_stock_reach_matrix.
- For every selected project, include high-play examples from:
  - likely_relevant: evidence for the current reach signal
  - needs_review: boundary cases that may move inclusive reach
  - low_relevance: noise/false-positive evidence, especially for high-risk projects
  - raw_top: absolute top videos if not already selected
- Deduplicate within project by video_id.

Outputs:
- data/derived/manual_check_priority_videos.csv
- data/derived/manual_check_priority_videos.json
- docs/人工核查优先视频清单.md
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FOCUS_PRIORITIES = {
    "P0_stock_high_reach_low",
    "P0_noise_or_tier_drop",
    "P1_low_stock_high_reach",
    "P1_inclusive_sensitive",
}

REVIEW_FIELDS = [
    "manual_relevance",          # relevant / not_relevant / unsure
    "manual_noise_type",         # generic_term / wrong_project / geography_not_china / product_commerce / other
    "manual_language_reach",     # cjk / english / mixed / non_cjk_non_en / unclear
    "manual_audience_proxy",     # comment_cn / comment_en / mixed / no_comments / not_checked
    "manual_notes",
]


def iter_ndjson(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Bad JSON at {path}:{line_no}: {exc}") from exc


def load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "rows" in data:
        return list(data["rows"])
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported JSON shape: {path}")


def i(v: Any) -> int:
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def f(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def compact_desc(s: Any, limit: int = 260) -> str:
    text = " ".join(str(s or "").replace("\n", " ").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def dedupe_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate project-video rows, keeping the strongest label/evidence copy."""
    rank = {"likely_relevant": 3, "needs_review": 2, "low_relevance": 1}
    best: dict[tuple[int, str], dict[str, Any]] = {}
    for r in rows:
        key = (int(r["project_id"]), str(r.get("video_id") or ""))
        if not key[1]:
            continue
        prev = best.get(key)
        if prev is None:
            best[key] = r
            continue
        score = (
            rank.get(str(r.get("quality_label")), 0),
            i(r.get("stats_play_count")),
            i(r.get("quality_score")),
        )
        prev_score = (
            rank.get(str(prev.get("quality_label")), 0),
            i(prev.get("stats_play_count")),
            i(prev.get("quality_score")),
        )
        if score > prev_score:
            best[key] = r
    return list(best.values())


def pick_top(candidates: list[dict[str, Any]], n: int, already: set[str]) -> list[dict[str, Any]]:
    picked = []
    for r in sorted(candidates, key=lambda x: i(x.get("stats_play_count")), reverse=True):
        vid = str(r.get("video_id") or "")
        if not vid or vid in already:
            continue
        picked.append(r)
        already.add(vid)
        if len(picked) >= n:
            break
    return picked


def choose_counts(matrix_row: dict[str, Any]) -> dict[str, int]:
    priority = matrix_row.get("review_priority")
    risk = matrix_row.get("reach_noise_risk")
    quadrant = matrix_row.get("quadrant")
    if str(priority).startswith("P0"):
        return {"likely_evidence": 3, "needs_review_boundary": 2, "low_noise_probe": 3, "raw_top_probe": 2}
    if quadrant == "stock_low__reach_high":
        return {"likely_evidence": 4, "needs_review_boundary": 2, "low_noise_probe": 2, "raw_top_probe": 1}
    if risk == "high":
        return {"likely_evidence": 2, "needs_review_boundary": 2, "low_noise_probe": 3, "raw_top_probe": 1}
    return {"likely_evidence": 2, "needs_review_boundary": 1, "low_noise_probe": 1, "raw_top_probe": 1}


def reason_for_bucket(bucket: str, matrix_row: dict[str, Any]) -> str:
    priority = matrix_row.get("review_priority")
    quadrant = matrix_row.get("quadrant")
    if bucket == "likely_evidence":
        if quadrant == "stock_low__reach_high":
            return "验证低存量高触达是否为真相关破圈视频"
        if quadrant == "stock_high__reach_low":
            return "检查高存量低/中触达项目中少数有效触达视频的性质"
        return "验证 likely_relevant 触达信号"
    if bucket == "needs_review_boundary":
        return "判定 needs_review 是否应回流到 likely 或 low，影响 inclusive 触达"
    if bucket == "low_noise_probe":
        return "核查 low_relevance 高播放噪声是否为撞词/泛词/错项目"
    if bucket == "raw_top_probe":
        return "核查 raw top 是否由低相关热门视频撑高"
    return str(priority or "manual review")


def build_priority_rows(matrix_rows: list[dict[str, Any]], label_rows: list[dict[str, Any]], include_p2: bool = False) -> list[dict[str, Any]]:
    selected_matrix = []
    for r in matrix_rows:
        pri = str(r.get("review_priority") or "")
        if pri in FOCUS_PRIORITIES or (include_p2 and pri.startswith("P2")):
            selected_matrix.append(r)
    selected_ids = {int(r["project_id"]) for r in selected_matrix}

    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in dedupe_labels(label_rows):
        pid = int(r["project_id"])
        if pid in selected_ids:
            by_project[pid].append(r)

    matrix_by_id = {int(r["project_id"]): r for r in selected_matrix}
    out: list[dict[str, Any]] = []
    for pid in sorted(selected_ids):
        m = matrix_by_id[pid]
        rows = by_project.get(pid, [])
        already: set[str] = set()
        counts = choose_counts(m)
        buckets = [
            ("likely_evidence", [r for r in rows if r.get("quality_label") == "likely_relevant"]),
            ("needs_review_boundary", [r for r in rows if r.get("quality_label") == "needs_review"]),
            ("low_noise_probe", [r for r in rows if r.get("quality_label") == "low_relevance"]),
            ("raw_top_probe", rows),
        ]
        local_rank = 0
        for bucket, candidates in buckets:
            for v in pick_top(candidates, counts.get(bucket, 0), already):
                local_rank += 1
                out.append({
                    "review_rank_project": local_rank,
                    "review_bucket": bucket,
                    "review_reason": reason_for_bucket(bucket, m),
                    "project_id": pid,
                    "project_name": m.get("project_name"),
                    "list_type": m.get("list_type"),
                    "category": m.get("category"),
                    "quadrant": m.get("quadrant"),
                    "quadrant_label": m.get("quadrant_label"),
                    "review_priority": m.get("review_priority"),
                    "scale_video_count_tier": m.get("scale_video_count_tier"),
                    "scale_video_count_best": m.get("scale_video_count_best"),
                    "scale_best_hashtag": m.get("scale_best_hashtag"),
                    "likely_reach_tier": m.get("likely_reach_tier"),
                    "raw_reach_tier": m.get("raw_reach_tier"),
                    "inclusive_reach_tier": m.get("inclusive_reach_tier"),
                    "reach_noise_risk": m.get("reach_noise_risk"),
                    "low_relevance_play_ratio_project": m.get("low_relevance_play_ratio"),
                    "likely_play_ratio_project": m.get("likely_play_ratio"),
                    "video_id": v.get("video_id"),
                    "web_url": v.get("web_url"),
                    "author_unique_id": v.get("author_unique_id"),
                    "source_term": v.get("source_term"),
                    "term_script": v.get("term_script"),
                    "ceiling_class": v.get("ceiling_class"),
                    "quality_label_auto": v.get("quality_label"),
                    "quality_score_auto": v.get("quality_score"),
                    "quality_reasons_auto": ";".join(str(x) for x in (v.get("quality_reasons") or [])),
                    "matched_terms_auto": ";".join(str(x) for x in (v.get("matched_terms") or [])),
                    "core_matched_terms_auto": ";".join(str(x) for x in (v.get("core_matched_terms") or [])),
                    "negative_matched_terms_auto": ";".join(str(x) for x in (v.get("negative_matched_terms") or [])),
                    "stats_play_count": i(v.get("stats_play_count")),
                    "stats_digg_count": i(v.get("stats_digg_count")),
                    "stats_comment_count": i(v.get("stats_comment_count")),
                    "stats_share_count": i(v.get("stats_share_count")),
                    "stats_collect_count": i(v.get("stats_collect_count")),
                    "hashtags": ";".join(str(x) for x in (v.get("hashtags") or [])),
                    "desc": compact_desc(v.get("desc")),
                    **{field: "" for field in REVIEW_FIELDS},
                })
    # Global rank: P0 first, then P1; inside sort by project priority and video play.
    priority_rank = {
        "P0_stock_high_reach_low": 0,
        "P0_noise_or_tier_drop": 1,
        "P1_low_stock_high_reach": 2,
        "P1_inclusive_sensitive": 3,
    }
    out.sort(key=lambda r: (priority_rank.get(str(r.get("review_priority")), 9), r["project_id"], r["review_rank_project"]))
    for idx, r in enumerate(out, 1):
        r["review_rank_global"] = idx
    # put global rank first
    return [{"review_rank_global": r.pop("review_rank_global"), **r} for r in out]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_json(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Targeted manual-review priority videos. Manual columns are blank for human adjudication.",
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_int(v: Any) -> str:
    try:
        return f"{int(float(v or 0)):,}"
    except Exception:
        return str(v)


def fmt_pct(v: Any) -> str:
    try:
        return f"{float(v or 0) * 100:.1f}%"
    except Exception:
        return str(v)


def write_report(rows: list[dict[str, Any]], matrix_rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pri_counts = Counter(r["review_priority"] for r in rows)
    bucket_counts = Counter(r["review_bucket"] for r in rows)
    label_counts = Counter(r["quality_label_auto"] for r in rows)
    projects = sorted({(int(r["project_id"]), r["project_name"], r["review_priority"], r["quadrant"]) for r in rows})
    p0_projects = [p for p in projects if str(p[2]).startswith("P0")]
    p1_projects = [p for p in projects if str(p[2]).startswith("P1")]

    lines: list[str] = []
    lines.append("# 人工核查优先视频清单")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：`project_stock_reach_matrix` + `video_relevance_labels`。  ")
    lines.append("> 性质：定点人工核查样本；不是全量随机样本。")
    lines.append("")
    lines.append("## 1. 抽样口径")
    lines.append("")
    lines.append("- 只抽 `P0/P1` 项目：优先检查象限异常、raw→likely 掉档、low 播放占比高、低存量高触达等关键风险。")
    lines.append("- 每个项目从 `likely_relevant / needs_review / low_relevance / raw_top` 四个桶取高播放视频。")
    lines.append("- CSV 预留人工字段：`manual_relevance`, `manual_noise_type`, `manual_language_reach`, `manual_audience_proxy`, `manual_notes`。")
    lines.append("- 目标是校准正式分层，不是估计总体相关率。")
    lines.append("")
    lines.append("## 2. 总览")
    lines.append("")
    lines.append(f"- 视频样本数：{len(rows)}")
    lines.append(f"- 覆盖项目数：{len(projects)}（P0={len(p0_projects)}，P1={len(p1_projects)}）")
    lines.append("- review_priority 分布：")
    for k, v in pri_counts.most_common():
        lines.append(f"  - `{k}`: {v}")
    lines.append("- review_bucket 分布：")
    for k, v in bucket_counts.most_common():
        lines.append(f"  - `{k}`: {v}")
    lines.append("- 自动标签分布：")
    for k, v in label_counts.most_common():
        lines.append(f"  - `{k}`: {v}")
    lines.append("")
    lines.append("## 3. 覆盖项目")
    lines.append("")
    for pid, name, pri, q in projects:
        n = sum(1 for r in rows if int(r["project_id"]) == pid)
        lines.append(f"- **{name}**: {n} 条；priority=`{pri}`；quadrant=`{q}`")
    lines.append("")
    lines.append("## 4. 每类优先级的最高播放样例")
    lines.append("")
    for pri in ["P0_stock_high_reach_low", "P0_noise_or_tier_drop", "P1_low_stock_high_reach", "P1_inclusive_sensitive"]:
        xs = [r for r in rows if r["review_priority"] == pri]
        if not xs:
            continue
        lines.append(f"### {pri}")
        for r in sorted(xs, key=lambda x: int(x["stats_play_count"]), reverse=True)[:12]:
            lines.append(
                f"- **{r['project_name']}** / `{r['review_bucket']}` / auto={r['quality_label_auto']} / "
                f"play={fmt_int(r['stats_play_count'])}: {r['web_url']} — {r['desc']}"
            )
        lines.append("")
    lines.append("## 5. 建议核查动作")
    lines.append("")
    lines.append("1. 先填 P0：判断是否真相关、噪声类型、视频语言。")
    lines.append("2. 对 `stock_low__reach_high` 的 P1 项，重点判断是否是小而精破圈，还是标签/关键词误召回。")
    lines.append("3. 回流后重算项目级：manual_relevant / manual_noise_flag / corrected_reach_note，再锁定正式分层。")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", type=Path, default=Path("data/derived/project_stock_reach_matrix.json"))
    ap.add_argument("--labels", type=Path, default=Path("data/derived/video_relevance_labels.ndjson"))
    ap.add_argument("--include-p2", action="store_true", help="also sample P2 projects")
    ap.add_argument("--out-csv", type=Path, default=Path("data/derived/manual_check_priority_videos.csv"))
    ap.add_argument("--out-json", type=Path, default=Path("data/derived/manual_check_priority_videos.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/人工核查优先视频清单.md"))
    args = ap.parse_args()

    matrix = load_rows(args.matrix)
    labels = list(iter_ndjson(args.labels))
    rows = build_priority_rows(matrix, labels, include_p2=args.include_p2)
    write_csv(rows, args.out_csv)
    write_json(rows, args.out_json)
    write_report(rows, matrix, args.out_report)
    print(f"wrote rows={len(rows)} projects={len({r['project_id'] for r in rows})}")
    print("priority", dict(Counter(r["review_priority"] for r in rows)))
    print("bucket", dict(Counter(r["review_bucket"] for r in rows)))
    print("auto_label", dict(Counter(r["quality_label_auto"] for r in rows)))


if __name__ == "__main__":
    main()
