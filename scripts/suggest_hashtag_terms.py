#!/usr/bin/env python3
"""Suggest TikTok hashtag term fixes from second-test data."""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler import create_api

CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_RE = re.compile(r"[A-Za-z]")

COMMON_ENGLISH: dict[str, list[str]] = {
    "赫哲族伊玛堪": ["yimakan", "hezhefolk", "yimakanstorytelling"],
    "麦西热甫": ["meshrep", "mashrap", "uyghurmeshrep"],
    "中国水密隔舱福船制造技艺": ["fuchuan", "junkboat", "chinesejunk", "watertightbulkhead"],
    "黎族传统纺染织绣技艺": ["librocade", "litextile", "litextiles"],
    "羌年": ["qiangnewyear", "qiangculture"],
    "西安鼓乐": ["xiangule", "xianwindandpercussion"],
    "中国蚕桑丝织技艺": ["sericulture", "silkreeling", "silkweaving", "silkcraft", "chinesesilk"],
    "格萨(斯)尔史诗传统": ["gesar", "kinggesar", "epicofgesar", "tibetanepic"],
    "蒙古族呼麦": ["khoomei", "hoomei", "throatsinging", "mongolianthroatsinging"],
    "花儿": ["huaer", "huaerfolk", "huaersong"],
    "中国朝鲜族农乐舞": ["nongak", "farmersdance", "koreanchinesedance", "chaoxianzu"],
}

GENERIC_ENGLISH: list[str] = []

GENERIC_TAGS = {
    "fyp", "foryou", "foryoupage", "viral", "tiktok", "trending", "fy", "fypシ",
    "capcut", "duet", "stitch", "vlog", "usa", "diy", "tips", "asmr", "learnontiktok",
    "china", "chinese", "culture", "chineseculture", "intangibleheritage", "unescoheritage",
    "intangibleculturalheritage", "culturalheritage", "非遗", "非物质文化遗产", "中国", "历史",
    "spring", "festival", "celebration", "year", "social", "traditional", "heritage",
    "music", "dance", "art", "craft", "folk", "ethnic", "people", "history",
    "processing", "techniques", "associated", "practices", "knowledge", "health", "life",
    "wood", "paper", "printing", "silk", "epic", "song", "singing", "opera",
    "tea", "fire", "puppet", "puppetry", "handmade", "textile", "fabric", "bridge", "engineering",
    "xian", "drums", "drumcover", "drummer", "weaving", "fujian", "fuji", "nanjing", "ricepaper",
    "papermaking", "recycledpaper", "musical", "buddhism", "tibet", "tibetan", "mongolia", "mongolian",
    "farmer", "architecture", "woodworking", "malaysia", "printmaking", "zither", "throat", "shin",
    "kpop", "soccer", "anime", "science", "popular", "lookism", "cdrama", "linkinpark", "huawei", "pagani",
    "holistichealth", "ancientwisdom", "healing", "mentalmath", "martialarts", "kungfu", "wushu",
    "chinatravel", "tibetanmedicine", "chinesemedicine", "traditionalchinesemedicine",
    "uyghur", "xinjiang", "watertight", "junk", "qiang", "侗族", "朝鲜族", "kyrgyz",
    "coveredbridge", "celadon", "thangka", "唐卡", "dragonboat", "zongzi",
}


def parse_jsonish(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return []
    try:
        data = json.loads(value)
        if isinstance(data, list):
            return [str(x).strip().lstrip("#") for x in data if str(x).strip()]
    except Exception:
        pass
    return [x.strip().strip('"').lstrip("#") for x in value.strip("[]").split(",") if x.strip()]


def lang_of(tag: str) -> str:
    has_cjk = bool(CJK_RE.search(tag))
    has_ascii = bool(ASCII_RE.search(tag))
    if has_cjk and has_ascii:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_ascii:
        return "en"
    return "other"


def norm_tag(tag: str) -> str:
    return re.sub(r"\s+", "", tag.strip().lstrip("#")).lower()


def load_config(path: Path) -> dict[int, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(p["id"]): p for p in data.get("projects", [])}


def collect_report_failures(path: Path) -> dict[int, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for project in data.get("projects", []):
        pid = int(project.get("id"))
        for ch in project.get("channels", []):
            if ch.get("channel") == "hashtag" and ch.get("status") not in ("ok", "skipped"):
                out[pid].append(ch)
    return out


def collect_search_volume(csv_path: Path) -> dict[int, dict[str, int]]:
    out: dict[int, dict[str, int]] = defaultdict(lambda: {"search_rows": 0, "search_likely": 0, "search_non_low": 0})
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = int(row["heritage_id"])
            if row.get("source_channel") != "search":
                continue
            out[pid]["search_rows"] += 1
            label = row.get("quality_label") or ""
            if label == "likely_relevant":
                out[pid]["search_likely"] += 1
            if label in ("likely_relevant", "needs_review"):
                out[pid]["search_non_low"] += 1
    return out


def collect_sample_tags(csv_path: Path) -> dict[int, Counter[str]]:
    counters: dict[int, Counter[str]] = defaultdict(Counter)
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = int(row["heritage_id"])
            tags = parse_jsonish(row.get("hashtags", "")) + parse_jsonish(row.get("hashtags_text", ""))
            seen = set()
            for tag in tags:
                clean = tag.strip().lstrip("#")
                key = norm_tag(clean)
                if not key or key in seen:
                    continue
                seen.add(key)
                counters[pid][clean] += 1
    return counters


async def resolve_terms(terms: list[str], cookies_path: str | None, proxy: str | None, limit: int) -> dict[str, dict[str, Any]]:
    ms_token = os.getenv("ms_token") or os.getenv("MS_TOKEN")
    api = await create_api(ms_token=ms_token, proxy=proxy, cookies_path=cookies_path)
    results: dict[str, dict[str, Any]] = {}
    try:
        for term in terms:
            tag = term.strip().lstrip("#")
            if not tag:
                continue
            try:
                info = await asyncio.wait_for(api.hashtag(name=tag).info(), timeout=15)
                challenge = ((info or {}).get("challengeInfo") or {}).get("challenge") or {}
                cid = challenge.get("id")
                title = challenge.get("title") or tag
                ok = bool(cid)
                results[tag] = {"resolved": ok, "challenge_id": cid or "", "resolved_title": title, "error": "" if ok else "missing_challenge_id"}
            except Exception as exc:
                results[tag] = {"resolved": False, "challenge_id": "", "resolved_title": "", "error": f"{type(exc).__name__}: {exc}"}
            await asyncio.sleep(0.4)
            if len(results) >= limit:
                break
    finally:
        await api.close_sessions()
    return results


def build_common_candidates(project: dict[str, Any]) -> list[str]:
    terms = list(COMMON_ENGLISH.get(project["name_cn"], []))
    dedup = []
    seen = set()
    for t in terms:
        key = norm_tag(t)
        if key and key not in seen and key not in {norm_tag(x) for x in GENERIC_TAGS}:
            seen.add(key); dedup.append(t)
    return dedup


def write_outputs(args, projects, counters, failures, search_volume, resolved):
    out_csv = Path(args.out_csv)
    out_md = Path(args.out_md)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for pid, project in projects.items():
        current = {norm_tag(x) for x in project.get("hashtag_terms", [])}
        disabled = []
        for ch in failures.get(pid, []):
            for term in ch.get("terms", []):
                r = resolved.get(term, {})
                if not r.get("resolved"):
                    disabled.append(term)
        for source, candidates in [
            ("sample", [t for t, _ in counters.get(pid, Counter()).most_common(args.top_sample)]),
            ("common_english", build_common_candidates(project)),
        ]:
            for tag in candidates:
                key = norm_tag(tag)
                r = resolved.get(tag, {})
                rows.append({
                    "heritage_id": pid,
                    "heritage_name_cn": project["name_cn"],
                    "candidate_tag": tag,
                    "language": lang_of(tag),
                    "is_generic_tag": norm_tag(tag) in {norm_tag(x) for x in GENERIC_TAGS},
                    "source": source,
                    "sample_count": counters.get(pid, Counter()).get(tag, 0),
                    "current_hashtag_term": key in current,
                    "resolved": r.get("resolved", ""),
                    "challenge_id": r.get("challenge_id", ""),
                    "resolved_title": r.get("resolved_title", ""),
                    "resolve_error": r.get("error", ""),
                    "search_rows": search_volume.get(pid, {}).get("search_rows", 0),
                    "search_likely": search_volume.get(pid, {}).get("search_likely", 0),
                    "search_non_low": search_volume.get(pid, {}).get("search_non_low", 0),
                    "disabled_hashtag_terms": ",".join(sorted(set(disabled))),
                })
    fields = list(rows[0].keys()) if rows else []
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

    lines = ["# 二测 hashtag 词表修复建议", "", "## 说明", "", "- `sample`：从二测视频真实 hashtag 反推。", "- `common_english`：不取自样本的常识英文候选，用于降低自我强化偏差。", "- 泛词一律不进入 `hashtag_terms` 建议；判定标准是该 tag 单独拿出来是否指向具体非遗。", "- `is_generic_tag=true`：泛词/平台词，仅保留在 CSV 供审计，不进入 Markdown 候选摘要。", "- `disabled_hashtag_terms`：本轮 challengeID resolve 失败，备查，不建议继续作为主 hashtag term。", "- `language`：发布者标签语言维度，可用于画像。", ""]
    lines.append("## challengeID 失败与低存在感线索")
    lines.append("")
    for pid, fail in failures.items():
        project = projects.get(pid)
        if not project: continue
        vol = search_volume.get(pid, {})
        failed_terms = sorted({t for ch in fail for t in ch.get("terms", []) if not resolved.get(t, {}).get("resolved")})
        lines.append(f"- {project['name_cn']}: disabled_hashtag_terms={', '.join(failed_terms) or '无'}; search_rows={vol.get('search_rows',0)}, search_likely={vol.get('search_likely',0)}, search_non_low={vol.get('search_non_low',0)}")
    lines.append("")
    lines.append("## 各项目候选摘要")
    lines.append("")
    by_pid: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_pid[int(row["heritage_id"])].append(row)
    for pid, project in projects.items():
        candidates = by_pid.get(pid, [])
        resolved_rows = [r for r in candidates if r["resolved"] is True and not r.get("is_generic_tag")]
        sample_top = [r for r in resolved_rows if r["source"] == "sample" and r["current_hashtag_term"]][:8]
        common_top = [r for r in resolved_rows if r["source"] == "common_english"][:8]
        lines.append(f"### {pid}. {project['name_cn']}")
        lines.append(f"- 当前 hashtag_terms: {', '.join(project.get('hashtag_terms', []))}")
        lines.append(f"- 当前词表中可保留候选: {', '.join(r['candidate_tag'] + '(' + r['language'] + ')' for r in sample_top) or '无'}")
        lines.append(f"- 常识英文可解析候选: {', '.join(r['candidate_tag'] for r in common_top) or '无'}")
        lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/unesco_tiktok_20260602_144321_labeled.csv")
    ap.add_argument("--report", default="data/collection_report_20260602_144321.json")
    ap.add_argument("--config", default="config/unesco_ich_keywords.v1.json")
    ap.add_argument("--out-csv", default="data/hashtag_term_suggestions_20260602_144321.csv")
    ap.add_argument("--out-md", default="docs/review/二测_hashtag词表修复建议.md")
    ap.add_argument("--top-sample", type=int, default=20)
    ap.add_argument("--resolve", action="store_true")
    ap.add_argument("--resolve-limit", type=int, default=500)
    ap.add_argument("--cookies", default=os.getenv("TIKTOK_COOKIES_JSON"))
    ap.add_argument("--proxy", default=os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"))
    args = ap.parse_args()

    projects = load_config(Path(args.config))
    counters = collect_sample_tags(Path(args.csv))
    failures = collect_report_failures(Path(args.report))
    search_volume = collect_search_volume(Path(args.csv))
    terms = []
    for pid, project in projects.items():
        terms.extend([t for t, _ in counters.get(pid, Counter()).most_common(args.top_sample)])
        terms.extend(build_common_candidates(project))
        for ch in failures.get(pid, []):
            terms.extend(ch.get("terms", []))
    dedup = []
    seen = set()
    for t in terms:
        key = norm_tag(t)
        if key and key not in seen and key not in {norm_tag(x) for x in GENERIC_TAGS}:
            seen.add(key); dedup.append(t)
    resolved = {}
    if args.resolve:
        resolved = asyncio.run(resolve_terms(dedup, args.cookies, args.proxy, args.resolve_limit))
    write_outputs(args, projects, counters, failures, search_volume, resolved)
    print(json.dumps({"projects": len(projects), "candidate_terms": len(dedup), "resolved_checked": len(resolved), "out_csv": args.out_csv, "out_md": args.out_md}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
