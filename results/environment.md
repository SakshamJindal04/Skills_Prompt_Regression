# System & Execution Environment

Recorded during the empirical evaluation pass of the Skill & Prompt Regression Manager.

## Hardware & Operating System
- **Platform**: macOS (Darwin 24.x aarch64 - Apple Silicon)
- **RAM**: 16 GB Unified Memory
- **CPU**: Apple M-Series

## Runtime & Tooling
- **Python**: `3.12.14` (CPython aarch64)
- **Package Manager**: `uv`
- **Database Engine (Primary)**: MySQL 8.0.x on `localhost:3306` (database `regression_db`)
- **Database Engine (Fallback)**: SQLite 3.x (`regression_manager.db`)
- **Local LLM Server**: Ollama `0.32.5` running on `http://localhost:11434`
- **Streamlit**: `1.43.2`
- **Pytest**: `9.2.0` with `pytest-cov 7.1.0`

## Installed Ollama Models & Cryptographic Digests

| Model ID | Pipeline Role | Architecture | Parameters | Quantization | SHA-256 Digest |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `qwen2.5:3b` | Default Baseline | Qwen2 | 3.09B | Q4_K_M | `357c53fb659c223c683ee065790c6caea47fce54a7ea39de32f91e9bf70d37e2` |
| `llama3.2:3b` | Candidate 1 | Llama3.2 | 3.21B | Q4_K_M | `a80c4f17acd55265feec403c7a6651a2066bb025179605d60293999903c5ae60` |
| `gemma2:2b` | Candidate 2 / Judge | Gemma2 | 2.61B | Q4_0 | `8ccf136fdd5287f3b5c65f9bf3ffae88950fc1d08e6f1f417f7d14ff0e68be41` |
| `nomic-embed-text` | Embedding Selector | Nomic Bert | 137M | F16 | `0a109f422b477b75f8a0026e9ddde675a850a5813735ff64bf87910fffa7dd46` |

## Resource Management
- **VRAM Concurrency Control**: `OLLAMA_MAX_LOADED_MODELS=1` recommended when running on 16GB machines to avoid OS unified memory swapping.
- **Seeds**: Fixed seeds per run index ($s = 42 + 1000 \times \text{run\_index}$) for reproducible generation.

