# Operational Runbook: Skill & Prompt Regression Manager

**Version:** 2.0.0 (Industry Hardened)  
**System Classification:** Local-First AI Quality & Regression Management System  
**Default Host Ports:** Streamlit UI (`8501`), FastAPI REST (`8000`), MySQL (`3306`), Ollama (`11434`)  

---

## 1. System Overview & Architecture

RegGuard operates as a local-first, air-gapped regression evaluation gate for local LLMs and autonomous agent workflows.

```
+-------------------------------------------------------------------------------+
|                             CLIENT INTERFACES                                 |
|   - Streamlit Web UI (http://localhost:8501)                                 |
|   - Console CLI (`regguard` or `python cli.py`)                               |
|   - Local REST API (`http://127.0.0.1:8000`)                                  |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                            REGGUARD CORE ENGINE                               |
|   - Pydantic v2 Config & RBAC Auth (`core/config.py`, `core/auth.py`)         |
|   - Statistical Gate & Frozen Rules (`core/decision_rules.py`)                |
|   - Multi-Dimensional Drift Telemetry (`core/drift_analysis.py`)               |
|   - Deterministic Invariant Checkers (`core/checkers.py`, `core/agent.py`)    |
|   - Cryptographic Audit Chaining (`core/audit.py`, `core/bundle.py`)          |
+-------------------+-----------------------------------+-----------------------+
                    |                                   |
                    v                                   v
+-----------------------------------+   +---------------------------------------+
|        LOCAL PERSISTENCE          |   |          LOCAL LLM INFERENCE          |
|  - MySQL 8.0 (3306)               |   |  - Local Ollama Daemon (11434)        |
|  - SQLite Fallback (.db)          |   |  - Models: Qwen2.5 3B, Llama3.2 3B,   |
|  - Alembic Auto-Migrations        |   |            Gemma2 2B                  |
|  - Append-Only Audit JSONL        |   |  - Deterministic Seeds (k=5)          |
+-----------------------------------+   +---------------------------------------+
```

---

## 2. Day-to-Day Operations

### 2.1 Starting Services
```bash
# 1. Ensure local Ollama is active with required models
ollama list
# If Ollama is inactive:
ollama serve &

# 2. Start the Streamlit Dashboard (default port 8501)
make run-dev
# or:
.venv/bin/streamlit run app/Home.py --server.port 8501

# 3. (Optional) Start the FastAPI REST API (default port 8000)
.venv/bin/uvicorn core.api:app --host 127.0.0.1 --port 8000 --reload
```

### 2.2 Running a Quality Regression Gate via CLI
```bash
# Run comparison between active baseline and candidate commit
regguard --base 7c255ba --cand c836eb2 --suite analytics -k 5

# Quick smoke test mode (k=3, 20 test sample)
regguard --quick

# Check statistical power for custom test suite size N and repetitions k
regguard power --n 108 --k 5
```

### 2.3 Creating and Verifying a Reproducibility Bundle
```bash
# 1. Package comparison run #100 into a cryptographically sealed ZIP
regguard bundle 100 --output results/bundles/run_100_bundle.zip

# 2. Replay stored traces offline with zero model calls (asserts exact reproduction)
regguard replay results/bundles/run_100_bundle.zip
```

### 2.4 Multi-Stage Environment Promotion
1. Open dashboard at `http://localhost:8501` and navigate to **Environments** (`16_Environments.py`).
2. Review active baselines across `dev`, `staging`, and `prod`.
3. To promote `dev` to `staging`: requires passing gate in `dev` and a `reviewer` or `admin` role approval.
4. To promote `staging` to `prod`: requires passing gate in `staging` and an `admin` role approval.
5. All promotions write an immutable record to `logs/audit.jsonl` and database table `environment_baselines`.

---

## 3. Troubleshooting Common Failure Modes

### 3.1 Ollama Daemon Offline or Models Missing
- **Symptom:** UI displays top bar status `Ollama: OFFLINE`, or CLI returns `Cannot connect to Ollama at http://localhost:11434`.
- **Diagnostic:**
  ```bash
  curl http://localhost:11434/api/tags
  ```
- **Remediation:**
  1. Start the daemon: `ollama serve`.
  2. If models are missing:
     ```bash
     ollama pull qwen2.5:3b
     ollama pull llama3.2:3b
     ollama pull gemma2:2b
     ollama pull nomic-embed-text
     ```
  3. If VRAM is constrained on 16GB systems, export `export OLLAMA_MAX_LOADED_MODELS=1` to force serial unloading.

### 3.2 Database Connection Failures & SQLite Fallback
- **Symptom:** Logs show `MySQL connection refused; falling back to SQLite`.
- **Diagnostic:**
  ```bash
  python scripts/verify_mysql.py
  ```
- **Remediation:**
  1. If running native MySQL, ensure service is running: `brew services start mysql` or `systemctl start mysql`.
  2. If using Docker Compose:
     ```bash
     docker compose up -d db
     ```
  3. Note: The system automatically and safely falls back to local `regression_manager.db` SQLite database with zero user intervention.

### 3.3 Database Migration Desynchronization
- **Symptom:** SQLAlchemy queries fail with `no such table` or `column missing`.
- **Diagnostic:**
  ```bash
  .venv/bin/alembic current
  ```
- **Remediation:**
  Run Alembic upgrade to bring the active database to `head`:
  ```bash
  .venv/bin/alembic upgrade head
  ```

### 3.4 Cryptographic Audit Chain Broken
- **Symptom:** `regguard audit-verify` or `tests/test_audit_chain.py` fails with `Audit chain broken at event #X`.
- **Root Cause:** A direct SQL `UPDATE` or manual file modification occurred on `logs/audit.jsonl` or `audit_logs` table.
- **Remediation:**
  1. Inspect the tampered entry: `regguard audit-inspect <id>`.
  2. In production, investigate unauthorized database write access.
  3. Re-sync from verified backup or append a signed incident remediation entry.

---

## 4. Backup & Disaster Recovery

### 4.1 Backup Procedure
```bash
# 1. Dump MySQL Database (if utilizing MySQL backend)
mysqldump -u regression_user -pregression_pass -h localhost regression_db > backups/mysql_backup_$(date +%Y%m%d).sql

# 2. Backup SQLite Database (if utilizing SQLite backend)
sqlite3 regression_manager.db ".backup 'backups/sqlite_backup_$(date +%Y%m%d).db'"

# 3. Archive Audit Ledger & Credentials
tar -czf backups/audit_archive_$(date +%Y%m%d).tar.gz logs/audit.jsonl data/credentials.json policy.yaml
```

### 4.2 Disaster Recovery Procedure
```bash
# 1. Restore MySQL from dump
mysql -u regression_user -pregression_pass -h localhost regression_db < backups/mysql_backup_YYYYMMDD.sql

# 2. Or restore SQLite database
cp backups/sqlite_backup_YYYYMMDD.db regression_manager.db

# 3. Verify database integrity
python scripts/verify_mysql.py
pytest tests/test_db.py
```

---

## 5. Model Upgrades & Model Swapping Runbook

When evaluating a new model (e.g., upgrading from `qwen2.5:3b` to `qwen2.5:7b` or swapping to `llama3.2:3b`):

1. **Pull Model Locally:**
   ```bash
   ollama pull <new_model_id>
   ```
2. **Execute Cross-Model Benchmark Suite:**
   ```bash
   python scripts/run_cross_model_benchmark.py --cand-model <new_model_id>
   ```
3. **Inspect Critical Invariants in Model Matrix Dashboard:**
   - Open `http://localhost:8501` and navigate to **Model Matrix** (`9_Model_Matrix.py`).
   - Check the **Candidate V2 Gate Comparison**:
     - Check discordant pair counts: $b$ (regressed) and $c$ (fixed).
     - **Verify Critical Regressions ($b_{\text{crit}}$):** If $b_{\text{crit}} \ge 1$, the model swap is immediately **BLOCKED**.
     - Check $p_{95}$ latency delta: ensure latency does not exceed operational SLAs.
4. **Update Production Configuration (`policy.yaml`):**
   - If the model achieves a passing gate, update `allowed_models` and `default_model` in `policy.yaml`:
     ```yaml
     model:
       default: "<new_model_id>"
     ```
   - Commit changes to Git with clear rationale:
     ```bash
     git add policy.yaml
     git commit -m "chore(model): upgrade default model to <new_model_id> after passing regression gate"
     ```
