# 二测 hashtag 词表修复建议

## 说明

- `sample`：从二测视频真实 hashtag 反推。
- `common_english`：不取自样本的常识英文候选，用于降低自我强化偏差。
- 泛词一律不进入 `hashtag_terms` 建议；判定标准是该 tag 单独拿出来是否指向具体非遗。
- `is_generic_tag=true`：泛词/平台词，仅保留在 CSV 供审计，不进入 Markdown 候选摘要。
- `disabled_hashtag_terms`：本轮 challengeID resolve 失败，备查，不建议继续作为主 hashtag term。
- `language`：发布者标签语言维度，可用于画像。

## challengeID 失败与低存在感线索

- 赫哲族伊玛堪: disabled_hashtag_terms=yimakan, 伊玛堪; search_rows=116, search_likely=8, search_non_low=30
- 麦西热甫: disabled_hashtag_terms=mäshräp, uyghur, 麦西热甫; search_rows=119, search_likely=19, search_non_low=52
- 中国水密隔舱福船制造技艺: disabled_hashtag_terms=junk, watertight, 水密隔舱; search_rows=145, search_likely=14, search_non_low=78
- 黎族传统纺染织绣技艺: disabled_hashtag_terms=纺染织绣; search_rows=174, search_likely=37, search_non_low=70
- 羌年: disabled_hashtag_terms=qiang, 羌年; search_rows=110, search_likely=32, search_non_low=59
- 西安鼓乐: disabled_hashtag_terms=xianwind; search_rows=116, search_likely=24, search_non_low=52
- 中国蚕桑丝织技艺: disabled_hashtag_terms=silk, 缫丝, 蚕桑; search_rows=194, search_likely=60, search_non_low=133
- 格萨(斯)尔史诗传统: disabled_hashtag_terms=epic, 格萨; search_rows=114, search_likely=10, search_non_low=56
- 蒙古族呼麦: disabled_hashtag_terms=höömii; search_rows=113, search_likely=16, search_non_low=57
- 花儿: disabled_hashtag_terms=northwestchinasong; search_rows=90, search_likely=21, search_non_low=37
- 中国朝鲜族农乐舞: disabled_hashtag_terms=农乐舞, 朝鲜族; search_rows=118, search_likely=18, search_non_low=55

## 各项目候选摘要

### 1. 春节
- 当前 hashtag_terms: 春节, 新年, 过年, chinesenewyear, lunarnewyear, cny
- 当前词表中可保留候选: chinesenewyear(en), lunarnewyear(en), cny(en), 春节(zh)
- 常识英文可解析候选: 无

### 2. 中国传统制茶技艺及其相关习俗
- 当前 hashtag_terms: gongfutea, 茶艺, 功夫茶, 炒茶, 制茶, 揉捻
- 当前词表中可保留候选: gongfutea(en)
- 常识英文可解析候选: 无

### 3. 太极拳
- 当前 hashtag_terms: 太极, 太极拳, taichi, taijiquan
- 当前词表中可保留候选: taichi(en), 太极(zh), 太极拳(zh), taijiquan(en)
- 常识英文可解析候选: 无

### 4. 送王船
- 当前 hashtag_terms: 送王船, 王船, ongchun, wangchuan, wangkang, boatburning
- 当前词表中可保留候选: wangkang(en), 送王船(zh)
- 常识英文可解析候选: 无

### 5. 藏医药浴法
- 当前 hashtag_terms: 藏医, 药浴, sowarigpa, tibetanmedicine, tibetanhealing
- 当前词表中可保留候选: sowarigpa(en)
- 常识英文可解析候选: 无

### 6. 二十四节气
- 当前 hashtag_terms: 二十四节气, 节气, solarterms, 24solarterms, chinesecalendar
- 当前词表中可保留候选: 二十四节气(zh), chinesecalendar(en), 24solarterms(en)
- 常识英文可解析候选: 无

### 7. 中国珠算
- 当前 hashtag_terms: 珠算, 算盘, abacus, zhusuan
- 当前词表中可保留候选: abacus(en)
- 常识英文可解析候选: 无

### 8. 福建木偶戏
- 当前 hashtag_terms: budaixi, 布袋戏, 掌中戏
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 9. 赫哲族伊玛堪
- 当前 hashtag_terms: 赫哲, 伊玛堪, hezhe, yimakan
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 10. 中国皮影戏
- 当前 hashtag_terms: 皮影戏, 皮影, piying
- 当前词表中可保留候选: 皮影戏(zh)
- 常识英文可解析候选: 无

### 11. 麦西热甫
- 当前 hashtag_terms: 麦西热甫, meshrep, mäshräp, uyghur
- 当前词表中可保留候选: 无
- 常识英文可解析候选: meshrep, mashrap, uyghurmeshrep

### 12. 中国水密隔舱福船制造技艺
- 当前 hashtag_terms: 水密隔舱, 福船, watertight, junk, fuchuan
- 当前词表中可保留候选: 无
- 常识英文可解析候选: fuchuan, junkboat, chinesejunk

### 13. 中国木活字印刷术
- 当前 hashtag_terms: 木活字, 活字, movabletype, woodentype, printing
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 14. 京剧
- 当前 hashtag_terms: 京剧, pekingopera, beijingopera, chineseopera
- 当前词表中可保留候选: chineseopera(en), pekingopera(en), 京剧(zh)
- 常识英文可解析候选: 无

### 15. 中医针灸
- 当前 hashtag_terms: 针灸, acupuncture, tcm, chinesemedicine
- 当前词表中可保留候选: tcm(en), acupuncture(en), 针灸(zh)
- 常识英文可解析候选: 无

### 16. 黎族传统纺染织绣技艺
- 当前 hashtag_terms: 黎锦, 黎族织锦, 纺染织绣, 黎族
- 当前词表中可保留候选: 无
- 常识英文可解析候选: librocade, litextile, litextiles

### 17. 中国木拱桥传统营造技艺
- 当前 hashtag_terms: 木拱桥, 廊桥, woodenarchbridge, coveredbridge
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 18. 羌年
- 当前 hashtag_terms: 羌年, 羌族, qiangnewyear, qiang
- 当前词表中可保留候选: 无
- 常识英文可解析候选: qiangnewyear, qiangculture

### 19. 侗族大歌
- 当前 hashtag_terms: 侗族, 侗族大歌, kamgrandchoir, dongchorus
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 20. 西安鼓乐
- 当前 hashtag_terms: 西安鼓乐, 鼓乐, xianwind, drummusic
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 21. 中国蚕桑丝织技艺
- 当前 hashtag_terms: silk, 丝绸, sericulture, 蚕桑, 缫丝
- 当前词表中可保留候选: 无
- 常识英文可解析候选: sericulture, silkreeling, silkweaving, silkcraft, chinesesilk

### 22. 南音
- 当前 hashtag_terms: Nanyin, 南音, 泉州南音
- 当前词表中可保留候选: nanyin(en), 南音(zh)
- 常识英文可解析候选: 无

### 23. 南京云锦织造技艺
- 当前 hashtag_terms: 云锦, 南京云锦, yunjin, nanjingbrocade
- 当前词表中可保留候选: yunjin(en)
- 常识英文可解析候选: 无

### 24. 宣纸传统制作技艺
- 当前 hashtag_terms: 宣纸, xuanpaper, ricepaper, papermaking
- 当前词表中可保留候选: xuanpaper(en)
- 常识英文可解析候选: 无

### 25. 粤剧
- 当前 hashtag_terms: cantoneseopera, 粤剧
- 当前词表中可保留候选: cantoneseopera(en), 粤剧(zh)
- 常识英文可解析候选: 无

### 26. 格萨(斯)尔史诗传统
- 当前 hashtag_terms: 格萨尔, 格萨, gesar, epic
- 当前词表中可保留候选: 无
- 常识英文可解析候选: gesar, kinggesar, epicofgesar, tibetanepic

### 27. 龙泉青瓷传统烧制技艺
- 当前 hashtag_terms: 龙泉, 青瓷, longquanceladon, celadon
- 当前词表中可保留候选: longquanceladon(en)
- 常识英文可解析候选: 无

### 28. 热贡艺术
- 当前 hashtag_terms: 热贡, 唐卡, regong, thangka
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无

### 29. 藏戏
- 当前 hashtag_terms: 藏戏, tibetanopera, lhamo, achelhamo
- 当前词表中可保留候选: tibetanopera(en)
- 常识英文可解析候选: 无

### 30. 玛纳斯
- 当前 hashtag_terms: 玛纳斯, manas, kyrgyz
- 当前词表中可保留候选: manas(en)
- 常识英文可解析候选: 无

### 31. 蒙古族呼麦
- 当前 hashtag_terms: khoomei, höömii, 呼麦
- 当前词表中可保留候选: khoomei(en)
- 常识英文可解析候选: khoomei, hoomei, throatsinging, mongolianthroatsinging

### 32. 花儿
- 当前 hashtag_terms: 花儿, huaer, northwestchinasong
- 当前词表中可保留候选: huaer(en)
- 常识英文可解析候选: huaer

### 33. 中国朝鲜族农乐舞
- 当前 hashtag_terms: 农乐舞, 朝鲜族, nongak, farmersdance
- 当前词表中可保留候选: 无
- 常识英文可解析候选: nongak, farmersdance, koreanchinesedance, chaoxianzu

### 34. 中国书法
- 当前 hashtag_terms: 书法, calligraphy, shufa, chineseink
- 当前词表中可保留候选: calligraphy(en), 书法(zh), shufa(en)
- 常识英文可解析候选: 无

### 35. 中国篆刻
- 当前 hashtag_terms: 篆刻, 印章, sealcarving, chineseseal
- 当前词表中可保留候选: sealcarving(en), 篆刻(zh), chineseseal(en)
- 常识英文可解析候选: 无

### 36. 中国剪纸
- 当前 hashtag_terms: 剪纸, papercut, papercutting, chinesepapercut
- 当前词表中可保留候选: papercut(en), papercutting(en)
- 常识英文可解析候选: 无

### 37. 中国传统木结构建筑营造技艺
- 当前 hashtag_terms: 斗拱, 古建, 木结构, timberframe, chinesearchitecture
- 当前词表中可保留候选: timberframe(en)
- 常识英文可解析候选: 无

### 38. 端午节
- 当前 hashtag_terms: 端午, 端午节, dragonboat, duanwu, zongzi
- 当前词表中可保留候选: duanwu(en)
- 常识英文可解析候选: 无

### 39. 妈祖信俗
- 当前 hashtag_terms: 妈祖, mazu, seagoddess
- 当前词表中可保留候选: mazu(en), 妈祖(zh), seagoddess(en)
- 常识英文可解析候选: 无

### 40. 中国雕版印刷技艺
- 当前 hashtag_terms: 雕版, 雕版印刷, blockprinting, woodblock
- 当前词表中可保留候选: blockprinting(en), woodblock(en)
- 常识英文可解析候选: 无

### 41. 昆曲
- 当前 hashtag_terms: 昆曲, kunqu, kunopera, kunquopera
- 当前词表中可保留候选: 昆曲(zh)
- 常识英文可解析候选: 无

### 42. 古琴艺术
- 当前 hashtag_terms: 古琴, guqin, chinesezither
- 当前词表中可保留候选: guqin(en), 古琴(zh), chinesezither(en)
- 常识英文可解析候选: 无

### 43. 新疆维吾尔木卡姆艺术
- 当前 hashtag_terms: 木卡姆, muqam, uyghurmuqam
- 当前词表中可保留候选: muqam(en)
- 常识英文可解析候选: 无

### 44. 蒙古族长调民歌
- 当前 hashtag_terms: 长调, longsong, urtiinduu, mongoliansong
- 当前词表中可保留候选: 无
- 常识英文可解析候选: 无
