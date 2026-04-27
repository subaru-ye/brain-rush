# Brain Rush Backend

Python 后端使用 FastAPI + LangChain 调用 OpenAI-compatible 大模型接口，默认配置指向 DeepSeek。

## 环境配置

复制环境变量模板：

```powershell
Copy-Item backend\.env.example backend\.env
```

然后在 `backend\.env` 中配置：

```env
OPENAI_API_KEY=你的 DeepSeek API Key
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
OPENAI_TIMEOUT_SECONDS=60
OPENAI_MAX_RETRIES=2
```

## 普通测试

普通测试使用 mock AI，不会消耗真实 API：

```powershell
.\backend\scripts\test.ps1
```

## 真实 API 手动测试

真实 API 测试文件是：

```text
backend\tests\real_api_manual.py
```

它会真实请求 `/api/generate-quiz`，并把生成的题目 JSON 打印出来。运行：

```powershell
.\backend\scripts\test-real-api.ps1
```

默认测试问题在 `real_api_manual.py` 顶部：

```python
DEFAULT_QUIZ_INPUT = "AI Agent core concepts, tool calling, planning, and memory"
```

你可以直接改这个常量，换成想让大模型出题的学习内容。

也可以不改代码，用环境变量临时覆盖：

```powershell
$env:REAL_API_QUIZ_INPUT = "Transformer 注意力机制和多头注意力"
.\backend\scripts\test-real-api.ps1
```

注意：真实 API 测试会消耗模型额度，并且需要 `backend\.env` 中配置有效的 `OPENAI_API_KEY`。
当前实现会优先使用 structured output，并在 DeepSeek JSON 输出返回空内容或解析失败时回退到原始 JSON 解析，这是为了兼容 DeepSeek OpenAI-compatible JSON mode 的偶发不稳定情况。
