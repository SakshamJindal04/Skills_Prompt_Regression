import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.llm import default_client
from core.runner import get_llm_adapter, execute_agent_loop
from core.skills import SkillRegistry, EmbeddingSelector
from core.scorer import score_trace

TESTS = [
    {
        "id": "live_sent_pos",
        "target": "sentiment_classifier",
        "prompt": "You are a sentiment classification model.\nAnalyze the sentiment of the user input text.\nOutput EXACTLY ONE of the following three words:\nPOSITIVE\nNEGATIVE\nNEUTRAL\n\nRules:\n1. Do not include punctuation.\n2. Do not include markdown formatting.\n3. Do not include any explanations, sentences, or extra words.\n4. Output strictly one uppercase word.\n\nInput:\nThe customer support agent was remarkably fast, polite, and helpful!\nOutput:\n",
        "checks": [
            {"type": "exact_match", "value": "POSITIVE"},
            {"type": "max_words", "count": 1},
        ],
    },
    {
        "id": "live_sent_neg",
        "target": "sentiment_classifier",
        "prompt": "You are a sentiment classification model.\nAnalyze the sentiment of the user input text.\nOutput EXACTLY ONE of the following three words:\nPOSITIVE\nNEGATIVE\nNEUTRAL\n\nRules:\n1. Do not include punctuation.\n2. Do not include markdown formatting.\n3. Do not include any explanations, sentences, or extra words.\n4. Output strictly one uppercase word.\n\nInput:\nThe battery died within ten minutes and the screen stopped responding.\nOutput:\n",
        "checks": [
            {"type": "exact_match", "value": "NEGATIVE"},
            {"type": "max_words", "count": 1},
        ],
    },
    {
        "id": "live_ent_json",
        "target": "entity_extractor",
        "prompt": "You are a precise Named Entity Recognition (NER) system.\nExtract all named entities (Persons, Organizations, Locations) from the text.\n\nRules:\n1. Return ONLY a valid JSON object. No conversational prelude or conclusion.\n2. The JSON object must strictly match this structure:\n{\n  \"entities\": [\n    {\n      \"text\": \"<entity name>\",\n      \"type\": \"PERSON\" | \"ORG\" | \"LOC\"\n    }\n  ]\n}\n3. If no entities are found, return {\"entities\": []}.\n\nInput:\nSatya Nadella spoke at the Microsoft campus in Redmond.\nOutput:\n",
        "checks": [
            {"type": "valid_json"},
            {"type": "json_schema", "required_keys": ["entities"]},
        ],
    },
    {
        "id": "live_sum_len",
        "target": "short_summarizer",
        "prompt": "You are an expert executive summarizer.\nSummarize the key facts of the provided text.\n\nRules:\n1. The summary MUST be at most 40 words in total.\n2. Do not write filler intros like 'Here is a summary'.\n3. Write in clear, dense, informative sentences.\n\nInput:\nGlobal renewable energy capacity expanded by fifty percent in 2023, driven primarily by solar photovoltaic installations across Europe and Asia, marking the fastest growth rate in two decades according to the International Energy Agency.\nOutput:\n",
        "checks": [
            {"type": "max_words", "count": 40},
            {"type": "not_contains", "values": ["Here is", "Here's"]},
        ],
    },
    {
        "id": "live_skill_sel",
        "target": "skill_selection",
        "input": "Calculate the average order value grouped by customer country from our transactions database table.",
        "checks": [
            {"type": "exact_match", "value": "write-sql"},
        ],
    },
]


def main():
    print("Connecting to local Ollama instance...")
    ok, msg = default_client.is_available()
    if not ok:
        print(f"Error: Ollama is not accessible: {msg}")
        sys.exit(1)
    print(f"Status: {msg}\n")

    adapter = get_llm_adapter(model_id="qwen2.5:3b")
    ws_skills = BASE_DIR / "workspace" / "skills"
    registry = SkillRegistry(skills_dir=str(ws_skills))

    k = 5
    print("=" * 80)
    print(f"LIVE VERIFICATION: Running {len(TESTS)} tests x {k} repetitions against Ollama (qwen2.5:3b)")
    print("=" * 80)

    total_start = time.perf_counter()
    overall_calls = 0
    test_summaries = []

    for t_idx, test in enumerate(TESTS, 1):
        tid = test["id"]
        target = test["target"]
        print(f"\n[Test {t_idx}/{len(TESTS)}] ID: {tid} (Target: {target})")

        passed_runs = 0
        latencies = []

        for r in range(k):
            seed = 42 + r * 1000
            run_start = time.perf_counter()

            if target == "skill_selection":
                selector = EmbeddingSelector(registry, client=default_client)
                ranked, _ = selector.select(test["input"], top_k=3)
                output = ranked[0][0] if ranked else ""
                call_lat = time.perf_counter() - run_start
            else:
                resp = default_client.generate(
                    prompt=test["prompt"],
                    temperature=0.7,
                    seed=seed,
                    model="qwen2.5:3b",
                )
                output = resp.text.strip()
                call_lat = resp.latency_ms / 1000.0  # seconds

            elapsed_s = time.perf_counter() - run_start
            latencies.append(elapsed_s)
            overall_calls += 1

            # Score run
            trace = {"output": output}
            score_res = score_trace(trace, test["checks"])
            passed = score_res["passed"]
            if passed:
                passed_runs += 1

            status_str = "PASS" if passed else "FAIL"
            # Format output for display (clean one line or compact)
            clean_out = repr(output) if len(output) < 80 else repr(output[:75] + "...")
            print(f"  Run {r+1}/{k} [seed={seed}]: {status_str} | latency: {elapsed_s:.3f}s | raw: {clean_out}")

        pass_rate = passed_runs / k
        test_summaries.append({
            "test_id": tid,
            "target": target,
            "passed_runs": passed_runs,
            "k": k,
            "pass_rate": pass_rate,
            "avg_latency_s": sum(latencies) / len(latencies),
        })

    total_wall_s = time.perf_counter() - total_start
    print("\n" + "=" * 80)
    print("LIVE VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"{'Test ID':<20} {'Target':<22} {'Passed':<10} {'Pass Rate':<12} {'Mean Latency':<15}")
    print("-" * 80)
    for s in test_summaries:
        print(
            f"{s['test_id']:<20} {s['target']:<22} {s['passed_runs']}/{s['k']:<8} "
            f"{s['pass_rate']*100:>5.1f}%      {s['avg_latency_s']:>6.3f}s"
        )
    print("-" * 80)
    print(f"Total Model Calls: {overall_calls}")
    print(f"Total Wall-Clock Time: {total_wall_s:.2f}s ({total_wall_s/overall_calls:.3f}s / call)")
    print("=" * 80)


if __name__ == "__main__":
    main()

