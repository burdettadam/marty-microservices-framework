# Marty Microservices Framework - Makefile
# Convenient commands for framework development and usage

.PHONY: help setup install test dev setup-dev generate new clean docs scripts

# Default target
help: ## Show this help message
	@echo "Marty Microservices Framework"
	@echo "=============================="
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ==============================================================================
# Setup & Installation
# ==============================================================================

setup: ## Complete setup: install deps, hooks, and validate
	@echo "🚀 Setting up Marty Microservices Framework..."
	@uv sync --group dev
	@uv run playwright install chromium
	@uv run pre-commit install
	@python3 scripts/validate_templates.py
	@echo "✅ Setup complete!"

install: ## Install framework dependencies
	@echo "📦 Installing framework dependencies..."
	@uv sync --group dev
	@echo "✅ Dependencies installed!"

# ==============================================================================
# Testing
# ==============================================================================

test: ## Run all tests (unit + integration + e2e)
	@echo "🧪 Running all tests..."
	@uv run pytest -v

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	@uv run pytest -m unit -v

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	@uv run pytest -m integration -v

test-e2e: ## Run end-to-end tests (includes docker containers)
	@echo "🧪 Running E2E tests..."
	@uv run pytest -m e2e -v

test-kind: ## Run Kind-based E2E tests only (no docker containers)
	@echo "🎭 Running Kind + Playwright E2E tests..."
	@uv run pytest tests/e2e/test_kind_playwright_e2e.py tests/e2e/simple_kind_playwright_test.py -v

test-coverage: ## Run all tests with coverage report
	@echo "🧪 Running tests with coverage..."
	@uv run pytest --cov=src --cov-report=html --cov-report=term

test-quick: ## Run tests with fail-fast mode
	@echo "🧪 Running quick tests (fail-fast)..."
	@uv run pytest -x --tb=short

# ==============================================================================
# Development
# ==============================================================================

dev: ## Setup complete development environment
	@echo "🔧 Setting up development environment..."
	@$(MAKE) setup
	@echo "🎉 Development environment ready!"
	@echo "💡 Try: make test, make generate, make new"

setup-dev: ## Run comprehensive development setup script
	@echo "🚀 Running comprehensive development setup..."
	@python3 scripts/setup_dev.py

check: ## Run all code quality checks
	@echo "🔍 Running code quality checks..."
	@uv run ruff check .
	@uv run ruff format --check .
	@python3 -m mypy scripts/ --config-file mypy.ini
	@python3 scripts/validate_templates.py
	@echo "✅ All checks passed!"

fix: ## Fix code formatting and linting issues
	@echo "🔧 Fixing code issues..."
	@uv run ruff check --fix .
	@uv run ruff format .
	@echo "✅ Code formatting fixed!"

security: ## Run security checks
	@echo "🔒 Running security checks..."
	@uv run bandit -r src/

# ==============================================================================
# Code Generation
# ==============================================================================

generate: ## Generate a service (make generate TYPE=fastapi NAME=my-service)
	@if [ -z "$(TYPE)" ] || [ -z "$(NAME)" ]; then \
		echo "❌ Error: TYPE and NAME parameters are required"; \
		echo "Usage: make generate TYPE=fastapi NAME=my-service"; \
		echo "Available types: fastapi, grpc, hybrid, auth"; \
		exit 1; \
	fi
	@echo "🏗️ Generating $(TYPE) service: $(NAME)"
	@python3 scripts/generate_service.py $(TYPE) $(NAME) --description "$(NAME) service"

new: ## Create a new project (make new NAME=my-project)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make new NAME=my-project"; \
		exit 1; \
	fi
	@if [ -d "$(NAME)" ]; then \
		echo "❌ Error: Directory $(NAME) already exists"; \
		exit 1; \
	fi
	@echo "�️ Creating new project: $(NAME)"
	@cp -r microservice_project_template $(NAME)
	@echo "✅ Project created: ./$(NAME)"
	@echo "🚀 Next: cd $(NAME) && make dev"

# ==============================================================================
# Utilities
# ==============================================================================

clean: ## Clean build artifacts and cache files
	@echo "🧹 Cleaning build artifacts..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ htmlcov/ .coverage
	@rm -f test_results.json *_test_demo_results.json *_test_results.json coverage.xml
	@echo "✅ Cleanup complete!"

docs: ## Show documentation and usage examples
	@echo "📚 Marty Microservices Framework"
	@echo "================================="
	@echo ""
	@echo "📖 Quick Start:"
	@echo "   make setup                              # Complete setup"
	@echo "   make test                               # Run all tests"
	@echo "   make generate TYPE=fastapi NAME=api     # Generate service"
	@echo "   make new NAME=my-project                # Create new project"
	@echo ""
	@echo "🧪 Testing:"
	@echo "   make test-unit                          # Unit tests only"
	@echo "   make test-integration                   # Integration tests"
	@echo "   make test-e2e                          # All E2E tests"
	@echo "   make test-kind                          # Kind E2E tests only"
	@echo "   make test-coverage                      # With coverage"
	@echo ""
	@echo "🔧 Development:"
	@echo "   make dev                                # Setup dev environment"
	@echo "   make check                              # Run all quality checks"
	@echo "   make fix                                # Fix formatting/linting"
	@echo ""
	@echo "🏗️ Generation (TYPE: fastapi, grpc, hybrid, auth):"
	@echo "   make generate TYPE=fastapi NAME=user-api"
	@echo "   make generate TYPE=grpc NAME=data-processor"
	@echo "   make new NAME=my-awesome-project"
	@echo ""
	@echo "📜 Scripts:"
	@echo "   make scripts                            # Show available scripts"

scripts: ## Show available development scripts
	@echo "📜 Development Scripts"
	@echo "====================="
	@echo ""
	@echo "📖 For detailed descriptions, see: scripts/README.md"
	@echo ""
	@echo "🔧 Development:"
	@echo "   python3 scripts/setup_dev.py           # Development environment setup"
	@echo "   python3 scripts/test_framework.py      # Framework component testing"
	@echo ""
	@echo "🧪 Testing:"
	@echo "   python3 scripts/test_runner.py         # Main test runner with reports"
	@echo "   python3 scripts/real_e2e_test_runner.py # E2E test runner"
	@echo "   ./scripts/run_kind_playwright_e2e.sh   # Kind + Playwright E2E"
	@echo ""
	@echo "✅ Validation:"
	@echo "   ./scripts/validate.sh                  # General validation"
	@echo "   python3 scripts/validate_templates.py  # Template validation"
	@echo "   python3 scripts/validate_observability.py # Observability validation"
	@echo "   python3 scripts/verify_security_framework.py # Security verification"
	@echo ""
	@echo "🏗️ Generation:"
	@echo "   python3 scripts/generate_service.py    # Service generation utility"
	@echo ""
	@echo "🛠️ Utilities:"
	@echo "   python3 scripts/check_dependencies.py  # Dependency checking"
	@echo "   ./scripts/cleanup.sh                   # Clean up artifacts"
	@echo "   ./scripts/show_script_commands.sh      # Show script commands"

status: ## Show framework status
	@echo "📊 Framework Status"
	@echo "=================="
	@echo ""
	@if command -v uv >/dev/null 2>&1; then echo "✅ UV installed"; else echo "❌ UV missing"; fi
	@if [ -d ".venv" ]; then echo "✅ Virtual environment"; else echo "❌ No virtual environment"; fi
	@if [ -f "scripts/validate_templates.py" ]; then echo "✅ Scripts available"; else echo "❌ Scripts missing"; fi
	@if [ -d "microservice_project_template" ]; then echo "✅ Project template"; else echo "❌ Template missing"; fi

# ==============================================================================
# CI/CD
# ==============================================================================

ci: ## Run CI/CD pipeline (validate, test, check)
	@echo "🚀 Running CI/CD pipeline..."
	@python3 scripts/validate_templates.py
	@uv run pytest -m "unit or integration" --tb=short
	@uv run ruff check .
	@python3 -m mypy scripts/ --config-file mypy.ini
	@echo "✅ CI/CD pipeline completed!"

# Legacy support (will be removed in future versions)
lint: fix
format: fix
validate: check
typecheck: check
	@echo "🔍 Running strict mypy type checking..."
