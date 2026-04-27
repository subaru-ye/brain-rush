from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from .config import Settings
from .schemas import QuizQuestion, UserAnswer


class AiQuizDraft(BaseModel):
    topic: str = Field(min_length=1, max_length=120)
    questions: list[QuizQuestion] = Field(min_length=5, max_length=5)


class AiReportDraft(BaseModel):
    summary: str = Field(min_length=1, max_length=800)
    weakPoints: list[str] = Field(default_factory=list, max_length=5)
    suggestions: list[str] = Field(default_factory=list, max_length=5)


TModel = TypeVar("TModel", bound=BaseModel)


def parse_json_model(content: object, model: type[TModel]) -> TModel:
    if isinstance(content, str):
        raw_text = content.strip()
    else:
        raw_text = json.dumps(content, ensure_ascii=False)

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
    if fence_match:
        raw_text = fence_match.group(1).strip()

    if not raw_text.startswith("{"):
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start >= 0 and end > start:
            raw_text = raw_text[start : end + 1]

    return model.model_validate_json(raw_text)


class LangChainAiClient:
    def __init__(self, settings: Settings):
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for real AI generation")

        self.llm = ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            temperature=0.4,
        )

    def generate_quiz(self, input_text: str) -> AiQuizDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个擅长把知识点转成闯关题的中文学习教练。"
                    "请生成严格适合移动端展示的 5 道单选题。"
                    "每题 4 个选项，只有一个正确答案，讲解要短且具体。"
                    "所有题目必须直接围绕用户提供的学习内容，不要切换到无关主题。",
                ),
                (
                    "human",
                    "用户要学习的内容是：{input_text}\n"
                    "请只围绕这个内容出题。\n\n"
                    "只返回 JSON，不要 Markdown，不要解释。JSON 结构必须是：\n"
                    "{{\n"
                    '  "topic": "主题名",\n'
                    '  "questions": [\n'
                    "    {{\n"
                    '      "id": "q1",\n'
                    '      "stem": "题干",\n'
                    '      "options": ["选项A", "选项B", "选项C", "选项D"],\n'
                    '      "answerIndex": 0,\n'
                    '      "explanation": "答案讲解",\n'
                    '      "knowledgePoint": "知识点"\n'
                    "    }}\n"
                    "  ]\n"
                    "}}\n"
                    "必须刚好 5 道题，id 从 q1 到 q5，answerIndex 必须是 0 到 3。",
                ),
            ]
        )
        chain = prompt | self.llm
        message = chain.invoke({"input_text": input_text})
        return parse_json_model(message.content, AiQuizDraft)

    def generate_report(
        self,
        topic: str,
        questions: list[QuizQuestion],
        answers: list[UserAnswer],
        accuracy: int,
    ) -> AiReportDraft:
        wrong_points = []
        answer_by_question = {answer.questionId: answer for answer in answers}
        for question in questions:
            answer = answer_by_question.get(question.id)
            if answer and not answer.isCorrect:
                wrong_points.append(
                    {
                        "stem": question.stem,
                        "knowledgePoint": question.knowledgePoint,
                        "correctAnswer": question.options[question.answerIndex],
                        "explanation": question.explanation,
                    }
                )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个中文学习复盘教练。"
                    "你只能基于前端提供的真实答题结果做总结，不要改写分数或正确率。"
                    "输出要适合小程序移动端阅读，短句、具体、有行动建议。",
                ),
                (
                    "human",
                    "主题：{topic}\n正确率：{accuracy}%\n错题信息：{wrong_points}\n"
                    "请生成总结、薄弱点和下一步建议。\n\n"
                    "只返回 JSON，不要 Markdown，不要解释。JSON 结构必须是：\n"
                    "{{\n"
                    '  "summary": "本轮学习总结",\n'
                    '  "weakPoints": ["薄弱点1"],\n'
                    '  "suggestions": ["建议1", "建议2"]\n'
                    "}}",
                ),
            ]
        )
        chain = prompt | self.llm
        message = chain.invoke(
            {
                "topic": topic,
                "accuracy": accuracy,
                "wrong_points": wrong_points,
            }
        )
        return parse_json_model(message.content, AiReportDraft)
