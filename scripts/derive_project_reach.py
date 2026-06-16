#!/usr/bin/env python3
"""Derive project-level reach metrics from the fixed TikTok search baseline.

This is a DERIVED analysis step: it reads the immutable baseline files and writes
summary artifacts under data/derived/. It does not modify raw collection data.

Inputs (defaults):
- config/unesco_ich_keywords.v1.json
- data/sched_run_20260612_030425/term_results_labeled.ndjson
- data/sched_run_20260612_030425/videos.ndjson

Outputs (defaults):
- data/derived/project_reach_summary.csv
- data/derived/project_reach_summary.json
- docs/触达维初步分析.md
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

CJK_RE = re.compile(r"[\u3400-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


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
    """Nearest-rank-ish percentile with interpolation, returned as int."""
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
    val = xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)
    return int(round(val))


def text_language_proxy(text: str) -> str:
    has_cjk = bool(CJK_RE.search(text or ""))
    has_latin = bool(LATIN_RE.search(text or ""))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "cjk"
    if has_latin:
        return "latin"
    return "unknown"


def absolute_reach_tier(max_play: int, p95_play: int, total_play: int, ge_10k: int, ge_100k: int, unique_videos: int) -> str:
    """Coarse absolute reach signal for raw baseline videos.

    This is intentionally separate from the cohort-relative `initial_reach_tier`.
    In the current baseline many projects have at least one high-play video,
    partly because broad search terms recall noisy popular content.
    """
    if unique_videos == 0:
        return "near_invisible"
    if max_play >= 1_000_000 or p95_play >= 100_000 or ge_100k >= 3:
        return "very_high"
    if max_play >= 100_000 or p95_play >= 10_000 or ge_10k >= 10:
        return "high"
    if max_play >= 10_000 or p95_play >= 1_000 or total_play >= 100_000:
        return "medium"
    if max_play >= 1_000 or total_play >= 10_000:
        return "low"
    return "near_invisible"


def reach_score(row: dict[str, Any]) -> float:
    """Relative score used only to sort projects within this baseline cohort."""
    return (
        math.log10(row.get("total_play_count", 0) + 1) * 0.35
        + math.log10(row.get("p95_play_count", 0) + 1) * 0.35
        + math.log10(row.get("max_play_count", 0) + 1) * 0.20
        + math.log10(row.get("videos_ge_100k_play", 0) + 1) * 0.10
    )


def assign_relative_reach_tiers(rows: list[dict[str, Any]]) -> None:
    """Add `initial_reach_tier` as a cohort-relative band.

    Absolute thresholds make every project look "very_high" in this noisy raw
    baseline, so the useful first pass is relative: who is higher/lower *within
    the 44 projects*. This still needs relevance cleaning before final claims.
    """
    ordered = sorted(rows, key=reach_score, reverse=True)
    n = len(ordered)
    for i, row in enumerate(ordered):
        pct = (i + 1) / max(n, 1)
        if pct <= 0.20:
            tier = "top_20pct_raw_reach"
        elif pct <= 0.40:
            tier = "high_20_40pct_raw_reach"
        elif pct <= 0.70:
            tier = "middle_40_70pct_raw_reach"
        elif pct <= 0.90:
            tier = "lower_70_90pct_raw_reach"
        else:
            tier = "bottom_10pct_raw_reach"
        row["initial_reach_tier"] = tier
        row["raw_reach_score"] = round(reach_score(row), 6)


def search_stock_proxy(term_rows: list[dict[str, Any]]) -> str:
    """Search stock proxy from ceiling labels, not a reach judgement."""
    if not term_rows:
        return "no_terms"
    classes = Counter((r.get("ceiling_class") or r.get("depth_verdict") or "unknown") for r in term_rows)
    result_classes = Counter(r.get("result_class") or "unknown" for r in term_rows)
    if result_classes.get("has_data", 0) == 0 and result_classes.get("zero_real", 0) > 0:
        return "zero_search_stock"
    if classes.get("ceiling_capped", 0) > 0:
        return "ceiling_capped_stock"
    if classes.get("boundary", 0) > 0:
        return "boundary_stock"
    if classes.get("exhausted", 0) > 0 or result_classes.get("has_data", 0) > 0:
        return "below_ceiling_stock"
    return "unknown"


def quadrant(search_stock: str, tier: str) -> str:
    """Preliminary stock × reach quadrant using SEARCH-STOCK proxy only.

    Hashtag statsV2.videoCount is still required for the final stock axis.
    """
    stock_high = search_stock == "ceiling_capped_stock"
    stock_boundary = search_stock == "boundary_stock"
    reach_high = tier in {"top_20pct_raw_reach", "high_20_40pct_raw_reach", "very_high", "high"}
    reach_low = tier in {"lower_70_90pct_raw_reach", "bottom_10pct_raw_reach", "low", "near_invisible"}
    if stock_high and reach_high:
        return "search_stock_high__reach_high"
    if stock_high and reach_low:
        return "search_stock_high__reach_low"
    if (not stock_high) and reach_high:
        return "search_stock_low_or_unclear__reach_high"
    if stock_boundary:
        return "search_stock_boundary__reach_" + tier
    return "search_stock_low_or_unclear__reach_low_or_medium"


@dataclass
class ProjectAgg:
    project: dict[str, Any]
    term_rows: list[dict[str, Any]] = field(default_factory=list)
    # video_id -> compact video record. If duplicated by multiple terms in same project,
    # keep max observed stats and all source terms.
    videos: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add_video(self, obj: dict[str, Any]) -> None:
        vid = str(obj.get("id") or "")
        if not vid:
            return
        stats = {
            "play": int(obj.get("stats_play_count") or 0),
            "digg": int(obj.get("stats_digg_count") or 0),
            "comment": int(obj.get("stats_comment_count") or 0),
            "share": int(obj.get("stats_share_count") or 0),
            "collect": int(obj.get("stats_collect_count") or 0),
        }
        text_parts = [
            obj.get("desc") or "",
            " ".join(str(x) for x in (obj.get("hashtags") or [])),
            " ".join(str(x) for x in (obj.get("hashtags_text") or [])),
        ]
        text = " ".join(text_parts)
        if vid not in self.videos:
            self.videos[vid] = {
                "id": vid,
                "web_url": obj.get("web_url") or "",
                "desc": obj.get("desc") or "",
                "author_unique_id": obj.get("author_unique_id") or "",
                "source_terms": sorted({obj.get("source") or ""}),
                "play": stats["play"],
                "digg": stats["digg"],
                "comment": stats["comment"],
                "share": stats["share"],
                "collect": stats["collect"],
                "content_language_proxy": text_language_proxy(text),
            }
            return
        cur = self.videos[vid]
        cur["source_terms"] = sorted(set(cur.get("source_terms") or []) | {obj.get("source") or ""})
        for k, v in stats.items():
            cur[k] = max(int(cur.get(k) or 0), v)

    def summarize(self) -> dict[str, Any]:
        rows = list(self.videos.values())
        plays = [int(v["play"]) for v in rows]
        diggs = [int(v["digg"]) for v in rows]
        comments = [int(v["comment"]) for v in rows]
        shares = [int(v["share"]) for v in rows]
        unique_videos = len(rows)
        ge_1k = sum(p >= 1_000 for p in plays)
        ge_10k = sum(p >= 10_000 for p in plays)
        ge_100k = sum(p >= 100_000 for p in plays)
        ge_1m = sum(p >= 1_000_000 for p in plays)
        max_play = max(plays) if plays else 0
        p95_play = percentile(plays, 0.95)
        total_play = sum(plays)
        abs_tier = absolute_reach_tier(max_play, p95_play, total_play, ge_10k, ge_100k, unique_videos)
        stock = search_stock_proxy(self.term_rows)

        top = sorted(rows, key=lambda x: int(x.get("play") or 0), reverse=True)[:10]
        top_lang = Counter(v.get("content_language_proxy") or "unknown" for v in top)
        all_lang = Counter(v.get("content_language_proxy") or "unknown" for v in rows)
        ceiling_counts = Counter((r.get("ceiling_class") or r.get("depth_verdict") or "unknown") for r in self.term_rows)
        result_counts = Counter(r.get("result_class") or "unknown" for r in self.term_rows)
        term_scripts = Counter(r.get("term_script") or "unknown" for r in self.term_rows)

        return {
            "project_id": self.project["id"],
            "project_name": self.project["name_cn"],
            "project_name_en": self.project.get("name_en", ""),
            "list_type": self.project.get("list_type", ""),
            "category": self.project.get("category", ""),
            "search_terms_config_count": len(self.project.get("search_terms") or []),
            "term_result_count": len(self.term_rows),
            "term_scripts": dict(sorted(term_scripts.items())),
            "term_result_classes": dict(sorted(result_counts.items())),
            "ceiling_classes": dict(sorted(ceiling_counts.items())),
            "search_stock_proxy": stock,
            "unique_video_count": unique_videos,
            "row_video_count_after_project_dedupe": unique_videos,
            "total_play_count": total_play,
            "median_play_count": int(median(plays)) if plays else 0,
            "mean_play_count": int(round(mean(plays))) if plays else 0,
            "p75_play_count": percentile(plays, 0.75),
            "p90_play_count": percentile(plays, 0.90),
            "p95_play_count": p95_play,
            "p99_play_count": percentile(plays, 0.99),
            "max_play_count": max_play,
            "videos_ge_1k_play": ge_1k,
            "videos_ge_10k_play": ge_10k,
            "videos_ge_100k_play": ge_100k,
            "videos_ge_1m_play": ge_1m,
            "zero_play_videos": sum(p == 0 for p in plays),
            "zero_play_ratio": round((sum(p == 0 for p in plays) / unique_videos), 4) if unique_videos else 0,
            "total_digg_count": sum(diggs),
            "total_comment_count": sum(comments),
            "total_share_count": sum(shares),
            "max_digg_count": max(diggs) if diggs else 0,
            "max_comment_count": max(comments) if comments else 0,
            "max_share_count": max(shares) if shares else 0,
            "all_video_language_proxy_counts": dict(sorted(all_lang.items())),
            "top10_by_play_language_proxy_counts": dict(sorted(top_lang.items())),
            "top_video_id": top[0]["id"] if top else "",
            "top_video_url": top[0]["web_url"] if top else "",
            "top_video_author": top[0]["author_unique_id"] if top else "",
            "top_video_desc": top[0]["desc"][:240] if top else "",
            "absolute_reach_tier": abs_tier,
            "initial_reach_tier": "unassigned",
            "prelim_search_stock_x_reach_quadrant": "unassigned",
            "top_videos": top,
        }


def build_summary(config_path: Path, term_path: Path, videos_path: Path) -> list[dict[str, Any]]:
    cfg = load_json(config_path)
    projects = {int(p["id"]): p for p in cfg["projects"]}
    aggs = {pid: ProjectAgg(project=p) for pid, p in projects.items()}

    term_to_project: dict[str, int] = {}
    for row in iter_ndjson(term_path):
        pid = int(row["project_id"])
        if pid not in aggs:
            continue
        aggs[pid].term_rows.append(row)
        kw = row.get("keyword")
        if kw:
            if kw in term_to_project and term_to_project[kw] != pid:
                raise RuntimeError(f"Keyword maps to multiple projects: {kw!r}")
            term_to_project[kw] = pid

    unmatched_sources = Counter()
    for obj in iter_ndjson(videos_path):
        src = obj.get("source")
        pid = term_to_project.get(src)
        if not pid:
            unmatched_sources[src or ""] += 1
            continue
        aggs[pid].add_video(obj)

    if unmatched_sources:
        print("WARN unmatched video sources:", unmatched_sources.most_common(20))

    summaries = [aggs[pid].summarize() for pid in sorted(aggs)]
    assign_relative_reach_tiers(summaries)
    for row in summaries:
        row["prelim_search_stock_x_reach_quadrant"] = quadrant(row["search_stock_proxy"], row["initial_reach_tier"])
    return summaries


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Keep top_videos out of CSV; JSON has the nested evidence.
    fieldnames = [
        "project_id", "project_name", "project_name_en", "list_type", "category",
        "search_terms_config_count", "term_result_count", "term_scripts",
        "term_result_classes", "ceiling_classes", "search_stock_proxy",
        "unique_video_count", "total_play_count", "median_play_count", "mean_play_count",
        "p75_play_count", "p90_play_count", "p95_play_count", "p99_play_count", "max_play_count",
        "videos_ge_1k_play", "videos_ge_10k_play", "videos_ge_100k_play", "videos_ge_1m_play",
        "zero_play_videos", "zero_play_ratio", "total_digg_count", "total_comment_count",
        "total_share_count", "max_digg_count", "max_comment_count", "max_share_count",
        "all_video_language_proxy_counts", "top10_by_play_language_proxy_counts",
        "top_video_id", "top_video_url", "top_video_author", "top_video_desc",
        "absolute_reach_tier", "initial_reach_tier", "raw_reach_score", "prelim_search_stock_x_reach_quadrant",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            out = {k: r.get(k, "") for k in fieldnames}
            for k, v in list(out.items()):
                if isinstance(v, (dict, list)):
                    out[k] = json.dumps(v, ensure_ascii=False, sort_keys=True)
            w.writerow(out)


def write_json(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Derived from immutable search baseline. Reach tiers are initial coarse heuristics, not final research verdicts.",
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fmt_int(n: int) -> str:
    return f"{int(n):,}"


def write_markdown(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tier_counts = Counter(r["initial_reach_tier"] for r in rows)
    list_tier = defaultdict(Counter)
    quad_counts = Counter(r["prelim_search_stock_x_reach_quadrant"] for r in rows)
    stock_counts = Counter(r["search_stock_proxy"] for r in rows)
    for r in rows:
        list_tier[r["list_type"]][r["initial_reach_tier"]] += 1

    top_by_max = sorted(rows, key=lambda r: r["max_play_count"], reverse=True)[:12]
    top_by_total = sorted(rows, key=lambda r: r["total_play_count"], reverse=True)[:12]
    low_stock_high_reach = [r for r in rows if r["prelim_search_stock_x_reach_quadrant"] == "search_stock_low_or_unclear__reach_high"]
    high_stock_low_reach = [r for r in rows if r["prelim_search_stock_x_reach_quadrant"] == "search_stock_high__reach_low"]

    def bullet_project(r: dict[str, Any]) -> str:
        return (
            f"- **{r['project_name']}** ({r['list_type']}): tier=`{r['initial_reach_tier']}`, "
            f"unique_videos={r['unique_video_count']}, max_play={fmt_int(r['max_play_count'])}, "
            f"p95={fmt_int(r['p95_play_count'])}, total_play={fmt_int(r['total_play_count'])}, "
            f"stock_proxy=`{r['search_stock_proxy']}`"
        )

    lines: list[str] = []
    lines.append("# 触达维初步分析（由 search baseline 派生）")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：`data/sched_run_20260612_030425/videos.ndjson` + `term_results_labeled.ndjson` + `config/unesco_ich_keywords.v1.json`  ")
    lines.append("> 性质：**派生分析**，未修改原始 baseline。")
    lines.append("")
    lines.append("## 1. 口径提醒")
    lines.append("")
    lines.append("- 本文只做**触达维初步量化**：playCount / digg / comment / share。")
    lines.append("- `initial_reach_tier` 是透明阈值的初版分档，不是最终研究结论。")
    lines.append("- `search_stock_proxy` 只来自 search 触顶状态，仍不是最终存量轴；最终存量还要补 hashtag `statsV2.videoCount` + clean/noisy/unavailable。")
    lines.append("- `top10_by_play_language_proxy_counts` 是标题/标签文本语言代理，只能作为触达语言的粗线索，不能替代评论区受众语言。")
    lines.append("")
    lines.append("## 2. 总览")
    lines.append("")
    lines.append(f"- 项目数：**{len(rows)}**")
    lines.append(f"- 项目去重视频总数（按项目内去重后求和）：**{fmt_int(sum(r['unique_video_count'] for r in rows))}**")
    lines.append(f"- 总播放量（按项目内去重后求和，跨项目不再二次去重）：**{fmt_int(sum(r['total_play_count'] for r in rows))}**")
    lines.append("")
    lines.append("### 2.1 触达初档分布")
    lines.append("")
    for k in ["top_20pct_raw_reach", "high_20_40pct_raw_reach", "middle_40_70pct_raw_reach", "lower_70_90pct_raw_reach", "bottom_10pct_raw_reach"]:
        lines.append(f"- `{k}`: {tier_counts.get(k, 0)}")
    lines.append("")
    lines.append("### 2.2 按名录类别 × 触达初档")
    lines.append("")
    for lt in sorted(list_tier):
        parts = ", ".join(f"{k}={list_tier[lt].get(k,0)}" for k in ["top_20pct_raw_reach", "high_20_40pct_raw_reach", "middle_40_70pct_raw_reach", "lower_70_90pct_raw_reach", "bottom_10pct_raw_reach"])
        lines.append(f"- `{lt}`: {parts}")
    lines.append("")
    lines.append("### 2.3 search 存量代理分布")
    lines.append("")
    for k, v in stock_counts.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("### 2.4 初步 search-stock × reach 象限")
    lines.append("")
    for k, v in quad_counts.most_common():
        lines.append(f"- `{k}`: {v}")
    lines.append("")
    lines.append("## 3. 播放峰值最高的项目（max_play）")
    lines.append("")
    for r in top_by_max:
        lines.append(bullet_project(r))
        if r.get("top_video_url"):
            lines.append(f"  - top video: {r['top_video_url']}")
    lines.append("")
    lines.append("## 4. 累计播放最高的项目（total_play）")
    lines.append("")
    for r in top_by_total:
        lines.append(bullet_project(r))
    lines.append("")
    lines.append("## 5. 需要重点看的反差格")
    lines.append("")
    lines.append("### 5.1 search 存量触顶但触达低：可能是“内容多但没人看”的候选")
    lines.append("")
    if high_stock_low_reach:
        for r in sorted(high_stock_low_reach, key=lambda x: x["max_play_count"]):
            lines.append(bullet_project(r))
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("### 5.2 search 存量未触顶/不明确但触达高：可能是“小而精破圈”候选")
    lines.append("")
    if low_stock_high_reach:
        for r in sorted(low_stock_high_reach, key=lambda x: x["max_play_count"], reverse=True):
            lines.append(bullet_project(r))
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 6. 初版触达阈值")
    lines.append("")
    lines.append("- `top_20pct_raw_reach`: 本 baseline 内 raw reach score 前 20%")
    lines.append("- `high_20_40pct_raw_reach`: 20–40%")
    lines.append("- `middle_40_70pct_raw_reach`: 40–70%")
    lines.append("- `lower_70_90pct_raw_reach`: 70–90%")
    lines.append("- `bottom_10pct_raw_reach`: 后 10%")
    lines.append("- raw reach score = log10(total_play+1)*0.35 + log10(p95_play+1)*0.35 + log10(max_play+1)*0.20 + log10(videos_ge_100k+1)*0.10")
    lines.append("- 另保留 `absolute_reach_tier` 字段；本轮全部项目都因噪声/宽词召回而达到 absolute very_high，所以正式初档采用 cohort-relative 分位。")
    lines.append("")
    lines.append("## 7. 下一步")
    lines.append("")
    lines.append("1. 补 hashtag `statsV2.videoCount`，给每项目规模数据状态打 `clean/noisy/unavailable`。")
    lines.append("2. 用 hashtag 存量轴替换这里的 `search_stock_proxy`，生成正式 `存量 × 触达` 分层表。")
    lines.append("3. 对高触达项目抽 top videos 做触达语言复核；分层后再抽评论区做受众语言佐证。")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config/unesco_ich_keywords.v1.json"))
    ap.add_argument("--term-results", type=Path, default=Path("data/sched_run_20260612_030425/term_results_labeled.ndjson"))
    ap.add_argument("--videos", type=Path, default=Path("data/sched_run_20260612_030425/videos.ndjson"))
    ap.add_argument("--out-csv", type=Path, default=Path("data/derived/project_reach_summary.csv"))
    ap.add_argument("--out-json", type=Path, default=Path("data/derived/project_reach_summary.json"))
    ap.add_argument("--out-md", type=Path, default=Path("docs/触达维初步分析.md"))
    args = ap.parse_args()

    rows = build_summary(args.config, args.term_results, args.videos)
    write_csv(rows, args.out_csv)
    write_json(rows, args.out_json)
    write_markdown(rows, args.out_md)

    print(f"projects={len(rows)}")
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_json}")
    print(f"wrote {args.out_md}")
    print("reach_tiers", dict(Counter(r["initial_reach_tier"] for r in rows)))


if __name__ == "__main__":
    main()
