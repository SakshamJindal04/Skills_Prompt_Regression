# Known Issues & Operational Considerations

This document records operational edge cases, platform dependencies, and known constraints in the current prototype implementation.

---

## 1. Multiple Concurrent Models in Ollama on 16GB Machines
- **Issue**: Attempting to query `qwen2.5:3b`, `llama3.2:3b`, and `gemma2:2b` simultaneously without configuring memory limits can cause macOS Unified Memory or Linux swap pressure.
- **Resolution**: We advise setting `export OLLAMA_MAX_LOADED_MODELS=1` in developer environments. Ollama automatically unloads the previous model before serving the next, keeping VRAM utilization below 4GB.

---

## 2. Preamble Text in 3B Model JSON Outputs
- **Issue**: Without strict formatting constraints, 3B models occasionally prepend conversational pleasantries (e.g., *"Here is the requested JSON output:"*) before the JSON object, which causes standard `json.loads()` to raise `JSONDecodeError`.
- **Resolution**: `core/checkers.py` incorporates `extract_json_from_text()`, which uses regular expression bracket matching (`r'\{.*\}'`) and markdown code block extraction to safely isolate JSON payloads before schema validation.

---

## 3. GitHub Actions Execution Environment
- **Issue**: Standard GitHub-hosted runners (`ubuntu-latest`) do not include GPU acceleration or local Ollama daemons, causing CLI regression runs that call Ollama to fail if run on cloud infrastructure without pre-pulled weights.
- **Resolution**: The provided workflow (`.github/workflows/regression_gate.yml`) is documented and configured for **self-hosted runners** equipped with local Ollama weights. We verified the CLI gate locally.

---

## 4. Git Workspace Boundary
- **Issue**: The Git repository tracked by `core/repo.py` resides inside the managed subfolder `workspace/` (`workspace/.git`), rather than the project root.
- **Resolution**: All versioning commands in `core/repo.py` and `app/pages/1_Repository.py` explicitly resolve to `get_workspace_path()`. Running Git commands from the project root will not show the prompt commit history unless targeting `-C workspace`.

