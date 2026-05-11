# Brain Rush

AI 闯关学习微信小程序 MVP。

## 当前范围

- 前端：Taro + React + TypeScript 微信小程序。
- 后端：FastAPI + LangChain + OpenAI-compatible AI 服务，默认配置指向 DeepSeek。
- 数据：PostgreSQL 保存完成后的学习历史、题目质量反馈、错题聚合和自维护题库/RAG 内容，微信静默身份用于区分用户。
- MVP 闭环：首页输入 -> AI 生成题库 -> 闯关答题 -> AI 生成报告 -> 保存历史 -> 复盘展示 -> 错题本复训。
- 暂不包含：支付、排行榜、用户上传文件/视频/网页解析。

## 后端本地运行

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

在 `backend\.env` 中至少配置：

```env
OPENAI_API_KEY=你的 DeepSeek API Key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
EMBEDDING_API_KEY=你的百炼或 OpenAI-compatible Embedding API Key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1536
GENERATION_RATE_LIMIT_MAX_REQUESTS=10
GENERATION_RATE_LIMIT_WINDOW_SECONDS=3600
DATABASE_URL=postgresql+psycopg://brain_rush:brain_rush@localhost:5432/brain_rush
AUTH_TOKEN_SECRET=change-me-in-production
```

微信登录相关变量 `WECHAT_APPID`、`WECHAT_SECRET` 可后续补充；开发环境会使用本地 fallback 身份。初始化数据库：

```powershell
.\backend\scripts\init-db.ps1
```

数据库 schema 由 Alembic 管理，`init-db.ps1` 会执行 `alembic upgrade head`。
如果已有数据库已经人工确认等价于当前 schema，可以只标记一次版本：

```powershell
.\backend\scripts\stamp-db.ps1
```

当前 RAG 采用 `pgvector` 混合检索：`knowledge_collections` 保存知识领域，
`knowledge_documents` 预留给后续文件、网页、截图等具体资料来源，
`knowledge_chunks` 保存可检索知识片段和向量，`question_bank_items` 保存高质量原题和向量。
导入知识库时会调用 Embedding 模型生成向量；生成题目时会对用户输入生成 query embedding，
再结合关键词检索与向量检索召回相关内容。命中足够原题时不调用出题 AI，不足时只让 AI 基于检索上下文补齐。

知识库建模时先判断 `collection`，再判断 `tags`，最后写 `chunks/questions`：

- `collection` 是知识领域，不是资料批次。例如同一批或多批 RAG 资料都应归入 `RAG 知识库`。
- `tags` 表示子主题，例如基础概念、检索优化、Rerank、评估、pgvector。
- `chunks` 保存具体知识片段，`questions` 保存精选题目。
- 不要因为用户分多次提供资料，就为每批资料新建一个 collection。

可用 JSON 文件导入自维护内容：

```powershell
.\backend\scripts\import-curated-rag.ps1 -Path .\backend\data\rag-knowledge.json
```

导入后可用调试脚本查看检索命中和分数：

```powershell
.\backend\scripts\debug-rag.ps1 -Query "RAG 检索效果怎么优化"
```

输出会包含 `retrievalVersion`、命中的题目和知识片段、`keywordScore`、`vectorScore`、`totalScore`。

填好 `backend\.env` 后启动：

```powershell
$env:PYTHONPATH = "$pwd\backend"
.\backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```

后端会输出结构化 JSON 日志，每次请求的响应头都会带上 `X-Request-ID`，可用来在控制台日志中定位本次请求。生成题目和生成报告接口默认按 IP + 接口限制为每小时 10 次，可通过 `GENERATION_RATE_LIMIT_MAX_REQUESTS` 和 `GENERATION_RATE_LIMIT_WINDOW_SECONDS` 调整。

## 后端测试

```powershell
.\backend\scripts\test.ps1
```

测试使用 mock AI，不需要真实大模型 Key。

如需验证真实模型接口，可运行：

```powershell
.\backend\scripts\test-real-api.ps1
```

真实 API 测试会请求 `/api/generate-quiz` 并消耗模型额度；默认输入在 `backend\tests\real_api_manual.py` 中，也可以临时覆盖：

```powershell
$env:REAL_API_QUIZ_INPUT = "Transformer 注意力机制和多头注意力"
.\backend\scripts\test-real-api.ps1
```

当前实现优先使用 structured output，并在 DeepSeek JSON 输出返回空内容或解析失败时回退到原始 JSON 解析，以兼容 DeepSeek OpenAI-compatible JSON mode 的偶发不稳定情况。

## 前端本地运行

```powershell
npm install
npm run dev:weapp
```

微信开发者工具打开项目根目录，构建产物在 `dist/`。

默认后端地址是 `http://127.0.0.1:8000`。如需调整：

```powershell
$env:TARO_APP_API_BASE_URL = "http://127.0.0.1:8000"
npm run build:weapp
```
