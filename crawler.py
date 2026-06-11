from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from TikTokApi import TikTokApi


def split_csv(value: str) -> list[str]:
    return [x.strip().lstrip("#") for x in value.split(",") if x.strip()]


def collector_meta() -> dict[str, str]:
    return {
        "collector_account": os.getenv("TIKTOK_ACCOUNT_ID", ""),
        "collector_account_role": os.getenv("TIKTOK_ACCOUNT_ROLE", "neutral"),
        "proxy_region": os.getenv("TIKTOK_PROXY_REGION", "unknown"),
        "proxy_subregion": os.getenv("TIKTOK_PROXY_SUBREGION", ""),
        "proxy_pool": os.getenv("TIKTOK_PROXY_POOL", ""),
        "proxy_id": os.getenv("TIKTOK_PROXY_ID", ""),
        "proxy_exit_ip": os.getenv("TIKTOK_PROXY_EXIT_IP", ""),
        "proxy_isp": os.getenv("TIKTOK_PROXY_ISP", ""),
    }


def load_cookies(path: str | None) -> list[dict[str, Any]] | None:
    """Load Playwright-compatible cookies exported from browser/devtools extensions."""
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "cookies" in data:
        data = data["cookies"]
    if not isinstance(data, list):
        raise ValueError("cookies file must be a JSON list or an object with a cookies list")

    cookies: list[dict[str, Any]] = []
    for c in data:
        if not isinstance(c, dict) or not c.get("name") or c.get("value") is None:
            continue
        cookie = {
            "name": c["name"],
            "value": c["value"],
            "domain": c.get("domain") or ".tiktok.com",
            "path": c.get("path") or "/",
            "secure": bool(c.get("secure", True)),
            "httpOnly": bool(c.get("httpOnly", False)),
        }
        if c.get("expirationDate"):
            cookie["expires"] = int(c["expirationDate"])
        elif c.get("expires") and isinstance(c.get("expires"), (int, float)):
            cookie["expires"] = int(c["expires"])
        same_site = c.get("sameSite") or c.get("same_site")
        if same_site:
            same_site = str(same_site).lower().replace("no_restriction", "none")
            cookie["sameSite"] = {"none": "None", "lax": "Lax", "strict": "Strict"}.get(same_site, "None")
        cookies.append(cookie)
    return cookies or None


def as_dict(video: Any) -> dict[str, Any]:
    if isinstance(video, dict):
        return video
    data = getattr(video, "as_dict", None)
    if isinstance(data, dict):
        return data
    return {}


def normalize_video(raw_video: dict[str, Any], source_type: str, source: str) -> dict[str, Any]:
    author = raw_video.get("author") or {}
    stats = raw_video.get("stats") or raw_video.get("statsV2") or {}
    music = raw_video.get("music") or {}
    challenges = raw_video.get("challenges") or []
    video_id = raw_video.get("id") or raw_video.get("aweme_id")

    create_time = raw_video.get("createTime") or raw_video.get("create_time")
    create_iso = None
    if create_time:
        try:
            create_iso = datetime.fromtimestamp(int(create_time), tz=timezone.utc).isoformat()
        except Exception:
            create_iso = None

    unique_id = author.get("uniqueId") or author.get("unique_id")
    web_url = raw_video.get("webVideoUrl") or raw_video.get("shareUrl")
    if not web_url and unique_id and video_id:
        web_url = f"https://www.tiktok.com/@{unique_id}/video/{video_id}"

    hashtags = [c.get("title") for c in challenges if isinstance(c, dict) and c.get("title")]
    hashtag_ids = [c.get("id") for c in challenges if isinstance(c, dict) and c.get("id")]
    desc = raw_video.get("desc") or ""
    hashtags_text = []
    for part in desc.replace("\n", " ").split():
        if part.startswith("#") and len(part) > 1:
            tag = part.lstrip("#").strip(".,;:!?，。；：！？()[]{}\"'")
            if tag and tag not in hashtags_text:
                hashtags_text.append(tag)

    row = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_type": source_type,
        "source": source,
        "id": video_id,
        "desc": raw_video.get("desc"),
        "create_time": create_time,
        "create_time_iso": create_iso,
        "web_url": web_url,
        "author_id": author.get("id"),
        "author_unique_id": unique_id,
        "author_nickname": author.get("nickname"),
        "author_verified": author.get("verified"),
        "stats_play_count": int(stats.get("playCount") or stats.get("play_count") or 0),
        "stats_digg_count": int(stats.get("diggCount") or stats.get("digg_count") or 0),
        "stats_comment_count": int(stats.get("commentCount") or stats.get("comment_count") or 0),
        "stats_share_count": int(stats.get("shareCount") or stats.get("share_count") or 0),
        "stats_collect_count": int(stats.get("collectCount") or stats.get("collect_count") or 0),
        "music_id": music.get("id"),
        "music_title": music.get("title"),
        "music_author": music.get("authorName") or music.get("author_name"),
        "hashtags": hashtags,
        "hashtag_ids": hashtag_ids,
        "hashtags_text": hashtags_text,
        "raw": raw_video,
    }
    row.update(collector_meta())
    return row


async def create_api(ms_token: str | None, proxy: str | None = None, cookies_path: str | None = None) -> TikTokApi:
    api = TikTokApi()
    cookies = load_cookies(cookies_path)
    
    # Convert Playwright cookie list to dict format expected by TikTok-Api
    cookies_dict = None
    if cookies:
        cookies_dict = {c["name"]: c["value"] for c in cookies if c.get("name") and c.get("value")}
        if not ms_token and "msToken" in cookies_dict:
            ms_token = cookies_dict["msToken"]
    
    kwargs = {
        "ms_tokens": [ms_token] if ms_token else [None],
        "num_sessions": 1,
        "sleep_after": 3,
        "browser": os.getenv("TIKTOK_BROWSER", "chromium"),
        "headless": os.getenv("TIKTOK_HEADLESS", "true").lower() not in ("0", "false", "no"),
        "timeout": int(os.getenv("TIKTOK_TIMEOUT_MS", "90000")),
        "suppress_resource_load_types": ["image", "media", "font", "stylesheet"],
        "allow_partial_sessions": True,
        "min_sessions": 1,
    }
    if proxy:
        kwargs["proxies"] = [{"server": proxy}]
    if cookies_dict:
        kwargs["cookies"] = [cookies_dict]
    await api.create_sessions(**kwargs)
    return api


async def collect_search_pagewise(api: TikTokApi, keyword: str, count: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    search_url = "https://www.tiktok.com/api/search/item/full/"
    # TikTok search 翻页必须带 search_id（取自第一页 log_pb.impr_id）+ from_page + web_search_code，
    # 否则第二页直接返回空 + search_nil_info。裸 cursor 翻页只能拿到第一页 30 条。
    web_search_code = (
        '{"tiktok":{"client_params_x":{"search_engine":'
        '{"ies_mt_user_live_video_card_use_libra":1,'
        '"mt_search_general_user_live_card":1}},"search_server":{}}}'
    )
    cursor = 0
    found = 0
    rows: list[dict[str, Any]] = []
    last_has_more = False
    stop_reason = "count_reached"
    last_cursor: Any = cursor
    search_id = ""
    while found < count:
        params = {
            "keyword": keyword,
            "count": min(30, count - found),
            "cursor": cursor,
            "from_page": "search",
            "web_search_code": web_search_code,
        }
        if search_id:
            params["search_id"] = search_id
        response = await api.make_request(url=search_url, params=params)
        if not response:
            stop_reason = "empty_response"
            last_has_more = False
            break
        items = response.get("item_list") or response.get("itemList") or []
        last_has_more = bool(response.get("has_more") or response.get("hasMore"))
        last_cursor = response.get("cursor", cursor)
        # 第一页拿到 search_id，后续每页都带同一个续页
        if not search_id:
            search_id = (response.get("log_pb") or {}).get("impr_id") or ""
        if not items:
            stop_reason = "empty_items"
            break
        for item in items:
            raw = item.get("item") if isinstance(item, dict) and "item" in item else item
            if not isinstance(raw, dict):
                continue
            rows.append(normalize_video(raw, "search", keyword))
            found += 1
            if found >= count:
                stop_reason = "count_reached"
                break
        if found >= count:
            break
        if not last_has_more:
            stop_reason = "exhausted"
            break
        cursor = response.get("cursor", cursor + len(items))
        await asyncio.sleep(1.2)
    # 语言标记：判断该 term 是中文还是拉丁文（支撑"美区中文词触达浅"这一数据发现）
    has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in keyword)
    term_script = "cjk" if has_cjk else "latin"

    # depth_verdict：翻页深度语义。注意 empty_response 是限流信号，不算真实触底！
    if found >= count and last_has_more:
        depth_verdict = "truncated_by_cap"      # 被 N 截断，平台仍有更多（真实值>=N，超级头部）
    elif stop_reason in ("exhausted", "empty_items"):
        depth_verdict = "exhausted"             # has_more=0 自然触底，拿到该 region 全部可达视频
    elif stop_reason == "empty_response":
        depth_verdict = "rate_limited"          # 空响应=bot检测/限流，不是真实触底
    else:
        depth_verdict = "count_reached_exact"

    # result_class：底线字段——failed/zero_real/has_data 严格分离，绝不混。
    #   下游"近乎隐形"判定只能用 zero_real，永不用 failed。
    if depth_verdict == "rate_limited":
        result_class = "failed"                 # 技术噪声：限流，必须可重采，不计入低传播
    elif found == 0:
        result_class = "zero_real"              # 研究结论：该 region 该词真实零结果
    else:
        result_class = "has_data"

    meta = {
        "keyword": keyword,
        "term_script": term_script,
        "requested_count": count,
        "collected_count": found,
        "hit_cap": found >= count,
        "has_more_at_stop": bool(last_has_more) if found >= count else False,
        "stop_reason": stop_reason,
        "cursor_at_stop": last_cursor,
        "depth_verdict": depth_verdict,
        "result_class": result_class,
    }
    return rows, meta


async def collect_search(api: TikTokApi, keyword: str, count: int) -> AsyncIterator[dict[str, Any]]:
    rows, _meta = await collect_search_pagewise(api, keyword, count)
    for row in rows:
        yield row


async def collect_hashtag(api: TikTokApi, hashtag: str, count: int) -> AsyncIterator[dict[str, Any]]:
    found = 0
    tag = api.hashtag(name=hashtag)
    async for video in tag.videos(count=count):
        yield normalize_video(as_dict(video), "hashtag", hashtag)
        found += 1
        if found >= count:
            break
        if found % 30 == 0:
            await asyncio.sleep(1.2)


async def collect_hashtag_safe(api: TikTokApi, hashtag: str, count: int) -> tuple[list[dict[str, Any]], str | None]:
    rows: list[dict[str, Any]] = []
    try:
        async for row in collect_hashtag(api, hashtag, count):
            rows.append(row)
    except Exception as exc:
        # Some tags do not resolve to a TikTok challengeID. Record this as a
        # per-term failure instead of aborting the whole hashtag channel.
        return rows, f"{type(exc).__name__}: {exc}"
    return rows, None


# 标签规模噪声声明：videoCount/viewCount 是 challenge 聚合规模，含大量撞词噪声，
# 不等于该非遗的真实传播量；仅作"标签规模"参考。
HASHTAG_STATS_NOISE_NOTE = (
    "tag_scale_with_noise: videoCount/viewCount reflect the challenge's aggregate "
    "scale and include cross-topic/ambiguous content; NOT the heritage item's reach"
)


def normalize_challenge_info(info: dict, hashtag: str) -> dict[str, Any]:
    """从 tag.info() 提取 challenge 规模字段。优先 statsV2（真实精确值），
    stats 为四舍五入粗值/已失效（videoCount 常为 0），两者都留以便核对。"""
    ci = (info or {}).get("challengeInfo", {}) or {}
    challenge = ci.get("challenge", {}) or {}
    stats = ci.get("stats", {}) or {}
    stats_v2 = ci.get("statsV2", {}) or {}

    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    # statsV2 是字符串型精确值，优先；缺失时回落 stats
    video_count = _int(stats_v2.get("videoCount"))
    view_count = _int(stats_v2.get("viewCount"))
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "source_type": "hashtag_stats",
        "query_term": hashtag,
        "challenge_id": challenge.get("id"),
        "challenge_title": challenge.get("title"),
        "challenge_desc": challenge.get("desc") or "",
        "is_commerce": challenge.get("isCommerce"),
        # 真实精确规模（statsV2）
        "video_count": video_count,
        "view_count": view_count,
        # 原始粗值/失效字段，保留供核对（不删原始数据）
        "stats_raw_video_count": stats.get("videoCount"),
        "stats_raw_view_count": stats.get("viewCount"),
        "stats_v2_video_count": stats_v2.get("videoCount"),
        "stats_v2_view_count": stats_v2.get("viewCount"),
        "status_code": info.get("statusCode", info.get("status_code")),
        "noise_disclaimer": HASHTAG_STATS_NOISE_NOTE,
        **collector_meta(),
    }


async def collect_hashtag_stats_safe(api: TikTokApi, hashtag: str) -> tuple[dict[str, Any] | None, str | None]:
    """只拉 challenge 规模元数据，不取视频。失败记错不中断。"""
    try:
        tag = api.hashtag(name=hashtag)
        info = await tag.info()
        row = normalize_challenge_info(info, hashtag)
        # challenge_id 为空通常意味着该 tag 不解析为有效 challenge
        if not row.get("challenge_id"):
            return row, "no_challenge_id"
        return row, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


async def run(args: argparse.Namespace) -> None:
    ms_token = os.getenv("ms_token") or os.getenv("MS_TOKEN")
    proxy = args.proxy or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    api = await create_api(ms_token=ms_token, proxy=proxy, cookies_path=args.cookies)
    written = 0
    seen: set[str] = set()
    try:
        with out_path.open("a", encoding="utf-8") as f:
            if args.command == "search":
                sources = split_csv(args.keywords)
                term_errors = []
                for keyword in sources:
                    # 单 term 失败（限流/EmptyResponse/超时）不能害死同批后续 term。
                    # 失败也写一条 meta（零结果/失败也是结论，符合不删数据口径）。
                    try:
                        rows, meta = await collect_search_pagewise(api, keyword, args.count)
                    except Exception as exc:
                        term_errors.append(f"{keyword}: {type(exc).__name__}: {exc}")
                        print(f"SEARCH_FAILED {keyword}: {type(exc).__name__}: {exc}", file=sys.stderr)
                        meta = {
                            "keyword": keyword,
                            "term_script": "cjk" if any("\u4e00" <= ch <= "\u9fff" for ch in keyword) else "latin",
                            "requested_count": args.count,
                            "collected_count": 0, "hit_cap": False,
                            "has_more_at_stop": False, "stop_reason": "exception",
                            "cursor_at_stop": None, "depth_verdict": "rate_limited",
                            "result_class": "failed",
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                        print("SEARCH_META " + json.dumps(meta, ensure_ascii=False), file=sys.stderr)
                        # 限流后退避，给下一个 term 喘息，降低连锁触发
                        await asyncio.sleep(8)
                        continue
                    print("SEARCH_META " + json.dumps(meta, ensure_ascii=False), file=sys.stderr)
                    for row in rows:
                        key = row.get("id") or json.dumps(row, ensure_ascii=False, sort_keys=True)[:200]
                        if key in seen:
                            continue
                        seen.add(key)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        written += 1
                    # term 间节流：给出口冷却，避免连续请求触发 bot 检测/限流（方案A）
                    if keyword != sources[-1]:
                        await asyncio.sleep(float(os.getenv("TIKTOK_TERM_DELAY", "30")))
                if term_errors:
                    print(f"search_term_failures={len(term_errors)}", file=sys.stderr)
            elif args.command == "hashtag":
                sources = split_csv(args.hashtags)
                term_errors: list[str] = []
                for hashtag in sources:
                    rows, error = await collect_hashtag_safe(api, hashtag, args.count)
                    if error:
                        term_errors.append(f"{hashtag}: {error}")
                        print(f"HASHTAG_FAILED {hashtag}: {error}", file=sys.stderr)
                    for row in rows:
                        key = row.get("id") or json.dumps(row, ensure_ascii=False, sort_keys=True)[:200]
                        if key in seen:
                            continue
                        seen.add(key)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        written += 1
                if term_errors:
                    print(f"hashtag_term_failures={len(term_errors)}", file=sys.stderr)
            elif args.command == "hashtag-stats":
                sources = split_csv(args.hashtags)
                term_errors = []
                for hashtag in sources:
                    row, error = await collect_hashtag_stats_safe(api, hashtag)
                    if error and not row:
                        term_errors.append(f"{hashtag}: {error}")
                        print(f"HASHTAG_STATS_FAILED {hashtag}: {error}", file=sys.stderr)
                        continue
                    if row is None:
                        continue
                    if error:  # 有 row 但有提示(如 no_challenge_id)
                        print(f"HASHTAG_STATS_WARN {hashtag}: {error}", file=sys.stderr)
                    # stats 按 challenge_id 去重(同一 challenge 多别名只记一次)
                    key = row.get("challenge_id") or f"noid:{hashtag}"
                    if key in seen:
                        continue
                    seen.add(key)
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                    written += 1
                    print("HASHTAG_STATS_META " + json.dumps(
                        {"term": hashtag, "challenge_id": row.get("challenge_id"),
                         "video_count": row.get("video_count"),
                         "view_count": row.get("view_count")}, ensure_ascii=False),
                        file=sys.stderr)
                if term_errors:
                    print(f"hashtag_stats_failures={len(term_errors)}", file=sys.stderr)
    finally:
        await api.close_sessions()

    print(f"wrote {written} rows to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TikTok 非遗出海视频元数据采集器")
    parser.add_argument("--proxy", default=None, help="可选代理，例如 http://user:pass@host:port")
    parser.add_argument("--cookies", default=os.getenv("TIKTOK_COOKIES_JSON"), help="可选：浏览器导出的 TikTok cookies JSON 文件路径，优先于单个 ms_token 更稳定")
    sub = parser.add_subparsers(dest="command", required=True)

    p_search = sub.add_parser("search", help="按关键词搜索视频")
    p_search.add_argument("--keywords", required=True, help="逗号分隔关键词")
    p_search.add_argument("--count", type=int, default=50, help="每个关键词采集数量")
    p_search.add_argument("--out", default="data/search.ndjson")

    p_tag = sub.add_parser("hashtag", help="按 hashtag 采集视频")
    p_tag.add_argument("--hashtags", required=True, help="逗号分隔 hashtag，不需要 #")
    p_tag.add_argument("--count", type=int, default=50, help="每个 hashtag 采集数量")
    p_tag.add_argument("--out", default="data/hashtags.ndjson")

    p_stats = sub.add_parser("hashtag-stats", help="只采 challenge 规模元数据(videoCount/viewCount，标含噪声)")
    p_stats.add_argument("--hashtags", required=True, help="逗号分隔 hashtag，不需要 #")
    p_stats.add_argument("--count", type=int, default=0, help="忽略(stats 不取视频)")
    p_stats.add_argument("--out", default="data/hashtag_stats.ndjson")

    args = parser.parse_args()
    started = time.time()
    asyncio.run(run(args))
    print(f"done in {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
