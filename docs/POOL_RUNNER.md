# 账号×IP Pool Runner（US 住宅基准）

把 N 个非遗项目按「账号×住宅 IP」固定分配，每个分片用钉死的
`(account, cookie, proxy_port, region)` 组合调用 `batch_collect.py`，
保证 **single-region baseline** + **来源可追溯**。

## 架构

```
pool_runner.py
  ├─ 读 config/us_pool.json   (账号列表 × 住宅IP端口列表)
  ├─ build_slots()            每个 slot = 一个账号绑一个独立 SOCKS 端口
  ├─ assign_projects()        44 项 round-robin / chunk 分到各 slot
  ├─ 每 slot 写临时 keyword config（只含分到的项目）
  └─ 每 slot 钉死 env 起 batch_collect.py（串行）
       HTTPS_PROXY=socks5://127.0.0.1:<port>   ← region 锁死
       TIKTOK_ACCOUNT_ID / PROXY_ID / PROXY_REGION ...  ← 写进每条数据
```

## 代理层：独立 US-only SOCKS 实例（路 B，隔离）

**绝不碰** turn-proxy 既有 `:1090`(全球混合) / `:1091`(住宅混合)。
采集专用，每条 US 住宅 IP 一个单出口端口：

| 端口 | service | exit IP | ISP | 地区 |
|---|---|---|---|---|
| :1092 | tiktok-us-socks-1 | 142.196.231.14 | Charter | US-FL |
| :1093 | tiktok-us-socks-2 | 192.184.255.206 | Sonic | US-CA |
| :1094 | tiktok-us-socks-3 | 76.113.58.60 | Comcast | US-NM |

- 配置：`/opt/turn-proxy-pool/us-pool/us{1,2,3}.json`（各只含 1 条 IP）
- systemd：`tiktok-us-socks-{1,2,3}.service`（enabled + Restart=always）
- 复用 `/opt/turn-proxy-pool/turn-socks.js`，单点模式（config 里只 1 条 → 不轮换 → 出口锁死）
- 日志：`/var/log/tiktok-us-socks-{1,2,3}.log`

### 验活 / 重启

```bash
# 看落地 IP（必须 = 对应 exit_ip）
for p in 1092 1093 1094; do
  curl -s -m 20 --socks5-hostname 127.0.0.1:$p https://ipinfo.io/json | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("ip"),d.get("country"),d.get("region"))'
done

# 重启
systemctl restart tiktok-us-socks-1 tiktok-us-socks-2 tiktok-us-socks-3
```

### IP 死了怎么换

1. 从 `/opt/turn-proxy-pool/residential-only.json` 重新筛 US 住宅、验活
   （落地匹配 + tiktok 200，参考下面的筛选脚本）
2. 替换对应 `us-pool/usN.json` 里那一条
3. `systemctl restart tiktok-us-socks-N`
4. 同步更新 `config/us_pool.json` 里的 exit_ip/isp/subregion

> Level3（机房性质）和 ipinfo 拿不到落地的 IP 不要用。当前 6 条 US 住宅里
> 只有 3 条通过双重验活（142.196.231.14 / 192.184.255.206 / 76.113.58.60）。

## 账号绑定

`config/us_pool.json`：acc1→FL / acc2→CA / acc3→NM。**acc4 留作备份 / 降质核对，不进池**。
cookie 由 `tiktok-cookie-refresh.timer` 每 30min 刷新（acc1-4 全活）。

## 用法

```bash
cd /root/workspace/tiktok-heritage-crawler

# dry-run：只看分配方案
python3 pool_runner.py --dry-run --channels both --videos-per-term 2000

# 端到端 smoke（每号 1 项，少量）
python3 pool_runner.py --channels hashtag --videos-per-term 5 --limit-projects 3 --phase smoke --headful

# 标签规模全量（challenge videoCount/viewCount，快，几分钟出 44 项骨架）
python3 pool_runner.py --channels hashtag-stats --phase tag-scale --headful

# 正式摸底（search 单 region 基准，临时上限 2000）
python3 pool_runner.py --channels search --videos-per-term 2000 --phase pilot --headful
```

- 通道：`search` / `hashtag`（视频流）/ `hashtag-stats`（challenge 规模，标含噪声）/ `both`(=search+hashtag)

- `--assign round-robin`（默认，均衡）/ `chunk`（连续切块）
- `--headful`：xvfb-run + TIKTOK_HEADLESS=false（hashtag 通道更稳）
- 每 slot 是独立 `batch_collect` run，各自 run_id，数据落 `data/`
- 分配 manifest：`data/pool_manifest_<run_id>.json`（号×IP×项目，可追溯）

## 元数据落库（口径保证）

每条数据带 `collector` 上下文（batch_collect.collector_context 读 env）：
`collector_account / collector_account_role / proxy_region / proxy_pool / proxy_id`。
report 顶层带 `region_policy=single-region-baseline` + `collection_phase`。
→ 任何一条数据都能回溯「哪个号、走哪条 US 住宅 IP、什么 region」采的。

## 注意

- runner 当前**串行**跑各 slot（避免同时多号触发风控 / cookie 刷新竞争）。
  需要并行后续再加（每 slot 独立端口 + 独立号，技术上可并行）。
- region 只锁 US。要扩别的 region/全球，另起 pool 文件 + 另一批端口，不在本 pool 混。
