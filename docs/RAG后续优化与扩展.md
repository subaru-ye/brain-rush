# RAG 后续优化与扩展分析

本文档整理当前项目 RAG 流程中仍然比较粗糙的地方，以及后续最值得推进的优化点。当前系统已经完成从 0 到 1：可以导入知识库、生成 embedding、执行 hybrid 检索、参与出题，并能通过调试脚本查看检索命中结果。

当前 RAG 的真实链路、数据库表和操作方式见 [RAG当前实现说明.md](RAG当前实现说明.md)。本文档只讨论后续成熟化路线，重点放在可维护性、可评估性和资料导入能力上。

## 当前还比较粗糙的地方

### 1. 关键词检索已升级，但仍需继续校准中文召回

当前关键词检索已经升级为 `hybrid-rag-v1.3`：PostgreSQL 环境优先使用 Full-Text Search，安装 `pg_jieba` 时使用 `jiebacfg` 做中文分词；如果扩展不可用，则使用 `simple` FTS。同时系统会合并 Python 字段加权 scorer 作为兜底，并对常见 RAG 术语做轻量 query 同义词扩展，例如 chunk/切分/切块、embedding/语义搜索、rerank/重排/精排、knowledge_documents/资料来源。

这已经解决了早期“纯文本包含 + 简单加分”的一部分问题：

- 标题、tags、正文、来源、document 来源和 collection 元数据有了字段权重。
- `debug-rag.ps1` 会输出 `keywordScoreBreakdown`，便于判断命中来源。
- `RAG`、`BM25`、`pgvector`、`HNSW` 等英文术语和数字类关键词有更稳定的召回。
- eval 从 `top5=0.3488` 提升到 `top5=0.7907`，主要改善了 indexing、chunking、embeddings、preprocessing、query_enhancement、dedup 等分类。

后续仍需关注：

- 生产数据库是否能稳定安装和维护 `pg_jieba`。
- `simple` FTS 对中文连续文本仍不如真正中文分词，同义词表也需要继续靠 eval 失败案例校准。
- 当前还不是 BM25，字段权重也需要通过评估集继续校准。

### 2. 混合检索分数融合已升级为 RRF

`hybrid-rag-v1.3` 延续 RRF 融合排序。排序逻辑可以简化理解为：

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

document 下的 chunk 会写入 `document_id`，旧格式 collection 直属 chunk 仍保持兼容。后续更大的工作不再是基础挂载，而是扩展到 Word、网页、截图 OCR 和后台审核管理。

### 5. 已有基础知识库管理后台和导入任务视图，仍缺少完整审核流

目前已经有 `/api/admin/rag/*` 后端管理 API，使用 `ADMIN_API_TOKEN` 和 `X-Admin-Token` 做第一版保护。它可以查看 collection/document/chunk/question，支持启停、轻量编辑 tags/状态/source 元数据，并能触发 chunk/question 重新 embedding。

当前也已经新增独立 `admin-web` 基础管理端，用于在 Web 页面里查看、搜索、筛选、启停、轻量编辑 collection/document/chunk/question，并手动触发 chunk/question reembed。Imports 页面支持上传 `.txt`、`.md` 和文本型 `.pdf`，后端通过 Redis + RQ 异步执行导入任务并记录状态、统计和失败原因。

后续如果知识库越来越多，还需要继续补齐：

- 完整题目结构编辑和校验。
- 新增和删除能力。
- 批量上传、取消任务和更细的导入进度。
- 后台审核流。

也就是说，当前已经具备基础管理页面和导入任务入口，但还没有形成完整知识库后台产品。

### 6. 已有 Redis + RQ 异步导入任务，仍需增强任务治理

当前 `admin-web` 上传导入会创建 `rag_import_jobs` 记录，并交给 Redis + RQ worker 执行 document pipeline。任务会记录 queued/running/succeeded/failed 状态、导入统计和失败原因，failed 或长时间未处理的任务可以手动 Requeue。Imports 页面已经展示 Redis、`rag-imports` 队列、worker 数量和 stale 任务数量；worker 未启动时任务会停留在 `queued`。Windows 本地 worker 使用 `app.rq_worker.WindowsSimpleWorker`，Linux 环境默认使用普通 RQ worker。

后续仍可继续增强：

- 任务取消。
- 更细粒度进度，例如 loader、cleaner、splitter、embedding 阶段。
- 批量上传和批量重试。
- URL、Word、OCR 导入来源。
- 导入审核和版本回滚。

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

当前也已经增加开发环境可用的 Debug API 和 `admin-web` Debug 标签页：

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

这个接口在 `APP_ENV=development` 时可直接访问；非开发环境需要 `X-Admin-Token`。后续还可以继续把它升级成可保存案例、对比多次检索结果和导出评估样本的工具。

当前也已经新增固定评估集和脚本：

```powershell
.\backend\scripts\eval-rag.ps1
```

评估集位于 `backend/data/rag-eval.json`，用 `category` 标注主题，并用 `kind + collectionTitle + title` 描述期望命中。输出包含全局 top1/top3/top5 命中率、失败案例和按分类聚合的命中率，便于观察 chunking、embedding、hybrid retrieval、rerank、evaluation 等主题的检索弱项。后续可以继续扩展为保存历史评估结果、对比不同检索版本和在 CI 中做最低命中率门禁。

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
2. 用 debug 脚本、Debug API、admin-web Debug 页和 eval 脚本验证检索命中。
3. 继续补充 `backend/data/rag-eval.json` 的分类 case，并按分类观察检索弱项。
4. 扩展资料导入 Pipeline 的 URL、Word 和 OCR 能力。

中期推进：

1. 优化混合排序策略。
2. 保存历史评估结果，对比不同检索版本。
3. 继续校准关键词字段权重和中文分词部署。
4. 完善导入任务的取消、批量操作和进度展示。

后期再做：

1. 接入 Rerank。
2. 完善知识库管理页面的审核流。
3. 引入更完整的任务编排和失败恢复。
4. 做知识库版本管理和审核流。

当前最重要的不是继续堆模型，而是让知识库数据更容易维护，让检索效果可以被验证，让资料导入流程逐步从手写 JSON 过渡到自动化。
