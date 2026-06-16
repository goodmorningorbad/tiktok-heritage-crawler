#!/usr/bin/env python3
"""Collect TikTok hashtag statsV2 scale for UNESCO heritage hashtag terms.

This is a derived scale-collection step. It reads configured `hashtag_terms`,
queries TikTok challenge metadata (`tag.info()`), and writes term-level +
project-level scale artifacts. Raw collection/search baseline files are not
modified.

Outputs:
- data/derived/hashtag_scale_terms.ndjson
- data/derived/project_hashtag_scale_summary.csv
- data/derived/project_hashtag_scale_summary.json
- docs/标签规模分层_tagscale.md
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crawler import collect_hashtag_stats_safe, create_api

GENERIC_OR_NOISY_TERMS = {
    # too broad / cross-topic
    "silk", "tea", "printing", "papermaking", "dragonboat", "dragonboatfestival",
    "zongzi", "mongolian", "epic", "puppet", "puppetry", "chineseopera",
    "opera", "music", "dance", "festival", "art", "culture", "traditional",
    "junk", "watertight", "coveredbridge", "abacus", "celadon", "ricepaper",
    "tcm", "acupuncture", "chinesemedicine", "throatsinging", "mongolianthroatsinging",
    "uyghur", "kyrgyz", "tibetanmedicine", "tibetanhealing", "chinesezither",
    # Chinese generic terms
    "新年", "过年", "茶艺", "功夫茶", "制茶", "揉捻", "算盘", "黎族", "羌族",
    "侗族", "鼓乐", "丝绸", "青瓷", "皮影", "木偶", "福船", "王船", "南音",
    "龙舟", "粽子", "木结构", "古建", "雕版", "印章", "剪纸", "书法", "长调",
}

# These are known to be usable but still carry scale-with-noise risk; final state
# remains reviewable in the report.
KNOWN_CLEANISH_TERMS = {
    "chinesenewyear", "lunarnewyear", "cny", "春节", "taichi", "taijiquan", "太极", "太极拳",
    "budaixi", "布袋戏", "掌中戏", "shadowpuppetry", "皮影戏", "pekingopera", "beijingopera",
    "cantoneseopera", "粤剧", "kunqu", "昆曲", "guqin", "古琴", "nanyin", "泉州南音",
    "calligraphy", "shufa", "sealcarving", "chineseseal", "chinesepapercut", "xuanpaper",
    "longquanceladon", "gongfutea", "sowarigpa", "solarterms", "24solarterms", "mazu",
    "seagoddess", "khoomei", "呼麦", "muqam", "uyghurmuqam", "urtiinduu", "dongchorus",
    "kamgrandchoir", "meshrep", "mashrap", "gesar", "kinggesar", "epicofgesar",
    "thangka", "tibetanopera", "lhamo", "achelhamo", "yunjin", "nanjingbrocade",
    "sericulture", "silkreeling", "silkweaving", "librocade", "黎锦", "黎族织锦",
}


def norm_tag(tag: str) -> str:
    return str(tag or "").strip().lstrip("#").lower().replace(" ", "")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_pool(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], []
    data = load_json(path)
    return data.get("accounts") or [], data.get("proxies") or []


def term_status(hashtag: str, row: dict[str, Any] | None, error: str | None) -> str:
    if error and not row:
        return "failed"
    if not row or not row.get("challenge_id"):
        return "unavailable"
    t = norm_tag(hashtag)
    if t in GENERIC_OR_NOISY_TERMS:
        return "noisy"
    if t in KNOWN_CLEANISH_TERMS:
        return "clean"
    # Heuristic: very short Latin tags and enormous generic-looking tags need review.
    vc = row.get("video_count")
    try:
        vc_i = int(vc) if vc is not None else 0
    except Exception:
        vc_i = 0
    if len(t) <= 3 and not any("\u4e00" <= ch <= "\u9fff" for ch in hashtag):
        return "noisy"
    if vc_i >= 5_000_000:
        return "noisy"
    return "clean"


def build_terms(config_path: Path, only: list[str] | None = None) -> list[dict[str, Any]]:
    cfg = load_json(config_path)
    only_set = {norm_tag(x) for x in only} if only else None
    terms: list[dict[str, Any]] = []
    seen = set()
    for p in cfg.get("projects", []):
        for tag in p.get("hashtag_terms") or []:
            tag = str(tag).strip().lstrip("#")
            if not tag:
                continue
            if only_set and norm_tag(tag) not in only_set:
                continue
            key = (int(p["id"]), norm_tag(tag))
            if key in seen:
                continue
            seen.add(key)
            terms.append({
                "project_id": int(p["id"]),
                "project_name": p.get("name_cn", ""),
                "project_name_en": p.get("name_en", ""),
                "list_type": p.get("list_type", ""),
                "category": p.get("category", ""),
                "hashtag": tag,
            })
    return terms


async def collect_for_slot(slot_terms: list[dict[str, Any]], account: dict[str, Any] | None, proxy: dict[str, Any] | None, delay: float) -> list[dict[str, Any]]:
    # Set env for collector_meta() used inside crawler.normalize_challenge_info.
    old_env = dict(os.environ)
    try:
        if account:
            os.environ["TIKTOK_ACCOUNT_ID"] = account.get("id", "")
            os.environ["TIKTOK_ACCOUNT_ROLE"] = account.get("role", "neutral")
            os.environ["TIKTOK_COOKIES_JSON"] = account.get("cookies", "")
        if proxy:
            os.environ["TIKTOK_PROXY_ID"] = proxy.get("proxy_id", "")
            os.environ["TIKTOK_PROXY_EXIT_IP"] = proxy.get("exit_ip", "")
            os.environ["TIKTOK_PROXY_ISP"] = proxy.get("isp", "")
            os.environ["TIKTOK_PROXY_REGION"] = proxy.get("region", "unknown")
            os.environ["TIKTOK_PROXY_SUBREGION"] = proxy.get("subregion", "")
            os.environ["TIKTOK_PROXY_POOL"] = proxy.get("pool", "")
        ms_token = os.getenv("ms_token") or os.getenv("MS_TOKEN")
        cookies = account.get("cookies") if account else os.getenv("TIKTOK_COOKIES_JSON")
        proxy_url = proxy.get("socks") if proxy else (os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY"))
        api = await create_api(ms_token=ms_token, proxy=proxy_url, cookies_path=cookies)
        out: list[dict[str, Any]] = []
        try:
            for item in slot_terms:
                hashtag = item["hashtag"]
                row, error = await collect_hashtag_stats_safe(api, hashtag)
                status = term_status(hashtag, row, error)
                if row is None:
                    row = {
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                        "source_type": "hashtag_stats",
                        "query_term": hashtag,
                        "challenge_id": None,
                        "challenge_title": None,
                        "video_count": None,
                        "view_count": None,
                    }
                merged = {
                    **item,
                    **row,
                    "hashtag": hashtag,
                    "resolve_status": "ok" if status in {"clean", "noisy"} else status,
                    "scale_term_status": status,
                    "error": error or "",
                }
                out.append(merged)
                print(json.dumps({
                    "project": item["project_name"], "tag": hashtag, "status": status,
                    "challenge_id": merged.get("challenge_id"), "video_count": merged.get("video_count"),
                    "account": account.get("id") if account else "env",
                }, ensure_ascii=False), flush=True)
                if delay:
                    await asyncio.sleep(delay)
        finally:
            await api.close_sessions()
        return out
    finally:
        os.environ.clear()
        os.environ.update(old_env)


async def collect_all(terms: list[dict[str, Any]], pool_path: Path, delay: float) -> list[dict[str, Any]]:
    accounts, proxies = load_pool(pool_path)
    if not accounts:
        accounts = [None]
    if not proxies:
        proxies = [None]
    slots: list[list[dict[str, Any]]] = [[] for _ in accounts]
    for i, term in enumerate(terms):
        slots[i % len(slots)].append(term)
    all_rows: list[dict[str, Any]] = []
    # Sequential by account: stats endpoint is light, and sequential avoids hitting every account at once.
    for i, slot_terms in enumerate(slots):
        if not slot_terms:
            continue
        account = accounts[i]
        proxy = proxies[i % len(proxies)] if proxies else None
        print(f"=== slot {i+1}/{len(slots)} account={account.get('id') if account else 'env'} proxy={proxy.get('proxy_id') if proxy else 'env'} terms={len(slot_terms)} ===", flush=True)
        rows = await collect_for_slot(slot_terms, account, proxy, delay)
        all_rows.extend(rows)
        await asyncio.sleep(max(delay, 1.0))
    return all_rows


def video_count_tier(value: int | None) -> str:
    if value is None:
        return "unavailable"
    if value >= 100_000:
        return "head"
    if value >= 10_000:
        return "mid"
    if value >= 1_000:
        return "long_tail"
    return "near_invisible"


def project_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_project: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_project[int(r["project_id"])].append(r)
    summaries = []
    for pid in sorted(by_project):
        xs = by_project[pid]
        clean = [r for r in xs if r.get("scale_term_status") == "clean" and r.get("video_count") is not None]
        noisy = [r for r in xs if r.get("scale_term_status") == "noisy" and r.get("video_count") is not None]
        resolved = clean + noisy
        unavailable = [r for r in xs if r.get("scale_term_status") in {"unavailable", "failed"}]
        chosen_pool = clean if clean else noisy
        best = max(chosen_pool, key=lambda r: int(r.get("video_count") or 0), default=None)
        if clean:
            state = "clean"
        elif noisy:
            state = "noisy"
        else:
            state = "unavailable"
        counts = [int(r.get("video_count") or 0) for r in chosen_pool]
        best_video_count = int(best.get("video_count") or 0) if best else None
        summaries.append({
            "project_id": pid,
            "project_name": xs[0]["project_name"],
            "project_name_en": xs[0].get("project_name_en", ""),
            "list_type": xs[0].get("list_type", ""),
            "category": xs[0].get("category", ""),
            "hashtag_terms_total": len(xs),
            "terms_clean": len(clean),
            "terms_noisy": len(noisy),
            "terms_unavailable_or_failed": len(unavailable),
            "scale_data_state": state,
            "scale_video_count_best": best_video_count,
            "scale_video_count_tier": video_count_tier(best_video_count),
            "scale_best_hashtag": best.get("hashtag") if best else "",
            "scale_best_challenge_id": best.get("challenge_id") if best else "",
            "scale_best_challenge_title": best.get("challenge_title") if best else "",
            "scale_video_count_median_usable": int(median(counts)) if counts else None,
            "scale_video_count_max_clean": max((int(r.get("video_count") or 0) for r in clean), default=None),
            "scale_video_count_max_noisy": max((int(r.get("video_count") or 0) for r in noisy), default=None),
            "usable_terms": json.dumps([
                {"tag": r.get("hashtag"), "status": r.get("scale_term_status"), "video_count": r.get("video_count"), "challenge_id": r.get("challenge_id")}
                for r in resolved
            ], ensure_ascii=False),
            "unavailable_terms": json.dumps([r.get("hashtag") for r in unavailable], ensure_ascii=False),
            "scale_note": "hashtag statsV2 videoCount is stock/scale with noise, not reach or final spread verdict",
        })
    return summaries


def write_ndjson(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


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
        "note": "Project hashtag statsV2 scale summary. videoCount is stock/scale-with-noise, not reach.",
        "rows": rows,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_report(summaries: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    states = Counter(r["scale_data_state"] for r in summaries)
    tiers = Counter(r["scale_video_count_tier"] for r in summaries)
    top_clean = sorted([r for r in summaries if r["scale_video_count_best"] is not None], key=lambda r: int(r["scale_video_count_best"] or 0), reverse=True)[:15]
    unavailable = [r for r in summaries if r["scale_data_state"] == "unavailable"]
    noisy = [r for r in summaries if r["scale_data_state"] == "noisy"]
    lines = []
    lines.append("# 标签规模分层：hashtag statsV2 videoCount")
    lines.append("")
    lines.append(f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append("> 性质：派生存量规模轴；`videoCount` 是 hashtag challenge 聚合规模，含噪声，不等于触达。")
    lines.append("")
    lines.append("## 1. 总览")
    lines.append("")
    lines.append(f"- 项目数：{len(summaries)}")
    for k in ["clean", "noisy", "unavailable"]:
        lines.append(f"- `{k}`: {states.get(k, 0)}")
    lines.append("- 分层阈值：head ≥100K；mid 10K–100K；long_tail 1K–10K；near_invisible <1K")
    for k in ["head", "mid", "long_tail", "near_invisible", "unavailable"]:
        lines.append(f"- `scale_video_count_tier={k}`: {tiers.get(k, 0)}")
    lines.append("")
    lines.append("## 2. 规模最高项目（按 best usable hashtag videoCount）")
    lines.append("")
    for r in top_clean:
        lines.append(f"- **{r['project_name']}** ({r['list_type']}): state=`{r['scale_data_state']}`, best=#{r['scale_best_hashtag']}, videoCount={int(r['scale_video_count_best'] or 0):,}, clean_terms={r['terms_clean']}, noisy_terms={r['terms_noisy']}")
    lines.append("")
    lines.append("## 3. 只有 noisy hashtag 可用的项目")
    lines.append("")
    if noisy:
        for r in noisy:
            lines.append(f"- **{r['project_name']}** ({r['list_type']}): best=#{r['scale_best_hashtag']}, videoCount={int(r['scale_video_count_best'] or 0):,}, note=规模可能高估")
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 4. hashtag 规模不可得项目")
    lines.append("")
    if unavailable:
        for r in unavailable:
            lines.append(f"- **{r['project_name']}** ({r['list_type']}): terms={r['hashtag_terms_total']}, unavailable={r['unavailable_terms']}")
    else:
        lines.append("- 暂无。")
    lines.append("")
    lines.append("## 5. 使用注意")
    lines.append("")
    lines.append("- `scale_data_state=clean` 也不代表完全无噪声，只代表当前 hashtag 相对专指。")
    lines.append("- `scale_data_state=noisy` 表示只有泛词/撞词规模可用，后续分层要降权或人工说明。")
    lines.append("- `unavailable` 不能强行填 0；它表示没有可用 hashtag 规模源，本身可作为低存在感线索。")
    lines.append("- 下一步：与 relevance-aware reach 合成 `存量 × 触达` 草表。")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("config/unesco_ich_keywords.v1.json"))
    ap.add_argument("--pool", type=Path, default=Path("config/us_pool.json"))
    ap.add_argument("--only", default="", help="comma-separated hashtags for smoke tests")
    ap.add_argument("--delay", type=float, default=1.2)
    ap.add_argument("--out-terms", type=Path, default=Path("data/derived/hashtag_scale_terms.ndjson"))
    ap.add_argument("--out-summary-csv", type=Path, default=Path("data/derived/project_hashtag_scale_summary.csv"))
    ap.add_argument("--out-summary-json", type=Path, default=Path("data/derived/project_hashtag_scale_summary.json"))
    ap.add_argument("--out-report", type=Path, default=Path("docs/标签规模分层_tagscale.md"))
    args = ap.parse_args()
    only = [x.strip() for x in args.only.split(",") if x.strip()] if args.only else None
    terms = build_terms(args.config, only=only)
    print(f"terms={len(terms)}")
    rows = asyncio.run(collect_all(terms, args.pool, args.delay))
    summaries = project_summary(rows)
    write_ndjson(rows, args.out_terms)
    write_csv(summaries, args.out_summary_csv)
    write_json(summaries, args.out_summary_json)
    write_report(summaries, args.out_report)
    print(f"wrote term_rows={len(rows)} project_summaries={len(summaries)}")
    print("states", dict(Counter(r["scale_data_state"] for r in summaries)))


if __name__ == "__main__":
    main()
