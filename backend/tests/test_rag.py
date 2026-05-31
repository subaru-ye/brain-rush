from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.curated_import import import_curated_payload, import_curated_payload_with_stats
from app.database import Base
from app.llm import AiQuizDraft
from app.models import KnowledgeChunk, KnowledgeCollection, KnowledgeDocument, QuestionBankItem
from app.rag import debug_retrieve_curated_context, retrieve_curated_context_with_client
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


class FakeEmbeddingClient:
    is_enabled = True
    model_name = "fake-embedding"
    version = "embedding-test-v1"

    def __init__(self, query_vector: list[float] | None = None):
        self.query_vector = query_vector or make_vector(0)
        self.embed_calls: list[list[str]] = []

    def embed_query(self, text: str) -> list[float]:
        return self.query_vector

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(texts)
        return [make_vector(index) for index, _ in enumerate(texts)]


class DisabledEmbeddingClient:
    is_enabled = False
    model_name = ""
    version = ""


def make_vector(index: int) -> list[float]:
    values = [0.0] * 1536
    values[index] = 1.0
    return values


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
        title="AI Agent intro",
        description="AI Agent definition, capabilities, and tool use",
        source_type="curated",
        tags_json=["AI Agent", "RAG"],
    )
    db.add(collection)
    db.flush()

    if with_chunk:
        db.add(
            KnowledgeChunk(
                collection_id=collection.id,
                title="AI Agent definition",
                content="AI Agent can perceive context, plan tasks, and call tools to complete goals.",
                source_ref="manual",
                tags_json=["AI Agent"],
            )
        )

    for index in range(1, question_count + 1):
        db.add(
            QuestionBankItem(
                collection_id=collection.id,
                stem=f"AI Agent curated question {index}",
                options_json=["Perceive and act", "Only chat", "Only search", "Only store"],
                answer_index=0,
                explanation="AI Agent is about perception, planning, and action.",
                knowledge_point="AI Agent definition",
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
    assert response.retrievalVersion == "hybrid-rag-v1.4"
    assert {question.sourceType for question in response.questions} == {"curated_question"}
    assert response.questions[0].id == "q1"
    assert response.questions[0].answerIndexes == [0]


def test_generate_quiz_uses_ai_only_for_missing_questions():
    db = build_db()
    add_collection(db, question_count=3)
    ai_client = CountingAiClient()
    service = LearningService(ai_client=ai_client, db=db)

    response = service.generate_quiz("AI Agent")

    assert len(response.questions) == 5
    assert ai_client.quiz_calls[0]["question_count"] == 2
    assert "AI Agent can perceive context" in ai_client.quiz_calls[0]["retrieved_context"]
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

    response = service.generate_quiz("fund investing")

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
                    "title": "Product interview",
                    "description": "Requirement analysis and metrics",
                    "tags": ["product", "interview"],
                    "chunks": [
                        {
                            "title": "Priority",
                            "content": "Priority can be judged by user value, business value, and implementation cost.",
                            "sourceRef": "manual",
                            "tags": ["priority"],
                        }
                    ],
                    "questions": [
                        {
                            "stem": "What should priority decisions consider?",
                            "options": ["Value and cost", "Boss preference", "Color", "Release time"],
                            "answerIndex": 0,
                            "explanation": "Priority decisions should consider value and cost.",
                            "knowledgePoint": "Priority",
                            "tags": ["priority"],
                        }
                    ],
                }
            ]
        },
    )

    assert count == 2
    assert db.query(KnowledgeCollection).count() == 1
    assert db.query(KnowledgeChunk).count() == 1
    assert db.query(KnowledgeChunk).one().document_id is None
    assert db.query(QuestionBankItem).count() == 1


def test_import_curated_payload_creates_documents_and_links_chunks():
    db = build_db()
    payload = {
        "collections": [
            {
                "title": "Documented RAG",
                "documents": [
                    {
                        "title": "RAG web source",
                        "sourceType": "web",
                        "sourceUri": "https://example.com/rag",
                        "metadata": {"section": "retrieval"},
                        "chunks": [
                            {
                                "title": "Document chunk",
                                "content": "Document level chunks should keep source lineage.",
                            }
                        ],
                    }
                ],
            }
        ]
    }

    first = import_curated_payload(db, payload)
    second = import_curated_payload(db, payload)

    document = db.query(KnowledgeDocument).one()
    chunk = db.query(KnowledgeChunk).one()
    assert first == 1
    assert second == 1
    assert db.query(KnowledgeDocument).count() == 1
    assert db.query(KnowledgeChunk).count() == 1
    assert document.title == "RAG web source"
    assert document.source_type == "web"
    assert document.source_uri == "https://example.com/rag"
    assert document.metadata_json == {"section": "retrieval"}
    assert chunk.document_id == document.id
    assert chunk.source_ref == "https://example.com/rag"


def test_import_curated_payload_allows_same_chunk_title_in_different_documents():
    db = build_db()

    import_curated_payload(
        db,
        {
            "collections": [
                {
                    "title": "Duplicate titles",
                    "documents": [
                        {
                            "title": "Doc A",
                            "sourceUri": "doc-a",
                            "chunks": [{"title": "Shared title", "content": "A content"}],
                        },
                        {
                            "title": "Doc B",
                            "sourceUri": "doc-b",
                            "chunks": [{"title": "Shared title", "content": "B content"}],
                        },
                    ],
                }
            ]
        },
    )

    chunks = sorted(db.query(KnowledgeChunk).all(), key=lambda item: item.content)
    assert len(chunks) == 2
    assert {chunk.title for chunk in chunks} == {"Shared title"}
    assert {chunk.document_id for chunk in chunks} == {
        document.id for document in db.query(KnowledgeDocument).all()
    }


def test_import_curated_payload_reuses_legacy_chunk_when_moving_under_document():
    db = build_db()
    legacy_payload = {
        "collections": [
            {
                "title": "Legacy migration",
                "chunks": [{"title": "Migrated chunk", "content": "Legacy content"}],
            }
        ]
    }
    document_payload = {
        "collections": [
            {
                "title": "Legacy migration",
                "documents": [
                    {
                        "title": "Migration source",
                        "sourceUri": "migration-source",
                        "chunks": [{"title": "Migrated chunk", "content": "Document content"}],
                    }
                ],
            }
        ]
    }

    import_curated_payload(db, legacy_payload)
    import_curated_payload(db, document_payload)

    document = db.query(KnowledgeDocument).one()
    chunk = db.query(KnowledgeChunk).one()
    assert chunk.document_id == document.id
    assert chunk.content == "Document content"
    assert chunk.source_ref == "migration-source"


def test_import_curated_payload_supports_multiple_choice_format():
    db = build_db()

    import_curated_payload(
        db,
        {
            "collections": [
                {
                    "title": "RAG intro",
                    "questions": [
                        {
                            "stem": "Which key steps does RAG include?",
                            "questionType": "multiple_choice",
                            "options": ["Retrieval", "Generation", "Skip context", "Only UI"],
                            "answerIndexes": [0, 1],
                            "explanation": "RAG includes retrieval and generation.",
                            "knowledgePoint": "RAG flow",
                        }
                    ],
                }
            ]
        },
    )

    item = db.query(QuestionBankItem).one()
    assert item.question_type == "multiple_choice"
    assert item.answer_indexes_json == [0, 1]


def test_hybrid_retrieval_uses_vector_matches_without_keyword_overlap():
    db = build_db()
    collection = KnowledgeCollection(title="Vector RAG", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        QuestionBankItem(
            collection_id=collection.id,
            stem="Completely different stem",
            options_json=["A", "B", "C", "D"],
            answer_index=0,
            answer_indexes_json=[0],
            question_type="single_choice",
            explanation="Different explanation",
            knowledge_point="Different point",
            difficulty="normal",
            tags_json=[],
            embedding=make_vector(0),
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "semantic query",
        embedding_client=FakeEmbeddingClient(query_vector=make_vector(0)),
    )

    assert context.retrieval_version == "hybrid-rag-v1.4"
    assert [item.stem for item in context.question_items] == ["Completely different stem"]


def test_rrf_fusion_promotes_results_ranked_by_both_keyword_and_vector():
    db = build_db()
    collection = KnowledgeCollection(title="RRF ranking", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add_all(
        [
            KnowledgeChunk(
                collection_id=collection.id,
                title="target target target",
                content="Keyword-only chunk with a much stronger raw keyword score.",
                source_ref="manual",
                tags_json=["target"],
            ),
            KnowledgeChunk(
                collection_id=collection.id,
                title="Semantic target",
                content="target",
                source_ref="manual",
                tags_json=[],
                embedding=make_vector(0),
            ),
        ]
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "target",
        embedding_client=FakeEmbeddingClient(query_vector=make_vector(0)),
    )

    assert context.retrieval_version == "hybrid-rag-v1.4"
    assert [chunk.title for chunk in context.chunks[:2]] == ["Semantic target", "target target target"]


def test_debug_retrieval_reports_keyword_and_vector_scores():
    db = build_db()
    collection = KnowledgeCollection(title="Vector RAG", source_type="curated", tags_json=["RAG"])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="RAG debug chunk",
            content="RAG debug retrieval content",
            source_ref="manual",
            tags_json=["RAG"],
            embedding=make_vector(0),
        )
    )
    db.add(
        QuestionBankItem(
            collection_id=collection.id,
            stem="RAG debug question",
            options_json=["A", "B", "C", "D"],
            answer_index=0,
            answer_indexes_json=[0],
            question_type="single_choice",
            explanation="RAG debug explanation",
            knowledge_point="RAG debug",
            difficulty="normal",
            tags_json=["RAG"],
            embedding=make_vector(0),
        )
    )
    db.commit()

    result = debug_retrieve_curated_context(
        db,
        "RAG debug",
        embedding_client=FakeEmbeddingClient(query_vector=make_vector(0)),
    )

    assert result.retrieval_version == "hybrid-rag-v1.4"
    assert result.questions[0].title == "RAG debug question"
    assert result.questions[0].keyword_score > 0
    assert result.questions[0].vector_score > 0
    assert result.questions[0].keyword_rank == 1
    assert result.questions[0].vector_rank == 1
    assert result.questions[0].fusion_method == "rrf"
    assert abs(result.questions[0].total_score - (1 / 61 + 1 / 61)) < 0.000001
    assert result.questions[0].total_score != result.questions[0].keyword_score + result.questions[0].vector_score
    assert sum(result.questions[0].keyword_score_breakdown.values()) == result.questions[0].keyword_score
    assert result.questions[0].to_dict()["fusionMethod"] == "rrf"
    assert result.questions[0].to_dict()["keywordRank"] == 1
    assert result.questions[0].to_dict()["vectorRank"] == 1
    assert result.chunks[0].title == "RAG debug chunk"
    assert result.chunks[0].source_ref == "manual"
    assert result.chunks[0].keyword_score_breakdown["title"] > 0


def test_keyword_retrieval_weights_title_and_tags_above_body_only_matches():
    db = build_db()
    collection = KnowledgeCollection(title="Keyword RAG", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add_all(
        [
            KnowledgeChunk(
                collection_id=collection.id,
                title="BM25 scoring",
                content="Search ranking overview.",
                source_ref="manual",
                tags_json=["ranking"],
            ),
            KnowledgeChunk(
                collection_id=collection.id,
                title="Search overview",
                content="BM25 can be used for keyword ranking.",
                source_ref="manual",
                tags_json=[],
            ),
        ]
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "BM25",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert context.retrieval_version == "hybrid-rag-v1.4"
    assert [chunk.title for chunk in context.chunks[:2]] == ["BM25 scoring", "Search overview"]


def test_keyword_retrieval_matches_technical_terms():
    db = build_db()
    collection = KnowledgeCollection(title="Technical RAG", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="pgvector HNSW settings",
            content="RAG systems can combine BM25 and pgvector HNSW indexes.",
            source_ref="manual",
            tags_json=["RAG", "BM25", "pgvector", "HNSW"],
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "RAG BM25 pgvector HNSW",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert [chunk.title for chunk in context.chunks] == ["pgvector HNSW settings"]


def test_keyword_retrieval_expands_chunk_synonyms():
    db = build_db()
    collection = KnowledgeCollection(title="RAG Chunking", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="文档切分的作用",
            content="长文档切分成较小的 chunk 后，检索器可以返回更聚焦的片段。",
            source_ref="manual",
            tags_json=["Chunk", "文档切分"],
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "资料切块为什么有用",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert [chunk.title for chunk in context.chunks] == ["文档切分的作用"]


def test_keyword_retrieval_matches_mixed_language_synonyms():
    db = build_db()
    collection = KnowledgeCollection(title="RAG Rerank", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="Rerank的定义与作用",
            content="Rerank 使用 Cross-Encoder 对初步召回的候选文档进行重排和精排。",
            source_ref="manual",
            tags_json=["RAG", "Rerank", "重排"],
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "精排 cross encoder 怎么提升相关性",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert [chunk.title for chunk in context.chunks] == ["Rerank的定义与作用"]


def test_keyword_retrieval_expands_final_answer_evaluation_phrase():
    db = build_db()
    collection = KnowledgeCollection(title="RAG Evaluation", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="RAG 评估的两个层面",
            content="RAG 评估需要同时看检索质量和生成质量，只看最终答案会掩盖检索阶段问题。",
            source_ref="manual",
            tags_json=["RAG评估", "检索质量", "生成质量"],
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "为什么只看最终答案会掩盖检索阶段问题",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert [chunk.title for chunk in context.chunks] == ["RAG 评估的两个层面"]


def test_keyword_retrieval_keeps_vector_database_metadata_ahead_of_pgvector_terms():
    db = build_db()
    collection = KnowledgeCollection(title="Vector DB", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add_all(
        [
            KnowledgeChunk(
                collection_id=collection.id,
                title="向量数据库在 RAG 中的角色",
                content="向量数据库通常还需要保存原文、来源、标签、是否启用等元数据，便于过滤和生成时引用。",
                source_ref="manual",
                tags_json=["向量数据库", "元数据"],
            ),
            KnowledgeChunk(
                collection_id=collection.id,
                title="pgvector 的距离与索引",
                content="pgvector 支持 cosine distance、IVFFlat 和 HNSW 索引。",
                source_ref="manual",
                tags_json=["pgvector", "HNSW", "cosine"],
            ),
        ]
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "向量数据库为什么还要保存原文和元数据",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert context.chunks[0].title == "向量数据库在 RAG 中的角色"


def test_keyword_retrieval_expands_retrieval_optimization_phrase():
    db = build_db()
    collection = KnowledgeCollection(title="RAG Optimization", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="RAG检索效果优化核心环节",
            content="RAG检索效果差通常出在文档切片、查询理解、检索策略三个核心环节。",
            source_ref="manual",
            tags_json=["RAG", "检索优化", "核心环节"],
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "RAG 检索效果差通常要优化哪些环节",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert [chunk.title for chunk in context.chunks] == ["RAG检索效果优化核心环节"]


def test_keyword_retrieval_expands_pure_vector_retrieval_phrase():
    db = build_db()
    collection = KnowledgeCollection(title="Hybrid RAG", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add_all(
        [
            KnowledgeChunk(
                collection_id=collection.id,
                title="关键词检索与向量检索的互补性",
                content="关键词检索和向量检索可以互相补充。",
                source_ref="manual",
                tags_json=["混合检索", "向量检索"],
            ),
            KnowledgeChunk(
                collection_id=collection.id,
                title="混合检索与重排序优化",
                content="解决纯向量检索对专有名词、代码片段、数字召回率低的问题，采用向量检索+BM25关键词检索组合，通过RRF算法融合排序。",
                source_ref="manual",
                tags_json=["RAG", "混合检索", "重排序"],
            ),
        ]
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "为什么纯向量检索对专有名词和数字不稳定",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert context.chunks[0].title == "混合检索与重排序优化"


def test_keyword_retrieval_expands_reliability_limitations_phrase():
    db = build_db()
    collection = KnowledgeCollection(title="RAG Reliability", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="RAG的局限性与解决方案",
            content="RAG 的局限性包括检索质量、上下文窗口和实时性问题，可通过 Rerank、Top-K 截断、摘要压缩和定期更新缓解。",
            source_ref="manual",
            tags_json=["RAG", "局限性", "解决方案"],
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "RAG 有哪些局限性，怎么缓解",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert [chunk.title for chunk in context.chunks] == ["RAG的局限性与解决方案"]


def test_keyword_retrieval_uses_document_title_and_source():
    db = build_db()
    collection = KnowledgeCollection(title="Documented RAG", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    document = KnowledgeDocument(
        collection_id=collection.id,
        title="knowledge_documents handbook",
        source_type="manual",
        source_uri="manual:knowledge_documents",
        metadata_json={},
        status="active",
        is_active=True,
    )
    db.add(document)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            document_id=document.id,
            title="Document lineage",
            content="Chunks should retain source lineage.",
            source_ref="manual",
            tags_json=[],
        )
    )
    db.commit()

    result = debug_retrieve_curated_context(
        db,
        "资料来源 document_id",
        embedding_client=DisabledEmbeddingClient(),
    )

    assert result.chunks[0].title == "Document lineage"
    assert result.chunks[0].keyword_score_breakdown["source"] > 0
    assert set(result.chunks[0].keyword_score_breakdown) == {
        "title",
        "tags",
        "body",
        "source",
        "collection",
    }


def test_retrieval_ignores_inactive_collections():
    db = build_db()
    inactive = KnowledgeCollection(
        title="Inactive",
        source_type="curated",
        tags_json=["AI Agent"],
        is_active=False,
    )
    db.add(inactive)
    db.flush()
    db.add(
        QuestionBankItem(
            collection_id=inactive.id,
            stem="AI Agent inactive question",
            options_json=["A", "B", "C", "D"],
            answer_index=0,
            answer_indexes_json=[0],
            question_type="single_choice",
            explanation="AI Agent explanation",
            knowledge_point="AI Agent",
            difficulty="normal",
            tags_json=["AI Agent"],
            embedding=make_vector(0),
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "AI Agent",
        embedding_client=FakeEmbeddingClient(query_vector=make_vector(0)),
    )

    assert context.question_items == []
    assert context.chunks == []


def test_retrieval_ignores_chunks_from_inactive_documents():
    db = build_db()
    collection = KnowledgeCollection(title="Document status", source_type="curated", tags_json=[])
    db.add(collection)
    db.flush()
    document = KnowledgeDocument(
        collection_id=collection.id,
        title="Inactive document",
        source_type="manual",
        source_uri="",
        metadata_json={},
        status="inactive",
        is_active=True,
    )
    db.add(document)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            document_id=document.id,
            title="Document inactive chunk",
            content="RAG document status should hide this chunk.",
            source_ref="manual",
            tags_json=["RAG"],
            embedding=make_vector(0),
        )
    )
    db.commit()

    context = retrieve_curated_context_with_client(
        db,
        "RAG document status",
        embedding_client=FakeEmbeddingClient(query_vector=make_vector(0)),
    )

    assert context.chunks == []


def test_import_curated_payload_generates_and_skips_embeddings():
    db = build_db()
    embedding_client = FakeEmbeddingClient()
    payload = {
        "collections": [
            {
                "title": "Embedding Import",
                "chunks": [{"title": "Chunk", "content": "Chunk content"}],
                "questions": [
                    {
                        "stem": "Question stem",
                        "options": ["A", "B", "C", "D"],
                        "answerIndex": 0,
                        "explanation": "Explanation",
                        "knowledgePoint": "Point",
                    }
                ],
            }
        ]
    }

    first = import_curated_payload_with_stats(db, payload, embedding_client=embedding_client)
    second = import_curated_payload_with_stats(db, payload, embedding_client=embedding_client)

    assert first.total_imported == 2
    assert first.embeddings_generated == 2
    assert first.embeddings_skipped == 0
    assert second.embeddings_generated == 0
    assert second.embeddings_skipped == 2


def test_import_curated_payload_regenerates_embedding_when_content_changes():
    db = build_db()
    embedding_client = FakeEmbeddingClient()
    payload = {
        "collections": [
            {
                "title": "Embedding Import",
                "chunks": [{"title": "Chunk", "content": "Chunk content"}],
            }
        ]
    }
    import_curated_payload_with_stats(db, payload, embedding_client=embedding_client)
    changed_payload = {
        "collections": [
            {
                "title": "Embedding Import",
                "chunks": [{"title": "Chunk", "content": "Changed chunk content"}],
            }
        ]
    }

    stats = import_curated_payload_with_stats(db, changed_payload, embedding_client=embedding_client)

    assert stats.embeddings_generated == 1
    assert stats.embeddings_skipped == 0


def test_import_curated_payload_regenerates_chunk_embedding_when_document_changes():
    db = build_db()
    embedding_client = FakeEmbeddingClient()
    payload = {
        "collections": [
            {
                "title": "Embedding Document Import",
                "documents": [
                    {
                        "title": "Original document",
                        "sourceUri": "stable-source",
                        "chunks": [{"title": "Chunk", "content": "Chunk content"}],
                    }
                ],
            }
        ]
    }
    import_curated_payload_with_stats(db, payload, embedding_client=embedding_client)
    changed_payload = {
        "collections": [
            {
                "title": "Embedding Document Import",
                "documents": [
                    {
                        "title": "Renamed document",
                        "sourceUri": "stable-source",
                        "chunks": [{"title": "Chunk", "content": "Chunk content"}],
                    }
                ],
            }
        ]
    }

    stats = import_curated_payload_with_stats(db, changed_payload, embedding_client=embedding_client)

    assert stats.embeddings_generated == 1
    assert stats.embeddings_skipped == 0

