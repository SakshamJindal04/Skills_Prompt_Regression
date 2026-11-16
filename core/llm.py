"""
Ollama client wrapper with temperature/seed control, timing, caching, and embeddings.
"""

import os
import time
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Raised when Ollama generation fails or returns an error."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when Ollama server cannot be reached."""
    pass


@dataclass
class LLMResponse:
    text: str
    latency_ms: float
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw: Optional[Dict[str, Any]] = None


class OllamaClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        embed_model: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.default_model = default_model or os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
        self.embed_model = embed_model or os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        self._cache: Dict[str, LLMResponse] = {}
        self._last_latencies: Dict[str, float] = {}

    def is_available(self) -> tuple[bool, str]:
        """Check if Ollama server is running and models are accessible."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                return True, f"Connected to Ollama. Available models: {', '.join(models)}"
            return False, f"Ollama HTTP error: status {resp.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Cannot connect to Ollama at {self.base_url}: {e}. Ensure Ollama is running ('ollama serve')."

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        seed: Optional[int] = None,
        model: Optional[str] = None,
        use_cache: bool = True,
        format_json: bool = False,
    ) -> LLMResponse:
        """
        Generate a completion from Ollama with temperature/seed control and latency measurement.
        """
        model = model or self.default_model
        cache_key = f"{model}|{system}|{prompt}|{temperature}|{seed}|{format_json}"
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            return LLMResponse(
                text=cached.text,
                latency_ms=cached.latency_ms,
                model=cached.model,
                prompt_tokens=cached.prompt_tokens,
                completion_tokens=cached.completion_tokens,
                raw=cached.raw,
            )

        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": float(temperature),
            },
        }
        if seed is not None:
            payload["options"]["seed"] = int(seed)
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"

        start_time = time.perf_counter()
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
        except requests.exceptions.ConnectionError as e:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama at {self.base_url}. Ensure 'ollama serve' is active. Details: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"Ollama request failed: {e}") from e

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        if resp.status_code != 200:
            raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        response_text = data.get("response", "")
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        result = LLMResponse(
            text=response_text,
            latency_ms=round(latency_ms, 2),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            raw=data,
        )

        self._last_latencies[model] = round(latency_ms / 1000.0, 3)

        if use_cache:
            self._cache[cache_key] = result

        return result

    def embed(self, text: str, model: Optional[str] = None) -> List[float]:
        """
        Get vector embeddings for a given text.
        Supports both /api/embeddings and modern /api/embed endpoints.
        """
        model = model or self.embed_model
        try:
            # Try /api/embeddings first
            resp = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": model, "prompt": text},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "embedding" in data:
                    return data["embedding"]

            # Fallback to /api/embed
            resp = requests.post(
                f"{self.base_url}/api/embed",
                json={"model": model, "input": text},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                embeddings = data.get("embeddings", [])
                if embeddings:
                    return embeddings[0]

            raise OllamaError(f"Embedding API returned status {resp.status_code}: {resp.text}")
        except requests.exceptions.ConnectionError as e:
            raise OllamaConnectionError(
                f"Failed to connect to Ollama for embedding. Ensure 'ollama serve' is active. Details: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise OllamaError(f"Ollama embedding request failed: {e}") from e

    def get_last_latency(self, model: str) -> Optional[float]:
        """Return the most recent latency measurement in seconds for a model."""
        return self._last_latencies.get(model)

    def get_last_latencies(self) -> Dict[str, float]:
        """Return all tracked model latencies in seconds."""
        return dict(self._last_latencies)

    def get_installed_models(self) -> List[Dict[str, Any]]:
        """List models installed in Ollama via /api/tags."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
        except Exception as e:
            logger.warning(f"Failed to fetch installed models: {e}")
        return []

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """List models currently loaded in memory via /api/ps."""
        try:
            resp = requests.get(f"{self.base_url}/api/ps", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("models", [])
        except Exception as e:
            logger.warning(f"Failed to fetch loaded models: {e}")
        return []

    def get_model_metadata(self, model_name: str) -> Dict[str, Any]:
        """
        Fetch model id, digest, family, parameter size, and details from Ollama.
        """
        installed = self.get_installed_models()
        digest = None
        size_bytes = 0
        modified_at = None
        for m in installed:
            name = m.get("name", "")
            if name == model_name or name.split(":")[0] == model_name.split(":")[0]:
                digest = m.get("digest")
                size_bytes = m.get("size", 0)
                modified_at = m.get("modified_at")
                break

        family = "unknown"
        param_size = "unknown"
        quant = "unknown"
        context_window = 4096
        capabilities = []
        try:
            resp = requests.post(f"{self.base_url}/api/show", json={"name": model_name}, timeout=5)
            if resp.status_code == 200:
                sdata = resp.json()
                details = sdata.get("details", {})
                family = details.get("family", "unknown")
                param_size = details.get("parameter_size", "unknown")
                quant = details.get("quantization_level", "unknown")
                capabilities = sdata.get("capabilities", [])
                mod_info = sdata.get("model_info", {})
                for k, v in mod_info.items():
                    if "context_length" in k:
                        context_window = v
                        break
        except Exception as e:
            logger.debug(f"Could not fetch show metadata for {model_name}: {e}")

        return {
            "model_id": model_name,
            "digest": digest or "unknown",
            "family": family,
            "parameter_size": param_size,
            "quantization": quant,
            "context_window": context_window,
            "capabilities": capabilities,
            "size_bytes": size_bytes,
            "modified_at": modified_at,
        }

    def unload_model(self, model_name: str) -> bool:
        """
        Explicitly unloads a model from memory by sending keep_alive: 0.
        Essential for respecting OLLAMA_MAX_LOADED_MODELS=1 constraints.
        """
        try:
            resp = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model_name, "prompt": "", "keep_alive": 0},
                timeout=5
            )
            return resp.status_code == 200
        except Exception as e:
            logger.debug(f"Could not unload model {model_name}: {e}")
            return False

    def show(self, model_name: str) -> Dict[str, Any]:
        """Convenience alias returning full metadata and details for a model."""
        return self.get_model_metadata(model_name)

    def get_judge_model(self, model_under_test: Optional[str] = None) -> str:
        """
        Selects a judge model from a different model family than the model under test.
        Configurable via JUDGE_MODEL in .env.
        Example: gemma2:2b judging qwen outputs; qwen2.5:3b judging llama/gemma outputs.
        """
        env_judge = os.getenv("JUDGE_MODEL", "gemma2:2b")
        if not model_under_test:
            return env_judge

        model_lower = str(model_under_test).lower()
        judge_lower = str(env_judge).lower()

        # If model under test is in the same family as env_judge, swap judge to an alternate family
        if "qwen" in model_lower:
            if "qwen" in judge_lower:
                return "gemma2:2b"
            return env_judge
        elif "gemma" in model_lower:
            if "gemma" in judge_lower:
                return "qwen2.5:3b"
            return env_judge
        elif "llama" in model_lower:
            if "llama" in judge_lower:
                return "qwen2.5:3b"
            return env_judge

        return env_judge


# Singleton instance
default_client = OllamaClient()

