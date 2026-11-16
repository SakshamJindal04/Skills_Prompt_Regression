.PHONY: test lint typecheck format coverage check-docs run-dev build demo demo-quick verify clean

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
STREAMLIT ?= .venv/bin/streamlit
RUFF ?= .venv/bin/ruff
MYPY ?= .venv/bin/mypy

test:
	$(PYTEST) tests/ -v

lint:
	$(RUFF) check core/ app/ cli.py

typecheck:
	$(MYPY) core/

format:
	$(RUFF) format core/ app/ cli.py

coverage:
	$(PYTEST) --cov=core --cov-report=term-missing --cov-fail-under=85

check-docs:
	$(PYTHON) scripts/check_docs_numbers.py

run-dev:
	$(STREAMLIT) run app/Home.py --server.port 8501

build:
	uv pip install -e .

demo:
	$(PYTHON) scripts/demo.py

demo-quick:
	$(PYTHON) scripts/demo.py --quick

verify:
	$(PYTHON) scripts/verify_mysql.py
	$(PYTHON) scripts/check_docs_numbers.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage .mypy_cache .ruff_cache
