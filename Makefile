.PHONY: help install run test format check clean

# Default target
help:
	@echo "Available commands:"
	@echo "  install - Install dependencies"
	@echo "  run     - Start the GitHub App server"
	@echo "  test    - Run syntax and validation checks"
	@echo "  format  - Format code"
	@echo "  clean   - Clean up temporary files"

# Setup
install:
	uv sync
	@echo "Dependencies installed!"

# Run the app
run:
	@echo "Starting JIRA GitHub App server..."
	python github_app.py

# Testing and validation
test:
	@echo "Checking syntax..."
	@python -m py_compile *.py
	@echo "Validating configuration..."
	@python -c "from config import Config; missing = Config.validate(); print('✅ All checks passed!' if not missing else f'❌ Missing env vars: {missing}')"

# Code formatting
format:
	@echo "Formatting code..."
	@which black >/dev/null 2>&1 && black . || echo "Install black with: uv add --dev black"

# Cleanup
clean:
	@echo "Cleaning up..."
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true