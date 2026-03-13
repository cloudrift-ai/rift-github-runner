.PHONY: setup test lint fmt

setup:
	python3 -m venv .venv
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest -vv

lint:
	.venv/bin/ruff check rift_github_runner/ tests/
	.venv/bin/ruff format --check rift_github_runner/ tests/

fmt:
	.venv/bin/ruff format rift_github_runner/ tests/
	.venv/bin/ruff check --fix rift_github_runner/ tests/
