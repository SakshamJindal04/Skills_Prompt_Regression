"""
Unit tests for extended skill registry, selectors, and benchmarking (core.skills).
"""

from unittest.mock import MagicMock
from core.skills import (
    SkillRegistry,
    EmbeddingSelector,
    BM25Selector,
    EmbeddingLLMSelector,
    run_skill_benchmark,
)


def test_pseudo_embedding_fallback():
    emb = EmbeddingSelector._pseudo_embedding("Calculate summary metrics", dim=64)
    assert len(emb) == 64
    assert sum(x * x for x in emb) > 0.99  # Normalized vector


def test_embedding_llm_selector_mocked():
    mock_registry = SkillRegistry()
    mock_client = MagicMock()
    mock_client.embed.return_value = [0.1] * 128
    mock_resp = MagicMock()
    mock_resp.text = '{"selected_skill": "write-sql", "reason": "Requires SQL query generation"}'
    mock_client.generate.return_value = mock_resp

    selector = EmbeddingLLMSelector(mock_registry, client=mock_client)
    selector.embedding_selector.select = MagicMock(return_value=([("write-sql", 0.85), ("draft-email", 0.70)], 10.0))
    ranked, lat = selector.select("Write SQL queries to join database tables", top_k=2)

    assert len(ranked) >= 1
    assert ranked[0][0] == "write-sql"
    assert ranked[0][1] == 1.0


def test_run_skill_benchmark_mocked():
    mock_registry = SkillRegistry()
    items = [
        {"input": "Calculate total sum of expenses", "expected_skill": "data_analysis"},
        {"input": "Format customer phone numbers", "expected_skill": "data_cleaning"},
    ]

    mock_client = MagicMock()
    mock_client.embed.return_value = [0.1] * 128

    res_emb = run_skill_benchmark(items, selector_method="embedding", registry=mock_registry, client=mock_client)
    assert "top1" in res_emb
    assert "top3" in res_emb
    assert "latency_mean" in res_emb

    res_bm25 = run_skill_benchmark(items, selector_method="bm25", registry=mock_registry, client=mock_client)
    assert "top1" in res_bm25
