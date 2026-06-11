# TikTok-Api 库 patch 记录：page.goto 等待条件

更新时间：2026-06-11

## 问题

`run_second_test.py` / `crawler.py` 走 TikTokApi 的 `create_sessions` 创建浏览器
session 时，会卡 `Page.goto: Timeout 30000ms exceeded - navigating to
"https://www.tiktok.com/", waiting until "load"`，所有项目采到 0 条。

根因：TikTok-Api 库内部 `page.goto(url)` 用 playwright 默认 `wait_until="load"`，
而 TikTok 首页资源持续加载、`load` 事件几乎永远不触发，30s 必超时。
`crawler.py` 里设的 `timeout=90000` 控制不到库内部这个 goto 的等待条件。

对照：cookie refresher（`refresh_tiktok_cookies.py`）一直成功，因为它用的是
`wait_until="domcontentloaded"` + `timeout=90000`。

## 改动

文件：`/root/workspace/TikTok-Api/TikTokApi/tiktok.py`（约 368 / 371 行）

```python
# 原
_ = await page.goto(url)
...
_ = await page.goto("https://www.tiktok.com")

# 改为
_ = await page.goto(url, wait_until="domcontentloaded", timeout=90000)
...
_ = await page.goto("https://www.tiktok.com", wait_until="domcontentloaded", timeout=90000)
```

备份：同目录 `tiktok.py.bak-goto-20260611_231539`

## 验证

patch 后 hashtag smoke 前 3 项全 ✓：春节 6 / 制茶 6 / 太极 4，共 16 条真实视频
（含 play/digg/comment/share、hashtags、作者、create_time 等完整字段）。

## 注意

- TikTok-Api 是从 git 源码装在 `/root/workspace/TikTok-Api`，不是 pip 包，patch 直接生效。
- 若将来重装/更新该库，需要重新打这个 patch，否则采集会再次全 0。
