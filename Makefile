.PHONY: help init install test lint typecheck format run docker-build docker-run clean all release

.DEFAULT_GOAL := help

help: ## Show available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

init: ## Initialize runtime files
	python runner.py --init

install: ## Install package in development mode
	pip install -e ".[dev]"

test: ## Run tests with coverage
	python -m pytest tests/ --cov --cov-fail-under=90 -q

lint: ## Run ruff linter
	ruff check .

typecheck: ## Run mypy type checking
	mypy kernel/ --ignore-missing-imports

format: ## Format code with ruff
	ruff format .

run: ## Run the kernel (usage: make run GOAL="Build a REST API")
	python runner.py --goal "$(GOAL)"

docker-build: ## Build Docker image
	docker build -t ai-coding-guidance-skills .

docker-run: ## Run Docker container
	docker run -p 8000:8000 ai-coding-guidance-skills

clean: ## Remove generated files
	rm -rf __pycache__ .pytest_cache .coverage .ruff_cache *.egg-info dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

all: lint typecheck test ## Run lint, typecheck, and test

release: ## Create a git tag from pyproject.toml version
	$(eval VERSION := $(shell python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"))
	git tag -a "v$(VERSION)" -m "Release v$(VERSION)"
	@echo "Created tag v$(VERSION)"
