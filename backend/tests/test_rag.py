from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.curated_import import import_curated_payload
from app.database import Base
from app.llm import AiQuizDraft
from app.models import KnowledgeChunk, KnowledgeCollection, QuestionBankItem
from app.schemas import QuizQuestion
from app.services import LearningService


class CountingAiClient:
    model_name = "fake-rag-model"
    quiz_prompt_version = "quiz-rag-test-v1"
    report_prompt_version = "report-rag-test-v1"

    def __init__(self):
        self.quiz_calls: list[dict] = []

    def generate_quiz(
        self,
        input_text: str,
        *,
        retrieved_context: str | None = None,
        question_count: int = 5,
    ) -> AiQuizDraft:
        self.quiz_calls.append(
            {
                "input_text": input_text,
                "retrieved_context": retrieved_context,
                "question_count": question_count,
            }
        )
        return AiQuizDraft(
            topic=input_text,
            questions=[
                QuizQuestion(
                    id=f"ai-{index}",
                    stem=f"AI question {index}",
                    options=["A", "B", "C", "D"],
                    answerIndex=0,
                    explanation="AI explanation",
                    knowledgePoint="AI point",
                )
                for index in range(1, question_count + 1)
            ],
        )

    def generate_report(self, topic, questions, answers, accuracy):
        raise AssertionError("not needed")


def build_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def add_collection(db, *, question_count: int, with_chunk: bool = True):
    collection = KnowledgeCollection(
        title="AI Agent 入门",
        description="AI Agent 定义、能力和工具调用",
        source_type="curated",
        tags_json=["AI Agent", "RAG"],
    )
    db.add(collection)
    db.flush()

    if with_chunk:
        db.add(
            KnowledgeChunk(
                collection_id=collection.id,
                title="AI Agent 定义",
                content="AI Agent 是能够感知环境、规划任务并调用工具完成目标的软件实体。",
                source_ref="manual",
                tags_json=["AI Agent"],
            )
        )

    for index in range(1, question_count + 1):
        db.add(
            QuestionBankItem(
                collection_id=collection.id,
                stem=f"AI Agent 题库题 {index}",
                options_json=["感知环境并采取行动", "只会聊天", "只会搜索", "只会存储"],
                answer_index=0,
                explanation="AI Agent 的关键是感知、规划和行动。",
                knowledge_point="AI Agent 定义",
                difficulty="easy",
                tags_json=["AI Agent"],
            )
        )
    db.commit()


def test_generate_quiz_returns_curated_questions_without_ai_call():
    db = build_db()
    add_collection(db, question_count=5)
    ai_client = CountingAiClient()
    service = LearningService(ai_client=ai_client, db=db)

    response = service.generate_quiz("AI Agent")

    assert ai_client.quiz_calls == []
    assert len(response.questions) == 5
    assert response.retrievalVersion == "curated-rag-v1"
    assert {question.sourceType for question in response.questions} == {"curated_question"}
    assert response.questions[0].id == "q1"


def test_generate_quiz_uses_ai_only_for_missing_questions():
    db = build_db()
    add_collection(db, question_count=3)
    ai_client = CountingAiClient()
    service = LearningService(ai_client=ai_client, db=db)

    response = service.generate_quiz("AI Agent")

    assert len(response.questions) == 5
    assert ai_client.quiz_calls[0]["question_count"] == 2
    assert "AI Agent 是能够感知环境" in ai_client.quiz_calls[0]["retrieved_context"]
    assert [question.sourceType for question in response.questions] == [
        "curated_question",
        "curated_question",
        "curated_question",
        "rag_generated",
        "rag_generated",
    ]


def test_generate_quiz_falls_back_to_plain_ai_when_no_context_matches():
    db = build_db()
    add_collection(db, question_count=5)
    ai_client = CountingAiClient()
    service = LearningService(ai_client=ai_client, db=db)

    response = service.generate_quiz("基金定投")

    assert len(response.questions) == 5
    assert ai_client.quiz_calls[0]["question_count"] == 5
    assert ai_client.quiz_calls[0]["retrieved_context"] is None
    assert response.retrievalVersion is None
    assert {question.sourceType for question in response.questions} == {"ai_generated"}


def test_import_curated_payload_upserts_questions_and_chunks():
    db = build_db()

    count = import_curated_payload(
        db,
        {
            "collections": [
                {
                    "title": "产品经理面试",
                    "description": "需求分析和指标设计",
                    "tags": ["产品", "面试"],
                    "chunks": [
                        {
                            "title": "需求优先级",
                            "content": "需求优先级可以结合用户价值、业务价值和实现成本判断。",
                            "sourceRef": "manual",
                            "tags": ["优先级"],
                        }
                    ],
                    "questions": [
                        {
                            "stem": "判断需求优先级时最应该综合考虑什么？",
                            "options": ["用户价值、业务价值和实现成本", "老板偏好", "页面颜色", "发布时间"],
                            "answerIndex": 0,
                            "explanation": "优先级判断需要同时考虑价值和成本。",
                            "knowledgePoint": "需求优先级",
                            "tags": ["优先级"],
                        }
                    ],
                }
            ]
        },
    )

    assert count == 2
    assert db.query(KnowledgeCollection).count() == 1
    assert db.query(KnowledgeChunk).count() == 1
    assert db.query(QuestionBankItem).count() == 1
