#!/usr/bin/env python3
"""Apply returned manual review labels to TikTok relevance labels and rebuild reach/matrix.

Inputs:
- data/derived/video_relevance_labels.ndjson
- external/人工核查合并结果.csv (or --manual-csv)
- data/derived/project_hashtag_scale_summary.json

Outputs are additive derived artifacts; raw baseline is never modified.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LABELS = ROOT / "data" / "derived" / "video_relevance_labels.ndjson"
DEFAULT_MANUAL = ROOT / "data" / "derived" / "manual_review_returned_20260619.csv"
DEFAULT_SCALE = ROOT / "data" / "derived" / "project_hashtag_scale_summary.json"
DEFAULT_OUT_DIR = ROOT / "data" / "derived"

LABEL_MAP = {
    "相关": "likely_relevant",
    "不相关": "low_relevance",
    "拿不准": "needs_review",
    "relevant": "likely_relevant",
    "irrelevant": "low_relevance",
    "uncertain": "needs_review",
}
LABEL_BUCKETS = {
    "raw": {"likely_relevant", "needs_review", "low_relevance"},
    "likely": {"likely_relevant"},
    "inclusive": {"likely_relevant", "needs_review"},
    "low": {"low_relevance"},
}
REACH_ORDER = {
    "top_20pct_reach": 5,
    "high_20_40pct_reach": 4,
    "middle_40_70pct_reach": 3,
    "lower_70_90pct_reach": 2,
    "bottom_10pct_reach": 1,
    "no_videos": 0,
}


def iter_ndjson(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Bad JSON at {path}:{line_no}: {e}") from e


def write_ndjson(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_int(v: Any) -> int:
    try:
        if v is None or v == "":
            return 0
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return int(xs[lo])
    return int(round(xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)))


def reach_score(row: dict[str, Any], prefix: str) -> float:
    return (
        math.log10(row.get(f"{prefix}_total_play", 0) + 1) * 0.35
        + math.log10(row.get(f"{prefix}_p95_play", 0) + 1) * 0.35
        + math.log10(row.get(f"{prefix}_max_play", 0) + 1) * 0.20
        + math.log10(row.get(f"{prefix}_videos_ge_100k", 0) + 1) * 0.10
    )


def assign_relative_tiers(rows: list[dict[str, Any]], prefix: str, out_field: str, score_field: str) -> None:
    valid = [r for r in rows if r.get(f"{prefix}_unique_videos", 0) > 0]
    ordered = sorted(valid, key=lambda r: reach_score(r, prefix), reverse=True)
    n = len(ordered)
    for r in rows:
        r[out_field] = "no_videos"
        r[score_field] = 0.0
    for i, r in enumerate(ordered):
        pct = (i + 1) / max(n, 1)
        if pct <= 0.20:
            tier = "top_20pct_reach"
        elif pct <= 0.40:
            tier = "high_20_40pct_reach"
        elif pct <= 0.70:
            tier = "middle_40_70pct_reach"
        elif pct <= 0.90:
            tier = "lower_70_90pct_reach"
        else:
            tier = "bottom_10pct_reach"
        r[out_field] = tier
        r[score_field] = round(reach_score(r, prefix), 6)


def load_manual(path: Path) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    by_url: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            url = (row.get("video_url") or row.get("web_url") or "").strip()
            rel = (row.get("manual_relevance") or row.get("manual_label") or "").strip()
            mapped = LABEL_MAP.get(rel)
            out = dict(row)
            out["video_url"] = url
            out["manual_relevance_mapped_label"] = mapped or ""
            rows.append(out)
            if url and mapped:
                by_url[url] = out
    return by_url, rows


def apply_manual(labels_path: Path, manual_by_url: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corrected: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    for row in iter_ndjson(labels_path):
        url = str(row.get("web_url") or "")
        manual = manual_by_url.get(url)
        out = dict(row)
        out["quality_label_auto"] = row.get("quality_label")
        out["manual_review_applied"] = False
        if manual:
            new_label = manual["manual_relevance_mapped_label"]
            old_label = str(row.get("quality_label") or "")
            out["quality_label"] = new_label
            out["manual_review_applied"] = True
            out["manual_relevance_raw"] = manual.get("manual_relevance", "")
            out["manual_noise_type"] = manual.get("manual_noise_type", "")
            out["manual_reviewer"] = manual.get("reviewer", "")
            out["manual_notes"] = manual.get("notes", "")
            out["manual_content_language"] = manual.get("content_language", "")
            out["manual_audience_language"] = manual.get("audience_language", "")
            out["quality_reasons"] = list(row.get("quality_reasons") or []) + [f"manual_override:{old_label}->{new_label}"]
            applied.append({
                "project_id": row.get("project_id"),
                "project_name": row.get("project_name"),
                "web_url": url,
                "video_id": row.get("video_id"),
                "auto_label": old_label,
                "manual_label": new_label,
                "manual_relevance_raw": manual.get("manual_relevance", ""),
                "manual_noise_type": manual.get("manual_noise_type", ""),
                "stats_play_count": parse_int(row.get("stats_play_count")),
                "label_changed": old_label != new_label,
            })
        corrected.append(out)
    return corrected, applied


def metric_for(rows: list[dict[str, Any]], labels: set[str]) -> dict[str, Any]:
    best: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("quality_label") not in labels:
            continue
        vid = str(r.get("video_id") or "")
        if not vid:
            continue
        cur = best.get(vid)
        if cur is None or parse_int(r.get("stats_play_count")) > parse_int(cur.get("stats_play_count")):
            best[vid] = r
    xs = list(best.values())
    plays = [parse_int(r.get("stats_play_count")) for r in xs]
    diggs = [parse_int(r.get("stats_digg_count")) for r in xs]
    comments = [parse_int(r.get("stats_comment_count")) for r in xs]
    shares = [parse_int(r.get("stats_share_count")) for r in xs]
    top = max(xs, key=lambda r: parse_int(r.get("stats_play_count"))) if xs else {}
    return {
        "unique_videos": len(xs),
        "total_play": sum(plays),
        "median_play": int(median(plays)) if plays else 0,
        "mean_play": int(round(mean(plays))) if plays else 0,
        "p75_play": percentile(plays, 0.75),
        "p90_play": percentile(plays, 0.90),
        "p95_play": percentile(plays, 0.95),
        "p99_play": percentile(plays, 0.99),
        "max_play": max(plays) if plays else 0,
        "videos_ge_1k": sum(p >= 1_000 for p in plays),
        "videos_ge_10k": sum(p >= 10_000 for p in plays),
        "videos_ge_100k": sum(p >= 100_000 for p in plays),
        "videos_ge_1m": sum(p >= 1_000_000 for p in plays),
        "zero_play_videos": sum(p == 0 for p in plays),
        "total_digg": sum(diggs),
        "total_comment": sum(comments),
        "total_share": sum(shares),
        "max_digg": max(diggs) if diggs else 0,
        "max_comment": max(comments) if comments else 0,
        "max_share": max(shares) if shares else 0,
        "top_video_id": top.get("video_id", ""),
        "top_video_url": top.get("web_url", ""),
        "top_video_desc": str(top.get("desc", ""))[:220] if top else "",
    }


def derive_reach(labels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in labels:
        by_project[int(r["project_id"])].append(r)
    rows: list[dict[str, Any]] = []
    for pid in sorted(by_project):
        xs = by_project[pid]
        base: dict[str, Any] = {
            "project_id": pid,
            "project_name": xs[0].get("project_name", ""),
            "project_name_en": xs[0].get("project_name_en", ""),
            "list_type": xs[0].get("list_type", ""),
            "category": xs[0].get("category", ""),
        }
        label_counts = Counter(r.get("quality_label") for r in xs)
        auto_counts = Counter(r.get("quality_label_auto", r.get("quality_label")) for r in xs)
        manual_xs = [r for r in xs if r.get("manual_review_applied")]
        base.update({
            "label_likely_relevant_rows": label_counts.get("likely_relevant", 0),
            "label_needs_review_rows": label_counts.get("needs_review", 0),
            "label_low_relevance_rows": label_counts.get("low_relevance", 0),
            "auto_label_likely_relevant_rows": auto_counts.get("likely_relevant", 0),
            "auto_label_needs_review_rows": auto_counts.get("needs_review", 0),
            "auto_label_low_relevance_rows": auto_counts.get("low_relevance", 0),
            "manual_reviewed_rows": len(manual_xs),
            "manual_related_rows": sum(r.get("quality_label") == "likely_relevant" for r in manual_xs),
            "manual_uncertain_rows": sum(r.get("quality_label") == "needs_review" for r in manual_xs),
            "manual_unrelated_rows": sum(r.get("quality_label") == "low_relevance" for r in manual_xs),
            "manual_changed_rows": sum(r.get("quality_label") != r.get("quality_label_auto") for r in manual_xs),
        })
        for prefix, bucket_labels in LABEL_BUCKETS.items():
            m = metric_for(xs, bucket_labels)
            for k, v in m.items():
                base[f"{prefix}_{k}"] = v
        raw_n = base.get("raw_unique_videos", 0) or 0
        base["likely_video_ratio"] = round(base.get("likely_unique_videos", 0) / raw_n, 4) if raw_n else 0
        base["inclusive_video_ratio"] = round(base.get("inclusive_unique_videos", 0) / raw_n, 4) if raw_n else 0
        base["low_relevance_video_ratio"] = round(base.get("low_unique_videos", 0) / raw_n, 4) if raw_n else 0
        raw_play = base.get("raw_total_play", 0) or 0
        base["likely_play_ratio"] = round(base.get("likely_total_play", 0) / raw_play, 4) if raw_play else 0
        base["inclusive_play_ratio"] = round(base.get("inclusive_total_play", 0) / raw_play, 4) if raw_play else 0
        base["low_relevance_play_ratio"] = round(base.get("low_total_play", 0) / raw_play, 4) if raw_play else 0
        base["reach_noise_risk"] = (
            "high" if base["low_relevance_play_ratio"] >= 0.50 or base["low_relevance_video_ratio"] >= 0.60 else
            "medium" if base["low_relevance_play_ratio"] >= 0.25 or base["low_relevance_video_ratio"] >= 0.35 else
            "low"
        )
        rows.append(base)
    assign_relative_tiers(rows, "raw", "raw_reach_tier", "raw_reach_score")
    assign_relative_tiers(rows, "likely", "likely_reach_tier", "likely_reach_score")
    assign_relative_tiers(rows, "inclusive", "inclusive_reach_tier", "inclusive_reach_score")
    for r in rows:
        r["reach_tier_changed_after_relevance_filter"] = r["raw_reach_tier"] != r["likely_reach_tier"]
        r["raw_to_likely_tier_delta"] = REACH_ORDER.get(r["likely_reach_tier"], 0) - REACH_ORDER.get(r["raw_reach_tier"], 0)
    return rows


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
    if row.get("manual_reviewed_rows", 0) and row.get("manual_related_rows", 0) == 0 and row.get("manual_unrelated_rows", 0) >= 3:
        return "P0_manual_false_breakout"
    if row["quadrant"] == "stock_high__reach_low":
        return "P0_stock_high_reach_low"
    if row.get("reach_noise_risk") == "high" and (float(row.get("low_relevance_play_ratio") or 0) >= 0.8 or int(row.get("raw_to_likely_tier_delta") or 0) <= -2):
        return "P0_noise_or_tier_drop"
    if row["quadrant"] == "stock_low__reach_high":
        return "P1_low_stock_high_reach"
    if row.get("reach_noise_risk") == "high":
        return "P2_noise_risk"
    return "P3_normal"


def load_scale(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data["rows"] if isinstance(data, dict) and "rows" in data else data)


def build_matrix(scale_rows: list[dict[str, Any]], reach_rows: list[dict[str, Any]], prior_matrix_path: Path | None = None) -> list[dict[str, Any]]:
    scale_by_id = {int(r["project_id"]): r for r in scale_rows}
    reach_by_id = {int(r["project_id"]): r for r in reach_rows}
    prior_by_id: dict[int, dict[str, Any]] = {}
    if prior_matrix_path and prior_matrix_path.exists():
        with prior_matrix_path.open("r", encoding="utf-8-sig", newline="") as f:
            prior_by_id = {int(r["project_id"]): r for r in csv.DictReader(f)}
    out: list[dict[str, Any]] = []
    for pid in sorted(scale_by_id):
        s = scale_by_id[pid]
        r = reach_by_id[pid]
        prior = prior_by_id.get(pid, {})
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
            "scale_data_state": s.get("scale_data_state"),
            "scale_video_count_best": s.get("scale_video_count_best"),
            "scale_video_count_tier": s_tier,
            "stock_band": stock_b,
            "scale_best_hashtag": s.get("scale_best_hashtag"),
            "likely_reach_tier_statistical": l_tier,
            "likely_reach_tier": l_tier,
            "likely_reach_score": r.get("likely_reach_score"),
            "likely_total_play": r.get("likely_total_play"),
            "likely_unique_videos": r.get("likely_unique_videos"),
            "likely_max_play": r.get("likely_max_play"),
            "likely_p95_play": r.get("likely_p95_play"),
            "likely_videos_ge_100k": r.get("likely_videos_ge_100k"),
            "likely_play_ratio": r.get("likely_play_ratio"),
            "likely_video_ratio": r.get("likely_video_ratio"),
            "reach_band_statistical": reach_b,
            "reach_band": reach_b,
            "raw_reach_tier": r.get("raw_reach_tier"),
            "raw_total_play": r.get("raw_total_play"),
            "inclusive_reach_tier": r.get("inclusive_reach_tier"),
            "inclusive_total_play": r.get("inclusive_total_play"),
            "low_relevance_play_ratio": r.get("low_relevance_play_ratio"),
            "reach_noise_risk": r.get("reach_noise_risk"),
            "raw_to_likely_tier_delta": r.get("raw_to_likely_tier_delta"),
            "raw_unique_videos": r.get("raw_unique_videos"),
            "label_likely_relevant_rows": r.get("label_likely_relevant_rows"),
            "label_needs_review_rows": r.get("label_needs_review_rows"),
            "label_low_relevance_rows": r.get("label_low_relevance_rows"),
            "auto_label_likely_relevant_rows": r.get("auto_label_likely_relevant_rows"),
            "auto_label_needs_review_rows": r.get("auto_label_needs_review_rows"),
            "auto_label_low_relevance_rows": r.get("auto_label_low_relevance_rows"),
            "manual_reviewed_rows": r.get("manual_reviewed_rows"),
            "manual_related_rows": r.get("manual_related_rows"),
            "manual_uncertain_rows": r.get("manual_uncertain_rows"),
            "manual_unrelated_rows": r.get("manual_unrelated_rows"),
            "manual_changed_rows": r.get("manual_changed_rows"),
            "likely_top_video_url": r.get("likely_top_video_url"),
            "likely_top_video_desc": r.get("likely_top_video_desc"),
            "manual_audit_verdict": "",
            "manual_audit_note": "",
            "quadrant": q,
            "quadrant_label": q_label,
            "previous_quadrant": prior.get("quadrant", ""),
            "previous_likely_reach_tier": prior.get("likely_reach_tier", ""),
            "previous_likely_total_play": parse_int(prior.get("likely_total_play")),
            "manual_corrected_quadrant_changed": bool(prior) and prior.get("quadrant") != q,
            "manual_corrected_reach_tier_changed": bool(prior) and prior.get("likely_reach_tier") != l_tier,
            "manual_reach_play_delta": r.get("likely_total_play", 0) - parse_int(prior.get("likely_total_play")) if prior else 0,
            "review_priority": "",
            "matrix_note": "manual-corrected stock×reach matrix; reviewed videos override auto labels; unreviewed videos keep auto labels",
        }
        # If a targeted audit of a previous breakout candidate finds zero relevant
        # examples among high-impact sampled evidence, treat the project's breakout
        # as manually falsified even if unreviewed automatic likely rows remain.
        # This preserves the statistical fields while the final quadrant follows
        # the human-validated interpretation.
        false_breakout_names = {"麦西热甫", "中国水密隔舱福船制造技艺", "中国珠算"}
        if row["project_name"] in false_breakout_names:
            row["manual_audit_verdict"] = "false_breakout_confirmed"
            row["manual_audit_note"] = "targeted human audit found the sampled high-reach breakout evidence unrelated; remaining auto-likely signal is not trusted for final quadrant"
            row["reach_band"] = "reach_low"
            row["likely_reach_tier"] = "manual_demoted_false_breakout"
            row["quadrant"] = "stock_low__reach_low" if row["stock_band"] != "stock_high" else "stock_high__reach_low"
            row["quadrant_label"] = "低存量低触达：近乎隐形候选" if row["stock_band"] != "stock_high" else "高存量低触达：自产自销/虚假繁荣候选"
            row["manual_corrected_quadrant_changed"] = bool(prior) and prior.get("quadrant") != row["quadrant"]
            row["manual_corrected_reach_tier_changed"] = True
            row["matrix_note"] += "; targeted audit can demote false breakout candidates beyond row-level relabeling"
        row["review_priority"] = review_priority(row)
        out.append(row)
    return out


def write_report(summary: dict[str, Any], matrix: list[dict[str, Any]], applied: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    q_counts = Counter(r["quadrant"] for r in matrix)
    changed_q = [r for r in matrix if r.get("manual_corrected_quadrant_changed")]
    changed_tier = [r for r in matrix if r.get("manual_corrected_reach_tier_changed")]
    false_breakout = [r for r in matrix if r.get("review_priority") == "P0_manual_false_breakout"]
    by_play_drop = sorted(matrix, key=lambda r: r.get("manual_reach_play_delta", 0))[:15]
    conflict_projects = ["麦西热甫", "中国水密隔舱福船制造技艺", "中国珠算"]

    lines = [
        "# TikTok 人工核查回流后的触达修正（2026-06-19）",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        "> 口径：`manual_relevance` 覆盖自动 `quality_label`；未核查视频保留自动标签；raw 不删。",
        "",
        "## 1. 回流覆盖",
        "",
        f"- 人工 CSV 行数：{summary['manual_rows']}",
        f"- 成功匹配 baseline URL：{summary['manual_matched_urls']}",
        f"- 未匹配 URL：{summary['manual_unmatched_urls']}",
        f"- 实际应用覆盖行：{summary['manual_applied_rows']}",
        f"- 其中改写自动标签：{summary['manual_changed_rows']}",
        f"- 人工相关/拿不准/不相关：{summary['manual_related_rows']} / {summary['manual_uncertain_rows']} / {summary['manual_unrelated_rows']}",
        "",
        "## 2. 修正后的象限分布",
        "",
    ]
    for q in ["stock_high__reach_high", "stock_high__reach_low", "stock_low__reach_high", "stock_low__reach_low"]:
        lines.append(f"- `{q}`: {q_counts.get(q, 0)}")
    lines += ["", "## 3. 关键冲突项目确认", ""]
    for name in conflict_projects:
        r = next((x for x in matrix if x["project_name"] == name), None)
        if not r:
            continue
        lines.append(
            f"- **{name}**: manual={r['manual_related_rows']}相关/{r['manual_uncertain_rows']}拿不准/{r['manual_unrelated_rows']}不相关；"
            f"likely_play {r['previous_likely_total_play']:,} → {r['likely_total_play']:,}；"
            f"tier {r['previous_likely_reach_tier']} → {r['likely_reach_tier']}；"
            f"quadrant {r['previous_quadrant']} → {r['quadrant']}。"
        )
    lines += [
        "",
        "结论：麦西热甫、福船、珠算此前的“低存量高触达/小而精破圈”是典型假性高触达；抽查确认由噪声、衍生品或撞词内容撑起，应作为“看似破圈实为噪声”的方法论发现保留。",
        "",
        "珠算人工口径：UNESCO 项是“算盘被实际使用的计算实践”。判断尺子是算盘是否被拨、被用来算；拨珠运算算相关，算盘摆着/装饰/心算/闪卡/珠心算衍生训练不算。出现算盘 ≠ 使用算盘。",
        "",
        "## 4. 象限/触达档变动项目",
        "",
    ]
    if changed_q:
        for r in changed_q:
            lines.append(f"- **{r['project_name']}**: {r['previous_quadrant']} → {r['quadrant']}; likely_play_delta={r['manual_reach_play_delta']:,}")
    else:
        lines.append("- 无项目跨 2×2 象限；但若干项目 reach tier 下调，见下。")
    lines += ["", "### Reach tier changed", ""]
    for r in changed_tier:
        lines.append(f"- **{r['project_name']}**: {r['previous_likely_reach_tier']} → {r['likely_reach_tier']}; likely_play {r['previous_likely_total_play']:,} → {r['likely_total_play']:,}")
    lines += ["", "## 5. likely 触达降幅最大", ""]
    for r in by_play_drop:
        if r.get("manual_reach_play_delta", 0) < 0:
            lines.append(f"- **{r['project_name']}**: delta={r['manual_reach_play_delta']:,}; reviewed={r['manual_reviewed_rows']}; unrelated={r['manual_unrelated_rows']}; quadrant={r['quadrant']}")
    lines += ["", "## 6. 输出", "", "- `data/derived/video_relevance_labels_manual_corrected.ndjson`", "- `data/derived/manual_review_returned_applied.csv`", "- `data/derived/project_reach_manual_corrected.csv/json`", "- `data/derived/project_stock_reach_matrix_manual_corrected.csv/json`"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    ap.add_argument("--manual-csv", type=Path, default=DEFAULT_MANUAL)
    ap.add_argument("--scale", type=Path, default=DEFAULT_SCALE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--report", type=Path, default=ROOT / "docs" / "人工核查回流触达修正_20260619.md")
    args = ap.parse_args()

    manual_by_url, manual_rows = load_manual(args.manual_csv)
    corrected, applied = apply_manual(args.labels, manual_by_url)
    applied_urls = {r["web_url"] for r in applied}
    unmatched = sorted(set(manual_by_url) - applied_urls)

    reach = derive_reach(corrected)
    matrix = build_matrix(load_scale(args.scale), reach, args.out_dir / "project_stock_reach_matrix.csv")

    out = args.out_dir
    write_ndjson(corrected, out / "video_relevance_labels_manual_corrected.ndjson")
    write_csv(applied, out / "manual_review_returned_applied.csv")
    write_json({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manual_rows": len(manual_rows),
        "manual_urls_with_valid_label": len(manual_by_url),
        "unmatched_urls": unmatched,
        "note": "manual_relevance overrides quality_label only for reviewed rows; unreviewed labels remain automatic.",
    }, out / "manual_review_returned_summary.json")
    write_csv(reach, out / "project_reach_manual_corrected.csv")
    write_json({"generated_at": datetime.now(timezone.utc).isoformat(), "rows": reach}, out / "project_reach_manual_corrected.json")
    write_csv(matrix, out / "project_stock_reach_matrix_manual_corrected.csv")
    write_json({"generated_at": datetime.now(timezone.utc).isoformat(), "rows": matrix}, out / "project_stock_reach_matrix_manual_corrected.json")

    label_counts = Counter(r.get("quality_label") for r in corrected)
    applied_counts = Counter(r.get("manual_label") for r in applied)
    summary = {
        "manual_rows": len(manual_rows),
        "manual_matched_urls": len(applied_urls),
        "manual_unmatched_urls": len(unmatched),
        "manual_applied_rows": len(applied),
        "manual_changed_rows": sum(r["label_changed"] for r in applied),
        "manual_related_rows": applied_counts.get("likely_relevant", 0),
        "manual_uncertain_rows": applied_counts.get("needs_review", 0),
        "manual_unrelated_rows": applied_counts.get("low_relevance", 0),
        "corrected_label_counts": dict(label_counts),
        "quadrant_counts": dict(Counter(r["quadrant"] for r in matrix)),
        "unmatched_urls": unmatched,
    }
    write_report(summary, matrix, applied, args.report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
