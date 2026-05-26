from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from .database import SessionLocal
from .rag import debug_retrieve_curated_context


TOP_KS = (1, 3, 5)


@dataclass
class EvalSummary:
    total: int
    hits: dict[int, int]
    failures: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "top1": _rate(self.hits.get(1, 0), self.total),
            "top3": _rate(self.hits.get(3, 0), self.total),
            "top5": _rate(self.hits.get(5, 0), self.total),
            "hits": {f"top{k}": self.hits.get(k, 0) for k in TOP_KS},
            "failures": self.failures,
        }


def load_eval_cases(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("RAG eval file must contain a cases list")
    return cases


def run_rag_eval(db: Session, cases: list[dict[str, Any]]) -> EvalSummary:
    hits = {k: 0 for k in TOP_KS}
    failures: list[dict[str, Any]] = []

    for case in cases:
        query = str(case.get("query", "")).strip()
        if not query:
            continue
        limit = int(case.get("limit", 5))
        expected = case.get("expectedMatches", [])
        result = debug_retrieve_curated_context(db, query, limit=max(limit, max(TOP_KS)))
        matches = [*result.questions, *result.chunks]

        case_hits = {k: _case_hits(matches, expected, k) for k in TOP_KS}
        for k, is_hit in case_hits.items():
            if is_hit:
                hits[k] += 1
        if not case_hits[5]:
            failures.append(
                {
                    "query": query,
                    "expectedMatches": expected,
                    "actualMatches": [
                        {
                            "kind": match.kind,
                            "collectionTitle": match.collection_title,
                            "title": match.title,
                            "totalScore": round(match.total_score, 4),
                        }
                        for match in matches[:5]
                    ],
                }
            )

    total = len([case for case in cases if str(case.get("query", "")).strip()])
    return EvalSummary(total=total, hits=hits, failures=failures)


def run_rag_eval_file(path: str | Path) -> dict[str, Any]:
    cases = load_eval_cases(path)
    with SessionLocal() as db:
        return run_rag_eval(db, cases).to_dict()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval results.")
    parser.add_argument("path", help="Path to rag-eval.json")
    args = parser.parse_args()
    print(json.dumps(run_rag_eval_file(args.path), ensure_ascii=False, indent=2))


def _case_hits(matches, expected: list[dict[str, Any]], top_k: int) -> bool:
    if not expected:
        return False
    return any(_matches_expected(match, expected_item) for match in matches[:top_k] for expected_item in expected)


def _matches_expected(match, expected: dict[str, Any]) -> bool:
    return (
        _normalize(match.kind) == _normalize(str(expected.get("kind", "")))
        and _normalize(match.collection_title) == _normalize(str(expected.get("collectionTitle", "")))
        and _normalize(match.title) == _normalize(str(expected.get("title", "")))
    )


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _rate(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(value / total, 4)


if __name__ == "__main__":
    main()
