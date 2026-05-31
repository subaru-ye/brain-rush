from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import KnowledgeChunk, KnowledgeCollection
from app.rag_eval import run_rag_eval


def build_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def seed_eval_data(db):
    collection = KnowledgeCollection(
        title="RAG 知识库",
        description="Eval collection",
        source_type="curated",
        tags_json=["RAG"],
    )
    db.add(collection)
    db.flush()
    db.add(
        KnowledgeChunk(
            collection_id=collection.id,
            title="RAG 的基本定义",
            content="RAG 会先检索外部知识，再把检索结果作为上下文提供给语言模型。",
            source_ref="eval",
            tags_json=["RAG"],
            is_active=True,
        )
    )
    db.commit()


def test_rag_eval_reports_title_match_hits():
    db = build_db()
    seed_eval_data(db)

    summary = run_rag_eval(
        db,
        [
            {
                "query": "RAG 为什么要检索外部知识",
                "category": "fundamentals",
                "expectedMatches": [
                    {
                        "kind": "chunk",
                        "collectionTitle": "RAG 知识库",
                        "title": "RAG 的基本定义",
                    }
                ],
            }
        ],
    ).to_dict()

    assert summary["total"] == 1
    assert summary["top1"] == 1.0
    assert summary["top3"] == 1.0
    assert summary["top5"] == 1.0
    assert summary["failures"] == []
    assert summary["categoryOrder"] == ["fundamentals"]
    assert summary["byCategory"]["fundamentals"]["total"] == 1
    assert summary["byCategory"]["fundamentals"]["top1"] == 1.0
    assert summary["byCategory"]["fundamentals"]["failures"] == []


def test_rag_eval_reports_failures_with_actual_matches():
    db = build_db()
    seed_eval_data(db)

    summary = run_rag_eval(
        db,
        [
            {
                "query": "RAG 为什么要检索外部知识",
                "category": "fundamentals",
                "expectedMatches": [
                    {
                        "kind": "chunk",
                        "collectionTitle": "RAG 知识库",
                        "title": "不存在的标题",
                    }
                ],
            }
        ],
    ).to_dict()

    assert summary["total"] == 1
    assert summary["top5"] == 0.0
    assert summary["failures"][0]["category"] == "fundamentals"
    assert summary["failures"][0]["actualMatches"][0]["title"] == "RAG 的基本定义"
    assert "keywordRank" in summary["failures"][0]["actualMatches"][0]
    assert "vectorRank" in summary["failures"][0]["actualMatches"][0]
    assert "fusionMethod" in summary["failures"][0]["actualMatches"][0]
    assert summary["byCategory"]["fundamentals"]["top5"] == 0.0
    assert summary["byCategory"]["fundamentals"]["failures"][0]["category"] == "fundamentals"
    assert (
        summary["byCategory"]["fundamentals"]["failures"][0]["actualMatches"][0]["title"]
        == "RAG 的基本定义"
    )


def test_rag_eval_groups_legacy_cases_as_uncategorized():
    db = build_db()
    seed_eval_data(db)

    summary = run_rag_eval(
        db,
        [
            {
                "query": "RAG 为什么要检索外部知识",
                "expectedMatches": [
                    {
                        "kind": "chunk",
                        "collectionTitle": "RAG 知识库",
                        "title": "RAG 的基本定义",
                    }
                ],
            }
        ],
    ).to_dict()

    assert summary["categoryOrder"] == ["uncategorized"]
    assert summary["byCategory"]["uncategorized"]["total"] == 1
    assert summary["byCategory"]["uncategorized"]["top5"] == 1.0


def test_rag_eval_sorts_question_and_chunk_matches_by_total_score(monkeypatch):
    def fake_debug_retrieve_curated_context(db, query, limit):
        return SimpleNamespace(
            questions=[
                SimpleNamespace(
                    kind="question",
                    collection_title="RAG 知识库",
                    title="Generic question",
                    total_score=0.01,
                )
            ],
            chunks=[
                SimpleNamespace(
                    kind="chunk",
                    collection_title="RAG 知识库",
                    title="Expected chunk",
                    total_score=0.03,
                )
            ],
        )

    monkeypatch.setattr("app.rag_eval.debug_retrieve_curated_context", fake_debug_retrieve_curated_context)

    summary = run_rag_eval(
        None,  # type: ignore[arg-type]
        [
            {
                "query": "expected",
                "category": "chunking",
                "expectedMatches": [
                    {
                        "kind": "chunk",
                        "collectionTitle": "RAG 知识库",
                        "title": "Expected chunk",
                    }
                ],
            }
        ],
    ).to_dict()

    assert summary["top1"] == 1.0
    assert summary["byCategory"]["chunking"]["top1"] == 1.0
    assert summary["failures"] == []


def test_rag_eval_handles_empty_cases():
    db = build_db()

    summary = run_rag_eval(db, []).to_dict()

    assert summary["total"] == 0
    assert summary["top1"] == 0.0
    assert summary["failures"] == []
    assert summary["byCategory"] == {}
    assert summary["categoryOrder"] == []
