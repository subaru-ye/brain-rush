# Brain Rush Admin Web

独立知识库管理端，用于查看、筛选、启停、轻量编辑 RAG 知识库，并手动重跑 chunk/question embedding。

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

## 当前范围

- 支持 Collections、Documents、Chunks、Questions 的列表、搜索、筛选和允许字段编辑。
- 支持 chunk/question 手动 reembed。
- 不支持创建、删除、文件上传、导入任务队列或新的权限体系。
