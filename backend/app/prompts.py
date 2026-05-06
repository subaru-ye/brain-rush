from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


QUIZ_PROMPT_VERSION = "quiz-v2"
REPORT_PROMPT_VERSION = "report-v1"

QUIZ_SYSTEM_PROMPT = (
    "You are a Chinese learning coach for a mobile quiz app. "
    "Turn the user's study material into concise, accurate quiz questions. "
    "Keep every user-facing field in Simplified Chinese except question ids."
)

QUIZ_USER_PROMPT = """
Study material:
{input_text}

Retrieved context:
{retrieved_context}

Target question count: {question_count}

Return exactly one JSON object and do not wrap it in Markdown.

JSON schema:
{{
  "topic": "主题名称",
  "questions": [
    {{
      "id": "q1",
      "stem": "题干",
      "questionType": "single_choice",
      "options": ["选项A", "选项B", "选项C", "选项D"],
      "answerIndexes": [0],
      "explanation": "答案讲解",
      "knowledgePoint": "知识点"
    }}
  ]
}}

Requirements:
- Stay strictly within the provided study material.
- If retrieved context is not "None", only use facts that appear in the retrieved context.
- Return exactly {question_count} questions.
- ids must start at q1 and increase by 1.
- Mix question types when question_count is 5: 3 single_choice, 1 multiple_choice, and 1 true_false.
- questionType must be one of single_choice, multiple_choice, true_false.
- single_choice must have exactly 4 options and exactly one answerIndexes item.
- multiple_choice must have exactly 4 options and 2 or 3 answerIndexes items.
- true_false must have exactly 2 options and exactly one answerIndexes item.
- answerIndexes values must point to existing options.
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
