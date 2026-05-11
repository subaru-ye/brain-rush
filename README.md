# Brain Rush

Brain Rush 是一个 AI 闯关学习微信小程序。用户输入学习主题或材料后，系统生成闯关题，用户逐题作答并获得即时讲解，完成后生成复盘报告、保存学习历史，并可通过错题本继续复训。

当前项目已经从早期 MVP 进入可持续迭代阶段：基础学习闭环已跑通，后端接入 PostgreSQL、微信静默身份、历史记录、题目反馈、错题聚合，并已扩展 `pgvector` 混合 RAG，用于优先召回自维护题库和知识片段辅助出题。

## 当前能力

- 微信小程序前端：Taro + React + TypeScript。
- Python 后端：FastAPI + LangChain + OpenAI-compatible AI 服务。
- 用户身份：微信静默登录；开发环境支持本地 fallback 身份。
- 学习闭环：首页输入 -> 生成题目 -> 闯关答题 -> 生成复盘报告 -> 保存历史。
- 学习沉淀：历史记录、历史详情、错题本复训、题目质量反馈。
- 数据库：PostgreSQL + Alembic 管理 schema。
- RAG：`pgvector` 向量检索 + 关键词检索，支持精选题优先返回，不足时基于检索上下文让 AI 补题。
- 可观测性：结构化日志、`X-Request-ID`、RAG 调试脚本。

暂未实现：文件/PDF/网页/截图自动解析入库、知识库后台管理、异步导入任务、Rerank 精排、支付、排行榜、多人 PK。

## 技术栈

- 前端：Taro、React、TypeScript、微信小程序。
- 后端：FastAPI、LangChain、Pydantic、OpenAI-compatible API。
- 数据：PostgreSQL、Alembic、pgvector。
- AI：默认聊天模型配置指向 DeepSeek；embedding 可配置为阿里云百炼或其他 OpenAI-compatible embedding 服务。

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
EMBEDDING_TIMEOUT_SECONDS=30
EMBEDDING_MAX_RETRIES=2

DATABASE_URL=postgresql+psycopg://brain_rush:brain_rush@localhost:5432/brain_rush
AUTH_TOKEN_SECRET=change-me-in-production
GENERATION_RATE_LIMIT_MAX_REQUESTS=10
GENERATION_RATE_LIMIT_WINDOW_SECONDS=3600
```

微信登录相关变量 `WECHAT_APPID`、`WECHAT_SECRET` 可后续补充；开发环境未配置时会使用本地 fallback 身份。

初始化或升级数据库：

```powershell
.\backend\scripts\init-db.ps1
```

如果已有数据库已人工确认等价于当前 schema，可只标记版本：

```powershell
.\backend\scripts\stamp-db.ps1
```

启动后端：

```powershell
$env:PYTHONPATH = "$pwd\backend"
.\backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```

## RAG 数据导入与调试

导入 curated RAG JSON：

```powershell
.\backend\scripts\import-curated-rag.ps1 -Path .\backend\data\rag-knowledge.json
```

查看一次查询命中了哪些题目和知识片段：

```powershell
.\backend\scripts\debug-rag.ps1 -Query "RAG 检索效果怎么优化"
```

RAG 当前实现说明见 [docs/RAG当前实现说明.md](docs/RAG当前实现说明.md)，后续优化路线见 [docs/RAG后续优化与扩展.md](docs/RAG后续优化与扩展.md)。

## 测试

后端测试：

```powershell
.\backend\scripts\test.ps1
```

真实模型接口手动验证：

```powershell
.\backend\scripts\test-real-api.ps1
```

真实 API 测试会请求 `/api/generate-quiz` 并消耗模型额度；默认输入在 `backend\tests\real_api_manual.py` 中，也可临时覆盖：

```powershell
$env:REAL_API_QUIZ_INPUT = "Transformer 注意力机制和多头注意力"
.\backend\scripts\test-real-api.ps1
```

前端类型检查和构建：

```powershell
npm run typecheck
npm run build:weapp
```

## 前端本地运行

```powershell
npm install
npm run dev:weapp
```

微信开发者工具打开项目根目录，构建产物在 `dist/`。默认后端地址是 `http://127.0.0.1:8000`，如需调整：

```powershell
$env:TARO_APP_API_BASE_URL = "http://127.0.0.1:8000"
npm run build:weapp
```

## 文档导航

- [docs/README.md](docs/README.md)：文档目录、阅读顺序和维护规则。
- [docs/PRD.md](docs/PRD.md)：产品需求、用户场景和优先级。
- [docs/方案设计文档.md](docs/方案设计文档.md)：当前技术架构、核心流程和后续路线。
- [docs/optimize.md](docs/optimize.md)：工程优化清单和阶段性工程总结。
- [docs/RAG当前实现说明.md](docs/RAG当前实现说明.md)：当前 RAG 数据模型、导入、检索和调试说明。
- [docs/RAG后续优化与扩展.md](docs/RAG后续优化与扩展.md)：RAG 后续优化点和扩展路线。
- [docs/Learning.md](docs/Learning.md)：历史交接笔记，后续不作为主要项目入口。
