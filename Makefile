.PHONY: test lint cov validate

test:
	uv run pytest

lint:
	uv run ruff check .

cov:
	uv run pytest --cov=skills --cov=examples --cov-report=term-missing --cov-fail-under=90

validate:
	claude plugin validate . --strict
