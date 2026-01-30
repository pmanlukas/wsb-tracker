# WSB Tracker Makefile
# Common development tasks

.PHONY: help install dev test lint format clean build run scan

# Default target
help:
	@echo "WSB Tracker - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install     Install package in current environment"
	@echo "  make dev         Install with development dependencies"
	@echo "  make all         Install with all optional dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test        Run tests with coverage"
	@echo "  make lint        Run linter (ruff)"
	@echo "  make format      Auto-format code"
	@echo "  make typecheck   Run type checker (mypy)"
	@echo ""
	@echo "Usage:"
	@echo "  make scan        Run a quick scan"
	@echo "  make top         Show top tickers"
	@echo "  make watch       Start continuous monitoring"
	@echo ""
	@echo "Build:"
	@echo "  make build       Build distribution packages"
	@echo "  make clean       Remove build artifacts"

# =============================================================================
# Setup
# =============================================================================

install:
	pip install -e .

dev:
	pip install -e ".[dev]"

all:
	pip install -e ".[dev,all]"

# =============================================================================
# Development
# =============================================================================

test:
	pytest -v --cov=wsb_tracker --cov-report=term-missing

test-fast:
	pytest -v -x --tb=short

lint:
	ruff check wsb_tracker tests

format:
	ruff check --fix wsb_tracker tests
	ruff format wsb_tracker tests

typecheck:
	mypy wsb_tracker

# =============================================================================
# Usage shortcuts
# =============================================================================

scan:
	wsb scan --limit 50

top:
	wsb top

watch:
	wsb watch --interval 300

# =============================================================================
# Build & Clean
# =============================================================================

build:
	python -m build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
