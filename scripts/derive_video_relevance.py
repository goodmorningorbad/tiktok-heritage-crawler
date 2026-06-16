#!/usr/bin/env python3
"""Apply relevance guideline v1 to the fixed TikTok search baseline.

This is a DERIVED analysis step. It reads immutable baseline NDJSON files,
maps each video row back to its UNESCO project via the term_results stream, and
adds the same three-bucket relevance labels used in the earlier manual-review
workflow:

- likely_relevant
- needs_review
- low_relevance

No raw collection data is modified and no rows are deleted.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

GENERIC_WEAK_TERMS = {
    "china", "chinese", "culture", "traditional", "tradition", "art", "music",
    "dance", "opera", "festival", "springfestival", "chineseopera", "martialarts",
    "folksong", "kyrgyz", "mongolian", "xinjiang", "fujian", "yangzhou",
    # single broad media/product terms observed in this project
    "silk", "tea", "printing", "papermaking", "dragonboat", "puppet", "epic",
}

CHINA_CONTEXT_TERMS = {
    "china", "chinese", "中国", "中华", "中文", "华人", "华裔", "cny", "lunarnewyear",
    "chinesenewyear", "springfestival", "mandarin", "tiktokchina", "抖音", "内蒙古",
    "fujian", "quanzhou", "cantonese", "hongkong", "hong kong", "tibet", "tibetan",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]")


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


def load_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["by_id"] = {int(p["id"]): p for p in data.get("projects", [])}
    data["by_name"] = {p.get("name_cn", ""): p for p in data.get("projects", []) if p.get("name_cn")}
    return data


def build_term_project_map(term_results_path: Path) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for row in iter_ndjson(term_results_path):
        key = str(row.get("keyword") or "")
        if not key:
            continue
        if key in mapping and mapping[key].get("project_id") != row.get("project_id"):
            raise RuntimeError(f"keyword maps to multiple projects: {key!r}")
        mapping[key] = {
            "project_id": int(row["project_id"]),
            "project_name": row.get("project_name") or "",
            "term_script": row.get("term_script") or "unknown",
            "term_result_class": row.get("result_class") or "unknown",
            "ceiling_class": row.get("ceiling_class") or row.get("depth_verdict") or "unknown",
        }
    return mapping


def project_terms(project: dict[str, Any]) -> tuple[set[str], set[str], set[str], set[str]]:
    positive_raw = set()
    core_raw = set()
    search_raw = set()
    hashtag_raw = set()
    negative_raw = set()
    for k, target in [
        ("core_terms", core_raw),
        ("search_terms", search_raw),
        ("hashtag_terms", hashtag_raw),
        ("negative_terms", negative_raw),
    ]:
        for t in project.get(k) or []:
            target.add(str(t))
    positive_raw |= core_raw | search_raw | hashtag_raw
    positive = {norm_text(t) for t in positive_raw if norm_text(t)}
    core = {norm_text(t) for t in core_raw if norm_text(t)}
    negative = {norm_text(t) for t in negative_raw if norm_text(t)}
    weak = {compact_term(t) for t in search_raw if compact_term(t) in GENERIC_WEAK_TERMS}
    return positive, core, negative, weak


def list_text(obj: dict[str, Any]) -> str:
    parts: list[str] = []
    for k in ["desc", "author_nickname", "author_unique_id", "music_title", "music_author"]:
        if obj.get(k):
            parts.append(str(obj.get(k)))
    for k in ["hashtags", "hashtags_text"]:
        v = obj.get(k) or []
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        else:
            parts.append(str(v))
    return " ".join(parts)


def parse_int(v: Any) -> int:
    try:
        return int(float(v or 0))
    except Exception:
        return 0


def label_video(obj: dict[str, Any], project: dict[str, Any], term_info: dict[str, Any]) -> dict[str, Any]:
    raw_text = list_text(obj)
    text = norm_text(raw_text)
    desc = obj.get("desc") or ""
    source = str(obj.get("source") or "")
    source_norm = compact_term(source)
    positive, core_terms, negative_terms, weak_search_terms = project_terms(project)
    if source_norm:
        positive.add(source_norm)

    hit_set = {t for t in positive if t and t in text}
    core_hit_set = {t for t in core_terms if t and t in text}
    negative_hit_set = {t for t in negative_terms if t and t in text}
    china_context_set = {norm_text(t) for t in CHINA_CONTEXT_TERMS if norm_text(t) and norm_text(t) in text}

    source_hit = bool(source_norm and source_norm in text)
    has_cjk_desc = bool(CJK_RE.search(desc))
    weak_generic_source = source_norm in GENERIC_WEAK_TERMS or source_norm in weak_search_terms
    zero_play = parse_int(obj.get("stats_play_count")) == 0
    empty_desc = not str(desc).strip()

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
    if has_cjk_desc:
        score += 1
        reasons.append("cjk_desc")
    if zero_play:
        score -= 1
        reasons.append("zero_play")
    if empty_desc:
        score -= 2
        reasons.append("empty_desc")
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

    return {
        "project_id": int(project["id"]),
        "project_name": project.get("name_cn", ""),
        "project_name_en": project.get("name_en", ""),
        "list_type": project.get("list_type", ""),
        "category": project.get("category", ""),
        "video_id": str(obj.get("id") or ""),
        "web_url": obj.get("web_url") or "",
        "source_term": source,
        "term_script": term_info.get("term_script") or "unknown",
        "term_result_class": term_info.get("term_result_class") or "unknown",
        "ceiling_class": term_info.get("ceiling_class") or "unknown",
        "author_unique_id": obj.get("author_unique_id") or "",
        "desc": desc,
        "hashtags": obj.get("hashtags") or [],
        "hashtags_text": obj.get("hashtags_text") or [],
        "stats_play_count": parse_int(obj.get("stats_play_count")),
        "stats_digg_count": parse_int(obj.get("stats_digg_count")),
        "stats_comment_count": parse_int(obj.get("stats_comment_count")),
        "stats_share_count": parse_int(obj.get("stats_share_count")),
        "stats_collect_count": parse_int(obj.get("stats_collect_count")),
        "quality_score": score,
        "quality_label": label,
        "quality_reasons": reasons,
        "matched_terms": sorted(hit_set)[:30],
        "core_matched_terms": sorted(core_hit_set)[:30],
        "negative_matched_terms": sorted(negative_hit_set)[:30],
        "source_hit_in_text": source_hit,
        "china_context_hit": bool(china_context_set),
        "china_context_terms": sorted(china_context_set),
        "has_cjk_desc": has_cjk_desc,
        "weak_generic_source": weak_generic_source,
        "needs_manual_review": label == "needs_review" or bool(negative_hit_set),
    }


def dedupe_key(row: dict[str, Any]) -> tuple[int, str]:
    return int(row["project_id"]), str(row["video_id"])


def derive(config_path: Path, term_results_path: Path, videos_path: Path) -> list[dict[str, Any]]:
    cfg = load_config(config_path)
    by_id = cfg["by_id"]
    term_map = build_term_project_map(term_results_path)
    out: list[dict[str, Any]] = []
    unmatched = Counter()
    for obj in iter_ndjson(videos_path):
        src = str(obj.get("source") or "")
        info = term_map.get(src)
        if not info:
            unmatched[src] += 1
            continue
        project = by_id[int(info["project_id"])]
        out.append(label_video(obj, project, info))
    if unmatched:
        print("WARN unmatched sources", unmatched.most_common(20))
    return out


def write_ndjson(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def project_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    # project-level dedupe by video id: if a video appears under multiple terms of the same project,
    # keep the highest relevance score; ties keep max play.
    best: dict[tuple[int, str], dict[str, Any]] = {}
    for r in rows:
        key = dedupe_key(r)
        cur = best.get(key)
        if cur is None or (r["quality_score"], r["stats_play_count"]) > (cur["quality_score"], cur["stats_play_count"]):
            best[key] = r
    for r in best.values():
        by_project[int(r["project_id"])].append(r)

    summaries = []
    for pid in sorted(by_project):
        xs = by_project[pid]
        labels = Counter(r["quality_label"] for r in xs)
        reasons = Counter(reason for r in xs for reason in r.get("quality_reasons", []))
        neg_terms = Counter(t for r in xs for t in r.get("negative_matched_terms", []))
        plays_by_label = defaultdict(int)
        max_by_label = defaultdict(int)
        for r in xs:
            lab = r["quality_label"]
            plays_by_label[lab] += r["stats_play_count"]
            max_by_label[lab] = max(max_by_label[lab], r["stats_play_count"])
        n = len(xs)
        likely_n = labels.get("likely_relevant", 0)
        low_n = labels.get("low_relevance", 0)
        summary = {
            "project_id": pid,
            "project_name": xs[0]["project_name"],
            "list_type": xs[0]["list_type"],
            "unique_videos": n,
            "likely_relevant": likely_n,
            "needs_review": labels.get("needs_review", 0),
            "low_relevance": low_n,
            "likely_ratio": round(likely_n / n, 4) if n else 0,
            "needs_review_ratio": round(labels.get("needs_review", 0) / n, 4) if n else 0,
            "low_relevance_ratio": round(low_n / n, 4) if n else 0,
            "avg_quality_score": round(mean([r["quality_score"] for r in xs]), 3) if xs else 0,
            "negative_hit_videos": sum(1 for r in xs if r.get("negative_matched_terms")),
            "negative_hit_ratio": round(sum(1 for r in xs if r.get("negative_matched_terms")) / n, 4) if n else 0,
            "weak_generic_source_videos": sum(1 for r in xs if r.get("weak_generic_source")),
            "weak_generic_source_ratio": round(sum(1 for r in xs if r.get("weak_generic_source")) / n, 4) if n else 0,
            "total_play_likely": plays_by_label.get("likely_relevant", 0),
            "total_play_needs_review": plays_by_label.get("needs_review", 0),
            "total_play_low_relevance": plays_by_label.get("low_relevance", 0),
            "max_play_likely": max_by_label.get("likely_relevant", 0),
            "max_play_needs_review": max_by_label.get("needs_review", 0),
            "max_play_low_relevance": max_by_label.get("low_relevance", 0),
            "top_quality_reasons": dict(reasons.most_common(8)),
            "top_negative_terms": dict(neg_terms.most_common(8)),
        }
        summaries.append(summary)
    return summaries


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            out = dict(r)
            for k, v in list(out.items()):
                if isinstance(v, (dict, list)):
                    out[k] = json.dumps(v, ensure_ascii=False, sort_keys=True)
            w.writerow(out)


def write_json(rows: list[dict[str, Any]], path: Path, note: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_report(summaries: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    total = sum(r["unique_videos"] for r in summaries)
    totals = Counter()
    for r in summaries:
        totals["likely_relevant"] += r["likely_relevant"]
        totals["needs_review"] += r["needs_review"]
        totals["low_relevance"] += r["low_relevance"]
    low_noise = sorted(summaries, key=lambda r: (r["low_relevance_ratio"], r["total_play_low_relevance"]), reverse=True)[:12]
    high_likely = sorted(summaries, key=lambda r: (r["likely_ratio"], r["likely_relevant"]), reverse=True)[:12]
    neg_hit = sorted(summaries, key=lambda r: (r["negative_hit_ratio"], r["negative_hit_videos"]), reverse=True)[:12]

    def line(r: dict[str, Any]) -> str:
        return (
            f"- **{r['project_name']}** ({r['list_type']}): n={r['unique_videos']}, "
            f"likely={r['likely_relevant']} ({r['likely_ratio']:.1%}), "
            f"needs_review={r['needs_review']} ({r['needs_review_ratio']:.1%}), "
            f"low={r['low_relevance']} ({r['low_relevance_ratio']:.1%}), "
            f"neg_hit={r['negative_hit_videos']} ({r['negative_hit_ratio']:.1%})"
        )

    lines = []
    lines.append("# 相关性口径 v1：baseline 应用报告")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 输入：`videos.ndjson` + `term_results_labeled.ndjson` + `config/unesco_ich_keywords.v1.json`  ")
    lines.append("> 性质：派生标签；不删除、不覆盖原始数据。")
    lines.append("")
    lines.append("## 1. 口径来源")
    lines.append("")
    lines.append("- 继承此前 60 条人工核查后的三档口径：`likely_relevant / needs_review / low_relevance`。")
    lines.append("- 校正后人工核查结果：likely 桶 relevant 17/20，needs_review 桶 relevant 8/20，low 桶 relevant 4/20。")
    lines.append("- 因 low 桶仍有真相关，本文只打派生标签，**不删除任何视频**。")
    lines.append("")
    lines.append("## 2. baseline 全体分布（项目内去重后求和）")
    lines.append("")
    lines.append(f"- 项目数：{len(summaries)}")
    lines.append(f"- 项目内去重视频总数：{total:,}")
    for lab in ["likely_relevant", "needs_review", "low_relevance"]:
        n = totals[lab]
        lines.append(f"- `{lab}`: {n:,} ({(n/total if total else 0):.1%})")
    lines.append("")
    lines.append("## 3. likely 比例最高的项目")
    lines.append("")
    for r in high_likely:
        lines.append(line(r))
    lines.append("")
    lines.append("## 4. low_relevance 比例最高 / 噪声风险候选")
    lines.append("")
    for r in low_noise:
        lines.append(line(r))
    lines.append("")
    lines.append("## 5. negative_terms 命中最高的项目")
    lines.append("")
    for r in neg_hit:
        lines.append(line(r))
        if r.get("top_negative_terms"):
            lines.append(f"  - top negative terms: `{json.dumps(r['top_negative_terms'], ensure_ascii=False)}`")
    lines.append("")
    lines.append("## 6. 下一步")
    lines.append("")
    lines.append("1. 用本标签重算触达：raw / likely / inclusive(likely+needs_review) / low 四套。")
    lines.append("2. 标记 raw 高但 likely 后明显下跌的项目，作为人工复核优先对象。")
    lines.append("3. 后续分层时同时保留 raw 与 relevance-aware 结果，避免噪声热门视频抬高结论。")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config/unesco_ich_keywords.v1.json"))
    ap.add_argument("--term-results", type=Path, default=Path("data/sched_run_20260612_030425/term_results_labeled.ndjson"))
    ap.add_argument("--videos", type=Path, default=Path("data/sched_run_20260612_030425/videos.ndjson"))
    ap.add_argument("--out-labels", type=Path, default=Path("data/derived/video_relevance_labels.ndjson"))
    ap.add_argument("--out-summary-csv", type=Path, default=Path("data/derived/project_relevance_summary.csv"))
    ap.add_argument("--out-summary-json", type=Path, default=Path("data/derived/project_relevance_summary.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/相关性口径v1_baseline应用报告.md"))
    args = ap.parse_args()

    labels = derive(args.config, args.term_results, args.videos)
    summaries = project_summary(labels)
    write_ndjson(labels, args.out_labels)
    write_csv(summaries, args.out_summary_csv)
    write_json(summaries, args.out_summary_json, "Project-level relevance summary derived from video_relevance_labels.ndjson")
    write_report(summaries, args.out_report)
    print(f"labels={len(labels)} summaries={len(summaries)}")
    print("label_counts", dict(Counter(r["quality_label"] for r in labels)))
    print(f"wrote {args.out_labels}")
    print(f"wrote {args.out_summary_csv}")
    print(f"wrote {args.out_summary_json}")
    print(f"wrote {args.out_report}")


if __name__ == "__main__":
    main()
