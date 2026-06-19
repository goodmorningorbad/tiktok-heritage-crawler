# YouTube 相关性 + 触达初步汇总（3页扩采）

> 生成时间：2026-06-19 13:58:18
> 输入：`data/derived/youtube_initial_20260616_pages3/`
> 口径：复用 TikTok 相关性口径 v1；派生标签，不删除 raw 视频。

## 1. 口径确认

- 三档标签沿用 TikTok：`likely_relevant / needs_review / low_relevance`。
- `low_relevance` 不删除，只作为噪声与语义稀释风险进入后续判断。
- 组员标出的 YouTube 噪声词作为 `negative_terms` 参考，例如 calligraphy / paper cutting / timber architecture / Korean farmers dance 等；命中后降分并保留证据。
- `failed / zero_real / exhausted / sample_limit_reached / ceiling_capped_500` 与相关性标签分开，不混用。
- 当前 56 个 `sample_limit_reached` 词是**3页截断下限**，不是平台硬顶；热门项目 YouTube 触达会被低估，后续深采要继续加页。

## 2. 采集状态

- term 数：8
- `exhausted`: 3
- `ceiling_capped_500`: 5
- `sample_limit_reached` = 人为 3 页限制后的下限；区别于 TikTok search 接口约 196 条的真实平台翻页上限。

## 3. 相关性分布（项目内去重后求和）

- 项目数：6
- 项目内去重视频总数：2,674
- `likely_relevant`: 2,341 (87.5%)
- `needs_review`: 190 (7.1%)
- `low_relevance`: 143 (5.3%)

## 4. likely 触达最高的项目（当前为3页下限）

- **中国蚕桑丝织技艺**: raw=264 / likely=153 (58.0%), low=22 (8.3%); likely_play=241,296,974, raw_play=328,035,486, risk=low, tier=top_20pct_reach
- **古琴艺术**: raw=762 / likely=706 (92.7%), low=14 (1.8%); likely_play=175,390,571, raw_play=345,334,925, risk=low, tier=high_20_40pct_reach
- **中国书法**: raw=451 / likely=413 (91.6%), low=26 (5.8%); likely_play=50,451,296, raw_play=89,291,388, risk=low, tier=middle_40_70pct_reach
- **粤剧**: raw=441 / likely=420 (95.2%), low=14 (3.2%); likely_play=24,638,281, raw_play=35,175,013, risk=medium, tier=middle_40_70pct_reach
- **妈祖信俗**: raw=229 / likely=188 (82.1%), low=35 (15.3%); likely_play=15,271,814, raw_play=18,848,417, risk=low, tier=lower_70_90pct_reach
- **中国篆刻**: raw=527 / likely=461 (87.5%), low=32 (6.1%); likely_play=39,614,347, raw_play=45,711,131, risk=low, tier=bottom_10pct_reach
- **春节**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **中国传统制茶技艺及其相关习俗**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **太极拳**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **送王船**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **藏医药浴法**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **二十四节气**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos

## 5. 噪声风险最高的项目

- **粤剧**: raw=441 / likely=420 (95.2%), low=14 (3.2%); likely_play=24,638,281, raw_play=35,175,013, risk=medium, tier=middle_40_70pct_reach
- **中国书法**: raw=451 / likely=413 (91.6%), low=26 (5.8%); likely_play=50,451,296, raw_play=89,291,388, risk=low, tier=middle_40_70pct_reach
- **中国篆刻**: raw=527 / likely=461 (87.5%), low=32 (6.1%); likely_play=39,614,347, raw_play=45,711,131, risk=low, tier=bottom_10pct_reach
- **古琴艺术**: raw=762 / likely=706 (92.7%), low=14 (1.8%); likely_play=175,390,571, raw_play=345,334,925, risk=low, tier=high_20_40pct_reach
- **中国蚕桑丝织技艺**: raw=264 / likely=153 (58.0%), low=22 (8.3%); likely_play=241,296,974, raw_play=328,035,486, risk=low, tier=top_20pct_reach
- **妈祖信俗**: raw=229 / likely=188 (82.1%), low=35 (15.3%); likely_play=15,271,814, raw_play=18,848,417, risk=low, tier=lower_70_90pct_reach
- **春节**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **中国传统制茶技艺及其相关习俗**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **太极拳**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **送王船**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **藏医药浴法**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos
- **二十四节气**: raw=0 / likely=0 (0.0%), low=0 (0.0%); likely_play=0, raw_play=0, risk=low, tier=no_videos

## 6. raw → likely 后触达档位下跌项目

- 暂无 raw→likely 相对档位下跌项目；后续仍需人工抽查高播放 raw top 是否为噪声。

## 7. 3页内自然采空词与跨平台一致低存量

- **中国蚕桑丝织技艺** — `Chinese silk sericulture`: collected=264, totalResults_estimate≈22626
- **中国篆刻** — `seal engraving`: collected=195, totalResults_estimate≈574180
- **妈祖信俗** — `Mazu`: collected=229, totalResults_estimate≈985852

这 5 个词不是 3页人为截断，而是在当前 YouTube relevance 搜索口径下自然结束；其中侗族大歌、龙泉青瓷、热贡、呼麦、蒙古族长调与 TikTok 低存量方向一致，后续可作为跨平台一致性发现继续验证。

## 8. 下一步

1. 先由本表挑 deep-crawl 候选：YouTube likely 高触达、raw→likely 噪声变化大、以及 TikTok 关键象限项目。
2. 深采名单不要按 YouTube raw 热度单独决定，要参照 TikTok 存量×触达象限。
3. 对仍为 `sample_limit_reached` 的热门词继续加页；采到 10 页仍有 nextPageToken 时再标 `ceiling_capped_500`。
