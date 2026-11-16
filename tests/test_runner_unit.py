"""
Unit tests for Runner module (core.runner).
"""

import pytest
from unittest.mock import MagicMock, patch
from core.runner import (
    BaseLLMAdapter,
    OllamaAdapter,
    get_llm_adapter,
    execute_agent_loop,
    sync_tests_to_db,
)
from core.models import TestCase
from core.db import get_session


def test_base_llm_adapter_not_implemented():
    adapter = BaseLLMAdapter()
    with pytest.raises(NotImplementedError):
        adapter.generate("Hello world")


def test_ollama_adapter_generate():
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = "Mocked answer"
    mock_resp.latency_ms = 123.45
    mock_client.generate.return_value = mock_resp

    adapter = OllamaAdapter(model_id="qwen2.5:3b", client=mock_client)
    text, lat = adapter.generate("Test prompt", system="Test system", temperature=0.5, seed=42)

    assert text == "Mocked answer"
    assert lat == 123.45
    mock_client.generate.assert_called_once_with(
        prompt="Test prompt",
        system="Test system",
        temperature=0.5,
        seed=42,
        model="qwen2.5:3b",
    )


def test_get_llm_adapter_factory():
    ad1 = get_llm_adapter("qwen2.5:3b", provider="ollama")
    assert isinstance(ad1, OllamaAdapter)
    assert ad1.model_id == "qwen2.5:3b"

    ad2 = get_llm_adapter("llama3.2:3b", provider="other")
    assert isinstance(ad2, OllamaAdapter)
    assert ad2.model_id == "llama3.2:3b"


def test_execute_agent_loop_with_and_without_skill():
    mock_adapter = MagicMock()
    mock_adapter.generate.return_value = ("Agent answer", 80.0)

    # Without skill
    out, skills, lat = execute_agent_loop("User task", mock_adapter, registry=None, with_skill=False)
    assert out == "Agent answer"
    assert skills == []
    assert lat == 80.0

    # With mock registry
    mock_registry = MagicMock()
    mock_skill = MagicMock()
    mock_skill.body = "Do the thing step by step."
    mock_registry.get_skill.return_value = mock_skill

    with patch("core.runner.EmbeddingLLMSelector") as MockSelector:
        instance = MockSelector.return_value
        instance.select.return_value = ([("calculator", 0.9)], 25.0)

        out, skills, lat = execute_agent_loop("Compute 2+2", mock_adapter, registry=mock_registry, with_skill=True)
        assert out == "Agent answer"
        assert skills == ["calculator"]
        mock_adapter.generate.assert_called_with(
            prompt="Compute 2+2",
            system="You are equipped with the skill 'calculator'.\nSkill Instructions:\nDo the thing step by step.",
        )


def test_sync_tests_to_db():
    # Sync test cases to database
    count = sync_tests_to_db()
    assert count > 0

    with get_session() as session:
        tcs = session.query(TestCase).all()
        assert len(tcs) >= count
        ids = [tc.id for tc in tcs]
        assert "sent_01" in ids or "sum_01" in ids or "ext_01" in ids

