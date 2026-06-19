# TikTok 人工修正后正式分层与发现（2026-06-19）

> 口径：基于 `project_stock_reach_matrix_manual_corrected.csv` 与 `tiktok_manual_corrected_final_project_findings_20260619.csv`。人工核查覆盖的视频优先覆盖自动标签；麦西热甫/福船/珠算这类 targeted audit 证伪项按最终解释降级，不再作为破圈。`likely_total_play` 为最终展示/矩阵口径；`statistical_likely_total_play` 保留行级统计值供追溯。

## 1. 分层总览
- `T1_scale_export`: 4
- `T1_scale_export_with_noise_risk`: 3
- `T2_small_breakout`: 9
- `T3_domestic_or_self_circulating`: 3
- `T0_false_breakout_demoted`: 3
- `T4_near_invisible_noise_checked`: 21
- `T4_near_invisible`: 1

象限：
- `stock_high__reach_high`: 7
- `stock_low__reach_high`: 9
- `stock_high__reach_low`: 3
- `stock_low__reach_low`: 25

## 2. T1 规模化可见项目
- **春节**：final_play=1,190,216,794，stock=stock_high，noise=medium；春节 是规模与相关触达均较强的头部可见项目。
- **中国书法**：final_play=842,210,064，stock=stock_high，noise=low；中国书法 是规模与相关触达均较强的头部可见项目。
- **太极拳**：final_play=248,769,168，stock=stock_high，noise=low；太极拳 是规模与相关触达均较强的头部可见项目。
- **中国剪纸**：final_play=205,339,021，stock=stock_high，noise=medium；中国剪纸 是规模与相关触达均较强的头部可见项目。
- **中国传统制茶技艺及其相关习俗**：final_play=143,086,500，stock=stock_high，noise=high；中国传统制茶技艺及其相关习俗 是规模与相关触达均较强的头部可见项目。
- **南京云锦织造技艺**：final_play=101,751,989，stock=stock_high，noise=high；南京云锦织造技艺 是规模与相关触达均较强的头部可见项目。
- **玛纳斯**：final_play=101,345,094，stock=stock_high，noise=high；玛纳斯 是规模与相关触达均较强的头部可见项目。

## 3. T2 小而精/高噪声破圈候选
- **京剧**：final_play=344,408,249，statistical_play=344,408,249，manual_review=4/19 related/reviewed；top=https://www.tiktok.com/@musicwang136/video/7205388003118697770
- **蒙古族呼麦**：final_play=320,266,425，statistical_play=320,266,425，manual_review=3/9 related/reviewed；top=https://www.tiktok.com/@erklen/video/7544518597226401037
- **宣纸传统制作技艺**：final_play=273,472,611，statistical_play=273,472,611，manual_review=3/10 related/reviewed；top=https://www.tiktok.com/@trendygabriel/video/7321072687260962091
- **中医针灸**：final_play=245,199,475，statistical_play=245,199,475，manual_review=1/8 related/reviewed；top=https://www.tiktok.com/@geotherapy/video/7416634811328007456
- **蒙古族长调民歌**：final_play=149,500,000，statistical_play=153,711,277，manual_review=3/13 related/reviewed；top=https://www.tiktok.com/@erklen/video/7544518597226401037；注意：这是人工确认相关高播放样本后的高噪声案例，不是近不可见
- **中国木活字印刷术**：final_play=140,944,338，statistical_play=140,944,338，manual_review=7/14 related/reviewed；top=https://www.tiktok.com/@xiedapao88/video/7404039857405742344
- **龙泉青瓷传统烧制技艺**：final_play=112,095,917，statistical_play=112,095,917，manual_review=5/16 related/reviewed；top=https://www.tiktok.com/@shanbai09/video/7569629481434975502
- **端午节**：final_play=111,202,009，statistical_play=111,202,009，manual_review=0/1 related/reviewed；top=https://www.tiktok.com/@art6859/video/7378664738378517806
- **古琴艺术**：final_play=106,426,001，statistical_play=106,426,001，manual_review=6/12 related/reviewed；top=https://www.tiktok.com/@mizdramaholic/video/7485060943156694303

## 4. T3 高存量低触达
- **中国雕版印刷技艺**：stock=stock_high，final_play=93,351,113，low_ratio=0.7101；中国雕版印刷技艺 存量较高但相关触达未同步放大，偏自产自销/弱外溢。
- **妈祖信俗**：stock=stock_high，final_play=46,836,788，low_ratio=0.8212；妈祖信俗 存量较高但相关触达未同步放大，偏自产自销/弱外溢。
- **中国传统木结构建筑营造技艺**：stock=stock_high，final_play=38,819,861，low_ratio=0.8407；中国传统木结构建筑营造技艺 存量较高但相关触达未同步放大，偏自产自销/弱外溢。

## 5. 人工确认 false breakout
- **中国水密隔舱福船制造技艺**：statistical_play=184,008,225 → final_play=0，final=stock_low__reach_low，manual_unrelated=9/9。
- **中国珠算**：statistical_play=169,744,719 → final_play=0，final=stock_low__reach_low，manual_unrelated=9/9。
- **麦西热甫**：statistical_play=61,411,002 → final_play=0，final=stock_low__reach_low，manual_unrelated=10/10。

## 6. 关键修正说明
- 福船、珠算、麦西热甫：行级统计里仍可追溯未审自动 likely 残余，但 targeted high-impact 人工核查证伪了破圈证据，因此最终展示触达置为 0/低触达。
- 蒙古族长调民歌：人工核查并非全盘否定；最终行级标签中有 3 条人工确认相关的高播放样本，final_play=149,500,000，因此从“近不可见/已查噪”修正为 T2 高噪声小众破圈。
- 输出只说明平台可见性/likely 触达，不直接推出受众认同或文化理解。

## 7. 输出文件
- CSV: `data/derived/tiktok_manual_corrected_final_project_findings_20260619.csv`
- JSON: `data/derived/tiktok_manual_corrected_final_project_findings_20260619.json`
