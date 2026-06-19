#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fuse YouTube machine relevance with Softr AI audit and build a targeted manual queue.

The queue implements the agreed recommended tier: top evidence per project plus
high-impact conflicts/uncertain rows and key projects that can change the cross-
platform matrix. Raw crawl outputs are not modified.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LABELS_IN = ROOT / "data/derived/youtube_deepcrawl_y3_y4_merged_20260619/youtube_video_relevance_labels.ndjson"
AI_IN = ROOT / "data/derived/youtube_ai_audit_results_softr_v4_clean_20260619.jsonl"
MATRIX_IN = ROOT / "data/derived/cross_platform_tiktok_youtube_matrix_20260619.csv"
FUSION_JSONL = ROOT / "data/derived/youtube_ai_machine_fusion_labels_20260619.ndjson"
FUSION_CSV = ROOT / "data/derived/youtube_ai_machine_fusion_labels_20260619.csv"
MANUAL_CSV = ROOT / "data/derived/youtube_manual_review_queue_recommended_20260619.csv"
SUMMARY_JSON = ROOT / "data/derived/youtube_ai_machine_fusion_summary_20260619.json"
REPORT_MD = ROOT / "docs/YouTube_AI机器融合与推荐人工清单_20260619.md"

# User-confirmed critical projects where false high YouTube reach could change narrative.
KEY_PROJECT_IDS = {21}  # 中国蚕桑丝织技艺 — high-impact silk/sericulture collision risk.
HIGH_IMPACT_VIEWS = 5_000_000
TOP_N_PER_PROJECT = 10
TARGET_MIN = 150
TARGET_MAX = 250


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_matrix(path: Path) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            out[int(row["project_id"])] = row
    return out


def stable_id(row: dict[str, Any]) -> str:
    return f"{int(row['project_id'])}:{row['video_id']}"


def ai_label_to_short(label: str) -> str:
    if label == "相关":
        return "ai_relevant"
    if label == "不相关":
        return "ai_irrelevant"
    return "ai_uncertain"


def fuse(machine: str, ai: str, views: int, is_key_project: bool) -> tuple[str, bool, list[str]]:
    reasons: list[str] = []
    manual = False
    if machine == "likely_relevant" and ai == "相关":
        fusion = "machine_ai_agree_likely"
    elif machine == "likely_relevant" and ai == "不相关":
        fusion = "conflict_ai_negative_machine_likely"
        reasons.append("machine_likely_ai_irrelevant_conflict")
        if views >= HIGH_IMPACT_VIEWS or is_key_project:
            manual = True
    elif machine == "likely_relevant" and ai == "拿不准":
        fusion = "uncertain_ai_machine_likely"
        reasons.append("ai_uncertain_machine_likely")
        if views >= HIGH_IMPACT_VIEWS or is_key_project:
            manual = True
    elif machine in {"low_relevance", "needs_review"} and ai == "不相关":
        fusion = "auto_demote_low_machine_weak_ai_irrelevant"
    elif machine in {"low_relevance", "needs_review"} and ai == "相关":
        fusion = "candidate_ai_positive_machine_weak"
        reasons.append("ai_positive_machine_weak")
        if views >= HIGH_IMPACT_VIEWS or is_key_project:
            manual = True
    else:
        fusion = f"middle_confidence_{machine}_{ai_label_to_short(ai)}"
        if ai == "拿不准" and (views >= HIGH_IMPACT_VIEWS or is_key_project):
            reasons.append("ai_uncertain_high_impact_or_key")
            manual = True
    if views >= HIGH_IMPACT_VIEWS and fusion.startswith(("conflict", "uncertain", "candidate", "middle_confidence")):
        reasons.append("views_ge_5m_high_impact")
        manual = True
    return fusion, manual, reasons


def queue_add(queue: dict[str, dict[str, Any]], row: dict[str, Any], reason: str, priority: int) -> None:
    sid = row["id"]
    if sid in queue:
        queue[sid]["manual_queue_reason"] = queue[sid]["manual_queue_reason"] + ";" + reason
        queue[sid]["manual_priority"] = min(queue[sid]["manual_priority"], priority)
    else:
        q = dict(row)
        q["manual_queue_reason"] = reason
        q["manual_priority"] = priority
        queue[sid] = q


def main() -> int:
    machine_rows = load_jsonl(LABELS_IN)
    ai_rows = {str(r["id"]): r for r in load_jsonl(AI_IN)}
    matrix = load_matrix(MATRIX_IN)
    if len(ai_rows) != 7320:
        raise SystemExit(f"expected 7320 AI rows, got {len(ai_rows)}")

    fused: list[dict[str, Any]] = []
    for r in machine_rows:
        sid = stable_id(r)
        ai = ai_rows.get(sid)
        if not ai:
            raise SystemExit(f"missing AI row {sid}")
        views = int(r.get("stats_play_count") or 0)
        project_id = int(r["project_id"])
        fusion_label, requires_manual, fusion_reasons = fuse(
            str(r.get("quality_label") or ""),
            str(ai.get("verdict") or "拿不准"),
            views,
            project_id in KEY_PROJECT_IDS,
        )
        mrow = matrix.get(project_id, {})
        out = {
            "id": sid,
            "source_platform": "youtube",
            "project_id": project_id,
            "project_name": r.get("project_name", ""),
            "project_name_en": r.get("project_name_en", ""),
            "list_type": r.get("list_type", ""),
            "category": r.get("category", ""),
            "video_id": r.get("video_id", ""),
            "web_url": r.get("web_url", ""),
            "title": r.get("title", ""),
            "desc": r.get("desc", ""),
            "channelTitle": r.get("channelTitle", ""),
            "publishDate": r.get("publishDate", ""),
            "source_term": r.get("source_term", ""),
            "stats_play_count": views,
            "machine_quality_label": r.get("quality_label", ""),
            "machine_quality_score": r.get("quality_score", ""),
            "machine_quality_reasons": "|".join(map(str, r.get("quality_reasons") or [])),
            "matched_terms": "|".join(map(str, r.get("matched_terms") or [])),
            "negative_matched_terms": "|".join(map(str, r.get("negative_matched_terms") or [])),
            "china_context_hit": r.get("china_context_hit", False),
            "ai_verdict": ai.get("verdict", ""),
            "ai_noise_type": ai.get("noise_type", ""),
            "ai_reason": ai.get("reason", ""),
            "fusion_label": fusion_label,
            "fusion_reasons": "|".join(fusion_reasons),
            "requires_manual_by_rule": requires_manual,
            "cross_platform_verdict_prelim": mrow.get("cross_platform_verdict", ""),
            "youtube_likely_total_view_prelim": mrow.get("youtube_likely_total_view", ""),
        }
        fused.append(out)

    # Build manual queue.
    queue: dict[str, dict[str, Any]] = {}
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in fused:
        if row["machine_quality_label"] == "likely_relevant":
            by_project[int(row["project_id"])].append(row)

    # Top 10 per project with machine likely: anchors project-level evidence.
    for pid, rows in by_project.items():
        for row in sorted(rows, key=lambda x: int(x["stats_play_count"]), reverse=True)[:TOP_N_PER_PROJECT]:
            queue_add(queue, row, f"top{TOP_N_PER_PROJECT}_machine_likely_per_project", 20)

    # High-impact conflicts/uncertain/candidates across all projects.
    for row in fused:
        if int(row["stats_play_count"]) >= HIGH_IMPACT_VIEWS and row["fusion_label"].startswith(
            ("conflict", "uncertain", "candidate", "middle_confidence")
        ):
            queue_add(queue, row, "views_ge_5m_conflict_uncertain_or_candidate", 5)

    # Key project coverage: for sericulture, include top machine-likely and all >=1M conflicts/uncertain/candidates.
    for row in fused:
        pid = int(row["project_id"])
        if pid not in KEY_PROJECT_IDS:
            continue
        if row["machine_quality_label"] == "likely_relevant" and int(row["stats_play_count"]) >= 1_000_000:
            queue_add(queue, row, "key_project_sericulture_likely_ge_1m", 1)
        if row["fusion_label"].startswith(("conflict", "uncertain", "candidate")):
            queue_add(queue, row, "key_project_sericulture_conflict_uncertain_candidate", 1)

    # If over target max, keep all key/high-impact rows, then trim lower-priority top10 rows by views.
    qrows = list(queue.values())
    def sort_key(x: dict[str, Any]) -> tuple[int, int, str]:
        return (int(x["manual_priority"]), -int(x["stats_play_count"]), str(x["id"]))
    qrows.sort(key=sort_key)
    if len(qrows) > TARGET_MAX:
        protected = [r for r in qrows if int(r["manual_priority"]) <= 5]
        rest = [r for r in qrows if int(r["manual_priority"]) > 5]
        qrows = (protected + rest[: max(0, TARGET_MAX - len(protected))])[:TARGET_MAX]

    # Manual CSV fields: reviewer-friendly, with empty return columns.
    manual_fields = [
        "manual_priority", "manual_queue_reason", "project_id", "project_name", "video_id", "web_url",
        "stats_play_count", "title", "desc", "channelTitle", "source_term",
        "machine_quality_label", "ai_verdict", "ai_noise_type", "ai_reason", "fusion_label",
        "cross_platform_verdict_prelim", "youtube_likely_total_view_prelim",
        "manual_relevance", "manual_noise_type", "manual_notes",
    ]
    MANUAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MANUAL_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=manual_fields, extrasaction="ignore")
        w.writeheader()
        for row in qrows:
            rr = dict(row)
            rr.setdefault("manual_relevance", "")
            rr.setdefault("manual_noise_type", "")
            rr.setdefault("manual_notes", "")
            w.writerow(rr)

    # Full fusion artifacts.
    with FUSION_JSONL.open("w", encoding="utf-8") as f:
        for row in fused:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    fusion_fields = list(fused[0].keys())
    with FUSION_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fusion_fields)
        w.writeheader(); w.writerows(fused)

    by_fusion = Counter(r["fusion_label"] for r in fused)
    by_ai = Counter(r["ai_verdict"] for r in fused)
    by_machine = Counter(r["machine_quality_label"] for r in fused)
    manual_by_project = Counter(r["project_name"] for r in qrows)
    sericulture = [r for r in qrows if int(r["project_id"]) == 21]
    sericulture_top = sorted([r for r in fused if int(r["project_id"]) == 21], key=lambda x: int(x["stats_play_count"]), reverse=True)[:10]
    summary = {
        "input_rows": len(fused),
        "ai_rows": len(ai_rows),
        "machine_label_counts": dict(by_machine),
        "ai_verdict_counts": dict(by_ai),
        "fusion_label_counts": dict(by_fusion),
        "manual_queue_rows": len(qrows),
        "manual_queue_by_project": dict(manual_by_project),
        "manual_queue_high_impact_ge_5m": sum(1 for r in qrows if int(r["stats_play_count"]) >= HIGH_IMPACT_VIEWS),
        "manual_queue_sericulture_rows": len(sericulture),
        "sericulture_top10_in_queue": [r["id"] for r in sericulture_top if r["id"] in queue],
        "sericulture_top10": [
            {
                "id": r["id"], "views": r["stats_play_count"], "title": r["title"],
                "machine": r["machine_quality_label"], "ai": r["ai_verdict"],
                "fusion": r["fusion_label"], "in_manual_queue": r["id"] in queue,
            }
            for r in sericulture_top
        ],
        "caveat": "YouTube high-view evidence is manually queued; mid/low-view rows remain AI+machine fused without row-by-row manual audit and may contain residual noise.",
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# YouTube AI+机器融合与推荐档人工清单（2026-06-19）",
        "",
        "## 口径",
        "",
        "- 原始 YouTube 机器标签不修改；AI 结果与融合标签均为 additive derived artifacts。",
        "- `machine likely + AI 不相关` 不自动降级，只标为冲突；仅高影响/关键项目进入人工。",
        "- `machine weak + AI 不相关` 自动降为低可信噪声。",
        "- `AI 相关` 只作为候选增强，不单独当最终人工真值。",
        "",
        "## 重要限制",
        "",
        "> YouTube 高播放段经人工兜底；中低播放段为 AI+机器融合未逐条人工核查，可能含残余噪声。YouTube 侧定位为中等可信辅助维度，可信度低于 TikTok 全人工回流。",
        "",
        "## 统计",
        "",
        f"- 输入视频标签：{len(fused)} 条",
        f"- AI verdict：{dict(by_ai)}",
        f"- 机器标签：{dict(by_machine)}",
        f"- 推荐档人工清单：{len(qrows)} 条",
        f"- 其中 views ≥ 5M：{summary['manual_queue_high_impact_ge_5m']} 条",
        f"- 蚕桑强制覆盖：{len(sericulture)} 条",
        "",
        "## 蚕桑覆盖检查",
        "",
    ]
    for item in summary["sericulture_top10"]:
        mark = "✅" if item["in_manual_queue"] else "❌"
        report.append(f"- {mark} {item['id']} | views={item['views']} | machine={item['machine']} | AI={item['ai']} | {item['title'][:120]}")
    report += [
        "",
        "## 输出文件",
        "",
        f"- 融合标签 NDJSON：`{FUSION_JSONL.relative_to(ROOT)}`",
        f"- 融合标签 CSV：`{FUSION_CSV.relative_to(ROOT)}`",
        f"- 推荐人工清单：`{MANUAL_CSV.relative_to(ROOT)}`",
        f"- 摘要 JSON：`{SUMMARY_JSON.relative_to(ROOT)}`",
        "",
    ]
    REPORT_MD.write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
