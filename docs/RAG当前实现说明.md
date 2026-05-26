# RAG 当前实现说明

本文档说明 Brain Rush 当前已经落地的 RAG 能力。它只描述当前真实实现；后续优化方向见 [RAG后续优化与扩展.md](RAG后续优化与扩展.md)。

## 当前定位

当前 RAG 的目标不是完整知识库后台，而是为“AI 闯关出题”提供可控知识来源：

```text
用户输入学习主题
  -> 检索自维护题库和知识片段
  -> 精选题足够时直接返回
  -> 精选题不足时把检索上下文交给 AI 补题
```

这样可以减少纯 AI 出题的不稳定性，也能逐步沉淀高质量题库。

## 数据模型

当前 RAG 相关表如下：

| 表 | 当前职责 |
| --- | --- |
| `knowledge_collections` | 知识领域，例如 `RAG 知识库`。不要把每批资料都建成 collection。 |
| `knowledge_documents` | 具体资料来源，例如 PDF、网页、Word、截图整理材料。curated JSON 已支持 document 层级，chunk 可通过 `document_id` 挂载到具体资料来源。 |
| `knowledge_chunks` | 可检索知识片段，保存正文、tags、来源引用和 embedding。 |
| `question_bank_items` | 自维护精选题库，保存题干、选项、答案、解析、知识点、tags 和 embedding。 |

建模规则：

```text
先确定 collection
再确定 tags
最后写 chunks/questions
```

示例：

```text
collection: RAG 知识库
tags: Embedding、Rerank、检索优化、评估、pgvector
chunks: 具体知识片段
questions: 精选题
```

## 导入流程

当前使用 curated JSON 作为种子数据和人工整理资料的导入格式：

```powershell
.\backend\scripts\import-curated-rag.ps1 -Path .\backend\data\rag-knowledge.json
```

也可以用本地文件导入 Pipeline 把 `.txt`、`.md` 或文本型 `.pdf` 转为 document + chunks 后入库：

```powershell
.\backend\scripts\import-document-rag.ps1 -Path .\docs\rag-notes.md -Collection "RAG 知识库"
```

该 Pipeline 会提取文本、清洗空白、按段落优先切 chunk，并复用 curated 导入流程写入 `knowledge_documents` 和 `knowledge_chunks`。扫描版 PDF、Word、网页和截图 OCR 仍属于后续扩展。

当前也支持通过 `admin-web` 的 Imports 页面上传 `.txt`、`.md` 或文本型 `.pdf`。上传后后端会创建导入任务，交给 Redis + RQ worker 异步执行：

```powershell
.\backend\scripts\run-rag-worker.ps1
```

## 管理接口

当前已提供后端知识库管理 API。配置 `ADMIN_API_TOKEN` 后，请求 `/api/admin/rag/*` 需要携带：

```text
X-Admin-Token: 你的管理令牌
```

管理 API 支持：

- 查看 collection、document、chunk 和精选题。
- 按 collection、document、关键词、状态筛选。
- 启用或停用 collection/document/chunk/question。
- 编辑 collection 描述和 tags、document source 元数据、chunk 内容/source/tags、question difficulty/tags。
- 手动重跑 chunk/question embedding。
- 上传本地资料文件并查看导入任务状态、统计和失败原因。

当前仍不提供删除、完整题目结构编辑、批量上传、URL/Word/OCR 导入和小程序后台页面。

导入时会执行：

1. 读取 JSON 中的 collections。
2. 按 title 和 source type upsert `knowledge_collections`。
3. upsert `knowledge_documents`、`knowledge_chunks` 和 `question_bank_items`。
4. 支持 `collections[].documents[].chunks[]`，document 下的 chunk 会写入 `document_id`。
5. 旧格式 `collections[].chunks[]` 仍可导入，chunk 的 `document_id` 为空。
6. 为 chunk/question 拼接适合 embedding 的文本；chunk embedding 文本会包含 collection 和 document 来源信息。
7. 计算 `content_hash`。
8. 内容、模型和 embedding version 未变化时跳过 embedding。
9. 内容变化时调用 OpenAI-compatible embeddings 接口。
10. 写入 `embedding`、`embedding_model`、`embedding_version`、`content_hash`、`embedded_at`。

如果 embedding 配置缺失，导入仍可写入基础知识数据，但不会生成真实向量；运行时会继续使用关键词检索。

## Embedding 配置

相关环境变量：

```env
EMBEDDING_API_KEY=
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=
EMBEDDING_DIMENSIONS=1536
EMBEDDING_TIMEOUT_SECONDS=30
EMBEDDING_MAX_RETRIES=2
```

`EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL` 未显式配置时，可回退到现有 OpenAI-compatible 配置；但 `EMBEDDING_MODEL` 必须显式配置，真实向量化才会启用。

当前向量维度固定为 1536，对应数据库中的 `vector(1536)`。

## 运行时检索流程

用户调用：

```text
POST /api/generate-quiz
```

后端会先执行 RAG 检索：

```text
用户输入
  -> 提取关键词
  -> 生成 query embedding
  -> 检索 question_bank_items
  -> 检索 knowledge_chunks
  -> PostgreSQL FTS 关键词分 + 向量分合并排序
  -> 取前 5 个精选题和前 5 个知识片段
```

当前版本：

```text
hybrid-rag-v1.2 = PostgreSQL FTS 优先的关键词检索 + pgvector 向量检索 + RRF 融合排序
```

关键词检索负责精确词命中，例如 `RAG`、`Embedding`、`Rerank`、`BM25`、`pgvector`、`HNSW`。PostgreSQL 环境会优先使用 Full-Text Search；如果安装了 `pg_jieba`，会使用 `jiebacfg` 做中文分词，否则使用 `simple` FTS，并保留 Python 字段加权 scorer 兜底。向量检索负责语义相似，例如“检索效果怎么优化”可以命中“混合检索”“重排序”“评估指标”等内容。

关键词分会按字段拆分加权：

| 字段组 | 当前作用 |
| --- | --- |
| `title` | chunk 标题、题干、知识点，权重最高。 |
| `tags` | chunk/question tags，权重较高。 |
| `body` | chunk 正文、题目解释、选项等主体内容。 |
| `source` | chunk 的 `sourceRef`，用于低权重来源命中。 |
| `collection` | collection 标题、描述和 tags，作为领域辅助信号。 |

## 出题策略

检索完成后，后端按以下策略出题：

1. 如果命中精选题，优先把 `question_bank_items` 转成前端题目。
2. 如果精选题达到 5 道，不再调用出题 AI。
3. 如果精选题不足 5 道，把检索到的题目和知识片段拼成上下文。
4. AI 只负责补齐剩余题目数量。
5. 如果完全没有命中上下文，则退回普通 AI 出题。

前端和历史记录中会保留来源字段，便于调试和后续分析。

## 来源字段

题目级字段：

| 字段 | 含义 |
| --- | --- |
| `sourceType=curated_question` | 题目直接来自精选题库。 |
| `sourceType=rag_generated` | 题目由 AI 基于 RAG 检索上下文生成。 |
| `sourceType=ai_generated` | 未命中 RAG，上游 AI 普通生成。 |
| `sourceIds` | 命中的题目或知识片段 id，最多保留 10 个。 |
| `retrievalVersion` | 当前检索版本，例如 `hybrid-rag-v1.2`。 |

会话级字段：

| 字段 | 含义 |
| --- | --- |
| `retrievalVersion` | 本次生成是否使用 RAG 检索版本；未命中上下文时为 `null`。 |

前端开发环境会显示题目来源和 `retrievalVersion`，正式用户体验不依赖这些内部调试字段。

## 调试方式

使用脚本查看一次查询的检索结果：

```powershell
.\backend\scripts\debug-rag.ps1 -Query "RAG 检索效果怎么优化"
```

也可以使用开发调试 API：

```text
POST /api/debug/rag
```

该接口在 `APP_ENV=development` 时可直接访问；非开发环境需要携带 `X-Admin-Token`。独立 `admin-web` 管理端已提供 Debug 标签页，可以输入 query 后查看同一份检索调试结果。

输出会包含：

- `retrievalVersion`
- 命中的 questions
- 命中的 chunks
- `keywordScore`
- `keywordScoreBreakdown`
- `vectorScore`
- `totalScore`
- `keywordRank`
- `vectorRank`
- `fusionMethod`
- `tags`
- `sourceRef`

判断方式：

- 返回 `hybrid-rag-v1.2`：说明本次使用了当前 RAG 检索链路。
- questions 命中较多：可能直接返回精选题，减少 AI 出题调用。
- chunks 命中较多：AI 补题时会获得更具体的上下文。
- `vectorScore` 为 0：可能没有配置 embedding，或相关数据没有向量。
- `keywordScoreBreakdown` 可用于判断命中主要来自标题、tags、正文、来源还是 collection 元数据。
- `totalScore` 在 `hybrid-rag-v1.2` 中表示 RRF 融合分，不再是关键词分和向量分的直接相加。

## 检索评估

当前提供固定评估集文件：

```text
backend/data/rag-eval.json
```

评估项用 `query`、`limit` 和 `expectedMatches` 描述。期望命中按 `kind + collectionTitle + title` 匹配，不依赖数据库 UUID，便于在不同本地数据库之间复用。

运行方式：

```powershell
.\backend\scripts\eval-rag.ps1
```

输出包含总用例数、top1/top3/top5 命中率、命中数量和失败案例。评估逻辑复用 `debug_retrieve_curated_context()`，只读数据库，不触发出题或写入。
- `keywordRank`、`vectorRank` 和 `fusionMethod` 可用于判断排序是否来自关键词、向量或两路共同命中。

## 当前限制

- 已支持本地 `.txt`、`.md` 和文本型 `.pdf` 的最小导入 Pipeline；暂未支持 Word、网页、截图 OCR 和异步导入任务。
- 关键词检索已接入 PostgreSQL Full-Text Search，但中文分词依赖数据库是否安装 `pg_jieba`；未安装时会自动降级到 `simple` FTS 和 Python 兜底打分。
- 混合排序当前使用 RRF 融合关键词结果和向量结果，避免不同检索器的原始分数尺度互相压制。
- 暂未接入 Rerank；当前数据规模下暂不值得增加复杂度。
- 已提供后端知识库管理 API；暂未实现小程序后台页面、文档上传解析、异步导入任务和检索评估集。
- 运行时 AI 生成题不会自动进入精选题库，避免低质量生成结果污染 `question_bank_items`。
