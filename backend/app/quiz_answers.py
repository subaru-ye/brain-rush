from __future__ import annotations

from typing import Any

from .schemas import QuizQuestion, UserAnswer


def get_answer_indexes(question: QuizQuestion | dict[str, Any]) -> list[int]:
    if isinstance(question, QuizQuestion):
        return sorted(dict.fromkeys(question.answerIndexes or [question.answerIndex]))
    raw_indexes = question.get("answerIndexes")
    if isinstance(raw_indexes, list) and raw_indexes:
        return sorted(dict.fromkeys(index for index in raw_indexes if isinstance(index, int)))
    raw_index = question.get("answerIndex")
    return [raw_index] if isinstance(raw_index, int) else []


def get_selected_indexes(answer: UserAnswer | dict[str, Any]) -> list[int]:
    if isinstance(answer, UserAnswer):
        return sorted(dict.fromkeys(answer.selectedIndexes or [answer.selectedIndex]))
    raw_indexes = answer.get("selectedIndexes")
    if isinstance(raw_indexes, list) and raw_indexes:
        return sorted(dict.fromkeys(index for index in raw_indexes if isinstance(index, int)))
    raw_index = answer.get("selectedIndex")
    return [raw_index] if isinstance(raw_index, int) else []


def is_answer_correct(question: QuizQuestion | dict[str, Any], answer: UserAnswer | dict[str, Any]) -> bool:
    return get_answer_indexes(question) == get_selected_indexes(answer)


def format_option_indexes(options: list[str], indexes: list[int]) -> str:
    labels = ["A", "B", "C", "D"]
    texts = []
    for index in indexes:
        if 0 <= index < len(options):
            texts.append(f"{labels[index]}，{options[index]}")
    return "；".join(texts)


def normalize_question_dump(question: QuizQuestion) -> dict[str, Any]:
    data = question.model_dump()
    data["answerIndexes"] = get_answer_indexes(question)
    data["answerIndex"] = data["answerIndexes"][0]
    data["questionType"] = question.questionType or "single_choice"
    return data


def normalize_answer_dump(answer: UserAnswer) -> dict[str, Any]:
    data = answer.model_dump()
    data["selectedIndexes"] = get_selected_indexes(answer)
    data["selectedIndex"] = data["selectedIndexes"][0]
    return data
