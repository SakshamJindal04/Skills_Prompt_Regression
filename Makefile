.PHONY: demo demo-quick test coverage verify run-app clean

PYTHON ?= .venv/bin/python
PYTEST ?= .venv/bin/pytest
STREAMLIT ?= .venv/bin/streamlit

demo:
	$(PYTHON) scripts/demo.py

demo-quick:
	$(PYTHON) scripts/demo.py --quick

test:
	$(PYTEST) tests/ -v

coverage:
	$(PYTEST) --cov=core --cov-report=term-missing

verify:
	$(PYTHON) scripts/verify_mysql.py
	$(PYTHON) scripts/check_docs_numbers.py

run-app:
	$(STREAMLIT) run app/Home.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage

