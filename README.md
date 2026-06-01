# Brain Rush

Brain Rush 是一个 AI 闯关学习微信小程序。用户输入学习主题或材料后，系统生成闯关题，用户逐题作答并获得即时讲解，完成后生成复盘报告、保存学习历史，并可通过错题本继续复训。

当前项目已经从早期 MVP 进入可持续迭代阶段：基础学习闭环已跑通，后端接入 PostgreSQL、微信静默身份、历史记录、题目反馈、错题聚合，并已扩展 `pgvector` 混合 RAG，用于优先召回自维护题库和知识片段辅助出题。

## 当前能力

- 小程序学习闭环：输入主题 -> 生成题目 -> 闯关答题 -> 复盘报告 -> 历史记录。
- 用户沉淀：微信静默身份、历史详情、错题本、题目质量反馈。
- RAG：精选题优先返回；不足时基于知识片段让 AI 补题。
- 知识库管理：独立 `admin-web`，支持查看、筛选、启停、轻量编辑、reembed、Debug、Imports 上传导入和导入队列健康状态查看。
- 数据库：PostgreSQL + Alembic + pgvector。

## 日常启动

通常需要开 3 个终端：后端、小程序前端、RAG 管理后台。只有使用 Imports 上传导入时，才需要额外开 Redis 和 worker。

### 1. 启动后端

```powershell
$env:PYTHONPATH = "$pwd\backend"
.\backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
```

### 2. 启动小程序前端

```powershell
npm run dev:weapp
```

然后用微信开发者工具打开项目根目录。构建产物在 `dist/`。

### 3. 启动 RAG 管理后台

```powershell
cd admin-web
npm run dev
```

管理后台默认连接：

```text
http://127.0.0.1:8000
```

进入页面后输入后端 `.env` 里的 `ADMIN_API_TOKEN`。

### 4. 启动导入 worker

只有在 `admin-web` 的 Imports 页面上传资料时才需要这一步。

先确保 Redis 已启动，然后另开一个终端：

```powershell
.\backend\scripts\run-rag-worker.ps1
```

Imports 支持上传 `.txt`、`.md` 和文本型 `.pdf`。
Imports 页面会显示 Redis、`rag-imports` 队列、worker 和 stale 任务状态。worker 未启动时任务会停留在 `queued`，可以启动 worker 后等待处理，或使用 Requeue 重新把任务放回 Redis 队列。
Windows 本地脚本会使用 `app.rq_worker.WindowsSimpleWorker` 兼容 RQ 的 fork/SIGALRM 问题；Linux 环境默认使用普通 RQ worker。

## 第一次配置

### 后端依赖

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

### 后端环境变量

编辑 `backend\.env`，重点确认这些值：

```env
OPENAI_API_KEY=你的 DeepSeek API Key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash

DATABASE_URL=postgresql+psycopg://brain_rush:brain_rush@localhost:5432/brain_rush
AUTH_TOKEN_SECRET=change-me-in-production
ADMIN_API_TOKEN=本地管理后台令牌

EMBEDDING_API_KEY=你的 Embedding API Key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1536

REDIS_URL=redis://localhost:6379/0
RAG_IMPORT_UPLOAD_DIR=backend/storage/rag-imports
```

微信登录相关变量 `WECHAT_APPID`、`WECHAT_SECRET` 可以后续再配。开发环境未配置时会使用本地 fallback 身份。

### 数据库初始化或升级

```powershell
.\backend\scripts\init-db.ps1
```

### 前端依赖

小程序前端：

```powershell
npm install
```

RAG 管理后台：

```powershell
cd admin-web
npm install
```

## 常用 RAG 命令

导入内置 RAG 数据：

```powershell
.\backend\scripts\import-curated-rag.ps1 -Path .\backend\data\rag-knowledge.json
```

命令行导入本地资料：

```powershell
.\backend\scripts\import-document-rag.ps1 -Path .\docs\rag-notes.md -Collection "RAG 知识库"
```

查看单次检索命中：

```powershell
.\backend\scripts\debug-rag.ps1 -Query "RAG 检索效果怎么优化"
```

批量评估 RAG 命中率：

```powershell
.\backend\scripts\eval-rag.ps1
```

## 产品埋点

小程序端会通过 `POST /api/events` 上报首页访问、输入提交、生成成功/失败、答题、报告、历史和错题本等 V1 事件。登录前事件使用本地匿名 `clientId`，登录后会同时关联当前用户；埋点失败会静默忽略，不阻塞生成题目、答题、报告或历史记录主流程。

## 测试命令

后端测试：

```powershell
.\backend\scripts\test.ps1
```

小程序前端：

```powershell
npm run typecheck
npm run build:weapp
```

RAG 管理后台：

```powershell
cd admin-web
npm run typecheck
npm run build
```

真实模型接口手动验证会消耗模型额度，平时不需要跑：

```powershell
.\backend\scripts\test-real-api.ps1
```

## 文档导航

- [docs/README.md](docs/README.md)：文档目录、阅读顺序和维护规则。
- [docs/PRD.md](docs/PRD.md)：产品需求、用户场景和优先级。
- [docs/方案设计文档.md](docs/方案设计文档.md)：当前技术架构、核心流程和后续路线。
- [docs/optimize.md](docs/optimize.md)：工程优化清单和阶段性工程总结。
- [docs/RAG当前实现说明.md](docs/RAG当前实现说明.md)：当前 RAG 数据模型、导入、检索和调试说明。
- [docs/RAG后续优化与扩展.md](docs/RAG后续优化与扩展.md)：RAG 后续优化点和扩展路线。
- [docs/Learning.md](docs/Learning.md)：历史交接笔记，后续不作为主要项目入口。
