#!/usr/bin/env python3
"""Apply TikTok relevance guideline v1 to YouTube baseline and derive reach metrics.

This is intentionally a YouTube adapter of the TikTok relevance-aware pipeline:
- same three labels: likely_relevant / needs_review / low_relevance
- negative terms are label-only; rows are never deleted
- raw / likely / inclusive / low reach buckets are all preserved
- collection state (sample_limit/exhausted/failed/zero/ceiling) stays separate

Inputs default to the 3-page YouTube baseline under data/derived/youtube_initial_20260616_pages3.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

GENERIC_WEAK_TERMS = {
    "china", "chinese", "culture", "traditional", "tradition", "art", "music",
    "dance", "opera", "festival", "springfestival", "chineseopera", "martialarts",
    "folksong", "kyrgyz", "mongolian", "xinjiang", "fujian", "yangzhou",
    "silk", "tea", "printing", "papermaking", "dragonboat", "puppet", "epic",
}

CHINA_CONTEXT_TERMS = {
    "china", "chinese", "中国", "中华", "中文", "华人", "华裔", "cny", "lunarnewyear",
    "chinesenewyear", "springfestival", "mandarin", "tiktokchina", "抖音", "内蒙古",
    "fujian", "quanzhou", "cantonese", "hongkong", "hong kong", "tibet", "tibetan",
    "gansu", "nanjing", "xian", "xi'an", "uyghur", "dong", "li", "qiang",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
LABEL_BUCKETS = {
    "raw": {"likely_relevant", "needs_review", "low_relevance"},
    "likely": {"likely_relevant"},
    "inclusive": {"likely_relevant", "needs_review"},
    "low": {"low_relevance"},
}


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    if isinstance(s, (list, tuple, set)):
        s = " ".join(str(x) for x in s)
    else:
        s = str(s)
    s = s.lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", s)


def compact_term(s: Any) -> str:
    return norm_text(str(s or "").strip().lstrip("#"))


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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_int(v: Any) -> int:
    try:
        if v is None or v == "":
            return 0
        return int(float(v))
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


def project_terms(tiktok_project: dict[str, Any], youtube_project: dict[str, Any]) -> tuple[set[str], set[str], set[str], set[str]]:
    core_raw: set[str] = set()
    search_raw: set[str] = set()
    hashtag_raw: set[str] = set()
    yt_search_raw: set[str] = set()
    negative_raw: set[str] = set()
    for k, target in [
        ("core_terms", core_raw),
        ("search_terms", search_raw),
        ("hashtag_terms", hashtag_raw),
        ("negative_terms", negative_raw),
    ]:
        for t in tiktok_project.get(k) or []:
            target.add(str(t))
    for t in youtube_project.get("youtube_search_terms") or []:
        yt_search_raw.add(str(t))
    for t in youtube_project.get("youtube_negative_terms") or []:
        negative_raw.add(str(t))
    for t in youtube_project.get("youtube_uncertain_terms") or []:
        # uncertain terms are not hard negatives, but useful boundary signals.
        negative_raw.add(str(t))

    positive_raw = core_raw | search_raw | hashtag_raw | yt_search_raw
    positive = {norm_text(t) for t in positive_raw if norm_text(t)}
    core = {norm_text(t) for t in (core_raw | yt_search_raw) if norm_text(t)}
    negative = {norm_text(t) for t in negative_raw if norm_text(t)}
    weak = {compact_term(t) for t in (search_raw | yt_search_raw) if compact_term(t) in GENERIC_WEAK_TERMS}
    return positive, core, negative, weak


def build_project_maps(tiktok_config: Path, youtube_config: Path) -> tuple[dict[int, dict[str, Any]], dict[int, dict[str, Any]]]:
    tik = load_json(tiktok_config)
    yt = load_json(youtube_config)
    tik_by_id = {int(p["id"]): p for p in tik.get("projects", [])}
    yt_by_id = {int(p["id"]): p for p in yt.get("projects", [])}
    if set(tik_by_id) != set(yt_by_id):
        raise RuntimeError(f"TikTok/YouTube project id mismatch: {set(tik_by_id) ^ set(yt_by_id)}")
    return tik_by_id, yt_by_id


def load_term_meta(path: Path) -> dict[tuple[int, str], dict[str, Any]]:
    out: dict[tuple[int, str], dict[str, Any]] = {}
    for row in iter_ndjson(path):
        out[(int(row["project_id"]), str(row["search_keyword"]))] = row
    return out


def list_text(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for k in ["title", "description", "channelTitle"]:
        if row.get(k):
            parts.append(str(row.get(k)))
    tags = row.get("tags") or []
    if isinstance(tags, list):
        parts.extend(str(x) for x in tags)
    else:
        parts.append(str(tags))
    return " ".join(parts)


def label_video(row: dict[str, Any], tiktok_project: dict[str, Any], youtube_project: dict[str, Any], term_meta: dict[str, Any]) -> dict[str, Any]:
    raw_text = list_text(row)
    text = norm_text(raw_text)
    title_desc = " ".join(str(row.get(k) or "") for k in ["title", "description"])
    source = str(row.get("search_keyword") or "")
    source_norm = compact_term(source)
    positive, core_terms, negative_terms, weak_search_terms = project_terms(tiktok_project, youtube_project)
    if source_norm:
        positive.add(source_norm)
        core_terms.add(source_norm)

    hit_set = {t for t in positive if t and t in text}
    core_hit_set = {t for t in core_terms if t and t in text}
    negative_hit_set = {t for t in negative_terms if t and t in text}
    china_context_set = {norm_text(t) for t in CHINA_CONTEXT_TERMS if norm_text(t) and norm_text(t) in text}

    source_hit = bool(source_norm and source_norm in text)
    has_cjk_text = bool(CJK_RE.search(title_desc))
    weak_generic_source = source_norm in GENERIC_WEAK_TERMS or source_norm in weak_search_terms
    zero_view = parse_int(row.get("viewCount")) == 0
    empty_text = not title_desc.strip()

    score = 0
    reasons: list[str] = []
    if source_hit:
        score += 2
        reasons.append("source_hit")
    if hit_set:
        score += min(4, len(hit_set))
        reasons.append(f"project_term_hits:{len(hit_set)}")
    if core_hit_set:
        score += min(2, len(core_hit_set))
        reasons.append(f"core_term_hits:{len(core_hit_set)}")
    if china_context_set:
        score += 1
        reasons.append("china_context")
    if has_cjk_text:
        score += 1
        reasons.append("cjk_text")
    if zero_view:
        score -= 1
        reasons.append("zero_view")
    if empty_text:
        score -= 2
        reasons.append("empty_text")
    if weak_generic_source and not (hit_set - {source_norm}):
        score -= 2
        reasons.append("generic_source_only")
    if negative_hit_set:
        score -= min(4, len(negative_hit_set) * 2)
        reasons.append(f"negative_term_hits:{len(negative_hit_set)}")

    if score >= 4:
        label = "likely_relevant"
    elif score >= 2:
        label = "needs_review"
    else:
        label = "low_relevance"

    pid = int(row["project_id"])
    return {
        "source_platform": "youtube",
        "project_id": pid,
        "project_name": tiktok_project.get("name_cn", youtube_project.get("name_cn", "")),
        "project_name_en": tiktok_project.get("name_en", youtube_project.get("name_en", "")),
        "list_type": tiktok_project.get("list_type", ""),
        "category": tiktok_project.get("category", youtube_project.get("category", "")),
        "video_id": str(row.get("video_id") or ""),
        "web_url": row.get("url") or "",
        "source_term": source,
        "youtube_collection_state": term_meta.get("stop_reason", "unknown"),
        "youtube_pages_fetched": parse_int(term_meta.get("pages_fetched")),
        "youtube_totalResults_estimate": parse_int(term_meta.get("totalResults_estimate")),
        "youtube_is_three_page_lower_bound": term_meta.get("stop_reason") == "sample_limit_reached",
        "title": row.get("title") or "",
        "desc": row.get("description") or "",
        "tags": row.get("tags") or [],
        "channelId": row.get("channelId") or "",
        "channelTitle": row.get("channelTitle") or "",
        "publishDate": row.get("publishDate") or "",
        "stats_play_count": parse_int(row.get("viewCount")),
        "stats_digg_count": parse_int(row.get("likeCount")),
        "stats_comment_count": parse_int(row.get("commentCount")),
        "stats_share_count": 0,
        "quality_score": score,
        "quality_label": label,
        "quality_reasons": reasons,
        "matched_terms": sorted(hit_set)[:30],
        "core_matched_terms": sorted(core_hit_set)[:30],
        "negative_matched_terms": sorted(negative_hit_set)[:30],
        "source_hit_in_text": source_hit,
        "china_context_hit": bool(china_context_set),
        "china_context_terms": sorted(china_context_set),
        "has_cjk_text": has_cjk_text,
        "weak_generic_source": weak_generic_source,
        "needs_manual_review": label == "needs_review" or bool(negative_hit_set),
    }


def derive_labels(videos_path: Path, term_meta_path: Path, tiktok_config: Path, youtube_config: Path) -> list[dict[str, Any]]:
    tik_by_id, yt_by_id = build_project_maps(tiktok_config, youtube_config)
    meta = load_term_meta(term_meta_path)
    labels: list[dict[str, Any]] = []
    missing_meta = Counter()
    for row in iter_ndjson(videos_path):
        pid = int(row["project_id"])
        source = str(row.get("search_keyword") or "")
        tm = meta.get((pid, source))
        if not tm:
            missing_meta[(pid, source)] += 1
            tm = {}
        labels.append(label_video(row, tik_by_id[pid], yt_by_id[pid], tm))
    if missing_meta:
        print("WARN missing term meta", missing_meta.most_common(20))
    return labels


def dedupe_project_video(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    best: dict[tuple[int, str], dict[str, Any]] = {}
    for r in rows:
        key = (int(r["project_id"]), str(r["video_id"]))
        cur = best.get(key)
        if cur is None or (r["quality_score"], r["stats_play_count"]) > (cur["quality_score"], cur["stats_play_count"]):
            best[key] = r
    return best


def project_relevance_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best = dedupe_project_video(rows)
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in best.values():
        by_project[int(r["project_id"])].append(r)
    summaries: list[dict[str, Any]] = []
    for pid in sorted(by_project):
        xs = by_project[pid]
        labels = Counter(r["quality_label"] for r in xs)
        reasons = Counter(reason for r in xs for reason in r.get("quality_reasons", []))
        neg_terms = Counter(t for r in xs for t in r.get("negative_matched_terms", []))
        states = Counter(r.get("youtube_collection_state") for r in xs)
        plays_by_label = defaultdict(int)
        max_by_label = defaultdict(int)
        for r in xs:
            lab = r["quality_label"]
            plays_by_label[lab] += r["stats_play_count"]
            max_by_label[lab] = max(max_by_label[lab], r["stats_play_count"])
        n = len(xs)
        summaries.append({
            "project_id": pid,
            "project_name": xs[0]["project_name"],
            "list_type": xs[0].get("list_type", ""),
            "category": xs[0].get("category", ""),
            "unique_videos": n,
            "likely_relevant": labels.get("likely_relevant", 0),
            "needs_review": labels.get("needs_review", 0),
            "low_relevance": labels.get("low_relevance", 0),
            "likely_ratio": round(labels.get("likely_relevant", 0) / n, 4) if n else 0,
            "needs_review_ratio": round(labels.get("needs_review", 0) / n, 4) if n else 0,
            "low_relevance_ratio": round(labels.get("low_relevance", 0) / n, 4) if n else 0,
            "avg_quality_score": round(mean([r["quality_score"] for r in xs]), 3) if xs else 0,
            "negative_hit_videos": sum(1 for r in xs if r.get("negative_matched_terms")),
            "negative_hit_ratio": round(sum(1 for r in xs if r.get("negative_matched_terms")) / n, 4) if n else 0,
            "weak_generic_source_videos": sum(1 for r in xs if r.get("weak_generic_source")),
            "weak_generic_source_ratio": round(sum(1 for r in xs if r.get("weak_generic_source")) / n, 4) if n else 0,
            "three_page_lower_bound_videos": sum(1 for r in xs if r.get("youtube_is_three_page_lower_bound")),
            "three_page_lower_bound_ratio": round(sum(1 for r in xs if r.get("youtube_is_three_page_lower_bound")) / n, 4) if n else 0,
            "collection_state_counts": dict(states),
            "total_play_likely": plays_by_label.get("likely_relevant", 0),
            "total_play_needs_review": plays_by_label.get("needs_review", 0),
            "total_play_low_relevance": plays_by_label.get("low_relevance", 0),
            "max_play_likely": max_by_label.get("likely_relevant", 0),
            "max_play_needs_review": max_by_label.get("needs_review", 0),
            "max_play_low_relevance": max_by_label.get("low_relevance", 0),
            "top_quality_reasons": dict(reasons.most_common(8)),
            "top_negative_terms": dict(neg_terms.most_common(8)),
        })
    return summaries


def metric_for(rows: list[dict[str, Any]], labels: set[str]) -> dict[str, Any]:
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
    likes = [int(r.get("stats_digg_count") or 0) for r in xs]
    comments = [int(r.get("stats_comment_count") or 0) for r in xs]
    top = max(xs, key=lambda r: int(r.get("stats_play_count") or 0)) if xs else None
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
        "total_digg": sum(likes),
        "total_comment": sum(comments),
        "total_share": 0,
        "max_digg": max(likes) if likes else 0,
        "max_comment": max(comments) if comments else 0,
        "max_share": 0,
        "top_video_id": top.get("video_id", "") if top else "",
        "top_video_url": top.get("web_url", "") if top else "",
        "top_video_desc": ((top.get("title", "") + " — " + top.get("desc", ""))[:220] if top else ""),
    }


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


def reach_summary(rows: list[dict[str, Any]], tiktok_config: Path) -> list[dict[str, Any]]:
    tik = load_json(tiktok_config)
    projects = {int(p["id"]): p for p in tik.get("projects", [])}
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_project[int(r["project_id"])].append(r)
    out: list[dict[str, Any]] = []
    for pid in sorted(projects):
        xs = by_project.get(pid, [])
        p = projects[pid]
        base: dict[str, Any] = {
            "project_id": pid,
            "project_name": p.get("name_cn", ""),
            "project_name_en": p.get("name_en", ""),
            "list_type": p.get("list_type", ""),
            "category": p.get("category", ""),
        }
        label_counts = Counter(r.get("quality_label") for r in xs)
        state_counts = Counter(r.get("youtube_collection_state") for r in xs)
        base.update({
            "label_likely_relevant_rows": label_counts.get("likely_relevant", 0),
            "label_needs_review_rows": label_counts.get("needs_review", 0),
            "label_low_relevance_rows": label_counts.get("low_relevance", 0),
            "youtube_collection_state_counts": dict(state_counts),
            "youtube_three_page_lower_bound_rows": sum(1 for r in xs if r.get("youtube_is_three_page_lower_bound")),
        })
        for prefix, labs in LABEL_BUCKETS.items():
            m = metric_for(xs, labs)
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
        out.append(base)
    assign_relative_tiers(out, "raw", "raw_reach_tier", "raw_reach_score")
    assign_relative_tiers(out, "likely", "likely_reach_tier", "likely_reach_score")
    assign_relative_tiers(out, "inclusive", "inclusive_reach_tier", "inclusive_reach_score")
    order = {
        "top_20pct_reach": 5,
        "high_20_40pct_reach": 4,
        "middle_40_70pct_reach": 3,
        "lower_70_90pct_reach": 2,
        "bottom_10pct_reach": 1,
        "no_videos": 0,
    }
    for r in out:
        r["reach_tier_changed_after_relevance_filter"] = r["raw_reach_tier"] != r["likely_reach_tier"]
        r["raw_to_likely_tier_delta"] = order.get(r["likely_reach_tier"], 0) - order.get(r["raw_reach_tier"], 0)
    return out


def write_ndjson(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


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
        for r in rows:
            out = dict(r)
            for k, v in list(out.items()):
                if isinstance(v, (dict, list)):
                    out[k] = json.dumps(v, ensure_ascii=False, sort_keys=True)
            w.writerow(out)


def write_json(rows: list[dict[str, Any]], path: Path, note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "note": note, "rows": rows}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def md_project_line(r: dict[str, Any]) -> str:
    return (
        f"- **{r['project_name']}**: raw={r['raw_unique_videos']} / likely={r['likely_unique_videos']} "
        f"({r['likely_video_ratio']:.1%}), low={r['low_unique_videos']} ({r['low_relevance_video_ratio']:.1%}); "
        f"likely_play={r['likely_total_play']:,}, raw_play={r['raw_total_play']:,}, risk={r['reach_noise_risk']}, tier={r['likely_reach_tier']}"
    )


def write_report(rel_summary: list[dict[str, Any]], reach_rows: list[dict[str, Any]], term_meta_path: Path, report_path: Path) -> None:
    term_rows = list(iter_ndjson(term_meta_path))
    state_counts = Counter(r.get("stop_reason") for r in term_rows)
    total_unique = sum(r["unique_videos"] for r in rel_summary)
    labels = Counter()
    for r in rel_summary:
        labels["likely_relevant"] += r["likely_relevant"]
        labels["needs_review"] += r["needs_review"]
        labels["low_relevance"] += r["low_relevance"]
    low_noise = sorted(reach_rows, key=lambda r: (r["low_relevance_play_ratio"], r["low_total_play"]), reverse=True)[:12]
    top_likely = sorted(reach_rows, key=lambda r: (r["likely_reach_score"], r["likely_total_play"]), reverse=True)[:12]
    tier_drop = sorted([r for r in reach_rows if r["raw_to_likely_tier_delta"] < 0], key=lambda r: r["raw_to_likely_tier_delta"])[:12]
    exhausted_terms = [r for r in term_rows if r.get("stop_reason") == "exhausted"]
    known_cross_platform_low = {"Kgal laox", "Longquan celadon", "Chinese Regong art", "Khoomei throat singing", "Mongolian long song"}

    lines: list[str] = []
    lines.append("# YouTube 相关性 + 触达初步汇总（3页扩采）")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：`data/derived/youtube_initial_20260616_pages3/`  ")
    lines.append("> 口径：复用 TikTok 相关性口径 v1；派生标签，不删除 raw 视频。")
    lines.append("")
    lines.append("## 1. 口径确认")
    lines.append("")
    lines.append("- 三档标签沿用 TikTok：`likely_relevant / needs_review / low_relevance`。")
    lines.append("- `low_relevance` 不删除，只作为噪声与语义稀释风险进入后续判断。")
    lines.append("- 组员标出的 YouTube 噪声词作为 `negative_terms` 参考，例如 calligraphy / paper cutting / timber architecture / Korean farmers dance 等；命中后降分并保留证据。")
    lines.append("- `failed / zero_real / exhausted / sample_limit_reached / ceiling_capped_500` 与相关性标签分开，不混用。")
    lines.append("- 当前 56 个 `sample_limit_reached` 词是**3页截断下限**，不是平台硬顶；热门项目 YouTube 触达会被低估，后续深采要继续加页。")
    lines.append("")
    lines.append("## 2. 采集状态")
    lines.append("")
    lines.append(f"- term 数：{len(term_rows)}")
    for k, v in state_counts.items():
        lines.append(f"- `{k}`: {v}")
    lines.append("- `sample_limit_reached` = 人为 3 页限制后的下限；区别于 TikTok search 接口约 196 条的真实平台翻页上限。")
    lines.append("")
    lines.append("## 3. 相关性分布（项目内去重后求和）")
    lines.append("")
    lines.append(f"- 项目数：{len(rel_summary)}")
    lines.append(f"- 项目内去重视频总数：{total_unique:,}")
    for lab in ["likely_relevant", "needs_review", "low_relevance"]:
        n = labels[lab]
        lines.append(f"- `{lab}`: {n:,} ({(n/total_unique if total_unique else 0):.1%})")
    lines.append("")
    lines.append("## 4. likely 触达最高的项目（当前为3页下限）")
    lines.append("")
    for r in top_likely:
        lines.append(md_project_line(r))
    lines.append("")
    lines.append("## 5. 噪声风险最高的项目")
    lines.append("")
    for r in low_noise:
        lines.append(md_project_line(r))
    lines.append("")
    lines.append("## 6. raw → likely 后触达档位下跌项目")
    lines.append("")
    if tier_drop:
        for r in tier_drop:
            lines.append(f"- **{r['project_name']}**: raw_tier={r['raw_reach_tier']} → likely_tier={r['likely_reach_tier']}, delta={r['raw_to_likely_tier_delta']}, low_play_ratio={r['low_relevance_play_ratio']:.1%}")
    else:
        lines.append("- 暂无 raw→likely 相对档位下跌项目；后续仍需人工抽查高播放 raw top 是否为噪声。")
    lines.append("")
    lines.append("## 7. 3页内自然采空词与跨平台一致低存量")
    lines.append("")
    for r in exhausted_terms:
        marker = "（与 TikTok 低存量方向一致，先记为可用发现）" if r.get("search_keyword") in known_cross_platform_low else ""
        lines.append(f"- **{r.get('heritage_item')}** — `{r.get('search_keyword')}`: collected={r.get('collected_count')}, totalResults_estimate≈{r.get('totalResults_estimate')} {marker}")
    lines.append("")
    lines.append("这 5 个词不是 3页人为截断，而是在当前 YouTube relevance 搜索口径下自然结束；其中侗族大歌、龙泉青瓷、热贡、呼麦、蒙古族长调与 TikTok 低存量方向一致，后续可作为跨平台一致性发现继续验证。")
    lines.append("")
    lines.append("## 8. 下一步")
    lines.append("")
    lines.append("1. 先由本表挑 deep-crawl 候选：YouTube likely 高触达、raw→likely 噪声变化大、以及 TikTok 关键象限项目。")
    lines.append("2. 深采名单不要按 YouTube raw 热度单独决定，要参照 TikTok 存量×触达象限。")
    lines.append("3. 对仍为 `sample_limit_reached` 的热门词继续加页；采到 10 页仍有 nextPageToken 时再标 `ceiling_capped_500`。")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--youtube-dir", type=Path, default=Path("data/derived/youtube_initial_20260616_pages3"))
    ap.add_argument("--tiktok-config", type=Path, default=Path("config/unesco_ich_keywords.v1.json"))
    ap.add_argument("--youtube-config", type=Path, default=Path("config/youtube_ich_search_terms.v1.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/YouTube相关性触达初步汇总_20260616.md"))
    args = ap.parse_args()

    videos_path = args.youtube_dir / "youtube_videos.ndjson"
    term_meta_path = args.youtube_dir / "youtube_search_term_meta.ndjson"
    labels = derive_labels(videos_path, term_meta_path, args.tiktok_config, args.youtube_config)
    rel_summary = project_relevance_summary(labels)
    reach_rows = reach_summary(labels, args.tiktok_config)

    write_ndjson(labels, args.youtube_dir / "youtube_video_relevance_labels.ndjson")
    write_csv(rel_summary, args.youtube_dir / "youtube_project_relevance_summary.csv")
    write_json(rel_summary, args.youtube_dir / "youtube_project_relevance_summary.json", "YouTube project relevance summary; TikTok guideline v1 adapter.")
    write_csv(reach_rows, args.youtube_dir / "youtube_project_reach_relevance_aware.csv")
    write_json(reach_rows, args.youtube_dir / "youtube_project_reach_relevance_aware.json", "YouTube relevance-aware reach metrics: raw/likely/inclusive/low buckets retained.")
    write_report(rel_summary, reach_rows, term_meta_path, args.out_report)

    print(f"labels={len(labels)} rel_projects={len(rel_summary)} reach_projects={len(reach_rows)}")
    print("label_counts", dict(Counter(r["quality_label"] for r in dedupe_project_video(labels).values())))
    print(f"wrote {args.youtube_dir / 'youtube_video_relevance_labels.ndjson'}")
    print(f"wrote {args.youtube_dir / 'youtube_project_reach_relevance_aware.csv'}")
    print(f"wrote {args.out_report}")


if __name__ == "__main__":
    main()
