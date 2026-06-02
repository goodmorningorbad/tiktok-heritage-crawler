from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

from TikTokApi import TikTokApi


def split_csv(value: str) -> list[str]:
    return [x.strip().lstrip("#") for x in value.split(",") if x.strip()]


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

    return {
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


async def collect_search(api: TikTokApi, keyword: str, count: int) -> AsyncIterator[dict[str, Any]]:
    search_url = "https://www.tiktok.com/api/search/item/full/"
    cursor = 0
    found = 0
    while found < count:
        params = {
            "keyword": keyword,
            "count": min(30, count - found),
            "cursor": cursor,
            "source": "search_video",
        }
        response = await api.make_request(url=search_url, params=params)
        if not response:
            break
        items = response.get("item_list") or response.get("itemList") or []
        if not items:
            break
        for item in items:
            raw = item.get("item") if isinstance(item, dict) and "item" in item else item
            yield normalize_video(raw, "search", keyword)
            found += 1
            if found >= count:
                break
        if not (response.get("has_more") or response.get("hasMore")):
            break
        cursor = response.get("cursor", cursor + len(items))
        await asyncio.sleep(1.2)


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
                for keyword in sources:
                    async for row in collect_search(api, keyword, args.count):
                        key = row.get("id") or json.dumps(row, ensure_ascii=False, sort_keys=True)[:200]
                        if key in seen:
                            continue
                        seen.add(key)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        written += 1
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

    args = parser.parse_args()
    started = time.time()
    asyncio.run(run(args))
    print(f"done in {time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
