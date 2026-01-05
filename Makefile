.PHONY: install dev lint format test clean

install:
	pip install -e .

dev:
	pip install -e ".[dev,viz]"
	pre-commit install

lint:
	ruff check src/ tests/
	black --check src/ tests/

format:
	ruff check --fix src/ tests/
	black src/ tests/

test:
	pytest tests/ -v

test-fast:
	pytest tests/ -v -m "not hardware and not slow"

clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
