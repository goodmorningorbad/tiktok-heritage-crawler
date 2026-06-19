#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply a China-signal hard filter to TikTok likely reach.

Definition requested by the research lead:
- A likely_relevant video remains in the cleaned reach pool only if it has
  `china_context_hit == True` OR `has_cjk_desc == True`.
- Machine-likely videos without either signal are treated as text-level collision
  noise for the signal-filtered reach estimate.

Outputs:
- data/derived/tiktok_china_signal_filtered_reach_comparison_20260620.csv/json
- data/derived/tiktok_china_signal_filtered_matrix_20260620.csv/json
- data/derived/tiktok_china_signal_filtered_out_high_noise_review_sample_20260620.csv
- docs/TikTok_china_signal_filter_recalculation_20260620.md
- mirrored copies under data/final/tiktok_closed_20260619/{tables,manual_review,docs}
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FINAL_DIR = ROOT / "data/final/tiktok_closed_20260619"
ROW_LABELS = FINAL_DIR / "row_labels/tiktok_video_relevance_labels_final.ndjson"
FINAL_FINDINGS = FINAL_DIR / "tables/tiktok_final_project_findings.csv"
FINAL_MATRIX = FINAL_DIR / "tables/tiktok_project_stock_reach_matrix_final.csv"
DERIVED = ROOT / "data/derived"
DOCS = ROOT / "docs"
DATE = "20260620"

REACH_ORDER = {
    "top_20pct_reach": 5,
    "high_20_40pct_reach": 4,
    "middle_40_70pct_reach": 3,
    "lower_70_90pct_reach": 2,
    "bottom_10pct_reach": 1,
    "no_videos": 0,
}

LIMITATION_NOTE = (
    "经中国信号过滤（china_context_hit 或 has_cjk_desc），但未全量人工核查；"
    "中低播放段可能仍有残余噪声。文本撞词噪声（如 papercut/calligraphy/taichi 等）"
    "可有效识别并过滤；残余误差主要来自无文本线索、纯画面是中国非遗的视频，文本方法无法判定。"
)


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


def reach_score(row: dict[str, Any], prefix: str = "signal") -> float:
    return (
        math.log10(parse_int(row.get(f"{prefix}_likely_total_play")) + 1) * 0.35
        + math.log10(parse_int(row.get(f"{prefix}_likely_p95_play")) + 1) * 0.35
        + math.log10(parse_int(row.get(f"{prefix}_likely_max_play")) + 1) * 0.20
        + math.log10(parse_int(row.get(f"{prefix}_likely_videos_ge_100k")) + 1) * 0.10
    )


def assign_tiers(rows: list[dict[str, Any]]) -> None:
    valid = [r for r in rows if parse_int(r.get("signal_likely_unique_videos")) > 0]
    ordered = sorted(valid, key=lambda r: reach_score(r), reverse=True)
    n = len(ordered)
    for r in rows:
        r["signal_likely_reach_tier"] = "no_videos"
        r["signal_likely_reach_score"] = 0.0
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
        r["signal_likely_reach_tier"] = tier
        r["signal_likely_reach_score"] = round(reach_score(r), 6)


def reach_band(tier: str) -> str:
    if tier in {"top_20pct_reach", "high_20_40pct_reach"}:
        return "reach_high"
    if tier == "no_videos":
        return "reach_unknown"
    return "reach_low"


def quadrant(stock_band: str, reach_b: str) -> tuple[str, str]:
    stock_hi = stock_band == "stock_high"
    reach_hi = reach_b == "reach_high"
    if stock_hi and reach_hi:
        return "stock_high__reach_high", "真·规模化出海候选"
    if stock_hi and not reach_hi:
        return "stock_high__reach_low", "高存量低触达：自产自销/虚假繁荣候选"
    if not stock_hi and reach_hi:
        return "stock_low__reach_high", "低存量高触达：小而精破圈候选"
    return "stock_low__reach_low", "低存量低触达：近乎隐形候选"


def read_csv_by_name(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["project_name"]: r for r in csv.DictReader(f)}


def metric(records: list[dict[str, Any]]) -> dict[str, Any]:
    plays = [parse_int(r.get("stats_play_count")) for r in records]
    top = max(records, key=lambda r: parse_int(r.get("stats_play_count"))) if records else {}
    return {
        "unique_videos": len(records),
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
        "top_video_id": top.get("video_id", ""),
        "top_video_url": top.get("web_url", ""),
        "top_video_desc": str(top.get("desc", ""))[:220] if top else "",
    }


def better_record(a: dict[str, Any] | None, b: dict[str, Any]) -> dict[str, Any]:
    if a is None:
        return b
    return b if parse_int(b.get("stats_play_count")) > parse_int(a.get("stats_play_count")) else a


def load_likely_video_sets() -> tuple[dict[int, dict[str, Any]], dict[int, list[dict[str, Any]]]]:
    projects: dict[int, dict[str, Any]] = {}
    likely_rows_by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    videos: dict[int, dict[str, dict[str, Any]]] = defaultdict(dict)

    with ROW_LABELS.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            pid = int(d["project_id"])
            projects.setdefault(pid, {
                "project_id": pid,
                "project_name": d.get("project_name", ""),
                "project_name_en": d.get("project_name_en", ""),
                "list_type": d.get("list_type", ""),
                "category": d.get("category", ""),
            })
            if d.get("quality_label") != "likely_relevant":
                continue
            likely_rows_by_project[pid].append(d)
            vid = str(d.get("video_id") or "")
            if not vid:
                continue
            signal = bool(d.get("china_context_hit")) or bool(d.get("has_cjk_desc"))
            slot = videos[pid].setdefault(vid, {
                "video_id": vid,
                "any_signal": False,
                "best_signal_record": None,
                "best_no_signal_record": None,
                "best_any_record": None,
                "row_count": 0,
                "signal_row_count": 0,
                "no_signal_row_count": 0,
            })
            slot["row_count"] += 1
            slot["best_any_record"] = better_record(slot.get("best_any_record"), d)
            if signal:
                slot["any_signal"] = True
                slot["signal_row_count"] += 1
                slot["best_signal_record"] = better_record(slot.get("best_signal_record"), d)
            else:
                slot["no_signal_row_count"] += 1
                slot["best_no_signal_record"] = better_record(slot.get("best_no_signal_record"), d)

    for pid, info in projects.items():
        info["videos"] = videos.get(pid, {})
        info["likely_rows"] = likely_rows_by_project.get(pid, [])
    return projects, likely_rows_by_project


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for r in rows:
            for k in r:
                if k not in fields:
                    fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_outputs() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    findings = read_csv_by_name(FINAL_FINDINGS)
    matrix = read_csv_by_name(FINAL_MATRIX)
    projects, likely_rows_by_project = load_likely_video_sets()

    rows: list[dict[str, Any]] = []
    for pid in sorted(projects):
        info = projects[pid]
        name = info["project_name"]
        before = findings.get(name, {})
        mrow = matrix.get(name, {})
        vids = info["videos"]
        before_records = [v["best_any_record"] for v in vids.values() if v.get("best_any_record")]
        signal_records = [v["best_signal_record"] for v in vids.values() if v.get("any_signal") and v.get("best_signal_record")]
        filtered_records = [v["best_no_signal_record"] for v in vids.values() if not v.get("any_signal") and v.get("best_no_signal_record")]
        before_metric = metric(before_records)
        signal_metric = metric(signal_records)
        filtered_metric = metric(filtered_records)
        before_play = parse_int(before.get("final_likely_total_play") or before.get("likely_total_play") or before_metric["total_play"])
        signal_play = signal_metric["total_play"]
        filtered_play = filtered_metric["total_play"]
        before_unique = before_metric["unique_videos"]
        no_signal_unique_ratio = round(filtered_metric["unique_videos"] / before_unique, 4) if before_unique else 0
        no_signal_play_ratio = round(filtered_play / (signal_play + filtered_play), 4) if (signal_play + filtered_play) else 0
        row_count = len(likely_rows_by_project.get(pid, []))
        no_signal_row_count = sum(1 for r in likely_rows_by_project.get(pid, []) if not (bool(r.get("china_context_hit")) or bool(r.get("has_cjk_desc"))))
        row_no_signal_ratio = round(no_signal_row_count / row_count, 4) if row_count else 0
        row = {
            "project_id": pid,
            "project_name": name,
            "project_name_en": info.get("project_name_en", ""),
            "list_type": info.get("list_type", ""),
            "category": info.get("category", ""),
            "stock_band": mrow.get("stock_band", ""),
            "scale_video_count_best": mrow.get("scale_video_count_best", ""),
            "scale_video_count_tier": mrow.get("scale_video_count_tier", ""),
            "before_likely_total_play": before_play,
            "before_rowlabel_likely_total_play": before_metric["total_play"],
            "signal_likely_total_play": signal_play,
            "filtered_out_no_china_signal_play": filtered_play,
            "absolute_play_drop": before_play - signal_play,
            "play_retention_ratio": round(signal_play / before_play, 4) if before_play else 0,
            "play_drop_ratio": round((before_play - signal_play) / before_play, 4) if before_play else 0,
            "before_likely_unique_videos": before_unique,
            "signal_likely_unique_videos": signal_metric["unique_videos"],
            "filtered_out_no_china_signal_unique_videos": filtered_metric["unique_videos"],
            "likely_rows": row_count,
            "no_china_signal_likely_rows": no_signal_row_count,
            "no_china_signal_unique_ratio": no_signal_unique_ratio,
            "no_china_signal_play_ratio_rowlabel": no_signal_play_ratio,
            "no_china_signal_row_ratio": row_no_signal_ratio,
            "before_likely_reach_tier": before.get("likely_reach_tier_final") or mrow.get("likely_reach_tier") or before.get("likely_reach_tier_statistical", ""),
            "before_quadrant": before.get("quadrant") or mrow.get("quadrant", ""),
            "before_quadrant_label": before.get("quadrant_label") or mrow.get("quadrant_label", ""),
            "signal_likely_median_play": signal_metric["median_play"],
            "signal_likely_mean_play": signal_metric["mean_play"],
            "signal_likely_p75_play": signal_metric["p75_play"],
            "signal_likely_p90_play": signal_metric["p90_play"],
            "signal_likely_p95_play": signal_metric["p95_play"],
            "signal_likely_p99_play": signal_metric["p99_play"],
            "signal_likely_max_play": signal_metric["max_play"],
            "signal_likely_videos_ge_1k": signal_metric["videos_ge_1k"],
            "signal_likely_videos_ge_10k": signal_metric["videos_ge_10k"],
            "signal_likely_videos_ge_100k": signal_metric["videos_ge_100k"],
            "signal_likely_videos_ge_1m": signal_metric["videos_ge_1m"],
            "signal_likely_top_video_id": signal_metric["top_video_id"],
            "signal_likely_top_video_url": signal_metric["top_video_url"],
            "signal_likely_top_video_desc": signal_metric["top_video_desc"],
            "filter_note": LIMITATION_NOTE,
        }
        rows.append(row)

    assign_tiers(rows)
    for r in rows:
        rb = reach_band(r["signal_likely_reach_tier"])
        r["signal_reach_band"] = rb
        q, q_label = quadrant(r.get("stock_band", ""), rb)
        r["signal_quadrant"] = q
        r["signal_quadrant_label"] = q_label
        r["quadrant_changed_after_signal_filter"] = str(q != r.get("before_quadrant"))
        r["reach_tier_changed_after_signal_filter"] = str(r["signal_likely_reach_tier"] != r.get("before_likely_reach_tier"))
        before_tier = str(r.get("before_likely_reach_tier") or "")
        r["reach_tier_delta_after_signal_filter"] = REACH_ORDER.get(str(r["signal_likely_reach_tier"]), 0) - REACH_ORDER.get(before_tier, 0)
        r["high_noise_gt50pct_no_china_signal"] = str(r["no_china_signal_unique_ratio"] > 0.5)

    comparison = sorted(rows, key=lambda r: (parse_int(r["absolute_play_drop"]), parse_int(r["before_likely_total_play"])), reverse=True)
    matrix_rows = sorted(rows, key=lambda r: (r["signal_quadrant"], -parse_int(r["signal_likely_total_play"])))
    high_noise = [r for r in rows if r["no_china_signal_unique_ratio"] > 0.5]

    # Review sample: top 10 filtered-out, no-signal videos for each high-noise project.
    sample_rows: list[dict[str, Any]] = []
    for r in sorted(high_noise, key=lambda x: (-x["no_china_signal_unique_ratio"], -parse_int(x["filtered_out_no_china_signal_play"]))):
        pid = int(r["project_id"])
        vids = projects[pid]["videos"]
        filtered = [v["best_no_signal_record"] for v in vids.values() if not v.get("any_signal") and v.get("best_no_signal_record")]
        filtered = sorted(filtered, key=lambda d: parse_int(d.get("stats_play_count")), reverse=True)[:10]
        for idx, d in enumerate(filtered, 1):
            sample_rows.append({
                "sample_id": f"CS-{pid:02d}-{idx:02d}",
                "project_id": pid,
                "project_name": r["project_name"],
                "no_china_signal_unique_ratio": r["no_china_signal_unique_ratio"],
                "no_china_signal_play_ratio_rowlabel": r["no_china_signal_play_ratio_rowlabel"],
                "video_id": d.get("video_id", ""),
                "url": d.get("web_url", ""),
                "play_count": parse_int(d.get("stats_play_count")),
                "source_term": d.get("source_term", ""),
                "author_handle": d.get("author_unique_id", ""),
                "caption": d.get("desc", ""),
                "hashtags": json.dumps(d.get("hashtags", []), ensure_ascii=False),
                "hashtags_text": json.dumps(d.get("hashtags_text", []), ensure_ascii=False),
                "quality_label": d.get("quality_label", ""),
                "quality_score": d.get("quality_score", ""),
                "quality_reasons": json.dumps(d.get("quality_reasons", []), ensure_ascii=False),
                "china_context_hit": d.get("china_context_hit", False),
                "china_context_terms": json.dumps(d.get("china_context_terms", []), ensure_ascii=False),
                "has_cjk_desc": d.get("has_cjk_desc", False),
                "manual_label_relevant_irrelevant_uncertain": "",
                "manual_false_negative_if_relevant": "",
                "manual_notes": "",
            })
    return comparison, matrix_rows, sample_rows


def write_report(comparison: list[dict[str, Any]], sample_rows: list[dict[str, Any]]) -> None:
    changed = [r for r in comparison if r["quadrant_changed_after_signal_filter"] == "True"]
    high_noise = [r for r in comparison if r["high_noise_gt50pct_no_china_signal"] == "True"]
    out = DOCS / f"TikTok_china_signal_filter_recalculation_{DATE}.md"
    lines = [
        "# TikTok 中国信号硬过滤重算（2026-06-20）",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        "> 过滤口径：`quality_label == likely_relevant` 且必须满足 `china_context_hit == True` 或 `has_cjk_desc == True`。",
        "",
        "## 口径说明",
        "",
        f"- {LIMITATION_NOTE}",
        "- 被过滤掉的视频不是从原始数据删除，而是从 signal-filtered likely reach 池剔除；原始 row labels 保留，便于复核。",
        "- 防误杀抽样清单见 `manual_review/tiktok_china_signal_filtered_out_high_noise_review_sample_20260620.csv`：对 no-China-signal 占比 >50% 的高噪声项目，每项抽取最高播放 10 条被过滤视频，供人工标注误杀率。",
        "",
        "## 高噪声项目（no-China-signal likely unique 占比 >50%）",
        "",
    ]
    for r in sorted(high_noise, key=lambda x: (-x["no_china_signal_unique_ratio"], -parse_int(x["filtered_out_no_china_signal_play"]))):
        lines.append(
            f"- **{r['project_name']}**: no-signal unique {r['no_china_signal_unique_ratio']:.1%}; "
            f"play drop {parse_int(r['absolute_play_drop']):,}; "
            f"{parse_int(r['before_likely_total_play']):,} → {parse_int(r['signal_likely_total_play']):,}; "
            f"quadrant {r['before_quadrant']} → {r['signal_quadrant']}"
        )
    lines += ["", "## 象限变化项目", ""]
    if changed:
        for r in sorted(changed, key=lambda x: -parse_int(x["absolute_play_drop"])):
            lines.append(
                f"- **{r['project_name']}**: {r['before_quadrant']} → {r['signal_quadrant']}; "
                f"likely_play {parse_int(r['before_likely_total_play']):,} → {parse_int(r['signal_likely_total_play']):,}; "
                f"tier {r['before_likely_reach_tier']} → {r['signal_likely_reach_tier']}"
            )
    else:
        lines.append("- 无。")
    lines += ["", "## 触达缩水最多（Top 20）", ""]
    for r in comparison[:20]:
        lines.append(
            f"- **{r['project_name']}**: {parse_int(r['before_likely_total_play']):,} → "
            f"{parse_int(r['signal_likely_total_play']):,}; drop={parse_int(r['absolute_play_drop']):,} "
            f"({r['play_drop_ratio']:.1%}); quadrant={r['signal_quadrant']}"
        )
    lines += [
        "",
        "## 输出文件",
        "",
        f"- `tables/tiktok_china_signal_filtered_reach_comparison_{DATE}.csv/json` — 44 项重算前后对比。",
        f"- `tables/tiktok_china_signal_filtered_matrix_{DATE}.csv/json` — signal-filtered 新四象限矩阵。",
        f"- `manual_review/tiktok_china_signal_filtered_out_high_noise_review_sample_{DATE}.csv` — 高噪声项目被过滤视频人工防误杀抽样清单。",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    final_doc = FINAL_DIR / "docs" / out.name
    final_doc.parent.mkdir(parents=True, exist_ok=True)
    final_doc.write_text(out.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> int:
    comparison, matrix_rows, sample_rows = build_outputs()
    comp_fields = list(comparison[0].keys()) if comparison else []
    matrix_fields = list(matrix_rows[0].keys()) if matrix_rows else []
    sample_fields = list(sample_rows[0].keys()) if sample_rows else []

    paths = {
        "comparison_csv": DERIVED / f"tiktok_china_signal_filtered_reach_comparison_{DATE}.csv",
        "comparison_json": DERIVED / f"tiktok_china_signal_filtered_reach_comparison_{DATE}.json",
        "matrix_csv": DERIVED / f"tiktok_china_signal_filtered_matrix_{DATE}.csv",
        "matrix_json": DERIVED / f"tiktok_china_signal_filtered_matrix_{DATE}.json",
        "sample_csv": DERIVED / f"tiktok_china_signal_filtered_out_high_noise_review_sample_{DATE}.csv",
    }
    write_csv(paths["comparison_csv"], comparison, comp_fields)
    write_json(paths["comparison_json"], comparison)
    write_csv(paths["matrix_csv"], matrix_rows, matrix_fields)
    write_json(paths["matrix_json"], matrix_rows)
    write_csv(paths["sample_csv"], sample_rows, sample_fields)

    # Mirror into final closed bundle.
    final_tables = FINAL_DIR / "tables"
    final_review = FINAL_DIR / "manual_review"
    final_tables.mkdir(parents=True, exist_ok=True)
    final_review.mkdir(parents=True, exist_ok=True)
    write_csv(final_tables / paths["comparison_csv"].name, comparison, comp_fields)
    write_json(final_tables / paths["comparison_json"].name, comparison)
    write_csv(final_tables / paths["matrix_csv"].name, matrix_rows, matrix_fields)
    write_json(final_tables / paths["matrix_json"].name, matrix_rows)
    write_csv(final_review / paths["sample_csv"].name, sample_rows, sample_fields)
    write_report(comparison, sample_rows)

    summary = {
        "rows": len(comparison),
        "high_noise_gt50pct_projects": sum(1 for r in comparison if r["high_noise_gt50pct_no_china_signal"] == "True"),
        "quadrant_changed_projects": sum(1 for r in comparison if r["quadrant_changed_after_signal_filter"] == "True"),
        "sample_rows": len(sample_rows),
        "largest_drops": [
            {
                "project_name": r["project_name"],
                "before_likely_total_play": r["before_likely_total_play"],
                "signal_likely_total_play": r["signal_likely_total_play"],
                "absolute_play_drop": r["absolute_play_drop"],
                "signal_quadrant": r["signal_quadrant"],
            }
            for r in comparison[:10]
        ],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
