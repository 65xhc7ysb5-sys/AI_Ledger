# Makefile
.PHONY: test run install clean

install:
	uv sync

test:
	uv run python tests/test_e2e.py

run:
	uv run streamlit run home.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
