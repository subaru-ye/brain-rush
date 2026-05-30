from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.curated_import import import_curated_payload
from app.database import Base
from app.models import KnowledgeChunk, QuestionBankItem
from app.rag_data_check import check_rag_knowledge_data


def write_knowledge_file(tmp_path, payload):
    path = tmp_path / "rag-knowledge.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def build_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)()


def sample_payload():
    return {
        "collections": [
            {
                "title": "RAG 知识库",
                "description": "RAG data check fixture",
                "documents": [
                    {
                        "title": "RAG 文档导入示例",
                        "sourceType": "manual",
                        "sourceUri": "manual:rag-document-import-example",
                        "chunks": [
                            {
                                "title": "knowledge_documents 的导入作用",
                                "content": "document 下的 chunk 会写入 document_id。",
                            }
                        ],
                    }
                ],
                "chunks": [
                    {
                        "title": "RAG 的基本定义",
                        "content": "RAG 会先检索外部知识，再把结果交给模型生成。",
                    }
                ],
                "questions": [
                    {
                        "stem": "RAG 的核心思想是什么？",
                        "options": ["先检索再生成", "只随机生成", "只做 UI", "只存图片"],
                        "answerIndex": 0,
                        "explanation": "RAG 的核心是检索增强生成。",
                        "knowledgePoint": "RAG 基础概念",
                    }
                ],
            }
        ]
    }


def test_rag_data_check_reports_ok_when_imported_data_matches(tmp_path):
    db = build_db()
    payload = sample_payload()
    import_curated_payload(db, payload)
    path = write_knowledge_file(tmp_path, payload)

    result = check_rag_knowledge_data(db, path)

    assert result["ok"] is True
    assert result["summary"]["expected"] == {
        "collections": 1,
        "documents": 1,
        "chunks": 2,
        "questions": 1,
    }
    assert result["summary"]["missing"]["documents"] == 0
    assert result["summary"]["missing"]["chunks"] == 0
    assert result["summary"]["missing"]["questions"] == 0


def test_rag_data_check_reports_missing_document_chunk_and_question(tmp_path):
    db = build_db()
    payload = sample_payload()
    import_curated_payload(
        db,
        {
            "collections": [
                {
                    "title": "RAG 知识库",
                    "chunks": [
                        {
                            "title": "RAG 的基本定义",
                            "content": "RAG 会先检索外部知识，再把结果交给模型生成。",
                        }
                    ],
                }
            ]
        },
    )
    path = write_knowledge_file(tmp_path, payload)

    result = check_rag_knowledge_data(db, path)

    assert result["ok"] is False
    assert result["summary"]["missing"]["documents"] == 1
    assert result["summary"]["missing"]["chunks"] == 1
    assert result["summary"]["missing"]["questions"] == 1
    assert result["missing"]["documents"][0]["title"] == "RAG 文档导入示例"
    assert result["missing"]["chunks"][0]["title"] == "knowledge_documents 的导入作用"
    assert result["missing"]["questions"][0]["title"] == "RAG 的核心思想是什么？"


def test_rag_data_check_reports_inactive_records_as_unusable(tmp_path):
    db = build_db()
    payload = sample_payload()
    import_curated_payload(db, payload)
    db.query(KnowledgeChunk).filter_by(title="RAG 的基本定义").one().is_active = False
    db.query(QuestionBankItem).filter_by(stem="RAG 的核心思想是什么？").one().is_active = False
    db.commit()
    path = write_knowledge_file(tmp_path, payload)

    result = check_rag_knowledge_data(db, path)

    assert result["ok"] is False
    assert result["summary"]["inactive"]["chunks"] == 1
    assert result["summary"]["inactive"]["questions"] == 1
    assert result["inactive"]["chunks"][0]["title"] == "RAG 的基本定义"
    assert result["inactive"]["questions"][0]["title"] == "RAG 的核心思想是什么？"


def test_rag_data_check_reports_document_title_mismatch_by_source_uri(tmp_path):
    db = build_db()
    payload = sample_payload()
    import_curated_payload(db, payload)
    changed_payload = sample_payload()
    changed_payload["collections"][0]["documents"][0]["title"] = "更新后的资料标题"
    path = write_knowledge_file(tmp_path, changed_payload)

    result = check_rag_knowledge_data(db, path)

    assert result["ok"] is False
    assert result["summary"]["titleMismatches"]["documents"] == 1
    mismatch = result["titleMismatches"]["documents"][0]
    assert mismatch["title"] == "更新后的资料标题"
    assert mismatch["actualTitle"] == "RAG 文档导入示例"
