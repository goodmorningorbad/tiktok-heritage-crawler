#!/usr/bin/env python3
"""Derive relevance-aware project reach metrics from labeled baseline videos.

Inputs:
- data/derived/video_relevance_labels.ndjson

Outputs:
- data/derived/project_reach_relevance_aware.csv
- data/derived/project_reach_relevance_aware.json
- docs/触达维_相关性过滤后分析.md

The script computes reach under four buckets:
- raw: all project videos
- likely: quality_label == likely_relevant
- inclusive: likely_relevant + needs_review
- low: quality_label == low_relevance
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

LABEL_BUCKETS = {
    "raw": {"likely_relevant", "needs_review", "low_relevance"},
    "likely": {"likely_relevant"},
    "inclusive": {"likely_relevant", "needs_review"},
    "low": {"low_relevance"},
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


def reach_score(prefix_metrics: dict[str, Any], prefix: str) -> float:
    return (
        math.log10(prefix_metrics.get(f"{prefix}_total_play", 0) + 1) * 0.35
        + math.log10(prefix_metrics.get(f"{prefix}_p95_play", 0) + 1) * 0.35
        + math.log10(prefix_metrics.get(f"{prefix}_max_play", 0) + 1) * 0.20
        + math.log10(prefix_metrics.get(f"{prefix}_videos_ge_100k", 0) + 1) * 0.10
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


def metric_for(rows: list[dict[str, Any]], labels: set[str]) -> dict[str, Any]:
    # Deduplicate per project by video_id; keep max stats if duplicates exist.
    best: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("quality_label") not in labels:
            continue
        vid = str(r.get("video_id") or "")
        if not vid:
            continue
        cur = best.get(vid)
        if cur is None or int(r.get("stats_play_count") or 0) > int(cur.get("stats_play_count") or 0):
            best[vid] = r
    xs = list(best.values())
    plays = [int(r.get("stats_play_count") or 0) for r in xs]
    diggs = [int(r.get("stats_digg_count") or 0) for r in xs]
    comments = [int(r.get("stats_comment_count") or 0) for r in xs]
    shares = [int(r.get("stats_share_count") or 0) for r in xs]
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
        "top_video_id": max(xs, key=lambda r: int(r.get("stats_play_count") or 0))["video_id"] if xs else "",
        "top_video_url": max(xs, key=lambda r: int(r.get("stats_play_count") or 0)).get("web_url", "") if xs else "",
        "top_video_desc": (max(xs, key=lambda r: int(r.get("stats_play_count") or 0)).get("desc", "")[:220] if xs else ""),
    }


def derive(labels_path: Path) -> list[dict[str, Any]]:
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in iter_ndjson(labels_path):
        by_project[int(r["project_id"])].append(r)

    rows: list[dict[str, Any]] = []
    for pid in sorted(by_project):
        xs = by_project[pid]
        base = {
            "project_id": pid,
            "project_name": xs[0]["project_name"],
            "project_name_en": xs[0].get("project_name_en", ""),
            "list_type": xs[0].get("list_type", ""),
            "category": xs[0].get("category", ""),
        }
        label_counts = Counter(r.get("quality_label") for r in xs)
        base.update({
            "label_likely_relevant_rows": label_counts.get("likely_relevant", 0),
            "label_needs_review_rows": label_counts.get("needs_review", 0),
            "label_low_relevance_rows": label_counts.get("low_relevance", 0),
        })
        for prefix, labels in LABEL_BUCKETS.items():
            m = metric_for(xs, labels)
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
        # crude ordinal delta for prioritizing review
        order = {
            "top_20pct_reach": 5,
            "high_20_40pct_reach": 4,
            "middle_40_70pct_reach": 3,
            "lower_70_90pct_reach": 2,
            "bottom_10pct_reach": 1,
            "no_videos": 0,
        }
        r["raw_to_likely_tier_delta"] = order.get(r["likely_reach_tier"], 0) - order.get(r["raw_reach_tier"], 0)
    return rows


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
        "note": "Relevance-aware reach metrics. likely = high-confidence; inclusive = likely + needs_review; low bucket retained as noise/risk signal.",
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt(n: int) -> str:
    return f"{int(n):,}"


def write_report(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw_tiers = Counter(r["raw_reach_tier"] for r in rows)
    likely_tiers = Counter(r["likely_reach_tier"] for r in rows)
    inclusive_tiers = Counter(r["inclusive_reach_tier"] for r in rows)
    changed = [r for r in rows if r["reach_tier_changed_after_relevance_filter"]]
    noisy = sorted(rows, key=lambda r: (r["low_relevance_play_ratio"], r["low_total_play"]), reverse=True)[:12]
    dropped = sorted(rows, key=lambda r: (r["raw_to_likely_tier_delta"], r["low_relevance_play_ratio"]))[:12]
    strong_likely = sorted(rows, key=lambda r: r["likely_reach_score"], reverse=True)[:12]

    tier_order = ["top_20pct_reach", "high_20_40pct_reach", "middle_40_70pct_reach", "lower_70_90pct_reach", "bottom_10pct_reach", "no_videos"]

    def project_line(r: dict[str, Any]) -> str:
        return (
            f"- **{r['project_name']}** ({r['list_type']}): raw={r['raw_reach_tier']}, "
            f"likely={r['likely_reach_tier']}, inclusive={r['inclusive_reach_tier']}, "
            f"likely_videos={r['likely_unique_videos']}/{r['raw_unique_videos']} ({r['likely_video_ratio']:.1%}), "
            f"likely_play={fmt(r['likely_total_play'])}/{fmt(r['raw_total_play'])} ({r['likely_play_ratio']:.1%}), "
            f"low_play_ratio={r['low_relevance_play_ratio']:.1%}, risk={r['reach_noise_risk']}"
        )

    lines = []
    lines.append("# 触达维：相关性过滤后分析")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：`data/derived/video_relevance_labels.ndjson`  ")
    lines.append("> 性质：派生触达统计；raw / likely / inclusive / low 四套并存，不删除 low 桶。")
    lines.append("")
    lines.append("## 1. 口径")
    lines.append("")
    lines.append("- `raw`: 所有 search baseline 视频。")
    lines.append("- `likely`: 只算 `likely_relevant`，高置信触达。")
    lines.append("- `inclusive`: `likely_relevant + needs_review`，宽口径触达上界。")
    lines.append("- `low`: `low_relevance`，不删除，作为噪声/语义稀释风险。")
    lines.append("")
    lines.append("## 2. reach tier 对比")
    lines.append("")
    for name, c in [("raw", raw_tiers), ("likely", likely_tiers), ("inclusive", inclusive_tiers)]:
        lines.append(f"### {name}")
        for t in tier_order:
            if c.get(t, 0):
                lines.append(f"- `{t}`: {c[t]}")
        lines.append("")
    lines.append(f"- raw → likely 后 tier 发生变化的项目：**{len(changed)} / {len(rows)}**")
    lines.append("")
    lines.append("## 3. likely 触达最强项目")
    lines.append("")
    for r in strong_likely:
        lines.append(project_line(r))
    lines.append("")
    lines.append("## 4. raw 被 low_relevance 撑高的噪声风险项目")
    lines.append("")
    for r in noisy:
        lines.append(project_line(r))
    lines.append("")
    lines.append("## 5. raw → likely 掉档明显的项目（人工复核优先）")
    lines.append("")
    for r in dropped:
        if r["raw_to_likely_tier_delta"] < 0 or r["reach_noise_risk"] != "low":
            lines.append(project_line(r))
    lines.append("")
    lines.append("## 6. 下一步")
    lines.append("")
    lines.append("1. 从 raw 高但 likely 下跌/low 播放占比高的项目抽 top videos 人工复核。")
    lines.append("2. 继续采 hashtag `statsV2.videoCount`，补正式存量轴。")
    lines.append("3. 合成 `存量 × relevance-aware 触达` 分层草表。")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", type=Path, default=Path("data/derived/video_relevance_labels.ndjson"))
    ap.add_argument("--out-csv", type=Path, default=Path("data/derived/project_reach_relevance_aware.csv"))
    ap.add_argument("--out-json", type=Path, default=Path("data/derived/project_reach_relevance_aware.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/触达维_相关性过滤后分析.md"))
    args = ap.parse_args()
    rows = derive(args.labels)
    write_csv(rows, args.out_csv)
    write_json(rows, args.out_json)
    write_report(rows, args.out_report)
    print(f"projects={len(rows)}")
    print("raw_tiers", dict(Counter(r["raw_reach_tier"] for r in rows)))
    print("likely_tiers", dict(Counter(r["likely_reach_tier"] for r in rows)))
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_report}")


if __name__ == "__main__":
    main()
