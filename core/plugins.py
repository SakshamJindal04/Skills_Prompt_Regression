"""
Extension Points & Plugin Registry for Model Providers and Custom Checks.
Provides:
1. `@register_model_provider(name)` decorator and `get_model_provider(name)`.
2. `@register_check(name)` decorator and `get_custom_check(name)`.
3. Extensible interfaces for Ollama, Local vLLM, llama.cpp, and Mock providers.
"""

from typing import Dict, Any, Callable, Optional, Tuple, Type, List
import logging

logger = logging.getLogger("plugins")

# Registry storage
_MODEL_PROVIDERS: Dict[str, Type["BaseModelProvider"]] = {}
_CUSTOM_CHECKS: Dict[str, Callable[[Any, Dict[str, Any]], Tuple[bool, str]]] = {}


# --- Model Provider Interface ---
class BaseModelProvider:
    """Abstract base class for local model execution providers."""
    def __init__(self, model_id: str = "default", **kwargs):
        self.model_id = model_id
        self.kwargs = kwargs

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        seed: Optional[int] = None,
    ) -> Tuple[str, float]:
        """Returns (output_text, latency_ms)."""
        raise NotImplementedError

    def get_digest(self) -> Optional[str]:
        return "sha256:unknown"

    def is_available(self) -> bool:
        return True


def register_model_provider(name: str):
    """Decorator to register a model provider backend."""
    def decorator(cls: Type[BaseModelProvider]):
        _MODEL_PROVIDERS[name.lower().strip()] = cls
        logger.info(f"Registered model provider: {name}")
        return cls
    return decorator


def get_model_provider(name: str, model_id: str = "default", **kwargs) -> BaseModelProvider:
    """Factory retrieving a configured model provider instance."""
    provider_cls = _MODEL_PROVIDERS.get(name.lower().strip())
    if not provider_cls:
        raise ValueError(
            f"Unknown model provider '{name}'. Available: {sorted(list(_MODEL_PROVIDERS.keys()))}"
        )
    return provider_cls(model_id=model_id, **kwargs)


def list_model_providers() -> List[str]:
    return sorted(list(_MODEL_PROVIDERS.keys()))


# --- Custom Check Interface ---
def register_check(name: str):
    """Decorator to register a custom evaluation check function."""
    def decorator(fn: Callable[[Any, Dict[str, Any]], Tuple[bool, str]]):
        _CUSTOM_CHECKS[name.lower().strip()] = fn
        logger.info(f"Registered custom check: {name}")
        return fn
    return decorator


def get_custom_check(name: str) -> Optional[Callable[[Any, Dict[str, Any]], Tuple[bool, str]]]:
    """Retrieves a registered check function by name."""
    return _CUSTOM_CHECKS.get(name.lower().strip())


def list_custom_checks() -> List[str]:
    return sorted(list(_CUSTOM_CHECKS.keys()))


# --- Built-in Provider Implementations ---

@register_model_provider("mock")
class MockModelProvider(BaseModelProvider):
    """Deterministic offline mock provider for air-gapped environments and testing."""
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        seed: Optional[int] = None,
    ) -> Tuple[str, float]:
        if "sql" in prompt.lower() or "select" in prompt.lower():
            out = "SELECT * FROM orders WHERE status = 'completed';"
        elif "sentiment" in prompt.lower():
            out = "POSITIVE"
        else:
            out = '{"action": "final_answer", "answer": "Mock result."}'
        return out, 5.0

    def get_digest(self) -> str:
        return "sha256:mock_model_digest_0000"


@register_model_provider("ollama")
class OllamaProvider(BaseModelProvider):
    """Default local Ollama provider."""
    def __init__(self, model_id: str = "qwen2.5:3b", **kwargs):
        super().__init__(model_id, **kwargs)
        from core.llm import default_client
        self.client = default_client

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        seed: Optional[int] = None,
    ) -> Tuple[str, float]:
        resp = self.client.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            seed=seed,
            model=self.model_id,
        )
        return resp.text, resp.latency_ms

    def get_digest(self) -> Optional[str]:
        meta = self.client.get_model_metadata(self.model_id)
        return meta.get("digest")


@register_model_provider("vllm")
class LocalVLLMProvider(BaseModelProvider):
    """Local vLLM OpenAI-compatible endpoint (http://localhost:8000/v1)."""
    def __init__(self, model_id: str = "default", base_url: str = "http://localhost:8000/v1", **kwargs):
        super().__init__(model_id, **kwargs)
        self.base_url = base_url

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        seed: Optional[int] = None,
    ) -> Tuple[str, float]:
        import requests
        import time
        t0 = time.perf_counter()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model_id,
                    "messages": messages,
                    "temperature": temperature,
                    "seed": seed,
                },
                timeout=10,
            )
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"], lat
            return f"ERROR: vLLM request failed with status {resp.status_code}", lat
        except Exception as e:
            return f"ERROR: vLLM unreachable: {e}", 0.0


@register_model_provider("llama_cpp")
class LlamaCppProvider(BaseModelProvider):
    """Local llama.cpp server endpoint (http://localhost:8080/completion)."""
    def __init__(self, model_id: str = "default", base_url: str = "http://localhost:8080", **kwargs):
        super().__init__(model_id, **kwargs)
        self.base_url = base_url

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        seed: Optional[int] = None,
    ) -> Tuple[str, float]:
        import requests
        import time
        t0 = time.perf_counter()
        full_p = f"{system}\n\n{prompt}" if system else prompt
        try:
            resp = requests.post(
                f"{self.base_url}/completion",
                json={"prompt": full_p, "temperature": temperature, "seed": seed or -1},
                timeout=10,
            )
            lat = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                return resp.json().get("content", ""), lat
            return f"ERROR: llama.cpp failed with {resp.status_code}", lat
        except Exception as e:
            return f"ERROR: llama.cpp unreachable: {e}", 0.0
