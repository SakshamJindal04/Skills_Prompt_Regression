"""
Slow end-to-end integration test calling live Ollama (qwen2.5:3b) through runner, scorer, comparator, and gate.
"""

import pytest
from core.llm import default_client
from core.models import Artifact, Score, TestCase
from core.db import get_session
from core.runner import run_test
from core.scorer import score_artifact_runs
from core.comparator import compare_test_results
from core.gate import evaluate_gate


@pytest.mark.slow
def test_live_ollama_end_to_end_pipeline(tmp_path):
    available, msg = default_client.is_available()
    if not available:
        pytest.skip(f"Ollama not accessible: {msg}")

    # Register temporary test artifact
    with get_session() as session:
        art = Artifact(
            hash=f"live_art_e2e_{int(tmp_path.stat().st_mtime)}",
            type="prompt",
            name="sentiment_live.md",
            path="prompts/sentiment.md",
            manifest={"model": "qwen2.5:3b"},
        )
        session.add(art)
        session.flush()
        art_id = art.id

        # Insert test cases into DB to satisfy foreign key constraints
        for tc in [
            {
                "id": "e2e_live_pos",
                "suite": "golden",
                "target": "sentiment",
                "input": "I absolutely love this laptop! The keyboard is fantastic.",
                "checks": [{"type": "contains", "value": "POSITIVE"}],
                "critical": True,
            },
            {
                "id": "e2e_live_neg",
                "suite": "golden",
                "target": "sentiment",
                "input": "Horrible experience, broken screen on arrival.",
                "checks": [{"type": "contains", "value": "NEGATIVE"}],
                "critical": False,
            },
        ]:
            existing_tc = session.get(TestCase, tc["id"])
            if not existing_tc:
                session.add(TestCase(**tc))
        session.flush()

    # Define 2 test cases with strict deterministic checks
    test_cases = [
        {
            "id": "e2e_live_pos",
            "suite": "golden",
            "target": "sentiment",
            "input": "I absolutely love this laptop! The keyboard is fantastic.",
            "checks": [
                {"type": "contains", "value": "POSITIVE"},
            ],
            "critical": True,
        },
        {
            "id": "e2e_live_neg",
            "suite": "golden",
            "target": "sentiment",
            "input": "Horrible experience, broken screen on arrival.",
            "checks": [
                {"type": "contains", "value": "NEGATIVE"},
            ],
            "critical": False,
        },
    ]

    # Prompt template
    prompt_template = (
        "Classify sentiment as POSITIVE, NEGATIVE, or NEUTRAL.\n"
        "Input: {input}\n"
        "Output:"
    )

    # Run tests live with k=2
    all_traces = []
    for tc in test_cases:
        traces = run_test(
            artifact_id=art_id,
            test_case=tc,
            k=2,
            model_id="qwen2.5:3b",
            prompt_template_override=prompt_template,
            use_cache=False,
        )
        all_traces.extend(traces)

    assert len(all_traces) == 4  # 2 tests x 2 runs

    # Score artifact runs in DB
    score_res = score_artifact_runs(art_id, test_cases)
    assert len(score_res) == 4

    # Verify score entries in DB
    with get_session() as session:
        scores = session.query(Score).filter_by(artifact_id=art_id).all()
        assert len(scores) == 4
        for s in scores:
            assert s.passed is True
            assert s.score == 1.0

    # Compare against identical baseline (self comparison -> PROMOTE)
    base_runs = {tc["id"]: [True, True] for tc in test_cases}
    cand_runs = {tc["id"]: [True, True] for tc in test_cases}
    comp = compare_test_results(test_cases, base_runs, cand_runs, k=2)

    verdict, report = evaluate_gate(
        comp,
        candidate_id=art_id,
        baseline_id=art_id,
        auto_promote=False,
    )
    assert verdict == "PROMOTE"
    assert "**Verdict**: **PROMOTE**" in report
