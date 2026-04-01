.PHONY: help install dev test lint fmt check run clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package
	pip install -e .

dev:  ## Install with dev dependencies
	pip install -e ".[dev]"

test:  ## Run tests
	pytest -v

lint:  ## Run linter
	ruff check codyflow/ tests/

fmt:  ## Format code
	ruff format codyflow/ tests/
	ruff check --fix codyflow/ tests/

check: lint test  ## Run lint + tests

run:  ## Start the web server
	python -m codyflow

clean:  ## Remove build artifacts
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
