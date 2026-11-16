import json
import time
import os
import yaml
from pathlib import Path
from core.db import get_session
from core.models import Artifact, Trace, TestCase
from core.llm import default_client, OllamaClient
from core.skills import SkillRegistry, EmbeddingSelector, BM25Selector, EmbeddingLLMSelector


class BaseLLMAdapter:
    def generate(self, prompt, system=None, temperature=0.7, seed=None):
        raise NotImplementedError


class OllamaAdapter(BaseLLMAdapter):
    def __init__(self, model_id="qwen2.5:3b", client=None):
        self.model_id = model_id
        self.client = client or default_client

    def generate(self, prompt, system=None, temperature=0.7, seed=None):
        resp = self.client.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            seed=seed,
            model=self.model_id,
        )
        return resp.text, resp.latency_ms


def get_llm_adapter(model_id="qwen2.5:3b", provider="ollama"):
    if provider == "ollama":
        return OllamaAdapter(model_id=model_id)
    return OllamaAdapter(model_id=model_id)


def execute_agent_loop(user_input, adapter, registry, with_skill=True, client=None):
    skills_used = []
    system_prompt = "You are a helpful AI assistant."

    if with_skill and registry:
        # Step 1: select skill via embedding top-3 + Qwen
        selector = EmbeddingLLMSelector(registry, client=client or default_client)
        ranked, _ = selector.select(user_input, top_k=3)
        if ranked:
            chosen_skill_name = ranked[0][0]
            skill_obj = registry.get_skill(chosen_skill_name)
            if skill_obj:
                skills_used.append(chosen_skill_name)
                system_prompt = f"You are equipped with the skill '{chosen_skill_name}'.\nSkill Instructions:\n{skill_obj.body}"

    # Step 2: generate answer with system prompt
    out, lat = adapter.generate(prompt=user_input, system=system_prompt)
    return out, skills_used, lat


def run_test(artifact_id, test_case, k=5, model_id="qwen2.5:3b", with_skill=True, use_cache=True, workspace_dir=None, prompt_template_override=None):
    base_ws = Path(workspace_dir) if workspace_dir else Path(__file__).resolve().parent.parent / "workspace"
    adapter = get_llm_adapter(model_id=model_id)
    registry = SkillRegistry(skills_dir=str(base_ws / "skills"))

    art_path = ""
    with get_session() as session:
        art = session.query(Artifact).filter_by(id=artifact_id).first()
        art_path = art.path if art else ""

    prompt_template = prompt_template_override or ""
    if not prompt_template:
        target_file = base_ws / art_path if art_path else None
        if target_file and target_file.exists() and target_file.is_file():
            prompt_template = target_file.read_text(encoding="utf-8")
        else:
            target_name = test_case.get("target", "")
            cand_p = base_ws / "prompts" / f"{target_name}.md"
            if cand_p.exists():
                prompt_template = cand_p.read_text(encoding="utf-8")

    traces = []

    for run_idx in range(k):
        # Check cache in DB
        if use_cache:
            with get_session() as session:
                cached = session.query(Trace).filter_by(
                    artifact_id=artifact_id,
                    test_id=test_case["id"],
                    run_index=run_idx,
                ).first()
                if cached:
                    traces.append(cached.to_dict())
                    continue

        seed = 42 + run_idx * 1000
        target = test_case.get("target", "")

        start_time = time.perf_counter()
        skills_used = []
        tool_calls = []

        if target in ("agent_trajectory", "tool_agent") or "trajectory" in target:
            from core.agent import run_agent_trajectory
            traj_res = run_agent_trajectory(
                task_input=test_case["input"],
                client=default_client,
                model=model_id,
                max_steps=test_case.get("max_steps", 5),
            )
            out = json.dumps(traj_res)
            tools_used = traj_res.get("tools_used", [])
            tool_calls = traj_res.get("trajectory", [])
            lat = sum(step.get("latency_ms", 0.0) for step in traj_res.get("trajectory", []))
        elif target == "skill_selection":
            # Run skill selector
            selector = EmbeddingSelector(registry, client=default_client)
            ranked, lat = selector.select(test_case["input"], top_k=3)
            out = ranked[0][0] if ranked else ""
            skills_used = [out]
        elif "skills/" in art_path or target.startswith("skill_"):
            # Small local agent loop with skill
            out, skills_used, lat = execute_agent_loop(
                test_case["input"],
                adapter,
                registry,
                with_skill=with_skill,
            )
        else:
            # Prompt run
            if "{input}" in prompt_template:
                full_prompt = prompt_template.replace("{input}", test_case["input"])
            else:
                full_prompt = f"{prompt_template}\n\nInput:\n{test_case['input']}\nOutput:"

            out, lat = adapter.generate(prompt=full_prompt, temperature=0.7, seed=seed)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        # Fetch model digest
        model_meta = default_client.get_model_metadata(model_id)
        model_digest = model_meta.get("digest")

        # Store trace in DB
        with get_session() as session:
            trace = Trace(
                artifact_id=artifact_id,
                test_id=test_case["id"],
                run_index=run_idx,
                output=out,
                skills_used=skills_used,
                tool_calls=tool_calls,
                latency_ms=elapsed_ms,
                seed=seed,
                model=model_id,
                model_digest=model_digest,
                temperature=0.7,
            )
            session.add(trace)
            session.flush()
            t_dict = trace.to_dict()

        traces.append(t_dict)

    return traces


def sync_tests_to_db(tests_file=None):
    """
    Load test cases from YAML files and sync to DB.
    If tests_file is None, syncs golden_tests.yaml and analytics_tests.yaml.
    """
    tests_dir = Path(__file__).resolve().parent.parent / "tests_data"
    if tests_file:
        files = [Path(tests_file)]
    else:
        files = [
            tests_dir / "golden_tests.yaml",
            tests_dir / "analytics_tests.yaml",
            tests_dir / "promptpex_tests.yaml",
            tests_dir / "gpr_subset.yaml",
            tests_dir / "agent_trajectory_tests.yaml",
        ]

    total_synced = 0
    with get_session() as session:
        for fpath in files:
            if not fpath.exists():
                continue
            try:
                data = yaml.safe_load(fpath.read_text(encoding="utf-8")) or {}
                test_items = data.get("tests", [])
            except Exception:
                continue

            for t in test_items:
                existing = session.query(TestCase).filter_by(id=t["id"]).first()
                if not existing:
                    tc = TestCase(
                        id=t["id"],
                        suite=t.get("suite", "default"),
                        target=t["target"],
                        input=t["input"],
                        slices=t.get("slices", {}),
                        checks=t.get("checks", []),
                        origin=t.get("origin", "golden"),
                        rule_id=t.get("rule_id"),
                        critical=bool(t.get("critical", False)),
                    )
                    session.add(tc)
                    total_synced += 1
                else:
                    existing.suite = t.get("suite", "default")
                    existing.target = t["target"]
                    existing.input = t["input"]
                    existing.slices = t.get("slices", {})
                    existing.checks = t.get("checks", [])
                    existing.origin = t.get("origin", "golden")
                    existing.rule_id = t.get("rule_id")
                    existing.critical = bool(t.get("critical", False))
                    total_synced += 1

    return total_synced


def run_test_suite_live(artifact_id, tests, k=5, model="qwen2.5:3b", client=None):
    """
    Executes a test suite live for artifact_id across k runs.
    """
    all_traces = []
    for tc in tests:
        traces = run_test(artifact_id, tc, k=k, model_id=model)
        all_traces.extend(traces)
    return all_traces

