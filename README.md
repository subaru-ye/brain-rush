# Brain Rush

AI 闯关学习微信小程序 MVP。

## 当前范围

- 前端：Taro + React + TypeScript 微信小程序。
- 后端：FastAPI + LangChain + OpenAI-compatible AI 服务。
- MVP 闭环：首页输入 -> AI 生成题库 -> 闯关答题 -> AI 生成报告 -> 复盘展示。
- 暂不包含：登录、数据库历史记录、支付、排行榜、RAG、文件/视频/网页解析。

## 后端本地运行

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

填好 `backend\.env` 后启动：

```powershell
$env:PYTHONPATH = "$pwd\backend"
.\backend\.venv\Scripts\uvicorn app.main:app --app-dir backend --reload --port 8000
```

## 后端测试

```powershell
.\backend\scripts\test.ps1
```

测试使用 mock AI，不需要真实大模型 Key。

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
