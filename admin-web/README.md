# Brain Rush Admin Web

独立知识库管理端，用于查看、筛选、启停、轻量编辑 RAG 知识库，上传本地资料文件，并手动重跑 chunk/question embedding。

## 本地启动

```powershell
cd admin-web
npm install
npm run dev
```

默认 API 地址来自 `.env`：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

后端需要配置 `ADMIN_API_TOKEN`，管理端首屏输入该 token 后会保存在浏览器 `localStorage`，后续请求自动带 `X-Admin-Token`。

如果要使用 Imports 页面的文件上传导入，还需要启动 Redis 和 RAG worker：

```powershell
.\backend\scripts\run-rag-worker.ps1
```

## 当前范围

- 支持 Collections、Documents、Chunks、Questions 的列表、搜索、筛选和允许字段编辑。
- 支持 chunk/question 手动 reembed。
- 支持 Imports 上传 `.txt`、`.md`、文本型 `.pdf`，查看导入任务状态、统计、失败原因，并重试 failed 任务。
- 支持 Debug 查询 RAG 检索命中详情。
- 不支持删除、批量上传、URL/Word/OCR 导入或新的权限体系。
