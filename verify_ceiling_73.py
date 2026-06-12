#!/usr/bin/env python3
"""验证 39 个 cursor=180 存疑 term 究竟是「真触顶」还是「真采空」。

核心：逐页落盘 has_more + 每页采到条数（存量分不清(a)(b)就因为没存这个）。
判定靠逐页 has_more 突变，不靠 cursor 数值：
  - 真触顶: 倒数第二页 has_more=1（满30/接近满），最后一页突然 has_more=0 且 < 30（半页突降）
  - 真采空: 在 cursor<210 处自然 has_more=0，且最后一页前已显疲态（页量递减/未满），或最后一页 has_more=0 但拿到的是该词全部
  - 限流: empty_response（整页空）→ 不计入判定，标 failed 待重采

输出:
  data/boundary73_<ts>/pages.ndjson   每页一行: keyword/page/cursor_in/items/found/has_more/cursor_ret
  data/boundary73_<ts>/verdicts.ndjson 每词一行: 逐页摘要 + 判定 + 判据
  data/boundary73_<ts>/probe.log
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from crawler import create_api  # noqa: E402

SEARCH_URL = "https://www.tiktok.com/api/search/item/full/"
WEB_SEARCH_CODE = (
    '{"tiktok":{"client_params_x":{"search_engine":'
    '{"ies_mt_user_live_video_card_use_libra":1,'
    '"mt_search_general_user_live_card":1}},"search_server":{}}}'
)
MAX_PAGES = 12          # 翻到 cursor 330+, 远超接口上限, 确保能看到触顶行为
PAGE_SLEEP = 1.2
TERM_SLEEP = 30         # 同 baseline 节奏
BURST = 5               # 一个号连采5个后换号冷却
COOLDOWN = 90

# 39 个 cursor=180 存疑词（从 term_results 提取，保持原拼写含大小写/空格）
SUSPECT_TERMS = [w["keyword"] for w in __import__("json").load(open(str(ROOT / "boundary_73_wordlist.json"), encoding="utf-8"))]

ACCOUNTS = [
    {"id": "acc1", "cookies": str(ROOT / "cookies/acc1.json"), "socks": "socks5://127.0.0.1:1092"},
    {"id": "acc2", "cookies": str(ROOT / "cookies/acc2.json"), "socks": "socks5://127.0.0.1:1093"},
    {"id": "acc3", "cookies": str(ROOT / "cookies/acc3.json"), "socks": "socks5://127.0.0.1:1094"},
    {"id": "acc4", "cookies": str(ROOT / "cookies/acc4.json"), "socks": "socks5://127.0.0.1:1092"},
]


def log(logf, msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(logf, "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def probe_term(keyword: str, acc: dict, pages_f, logf):
    """单词逐页探测，落盘每页，返回 verdict dict。"""
    os.environ["TIKTOK_COOKIES_JSON"] = acc["cookies"]
    os.environ["HTTPS_PROXY"] = acc["socks"]
    os.environ["HTTP_PROXY"] = acc["socks"]
    os.environ["TIKTOK_HEADLESS"] = "false"
    os.environ["TIKTOK_TIMEOUT_MS"] = "90000"
    api = await create_api(ms_token=None, proxy=acc["socks"], cookies_path=acc["cookies"])

    cursor = 0
    found = 0
    search_id = ""
    pages = []          # 逐页摘要
    rate_limited = False
    empty_page_ratelimit = False    # items=0 但 has_more=1 的软限流
    try:
        for page in range(MAX_PAGES):
            params = {"keyword": keyword, "count": 30, "cursor": cursor,
                      "from_page": "search", "web_search_code": WEB_SEARCH_CODE}
            if search_id:
                params["search_id"] = search_id
            resp = await api.make_request(url=SEARCH_URL, params=params)
            if not resp:
                pages.append({"page": page + 1, "cursor_in": cursor, "items": 0,
                              "has_more": None, "cursor_ret": None, "empty_response": True})
                rate_limited = True
                break
            items = resp.get("item_list") or resp.get("itemList") or []
            has_more = bool(resp.get("has_more") or resp.get("hasMore"))
            ret_cursor = resp.get("cursor", cursor)
            if not search_id:
                search_id = (resp.get("log_pb") or {}).get("impr_id") or ""
            found += len(items)
            rec = {"keyword": keyword, "account": acc["id"], "page": page + 1,
                   "cursor_in": cursor, "items": len(items), "found": found,
                   "has_more": int(has_more), "cursor_ret": ret_cursor}
            pages_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            pages_f.flush()
            pages.append({"page": page + 1, "cursor_in": cursor, "items": len(items),
                          "has_more": int(has_more), "cursor_ret": ret_cursor})
            if not items:
                # items=0 但 has_more=1 = 限流软信号（空页），不是采空也不是触顶
                # items=0 且 has_more=0 = 平台明确说到底了（罕见，归采空）
                if has_more:
                    empty_page_ratelimit = True
                break
            if not has_more:
                break
            cursor = resp.get("cursor", cursor + len(items))
            await asyncio.sleep(PAGE_SLEEP)
    finally:
        await api.close_sessions()

    # ---- 判定（靠逐页 has_more 突变，不靠 cursor 数值）----
    data_pages = [p for p in pages if not p.get("empty_response")]
    last = data_pages[-1] if data_pages else None
    prev = data_pages[-2] if len(data_pages) >= 2 else None
    last_cursor = last["cursor_ret"] if last else 0
    reached_maxpages = len(data_pages) >= MAX_PAGES

    if rate_limited or empty_page_ratelimit:
        verdict = "rate_limited"
        reason = ("empty_response（整页 null）= 限流" if rate_limited
                  else f"空页(items=0 但 has_more=1)@cursor={last_cursor} = 软限流，判定无效待重采")
    elif last is None:
        verdict = "zero_real"
        reason = "首页即空"
    elif last["has_more"] == 1 and reached_maxpages:
        # 真的翻满 MAX_PAGES 仍 has_more=1 —— 极头部，超出本批存疑范围
        verdict = "not_exhausted_in_maxpages"
        reason = f"翻满{MAX_PAGES}页仍 has_more=1，未触底（超头部）"
    elif last["has_more"] == 1 and not reached_maxpages:
        # has_more=1 但没翻满就停了，又不是空页限流 —— 异常中断，标待查
        verdict = "anomaly_early_stop"
        reason = f"has_more=1 但仅{len(data_pages)}页即停，非空页非满页，待查"
    else:
        # 最后一页 has_more=0。区分触顶 vs 采空：
        # 触顶特征: 前面页面满30且 has_more=1，到接口上限区(cursor_ret>=180)才突然 has_more=0
        prev_full_and_more = prev is not None and prev["items"] >= 28 and prev["has_more"] == 1
        last_half = last["items"] < 30
        in_ceiling_zone = last_cursor >= 180
        if prev_full_and_more and last_half and in_ceiling_zone:
            verdict = "ceiling_capped"
            reason = (f"倒二页满({prev['items']}/30)+has_more=1，末页半页突降"
                      f"({last['items']}条)+has_more=0 @cursor={last_cursor} → 触顶")
        elif in_ceiling_zone and prev_full_and_more:
            verdict = "ceiling_capped"
            reason = (f"上限区(cursor={last_cursor})突变 has_more=0，倒二页仍满+more → 触顶")
        else:
            verdict = "exhausted"
            reason = (f"末页 has_more=0 @cursor={last_cursor}，"
                      f"倒二页{'满+more' if prev_full_and_more else '已显疲态/未满'} → 真实采空")

    summary = {
        "keyword": keyword, "account": acc["id"], "found": found,
        "n_pages": len(data_pages), "last_cursor": last_cursor,
        "last_page_items": last["items"] if last else 0,
        "last_has_more": last["has_more"] if last else None,
        "prev_page_items": prev["items"] if prev else None,
        "prev_has_more": prev["has_more"] if prev else None,
        "rate_limited": rate_limited,
        "verdict": verdict, "reason": reason,
        "pages_compact": [f"p{p['page']}:i{p['items']}h{p.get('has_more')}c{p.get('cursor_ret')}"
                          for p in pages],
    }
    log(logf, f"[{verdict}] {keyword} ({acc['id']}) found={found} pages={len(data_pages)} | {reason}")
    return summary


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "data" / f"boundary73_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    logf = out / "probe.log"
    pages_path = out / "pages.ndjson"
    verdicts_path = out / "verdicts.ndjson"
    log(logf, f"=== ceiling probe 启动: {len(SUSPECT_TERMS)} 个存疑词 → {out} ===")

    from collections import deque
    MAX_RETRY = 2
    queue = deque((kw, 0) for kw in SUSPECT_TERMS)
    acc_idx = 0
    burst = 0
    done = 0
    total = len(SUSPECT_TERMS)
    with open(pages_path, "w", encoding="utf-8") as pages_f, \
         open(verdicts_path, "w", encoding="utf-8") as vf:
        while queue:
            kw, retry = queue.popleft()
            acc = ACCOUNTS[acc_idx % len(ACCOUNTS)]
            try:
                summary = await probe_term(kw, acc, pages_f, logf)
            except Exception as exc:
                summary = {"keyword": kw, "account": acc["id"], "verdict": "rate_limited",
                           "reason": f"{type(exc).__name__}: {exc}", "found": 0}
                log(logf, f"[exc->rate_limited] {kw} ({acc['id']}): {type(exc).__name__}")
            v = summary.get("verdict")
            if v == "rate_limited":
                acc_idx += 1
                burst = 0
                if retry < MAX_RETRY:
                    queue.append((kw, retry + 1))
                    log(logf, f"  rate_limited {kw} -> requeue(retry={retry+1}) switch acc cooldown{COOLDOWN}s")
                else:
                    summary["verdict"] = "unresolved_rate_limited"
                    summary["reason"] += f" | retried{MAX_RETRY}x still limited"
                    vf.write(json.dumps(summary, ensure_ascii=False) + "\n"); vf.flush()
                    done += 1
                    log(logf, f"  {kw} unresolved_rate_limited [{done}/{total}]")
                await asyncio.sleep(COOLDOWN)
                continue
            vf.write(json.dumps(summary, ensure_ascii=False) + "\n"); vf.flush()
            done += 1
            burst += 1
            log(logf, f"  [{done}/{total}] {kw} -> {v}")
            if burst >= BURST:
                acc_idx += 1
                burst = 0
                log(logf, f"  burst{BURST} -> switch acc cooldown{COOLDOWN}s")
                await asyncio.sleep(COOLDOWN)
            if queue:
                await asyncio.sleep(TERM_SLEEP)

    log(logf, "=== 完成 ===")
    # 汇总
    from collections import Counter
    verdicts = [json.loads(l) for l in open(verdicts_path)]
    c = Counter(v["verdict"] for v in verdicts)
    log(logf, f"判定分布: {dict(c)}")
    print(f"\nVERDICTS_FILE={verdicts_path}")
    print(f"PAGES_FILE={pages_path}")


if __name__ == "__main__":
    asyncio.run(main())
