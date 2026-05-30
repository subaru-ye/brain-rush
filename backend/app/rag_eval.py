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
    by_category: dict[str, "EvalSummary"]
    category_order: list[str]

    def to_dict(self) -> dict[str, Any]:
        payload = _summary_payload(self.total, self.hits, self.failures)
        payload["byCategory"] = {
            category: _summary_payload(
                self.by_category[category].total,
                self.by_category[category].hits,
                self.by_category[category].failures,
            )
            for category in self.category_order
            if category in self.by_category
        }
        payload["categoryOrder"] = self.category_order
        return payload


def load_eval_cases(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = payload.get("cases", []) if isinstance(payload, dict) else payload
    if not isinstance(cases, list):
        raise ValueError("RAG eval file must contain a cases list")
    return cases


def run_rag_eval(db: Session, cases: list[dict[str, Any]]) -> EvalSummary:
    hits = {k: 0 for k in TOP_KS}
    failures: list[dict[str, Any]] = []
    category_totals: dict[str, int] = {}
    category_hits: dict[str, dict[int, int]] = {}
    category_failures: dict[str, list[dict[str, Any]]] = {}
    category_order: list[str] = []

    for case in cases:
        query = str(case.get("query", "")).strip()
        if not query:
            continue
        category = _case_category(case)
        if category not in category_totals:
            category_totals[category] = 0
            category_hits[category] = {k: 0 for k in TOP_KS}
            category_failures[category] = []
            category_order.append(category)
        category_totals[category] += 1
        limit = int(case.get("limit", 5))
        expected = case.get("expectedMatches", [])
        result = debug_retrieve_curated_context(db, query, limit=max(limit, max(TOP_KS)))
        matches = [*result.questions, *result.chunks]

        case_hits = {k: _case_hits(matches, expected, k) for k in TOP_KS}
        for k, is_hit in case_hits.items():
            if is_hit:
                hits[k] += 1
                category_hits[category][k] += 1
        if not case_hits[5]:
            failure = {
                "query": query,
                "category": category,
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
            failures.append(failure)
            category_failures[category].append(failure)

    total = len([case for case in cases if str(case.get("query", "")).strip()])
    by_category = {
        category: EvalSummary(
            total=category_totals[category],
            hits=category_hits[category],
            failures=category_failures[category],
            by_category={},
            category_order=[],
        )
        for category in category_order
    }
    return EvalSummary(
        total=total,
        hits=hits,
        failures=failures,
        by_category=by_category,
        category_order=category_order,
    )


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


def _case_category(case: dict[str, Any]) -> str:
    category = str(case.get("category", "")).strip()
    return category or "uncategorized"


def _summary_payload(total: int, hits: dict[int, int], failures: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": total,
        "top1": _rate(hits.get(1, 0), total),
        "top3": _rate(hits.get(3, 0), total),
        "top5": _rate(hits.get(5, 0), total),
        "hits": {f"top{k}": hits.get(k, 0) for k in TOP_KS},
        "failures": failures,
    }


def _normalize(value: str) -> str:
    return value.strip().casefold()


def _rate(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(value / total, 4)


if __name__ == "__main__":
    main()
