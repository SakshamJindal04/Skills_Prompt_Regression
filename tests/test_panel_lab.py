import pytest
from unittest.mock import MagicMock
from core.lab import (
    run_lab_pipeline,
    check_and_truncate_prompt,
    export_lab_markdown,
    export_lab_csv,
    LABEL_COMPLIANCE,
    LABEL_SAMPLE_POWER,
)
from core.llm import LLMResponse


def test_prompt_truncation_warning():
    short_p = "Short prompt text."
    p_clean, notice = check_and_truncate_prompt(short_p)
    assert notice is None
    assert p_clean == short_p

    long_p = "word " * 5000
    p_trunc, notice = check_and_truncate_prompt(long_p, max_tokens=1000)
    assert notice is not None
    assert "exceeded" in notice


def test_panel_lab_pipeline_mocked():
    mock_client = MagicMock()
    mock_client.generate.return_value = LLMResponse(
        text='{"vendor": "Acme", "amount": 100.0}',
        latency_ms=120.0,
        model="qwen2.5:3b",
        prompt_tokens=40,
        completion_tokens=20,
    )

    test_prompt = """
You are a parser.
Extract invoice fields into valid JSON with vendor and amount.
Input:
{input}
"""
    res = run_lab_pipeline(
        prompt_text=test_prompt,
        models=["qwen2.5:3b"],
        k=1,
        max_tests=2,
        client=mock_client,
    )

    assert res["overall_pass_rate"] >= 0.0
    assert res["k"] == 1
    assert res["n_tests"] == 2
    assert res["warning_compliance"] == LABEL_COMPLIANCE
    assert res["warning_power"] == LABEL_SAMPLE_POWER

    # Verify export functions
    md = export_lab_markdown(res)
    assert "Panel Lab Evaluation Report" in md

    csv_str = export_lab_csv(res)
    assert "test_id" in csv_str

