# TikTok 收口最终数据包（2026-06-19）

这个文件夹整理的是 **TikTok 单平台已经收口的最终版数据**。它是从 `data/derived/` 中已完成人工回流、人工降级、最终分层与可视化后的产物复制出来的冻结包，方便后续汇报、画图、交给队友使用。

> 口径：这里是 TikTok 单平台最终收口版，不是 YouTube，也不是跨平台最终版。

## 最重要的三个表

### 1. `tables/tiktok_final_project_findings.csv`

推荐优先读这个。它是 TikTok 单平台最终“项目级发现表”，每行一个非遗项目，包含：

- `final_tier`：最终叙事分层，例如 `T1_scale_export`、`T2_small_breakout`、`T0_false_breakout_demoted`
- `quadrant` / `quadrant_label`：存量 × 触达象限
- `likely_total_play`：最终展示/矩阵口径下的相关触达播放量；人工确认假破圈项目会被置为 0/低触达
- `statistical_likely_total_play`：行级人工回流后、但未做项目级审计降级的统计值，用于追溯
- `final_likely_total_play` / `audit_adjusted_likely_total_play`：与 `likely_total_play` 一致的审计后最终触达值
- `low_relevance_play_ratio`：低相关/噪声播放占比
- `manual_audit_verdict`：人工确认的假破圈等判定
- `headline_claim` / `interpretation`：可直接用于报告讨论的一句话解释
- `top_likely_url` / `top_noise_url`：代表性证据

用途：写报告、挑案例、做展示图时优先用这个。

### 2. `tables/tiktok_project_stock_reach_matrix_final.csv`

这是 TikTok 单平台最终 **stock × reach 矩阵表**，也就是你问的 `project_stock_reach_matrix` 最终版。

它来自原始 derived 文件：

`data/derived/project_stock_reach_matrix_manual_corrected.csv`

在 final 包中重命名为：

`tables/tiktok_project_stock_reach_matrix_final.csv`

用途：做象限图、解释“高存量高触达 / 低存量高触达 / 高存量低触达 / 低存量低触达”。

### 3. `tables/tiktok_project_reach_final.csv`

这是项目级触达统计明细，包含 raw / likely / inclusive / low 四套触达统计、播放分位数、top video 等。

用途：需要查每个项目播放量组成、噪声比例、top 视频时用这个。

## 行级标签

### `row_labels/tiktok_video_relevance_labels_final.ndjson`

TikTok 行级最终相关性标签，已应用人工回流：

- 已人工核查的视频优先使用人工标签
- 未核查视频保留自动标签
- 原始自动标签与人工回流痕迹在派生字段中保留

用途：如果需要重新聚合、抽样、查具体视频，用这个。

## 人工回流记录

### `manual_review/manual_review_returned_20260619.csv`

老师/组员返回的原始人工核查表。

### `manual_review/manual_review_applied_to_rows.csv`

人工核查如何匹配到行级视频、哪些标签被改写、一个人工 URL 是否命中多行等。

### `manual_review/manual_review_summary.json`

人工回流统计摘要。

## 文档与可视化

### `docs/TikTok_final_tiers_and_findings.md`

TikTok 人工修正后正式分层与发现说明。

### `docs/manual_review_backflow_reach_correction.md`

人工核查回流如何影响触达与矩阵的说明。

### `docs/TikTok_closed_dashboard.html`

内部分析用 HTML dashboard，可直接用浏览器打开。包含：

- 存量 × 触达气泡矩阵
- 最终分层分布
- 噪声/人工修正影响图
- 重点项目卡片
- 44 项全表筛选

### `figures/*.svg`

从 dashboard 中单独导出的 SVG 图，可用于汇报草稿或 PPT：

- `tiktok_quadrant_bubble.svg`
- `tiktok_final_tier_distribution.svg`
- `tiktok_noise_and_manual_impact.svg`

## 与跨平台矩阵的关系

跨平台 preliminary 文件仍在：

`data/derived/cross_platform_tiktok_youtube_matrix_20260619.csv`

它不是 TikTok 单平台最终版。它把 TikTok 最终收口结果与 YouTube 当时的机器-only likely 结果放在一起比较。

注意：该跨平台矩阵生成时 YouTube 侧还没有完成 AI+人工兜底回流，因此 YouTube 可信度低于 TikTok。后续如果要做“跨平台最终版”，应该使用：

1. 本文件夹中的 TikTok final 数据
2. YouTube AI+机器融合结果
3. YouTube 组员人工核查回流结果

重新生成新的 cross-platform matrix，不要把 `cross_platform_tiktok_youtube_matrix_20260619.csv` 当作最终跨平台结论。

## 关键口径

- 原始采集数据未修改；这里全部是 derived/final 复制件。
- TikTok stock 使用 hashtag `videoCount` 的定性分档。
- TikTok reach 使用审计后最终 `likely_total_play` 播放量；行级统计值保留在 `statistical_likely_total_play`。
- 人工回流优先于自动标签。
- 对人工确认的假破圈项目，即使仍有未核查自动 likely 行，也在最终矩阵中按人工审计结论降级；福船、珠算、麦西热甫最终展示触达置为 0/低触达，同时保留统计值供追溯。
- 蒙古族长调民歌经人工核查确认存在相关高播放样本，因此从“近不可见”修正为高噪声小众破圈案例；报告时必须同时说明噪声/边界风险。
- 输出只说明平台可见性/likely 触达，不直接推出受众认同、文化理解或传播成功。

## 当前最终分层摘要

- T1 规模化出海：4 项
- T1 噪声风险头部：3 项
- T2 小众破圈：9 项
- T3 国内/自循环：3 项
- T0 人工确认假破圈剔除：3 项
- T4 近不可见/已查噪：21 项
- T4 近不可见：1 项

总项目数：44。
