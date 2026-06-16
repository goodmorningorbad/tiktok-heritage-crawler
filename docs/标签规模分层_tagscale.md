# 标签规模分层：hashtag statsV2 videoCount

> 生成时间：2026-06-16 17:17:55  
> 性质：派生存量规模轴；`videoCount` 是 hashtag challenge 聚合规模，含噪声，不等于触达。

## 1. 总览

- 项目数：44
- `clean`: 44
- `noisy`: 0
- `unavailable`: 0
- 分层阈值：head ≥100K；mid 10K–100K；long_tail 1K–10K；near_invisible <1K
- `scale_video_count_tier=head`: 5
- `scale_video_count_tier=mid`: 5
- `scale_video_count_tier=long_tail`: 8
- `scale_video_count_tier=near_invisible`: 26
- `scale_video_count_tier=unavailable`: 0

## 2. 规模最高项目（按 best usable hashtag videoCount）

- **中国书法** (RL): state=`clean`, best=#calligraphy, videoCount=1,715,067, clean_terms=2, noisy_terms=1
- **春节** (RL): state=`clean`, best=#chinesenewyear, videoCount=640,926, clean_terms=4, noisy_terms=2
- **南京云锦织造技艺** (RL): state=`clean`, best=#yunjin, videoCount=603,357, clean_terms=4, noisy_terms=0
- **太极拳** (RL): state=`clean`, best=#taichi, videoCount=210,873, clean_terms=4, noisy_terms=0
- **玛纳斯** (RL): state=`clean`, best=#manas, videoCount=103,875, clean_terms=2, noisy_terms=0
- **中国雕版印刷技艺** (RL): state=`clean`, best=#blockprinting, videoCount=31,993, clean_terms=2, noisy_terms=0
- **中国剪纸** (RL): state=`clean`, best=#papercutting, videoCount=28,432, clean_terms=2, noisy_terms=1
- **中国传统木结构建筑营造技艺** (RL): state=`clean`, best=#timberframe, videoCount=16,173, clean_terms=2, noisy_terms=0
- **中国传统制茶技艺及其相关习俗** (RL): state=`clean`, best=#gongfutea, videoCount=16,140, clean_terms=2, noisy_terms=4
- **妈祖信俗** (RL): state=`clean`, best=#mazu, videoCount=13,995, clean_terms=2, noisy_terms=0
- **古琴艺术** (RL): state=`clean`, best=#guqin, videoCount=9,346, clean_terms=2, noisy_terms=0
- **端午节** (RL): state=`clean`, best=#端午节, videoCount=8,891, clean_terms=3, noisy_terms=2
- **京剧** (RL): state=`clean`, best=#pekingopera, videoCount=7,633, clean_terms=3, noisy_terms=0
- **中医针灸** (RL): state=`clean`, best=#针灸, videoCount=7,351, clean_terms=1, noisy_terms=1
- **新疆维吾尔木卡姆艺术** (RL): state=`clean`, best=#muqam, videoCount=7,108, clean_terms=3, noisy_terms=0

## 3. 只有 noisy hashtag 可用的项目

- 暂无。

## 4. hashtag 规模不可得项目

- 暂无。

## 5. 使用注意

- `scale_data_state=clean` 也不代表完全无噪声，只代表当前 hashtag 相对专指。
- `scale_data_state=noisy` 表示只有泛词/撞词规模可用，后续分层要降权或人工说明。
- `unavailable` 不能强行填 0；它表示没有可用 hashtag 规模源，本身可作为低存在感线索。
- 下一步：与 relevance-aware reach 合成 `存量 × 触达` 草表。

