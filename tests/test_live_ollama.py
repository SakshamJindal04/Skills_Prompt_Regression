"""
Live integration test calling local Ollama instance (qwen2.5:3b and nomic-embed-text).
Marked slow.
"""

import pytest
from core.llm import default_client
from core.scorer import score_trace


@pytest.mark.slow
def test_live_ollama_generation_and_scoring():
    available, msg = default_client.is_available()
    if not available:
        pytest.skip(f"Ollama not accessible: {msg}")

    # Test generation with temperature 0.0 for determinism
    prompt = (
        "You are a sentiment classification model.\n"
        "Analyze the sentiment of the user input text.\n"
        "Output EXACTLY ONE of the following three words:\n"
        "POSITIVE\n"
        "NEGATIVE\n"
        "NEUTRAL\n\n"
        "Rules:\n"
        "1. Do not include punctuation.\n"
        "2. Do not include markdown formatting.\n"
        "3. Do not include any explanations, sentences, or extra words.\n"
        "4. Output strictly one uppercase word.\n\n"
        "Input:\n"
        "The customer service agent was polite, speedy, and solved my problem immediately!\n"
        "Output:\n"
    )

    resp = default_client.generate(prompt=prompt, temperature=0.0, seed=42, model="qwen2.5:3b")
    assert resp is not None
    assert resp.text is not None
    assert len(resp.text.strip()) > 0
    assert resp.latency_ms > 0

    clean_out = resp.text.strip()
    checks = [
        {"type": "exact_match", "value": "POSITIVE"},
        {"type": "max_words", "count": 1},
    ]

    score_res = score_trace({"output": clean_out}, checks)
    assert score_res["passed"] is True
    assert score_res["score"] == 1.0


@pytest.mark.slow
def test_live_ollama_embeddings():
    available, msg = default_client.is_available()
    if not available:
        pytest.skip(f"Ollama not accessible: {msg}")

    emb = default_client.embed("Write SQL queries to join database tables and select fields.")
    assert emb is not None
    assert isinstance(emb, list)
    assert len(emb) > 0  # nomic-embed-text generates 768-dim embeddings

