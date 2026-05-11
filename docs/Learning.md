# Learning 历史交接笔记

> 本文档保留项目早期跨对话协作时积累的上下文，主要用于回看早期实现过程和工程决策。
>
> 当前项目的主要文档入口已经迁移到：
>
> 1. [README.md](../README.md)：项目入口、启动方式和常用命令。
> 2. [docs/README.md](README.md)：文档导航和维护规则。
> 3. [optimize.md](optimize.md)：工程优化清单和当前状态。
> 4. [方案设计文档.md](方案设计文档.md)：当前技术架构和后续路线。
> 5. [RAG当前实现说明.md](RAG当前实现说明.md)：当前 RAG 实现。
>
> 后续维护应优先更新上述文档。本文档不再作为主要事实来源，只保留历史交接价值。

## 项目定位

- 项目名：`brain-rush`
- 当前目标：打造一个可写进简历的 AI 学习闯关项目
- 当前技术形态：
  - 前端：Taro + React + TypeScript
  - 后端：FastAPI + LangChain + OpenAI-compatible 模型接口
  - 数据库：PostgreSQL
  - 默认模型链路：DeepSeek OpenAI-compatible API

## 当前后端能力概览

后端目前主要提供以下核心接口：

- `POST /api/generate-quiz`
  - 输入学习内容
  - 调用大模型生成 5 道单选题
- `POST /api/generate-report`
  - 输入题目、答案和答题结果
  - 生成学习复盘报告
- `POST /api/auth/wechat`
  - 使用微信静默登录 code 换取后端访问 token
  - 开发环境在未配置微信 AppId/Secret 时使用本地 fallback 身份
- `POST /api/history`
  - 报告生成成功后保存完整学习记录
- `GET /api/history`
  - 读取当前用户的历史记录列表
- `GET /api/history/{id}`
  - 读取当前用户的历史详情

后端当前设计特点：

- 已接入 PostgreSQL，保存完成后的学习历史
- 使用微信静默身份区分用户，不做显式注册登录页
- 当前答题会话仍由前端本地缓存承载，云端只保存完成后的记录
- 后端报告生成时会根据 `selectedIndex == answerIndex` 重算分数和错题
- 错题复盘中的 `wrongQuestions` 由后端程序自行拼装，不依赖 AI 编造

## 已完成内容

### 1. DeepSeek 模型切换与配置梳理

- 确认当前后端通过 `OPENAI_BASE_URL` / `OPENAI_MODEL` 使用 DeepSeek 的 OpenAI-compatible 接口
- 默认模型配置已切到：
  - `deepseek-v4-flash`
- `.env.example` 已补充模型、超时、重试配置示例

### 2. LangChain AI Client 缓存

- 已将 `LangChainAiClient` 从“每个请求新建”改为“进程内缓存复用”
- `LearningService` 仍按请求轻量创建
- 这样做的意义：
  - 避免重复初始化 `ChatOpenAI`
  - 为统一配置 timeout / retry / 日志埋点提供稳定入口
  - 保持测试中的依赖覆盖方式不变

### 3. 真实 API 手动测试链路

- 已增加手动测试文件：
  - `backend/tests/real_api_manual.py`
- 已增加脚本：
  - `backend/scripts/test-real-api.ps1`
- 现在可以：
  - 用真实 API 验证 `/api/generate-quiz`
  - 通过修改顶部常量或设置 `REAL_API_QUIZ_INPUT` 环境变量，自定义测试学习内容
- 后端本地运行、普通测试、真实 API 手动测试方式已统一收敛到根目录 `README.md`

### 4. PyCharm / Turtle 异常定位与清理

- 发现运行 pytest 时弹出的 `Python Turtle Graphics` 不是本项目代码导致
- 根因：
  - 系统 Python 安装目录下存在旧作业文件 `py.py`
  - pytest 启动时 `import py` 被这个旧文件抢占，执行了其中的 turtle 绘图代码
- 已完成处理：
  - 重命名并最终删除该旧文件及其缓存
- 这一问题已排除，不应再干扰当前项目测试

### 5. 后端 AI 调用稳态化改造

已完成以下增强：

- 新增可配置项：
  - `OPENAI_TIMEOUT_SECONDS`
  - `OPENAI_MAX_RETRIES`
- `ChatOpenAI` 现在显式设置：
  - `timeout`
  - `max_retries`
- 错误响应从只有 `detail` 扩展为：
  - `code`
  - `detail`
- 已实现错误分类：
  - `ai_auth_error`
  - `ai_rate_limited`
  - `ai_timeout`
  - `ai_connection_error`
  - `ai_invalid_response`
  - `ai_upstream_error`

### 6. Structured Output + 兼容兜底

- 题目生成和报告生成已优先使用结构化输出
- 具体策略：
  - 先走 `with_structured_output(..., method="json_mode", include_raw=True)`
  - 如果 structured parsing 失败，尝试使用同一次响应里的原始内容做 JSON 兜底解析
- 这样做的原因：
  - 提升输出结构稳定性
  - 避免为了兜底而重复请求模型
  - 兼容 DeepSeek JSON 输出偶发空内容或解析不稳定

### 7. Prompt 模块化

- 原先硬编码在 `backend/app/llm.py` 中的 prompt，已拆到：
  - `backend/app/prompts.py`
- 当前拆分形态：
  - quiz prompt
  - report prompt
  - 对应的 prompt builder 函数
- 当前还未做：
  - 多语言 prompt
  - A/B prompt 策略
  - 外部模板文件化

### 8. 测试补强

- API 层测试已覆盖：
  - 健康检查
  - 出题成功
  - 报告成功
  - 非法输入
  - AI 结构错误
  - 缓存 client 行为
  - 错误码返回
- LLM 层新增单元测试，覆盖：
  - structured output 成功
  - structured output 失败后 raw fallback 成功
  - 空内容触发 `ai_invalid_response`
  - OpenAI-compatible 异常分类

### 9. 前端错误码体验与答题状态抽离

- `api.ts` 已保留后端返回的 `code + detail`
- 首页和报告页会根据 `ai_timeout`、`ai_rate_limited`、`ai_auth_error`、`ai_invalid_response` 等错误码展示更准确的用户提示
- 答题页状态已抽到 `useQuizSession`
- 正误判断、正确率、首个未答题索引等计算已抽到 `utils/quiz.ts`

### 10. 云端历史记录与静默身份

- 已接入 PostgreSQL
- 已新增 `users` 和 `learning_records` 数据模型
- 已实现微信静默身份和开发环境 fallback
- 报告生成成功后保存题目快照、用户答案和报告 JSON
- 前端已新增历史记录页和历史详情页
- 历史记录接口按当前用户过滤，避免跨用户读取

### 11. 前端视觉体系优化

- 全局视觉 token 已收敛到更统一的低饱和青绿色主色
- 首页、答题页、学习报告页已按参考图进行视觉重构
- 已抽出基础展示壳组件，减少 badge、panel、button、report block 的重复样式拼接
- 答题页已为点击选项后的解析区域预留空间，减少首屏装饰占用

## 实现亮点

下面这些点更适合在简历或项目讲解时强调：

### 1. 不是简单“接 API”，而是做了 AI 调用稳态治理

- 显式接入 timeout / retry
- 做了错误分类和统一错误语义
- 给前端保留兼容性，同时为后续精细错误处理留出 `code` 字段

### 2. 结构化输出设计兼顾理想路径和现实兼容

- 优先 structured output
- 保留单次响应内的 raw fallback
- 避免重复调用模型
- 对 DeepSeek OpenAI-compatible 的兼容性问题有清晰工程兜底

### 3. Prompt 工程化开始成型

- Prompt 已从业务逻辑中拆出
- 为后续做多语言、AB 实验、运营调优打下结构基础

### 4. 测试思路比较完整

- 不只测 happy path
- 也测缓存、结构化失败回退、错误分类
- 同时保留 mock 测试和真实 API 手动测试路径

### 5. 能说明排障能力

- 曾定位并清理一个与项目无关、但严重干扰测试的 Python 环境问题
- 说明不仅能写功能，也能处理真实开发环境中的脏问题

### 6. 从一次性 demo 进化到可沉淀记录的 MVP

- 使用微信静默身份降低登录门槛
- 用 PostgreSQL 保存完成后的学习记录
- 保存题目、答案、报告快照，保证历史详情不依赖重新调用 AI
- 当前只保存完成态，避免过早引入恢复答题、草稿同步等复杂状态

## 当前已知不足

这些问题后续可以继续做，且适合作为持续优化点：

- 还没有请求日志、trace id、指标监控
- 还没有限流与额度保护
- 还没有完整用户资料体系、排行榜、学习画像
- Prompt 仍是代码内常量，不是外部化模板
- 暂未做异步化模型调用
- 当前只保存完成后的学习记录，不支持未完成答题恢复到云端
- 历史记录还没有搜索、筛选、错题本和复训入口

## 后续优先建议

如果继续把这个项目往“简历强项目”方向打磨，建议优先考虑：

1. 给出题/复盘/历史接口增加日志与 trace id
2. 增加 API 入口限流和额度保护
3. 增加题目质量反馈与题目质量控制策略
4. 基于历史记录增加错题本和复训机制
5. 增加历史记录搜索、筛选和学习画像
6. 将 Prompt 从代码常量进一步外部化和版本化

## 文档维护约定

本文档不再要求每轮对话持续追加。后续维护优先级如下：

1. 当前能力和启动方式更新到根 [README.md](../README.md)。
2. 文档职责和阅读顺序更新到 [docs/README.md](README.md)。
3. 工程优化项更新到 [optimize.md](optimize.md)。
4. 技术架构和后续路线更新到 [方案设计文档.md](方案设计文档.md)。
5. RAG 当前实现和后续优化分别更新到对应 RAG 文档。

如果需要保留新的交接信息，可以继续追加到本文档，但应避免与主文档形成冲突。
