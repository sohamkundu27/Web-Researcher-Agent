.PHONY: help install dev-install test lint format clean run

help:
	@echo "Web Researcher Agent - Development Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  make install       - Install dependencies"
	@echo "  make dev-install   - Install dependencies with dev tools"
	@echo "  make test          - Run unit tests"
	@echo "  make lint          - Run code linting"
	@echo "  make format        - Format code with black"
	@echo "  make clean         - Clean build artifacts"
	@echo "  make run-example   - Run example script"

install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install pytest pytest-asyncio black flake8 mypy

test:
	pytest tests/ -v

lint:
	flake8 src/ tests/ examples/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/ examples/ setup.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .mypy_cache/

run-example:
	python -m examples.research_example
