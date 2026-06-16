# YouTube Y2 深采候选清单（不采集，仅排优先级）

> 生成时间：2026-06-16 22:52:58  
> 输入：YouTube 3页扩采 + YouTube relevance-aware 触达 + TikTok 存量×触达草表 + TikTok 人工核查优先项目。

## 1. 原则

- 本阶段 **不采集**，只生成深采候选与优先级。
- 不全补 56 个 `sample_limit_reached`；只对结论关键词补。
- P0 结论关键 / YouTube 明确高触达词：建议补到 10 页；到 10 页仍有 nextPageToken 才标 `ceiling_capped_500`。
- 噪声诊断词：建议补到 5 页，够判断 raw 噪声结构，不补满。
- 5 个已自然采空词：不补，保留为跨平台低可见性候选。
- TikTok 相关人工核查未回流前，依赖 TikTok 结论的深采候选标为 wait，不硬采。
- Y5 跨平台对比中，**存量轴只能定性对比**：TikTok 是 hashtag videoCount，YouTube 是采集状态，两者不是同一量纲，不能数值比大小；触达轴使用两边 relevance-aware likely 口径。

## 2. 候选分布

- `P0_youtube_high_reach_deepcrawl_now`: 13
- `P0_wait_tiktok_manual_for_deepcrawl`: 35
- `P1_noise_probe_5_pages`: 2
- `P1_possible_reach_deepcrawl_after_review`: 3
- `P2_hold_exhausted_cross_platform_low`: 5
- `P3_no_deepcrawl_now`: 3

动作分布：

- `deepcrawl_to_10_pages`: 13
- `wait_tiktok_manual_then_decide`: 35
- `deepcrawl_to_5_pages_for_noise_diagnosis`: 2
- `review_then_maybe_deepcrawl`: 3
- `hold_no_deepcrawl`: 5
- `no_deepcrawl_now`: 3

## 3. 可先推进的 YouTube 高触达 P0

- #1 **春节** — `Chinese New Year`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=340,297,128, tiktok=stock_high__reach_high / P3_normal
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #2 **中国蚕桑丝织技艺** — `Chinese silk sericulture`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=240,638,320, tiktok=stock_low__reach_low / P2_noise_risk
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #3 **古琴艺术** — `Chinese Guqin`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=140,768,008, tiktok=stock_low__reach_high / P1_low_stock_high_reach
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #4 **太极拳** — `Tai Chi`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=87,245,248, tiktok=stock_high__reach_high / P3_normal
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #5 **古琴艺术** — `Guqin`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=83,874,855, tiktok=stock_low__reach_high / P1_low_stock_high_reach
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #6 **中国木活字印刷术** — `Chinese wooden movable type`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=79,502,559, tiktok=stock_low__reach_high / P0_noise_or_tier_drop
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #7 **太极拳** — `Taijiquan`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=41,367,287, tiktok=stock_high__reach_high / P3_normal
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #8 **中国篆刻** — `seal engraving`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=high_20_40pct_reach, term_likely_view=38,086,149, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #9 **妈祖信俗** — `Mazu`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=top_20pct_reach, term_likely_view=36,066,888, tiktok=stock_high__reach_low / P0_stock_high_reach_low
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #10 **中国传统制茶技艺及其相关习俗** — `Chinese tea ceremony`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=high_20_40pct_reach, term_likely_view=30,363,057, tiktok=stock_high__reach_high / P2_noise_risk
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #11 **中国书法** — `Chinese calligraphy`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=high_20_40pct_reach, term_likely_view=25,339,037, tiktok=stock_high__reach_high / P3_normal
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #12 **粤剧** — `Cantonese opera`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=high_20_40pct_reach, term_likely_view=25,293,544, tiktok=stock_low__reach_low / P2_noise_risk
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。
- #13 **中国篆刻** — `Chinese seal engraving`: action=deepcrawl_to_10_pages, pages=to_10_pages, yt_tier=high_20_40pct_reach, term_likely_view=20,620,221, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
  - reason: YouTube 自身 likely 高触达且噪声低；不必等待 TikTok 人工回流，可先补到 10 页验证触达上限。

## 4. 等 TikTok 人工回流再定的 P0

- #14 **中国木拱桥传统营造技艺** — `Chinese wooden arch bridge`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=top_20pct_reach, term_likely_view=60,349,388, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #15 **蒙古族呼麦** — `Khoomei`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=high_20_40pct_reach, term_likely_view=47,515,297, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #16 **蒙古族呼麦** — `Khoomei China`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=high_20_40pct_reach, term_likely_view=39,950,316, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #17 **蒙古族长调民歌** — `Urtiin Duu`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=top_20pct_reach, term_likely_view=24,870,667, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #18 **中国雕版印刷技艺** — `Chinese block printing`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=high_20_40pct_reach, term_likely_view=20,306,404, tiktok=stock_high__reach_low / P0_stock_high_reach_low
- #19 **中国雕版印刷技艺** — `Chinese woodblock printing`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=high_20_40pct_reach, term_likely_view=20,053,074, tiktok=stock_high__reach_low / P0_stock_high_reach_low
- #20 **京剧** — `Peking opera`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=high_20_40pct_reach, term_likely_view=14,971,584, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #21 **宣纸传统制作技艺** — `Xuan paper making`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=high_20_40pct_reach, term_likely_view=12,328,419, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #22 **花儿** — `Hua'er`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=11,264,577, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #23 **麦西热甫** — `Meshrep`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=6,455,423, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #24 **中医针灸** — `acupuncture moxibustion`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=5,712,974, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #25 **昆曲** — `Kunqu opera`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=3,315,499, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #26 **中国皮影戏** — `Chinese shadow puppetry`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=2,551,668, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #27 **藏戏** — `Tibetan opera`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=2,440,978, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #28 **赫哲族伊玛堪** — `Yimakan`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=2,014,472, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #29 **中国珠算** — `Chinese abacus`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=1,842,282, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #30 **中国传统木结构建筑营造技艺** — `Chinese wooden architecture`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=1,592,178, tiktok=stock_high__reach_low / P0_stock_high_reach_low
- #31 **二十四节气** — `24 solar terms`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=1,142,003, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #32 **中国水密隔舱福船制造技艺** — `Chinese junk watertight bulkhead`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=1,126,767, tiktok=stock_low__reach_high / P1_low_stock_high_reach
- #33 **格萨(斯)尔史诗传统** — `Chinese Gesar epic`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=760,949, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #34 **新疆维吾尔木卡姆艺术** — `Uyghur Muqam`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=686,528, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #35 **中国传统木结构建筑营造技艺** — `Chinese timber architecture`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=215,697, tiktok=stock_high__reach_low / P0_stock_high_reach_low
- #36 **黎族传统纺染织绣技艺** — `Li brocade`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=198,602, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #37 **南音** — `Nanyin music`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=182,999, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #38 **福建木偶戏后继人才培养计划** — `budaixi`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=130,956, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #39 **西安鼓乐** — `Xi'an drum music`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=120,770, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #40 **黎族传统纺染织绣技艺** — `Li textile`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=118,987, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #41 **送王船** — `Wangchuan ceremony`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=113,466, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #42 **花儿** — `Hua'er Gansu`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=72,048, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #43 **藏医药浴法** — `Tibetan medicine bath`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=bottom_10pct_reach, term_likely_view=55,636, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #44 **花儿** — `Hua'er folk song`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=middle_40_70pct_reach, term_likely_view=45,815, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #45 **侗族大歌** — `Dong grand song`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=bottom_10pct_reach, term_likely_view=37,948, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #46 **中国朝鲜族农乐舞** — `Farmers' dance of China's Korean ethnic group`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=bottom_10pct_reach, term_likely_view=14,930, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #47 **热贡艺术** — `Thangka`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=bottom_10pct_reach, term_likely_view=10,170, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
- #48 **福建木偶戏后继人才培养计划** — `Fujian puppetry`: action=wait_tiktok_manual_then_decide, pages=defer, yt_tier=lower_70_90pct_reach, term_likely_view=8,529, tiktok=stock_low__reach_low / P0_noise_or_tier_drop

## 5. 噪声诊断 P1（建议只补到5页）

- #49 **玛纳斯** — `Chinese Manas epic`: action=deepcrawl_to_5_pages_for_noise_diagnosis, pages=to_5_pages, yt_tier=lower_70_90pct_reach, term_likely_view=113,260, tiktok=stock_high__reach_high / P2_noise_risk
- #50 **羌年** — `Qiang New Year`: action=deepcrawl_to_5_pages_for_noise_diagnosis, pages=to_5_pages, yt_tier=bottom_10pct_reach, term_likely_view=40,650, tiktok=stock_low__reach_low / P2_noise_risk

## 6. 已自然采空：保留，不补采

- #54 **蒙古族长调民歌** — `Mongolian long song`: action=hold_no_deepcrawl, pages=none, yt_tier=top_20pct_reach, term_likely_view=10,480,182, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
  - reason: 3页内自然采空；与 TikTok 低存量方向一致，先保留为跨平台低可见性发现，不补采。
- #55 **蒙古族呼麦** — `Khoomei throat singing`: action=hold_no_deepcrawl, pages=none, yt_tier=high_20_40pct_reach, term_likely_view=4,831,403, tiktok=stock_low__reach_high / P1_low_stock_high_reach
  - reason: 3页内自然采空；与 TikTok 低存量方向一致，先保留为跨平台低可见性发现，不补采。
- #56 **龙泉青瓷传统烧制技艺** — `Longquan celadon`: action=hold_no_deepcrawl, pages=none, yt_tier=middle_40_70pct_reach, term_likely_view=3,191,221, tiktok=stock_low__reach_high / P1_low_stock_high_reach
  - reason: 3页内自然采空；与 TikTok 低存量方向一致，先保留为跨平台低可见性发现，不补采。
- #57 **侗族大歌** — `Kgal laox`: action=hold_no_deepcrawl, pages=none, yt_tier=bottom_10pct_reach, term_likely_view=28,181, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
  - reason: 3页内自然采空；与 TikTok 低存量方向一致，先保留为跨平台低可见性发现，不补采。
- #58 **热贡艺术** — `Chinese Regong art`: action=hold_no_deepcrawl, pages=none, yt_tier=bottom_10pct_reach, term_likely_view=0, tiktok=stock_low__reach_low / P0_noise_or_tier_drop
  - reason: 3页内自然采空；与 TikTok 低存量方向一致，先保留为跨平台低可见性发现，不补采。

## 7. 下一步

1. 云白先看 `P0_youtube_high_reach_deepcrawl_now` 是否认可；认可后可直接进入 Y3 对这些词补到 10 页。
2. `P0_wait_tiktok_manual_for_deepcrawl` 等 TikTok 321 条人工表回流后再筛。
3. `P1_noise_probe_5_pages` 只为噪声结构验证，不为了追求完整量。
