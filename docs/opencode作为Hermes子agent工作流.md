# opencode 作为 Hermes 子 agent 工作流

> 配套阅读：`docs/数据采集规格说明.md`，尤其第 9 节。本文只记录技术接线与调用约定；研究分工、红线与验收锚点以规格说明为准。

## 角色边界

- **Hermes**：编排者。负责需求拆分、资源/代理池、跨机器状态、长期运行、记录结论。
- **opencode**：仓库内代码执行子 agent。负责写脚本、改采集器、做字段/口径验收；任务结束即退出，不保留跨任务记忆。
- **人（Cloud）**：研究判断者。人工相关性标注、是否改词、是否是真实低传播等结论都由人决定。

## Morn 上的接线

- opencode worker：`http://127.0.0.1:4096`
- systemd：`opencode-worker.service`
- 主要项目目录：`/root/workspace/tiktok-heritage-crawler`
- 采集规格：`/root/workspace/tiktok-heritage-crawler/docs/数据采集规格说明.md`
- 大规模采集实际运行：Hermes 在 Morn 上拉起，不塞进 opencode session。

## 推荐调用方式

简单单次代码任务优先用：

```bash
cd /root/workspace/tiktok-heritage-crawler
opencode run --model newapi/claude-sonnet-4-6 "<完整任务 prompt>"
```

复杂多轮任务可用 HTTP API，但注意 HTTP serve 的 cwd 固定在 `/opt/opencode-worker/`，所以要在 prompt 里显式要求操作目标路径，或优先使用 `opencode run`。

## 每次派给 opencode 的 prompt 必带内容

1. 目标目录：`/root/workspace/tiktok-heritage-crawler`
2. 必读文档：`docs/数据采集规格说明.md`
3. 明确 deliverable：改哪些脚本、生成哪些文件、不要顺手跑大规模采集
4. 死命令：
   - 不删原始数据，只生成标注/清洗副本。
   - `negative_terms` 只用于打标/排序，不用于采集时排除。
   - 不自动归类内容类型，不自动改词催召回。
   - 零结果必须记录 `total_results=0`。
   - 缺失字段留空，不瞎填。
5. 退出前给出：改动文件、运行过的检查命令、还需 Hermes/人处理的事项。

## 当前阶段禁止委托给 opencode 的事

- 代替人判断视频是否相关。
- 自动决定高 `low_relevance` 项目是关键词问题还是真实低传播。
- 自动扩展/改写关键词并直接进入大规模采集。
- 长时间跑全量采集。

## 当前阶段适合委托给 opencode 的事

- 从三档标签中各抽 20 条，导出人工标注清单。
- 写/修字段口径校验脚本。
- 按人工确认后的词表改采集器。
- 生成二测任务脚本，但由 Hermes 运行。
