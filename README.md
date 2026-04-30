# Brain Rush

AI 闯关学习微信小程序 MVP。

## 当前范围

- 前端：Taro + React + TypeScript 微信小程序。
- 后端：FastAPI + LangChain + OpenAI-compatible AI 服务，默认配置指向 DeepSeek。
- 数据：PostgreSQL 保存完成后的学习历史，微信静默身份用于区分用户。
- MVP 闭环：首页输入 -> AI 生成题库 -> 闯关答题 -> AI 生成报告 -> 保存历史 -> 复盘展示。
- 暂不包含：支付、排行榜、RAG、文件/视频/网页解析。

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
DATABASE_URL=postgresql+psycopg://brain_rush:brain_rush@localhost:5432/brain_rush
AUTH_TOKEN_SECRET=change-me-in-production
```

微信登录相关变量 `WECHAT_APPID`、`WECHAT_SECRET` 可后续补充；开发环境会使用本地 fallback 身份。初始化数据库：

```powershell
.\backend\scripts\init-db.ps1
```

填好 `backend\.env` 后启动：

```powershell
$env:PYTHONPATH = "$pwd\backend"
.\backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```

后端会输出结构化 JSON 日志，每次请求的响应头都会带上 `X-Request-ID`，可用来在控制台日志中定位本次请求。

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
