# RAG 后续优化与扩展分析

本文档整理当前项目 RAG 流程中仍然比较粗糙的地方，以及后续最值得推进的优化点。当前系统已经完成从 0 到 1：可以导入知识库、生成 embedding、执行 hybrid 检索、参与出题，并能通过调试脚本查看检索命中结果。

当前 RAG 的真实链路、数据库表和操作方式见 [RAG当前实现说明.md](RAG当前实现说明.md)。本文档只讨论后续成熟化路线，重点放在可维护性、可评估性和资料导入能力上。

## 当前还比较粗糙的地方

### 1. 关键词检索已升级，但中文分词依赖数据库扩展

当前关键词检索已经升级为 `hybrid-rag-v1.2`：PostgreSQL 环境优先使用 Full-Text Search，安装 `pg_jieba` 时使用 `jiebacfg` 做中文分词；如果扩展不可用，则自动降级到 `simple` FTS 和 Python 字段加权 scorer。

这已经解决了早期“纯文本包含 + 简单加分”的一部分问题：

- 标题、tags、正文、来源、collection 元数据有了字段权重。
- `debug-rag.ps1` 会输出 `keywordScoreBreakdown`，便于判断命中来源。
- `RAG`、`BM25`、`pgvector`、`HNSW` 等英文术语和数字类关键词有更稳定的召回。

后续仍需关注：

- 生产数据库是否能稳定安装和维护 `pg_jieba`。
- `simple` FTS 对中文连续文本仍不如真正中文分词。
- 当前还不是 BM25，字段权重也需要通过评估集继续校准。

### 2. 混合检索分数融合已升级为 RRF

`hybrid-rag-v1.2` 已经把混合排序从直接加分升级为 RRF 融合排序。排序逻辑可以简化理解为：

```text
最终分数 = 关键词排序贡献 + 向量排序贡献
```

RRF 不直接依赖关键词分和向量分的原始尺度，而是分别看两个检索器里的排名。某条结果如果同时在关键词和向量结果中靠前，会比只在单一路径靠前的结果更容易排到前面。

后续仍可以继续优化：

- 对关键词分和向量分分别归一化。
- 对 question 和 chunk 使用不同权重。
- 对标题、tags、正文、解释等字段设置不同权重。
- 基于评估集校准 RRF 的 `k` 和 keyword/vector 权重。

### 3. 暂时没有 Rerank 精排

当前流程是：

```text
关键词召回 + 向量召回 -> 合并排序 -> 取 top 结果
```

还没有接入 Rerank 模型做二次精排。

当前知识库只有几十条数据，暂时不接 Rerank 是合理的。因为 Rerank 会增加模型调用成本、响应时间和系统复杂度。只有当知识库达到几千个 chunk，或者调试结果显示 top 20 已经包含正确内容但 top 5 经常排序不准时，才值得升级到 `hybrid-rag-v2`。

### 4. `knowledge_documents` 已进入基础导入流程，并具备本地文件 Pipeline 最小版

当前已经新增了 `knowledge_documents` 表，用于表示 PDF、网页、Word、截图等具体资料来源，并且 curated JSON 已支持 document 层级。本地文件 Pipeline 最小版已经支持 `.txt`、`.md` 和文本型 `.pdf` 的文本提取、清洗、切 chunk 和入库。

当前导入可以兼容两种结构：

```text
knowledge_collections -> knowledge_chunks
knowledge_collections -> question_bank_items
knowledge_collections -> knowledge_documents -> knowledge_chunks
```

document 下的 chunk 会写入 `document_id`，旧格式 collection 直属 chunk 仍保持兼容。后续更大的工作不再是基础挂载，而是扩展到 Word、网页、截图 OCR、异步导入任务和后台审核管理。

### 5. 还没有知识库后台管理能力

目前知识库维护主要依赖 JSON 文件和导入脚本。这对开发阶段足够，但长期不够方便。

后续如果知识库越来越多，会需要后台能力：

- 查看 collection。
- 查看 document。
- 查看 chunk。
- 编辑 tags。
- 启用或停用某个 chunk/question。
- 触发重新 embedding。
- 查看导入结果和失败原因。

没有后台管理时，知识库维护会越来越依赖人工改 JSON，容易出错。

### 6. 还没有异步导入任务

当前导入时会同步调用 embedding 接口。数据少时没问题，但如果后续导入一个大 PDF 或大量网页，可能会切出几百到几千个 chunk。

这时同步导入会带来问题：

- 导入耗时长。
- 失败后不好恢复。
- 用户不知道当前处理进度。
- embedding 调用失败时排查成本高。

后续应考虑导入任务表、后台队列、失败重试和任务状态。

### 7. query embedding 暂时没有缓存

用户生成题目时，会对输入文本生成 query embedding。

如果用户多次输入相同或非常相似的内容，当前会重复调用 embedding API。开发阶段影响不大，但用户量上来后会增加成本。

后续可以增加：

- query hash。
- 短期缓存。
- 常见查询缓存。
- embedding 调用统计。

### 8. AI 生成题还没有自动进入题库

当前 `question_bank_items` 主要用于人工整理或导入的精选题。运行时 AI 生成的题不会自动写入题库。

这是合理的，因为 AI 生成题质量不一定稳定，不应直接污染精选题库。

更稳妥的方式应该是：

```text
AI 生成题
  -> 暂存
  -> 收集用户反馈和答题表现
  -> 后台审核
  -> 通过后进入 question_bank_items
```

这样可以逐步沉淀高质量题库，而不是把所有生成结果都当成精选题。

## 后续最值得做的优化点

### 1. 把检索调试能力做扎实

当前已经有脚本：

```powershell
.\backend\scripts\debug-rag.ps1 -Query "RAG 检索效果怎么优化"
```

下一步可以增加开发环境专用 API：

```text
POST /api/debug/rag
```

输入 query 后返回：

- `retrievalVersion`
- 命中的 questions
- 命中的 chunks
- keywordScore
- vectorScore
- totalScore
- sourceIds
- tags

这个接口应只在开发环境开启，不能直接暴露给正式用户。

### 2. 继续完善资料处理 Pipeline

curated JSON 和本地文件 Pipeline 已支持 document 层级，例如：

```json
{
  "collections": [
    {
      "title": "RAG 知识库",
      "documents": [
        {
          "title": "RAG 检索优化资料",
          "sourceType": "web",
          "sourceUri": "https://example.com/rag",
          "chunks": []
        }
      ],
      "questions": []
    }
  ]
}
```

这样每个 chunk 都能追溯来源。后续重点应放在 URL/Word/截图 OCR、自动 tags、导入任务状态管理和人工审核。

### 3. 继续校准关键词检索

当前关键词检索已经接入 PostgreSQL FTS。后续可以继续考虑：

- BM25。
- 更稳定的中文分词部署方案。
- 更细粒度的字段权重调参。
- 基于检索评估集校准精确词、数字、英文缩写的权重。

关键词检索不要被向量检索替代。两者解决的问题不同：

- 向量检索负责语义相似。
- 关键词检索负责精确匹配。

对 RAG、BM25、RRF、pgvector、HNSW 这类术语，关键词检索非常重要。

### 4. 继续校准混合排序策略

当前已经使用 RRF 融合排序。后续可以继续演进为：

```text
向量召回 top 50
关键词召回 top 50
RRF 融合排序
基于评估集校准 RRF 参数和权重
再决定是否进入 Rerank
```

RRF 的好处是不用过度依赖不同检索器的分数尺度，更适合混合检索。

### 5. 增加检索评估集

当前主要靠人工看 debug 输出判断检索是否正确。后续需要建立一批固定测试问题。

例如：

```text
RAG 检索效果怎么优化
Embedding 和 Rerank 有什么区别
为什么要做混合检索
RAG 和微调有什么区别
```

每个问题标注应该命中的 chunk/question，然后计算：

- Recall@5
- Recall@10
- MRR

这样每次改检索逻辑，都能知道效果是变好还是变差。

### 6. 继续扩展资料处理 Pipeline

JSON 适合作为种子数据和人工整理格式，但不应该成为长期唯一入口。当前已经有本地 `.txt`、`.md` 和文本型 `.pdf` 导入的最小 Pipeline，后续需要继续扩展为更完整的资料处理系统。

后续更成熟的资料导入流程应该是：

```text
上传 PDF/Word/网页/截图
  -> 提取文本
  -> 清洗内容
  -> 按语义切 chunk
  -> 自动生成 tags
  -> 生成 embedding
  -> 入库
  -> 人工审核
```

这样知识库建设会从当前“本地文件导入最小版”继续升级为“资料处理系统”。

### 7. 数据量上来后再接 Rerank

Rerank 不建议现在马上做。

适合接入 Rerank 的条件是：

- 知识库达到几千个 chunk。
- debug 结果显示 top 20 有正确内容，但 top 5 排序不准。
- 用户明显感觉生成题引用的知识不够准。

升级后的版本可以叫：

```text
hybrid-rag-v2 = 关键词召回 + 向量召回 + Rerank 精排
```

### 8. 增加知识库版本和状态管理

后续知识库规模变大后，需要回答这些问题：

- 某个资料过期了怎么办？
- 某个 chunk 写错了怎么办？
- 重新导入会不会覆盖？
- 是否能回滚到旧版本？
- 哪次导入生成了哪些 chunks？
- 哪些 embedding 失败了？

可以逐步增加：

- import batch。
- document status。
- chunk version。
- embedding job。
- last_indexed_at。
- failed_reason。

这样知识库会从几张数据表，逐步变成可维护、可追踪、可回滚的系统。

## 推荐推进顺序

短期优先：

1. 继续补充高质量 RAG 数据。
2. 用 debug 脚本验证检索命中。
3. 增加开发环境 RAG debug API。
4. 扩展资料导入 Pipeline 的 URL、Word、OCR 和任务状态能力。

中期推进：

1. 优化混合排序策略。
2. 建立检索评估集。
3. 继续校准关键词字段权重和中文分词部署。
4. 扩展资料导入 Pipeline。

后期再做：

1. 接入 Rerank。
2. 建立知识库后台管理。
3. 引入异步任务队列。
4. 做知识库版本管理和审核流。

当前最重要的不是继续堆模型，而是让知识库数据更容易维护，让检索效果可以被验证，让资料导入流程逐步从手写 JSON 过渡到自动化。
