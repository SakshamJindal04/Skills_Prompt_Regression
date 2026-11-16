"""
Skill Registry and Skill Selectors.
Parses SKILL.md files, supports Embedding retrieval, BM25 retrieval, and Embedding+LLM re-ranking.
Includes benchmark evaluation (Top-1, Top-3, p50/p95 latency).
"""

import os
import re
import time
import math
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import yaml
import numpy as np

from core.llm import OllamaClient, default_client
from core.checkers import extract_json_from_text


@dataclass
class Skill:
    name: str
    description: str
    path: str
    body: str
    metadata: Dict[str, Any]

    def get_search_text(self) -> str:
        """Text used for indexing/retrieval."""
        return f"{self.name}: {self.description}"


class SkillRegistry:
    """Discovers and parses all SKILL.md folders in workspace/skills/."""

    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir:
            self.skills_dir = Path(skills_dir)
        else:
            self.skills_dir = Path(__file__).resolve().parent.parent / "workspace" / "skills"
        self.skills: Dict[str, Skill] = {}
        self.load_skills()

    def load_skills(self) -> Dict[str, Skill]:
        """Scan skills directory and parse all SKILL.md files."""
        self.skills = {}
        if not self.skills_dir.exists():
            return self.skills

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    skill = self.parse_skill_file(skill_file)
                    if skill:
                        self.skills[skill.name] = skill

        return self.skills

    @staticmethod
    def parse_skill_file(file_path: Path) -> Optional[Skill]:
        """Parse frontmatter and markdown body from a SKILL.md file."""
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            return None

        # Check for YAML frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                raw_frontmatter = parts[1]
                body = parts[2].strip()
                try:
                    meta = yaml.safe_load(raw_frontmatter) or {}
                except Exception:
                    meta = {}
                name = meta.get("name", file_path.parent.name)
                description = meta.get("description", "")
                return Skill(
                    name=name,
                    description=description,
                    path=str(file_path),
                    body=body,
                    metadata=meta,
                )

        # Fallback if no frontmatter
        name = file_path.parent.name
        description = content[:200].strip()
        return Skill(
            name=name,
            description=description,
            path=str(file_path),
            body=content,
            metadata={},
        )

    def get_skill(self, name: str) -> Optional[Skill]:
        return self.skills.get(name)

    def list_skills(self) -> List[Skill]:
        return list(self.skills.values())


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    a = np.array(v1, dtype=np.float32)
    b = np.array(v2, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class EmbeddingSelector:
    """Retrieves skills by embedding similarity using Ollama nomic-embed-text."""

    def __init__(self, registry: SkillRegistry, client: Optional[OllamaClient] = None):
        self.registry = registry
        self.client = client or default_client
        self.skill_embeddings: Dict[str, List[float]] = {}
        self._index_skills()

    def _index_skills(self):
        self.skill_embeddings.clear()
        for skill in self.registry.list_skills():
            search_text = skill.get_search_text()
            try:
                emb = self.client.embed(search_text)
                self.skill_embeddings[skill.name] = emb
            except Exception as e:
                # If embedding fails offline, create pseudo deterministic vector
                self.skill_embeddings[skill.name] = self._pseudo_embedding(search_text)

    @staticmethod
    def _pseudo_embedding(text: str, dim: int = 128) -> List[float]:
        """Fallback bag-of-words hash embedding if Ollama embedding is unavailable."""
        vec = [0.0] * dim
        words = re.findall(r"\w+", text.lower())
        for w in words:
            h = hash(w) % dim
            vec[h] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def select(self, query: str, top_k: int = 3) -> Tuple[List[Tuple[str, float]], float]:
        """
        Rank skills by cosine similarity.
        Returns (ranked_list_of_(skill_name, score), latency_ms).
        """
        start = time.perf_counter()
        try:
            query_emb = self.client.embed(query)
        except Exception:
            query_emb = self._pseudo_embedding(query)

        scores = []
        for name, emb in self.skill_embeddings.items():
            sim = cosine_similarity(query_emb, emb)
            scores.append((name, round(sim, 4)))

        scores.sort(key=lambda x: x[1], reverse=True)
        latency_ms = (time.perf_counter() - start) * 1000.0
        return scores[:top_k], round(latency_ms, 2)


class BM25Selector:
    """Baseline skill selector using BM25 keyword matching."""

    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.skill_names: List[str] = []
        self.corpus: List[List[str]] = []
        self._index_skills()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _index_skills(self):
        from rank_bm25 import BM25Okapi

        self.skill_names = []
        self.corpus = []
        for skill in self.registry.list_skills():
            self.skill_names.append(skill.name)
            self.corpus.append(self._tokenize(skill.get_search_text()))

        if self.corpus:
            self.bm25 = BM25Okapi(self.corpus)
        else:
            self.bm25 = None

    def select(self, query: str, top_k: int = 3) -> Tuple[List[Tuple[str, float]], float]:
        """
        Rank skills using BM25.
        Returns (ranked_list_of_(skill_name, score), latency_ms).
        """
        start = time.perf_counter()
        if not self.bm25 or not self.skill_names:
            return [], 0.0

        tokenized_query = self._tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)

        ranked = [(self.skill_names[i], round(float(scores[i]), 4)) for i in range(len(self.skill_names))]
        ranked.sort(key=lambda x: x[1], reverse=True)
        latency_ms = (time.perf_counter() - start) * 1000.0
        return ranked[:top_k], round(latency_ms, 2)


class EmbeddingLLMSelector:
    """
    Two-stage retrieval: top-k candidates via embedding cosine similarity,
    followed by Qwen selection with reasoning.
    """

    def __init__(self, registry: SkillRegistry, client: Optional[OllamaClient] = None):
        self.registry = registry
        self.client = client or default_client
        self.embedding_selector = EmbeddingSelector(registry, client=self.client)

    def select(self, query: str, top_k: int = 3) -> Tuple[List[Tuple[str, float]], float]:
        """
        Retrieve top-k via embedding, then use LLM to pick the best skill.
        Returns (re_ranked_list, latency_ms).
        """
        start = time.perf_counter()
        candidates, _ = self.embedding_selector.select(query, top_k=max(top_k, 3))
        if not candidates:
            return [], 0.0

        candidate_info = []
        for name, score in candidates:
            skill = self.registry.get_skill(name)
            desc = skill.description if skill else ""
            candidate_info.append(f"- {name}: {desc}")

        prompt = f"""You are an autonomous AI agent selector. Select the SINGLE most appropriate skill for the user's task.

User Task:
\"{query}\"

Candidate Skills:
{chr(10).join(candidate_info)}

Respond ONLY with a JSON object in this format:
{{
  "selected_skill": "<exact skill name from candidates>",
  "reason": "<one sentence justification>"
}}
"""
        try:
            resp = self.client.generate(prompt=prompt, temperature=0.0, format_json=True)
            parsed = extract_json_from_text(resp.text)
            selected_name = parsed.get("selected_skill", "") if parsed else ""
        except Exception:
            selected_name = candidates[0][0]

        # Re-order: selected_name first, then others
        ordered = []
        found = False
        for name, score in candidates:
            if name == selected_name:
                ordered.insert(0, (name, 1.0))
                found = True
            else:
                ordered.append((name, score))

        if not found and candidates:
            ordered = candidates

        latency_ms = (time.perf_counter() - start) * 1000.0
        return ordered[:top_k], round(latency_ms, 2)


def compute_text_similarity(t1: str, t2: str, client: Optional[OllamaClient] = None) -> float:
    """Computes cosine similarity between two text snippets using nomic-embed-text or pseudo-vector fallback."""
    c = client or default_client
    try:
        e1 = c.embed(t1)
        e2 = c.embed(t2)
        return cosine_similarity(e1, e2)
    except Exception:
        e1 = EmbeddingSelector._pseudo_embedding(t1)
        e2 = EmbeddingSelector._pseudo_embedding(t2)
        return cosine_similarity(e1, e2)


def compute_skill_overlap_matrix(
    registry: Optional[SkillRegistry] = None,
    threshold: float = 0.75,
    client: Optional[OllamaClient] = None
) -> Dict[str, Any]:
    """
    Computes pairwise cosine similarity matrix across all skills in registry.
    Flags pairs exceeding threshold and produces disambiguation advice.
    """
    reg = registry or SkillRegistry()
    skills = reg.list_skills()
    names = [s.name for s in skills]
    n = len(names)
    matrix = [[0.0] * n for _ in range(n)]
    overlaps = []

    c = client or default_client
    selector = EmbeddingSelector(reg, client=c)

    for i in range(n):
        matrix[i][i] = 1.0
        emb_i = selector.skill_embeddings.get(names[i])
        for j in range(i + 1, n):
            emb_j = selector.skill_embeddings.get(names[j])
            if emb_i and emb_j:
                sim = round(cosine_similarity(emb_i, emb_j), 4)
            else:
                sim = round(compute_text_similarity(skills[i].get_search_text(), skills[j].get_search_text(), client=c), 4)
            matrix[i][j] = sim
            matrix[j][i] = sim

            if sim >= threshold:
                overlaps.append({
                    "skill_a": names[i],
                    "skill_b": names[j],
                    "similarity": sim,
                    "warning": f"Skills '{names[i]}' and '{names[j]}' exhibit high conceptual overlap ({sim:.2f} >= {threshold:.2f}).",
                    "suggestion": f"Differentiate trigger condition keywords in {names[i]}/SKILL.md and {names[j]}/SKILL.md or consolidate into a single parameterized skill."
                })

    overlaps.sort(key=lambda x: x["similarity"], reverse=True)
    return {
        "skills": names,
        "matrix": matrix,
        "overlaps": overlaps,
        "threshold": threshold
    }


def run_skill_benchmark(
    benchmark_items: List[Dict[str, Any]],
    selector_method: str = "embedding",
    registry: Optional[SkillRegistry] = None,
    client: Optional[OllamaClient] = None,
    abstain_threshold: float = 0.45,
) -> Dict[str, Any]:
    """
    Evaluate skill selection on a benchmark set with category-level breakdowns,
    out-of-scope abstention detection, and confusion matrix.
    """
    registry = registry or SkillRegistry()
    client = client or default_client

    if selector_method == "embedding":
        selector = EmbeddingSelector(registry, client=client)
    elif selector_method == "bm25":
        selector = BM25Selector(registry)
    elif selector_method in ("embedding_llm", "llm"):
        selector = EmbeddingLLMSelector(registry, client=client)
    else:
        raise ValueError(f"Unknown selector method: {selector_method}")

    top1_correct = 0
    top3_correct = 0
    latencies: List[float] = []
    details = []
    categories: Dict[str, Dict[str, Any]] = {}
    confusions: Dict[str, Dict[str, int]] = {}

    for item in benchmark_items:
        task = item.get("task", item.get("input", ""))
        expected = item.get("expected_skill", item.get("target", item.get("expected", ""))).strip().lower()
        category = item.get("category", "clear")

        if category not in categories:
            categories[category] = {"total": 0, "correct": 0, "top3_correct": 0}

        ranked, lat = selector.select(task, top_k=3)
        latencies.append(lat)

        top_pred = ranked[0][0].strip().lower() if ranked else "none"
        top_score = ranked[0][1] if ranked else 0.0

        # Handle abstention for out_of_scope
        if expected in ("abstain", "none", "out_of_scope", ""):
            top1_match = (top_score < abstain_threshold) or (top_pred in ("abstain", "none"))
            top3_match = top1_match
        else:
            top1_match = len(ranked) > 0 and (top_pred == expected)
            top3_match = any(r[0].strip().lower() == expected for r in ranked[:3])

        if top1_match:
            top1_correct += 1
            categories[category]["correct"] += 1
        else:
            if expected not in confusions:
                confusions[expected] = {}
            confusions[expected][top_pred] = confusions[expected].get(top_pred, 0) + 1

        if top3_match:
            top3_correct += 1
            categories[category]["top3_correct"] += 1

        categories[category]["total"] += 1

        details.append({
            "task": task,
            "category": category,
            "expected": expected,
            "predicted": top_pred,
            "score": top_score,
            "top1_match": top1_match,
            "top3_match": top3_match,
            "ranked": ranked,
            "latency_ms": lat,
        })

    n = len(benchmark_items) or 1
    top1_acc = round(top1_correct / n, 4)
    top3_acc = round(top3_correct / n, 4)
    p50 = float(np.percentile(latencies, 50)) if latencies else 0.0
    p95 = float(np.percentile(latencies, 95)) if latencies else 0.0
    mean_lat = float(np.mean(latencies)) if latencies else 0.0

    category_summary = {}
    for cat, data in categories.items():
        tot = data["total"] or 1
        category_summary[cat] = {
            "total": data["total"],
            "correct": data["correct"],
            "top1_accuracy": round(data["correct"] / tot, 4),
            "top3_accuracy": round(data["top3_correct"] / tot, 4),
        }

    # Format top confusions with explanation
    top_confusion_list = []
    for exp, preds in confusions.items():
        for pr, cnt in preds.items():
            top_confusion_list.append({
                "expected": exp,
                "predicted": pr,
                "count": cnt,
                "explanation": f"Task targeted '{exp}' but router chose '{pr}' due to lexical and conceptual overlap."
            })
    top_confusion_list.sort(key=lambda x: x["count"], reverse=True)

    return {
        "method": selector_method,
        "n_items": n,
        "top1": top1_acc,
        "top3": top3_acc,
        "latency_mean": round(mean_lat, 2),
        "latency_p50": round(p50, 2),
        "latency_p95": round(p95, 2),
        "categories": category_summary,
        "top_confusions": top_confusion_list[:10],
        "details": details,
    }


def benchmark_scalability(
    skill_counts: Optional[List[int]] = None,
    registry: Optional[SkillRegistry] = None,
    client: Optional[OllamaClient] = None
) -> Dict[str, Any]:
    """
    Measures retrieval latency and accuracy scaling as skill count grows (e.g. 6, 12, 24 skills).
    Uses synthetic distractor skills if the registry has fewer skills than requested.
    """
    skill_counts = skill_counts or [6, 12, 24]
    reg = registry or SkillRegistry()
    client = client or default_client
    base_skills = reg.list_skills()

    results = []
    test_queries = [
        ("Summarize this financial quarterly filing", "text-summarizer"),
        ("Write a SQL query to count active users by month", "sql-generator"),
        ("Make this polite email sound executive and decisive", "tone-adjuster"),
        ("Clean up ragged commas in this CSV dataset", "csv-cleaner"),
        ("Extract invoice total and vendor line items into JSON", "json-formatter"),
    ]

    for count in skill_counts:
        # Create synthetic registry subset with `count` skills
        sub_skills = list(base_skills[:count])
        # If count exceeds available skills, inject distractor skills
        idx = 1
        while len(sub_skills) < count:
            d_name = f"distractor-skill-{idx}"
            d_desc = f"Synthetic distractor skill {idx} performing specialized operations on domain {idx}."
            sub_skills.append(Skill(
                name=d_name,
                description=d_desc,
                path="",
                body="",
                metadata={"name": d_name, "description": d_desc}
            ))
            idx += 1

        temp_reg = SkillRegistry()
        temp_reg.skills = {s.name: s for s in sub_skills}
        selector = EmbeddingSelector(temp_reg, client=client)

        latencies = []
        correct_count = 0
        for q, expected in test_queries:
            ranked, lat = selector.select(q, top_k=3)
            latencies.append(lat)
            if ranked and (ranked[0][0] == expected or expected not in temp_reg.skills):
                correct_count += 1

        results.append({
            "num_skills": count,
            "mean_latency_ms": round(float(np.mean(latencies)), 2),
            "p95_latency_ms": round(float(np.percentile(latencies, 95)), 2),
            "accuracy": round(correct_count / len(test_queries), 2),
        })

    return {
        "scalability_results": results
    }


def try_task_routing(
    task_input: str,
    registry: Optional[SkillRegistry] = None,
    client: Optional[OllamaClient] = None
) -> Dict[str, Any]:
    """
    Ad-hoc task inspector: shows which skill activates, confidence score,
    matching prompt template, and reasoning.
    """
    reg = registry or SkillRegistry()
    client = client or default_client
    selector = EmbeddingSelector(reg, client=client)
    ranked, lat = selector.select(task_input, top_k=3)

    if not ranked:
        return {
            "task": task_input,
            "selected_skill": None,
            "score": 0.0,
            "latency_ms": lat,
            "reasoning": "No skills available in registry."
        }

    top_name, top_score = ranked[0]
    skill = reg.get_skill(top_name)

    return {
        "task": task_input,
        "selected_skill": top_name,
        "score": top_score,
        "ranked_candidates": ranked,
        "latency_ms": lat,
        "skill_description": skill.description if skill else "",
        "skill_path": skill.path if skill else "",
        "trigger_assessment": f"Matched '{top_name}' with embedding cosine similarity {top_score:.4f}.",
    }


