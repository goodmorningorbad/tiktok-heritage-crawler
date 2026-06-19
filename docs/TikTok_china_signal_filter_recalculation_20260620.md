# TikTok 中国信号硬过滤重算（2026-06-20）

> 生成时间：2026-06-20 02:08:33  
> 过滤口径：`quality_label == likely_relevant` 且必须满足 `china_context_hit == True` 或 `has_cjk_desc == True`。

## 口径说明

- 经中国信号过滤（china_context_hit 或 has_cjk_desc），但未全量人工核查；中低播放段可能仍有残余噪声。文本撞词噪声（如 papercut/calligraphy/taichi 等）可有效识别并过滤；残余误差主要来自无文本线索、纯画面是中国非遗的视频，文本方法无法判定。
- 被过滤掉的视频不是从原始数据删除，而是从 signal-filtered likely reach 池剔除；原始 row labels 保留，便于复核。
- 防误杀抽样清单见 `manual_review/tiktok_china_signal_filtered_out_high_noise_review_sample_20260620.csv`：对 no-China-signal 占比 >50% 的高噪声项目，每项抽取最高播放 10 条被过滤视频，供人工标注误杀率。

## 高噪声项目（no-China-signal likely unique 占比 >50%）

- **中国雕版印刷技艺**: no-signal unique 95.6%; play drop 41,444,152; 93,351,113 → 51,906,961; quadrant stock_high__reach_low → stock_high__reach_high
- **中国水密隔舱福船制造技艺**: no-signal unique 93.7%; play drop 183,904,718; 184,008,225 → 103,507; quadrant stock_low__reach_high → stock_low__reach_low
- **赫哲族伊玛堪**: no-signal unique 91.5%; play drop 8,128,917; 8,230,401 → 101,484; quadrant stock_low__reach_low → stock_low__reach_low
- **玛纳斯**: no-signal unique 88.8%; play drop 98,453,986; 101,345,094 → 2,891,108; quadrant stock_high__reach_high → stock_high__reach_low
- **蒙古族长调民歌**: no-signal unique 87.7%; play drop 149,141,028; 149,500,000 → 358,972; quadrant stock_low__reach_high → stock_low__reach_low
- **南京云锦织造技艺**: no-signal unique 80.7%; play drop 101,091,995; 101,751,989 → 659,994; quadrant stock_high__reach_high → stock_high__reach_low
- **中国珠算**: no-signal unique 78.5%; play drop 149,513,448; 169,744,719 → 20,231,271; quadrant stock_low__reach_high → stock_low__reach_low
- **送王船**: no-signal unique 76.1%; play drop 19,774,877; 20,773,209 → 998,332; quadrant stock_low__reach_low → stock_low__reach_low
- **格萨(斯)尔史诗传统**: no-signal unique 75.0%; play drop 1,727,782; 1,787,008 → 59,226; quadrant stock_low__reach_low → stock_low__reach_low
- **新疆维吾尔木卡姆艺术**: no-signal unique 72.1%; play drop 5,641,576; 6,692,744 → 1,051,168; quadrant stock_low__reach_low → stock_low__reach_low
- **宣纸传统制作技艺**: no-signal unique 70.9%; play drop 207,510,160; 273,472,611 → 65,962,451; quadrant stock_low__reach_high → stock_low__reach_high
- **中国木拱桥传统营造技艺**: no-signal unique 69.7%; play drop 3,018,793; 4,076,393 → 1,057,600; quadrant stock_low__reach_low → stock_low__reach_low
- **中国剪纸**: no-signal unique 63.3%; play drop 176,581,547; 205,339,021 → 28,757,474; quadrant stock_high__reach_high → stock_high__reach_low
- **中国朝鲜族农乐舞**: no-signal unique 61.2%; play drop 1,480,965; 2,671,328 → 1,190,363; quadrant stock_low__reach_low → stock_low__reach_low
- **中国蚕桑丝织技艺**: no-signal unique 60.0%; play drop 9,487,293; 48,894,741 → 39,407,448; quadrant stock_low__reach_low → stock_low__reach_high
- **龙泉青瓷传统烧制技艺**: no-signal unique 58.6%; play drop 28,555,034; 112,095,917 → 83,540,883; quadrant stock_low__reach_high → stock_low__reach_high
- **蒙古族呼麦**: no-signal unique 58.0%; play drop 199,432,472; 320,266,425 → 120,833,953; quadrant stock_low__reach_high → stock_low__reach_high
- **中医针灸**: no-signal unique 55.3%; play drop 162,140,426; 245,199,475 → 83,059,049; quadrant stock_low__reach_high → stock_low__reach_high
- **麦西热甫**: no-signal unique 54.9%; play drop 29,269,051; 61,411,002 → 32,141,951; quadrant stock_low__reach_high → stock_low__reach_high

## 象限变化项目

- **中国水密隔舱福船制造技艺**: stock_low__reach_high → stock_low__reach_low; likely_play 184,008,225 → 103,507; tier high_20_40pct_reach → bottom_10pct_reach
- **中国剪纸**: stock_high__reach_high → stock_high__reach_low; likely_play 205,339,021 → 28,757,474; tier high_20_40pct_reach → middle_40_70pct_reach
- **中国珠算**: stock_low__reach_high → stock_low__reach_low; likely_play 169,744,719 → 20,231,271; tier high_20_40pct_reach → middle_40_70pct_reach
- **蒙古族长调民歌**: stock_low__reach_high → stock_low__reach_low; likely_play 149,500,000 → 358,972; tier manual_confirmed_high_noise_niche_reach → lower_70_90pct_reach
- **南京云锦织造技艺**: stock_high__reach_high → stock_high__reach_low; likely_play 101,751,989 → 659,994; tier high_20_40pct_reach → lower_70_90pct_reach
- **玛纳斯**: stock_high__reach_high → stock_high__reach_low; likely_play 101,345,094 → 2,891,108; tier high_20_40pct_reach → middle_40_70pct_reach
- **中国雕版印刷技艺**: stock_high__reach_low → stock_high__reach_high; likely_play 93,351,113 → 51,906,961; tier middle_40_70pct_reach → top_20pct_reach
- **中国蚕桑丝织技艺**: stock_low__reach_low → stock_low__reach_high; likely_play 48,894,741 → 39,407,448; tier middle_40_70pct_reach → high_20_40pct_reach
- **羌年**: stock_low__reach_low → stock_low__reach_high; likely_play 38,667,397 → 29,202,414; tier middle_40_70pct_reach → high_20_40pct_reach
- **粤剧**: stock_low__reach_low → stock_low__reach_high; likely_play 40,755,989 → 40,755,989; tier middle_40_70pct_reach → high_20_40pct_reach

## 触达缩水最多（Top 20）

- **中国书法**: 842,210,064 → 206,171,778; drop=636,038,286 (75.5%); quadrant=stock_high__reach_high
- **宣纸传统制作技艺**: 273,472,611 → 65,962,451; drop=207,510,160 (75.9%); quadrant=stock_low__reach_high
- **蒙古族呼麦**: 320,266,425 → 120,833,953; drop=199,432,472 (62.3%); quadrant=stock_low__reach_high
- **中国水密隔舱福船制造技艺**: 184,008,225 → 103,507; drop=183,904,718 (99.9%); quadrant=stock_low__reach_low
- **中国剪纸**: 205,339,021 → 28,757,474; drop=176,581,547 (86.0%); quadrant=stock_high__reach_low
- **中医针灸**: 245,199,475 → 83,059,049; drop=162,140,426 (66.1%); quadrant=stock_low__reach_high
- **中国珠算**: 169,744,719 → 20,231,271; drop=149,513,448 (88.1%); quadrant=stock_low__reach_low
- **蒙古族长调民歌**: 149,500,000 → 358,972; drop=149,141,028 (99.8%); quadrant=stock_low__reach_low
- **太极拳**: 248,769,168 → 115,211,676; drop=133,557,492 (53.7%); quadrant=stock_high__reach_high
- **南京云锦织造技艺**: 101,751,989 → 659,994; drop=101,091,995 (99.4%); quadrant=stock_high__reach_low
- **玛纳斯**: 101,345,094 → 2,891,108; drop=98,453,986 (97.2%); quadrant=stock_high__reach_low
- **京剧**: 344,408,249 → 277,040,345; drop=67,367,904 (19.6%); quadrant=stock_low__reach_high
- **中国雕版印刷技艺**: 93,351,113 → 51,906,961; drop=41,444,152 (44.4%); quadrant=stock_high__reach_high
- **麦西热甫**: 61,411,002 → 32,141,951; drop=29,269,051 (47.7%); quadrant=stock_low__reach_high
- **龙泉青瓷传统烧制技艺**: 112,095,917 → 83,540,883; drop=28,555,034 (25.5%); quadrant=stock_low__reach_high
- **春节**: 1,190,216,794 → 1,163,181,075; drop=27,035,719 (2.3%); quadrant=stock_high__reach_high
- **中国传统木结构建筑营造技艺**: 38,819,861 → 12,786,624; drop=26,033,237 (67.1%); quadrant=stock_high__reach_low
- **古琴艺术**: 106,426,001 → 81,703,950; drop=24,722,051 (23.2%); quadrant=stock_low__reach_high
- **妈祖信俗**: 46,836,788 → 25,059,404; drop=21,777,384 (46.5%); quadrant=stock_high__reach_low
- **送王船**: 20,773,209 → 998,332; drop=19,774,877 (95.2%); quadrant=stock_low__reach_low

## 输出文件

- `tables/tiktok_china_signal_filtered_reach_comparison_20260620.csv/json` — 44 项重算前后对比。
- `tables/tiktok_china_signal_filtered_matrix_20260620.csv/json` — signal-filtered 新四象限矩阵。
- `manual_review/tiktok_china_signal_filtered_out_high_noise_review_sample_20260620.csv` — 高噪声项目被过滤视频人工防误杀抽样清单。
