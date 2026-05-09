.PHONY: help install dev test lint format typecheck eval ci clean

PY := .venv/bin/python

help:
	@echo "install     Install backend deps (creates .venv if missing)"
	@echo "dev         Run FastAPI with reload"
	@echo "test        Run pytest"
	@echo "lint        ruff check + format check"
	@echo "format      Apply ruff format"
	@echo "typecheck   mypy --strict"
	@echo "eval        Run evals offline"
	@echo "ci          lint + typecheck + test"

install:
	uv venv
	uv pip install -e '.[dev]'

dev:
	$(PY) -m uvicorn backend.app.main:app --reload

test:
	$(PY) -m pytest backend/tests -q

lint:
	$(PY) -m ruff check backend
	$(PY) -m ruff format --check backend

format:
	$(PY) -m ruff format backend

typecheck:
	$(PY) -m mypy --strict backend/app

eval:
	$(PY) -m evals.run --offline

ci: lint typecheck test

clean:
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -exec rm -rf {} + 2>/dev/null || true
