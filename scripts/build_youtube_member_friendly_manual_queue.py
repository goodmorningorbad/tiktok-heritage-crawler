#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a member-friendly YouTube manual review queue.

Keeps the agreed 150-250 recommended queue logic, but trims the sericulture
project to high-view/high-impact rows only: the project verdict is determined by
large-view collision/evidence videos, not by the low-view long tail.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/derived/youtube_manual_review_queue_recommended_20260619.csv"
OUTPUT = ROOT / "data/derived/youtube_manual_review_queue_member_friendly_20260619.csv"
SUMMARY = ROOT / "data/derived/youtube_manual_review_queue_member_friendly_summary_20260619.json"
DOC = ROOT / "docs/YouTube_组员友好版人工清单_20260619.md"
SERICULTURE_PROJECT_ID = "21"
SERICULTURE_KEEP_N = 38
TARGET_MIN = 180
TARGET_MAX = 200


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def views(row: dict[str, str]) -> int:
    try:
        return int(float(row.get("stats_play_count") or 0))
    except Exception:
        return 0


def priority(row: dict[str, str]) -> int:
    try:
        return int(row.get("manual_priority") or 99)
    except Exception:
        return 99


def main() -> int:
    rows = read_rows(INPUT)
    fields = list(rows[0].keys())
    silk = [r for r in rows if r["project_id"] == SERICULTURE_PROJECT_ID]
    non_silk = [r for r in rows if r["project_id"] != SERICULTURE_PROJECT_ID]

    silk_kept = sorted(silk, key=lambda r: (-views(r), priority(r), r["video_id"]))[:SERICULTURE_KEEP_N]
    selected = non_silk + silk_kept

    # If still over max, trim only low-priority/non-high-impact rows by preserving
    # high-impact first. Current expected size: 172 non-silk + 30 silk = 202,
    # so remove the lowest-view priority-20 rows outside key high-impact logic.
    if len(selected) > TARGET_MAX:
        protected = [r for r in selected if priority(r) <= 5 or r["project_id"] == SERICULTURE_PROJECT_ID]
        rest = [r for r in selected if r not in protected]
        rest = sorted(rest, key=lambda r: (priority(r), -views(r), r["project_id"], r["video_id"]))
        selected = protected + rest[: max(0, TARGET_MAX - len(protected))]

    selected = sorted(selected, key=lambda r: (priority(r), r["project_id"] != SERICULTURE_PROJECT_ID, -views(r), r["project_id"], r["video_id"]))

    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(selected)

    kept_ids = {r["video_id"] for r in silk_kept}
    dropped_silk = [r for r in silk if r["video_id"] not in kept_ids]
    project_counts = Counter(r["project_name"] for r in selected)
    summary = {
        "input_rows": len(rows),
        "output_rows": len(selected),
        "sericulture_input_rows": len(silk),
        "sericulture_kept_rows": len([r for r in selected if r["project_id"] == SERICULTURE_PROJECT_ID]),
        "sericulture_dropped_rows": len(dropped_silk),
        "sericulture_keep_rule": f"top {SERICULTURE_KEEP_N} by stats_play_count; low-view long tail dropped",
        "project_counts": dict(project_counts),
        "sericulture_kept": [
            {
                "views": views(r),
                "title": r.get("title", ""),
                "url": r.get("web_url", ""),
                "machine": r.get("machine_quality_label", ""),
                "ai": r.get("ai_verdict", ""),
                "fusion": r.get("fusion_label", ""),
            }
            for r in sorted([r for r in selected if r["project_id"] == SERICULTURE_PROJECT_ID], key=lambda x: -views(x))
        ],
        "dropped_silk_max_views": max([views(r) for r in dropped_silk], default=0),
        "caveat": "Sericulture is trimmed by view impact: retained high-play evidence determines project verdict; low-play sericulture tail remains AI+machine fused and unreviewed.",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# YouTube 组员友好版人工清单（2026-06-19）",
        "",
        "## 压缩规则",
        "",
        "- 从推荐档 250 条压到组员友好版。",
        f"- 蚕桑从 108 条压到 {summary['sericulture_kept_rows']} 条：严格按播放量保留高影响样本，砍低播放长尾。",
        "- 蚕桑 verdict 由高播放证据决定；低播放长尾是否人工审不会改变项目触达结论，接受残余噪声。",
        "- 非蚕桑仍保留每项目 top evidence + 高播放冲突/uncertain 的兜底结构。",
        "",
        "## 数量",
        "",
        f"- 输入推荐档：{len(rows)} 条",
        f"- 组员友好版：{len(selected)} 条",
        f"- 蚕桑保留：{summary['sericulture_kept_rows']} 条，删除长尾：{summary['sericulture_dropped_rows']} 条",
        "",
        "## 蚕桑保留样本检查",
        "",
    ]
    for item in summary["sericulture_kept"][:30]:
        lines.append(f"- {item['views']} views | machine={item['machine']} | AI={item['ai']} | {item['title'][:120]} | {item['url']}")
    lines += [
        "",
        "## 输出",
        "",
        f"- CSV：`{OUTPUT.relative_to(ROOT)}`",
        f"- Summary：`{SUMMARY.relative_to(ROOT)}`",
    ]
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
