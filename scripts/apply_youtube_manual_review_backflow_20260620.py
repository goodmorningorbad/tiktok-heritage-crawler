#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Apply YouTube manual-review backflow and recompute project reach (band).

Additive: reads fusion labels + returned manual review, writes new derived
artifacts. Raw/fusion inputs untouched.

Relevance hierarchy: 人工(manual) > AI fusion > machine.
- manual (180 reviewed): 相关→likely / 拿不准→needs_review / 不相关→low
- unreviewed: map fusion_label → likely / needs_review / low (see MAPS below)

Reach reported as a BAND (mirrors TikTok filtered/likely band, so cross-platform is comparable):
- likely_total_view    = 下界 (only confirmed-likely bucket)
- inclusive_total_view = 上界 (likely + needs_review)
- raw_total_view / low_total_view also kept.

Inputs:
- data/derived/youtube_ai_machine_fusion_labels_20260619.csv   (7320 project-video rows)
- data/review/youtube_manual_review_returned_20260620.csv       (180 human labels)
Outputs:
- data/derived/youtube_final_video_relevance_labels_manual_corrected_20260620.ndjson
- data/derived/youtube_final_project_reach_manual_corrected_20260620.csv / .json
- docs/YouTube_人工回流触达收口_20260620.md
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
FUSION = ROOT / "data/derived/youtube_ai_machine_fusion_labels_20260619.csv"
RETURNED = ROOT / "data/review/youtube_manual_review_returned_20260620.csv"
DERIVED = ROOT / "data/derived"
DOCS = ROOT / "docs"
DATE = "20260620"

# fusion_label → relevance bucket (for UNREVIEWED videos)
FUSION_TO_BUCKET = {
    "machine_ai_agree_likely": "likely",
    "conflict_ai_negative_machine_likely": "needs_review",   # 机器likely但AI否,存疑,不进下界
    "candidate_ai_positive_machine_weak": "needs_review",
    "uncertain_ai_machine_likely": "needs_review",
    "middle_confidence_needs_review_ai_uncertain": "needs_review",
    "auto_demote_low_machine_weak_ai_irrelevant": "low",
    "middle_confidence_low_relevance_ai_uncertain": "low",
}
MANUAL_TO_BUCKET = {"relevant": "likely", "uncertain": "needs_review", "irrelevant": "low"}


def parse_int(v) -> int:
    try:
        return int(float(str(v).replace(",", ""))) if v not in (None, "") else 0
    except Exception:
        return 0


def main() -> int:
    manual = {r["video_id"]: r for r in csv.DictReader(RETURNED.open(encoding="utf-8-sig"))}
    fusion = list(csv.DictReader(FUSION.open(encoding="utf-8-sig")))

    per_video = []
    proj = defaultdict(lambda: {
        "raw": [], "likely": [], "needs": [], "low": [],
        "manual_demoted_play": 0, "manual_promoted_play": 0, "manual_rows": 0,
    })
    by_proj_meta = {}

    for row in fusion:
        vid = row["video_id"]
        pid = int(row["project_id"])
        play = parse_int(row.get("stats_play_count"))
        by_proj_meta.setdefault(pid, {
            "project_id": pid, "project_name": row.get("project_name", ""),
            "project_name_en": row.get("project_name_en", ""),
            "category": row.get("category", ""), "list_type": row.get("list_type", ""),
        })
        m = manual.get(vid)
        if m:
            bucket = MANUAL_TO_BUCKET.get(m["manual_relevance"], "needs_review")
            source = "manual"
            fusion_bucket = FUSION_TO_BUCKET.get(row.get("fusion_label", ""), "needs_review")
            if fusion_bucket == "likely" and bucket != "likely":
                proj[pid]["manual_demoted_play"] += play       # 人工把机器likely拉下来
            if fusion_bucket != "likely" and bucket == "likely":
                proj[pid]["manual_promoted_play"] += play
            proj[pid]["manual_rows"] += 1
        else:
            bucket = FUSION_TO_BUCKET.get(row.get("fusion_label", ""), "needs_review")
            source = "fusion"

        per_video.append({
            "video_id": vid, "project_id": pid, "project_name": row.get("project_name", ""),
            "web_url": row.get("web_url", ""), "stats_play_count": play,
            "title": row.get("title", ""), "channelTitle": row.get("channelTitle", ""),
            "effective_bucket": bucket, "label_source": source,
            "fusion_label": row.get("fusion_label", ""),
            "manual_relevance": m["manual_relevance"] if m else "",
            "manual_noise_type": m.get("manual_noise_type", "") if m else "",
        })
        p = proj[pid]
        p["raw"].append((play, vid, row.get("web_url", ""), row.get("title", "")))
        if bucket == "likely":
            p["likely"].append((play, vid, row.get("web_url", ""), row.get("title", "")))
        elif bucket == "needs_review":
            p["needs"].append((play, vid, row.get("web_url", ""), row.get("title", "")))
        else:
            p["low"].append((play, vid, row.get("web_url", ""), row.get("title", "")))

    # per-video ndjson
    nd = DERIVED / f"youtube_final_video_relevance_labels_manual_corrected_{DATE}.ndjson"
    with nd.open("w", encoding="utf-8") as f:
        for r in per_video:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # per-project reach band
    rows = []
    for pid in sorted(proj):
        p = proj[pid]
        meta = by_proj_meta[pid]
        raw_play = sum(x[0] for x in p["raw"])
        likely_play = sum(x[0] for x in p["likely"])
        needs_play = sum(x[0] for x in p["needs"])
        low_play = sum(x[0] for x in p["low"])
        top_likely = max(p["likely"], default=(0, "", "", ""))
        rows.append({
            **meta,
            "raw_unique_videos": len(p["raw"]),
            "likely_videos": len(p["likely"]),
            "needs_review_videos": len(p["needs"]),
            "low_videos": len(p["low"]),
            "raw_total_view": raw_play,
            "likely_total_view": likely_play,            # 下界
            "inclusive_total_view": likely_play + needs_play,  # 上界
            "low_total_view": low_play,
            "likely_median_view": int(median([x[0] for x in p["likely"]])) if p["likely"] else 0,
            "likely_max_view": top_likely[0],
            "top_likely_url": top_likely[2],
            "top_likely_title": str(top_likely[3])[:160],
            "manual_reviewed_rows": p["manual_rows"],
            "manual_demoted_play": p["manual_demoted_play"],
            "manual_promoted_play": p["manual_promoted_play"],
            "reach_note": "触达报区间: likely=下界, inclusive=上界(含needs_review). 人工>AI融合>机器. 未审conflict_ai_negative计入needs_review不计入下界.",
        })
    rows.sort(key=lambda r: r["inclusive_total_view"], reverse=True)

    fields = list(rows[0].keys())
    with (DERIVED / f"youtube_final_project_reach_manual_corrected_{DATE}.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    (DERIVED / f"youtube_final_project_reach_manual_corrected_{DATE}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    # brief report
    total_demoted = sum(r["manual_demoted_play"] for r in rows)
    lines = [
        f"# YouTube 人工回流触达收口（{DATE}）", "",
        f"- 回流人工标注 180 条(相关119/不相关55/拿不准6),按 video_id 覆盖 fusion。",
        f"- 触达口径:人工>AI融合>机器;报区间 likely(下界)/inclusive(上界=likely+needs_review)。",
        f"- 未审 `conflict_ai_negative_machine_likely`(机器likely但AI否)计入 needs_review,不进下界(避免高估,与 TikTok 一致)。",
        f"- 人工把机器likely判为非相关而扣出下界的播放量合计:{total_demoted:,}。", "",
        "## 各项目触达(按上界降序)", "",
        "| 项目 | likely下界 | inclusive上界 | likely视频 | 人工降级播放 |",
        "|---|--:|--:|--:|--:|",
    ]
    for r in rows:
        lines.append(f"| {r['project_name']} | {r['likely_total_view']:,} | {r['inclusive_total_view']:,} "
                     f"| {r['likely_videos']} | {r['manual_demoted_play']:,} |")
    (DOCS / f"YouTube_人工回流触达收口_{DATE}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "projects": len(rows), "videos": len(per_video),
        "manual_applied": sum(r["manual_reviewed_rows"] for r in rows),
        "total_manual_demoted_play": total_demoted,
        "outputs": [
            str(nd.name),
            f"youtube_final_project_reach_manual_corrected_{DATE}.csv/json",
            f"docs/YouTube_人工回流触达收口_{DATE}.md",
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
