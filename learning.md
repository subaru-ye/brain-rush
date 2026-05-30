# RAG 优化面试复盘

本文记录 Brain Rush 项目中 RAG 优化时遇到的真实取舍和落地问题，方便后续在面试中表达项目深度。

## 1. 关键词检索方案的取舍

这次 RAG 优化里，我重点处理了关键词检索的问题。项目早期的关键词检索不是 BM25，也不是数据库全文检索，而是基于文本包含关系和简单打分规则：比如用户输入里出现的词，如果在题干、标签、知识片段内容里出现，就按字段加一些分。

这个方案的优点是实现简单、可控、容易 debug，在知识库很小的时候也够用。但它有几个明显问题：

- 中文没有真正分词，只能做比较粗糙的包含匹配。
- 字段权重只能靠手写规则，很难利用数据库索引。
- 数据量变大后，Python 侧遍历打分会越来越低效。
- 对 `RAG`、`BM25`、`pgvector`、`HNSW` 这类英文技术词可以命中，但整体排序能力有限。

当时我考虑过三个方向：

1. 继续增强原来的 Python scorer。
2. 接入真正的 BM25 引擎。
3. 使用 PostgreSQL Full-Text Search。

如果继续增强 Python scorer，开发成本最低，也最容易保持原有行为，但它本质上仍然是应用层字符串匹配，后续知识库扩大后不太适合作为主检索路径。

BM25 的排序理论更成熟，面向关键词检索也更标准。如果项目已经接入 Elasticsearch、OpenSearch 或 Tantivy 这类搜索引擎，BM25 会是很自然的选择。但这个项目当时的数据量还不大，系统里已经有 PostgreSQL、pgvector 和 Alembic，再单独引入一个搜索服务会增加部署、维护和调试成本。对一个微信小程序后端 MVP 来说，这会让基础设施复杂度超过当前阶段需要。

最后选择 PostgreSQL Full-Text Search，是因为它和现有技术栈最贴合：数据已经在 PostgreSQL 里，迁移可以用 Alembic 管理，FTS 可以建 GIN 索引，和 pgvector 的向量检索也能在同一个数据库里组合。这样能在不引入额外搜索服务的前提下，把关键词检索从“应用层包含匹配”升级成“数据库全文检索 + 字段加权排序”。

我最终的实现是：

- RAG 检索版本升级为 `hybrid-rag-v1.1`。
- PostgreSQL 环境优先走 FTS。
- 中文优先使用 `pg_jieba` 的 `jiebacfg` 分词配置。
- 没有 `pg_jieba` 时降级到 `simple` FTS。
- FTS 查询失败或非 PostgreSQL 测试环境下，保留 Python scorer 兜底。
- debug 结果增加 `keywordScoreBreakdown`，按 `title/tags/body/source/collection` 拆分分数。

面试中可以这样说：

> 我没有一上来就引入 Elasticsearch 或完整 BM25 服务，而是先根据项目阶段做了取舍。当前知识库规模还不大，系统已经依赖 PostgreSQL 和 pgvector，所以我优先用 PostgreSQL FTS 把关键词检索升级起来，并通过字段权重和 GIN 索引提升可解释性和性能。BM25 和 Rerank 我保留为后续方案，等数据达到几千 chunk、debug 显示 top20 能召回但 top5 排序不准时，再升级到更复杂的检索排序链路。

## 2. pg_jieba 中文分词安装的落地难点

另一个实际困难是 `pg_jieba` 的本机安装。理论上 PostgreSQL FTS 能直接用 `simple` 配置，但 `simple` 对中文没有真正分词能力，中文查询效果会比较弱。所以我希望优先接入 `pg_jieba`，让 `to_tsvector('jiebacfg', '检索效果优化')` 能切出 `检索 / 效果 / 优化` 这样的词。

这部分麻烦点主要不在业务代码，而在本机编译和 PostgreSQL 扩展安装：

- `pg_jieba` 是 PostgreSQL C/C++ 扩展，不是普通 Python 包，不能靠 `pip install` 解决。
- Windows 上需要 CMake、Visual Studio Build Tools、Windows SDK、PostgreSQL server headers 和 `postgres.lib`。
- GitHub zip 下载时不会自动带 submodule，需要额外补 `cppjieba` 和 `limonp`。
- MSVC 默认按本机代码页读取部分 UTF-8 头文件，需要显式加 `/utf-8`。
- `cppjieba` 当前头文件里有需要较新 C++ 标准的写法，需要设置 C++20。
- PostgreSQL 服务端头文件里引用了类 Unix 头文件，需要在 Windows 下补兼容头。
- CMake 最终生成的 DLL 名称和 PostgreSQL `MODULE_PATHNAME` 期望名称不完全一致，需要补 `pg_jieba.dll`。
- `CREATE EXTENSION pg_jieba` 必须由 superuser 执行，普通应用数据库用户没有权限。

我处理这件事时没有让业务服务强依赖安装成功，而是做了两层保证：

1. 安装脚本尽量自动化：下载源码、补依赖、配置 CMake、编译安装、创建扩展、重建 FTS 索引。
2. 运行时保持降级：如果 `pg_jieba/jiebacfg` 不可用，服务自动使用 `simple` FTS，再不行回到 Python scorer。

这样即使本地或部署环境暂时没有装好 `pg_jieba`，核心出题流程也不会挂掉，只是中文关键词检索效果下降。

面试中可以这样说：

> 这次优化里比较真实的难点不是写 SQL，而是把 PostgreSQL 中文分词扩展在 Windows 本机跑通。`pg_jieba` 涉及 CMake、MSVC、PostgreSQL 服务端扩展、submodule 依赖、DLL 命名和 superuser 权限。我的处理方式是把安装链路脚本化，同时业务代码不强绑定扩展存在，做到 `pg_jieba` 可用时走中文分词，不可用时自动降级到 `simple` FTS 和 Python fallback。这样既提升了中文检索质量，也保证了系统可用性。

## 3. 可以强调的项目价值

这次 RAG 优化体现的不是单点功能，而是工程取舍：

- 没有盲目堆复杂组件，而是结合当前数据规模和已有 PostgreSQL 基础设施选择 FTS。
- 没有把中文分词安装失败变成线上不可用问题，而是设计了 fallback。
- 通过 debug 输出拆分字段分数，让检索排序可解释、可调试。
- 通过 Alembic 管理索引迁移，让数据库结构变化可追踪。
- 通过测试覆盖 SQLite fallback、关键词权重、英文技术词召回和 debug 输出，保证升级不破坏原有链路。

可以总结成一句面试表达：

> 我在项目里做 RAG 优化时，重点不是简单接一个向量库，而是把关键词检索、向量检索、中文分词、数据库索引、降级策略和 debug 可观测性一起考虑。这样 RAG 链路既能在小数据量阶段保持轻量，又为后续扩展到更大知识库、BM25/Rerank 或资料导入 pipeline 留好了空间。
