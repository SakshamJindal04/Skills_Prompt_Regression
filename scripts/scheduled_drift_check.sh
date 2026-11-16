#!/bin/bash
# Scheduled Model Drift Check Script
# Intended for execution via cron or systemd timer (Linux/macOS) or Task Scheduler (Windows WSL/Git Bash)
# Recommended cron entry:
# 0 2 * * * cd /path/to/Responsible_Ai && ./scripts/scheduled_drift_check.sh >> logs/drift_cron.log 2>&1

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

PYTHON_BIN=".venv/bin/python"
if [ ! -f "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Running scheduled model drift check..."

# Run drift CLI check for baseline model
"${PYTHON_BIN}" cli.py drift --model qwen2.5:3b

# Run audit chain verification
"${PYTHON_BIN}" cli.py audit-verify

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Drift check completed successfully."

