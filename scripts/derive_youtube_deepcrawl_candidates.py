#!/usr/bin/env python3
"""Build YouTube Y2 deep-crawl candidate list without collecting new data.

Principles:
- No API calls here. This is prioritization only.
- YouTube stock is qualitative collection state (exhausted/sample_limit/ceiling), not numerically comparable to TikTok hashtag stock.
- Deep crawl is selective: P0 conclusion-critical terms to 10 pages; noisy diagnostic terms to 5 pages; exhausted low-stock terms are held.
- TikTok manual-review dependent decisions are marked wait_tiktok_manual rather than forced now.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOP_REACH_TIERS = {"top_20pct_reach", "high_20_40pct_reach"}
TIKTOK_KEY_PRIORITIES = {"P0_noise_or_tier_drop", "P0_stock_high_reach_low", "P1_low_stock_high_reach"}
EXHAUSTED_CROSS_PLATFORM_LOW_TERMS = {
    "Kgal laox",
    "Longquan celadon",
    "Chinese Regong art",
    "Khoomei throat singing",
    "Mongolian long song",
}


def parse_int(v: Any) -> int:
    try:
        if v is None or v == "":
            return 0
        return int(float(v))
    except Exception:
        return 0


def parse_float(v: Any) -> float:
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except Exception:
        return 0.0


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


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


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_json(rows: list[dict[str, Any]], path: Path, note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "note": note, "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def term_metrics(labels_path: Path) -> dict[tuple[int, str], dict[str, Any]]:
    grouped: dict[tuple[int, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for r in iter_ndjson(labels_path):
        pid = int(r["project_id"])
        term = str(r.get("source_term") or "")
        vid = str(r.get("video_id") or "")
        if not term or not vid:
            continue
        cur = grouped[(pid, term)].get(vid)
        if cur is None or (parse_int(r.get("quality_score")), parse_int(r.get("stats_play_count"))) > (
            parse_int(cur.get("quality_score")), parse_int(cur.get("stats_play_count"))
        ):
            grouped[(pid, term)][vid] = r

    out: dict[tuple[int, str], dict[str, Any]] = {}
    for key, best_by_video in grouped.items():
        xs = list(best_by_video.values())
        labels = Counter(r.get("quality_label") for r in xs)
        raw_play = sum(parse_int(r.get("stats_play_count")) for r in xs)
        likely = [r for r in xs if r.get("quality_label") == "likely_relevant"]
        low = [r for r in xs if r.get("quality_label") == "low_relevance"]
        needs = [r for r in xs if r.get("quality_label") == "needs_review"]
        likely_play = sum(parse_int(r.get("stats_play_count")) for r in likely)
        low_play = sum(parse_int(r.get("stats_play_count")) for r in low)
        top_likely = max(likely, key=lambda r: parse_int(r.get("stats_play_count")), default={})
        top_raw = max(xs, key=lambda r: parse_int(r.get("stats_play_count")), default={})
        out[key] = {
            "term_raw_unique_videos": len(xs),
            "term_likely_unique_videos": len(likely),
            "term_needs_review_unique_videos": len(needs),
            "term_low_unique_videos": len(low),
            "term_likely_video_ratio": round(len(likely) / len(xs), 4) if xs else 0,
            "term_low_video_ratio": round(len(low) / len(xs), 4) if xs else 0,
            "term_raw_total_view": raw_play,
            "term_likely_total_view": likely_play,
            "term_low_total_view": low_play,
            "term_likely_play_ratio": round(likely_play / raw_play, 4) if raw_play else 0,
            "term_low_play_ratio": round(low_play / raw_play, 4) if raw_play else 0,
            "term_likely_max_view": parse_int(top_likely.get("stats_play_count")),
            "term_raw_max_view": parse_int(top_raw.get("stats_play_count")),
            "term_top_likely_url": top_likely.get("web_url", ""),
            "term_top_raw_url": top_raw.get("web_url", ""),
            "term_label_counts": dict(labels),
        }
    return out


def qualitative_youtube_stock(row: dict[str, Any]) -> str:
    state = row.get("stop_reason")
    if state == "exhausted":
        return "youtube_exhausted_low_or_finite_stock"
    if state == "sample_limit_reached":
        return "youtube_three_page_lower_bound_unresolved"
    if state == "ceiling_capped_500":
        return "youtube_visible_stock_capped_high"
    if state == "zero_real":
        return "youtube_zero_visible_stock"
    if state == "failed":
        return "youtube_failed_unknown"
    return "youtube_unknown"


def choose_priority(row: dict[str, Any]) -> tuple[str, int, str, str, int, str]:
    """Return (priority, rank, action, pages, max_pages, reason). Lower rank sorts earlier."""
    state = row["current_stop_reason"]
    term = row["search_keyword"]
    yt_tier = row["youtube_likely_reach_tier"]
    yt_project_noise = parse_float(row["youtube_project_low_relevance_play_ratio"])
    term_noise = parse_float(row["term_low_play_ratio"])
    term_likely_views = parse_int(row["term_likely_total_view"])
    term_likely_n = parse_int(row["term_likely_unique_videos"])
    tiktok_priority = row["tiktok_review_priority"]
    tiktok_quadrant = row["tiktok_quadrant"]
    raw_to_likely_delta = parse_int(row["youtube_raw_to_likely_tier_delta"])

    if state == "exhausted":
        if term in EXHAUSTED_CROSS_PLATFORM_LOW_TERMS:
            return (
                "P2_hold_exhausted_cross_platform_low",
                70,
                "hold_no_deepcrawl",
                "none",
                3,
                "3页内自然采空；与 TikTok 低存量方向一致，先保留为跨平台低可见性发现，不补采。",
            )
        return ("P2_hold_exhausted", 75, "hold_no_deepcrawl", "none", 3, "3页内自然采空；不属于当前深采优先对象。")

    # YouTube can move now: clear high likely reach, low noise, still sample-limited.
    if state == "sample_limit_reached" and yt_tier in TOP_REACH_TIERS and yt_project_noise < 0.25 and term_likely_views >= 20_000_000 and term_likely_n >= 30:
        return (
            "P0_youtube_high_reach_deepcrawl_now",
            10,
            "deepcrawl_to_10_pages",
            "to_10_pages",
            10,
            "YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。",
        )

    # Conclusion-critical but needs TikTok manual result before final selection.
    if state == "sample_limit_reached" and (tiktok_priority in TIKTOK_KEY_PRIORITIES or tiktok_quadrant in {"stock_high__reach_low", "stock_low__reach_high"}):
        return (
            "P0_wait_tiktok_manual_for_deepcrawl",
            20,
            "wait_tiktok_manual_then_decide",
            "defer",
            10,
            "TikTok 关键象限/人工核查项目；先列为候选，等 321 条人工表回流后决定是否补到 10 页。",
        )

    # Noise diagnostics: enough to 5 pages, not full 500.
    if state == "sample_limit_reached" and (term_noise >= 0.70 or yt_project_noise >= 0.70 or raw_to_likely_delta <= -2):
        return (
            "P1_noise_probe_5_pages",
            35,
            "deepcrawl_to_5_pages_for_noise_diagnosis",
            "to_5_pages",
            5,
            "raw/low 噪声强或 raw→likely 下跌明显；补到 5 页足够判断噪声结构，不补满 500。",
        )

    if state == "sample_limit_reached" and yt_tier in TOP_REACH_TIERS:
        return (
            "P1_possible_reach_deepcrawl_after_review",
            45,
            "review_then_maybe_deepcrawl",
            "defer_or_to_10_pages",
            10,
            "YouTube 触达相对靠前，但噪声或 TikTok 对照优先级不足；等候选表人工看过后再决定。",
        )

    return (
        "P3_no_deepcrawl_now",
        90,
        "no_deepcrawl_now",
        "none",
        3,
        "当前不是结论关键项；保持 3 页样本，暂不烧配额。",
    )


def derive(args: argparse.Namespace) -> list[dict[str, Any]]:
    yt_reach = {int(r["project_id"]): r for r in read_csv(args.youtube_reach)}
    term_meta = read_csv(args.youtube_term_meta)
    tik_matrix = {int(r["project_id"]): r for r in read_csv(args.tiktok_matrix)}
    manual_rows = read_csv(args.tiktok_manual_priority)
    manual_project_rows = Counter(int(r["project_id"]) for r in manual_rows)
    tm = term_metrics(args.youtube_labels)

    rows: list[dict[str, Any]] = []
    for m in term_meta:
        pid = int(m["project_id"])
        yr = yt_reach[pid]
        tr = tik_matrix[pid]
        metrics = tm.get((pid, m["search_keyword"]), {})
        base: dict[str, Any] = {
            "project_id": pid,
            "project_name": m.get("heritage_item", ""),
            "search_keyword": m.get("search_keyword", ""),
            "current_stop_reason": m.get("stop_reason", ""),
            "current_pages_fetched": parse_int(m.get("pages_fetched")),
            "current_collected_count": parse_int(m.get("collected_count")),
            "current_next_page_token_present": m.get("nextPageToken_present_at_stop", ""),
            "youtube_stock_qualitative_state": qualitative_youtube_stock(m),
            "youtube_totalResults_estimate_weak_signal": parse_int(m.get("totalResults_estimate")),
            "youtube_likely_reach_tier": yr.get("likely_reach_tier", ""),
            "youtube_likely_reach_score": yr.get("likely_reach_score", ""),
            "youtube_project_likely_total_view": parse_int(yr.get("likely_total_play")),
            "youtube_project_likely_unique_videos": parse_int(yr.get("likely_unique_videos")),
            "youtube_project_raw_total_view": parse_int(yr.get("raw_total_play")),
            "youtube_project_low_relevance_play_ratio": yr.get("low_relevance_play_ratio", ""),
            "youtube_raw_to_likely_tier_delta": yr.get("raw_to_likely_tier_delta", ""),
            "youtube_reach_noise_risk": yr.get("reach_noise_risk", ""),
            "tiktok_quadrant": tr.get("quadrant", ""),
            "tiktok_quadrant_label": tr.get("quadrant_label", ""),
            "tiktok_review_priority": tr.get("review_priority", ""),
            "tiktok_likely_reach_tier": tr.get("likely_reach_tier", ""),
            "tiktok_stock_band_qualitative": tr.get("stock_band", ""),
            "tiktok_scale_tier_qualitative": tr.get("scale_video_count_tier", ""),
            "tiktok_manual_priority_rows": manual_project_rows.get(pid, 0),
            "cross_platform_stock_compare_note": "qualitative_only: TikTok hashtag stock and YouTube collection state are not same units; do not compare numeric magnitude.",
        }
        base.update(metrics)
        priority, rank, action, page_plan, max_pages, reason = choose_priority(base)
        base.update({
            "deepcrawl_priority": priority,
            "priority_rank": rank,
            "recommended_action": action,
            "recommended_page_plan": page_plan,
            "recommended_max_pages": max_pages,
            "deepcrawl_reason": reason,
        })
        rows.append(base)

    rows.sort(key=lambda r: (
        parse_int(r["priority_rank"]),
        -parse_int(r.get("term_likely_total_view")),
        -parse_int(r.get("youtube_project_likely_total_view")),
        r["project_id"],
        r["search_keyword"],
    ))
    for i, r in enumerate(rows, 1):
        r["candidate_rank"] = i
    return rows


def write_report(rows: list[dict[str, Any]], path: Path) -> None:
    counts = Counter(r["deepcrawl_priority"] for r in rows)
    action_counts = Counter(r["recommended_action"] for r in rows)
    top_now = [r for r in rows if r["deepcrawl_priority"] == "P0_youtube_high_reach_deepcrawl_now"]
    wait = [r for r in rows if r["deepcrawl_priority"] == "P0_wait_tiktok_manual_for_deepcrawl"]
    noise = [r for r in rows if r["deepcrawl_priority"] == "P1_noise_probe_5_pages"]
    exhausted = [r for r in rows if r["deepcrawl_priority"].startswith("P2_hold_exhausted")]

    def line(r: dict[str, Any]) -> str:
        return (
            f"- #{r['candidate_rank']} **{r['project_name']}** — `{r['search_keyword']}`: "
            f"action={r['recommended_action']}, pages={r['recommended_page_plan']}, "
            f"yt_tier={r['youtube_likely_reach_tier']}, term_likely_view={parse_int(r.get('term_likely_total_view')):,}, "
            f"tiktok={r['tiktok_quadrant']} / {r['tiktok_review_priority']}"
        )

    lines: list[str] = []
    lines.append("# YouTube Y2 深采候选清单（不采集，仅排优先级）")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：YouTube 3页扩采 + YouTube relevance-aware 触达 + TikTok 存量×触达草表 + TikTok 人工核查优先项目。")
    lines.append("")
    lines.append("## 1. 原则")
    lines.append("")
    lines.append("- 本阶段 **不采集**，只生成深采候选与优先级。")
    lines.append("- 不全补 56 个 `sample_limit_reached`；只对结论关键词补。")
    lines.append("- P0 结论关键 / YouTube 明确高触达词：建议补到 10 页；到 10 页仍有 nextPageToken 才标 `ceiling_capped_500`。")
    lines.append("- 噪声诊断词：建议补到 5 页，够判断 raw 噪声结构，不补满。")
    lines.append("- 5 个已自然采空词：不补，保留为跨平台低可见性候选。")
    lines.append("- TikTok 相关人工核查未回流前，依赖 TikTok 结论的深采候选标为 wait，不硬采。")
    lines.append("- Y5 跨平台对比中，**存量轴只能定性对比**：TikTok 是 hashtag videoCount，YouTube 是采集状态，两者不是同一量纲，不能数值比大小；触达轴使用两边 relevance-aware likely 口径。")
    lines.append("")
    lines.append("## 2. 候选分布")
    lines.append("")
    for k, v in counts.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("动作分布：")
    lines.append("")
    for k, v in action_counts.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## 3. 可先推进的 YouTube 高触达 P0")
    lines.append("")
    if top_now:
        for r in top_now[:30]:
            lines.append(line(r))
            lines.append(f"  - reason: {r['deepcrawl_reason']}")
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 4. 等 TikTok 人工回流再定的 P0")
    lines.append("")
    if wait:
        for r in wait[:35]:
            lines.append(line(r))
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 5. 噪声诊断 P1（建议只补到5页）")
    lines.append("")
    if noise:
        for r in noise[:35]:
            lines.append(line(r))
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 6. 已自然采空：保留，不补采")
    lines.append("")
    for r in exhausted:
        lines.append(line(r))
        lines.append(f"  - reason: {r['deepcrawl_reason']}")
    lines.append("")
    lines.append("## 7. 下一步")
    lines.append("")
    lines.append("1. 云白先看 `P0_youtube_high_reach_deepcrawl_now` 是否认可；认可后可直接进入 Y3 对这些词补到 10 页。")
    lines.append("2. `P0_wait_tiktok_manual_for_deepcrawl` 等 TikTok 321 条人工表回流后再筛。")
    lines.append("3. `P1_noise_probe_5_pages` 只为噪声结构验证，不为了追求完整量。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--youtube-dir", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3"))
    ap.add_argument("--youtube-reach", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3/youtube_project_reach_relevance_aware.csv"))
    ap.add_argument("--youtube-labels", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3/youtube_video_relevance_labels.ndjson"))
    ap.add_argument("--youtube-term-meta", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3/youtube_search_term_meta.csv"))
    ap.add_argument("--tiktok-matrix", type=Path, default=Path("data/derived/project_stock_reach_matrix.csv"))
    ap.add_argument("--tiktok-manual-priority", type=Path, default=Path("data/derived/manual_check_priority_videos.csv"))
    ap.add_argument("--out-csv", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3/youtube_deepcrawl_candidates.csv"))
    ap.add_argument("--out-json", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3/youtube_deepcrawl_candidates.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/YouTube深采候选名单_Y2.md"))
    args = ap.parse_args()

    rows = derive(args)
    write_csv(rows, args.out_csv)
    write_json(rows, args.out_json, "YouTube Y2 deep-crawl candidates. Prioritization only; no API calls. Stock comparison is qualitative only.")
    write_report(rows, args.out_report)
    print(f"candidates={len(rows)}")
    print("priority_counts", dict(Counter(r["deepcrawl_priority"] for r in rows)))
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_report}")


if __name__ == "__main__":
    main()
