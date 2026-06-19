# YouTube AI+机器融合与推荐档人工清单（2026-06-19）

## 口径

- 原始 YouTube 机器标签不修改；AI 结果与融合标签均为 additive derived artifacts。
- `machine likely + AI 不相关` 不自动降级，只标为冲突；仅高影响/关键项目进入人工。
- `machine weak + AI 不相关` 自动降为低可信噪声。
- `AI 相关` 只作为候选增强，不单独当最终人工真值。

## 重要限制

> YouTube 高播放段经人工兜底；中低播放段为 AI+机器融合未逐条人工核查，可能含残余噪声。YouTube 侧定位为中等可信辅助维度，可信度低于 TikTok 全人工回流。

## 统计

- 输入视频标签：7320 条
- AI verdict：{'相关': 4352, '不相关': 2313, '拿不准': 655}
- 机器标签：{'likely_relevant': 5743, 'needs_review': 959, 'low_relevance': 618}
- 推荐档人工清单：250 条
- 其中 views ≥ 5M：66 条
- 蚕桑强制覆盖：108 条

## 蚕桑覆盖检查

- ✅ 21:87duJEtkLs4 | views=128533351 | machine=likely_relevant | AI=不相关 | Amazing Silk Preparation Complete Process Using Silkworm #shorts
- ✅ 21:rTqGygoYu9w | views=61703460 | machine=likely_relevant | AI=不相关 | Suzhou Embroidery: China’s 2,500-Year-Old Luxury Silk Art That Inspires the World
- ❌ 21:jL0lvjynycg | views=33869734 | machine=needs_review | AI=不相关 | Why I Don't Wear Silk #353
- ✅ 21:OrXiXDUQia8 | views=32422970 | machine=likely_relevant | AI=相关 | 古老的东方蚕桑文化，治愈每一个怕冷的人——蚕丝被 winter bedding from double-cocoon silk | Liziqi Channel
- ❌ 21:frUcQ0gWtlo | views=18912830 | machine=needs_review | AI=不相关 | Making Fabric From Caterpillar Cocoons
- ❌ 21:y69OO0QuSu0 | views=7731973 | machine=low_relevance | AI=不相关 | Silk manufacturing explained #factsintelugu 😱పట్టు పురుగులు😱 #amazingfacts #truefacts #shorts
- ✅ 21:ht6SPPJMqwE | views=5965291 | machine=needs_review | AI=相关 | SilkWorm Farm - How Billions of SilkWorm for silk Chinese - Silk Cocoon Harvest Processing Factory
- ✅ 21:xBz40ZxKJBs | views=4959104 | machine=likely_relevant | AI=不相关 | How Mountains Of Worm Cocoons Are Turned Into Expensive Silk In Vietnam | Big Business
- ❌ 21:oIPYqWkBhhA | views=4557503 | machine=needs_review | AI=不相关 | The Fuguangjin Silk #clothing #chinaculture #learnchinese #silk #style #fashion #fabric
- ✅ 21:3LcysDwqClY | views=4397318 | machine=likely_relevant | AI=不相关 | How Silkworms Create the World’s Most Luxurious Fabric?

## 输出文件

- 融合标签 NDJSON：`data/derived/youtube_ai_machine_fusion_labels_20260619.ndjson`
- 融合标签 CSV：`data/derived/youtube_ai_machine_fusion_labels_20260619.csv`
- 推荐人工清单：`data/derived/youtube_manual_review_queue_recommended_20260619.csv`
- 摘要 JSON：`data/derived/youtube_ai_machine_fusion_summary_20260619.json`
