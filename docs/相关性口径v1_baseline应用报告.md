# 相关性口径 v1：baseline 应用报告

> 生成时间：2026-06-16 16:59:30  
> 输入：`videos.ndjson` + `term_results_labeled.ndjson` + `config/unesco_ich_keywords.v1.json`  
> 性质：派生标签；不删除、不覆盖原始数据。

## 1. 口径来源

- 继承此前 60 条人工核查后的三档口径：`likely_relevant / needs_review / low_relevance`。
- 校正后人工核查结果：likely 桶 relevant 17/20，needs_review 桶 relevant 8/20，low 桶 relevant 4/20。
- 因 low 桶仍有真相关，本文只打派生标签，**不删除任何视频**。

## 2. baseline 全体分布（项目内去重后求和）

- 项目数：44
- 项目内去重视频总数：30,593
- `likely_relevant`: 9,241 (30.2%)
- `needs_review`: 3,488 (11.4%)
- `low_relevance`: 17,864 (58.4%)

## 3. likely 比例最高的项目

- **中医针灸** (RL): n=494, likely=368 (74.5%), needs_review=22 (4.5%), low=104 (21.1%), neg_hit=0 (0.0%)
- **太极拳** (RL): n=525, likely=377 (71.8%), needs_review=75 (14.3%), low=73 (13.9%), neg_hit=0 (0.0%)
- **春节** (RL): n=1343, likely=900 (67.0%), needs_review=115 (8.6%), low=328 (24.4%), neg_hit=0 (0.0%)
- **京剧** (RL): n=552, likely=366 (66.3%), needs_review=99 (17.9%), low=87 (15.8%), neg_hit=0 (0.0%)
- **中国书法** (RL): n=689, likely=402 (58.4%), needs_review=59 (8.6%), low=228 (33.1%), neg_hit=0 (0.0%)
- **古琴艺术** (RL): n=487, likely=277 (56.9%), needs_review=60 (12.3%), low=150 (30.8%), neg_hit=0 (0.0%)
- **端午节** (RL): n=792, likely=388 (49.0%), needs_review=180 (22.7%), low=224 (28.3%), neg_hit=0 (0.0%)
- **中国篆刻** (RL): n=669, likely=323 (48.3%), needs_review=20 (3.0%), low=326 (48.7%), neg_hit=0 (0.0%)
- **中国剪纸** (RL): n=622, likely=300 (48.2%), needs_review=137 (22.0%), low=185 (29.7%), neg_hit=0 (0.0%)
- **妈祖信俗** (RL): n=456, likely=219 (48.0%), needs_review=17 (3.7%), low=220 (48.2%), neg_hit=0 (0.0%)
- **龙泉青瓷传统烧制技艺** (RL): n=636, likely=282 (44.3%), needs_review=53 (8.3%), low=301 (47.3%), neg_hit=0 (0.0%)
- **昆曲** (RL): n=617, likely=265 (43.0%), needs_review=50 (8.1%), low=302 (48.9%), neg_hit=0 (0.0%)

## 4. low_relevance 比例最高 / 噪声风险候选

- **蒙古族长调民歌** (RL): n=617, likely=65 (10.5%), needs_review=15 (2.4%), low=537 (87.0%), neg_hit=0 (0.0%)
- **福建木偶戏** (GSP): n=865, likely=61 (7.0%), needs_review=66 (7.6%), low=738 (85.3%), neg_hit=8 (0.9%)
- **赫哲族伊玛堪** (USL): n=656, likely=62 (9.4%), needs_review=39 (5.9%), low=555 (84.6%), neg_hit=0 (0.0%)
- **西安鼓乐** (RL): n=725, likely=55 (7.6%), needs_review=79 (10.9%), low=591 (81.5%), neg_hit=0 (0.0%)
- **侗族大歌** (RL): n=572, likely=62 (10.8%), needs_review=50 (8.7%), low=460 (80.4%), neg_hit=0 (0.0%)
- **中国木活字印刷术** (USL): n=824, likely=65 (7.9%), needs_review=97 (11.8%), low=662 (80.3%), neg_hit=0 (0.0%)
- **花儿** (RL): n=462, likely=56 (12.1%), needs_review=35 (7.6%), low=371 (80.3%), neg_hit=0 (0.0%)
- **黎族传统纺染织绣技艺** (USL): n=971, likely=82 (8.4%), needs_review=121 (12.5%), low=768 (79.1%), neg_hit=1 (0.1%)
- **中国朝鲜族农乐舞** (RL): n=679, likely=88 (13.0%), needs_review=62 (9.1%), low=529 (77.9%), neg_hit=0 (0.0%)
- **藏医药浴法** (RL): n=746, likely=123 (16.5%), needs_review=44 (5.9%), low=579 (77.6%), neg_hit=0 (0.0%)
- **麦西热甫** (USL): n=542, likely=96 (17.7%), needs_review=36 (6.6%), low=410 (75.6%), neg_hit=0 (0.0%)
- **南音** (RL): n=773, likely=132 (17.1%), needs_review=60 (7.8%), low=581 (75.2%), neg_hit=0 (0.0%)

## 5. negative_terms 命中最高的项目

- **蒙古族呼麦** (RL): n=668, likely=163 (24.4%), needs_review=134 (20.1%), low=371 (55.5%), neg_hit=198 (29.6%)
  - top negative terms: `{"mongolia": 161, "tuva": 71, "tuvan": 52, "ulaanbaatar": 9, "huunhuurtu": 2, "alash": 1, "mongoliansinger": 1}`
- **中国蚕桑丝织技艺** (RL): n=1045, likely=176 (16.8%), needs_review=173 (16.6%), low=696 (66.6%), neg_hit=85 (8.1%)
  - top negative terms: `{"silkdress": 32, "factory": 19, "satin": 17, "silkscarf": 15, "duvet": 4, "silkpillowcase": 3, "industrial": 3}`
- **中国传统制茶技艺及其相关习俗** (RL): n=1206, likely=473 (39.2%), needs_review=172 (14.3%), low=561 (46.5%), neg_hit=69 (5.7%)
  - top negative terms: `{"teapet": 26, "boba": 16, "milktea": 13, "奶茶": 10, "teashop": 9, "bubbletea": 7, "matchalatte": 1}`
- **粤剧** (RL): n=457, likely=113 (24.7%), needs_review=95 (20.8%), low=249 (54.5%), neg_hit=14 (3.1%)
  - top negative terms: `{"yueopera": 10, "越剧": 5, "浙江": 4, "yueju": 1}`
- **中国皮影戏** (RL): n=728, likely=163 (22.4%), needs_review=78 (10.7%), low=487 (66.9%), neg_hit=15 (2.1%)
  - top negative terms: `{"handshadow": 11, "shadowhand": 6}`
- **福建木偶戏** (GSP): n=865, likely=61 (7.0%), needs_review=66 (7.6%), low=738 (85.3%), neg_hit=8 (0.9%)
  - top negative terms: `{"shadowpuppetry": 7, "皮影": 2, "chineseshadowpuppetry": 1}`
- **黎族传统纺染织绣技艺** (USL): n=971, likely=82 (8.4%), needs_review=121 (12.5%), low=768 (79.1%), neg_hit=1 (0.1%)
  - top negative terms: `{"restaurant": 1}`
- **春节** (RL): n=1343, likely=900 (67.0%), needs_review=115 (8.6%), low=328 (24.4%), neg_hit=0 (0.0%)
- **太极拳** (RL): n=525, likely=377 (71.8%), needs_review=75 (14.3%), low=73 (13.9%), neg_hit=0 (0.0%)
- **送王船** (RL): n=874, likely=145 (16.6%), needs_review=144 (16.5%), low=585 (66.9%), neg_hit=0 (0.0%)
- **藏医药浴法** (RL): n=746, likely=123 (16.5%), needs_review=44 (5.9%), low=579 (77.6%), neg_hit=0 (0.0%)
- **二十四节气** (RL): n=849, likely=191 (22.5%), needs_review=56 (6.6%), low=602 (70.9%), neg_hit=0 (0.0%)

## 6. 下一步

1. 用本标签重算触达：raw / likely / inclusive(likely+needs_review) / low 四套。
2. 标记 raw 高但 likely 后明显下跌的项目，作为人工复核优先对象。
3. 后续分层时同时保留 raw 与 relevance-aware 结果，避免噪声热门视频抬高结论。

