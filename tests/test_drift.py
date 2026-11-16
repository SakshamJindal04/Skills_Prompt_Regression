import pytest
from unittest.mock import MagicMock
from core.drift import check_model_drift


def test_drift_detector_matching_digest():
    mock_client = MagicMock()
    mock_client.show.return_value = {
        "digest": "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b",
        "details": {"family": "qwen2", "parameter_size": "3.1B"}
    }

    res = check_model_drift(model_tag="qwen2.5:3b", client=mock_client)
    assert res["model"] == "qwen2.5:3b"
    assert res["current_digest"] == "357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b"
    assert "No drift detected" in res["message"]


def test_drift_detector_digest_mismatch(monkeypatch):
    mock_client = MagicMock()
    mock_client.show.return_value = {
        "digest": "new_altered_sha256_digest_1234567890abcdef",
        "details": {"family": "qwen2", "parameter_size": "3.1B"}
    }

    # Mock runner and scorer to avoid calling live Ollama in unit test
    monkeypatch.setattr("core.runner.run_test_suite_live", lambda *args, **kwargs: [])
    monkeypatch.setattr("core.scorer.score_artifact_runs", lambda *args, **kwargs: None)

    # Simulate silent drift where current digest differs from baseline
    res = check_model_drift(model_tag="qwen2.5:3b", client=mock_client)
    assert res["drift_detected"] is True
    assert "CRITICAL WARNING" in res["message"]
