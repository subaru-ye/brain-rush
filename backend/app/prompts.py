from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


QUIZ_PROMPT_VERSION = "quiz-v1"
REPORT_PROMPT_VERSION = "report-v1"

QUIZ_SYSTEM_PROMPT = (
    "You are a Chinese learning coach for a mobile quiz app. "
    "Turn the user's study material into concise, accurate single-choice questions. "
    "Keep every user-facing field in Simplified Chinese except question ids."
)

QUIZ_USER_PROMPT = """
Study material:
{input_text}

Return exactly one JSON object and do not wrap it in Markdown.

JSON schema:
{{
  "topic": "主题名称",
  "questions": [
    {{
      "id": "q1",
      "stem": "题干",
      "options": ["选项A", "选项B", "选项C", "选项D"],
      "answerIndex": 0,
      "explanation": "答案讲解",
      "knowledgePoint": "知识点"
    }}
  ]
}}

Requirements:
- Stay strictly within the provided study material.
- Return exactly 5 questions.
- ids must be q1 to q5.
- Each question must have exactly 4 options.
- answerIndex must be between 0 and 3.
- explanation must be short and specific.
""".strip()

REPORT_SYSTEM_PROMPT = (
    "You are a Chinese learning review coach for a mobile quiz app. "
    "Summarize the user's performance based only on the provided real quiz results. "
    "Keep every user-facing field in Simplified Chinese."
)

REPORT_USER_PROMPT = """
Topic: {topic}
Accuracy: {accuracy}%
Wrong question details: {wrong_points}

Return exactly one JSON object and do not wrap it in Markdown.

JSON schema:
{{
  "summary": "本轮学习总结",
  "weakPoints": ["薄弱点1"],
  "suggestions": ["建议1", "建议2"]
}}

Requirements:
- Base the output only on the provided wrong question details and accuracy.
- Keep the summary concise and actionable.
- weakPoints and suggestions should each contain at most 5 items.
""".strip()


def build_quiz_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", QUIZ_SYSTEM_PROMPT),
            ("human", QUIZ_USER_PROMPT),
        ]
    )


def build_report_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", REPORT_SYSTEM_PROMPT),
            ("human", REPORT_USER_PROMPT),
        ]
    )
