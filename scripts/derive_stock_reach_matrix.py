#!/usr/bin/env python3
"""Build the first stock × reach matrix for UNESCO China ICH TikTok baseline.

Inputs are additive derived artifacts only:
- data/derived/project_hashtag_scale_summary.json   (stock axis: hashtag statsV2.videoCount)
- data/derived/project_reach_relevance_aware.json   (reach axis: relevance-aware play metrics)

Outputs:
- data/derived/project_stock_reach_matrix.csv
- data/derived/project_stock_reach_matrix.json
- docs/存量触达二维分层草表.md

This script does not modify the raw baseline.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REACH_ORDER = {
    "top_20pct_reach": 5,
    "high_20_40pct_reach": 4,
    "middle_40_70pct_reach": 3,
    "lower_70_90pct_reach": 2,
    "bottom_10pct_reach": 1,
}

STOCK_ORDER = {
    "head": 4,
    "mid": 3,
    "long_tail": 2,
    "near_invisible": 1,
    "unavailable": 0,
}


def load_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "rows" in data:
        return list(data["rows"])
    if isinstance(data, list):
        return data
    raise ValueError(f"Unsupported JSON shape: {path}")


def stock_band(tier: str) -> str:
    if tier in {"head", "mid"}:
        return "stock_high"
    if tier == "long_tail":
        return "stock_mid"
    if tier == "near_invisible":
        return "stock_low"
    return "stock_unavailable"


def reach_band(tier: str) -> str:
    if tier in {"top_20pct_reach", "high_20_40pct_reach"}:
        return "reach_high"
    if tier == "middle_40_70pct_reach":
        return "reach_mid"
    if tier in {"lower_70_90pct_reach", "bottom_10pct_reach"}:
        return "reach_low"
    return "reach_unknown"


def quadrant(stock_b: str, reach_b: str) -> tuple[str, str]:
    # Primary 2×2 uses high vs not-high. Mid bands keep their explicit band fields
    # but are conservatively assigned to the lower side of the 2×2 for first-draft review.
    stock_hi = stock_b == "stock_high"
    reach_hi = reach_b == "reach_high"
    if stock_hi and reach_hi:
        return "stock_high__reach_high", "真·规模化出海候选"
    if stock_hi and not reach_hi:
        return "stock_high__reach_low", "高存量低触达：自产自销/虚假繁荣候选"
    if not stock_hi and reach_hi:
        return "stock_low__reach_high", "低存量高触达：小而精破圈候选"
    return "stock_low__reach_low", "低存量低触达：近乎隐形候选"


def review_priority(row: dict[str, Any]) -> str:
    q = row["quadrant"]
    risk = row.get("reach_noise_risk")
    low_play_ratio = float(row.get("low_relevance_play_ratio") or 0)
    likely_play = int(row.get("likely_total_play") or 0)
    raw_delta = int(row.get("raw_to_likely_tier_delta") or 0)
    inclusive_tier = row.get("inclusive_reach_tier")
    likely_tier = row.get("likely_reach_tier")

    if q == "stock_high__reach_low":
        return "P0_stock_high_reach_low"
    if risk == "high" and (low_play_ratio >= 0.8 or raw_delta <= -2):
        return "P0_noise_or_tier_drop"
    if q == "stock_low__reach_high":
        return "P1_low_stock_high_reach"
    if likely_tier != inclusive_tier and likely_play < 10_000_000:
        return "P1_inclusive_sensitive"
    if risk == "high":
        return "P2_noise_risk"
    return "P3_normal"


def build_matrix(scale_rows: list[dict[str, Any]], reach_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scale_by_id = {int(r["project_id"]): r for r in scale_rows}
    reach_by_id = {int(r["project_id"]): r for r in reach_rows}
    missing_scale = sorted(set(reach_by_id) - set(scale_by_id))
    missing_reach = sorted(set(scale_by_id) - set(reach_by_id))
    if missing_scale or missing_reach:
        raise ValueError(f"ID mismatch missing_scale={missing_scale} missing_reach={missing_reach}")

    matrix: list[dict[str, Any]] = []
    for pid in sorted(scale_by_id):
        s = scale_by_id[pid]
        r = reach_by_id[pid]
        s_tier = s.get("scale_video_count_tier", "unavailable")
        l_tier = r.get("likely_reach_tier", "reach_unknown")
        stock_b = stock_band(s_tier)
        reach_b = reach_band(l_tier)
        q, q_label = quadrant(stock_b, reach_b)
        row = {
            "project_id": pid,
            "project_name": s.get("project_name") or r.get("project_name"),
            "project_name_en": s.get("project_name_en") or r.get("project_name_en"),
            "list_type": s.get("list_type") or r.get("list_type"),
            "category": s.get("category") or r.get("category"),
            # Stock axis
            "scale_data_state": s.get("scale_data_state"),
            "scale_video_count_best": s.get("scale_video_count_best"),
            "scale_video_count_tier": s_tier,
            "stock_band": stock_b,
            "scale_best_hashtag": s.get("scale_best_hashtag"),
            "scale_best_challenge_id": s.get("scale_best_challenge_id"),
            "scale_terms_clean": s.get("terms_clean"),
            "scale_terms_noisy": s.get("terms_noisy"),
            "scale_terms_unavailable_or_failed": s.get("terms_unavailable_or_failed"),
            # Primary reach axis: likely relevance only
            "likely_reach_tier": l_tier,
            "likely_reach_score": r.get("likely_reach_score"),
            "likely_total_play": r.get("likely_total_play"),
            "likely_unique_videos": r.get("likely_unique_videos"),
            "likely_max_play": r.get("likely_max_play"),
            "likely_p95_play": r.get("likely_p95_play"),
            "likely_videos_ge_100k": r.get("likely_videos_ge_100k"),
            "likely_play_ratio": r.get("likely_play_ratio"),
            "likely_video_ratio": r.get("likely_video_ratio"),
            "reach_band": reach_b,
            # Context / diagnostics
            "raw_reach_tier": r.get("raw_reach_tier"),
            "raw_total_play": r.get("raw_total_play"),
            "inclusive_reach_tier": r.get("inclusive_reach_tier"),
            "inclusive_total_play": r.get("inclusive_total_play"),
            "low_relevance_play_ratio": r.get("low_relevance_play_ratio"),
            "reach_noise_risk": r.get("reach_noise_risk"),
            "reach_tier_changed_after_relevance_filter": r.get("reach_tier_changed_after_relevance_filter"),
            "raw_to_likely_tier_delta": r.get("raw_to_likely_tier_delta"),
            "raw_unique_videos": r.get("raw_unique_videos"),
            "label_likely_relevant_rows": r.get("label_likely_relevant_rows"),
            "label_needs_review_rows": r.get("label_needs_review_rows"),
            "label_low_relevance_rows": r.get("label_low_relevance_rows"),
            "likely_top_video_id": r.get("likely_top_video_id"),
            "likely_top_video_url": r.get("likely_top_video_url"),
            "likely_top_video_desc": r.get("likely_top_video_desc"),
            "raw_top_video_url": r.get("raw_top_video_url"),
            "inclusive_top_video_url": r.get("inclusive_top_video_url"),
            # First-draft 2×2 verdict
            "quadrant": q,
            "quadrant_label": q_label,
            "review_priority": "",  # filled below
            "matrix_note": "first-draft stock×reach matrix; stock=hashtag statsV2 videoCount, reach=likely_relevant playCount; requires targeted manual review before final tiering",
        }
        row["review_priority"] = review_priority(row)
        matrix.append(row)
    return matrix


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
        "method": {
            "stock_axis": "hashtag statsV2.videoCount from project_hashtag_scale_summary; tier=head/mid/long_tail/near_invisible",
            "reach_axis": "likely_relevant playCount from project_reach_relevance_aware; raw/inclusive/low retained as diagnostics",
            "quadrant_rule": "stock_high=head+mid; reach_high=top_20pct+high_20_40pct; middle/lower/bottom are review-conservative lower side in first-draft 2x2",
        },
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_int(v: Any) -> str:
    if v is None or v == "":
        return "NA"
    try:
        return f"{int(float(v)):,}"
    except Exception:
        return str(v)


def fmt_pct(v: Any) -> str:
    if v is None or v == "":
        return "NA"
    try:
        return f"{float(v) * 100:.1f}%"
    except Exception:
        return str(v)


def write_report(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    q_counts = Counter(r["quadrant"] for r in rows)
    priority_counts = Counter(r["review_priority"] for r in rows)
    stock_counts = Counter(r["scale_video_count_tier"] for r in rows)
    reach_counts = Counter(r["likely_reach_tier"] for r in rows)

    by_q = {q: [r for r in rows if r["quadrant"] == q] for q in q_counts}
    for q in by_q:
        by_q[q].sort(key=lambda r: (REACH_ORDER.get(r["likely_reach_tier"], 0), int(r.get("likely_total_play") or 0)), reverse=True)

    lines: list[str] = []
    lines.append("# 存量 × 触达二维分层草表")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：`project_hashtag_scale_summary` + `project_reach_relevance_aware`。  ")
    lines.append("> 性质：初版草表，供下一步定点人工核查；不是正式结论。")
    lines.append("")
    lines.append("## 1. 口径")
    lines.append("")
    lines.append("- 存量轴：hashtag challenge `statsV2.videoCount`，优先 clean tag；`head/mid/long_tail/near_invisible`。")
    lines.append("- 触达轴：`likely_relevant` 视频的 playCount 聚合与 cohort-relative tier；raw/inclusive/low 只作诊断。")
    lines.append("- 初版 2×2：`head+mid` 视作 stock_high；`top_20pct+high_20_40pct` 视作 reach_high；中间档先保守放入 lower side，待人工核查再定。")
    lines.append("- 特别注意：存量不是传播成功，触达不是受众出海；后续还要做重点视频人工核查与评论语言小样本。")
    lines.append("")
    lines.append("## 2. 分布总览")
    lines.append("")
    lines.append("### Quadrant")
    for q in ["stock_high__reach_high", "stock_high__reach_low", "stock_low__reach_high", "stock_low__reach_low"]:
        lines.append(f"- `{q}`: {q_counts.get(q, 0)}")
    lines.append("")
    lines.append("### Stock tier")
    for k in ["head", "mid", "long_tail", "near_invisible", "unavailable"]:
        lines.append(f"- `{k}`: {stock_counts.get(k, 0)}")
    lines.append("")
    lines.append("### Likely reach tier")
    for k in ["top_20pct_reach", "high_20_40pct_reach", "middle_40_70pct_reach", "lower_70_90pct_reach", "bottom_10pct_reach"]:
        lines.append(f"- `{k}`: {reach_counts.get(k, 0)}")
    lines.append("")
    lines.append("### Review priority")
    for k, v in priority_counts.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    section_names = {
        "stock_high__reach_high": "真·规模化出海候选：高存量 × 高触达",
        "stock_high__reach_low": "重点风险：高存量 × 低/中触达（自产自销/虚假繁荣候选）",
        "stock_low__reach_high": "小而精破圈候选：低/中存量 × 高触达",
        "stock_low__reach_low": "近乎隐形候选：低/中存量 × 低/中触达",
    }
    lines.append("## 3. 四象限草表")
    for q in ["stock_high__reach_high", "stock_high__reach_low", "stock_low__reach_high", "stock_low__reach_low"]:
        lines.append("")
        lines.append(f"### {section_names[q]}")
        xs = by_q.get(q, [])
        if not xs:
            lines.append("- 暂无。")
            continue
        for r in xs:
            lines.append(
                f"- **{r['project_name']}** ({r['list_type']}): "
                f"stock={r['scale_video_count_tier']} #{r['scale_best_hashtag']} {fmt_int(r['scale_video_count_best'])}; "
                f"reach={r['likely_reach_tier']} likely_play={fmt_int(r['likely_total_play'])}; "
                f"likely_ratio={fmt_pct(r['likely_play_ratio'])}; low_play_ratio={fmt_pct(r['low_relevance_play_ratio'])}; "
                f"risk={r['reach_noise_risk']}; review={r['review_priority']}"
            )
    lines.append("")
    lines.append("## 4. 人工核查优先级建议")
    lines.append("")
    p0 = [r for r in rows if str(r["review_priority"]).startswith("P0")]
    p1 = [r for r in rows if str(r["review_priority"]).startswith("P1")]
    lines.append("### P0：先查")
    if p0:
        for r in sorted(p0, key=lambda x: (x["review_priority"], -int(x.get("raw_total_play") or 0))):
            lines.append(f"- **{r['project_name']}**: {r['review_priority']}; quadrant={r['quadrant']}; raw={r['raw_reach_tier']}→likely={r['likely_reach_tier']}; low_play_ratio={fmt_pct(r['low_relevance_play_ratio'])}")
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("### P1：第二批")
    if p1:
        for r in sorted(p1, key=lambda x: (x["review_priority"], -int(x.get("likely_total_play") or 0)))[:15]:
            lines.append(f"- **{r['project_name']}**: {r['review_priority']}; quadrant={r['quadrant']}; stock={r['scale_video_count_tier']}; likely={r['likely_reach_tier']}; inclusive={r['inclusive_reach_tier']}")
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 5. 下一步")
    lines.append("")
    lines.append("1. 从 P0/P1 项目抽 `likely_top_video`、`raw_top_video`、`inclusive_top_video`，生成人工核查优先视频表。")
    lines.append("2. 人工复核高噪声和象限异常项目，确认是否因撞词/泛词导致错位。")
    lines.append("3. 回流核查标签后锁定正式分层；再挑代表项做评论区语言小样本。")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=Path, default=Path("data/derived/project_hashtag_scale_summary.json"))
    ap.add_argument("--reach", type=Path, default=Path("data/derived/project_reach_relevance_aware.json"))
    ap.add_argument("--out-csv", type=Path, default=Path("data/derived/project_stock_reach_matrix.csv"))
    ap.add_argument("--out-json", type=Path, default=Path("data/derived/project_stock_reach_matrix.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/存量触达二维分层草表.md"))
    args = ap.parse_args()

    rows = build_matrix(load_rows(args.scale), load_rows(args.reach))
    write_csv(rows, args.out_csv)
    write_json(rows, args.out_json)
    write_report(rows, args.out_report)
    print(f"wrote matrix rows={len(rows)}")
    print("quadrants", dict(Counter(r["quadrant"] for r in rows)))
    print("review_priority", dict(Counter(r["review_priority"] for r in rows)))


if __name__ == "__main__":
    main()
