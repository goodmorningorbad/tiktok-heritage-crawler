# TikTok 非遗出海数据采集环境

部署目标：基于 <https://github.com/davidteather/TikTok-Api> 在本机采集 TikTok 搜索/话题视频元数据，用于数据新闻大赛「中国非遗出海」。

## 路径

- 项目源码：`/root/workspace/TikTok-Api`
- Python 虚拟环境：`/root/workspace/tiktok-api-venv`
- 采集工作目录：`/root/workspace/tiktok-heritage-crawler`
- 输出目录：`/root/workspace/tiktok-heritage-crawler/data`

## 首次配置

TikTok-Api 通常需要 TikTok 网页 Cookie 里的 `msToken`。

1. 用浏览器打开 `https://www.tiktok.com/`，最好先搜索一次任意关键词。
2. DevTools → Application/Storage → Cookies → `https://www.tiktok.com`
3. 找到 `msToken`，写入：

```bash
cd /root/workspace/tiktok-heritage-crawler
cp .env.example .env
nano .env
```

`.env` 格式：

```bash
ms_token="你的 msToken"
TIKTOK_BROWSER=chromium
TIKTOK_TIMEOUT_MS=90000
# 更推荐：导出整组 TikTok cookies 到 cookies.json，然后启用这一行
# TIKTOK_COOKIES_JSON=/root/workspace/tiktok-heritage-crawler/cookies.json
# 可选：代理，TikTok 如果本机网络不可达时填
# HTTPS_PROXY=http://user:pass@host:port
# HTTP_PROXY=http://user:pass@host:port
```

## 采集关键词搜索视频

```bash
cd /root/workspace/tiktok-heritage-crawler
source /root/workspace/tiktok-api-venv/bin/activate
set -a; source .env; set +a
python crawler.py search --keywords "intangible cultural heritage,Chinese intangible cultural heritage,非遗,汉服,剪纸,漆扇,中国传统文化" --count 50 --out data/search.ndjson
```

## 采集 hashtag 视频

```bash
cd /root/workspace/tiktok-heritage-crawler
source /root/workspace/tiktok-api-venv/bin/activate
set -a; source .env; set +a
python crawler.py hashtag --hashtags "chineseculture,hanfu,papercutting,traditionalchinese,非遗" --count 50 --out data/hashtags.ndjson
```

## 输出格式

默认是 NDJSON：一行一个视频，字段包括：

- `source_type`: search / hashtag
- `source`: 关键词或 hashtag
- `id`, `desc`, `create_time`, `web_url`
- `author_*`
- `stats_*`: 播放/点赞/评论/分享/收藏
- `music_*`
- `hashtags`
- `raw`: TikTok 返回的原始视频对象

## 导出 CSV

```bash
python ndjson_to_csv.py data/search.ndjson data/search.csv
python ndjson_to_csv.py data/hashtags.ndjson data/hashtags.csv
```

## 复现部署

```bash
bash deploy.sh
```
