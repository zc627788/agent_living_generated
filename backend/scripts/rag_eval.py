"""简单的 RAG 回归评测脚本。

用于在本地快速观察召回命中率和 MRR，帮助调整切片与检索参数。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "evals" / "rag_cases.jsonl"
sys.path.insert(0, str(ROOT))

from app.models.schemas import RetrievalOptions
from app.services.retriever import retriever


def score_case(case: dict, options: RetrievalOptions) -> tuple[int, float]:
    """计算单条样例的首个命中排名与倒数排名分数。"""
    results = retriever.search(case["query"], case.get("topic_type", ""), options)
    expected_keywords = [item.lower() for item in case.get("expected_keywords", [])]

    hit_rank = 0
    for index, result in enumerate(results, 1):
        haystack = " ".join([result.title, result.snippet, result.section_path]).lower()
        if any(keyword in haystack for keyword in expected_keywords):
            hit_rank = index
            break

    reciprocal_rank = 1 / hit_rank if hit_rank else 0.0
    return hit_rank, reciprocal_rank


def main() -> None:
    """遍历评测集并打印整体指标。"""
    options = RetrievalOptions(limit=6, candidate_multiplier=3, keyword_weight=0.06, neighbor_hops=1)
    cases = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]

    hit_count = 0
    rr_total = 0.0
    for case in cases:
        hit_rank, reciprocal_rank = score_case(case, options)
        hit_count += 1 if hit_rank else 0
        rr_total += reciprocal_rank
        print(
            json.dumps(
                {
                    "query": case["query"],
                    "topic_type": case.get("topic_type", ""),
                    "hit_rank": hit_rank,
                    "reciprocal_rank": round(reciprocal_rank, 3),
                },
                ensure_ascii=False,
            )
        )

    print(
        json.dumps(
            {
                "cases": len(cases),
                "hit_rate": round(hit_count / max(len(cases), 1), 3),
                "mrr": round(rr_total / max(len(cases), 1), 3),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
