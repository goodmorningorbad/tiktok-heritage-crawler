# 二测 hashtag 词表修复建议

## 说明

- `sample`：从二测视频真实 hashtag 反推。
- `common_english`：不取自样本的常识英文候选，用于降低自我强化偏差。
- `disabled_hashtag_terms`：本轮 challengeID resolve 失败，备查，不建议继续作为主 hashtag term。
- `language`：发布者标签语言维度，可用于画像。

## challengeID 失败与低存在感线索

- 赫哲族伊玛堪: disabled_hashtag_terms=yimakan, 伊玛堪; search_rows=116, search_likely=8, search_non_low=30
- 麦西热甫: disabled_hashtag_terms=mäshräp, 麦西热甫; search_rows=119, search_likely=19, search_non_low=52
- 中国水密隔舱福船制造技艺: disabled_hashtag_terms=水密隔舱; search_rows=145, search_likely=14, search_non_low=78
- 黎族传统纺染织绣技艺: disabled_hashtag_terms=纺染织绣; search_rows=174, search_likely=37, search_non_low=70
- 羌年: disabled_hashtag_terms=羌年; search_rows=110, search_likely=32, search_non_low=59
- 西安鼓乐: disabled_hashtag_terms=drummusic, xianwind, 西安鼓乐, 鼓乐; search_rows=116, search_likely=24, search_non_low=52
- 中国蚕桑丝织技艺: disabled_hashtag_terms=sericulture, silk, 丝绸, 缫丝, 蚕桑; search_rows=194, search_likely=60, search_non_low=133
- 格萨(斯)尔史诗传统: disabled_hashtag_terms=epic, gesar, 格萨, 格萨尔; search_rows=114, search_likely=10, search_non_low=56
- 蒙古族呼麦: disabled_hashtag_terms=höömii, khoomei, 呼麦; search_rows=113, search_likely=16, search_non_low=57
- 花儿: disabled_hashtag_terms=huaer, northwestchinasong, 花儿; search_rows=90, search_likely=21, search_non_low=37
- 中国朝鲜族农乐舞: disabled_hashtag_terms=farmersdance, nongak, 农乐舞, 朝鲜族; search_rows=118, search_likely=18, search_non_low=55

## 各项目候选摘要

### 1. 春节
- 当前 hashtag_terms: 春节, 新年, 过年, chinesenewyear, lunarnewyear, cny
- 样本可解析候选: chinesenewyear(en), lunarnewyear(en), cny(en), china(en), chinese(en), gongxifacai(en), 春节(zh), springfestival(en)
- 常识英文可解析候选: spring, festival, social, celebration, year, chineseculture, intangibleheritage, unescoheritage

### 2. 中国传统制茶技艺及其相关习俗
- 当前 hashtag_terms: gongfutea, 茶艺, 功夫茶, 炒茶, 制茶, 揉捻
- 样本可解析候选: tea(en), gongfutea(en), chinesetea(en), teaceremony(en), 召唤茶友(zh), 茶(zh), china(en), tealover(en)
- 常识英文可解析候选: processing, techniques, associated, social, chineseculture, intangibleheritage, unescoheritage

### 3. 太极拳
- 当前 hashtag_terms: 太极, 太极拳, taichi, taijiquan
- 样本可解析候选: taichi(en), 太极(zh), kungfu(en), 太极拳(zh), taijiquan(en), taiji(en), wushu(en), martialarts(en)
- 常识英文可解析候选: taijiquan, chineseculture, intangibleheritage, unescoheritage

### 4. 送王船
- 当前 hashtag_terms: 送王船, 王船, ongchun, wangchuan, wangkang, boatburning
- 样本可解析候选: wangkang(en), wangchuran(en), fire(en), wangochun(en), wangchuran王楚然(mixed), lookism(en), 送王船(zh), 王楚然(zh)
- 常识英文可解析候选: chun, wangchuan, wangkang, ceremony, rituals, related, chineseculture, intangibleheritage

### 5. 藏医药浴法
- 当前 hashtag_terms: 藏医, 药浴, sowarigpa, tibetanmedicine, tibetanhealing
- 样本可解析候选: tibetanmedicine(en), sowarigpa(en), tibetan(en), holistichealth(en), tibet(en), ancientwisdom(en), healing(en), tcm(en)
- 常识英文可解析候选: medicinal, bathing, sowa, rigpa, concerning, life, chineseculture, intangibleheritage

### 6. 二十四节气
- 当前 hashtag_terms: 二十四节气, 节气, solarterms, 24solarterms, chinesecalendar
- 样本可解析候选: chineseculture(en), chinese(en), 二十四节气(zh), china(en), chinesecalendar(en), 24solarterms(en), chinesenewyear(en), 习近平(zh)
- 常识英文可解析候选: twenty, four, solar, terms, time, developed, chineseculture, intangibleheritage

### 7. 中国珠算
- 当前 hashtag_terms: 珠算, 算盘, abacus, zhusuan
- 样本可解析候选: abacus(en), chenzhuoxuan(en), china(en), mentalmath(en), 陈卓璇(zh), zhuyuan(en), math(en), zhuxudan(en)
- 常识英文可解析候选: zhusuan, mathematical, calculation, through, abacus, chineseculture, intangibleheritage, unescoheritage

### 8. 福建木偶戏
- 当前 hashtag_terms: budaixi, 布袋戏, 掌中戏
- 样本可解析候选: puppetry(en), china(en), puppet(en), puppetshow(en), chinese(en), fujian(en), quanzhou(en), art(en)
- 常识英文可解析候选: strategy, training, coming, generations, fujian, puppetry, chineseculture, intangibleheritage

### 9. 赫哲族伊玛堪
- 当前 hashtag_terms: 赫哲, 伊玛堪, hezhe, yimakan
- 样本可解析候选: yamaken(en), mylittlemonster(en), zhanglinghe(en), xuhuong(en), anime(en), จางหลิงเฮ่อ(other), tianxiwei(en), 田作之赫(zh)
- 常识英文可解析候选: hezhe, chinesefolksong, oraltradition, storytelling, chineseculture, intangibleheritage, unescoheritage

### 10. 中国皮影戏
- 当前 hashtag_terms: 皮影戏, 皮影, piying
- 样本可解析候选: china(en), chineseculture(en), shadowpuppetry(en), intangibleculturalheritage(en), 皮影戏(zh), culture(en), chinese(en), 非遗(zh)
- 常识英文可解析候选: shadow, puppetry, chineseculture, intangibleheritage, unescoheritage

### 11. 麦西热甫
- 当前 hashtag_terms: 麦西热甫, meshrep, mäshräp, uyghur
- 样本可解析候选: uyghur(en), xinjiang(en), china(en), dance(en), culture(en), headspa(en), mash(en), chinese(en)
- 常识英文可解析候选: meshrep, mashrap, uyghurmeshrep, uyghurdance, uyghurculture, chineseculture, intangibleheritage, unescoheritage

### 12. 中国水密隔舱福船制造技艺
- 当前 hashtag_terms: 水密隔舱, 福船, watertight, junk, fuchuan
- 样本可解析候选: china(en), junkremoval(en), watertight(en), fuxuan(en), junk(en), HonkaiStarRail(en), junkjournal(en), hsr(en)
- 常识英文可解析候选: fuchuan, junkboat, chinesejunk, shipbuilding, watertight, bulkhead, technology, junks

### 13. 中国木活字印刷术
- 当前 hashtag_terms: 木活字, 活字, movabletype, woodentype, printing
- 样本可解析候选: wood(en), Science(en), printing(en), popular(en), china(en), calligraphy(en), 3dprinting(en), art(en)
- 常识英文可解析候选: wooden, movable, type, printing, chineseculture, intangibleheritage, unescoheritage

### 14. 京剧
- 当前 hashtag_terms: 京剧, pekingopera, beijingopera, chineseopera
- 样本可解析候选: chineseopera(en), pekingopera(en), 京剧(zh), chinese(en), chineseculture(en), china(en), intangibleculturalheritage(en), 戏曲(zh)
- 常识英文可解析候选: peking, opera, chineseculture, intangibleheritage, unescoheritage

### 15. 中医针灸
- 当前 hashtag_terms: 针灸, acupuncture, tcm, chinesemedicine
- 样本可解析候选: tcm(en), acupuncture(en), chinesemedicine(en), traditionalchinesemedicine(en), 中医(zh), 针灸(zh), health(en), acupressure(en)
- 常识英文可解析候选: acupuncture, moxibustion, medicine, chineseculture, intangibleheritage, unescoheritage

### 16. 黎族传统纺染织绣技艺
- 当前 hashtag_terms: 黎锦, 黎族织锦, 纺染织绣, 黎族
- 样本可解析候选: hainan(en), china(en), handmade(en), textile(en), chineseculture(en), fabric(en), librocade(en), traditionalart(en)
- 常识英文可解析候选: librocade, litextile, litextiles, hainanculture, traditionalweaving, textile, techniques, spinning

### 17. 中国木拱桥传统营造技艺
- 当前 hashtag_terms: 木拱桥, 廊桥, woodenarchbridge, coveredbridge
- 样本可解析候选: coveredbridge(en), bridge(en), engineering(en), Soccer(en), History(en), architecture(en), futbol(en), wood(en)
- 常识英文可解析候选: design, building, wooden, arch, bridges, chineseculture, intangibleheritage, unescoheritage

### 18. 羌年
- 当前 hashtag_terms: 羌年, 羌族, qiangnewyear, qiang
- 样本可解析候选: china(en), 太平年(zh), chinese(en), 中国(zh), chinatravel(en), qiang(en), 历史(zh), zhaolusi(en)
- 常识英文可解析候选: qiangnewyear, qiangculture, qiangpeople, chinesenewyear, ethnicfestival, qiang, year, festival

### 19. 侗族大歌
- 当前 hashtag_terms: 侗族, 侗族大歌, kamgrandchoir, dongchorus
- 样本可解析候选: choir(en), china(en), 侗族(zh), music(en), showchoir(en), kpop(en), dongpeople(en), chorus(en)
- 常识英文可解析候选: ethnic, chineseculture, intangibleheritage, unescoheritage

### 20. 西安鼓乐
- 当前 hashtag_terms: 西安鼓乐, 鼓乐, xianwind, drummusic
- 样本可解析候选: china(en), chinatravel(en), music(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 21. 中国蚕桑丝织技艺
- 当前 hashtag_terms: silk, 丝绸, sericulture, 蚕桑, 缫丝
- 样本可解析候选: china(en), chineseculture(en), handmade(en), weaving(en), culture(en), chinese(en), handwork(en), LearnOnTikTok(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 22. 南音
- 当前 hashtag_terms: Nanyin, 南音, 泉州南音
- 样本可解析候选: fujian(en), fyppppppppppppppppppppppp(en), music(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 23. 南京云锦织造技艺
- 当前 hashtag_terms: 云锦, 南京云锦, yunjin, nanjingbrocade
- 样本可解析候选: china(en), kpop(en), History(en), chinese(en), chinatravel(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 24. 宣纸传统制作技艺
- 当前 hashtag_terms: 宣纸, xuanpaper, ricepaper, papermaking
- 样本可解析候选: china(en), chinese(en), chineseculture(en), handmade(en), handwork(en), asmr(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 25. 粤剧
- 当前 hashtag_terms: cantoneseopera, 粤剧
- 样本可解析候选: chineseopera(en), china(en), chinese(en), chineseculture(en), opera(en), culture(en), intangibleculturalheritage(en)
- 常识英文可解析候选: opera, chineseculture, intangibleheritage, unescoheritage

### 26. 格萨(斯)尔史诗传统
- 当前 hashtag_terms: 格萨尔, 格萨, gesar, epic
- 样本可解析候选: china(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 27. 龙泉青瓷传统烧制技艺
- 当前 hashtag_terms: 龙泉, 青瓷, longquanceladon, celadon
- 样本可解析候选: handmade(en), china(en), intangibleculturalheritage(en), xuhuong(en)
- 常识英文可解析候选: technology, chineseculture, intangibleheritage, unescoheritage

### 28. 热贡艺术
- 当前 hashtag_terms: 热贡, 唐卡, regong, thangka
- 样本可解析候选: buddhism(en), tibet(en), tibetan(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 29. 藏戏
- 当前 hashtag_terms: 藏戏, tibetanopera, lhamo, achelhamo
- 样本可解析候选: tibet(en), tibetan(en), opera(en), culture(en), china(en), fyppppppppppppppppppppppp(en), culturalheritage(en)
- 常识英文可解析候选: opera, chineseculture, intangibleheritage, unescoheritage

### 30. 玛纳斯
- 当前 hashtag_terms: 玛纳斯, manas, kyrgyz
- 样本可解析候选: china(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 31. 蒙古族呼麦
- 当前 hashtag_terms: khoomei, höömii, 呼麦
- 样本可解析候选: china(en), chinese(en), singing(en), music(en)
- 常识英文可解析候选: singing, chineseculture, intangibleheritage, unescoheritage

### 32. 花儿
- 当前 hashtag_terms: 花儿, huaer, northwestchinasong
- 样本可解析候选: china(en), xuhuong(en), music(en)
- 常识英文可解析候选: chinesefolksong, chineseculture, intangibleheritage, unescoheritage

### 33. 中国朝鲜族农乐舞
- 当前 hashtag_terms: 农乐舞, 朝鲜族, nongak, farmersdance
- 样本可解析候选: dance(en), 中国(zh), music(en)
- 常识英文可解析候选: dance, ethnic, chineseculture, intangibleheritage, unescoheritage

### 34. 中国书法
- 当前 hashtag_terms: 书法, calligraphy, shufa, chineseink
- 样本可解析候选: calligraphy(en), 书法(zh), art(en), chinese(en), china(en)
- 常识英文可解析候选: calligraphy, chineseculture, intangibleheritage, unescoheritage

### 35. 中国篆刻
- 当前 hashtag_terms: 篆刻, 印章, sealcarving, chineseseal
- 样本可解析候选: handmade(en), asmr(en), intangibleculturalheritage(en), chinese(en), art(en), chineseculture(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 36. 中国剪纸
- 当前 hashtag_terms: 剪纸, papercut, papercutting, chinesepapercut
- 样本可解析候选: art(en), asmr(en), chinese(en), china(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 37. 中国传统木结构建筑营造技艺
- 当前 hashtag_terms: 斗拱, 古建, 木结构, timberframe, chinesearchitecture
- 样本可解析候选: architecture(en), china(en), chinatravel(en), History(en), LearnOnTikTok(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 38. 端午节
- 当前 hashtag_terms: 端午, 端午节, dragonboat, duanwu, zongzi
- 样本可解析候选: zhaolusi(en), china(en), chinese(en)
- 常识英文可解析候选: boat, festival, chineseculture, intangibleheritage, unescoheritage

### 39. 妈祖信俗
- 当前 hashtag_terms: 妈祖, mazu, seagoddess
- 样本可解析候选: china(en), chineseculture(en), 春节(zh)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage

### 40. 中国雕版印刷技艺
- 当前 hashtag_terms: 雕版, 雕版印刷, blockprinting, woodblock
- 样本可解析候选: art(en)
- 常识英文可解析候选: printing, chineseculture, intangibleheritage, unescoheritage

### 41. 昆曲
- 当前 hashtag_terms: 昆曲, kunqu, kunopera, kunquopera
- 样本可解析候选: opera(en), 戏曲(zh), chineseopera(en), 京剧(zh), kinhkich(en), pekingopera(en)
- 常识英文可解析候选: opera, chineseculture, intangibleheritage, unescoheritage

### 42. 古琴艺术
- 当前 hashtag_terms: 古琴, guqin, chinesezither
- 样本可解析候选: music(en), chineseculture(en), chinese(en), china(en), 中国(zh)
- 常识英文可解析候选: music, chineseculture, intangibleheritage, unescoheritage

### 43. 新疆维吾尔木卡姆艺术
- 当前 hashtag_terms: 木卡姆, muqam, uyghurmuqam
- 样本可解析候选: uyghur(en), xinjiang(en), music(en), dance(en), chineseculture(en), china(en), intangibleculturalheritage(en)
- 常识英文可解析候选: uyghur, xinjiang, chineseculture, intangibleheritage, unescoheritage

### 44. 蒙古族长调民歌
- 当前 hashtag_terms: 长调, longsong, urtiinduu, mongoliansong
- 样本可解析候选: music(en)
- 常识英文可解析候选: chineseculture, intangibleheritage, unescoheritage
