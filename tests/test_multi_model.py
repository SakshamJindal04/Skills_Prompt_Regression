import pytest
from pathlib import Path
import yaml
from core.llm import default_client
from core.policy import load_policy
from core.models import Trace, Score, Result
from scripts.judge_calibration import compute_cohens_kappa
from scripts.model_swap_case_study import compute_wilson_ci
from core.gate import evaluate_gate

BASE_DIR = Path(__file__).resolve().parent.parent


def test_models_yaml_structure():
    models_file = BASE_DIR / "models.yaml"
    assert models_file.exists()
    data = yaml.safe_load(models_file.read_text(encoding="utf-8"))

    assert "baseline_model" in data
    assert "candidate_models" in data
    assert "judge_model" in data
    assert "embedding_model" in data
    assert "models" in data

    assert data["baseline_model"] == "qwen2.5:3b"
    assert "llama3.2:3b" in data["candidate_models"]
    assert "gemma2:2b" in data["candidate_models"]
    assert data["judge_model"] == "gemma2:2b"

    # Verify per-model metadata
    for m in ["qwen2.5:3b", "llama3.2:3b", "gemma2:2b"]:
        assert m in data["models"]
        info = data["models"][m]
        assert "family" in info
        assert "context_window" in info
        assert "role" in info


def test_judge_model_family_separation():
    # If testing Qwen, judge should not be Qwen
    qwen_judge = default_client.get_judge_model("qwen2.5:3b")
    assert "qwen" not in qwen_judge.lower()

    # If testing Gemma, judge should not be Gemma
    gemma_judge = default_client.get_judge_model("gemma2:2b")
    assert "gemma" not in gemma_judge.lower()

    # If testing Llama, judge should not be Llama
    llama_judge = default_client.get_judge_model("llama3.2:3b")
    assert "llama" not in llama_judge.lower()


def test_cohens_kappa_math():
    # Perfect agreement
    det_perfect = [True, True, False, False]
    judge_perfect = [True, True, False, False]
    p_o, p_e, kappa, conf = compute_cohens_kappa(det_perfect, judge_perfect)
    assert p_o == 1.0
    assert kappa == 1.0
    assert conf["tp"] == 2
    assert conf["tn"] == 2
    assert conf["fp"] == 0
    assert conf["fn"] == 0

    # Known hand-calculated matrix:
    # TP = 20, FP = 5, FN = 5, TN = 10 (Total N=40)
    det_sample = [True] * 25 + [False] * 15
    judge_sample = [True] * 20 + [False] * 5 + [True] * 5 + [False] * 10
    p_o, p_e, kappa, conf = compute_cohens_kappa(det_sample, judge_sample)
    assert p_o == 30 / 40  # 0.75
    # p_d_pos = 25/40 = 0.625, p_d_neg = 15/40 = 0.375
    # p_j_pos = 25/40 = 0.625, p_j_neg = 15/40 = 0.375
    # p_e = (0.625 * 0.625) + (0.375 * 0.375) = 0.390625 + 0.140625 = 0.53125
    expected_pe = (0.625 * 0.625) + (0.375 * 0.375)
    expected_kappa = (0.75 - expected_pe) / (1.0 - expected_pe)
    assert pytest.approx(p_e, 0.0001) == expected_pe
    assert pytest.approx(kappa, 0.0001) == expected_kappa


def test_wilson_ci_math():
    # 0 out of 100
    low, high = compute_wilson_ci(0.0, 100)
    assert low >= 0.0
    assert high > 0.0

    # 100 out of 100
    low, high = compute_wilson_ci(1.0, 100)
    assert low < 1.0
    assert high <= 1.0

    # 50 out of 100 (symmetric around 0.5)
    low, high = compute_wilson_ci(0.5, 100)
    assert pytest.approx(low + high, 0.001) == 1.0


def test_evaluate_gate_critical_regression():
    comparison = {
        "regressed_count": 1,
        "fixed_count": 5,
        "p_value": 0.20,
        "delta_pass_rate": 0.04,
        "baseline_pass_rate": 0.80,
        "candidate_pass_rate": 0.84,
        "flips": [
            {"test_id": "crit-01", "critical": True, "outcome": "regressed"}
        ],
    }
    verdict, report_md = evaluate_gate(
        comparison,
        base_model="qwen2.5:3b",
        cand_model="llama3.2:3b",
        base_digest="abc123",
        cand_digest="def456",
    )
    assert verdict == "BLOCK"
    assert "qwen2.5:3b" in report_md
    assert "llama3.2:3b" in report_md


def test_evaluate_gate_significant_regression():
    comparison = {
        "regressed_count": 10,
        "fixed_count": 1,
        "p_value": 0.012,
        "delta_pass_rate": -0.09,
        "baseline_pass_rate": 0.85,
        "candidate_pass_rate": 0.76,
        "flips": [
            {"test_id": f"t-{i}", "critical": False, "outcome": "regressed"} for i in range(10)
        ],
    }
    verdict, report_md = evaluate_gate(
        comparison,
        alpha=0.05,
        base_model="qwen2.5:3b",
        cand_model="gemma2:2b",
    )
    assert verdict == "BLOCK"


def test_evaluate_gate_promote():
    comparison = {
        "regressed_count": 2,
        "fixed_count": 4,
        "p_value": 0.68,
        "delta_pass_rate": 0.02,
        "baseline_pass_rate": 0.80,
        "candidate_pass_rate": 0.82,
        "flips": [
            {"test_id": "t-1", "critical": False, "outcome": "regressed"},
            {"test_id": "t-2", "critical": False, "outcome": "regressed"},
            {"test_id": "t-3", "critical": False, "outcome": "fixed"},
        ],
    }
    verdict, report_md = evaluate_gate(
        comparison,
        alpha=0.05,
        base_model="qwen2.5:3b",
        cand_model="llama3.2:3b",
    )
    assert verdict == "PROMOTE"


def test_db_models_have_model_columns():
    t = Trace(
        artifact_id=1,
        test_id="t-1",
        output="sample output",
        model_id="llama3.2:3b",
        model_digest="sha256:1234567890abcdef",
    )
    d = t.to_dict()
    assert d["model_id"] == "llama3.2:3b"
    assert d["model_digest"] == "sha256:1234567890abcdef"

    s = Score(
        trace_id=1,
        test_id="t-1",
        passed=True,
        model_id="gemma2:2b",
        model_digest="sha256:abcdef1234567890",
    )
    sd = s.to_dict()
    assert sd["model_id"] == "gemma2:2b"
    assert sd["model_digest"] == "sha256:abcdef1234567890"

    r = Result(
        run_id=1,
        test_id="t-1",
        model_id="qwen2.5:3b",
        model_digest="sha256:9999999999999999",
    )
    rd = r.to_dict()
    assert rd["model_id"] == "qwen2.5:3b"
    assert rd["model_digest"] == "sha256:9999999999999999"
