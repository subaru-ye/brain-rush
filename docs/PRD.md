# PRD: AI 闯关学习微信小程序

## 1. 文档信息

- 产品名称：AI 闯关学习小程序
- 产品形态：微信小程序
- 当前阶段：MVP / V1 需求定义
- 目标用户：希望用更轻松方式学习知识的普通用户，以及后续可扩展的垂直学习场景用户
- 核心一句话：用户输入一个学习主题或一段知识内容，小程序自动生成 AI 闯关题，用户逐题答题并获得即时讲解，完成后得到复盘报告、历史记录和分享入口。

## 2. Problem Statement

很多知识学习过程枯燥、反馈慢、互动弱，用户需要主动搜索资料、阅读长内容、整理重点、自己判断掌握程度。这会导致学习门槛高、过程不够轻量、缺少即时反馈，也很难形成可复盘的学习闭环。

用户真正需要的不是单纯的 AI 总结，也不是传统题库，而是一个可以把任意学习意图快速转化为互动式学习体验的工具：用户只需要输入想学的主题或材料，系统就能自动生成闯关题，边答边学，答完后得到总结和复盘。

微信小程序适合这个场景，因为它低门槛、免安装、适合碎片时间使用，并且便于分享传播。

## 3. Solution

构建一个 AI 驱动的闯关学习微信小程序。V1 聚焦最短学习闭环：

1. 用户输入学习主题或粘贴一段文本。
2. 系统调用 AI 生成一组单选闯关题。
3. 用户逐题答题。
4. 每题答完立即展示正误、正确答案和知识讲解。
5. 全部答完后生成通关总结和复盘报告。
6. 系统保存本次学习记录。
7. 用户可以回看历史记录，也可以分享学习结果。

V1 不追求覆盖所有知识输入形式。文档、网页、视频、RAG 知识库、AI 生图、多人 PK、排行榜、VIP 付费等都作为后续扩展，避免首版范围失控。

## 4. 产品目标

### 4.1 用户目标

- 用户可以在短时间内开始一次学习，而不是先花大量时间找资料。
- 用户可以通过闯关问答保持参与感，而不是被动阅读。
- 用户可以在答错时立即理解原因。
- 用户可以在学习结束后看到自己学到了什么、错在哪里、后续该复习什么。
- 用户可以把学习结果分享给好友。

### 4.2 业务目标

- 验证“AI 生成闯关题”是否能提升学习兴趣和完成率。
- 验证用户是否愿意主动输入主题并完成一轮学习。
- 验证复盘报告是否有留存和分享价值。
- 为后续垂直题库、企业培训、考试复习、付费能力打基础。

### 4.3 非目标

- V1 不做完整课程体系。
- V1 不做多人实时竞技。
- V1 不做企业知识库。
- V1 不做复杂内容解析链路。
- V1 不做商业化闭环。

## 5. 用户画像

### 5.1 普通学习者

想快速理解一个陌生知识点，例如“机器学习入门”“股票基金基础”“时间管理方法”。用户希望过程轻松、反馈明确，不想先看大量资料。

### 5.2 备考或刷题用户

需要围绕某类知识进行练习，例如面试题、驾考、英语单词、考试复习。用户关注题目质量、错题讲解和复盘。

### 5.3 碎片时间学习用户

在通勤、午休、睡前等场景使用。用户需要快速开始、单轮学习时间可控、结果清晰。

### 5.4 后续扩展用户

包括企业培训负责人、垂直题库运营者、知识付费创作者等。他们需要把特定知识库转化成题库和学习流程，但这不属于 V1 的核心交付。

## 6. 核心场景

### 6.1 主题学习

用户输入一个想学习的主题，例如“AI Agent 是什么”，系统生成 5-10 道闯关题，用户通过答题快速掌握核心概念。

### 6.2 文本学习

用户粘贴一段文章、笔记或课程内容，系统基于文本生成题目，帮助用户检查理解程度。

### 6.3 错题理解

用户答错后立即看到正确答案和解释，理解自己错在哪里，而不是只看到分数。

### 6.4 通关复盘

用户完成闯关后查看正确率、知识总结、错题回顾、薄弱点和学习建议。

### 6.5 分享传播

用户将通关结果或复盘报告分享给好友，好友可以打开对应学习主题或进入同一闯关流程。

## 7. User Stories

1. As a first-time learner, I want to enter a topic I want to learn, so that I can start learning without searching for materials myself.
2. As a first-time learner, I want to paste a piece of text, so that the quiz can be generated from content I already have.
3. As a learner, I want the app to tell me when my input is too short or empty, so that I know how to fix it.
4. As a learner, I want the app to generate quiz questions automatically, so that I do not need to prepare exercises myself.
5. As a learner, I want the generated questions to match my topic, so that the session feels useful.
6. As a learner, I want each question to have clear options, so that I can answer quickly on mobile.
7. As a learner, I want V1 questions to be single-choice, so that the answer flow is simple and fast.
8. As a learner, I want to know how many questions are in the session, so that I understand the expected effort.
9. As a learner, I want to see my current progress, so that I know how far I am from completion.
10. As a learner, I want to answer one question at a time, so that the learning experience feels like a challenge.
11. As a learner, I want to receive feedback immediately after choosing an answer, so that I can learn while answering.
12. As a learner, I want to see whether my answer is correct or wrong, so that I can understand my performance.
13. As a learner, I want to see the correct answer after answering, so that I can correct my understanding.
14. As a learner, I want to see a knowledge explanation after each question, so that I understand the reasoning behind the answer.
15. As a learner who answered incorrectly, I want the explanation to address the likely misconception, so that the mistake becomes useful.
16. As a learner who answered correctly, I want the explanation to reinforce the key point, so that I can consolidate the knowledge.
17. As a learner, I want to move to the next question after reading the explanation, so that I control the pace.
18. As a learner, I want the app to remember my selected answer, so that my final report can reflect my actual performance.
19. As a learner, I want the app to record whether each answer was correct, so that I can review mistakes later.
20. As a learner, I want the app to record my completion state, so that unfinished and completed sessions can be distinguished.
21. As a learner, I want to see a final score after completing all questions, so that I can quickly understand how I did.
22. As a learner, I want to see my correct rate, so that I can compare learning sessions.
23. As a learner, I want to see a summary of core knowledge points, so that I can review the main content quickly.
24. As a learner, I want to see my wrong questions in the final report, so that I can focus on weak points.
25. As a learner, I want the report to identify weak areas, so that I know what to review next.
26. As a learner, I want follow-up learning suggestions, so that I can continue learning after the session.
27. As a learner, I want my learning history saved, so that I can return to previous sessions.
28. As a returning learner, I want to browse historical learning records, so that I can find previous topics.
29. As a returning learner, I want each history record to show topic, time, score, and status, so that I can choose what to review.
30. As a returning learner, I want to open a historical record, so that I can view the previous report.
31. As a returning learner, I want to revisit wrong questions from a past session, so that I can strengthen weak knowledge.
32. As a learner, I want to share my result, so that friends can see what I learned.
33. As a learner, I want the share content to include topic and score, so that the shared result is meaningful.
34. As a friend receiving a share, I want to open the shared mini program page, so that I can try the same learning topic.
35. As a friend receiving a share, I want to understand what the shared session is about, so that I can decide whether to start.
36. As a learner, I want generation failures to show a clear retry option, so that I am not stuck.
37. As a learner, I want long generation steps to show loading status, so that I know the app is working.
38. As a learner, I want inappropriate or unsupported input to be handled gracefully, so that the experience feels reliable.
39. As a product operator, I want to know the generation success rate, so that I can monitor AI reliability.
40. As a product operator, I want to know completion rate, so that I can evaluate whether the learning flow works.
41. As a product operator, I want to know share click rate, so that I can evaluate viral potential.
42. As a product operator, I want users to report poor questions, so that we can improve question quality.
43. As a product operator, I want to track common generated topics, so that I can identify promising vertical scenarios.
44. As a product operator, I want to know repeat learning rate, so that I can evaluate retention.
45. As a product operator, I want content safety checks around user input and AI output, so that the app can comply with platform requirements.
46. As a future enterprise user, I want to use a fixed knowledge base, so that employees can learn company-specific material.
47. As a future exam learner, I want a dedicated question bank mode, so that I can practice for a specific test.
48. As a future language learner, I want image-assisted questions, so that vocabulary learning becomes more intuitive.
49. As a future paid user, I want higher usage limits or premium learning modes, so that payment corresponds to clear value.
50. As a future competitive learner, I want to challenge friends, so that learning feels more social and playful.

## 8. 功能需求

### 8.1 首页与知识输入

用户进入小程序后，首页应直接提供学习输入能力。

V1 支持：

- 输入一句学习主题。
- 粘贴一段学习文本。
- 提交后生成闯关。
- 输入为空、过短或明显无效时给出提示。

V1 暂不支持：

- 上传文档。
- 输入网页后自动抓取。
- 上传或解析视频。
- 连接私有知识库。

验收标准：

- 用户可以在首页完成输入并提交。
- 主题输入和文本输入都能进入生成流程。
- 空输入不能提交。
- 生成过程中有明确 loading 状态。
- 生成失败时可以重试。

### 8.2 AI 题目生成

系统根据用户输入生成结构化题目。

每道题必须包含：

- 题干
- 3-4 个选项
- 正确答案
- 答案解析
- 对应知识点

V1 默认：

- 题型：单选题
- 题量：建议 5 题，可根据产品节奏配置为 5 或 10 题
- 难度：默认入门到中等，不提供复杂难度选择

验收标准：

- 生成结果可被前端稳定渲染。
- 每题只能有一个正确答案。
- 题目、选项、答案、解析不能为空。
- 如果 AI 输出结构不合法，系统应进行重试、修复或提示失败。
- 题目应与用户输入主题或文本相关。

### 8.3 闯关答题

用户以闯关方式逐题作答。

功能要求：

- 展示当前题号和总题数。
- 展示题干和选项。
- 用户选择选项后锁定当前题。
- 展示正误反馈。
- 展示正确答案。
- 展示知识讲解。
- 用户确认后进入下一题。
- 最后一题完成后进入复盘页。

验收标准：

- 用户作答前不能看到答案。
- 用户作答后不能反复修改该题答案。
- 每题的用户答案、正确性和答题时间应被记录。
- 用户完成所有题后必须能生成本轮学习结果。

### 8.4 即时讲解

每道题作答后展示讲解。

讲解内容应包含：

- 为什么正确答案正确。
- 用户答错时，帮助理解错误原因。
- 该题对应的核心知识点。

验收标准：

- 正确和错误状态都展示讲解。
- 讲解与题目内容相关。
- 讲解文本适合移动端阅读，不应过长。

### 8.5 通关总结与复盘报告

用户完成一轮闯关后进入复盘页。

复盘报告应包含：

- 学习主题
- 完成时间
- 题目数量
- 正确题数
- 正确率
- 核心知识点总结
- 错题回顾
- 薄弱点分析
- 后续学习建议

验收标准：

- 最后一题完成后自动进入复盘页。
- 复盘页至少展示得分、正确率、知识总结和错题。
- 错题信息与用户实际答案一致。
- 复盘内容可以被保存到历史记录。

### 8.6 学习记录

系统保存用户学习记录，供后续回看。

记录字段建议：

- 学习主题
- 输入类型
- 创建时间
- 完成时间
- 完成状态
- 题目数量
- 正确题数
- 正确率
- 每题答题详情
- 复盘报告

验收标准：

- 完成一次闯关后，历史列表出现该记录。
- 用户可以打开历史记录查看复盘。
- 未完成记录和已完成记录应能区分。
- 历史记录应按时间倒序展示。

### 8.7 分享

用户可以在复盘页分享学习结果。

分享内容建议包含：

- 学习主题
- 正确率或得分
- 简短总结
- 进入同主题学习的入口

验收标准：

- 复盘页提供分享入口。
- 微信分享卡片文案清晰。
- 好友打开分享后能进入对应主题或结果页。
- 分享链路不依赖分享者的私密数据。

### 8.8 题目质量反馈

V1 建议提供轻量反馈能力，用于识别 AI 生成质量问题。

反馈类型：

- 题目不相关
- 答案可能错误
- 讲解看不懂
- 内容不合适

验收标准：

- 用户可以在题目或复盘页提交问题反馈。
- 反馈应关联到对应题目和学习记录。
- 反馈不影响用户继续答题。

### 8.9 内容安全

系统应对用户输入和 AI 输出进行基础内容安全处理，避免明显违规、敏感或不适合传播的内容进入展示和分享。

验收标准：

- 明显违规输入不能进入题目生成。
- AI 输出展示前应具备基础校验或拦截机制。
- 被拦截时应向用户展示可理解的提示。

## 9. 非功能需求

### 9.1 性能

- 首页应快速可用。
- 题目生成应有明确等待反馈。
- 生成耗时较长时应避免用户误以为卡死。
- 答题过程中的页面切换和反馈展示应保持流畅。

### 9.2 稳定性

- AI 生成失败、网络失败、结构化结果异常时，应有重试或失败提示。
- 用户答题中断后，应尽量保留当前学习进度。
- 历史记录保存失败时，应提示用户或进行补偿处理。

### 9.3 可用性

- 移动端优先。
- 输入、答题、复盘流程应短路径完成。
- 选项按钮应易点击。
- 错误状态、空状态、加载状态要明确。

### 9.4 可扩展性

V1 虽然只支持主题和文本输入，但系统应为后续扩展保留清晰边界：

- 后续可增加网页、文档、视频等输入源。
- 后续可增加不同题型。
- 后续可增加知识库/RAG。
- 后续可增加付费和会员能力。
- 后续可增加垂直题库模板。

### 9.5 合规与安全

- 需要符合微信小程序平台规则。
- 需要考虑用户输入和 AI 输出的内容安全。
- 涉及教育、考试、医疗、法律等领域时，输出应避免暗示绝对正确。
- 分享内容不应泄露用户隐私。

## 10. Implementation Decisions

### 10.1 产品模块拆分

V1 建议按以下模块组织产品能力：

- 学习输入模块：负责主题输入、文本输入、输入校验、提交生成。
- 内容预处理模块：负责把用户输入整理成适合 AI 生成题目的上下文。
- AI 题目生成模块：负责生成结构化题目、选项、答案和讲解。
- 题目结构校验模块：负责校验 AI 输出是否可用，必要时触发修复或重试。
- 闯关会话模块：负责题目顺序、当前进度、作答状态和通关状态。
- 答题反馈模块：负责正误判断、答案展示、讲解展示。
- 复盘报告模块：负责根据题目和答题结果生成总结、错题回顾、薄弱点和建议。
- 学习记录模块：负责保存、查询、展示历史学习记录。
- 分享模块：负责生成微信分享内容和分享落地页。
- 内容安全模块：负责用户输入和 AI 输出的基础安全校验。
- 数据埋点模块：负责记录生成成功率、完成率、分享率、留存等指标。

### 10.2 深模块建议

以下模块应设计为接口稳定、内部可替换的深模块：

- AI 题目生成模块：外部只关心输入学习内容和返回题目集合，内部可以替换提示词、模型、联网搜索、RAG 或重试策略。
- 闯关会话模块：外部只关心开始、作答、进入下一题、完成等动作，内部维护进度、答案、正确性和状态。
- 复盘报告模块：外部只传入学习记录和题目作答结果，内部决定使用模板生成还是 AI 生成。
- 内容来源模块：V1 只支持主题和文本，但后续网页、文档、视频、知识库都应能作为内容来源扩展。

### 10.3 数据对象

V1 需要抽象以下核心对象：

- 用户
- 学习输入
- 学习会话
- 题目
- 选项
- 用户答案
- 题目讲解
- 复盘报告
- 学习记录
- 分享记录
- 题目质量反馈

### 10.4 关键交互决策

- 用户先输入，再生成题目，不在 V1 做预置课程首页。
- 答题采用逐题闯关，而不是一次性展示整套题。
- 用户选择答案后立即显示反馈，不等到全部题目完成后才批改。
- 复盘报告在通关后展示，是学习闭环的一部分，不是可选附属功能。
- 分享从复盘页发起，分享内容以学习结果和主题为核心。
- V1 题型固定为单选题，降低生成、校验和交互复杂度。

### 10.5 AI 生成策略

- AI 输出必须使用结构化格式，便于程序校验和渲染。
- 系统应限制题目数量、讲解长度和选项数量。
- 对 AI 输出进行完整性校验，避免缺题、缺答案、多个正确答案、解析为空等问题。
- 生成失败时允许重试。
- 对高风险主题应增加提示、拒答或免责声明。

### 10.6 登录与记录策略

V1 是否强制登录仍待确认。推荐策略：

- 用户首次体验可尽量降低门槛。
- 如果要跨设备保存历史记录，则需要登录。
- 如果用户未登录，至少应支持当前设备或当前会话内查看结果。
- 分享内容不应暴露用户敏感信息。

### 10.7 指标埋点

V1 应记录以下核心指标：

- 首页访问
- 输入提交
- 题目生成开始
- 题目生成成功
- 题目生成失败
- 开始答题
- 每题作答
- 完成闯关
- 查看复盘
- 点击分享
- 分享打开
- 查看历史记录
- 提交题目反馈

## 11. Testing Decisions

### 11.1 测试原则

- 测试外部行为，不测试内部实现细节。
- 优先覆盖用户关键路径，而不是覆盖所有内部函数。
- AI 相关能力应重点测试结构化输出校验、失败处理和边界输入。
- 闯关会话应重点测试状态流转和答题结果一致性。
- 复盘报告应重点测试是否基于真实答题结果生成。

### 11.2 必测模块

- 学习输入模块：空输入、短输入、正常主题、正常文本。
- AI 题目生成模块：成功生成、生成失败、输出结构异常、题目数量异常。
- 题目结构校验模块：缺题干、缺选项、缺正确答案、多个正确答案、解析为空。
- 闯关会话模块：开始会话、答题、重复答题、下一题、完成。
- 答题反馈模块：答对、答错、展示正确答案和讲解。
- 复盘报告模块：得分计算、正确率计算、错题列表、薄弱点生成。
- 学习记录模块：保存记录、查询列表、查看详情、区分完成状态。
- 分享模块：生成分享内容、打开分享入口。
- 内容安全模块：违规输入拦截、AI 输出拦截。

### 11.3 建议测试场景

1. 用户输入“机器学习入门”，系统成功生成 5 道题并进入答题页。
2. 用户输入空内容，系统提示补充学习内容。
3. AI 返回缺少正确答案的题目，系统识别异常并重试或提示失败。
4. 用户答对一题后，系统显示正确状态、正确答案和讲解。
5. 用户答错一题后，系统显示错误状态、正确答案和讲解。
6. 用户完成全部题目后，系统展示正确率和复盘报告。
7. 用户完成一次学习后，历史列表新增记录。
8. 用户打开历史记录，可以看到之前的复盘报告。
9. 用户点击分享，生成包含主题和得分的分享内容。
10. 违规或敏感输入被拦截，用户看到明确提示。

### 11.4 不建议的测试方式

- 不依赖真实大模型结果作为稳定测试断言。
- 不测试具体提示词文本是否完全一致。
- 不把 UI 动画和装饰样式作为核心业务测试目标。
- 不要求 V1 覆盖后续扩展功能。

## 12. 成功指标

### 12.1 激活指标

- 首页访问到提交输入的转化率
- 输入提交到生成成功的转化率
- 题目生成成功率
- 从进入首页到开始答题的转化率

### 12.2 学习完成指标

- 单轮闯关完成率
- 平均完成题数
- 平均正确率
- 用户查看讲解比例
- 用户查看复盘页比例

### 12.3 留存与分享指标

- 历史记录回看率
- 次日再次学习率
- 七日再次学习率
- 分享按钮点击率
- 分享打开率
- 分享带来的新学习会话数

### 12.4 质量指标

- 题目生成失败率
- AI 输出结构异常率
- 用户反馈题目错误率
- 用户反馈题目不相关率
- 内容安全拦截率

## 13. 需求优先级

### 13.1 Must

- 主题或文本输入
- AI 生成单选闯关题
- 题目结构校验
- 逐题答题
- 即时正误反馈
- 正确答案和知识讲解
- 通关总结和复盘报告
- 学习记录保存与查看
- 基础内容安全

### 13.2 Should

- 复盘报告分享
- 错题回顾
- 历史记录详情
- 生成失败重试
- 题目质量反馈
- 基础数据埋点

### 13.3 Could

- 题目数量选择
- 难度选择
- 错题本
- 学习建议追问
- 网页解析
- 文档解析

### 13.4 Won't for V1

- 视频解析
- 私有知识库/RAG
- AI 生图
- 多人 PK
- 排行榜
- 数字人
- 语音读题
- VIP 支付
- 企业后台
- 复杂题型
- 完整课程体系

## 14. Out of Scope

V1 明确不包含以下内容：

- 上传 PDF、Word、图片等文档后生成题目。
- 输入网页链接后自动抓取全文。
- 输入视频链接或上传视频后自动转写。
- 企业培训后台和组织管理。
- 私有知识库、RAG、题库管理。
- AI 生图题目或图片选项。
- 充值、会员、微信支付。
- 多人实时对战。
- 排行榜。
- 数字人讲题。
- 语音读题。
- 主观题自动评分。
- 完整课程路径规划。

这些能力可以作为后续版本规划，但不应阻塞 V1 验证。

## 15. 风险与应对

### 15.1 题目质量不稳定

风险：AI 生成题目可能不准确、不相关或讲解质量低。

应对：

- 使用结构化输出和校验。
- 限制题型和题量。
- 提供题目质量反馈。
- 对异常输出进行重试或降级提示。

### 15.2 “任何知识”范围过大

风险：不同知识领域差异大，通用体验可能不稳定。

应对：

- V1 只验证主题和文本输入。
- 通过数据观察高频主题。
- 后续选择表现好的垂直领域深化。

### 15.3 用户不知道输入什么

风险：首页只有输入框可能导致新用户无从开始。

应对：

- 提供示例主题。
- 提供最近热门学习主题。
- 提供输入提示，但不把首页做成复杂课程页。

### 15.4 AI 成本不可控

风险：生成题目和报告会产生模型调用成本。

应对：

- 限制题量和生成频率。
- 控制讲解长度。
- 复盘报告可采用模板加 AI 摘要的混合方式。
- 后续再接入付费或额度体系。

### 15.5 平台合规风险

风险：用户输入和 AI 输出可能涉及敏感内容。

应对：

- 对输入和输出做内容安全校验。
- 分享内容做额外检查。
- 高风险领域加入提示或拒答策略。

## 16. 待确认问题

1. V1 是否强制微信登录？
2. 历史记录是否必须云端保存，还是可以先本地/会话保存？
3. 题目数量 V1 固定为 5 题还是 10 题？
4. AI 是否允许联网搜索，还是 V1 只基于用户输入生成？
5. 复盘报告使用 AI 实时生成，还是固定模板生成？
6. 分享落地页展示用户成绩，还是让好友重新闯关？
7. 是否需要在 V1 加入用户反馈题目错误？
8. 首发定位是通用学习工具，还是先选择一个垂直场景？

## 17. Further Notes

V1 的关键不是一次性做成“万能学习平台”，而是验证一个最小闭环：用户愿意输入学习主题，AI 生成的题目能让用户完成闯关，逐题讲解能带来学习价值，通关复盘能让用户愿意保存或分享。

如果这个闭环成立，再扩展到文档解析、网页解析、视频解析、RAG 知识库、垂直题库、多人 PK、VIP 付费等方向会更稳。

当前建议的下一步是进入产品原型和系统设计阶段，优先设计首页输入、题目生成中状态、答题页、复盘页、历史记录页和分享落地页。
