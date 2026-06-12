#!/usr/bin/env python3
"""判决性探针：搜索接口是否在 offset~210 处有翻页硬顶？

直接复用 crawler 的 create_api + 同一套翻页参数，但逐页打印：
  page# | items本页 | 累计found | has_more(平台返) | cursor(平台返) | 是否有 search_id

如果热词(chinesenewyear)在第7页(cursor 180->210)被平台返 has_more=false 或空items，
而前几页都 has_more=true 且满30条 —— 坐实接口硬顶，不是真实采空。
"""
import asyncio
import json
import os
import sys

from TikTokApi import TikTokApi
from crawler import create_api

SEARCH_URL = "https://www.tiktok.com/api/search/item/full/"
WEB_SEARCH_CODE = (
    '{"tiktok":{"client_params_x":{"search_engine":'
    '{"ies_mt_user_live_video_card_use_libra":1,'
    '"mt_search_general_user_live_card":1}},"search_server":{}}}'
)


async def probe(keyword: str, max_pages: int = 12):
    ms_token = os.getenv("ms_token") or os.getenv("MS_TOKEN")
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    cookies = os.getenv("TIKTOK_COOKIES_JSON")
    api = await create_api(ms_token=ms_token, proxy=proxy, cookies_path=cookies)
    print(f"### probe keyword={keyword!r} proxy={proxy}", file=sys.stderr)
    cursor = 0
    found = 0
    search_id = ""
    try:
        for page in range(max_pages):
            params = {
                "keyword": keyword,
                "count": 30,
                "cursor": cursor,
                "from_page": "search",
                "web_search_code": WEB_SEARCH_CODE,
            }
            if search_id:
                params["search_id"] = search_id
            resp = await api.make_request(url=SEARCH_URL, params=params)
            if not resp:
                print(f"page={page+1} cursor_in={cursor} -> EMPTY_RESPONSE (限流/bot检测)")
                break
            items = resp.get("item_list") or resp.get("itemList") or []
            has_more = bool(resp.get("has_more") or resp.get("hasMore"))
            ret_cursor = resp.get("cursor", cursor)
            if not search_id:
                search_id = (resp.get("log_pb") or {}).get("impr_id") or ""
            found += len(items)
            extra = {k: resp.get(k) for k in ("search_nil_info", "log_pb") if resp.get(k)}
            has_nil = "search_nil_info" in resp
            print(f"page={page+1:>2} cursor_in={cursor:>4} items={len(items):>2} "
                  f"found={found:>4} has_more={int(has_more)} cursor_ret={ret_cursor:>4} "
                  f"search_id={'Y' if search_id else 'N'} nil={int(has_nil)}")
            if not items:
                print(f"   -> 空 item_list at cursor_in={cursor}: keys={list(resp.keys())}")
                if has_nil:
                    print(f"   -> search_nil_info: {json.dumps(resp.get('search_nil_info'), ensure_ascii=False)[:300]}")
                break
            if not has_more:
                print(f"   -> has_more=FALSE at found={found} (平台声称采空)")
                break
            cursor = resp.get("cursor", cursor + len(items))
            await asyncio.sleep(1.2)
    finally:
        await api.close_sessions()
    print(f"=== DONE keyword={keyword} total_found={found} stopped_cursor={cursor} ===")


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "chinesenewyear"
    asyncio.run(probe(kw))
