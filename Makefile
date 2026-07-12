.PHONY: help setup install lint format typecheck test check browser hooks clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup:  ## Full dev bootstrap (uv, deps, browser, hooks)
	./setup.sh

install:  ## Install dependencies via uv
	uv sync

browser:  ## Download the Playwright browser (required once)
	uv run rfbrowser init

hooks:  ## Install pre-commit hooks
	uv run pre-commit install
	uv run pre-commit install --hook-type pre-push

lint:  ## Lint with ruff
	uv run ruff check src tests

format:  ## Format with ruff
	uv run ruff format src tests

typecheck:  ## Type-check with mypy
	uv run mypy

test:  ## Run unit tests
	uv run pytest -q

check: lint typecheck test  ## Run lint + types + tests
	uv run ruff format --check src tests

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build browser
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
