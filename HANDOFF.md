# 项目交接状态：UNESCO 中国非遗 TikTok 数据采集

更新时间：2026-05-31 04:21:29 CST

## 当前阶段

项目目前停在：**等待人工标注 60 条抽样样本**。

下一次继续时，不要直接继续大规模爬取；应先读取人工填回来的标注表，计算机器 `quality_label` 的准确率，再决定是否修订关键词和打标规则。

## 已完成事项

1. 已建立 TikTok 非遗采集项目：
   - 项目目录：`/root/workspace/tiktok-heritage-crawler`
   - GitHub repo：`goodmorningorbad/tiktok-heritage-crawler`

2. 已接入用户提供的 TikTok cookies，并解决自动刷新/持久化问题。

3. 已完成首批粗搜数据采集：
   - 原始采集后清洗/打标数据：`data/unesco_tiktok_20260530_233505_labeled.csv`
   - 行数：3870 条
   - 三档机器标签分布：
     - `likely_relevant`: 1357
     - `needs_review`: 1076
     - `low_relevance`: 1437

4. 已把采集规格文档写入 repo：
   - `docs/数据采集规格说明.md`
   - 已提交并 push：`b9f549e Add project data collection specification`

5. 已从三档机器标签中固定随机种子抽样 60 条，供人工校验：
   - `likely_relevant`: 20 条
   - `needs_review`: 20 条
   - `low_relevance`: 20 条

6. 已生成两份人工标注 Excel：
   - 空白版，给小组填写：
     - `data/manual_review_sample_60_blank.xlsx`
     - `data/manual_review_sample_60_blank.csv`
   - 言言预标注版，供参考：
     - `data/manual_review_sample_60_yanyan_prefilled.xlsx`
     - `data/manual_review_sample_60_yanyan_prefilled.csv`
   - 中间 JSON：
     - `data/manual_review_sample_60_for_labeling.json`

## 人工标注表填写口径

建议 `manual_label` 只填以下三个值：

- `relevant`：该视频确实与对应非遗项目相关。
- `irrelevant`：明显不相关，属于关键词误召回。
- `uncertain`：仅凭 caption/hashtags 不能判断，或边缘相关，需要看视频画面/课堂讨论决定。

`manual_notes` 可自由填写原因。

## 言言预标注结果，仅供参考

言言根据 caption / hashtags / 搜索词文本证据填了一版：

- `relevant`: 26
- `uncertain`: 14
- `irrelevant`: 20

按机器原标签拆分：

- `likely_relevant`: 15 relevant / 3 uncertain / 2 irrelevant
- `needs_review`: 10 relevant / 2 uncertain / 8 irrelevant
- `low_relevance`: 1 relevant / 9 uncertain / 10 irrelevant

这说明当前机器规则大方向可用，但存在明显误判，尤其是宽泛英文词。

## 已发现的典型误判模式

后续修订 `quality_label.py` 或关键词表时优先处理：

1. `Spring Festival`：会误抓韩国/大学音乐节，不一定是春节。
2. `papercut`：会误抓 Linkin Park 歌曲《Papercut》，不是剪纸。
3. `nanguan`：会误抓兰州南关美食街，不是南音。
4. `gesar`：会误抓 `GESARA/NESARA` 阴谋论，不是格萨尔史诗。
5. `wangchuan` / `ongchun`：会误抓人名、账号名、越南语词，不是送王船。
6. `ricepaper`：会误抓食物米纸，不是宣纸。
7. `peking`：会误抓北京/餐饮/地名，不是京剧。
8. `celadon`：很多只是青瓷色/aesthetic，不一定是龙泉青瓷烧制技艺。
9. `chinesepuppet`：可能抓到中国皮影戏，但对“福建木偶戏”项目是误收。

注意：这些误判应优先用于**打标/排序修订**，不要在采集阶段直接过滤。规格红线仍是：`negative_terms` 只用于标记低相关，不用于采集时排除。

## 下一步操作

用户会把小组人工填写后的 Excel 发回来。收到后应执行：

1. 读取用户填回的人工标注表。
2. 校验 `manual_label` 是否只包含：`relevant` / `irrelevant` / `uncertain` / 空值。
3. 统计每个机器标签档位的人工结果：
   - `likely_relevant` 的真实准确率
   - `needs_review` 中 relevant / uncertain / irrelevant 占比
   - `low_relevance` 中误杀 relevant 的比例
4. 输出一份校准报告。
5. 根据人工结果修订：
   - `quality_label.py`
   - 后续关键词结构：`search_terms` / `core_terms` / `negative_terms`
6. 再进行二测，每项目 30–50 条，看噪声是否下降。

## 重要方法论口径

不要为了让数据“好看”而过滤噪声。项目目标是验证或推翻假设：

- 热门是结果。
- 冷门也是结果。
- 零结果/低传播也是结果。
- 噪声比例本身也是结果，可能说明某项非遗的海外辨识度被稀释。

高 `low_relevance` 不能直接解释为“关键词差”，需要区分：

1. 关键词太泛，真实相关内容被没召回好；
2. 该非遗在 TikTok 上确实近乎隐形。

第二种情况本身可能支持项目假设，不能通过关键词工程强行制造传播。

## 关键文件路径

项目目录：

```text
/root/workspace/tiktok-heritage-crawler
```

主要脚本：

```text
crawler.py
batch_collect.py
quality_label.py
```

规格文档：

```text
docs/数据采集规格说明.md
```

人工标注相关文件：

```text
data/manual_review_sample_60_blank.xlsx
data/manual_review_sample_60_blank.csv
data/manual_review_sample_60_yanyan_prefilled.xlsx
data/manual_review_sample_60_yanyan_prefilled.csv
data/manual_review_sample_60_for_labeling.json
```

首批 labeled 数据：

```text
data/unesco_tiktok_20260530_233505_labeled.csv
```

## Git 状态记录

最近重要提交：

```text
b9f549e Add project data collection specification
49c8f0b Document Scrapling as optional scraping fallback
27fdbc2 Initial TikTok heritage crawler toolkit
```

本交接文件建议提交到 git；`data/` 下的大文件和标注表一般不提交，保留在 VPS 文件系统即可。
