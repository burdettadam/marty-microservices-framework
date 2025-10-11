# Marty Microservices Framework - Makefile
# Convenient commands for framework development and usage

.PHONY: help setup test validate generate clean docs typecheck

# Default target
help: ## Show this help message
	@echo "Marty Microservices Framework"
	@echo "=============================="
	@echo ""
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Setup the framework and validate installation
	@echo "🚀 Setting up Marty Microservices Framework..."
	@bash scripts/setup_framework.sh

install: ## Install framework with UV in development mode
	@echo "📦 Installing framework with UV..."
	@uv sync --extra dev
	@echo "✅ Framework installed successfully!"

install-chassis: ## Install marty-chassis package with UV
	@echo "📦 Installing marty-chassis package..."
	@cd marty_chassis && uv sync --extra dev
	@echo "✅ marty-chassis installed successfully!"

# Test targets
test: ## Run comprehensive framework tests
	@echo "🧪 Running framework tests..."
	@python3 scripts/test_framework.py

test-all: ## Run all tests including type checking
	@echo "🧪 Running comprehensive tests with type checking..."
	@python3 scripts/test_framework.py
	@python3 -m mypy scripts/ --config-file mypy.ini

test-unit: ## Run unit tests only
	@echo "🧪 Running unit tests..."
	@uv run pytest -m unit -v

test-integration: ## Run integration tests only
	@echo "🧪 Running integration tests..."
	@uv run pytest -m integration -v

test-e2e: ## Run end-to-end tests
	@echo "🧪 Running E2E tests..."
	@uv run pytest -m e2e -v

test-coverage: ## Run tests with coverage report
	@echo "🧪 Running tests with coverage..."
	@uv run pytest --cov=src --cov-report=html --cov-report=term

test-fast: ## Run tests with fail-fast mode
	@echo "🧪 Running fast tests..."
	@uv run pytest -x -v --tb=short

# Kind + Playwright E2E test targets
test-kind-playwright: ## Run Kind + Playwright E2E tests
	@echo "🎭 Running Kind + Playwright E2E tests..."
	@uv run pytest tests/e2e/test_kind_playwright_e2e.py -v -s

test-kind-playwright-all: ## Run all Kind + Playwright E2E tests with options
	@echo "🎭 Running comprehensive Kind + Playwright E2E tests..."
	@./scripts/run_kind_playwright_e2e.sh

test-kind-playwright-dashboard: ## Run Kind + Playwright dashboard tests only
	@echo "🎭 Running Kind + Playwright dashboard tests..."
	@./scripts/run_kind_playwright_e2e.sh --test-type dashboard

test-kind-playwright-visual: ## Run Kind + Playwright visual regression tests
	@echo "🎭 Running Kind + Playwright visual tests..."
	@./scripts/run_kind_playwright_e2e.sh --test-type visual

test-kind-playwright-debug: ## Run Kind + Playwright tests with browser visible
	@echo "🎭 Running Kind + Playwright tests in debug mode..."
	@./scripts/run_kind_playwright_e2e.sh --headless false

# Development targets
lint: ## Run ruff linting
	@echo "🔍 Running ruff linting..."
	@uv run ruff check .

lint-fix: ## Run ruff linting with auto-fix
	@echo "🔧 Running ruff linting with auto-fix..."
	@uv run ruff check --fix .

format: ## Format code with ruff
	@echo "✨ Formatting code with ruff..."
	@uv run ruff format .

validate: ## Validate all service templates
	@echo "🔍 Validating service templates..."
	@python3 scripts/validate_templates.py

typecheck: ## Run mypy type checking on framework scripts
	@echo "🔍 Running mypy type checking..."
	@python3 -m mypy scripts/ --config-file mypy.ini

typecheck-strict: ## Run mypy type checking with strict mode
	@echo "🔍 Running strict mypy type checking..."
	@python3 -m mypy scripts/ --config-file mypy.ini --strict --show-error-codes

security: ## Run security checks with bandit
	@echo "🔒 Running security checks..."
	@uv run bandit -r src/

pre-commit-install: ## Install pre-commit hooks
	@echo "🪝 Installing pre-commit hooks..."
	@uv run pre-commit install

pre-commit-run: ## Run pre-commit on all files
	@echo "🪝 Running pre-commit on all files..."
	@uv run pre-commit run --all-files

# Build and documentation targets
build: ## Build the package
	@echo "📦 Building package..."
	@uv run python -m build

docs-serve: ## Serve documentation locally
	@echo "📚 Serving documentation at http://localhost:8000..."
	@uv run python -m http.server 8000 -d docs/

demo-e2e: ## Run the Kind + Playwright E2E demo
	@echo "🎭 Running Kind + Playwright E2E demo..."
	@uv run python demo_kind_playwright_e2e.py

# Simple E2E test
test-simple-e2e: ## Run simple Kind + Playwright E2E test
	@echo "🎭 Running simple Kind + Playwright E2E test..."
	@uv run python tests/e2e/simple_kind_playwright_test.py

# Show available script commands
show-commands: ## Show all available script commands (npm-like)
	@./scripts/show_script_commands.sh

# Check dependencies
check-deps: ## Check if all dependencies are properly installed
	@echo "🔍 Checking dependencies..."
	@uv run python scripts/check_dependencies.py

# Setup targets
setup-dev: ## Setup complete development environment
	@echo "🚀 Setting up development environment..."
	@uv sync --extra dev
	@uv run playwright install chromium
	@uv run pre-commit install
	@echo "✅ Development environment ready!"

setup-all: ## Setup environment with all extras
	@echo "🚀 Setting up complete environment..."
	@uv sync --all-extras
	@uv run playwright install chromium
	@uv run pre-commit install
	@echo "✅ Complete environment ready!"

clean: ## Clean build artifacts and cache files
	@echo "🧹 Cleaning build artifacts..."
	@rm -rf dist/ build/ .pytest_cache/ htmlcov/ .coverage .mypy_cache/ .ruff_cache/
	@echo "✅ Cleanup complete!"

# Service generation targets
generate-fastapi: ## Generate a FastAPI service (make generate-fastapi NAME=my-service)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make generate-fastapi NAME=my-service"; \
		exit 1; \
	fi
	@echo "🏗️ Generating FastAPI service: $(NAME)"
	@python3 scripts/generate_service.py fastapi $(NAME) --description "$(NAME) REST API service"

generate-grpc: ## Generate a gRPC service (make generate-grpc NAME=my-service)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make generate-grpc NAME=my-service"; \
		exit 1; \
	fi
	@echo "🏗️ Generating gRPC service: $(NAME)"
	@python3 scripts/generate_service.py grpc $(NAME) --description "$(NAME) gRPC service"

generate-hybrid: ## Generate a hybrid service (make generate-hybrid NAME=my-service)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make generate-hybrid NAME=my-service"; \
		exit 1; \
	fi
	@echo "🏗️ Generating hybrid service: $(NAME)"
	@python3 scripts/generate_service.py hybrid $(NAME) --description "$(NAME) hybrid service"

generate-auth: ## Generate an auth service (make generate-auth NAME=my-auth-service)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make generate-auth NAME=my-auth-service"; \
		exit 1; \
	fi
	@echo "🏗️ Generating authentication service: $(NAME)"
	@python3 scripts/generate_service.py auth $(NAME) --description "$(NAME) authentication service"

# Project template targets
new-project: ## Create a new project from template (make new-project NAME=my-project)
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Error: NAME parameter is required"; \
		echo "Usage: make new-project NAME=my-project"; \
		exit 1; \
	fi
	@if [ -d "$(NAME)" ]; then \
		echo "❌ Error: Directory $(NAME) already exists"; \
		exit 1; \
	fi
	@echo "🏗️ Creating new project: $(NAME)"
	@cp -r microservice_project_template $(NAME)
	@echo "✅ Project created successfully!"
	@echo "📁 Location: ./$(NAME)"
	@echo "🚀 Next steps:"
	@echo "   cd $(NAME)"
	@echo "   uv sync --extra dev"
	@echo "   make dev"

# Development targets
dev-project: ## Setup development environment in project template
	@echo "🔧 Setting up development environment in project template..."
	@cd microservice_project_template && uv sync --extra dev
	@echo "✅ Development environment ready!"

# Cleanup targets
clean: ## Clean generated files and caches
	@echo "🧹 Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf src/test_* 2>/dev/null || true
	@echo "✅ Cleanup complete!"

clean-all: clean ## Clean everything including virtual environments
	@echo "🧹 Deep cleaning..."
	@rm -rf microservice_project_template/.venv 2>/dev/null || true
	@rm -rf microservice_project_template/.pytest_cache 2>/dev/null || true
	@rm -rf microservice_project_template/.mypy_cache 2>/dev/null || true
	@rm -rf microservice_project_template/.ruff_cache 2>/dev/null || true
	@echo "✅ Deep cleanup complete!"

# Documentation and examples
docs: ## Show documentation links
	@echo "📚 Marty Microservices Framework Documentation"
	@echo "=============================================="
	@echo ""
	@echo "📖 Main Documentation:"
	@echo "   README.md                                 - Framework overview and usage"
	@echo "   microservice_project_template/README.md  - Project template documentation"
	@echo ""
	@echo "🏗️ Architecture Documentation:"
	@echo "   microservice_project_template/docs/ARCHITECTURE.md     - System architecture"
	@echo "   microservice_project_template/docs/LOCAL_DEVELOPMENT.md - Development guide"
	@echo "   microservice_project_template/docs/OBSERVABILITY.md    - Monitoring and metrics"
	@echo "   microservice_project_template/docs/ANALYTICS.md        - Analytics framework"
	@echo ""
	@echo "🛠️ Service Templates:"
	@echo "   service/fastapi_service/     - REST API services"
	@echo "   service/grpc_service/        - gRPC services"
	@echo "   service/hybrid_service/      - Combined REST + gRPC"
	@echo "   service/auth_service/        - Authentication services"
	@echo "   service/database_service/    - Database-backed services"
	@echo "   service/caching_service/     - Redis caching services"
	@echo "   service/message_queue_service/ - Message queue services"

examples: ## Show usage examples
	@echo "🚀 Marty Microservices Framework - Usage Examples"
	@echo "================================================="
	@echo ""
	@echo "🔧 Framework Setup:"
	@echo "   make setup                    # Setup framework and validate"
	@echo "   make test                     # Run comprehensive tests"
	@echo "   make test-all                 # Run tests with type checking"
	@echo "   make validate                 # Validate templates"
	@echo "   make typecheck                # Run mypy type checking"
	@echo ""
	@echo "🏗️ Service Generation:"
	@echo "   make generate-fastapi NAME=user-api        # REST API service"
	@echo "   make generate-grpc NAME=data-processor      # gRPC service"
	@echo "   make generate-hybrid NAME=payment-service   # Hybrid service"
	@echo "   make generate-auth NAME=auth-service        # Auth service"
	@echo ""
	@echo "📦 Project Creation:"
	@echo "   make new-project NAME=my-awesome-service    # New complete project"
	@echo "   cd my-awesome-service && make dev           # Start development"
	@echo ""
	@echo "🧹 Maintenance:"
	@echo "   make clean                    # Clean temporary files"
	@echo "   make clean-all               # Deep clean including venvs"
	@echo ""
	@echo "📚 Documentation:"
	@echo "   make docs                    # Show documentation links"
	@echo "   make examples               # Show this examples list"

# Status and information
status: ## Show framework status and information
	@echo "📊 Marty Microservices Framework Status"
	@echo "======================================="
	@echo ""
	@echo "📁 Framework Structure:"
	@ls -la scripts/ | grep -E '\.(py|sh)$$' | awk '{print "   " $$9}' || echo "   No scripts found"
	@echo ""
	@echo "🛠️ Available Service Templates:"
	@ls -d service/*/ 2>/dev/null | sed 's|service/||g; s|/||g' | awk '{print "   " $$1}' || echo "   No templates found"
	@echo ""
	@echo "📦 Project Template:"
	@if [ -d "microservice_project_template" ]; then echo "   ✅ Available"; else echo "   ❌ Missing"; fi
	@echo ""
	@echo "🔍 Template Validation:"
	@python3 scripts/validate_templates.py > /dev/null 2>&1 && echo "   ✅ All templates valid" || echo "   ❌ Some templates need attention"

# Quick development workflow
quick-start: setup ## Complete quick start workflow
	@echo "🎉 Quick Start Complete!"
	@echo ""
	@echo "Try these commands:"
	@echo "  make generate-fastapi NAME=hello-world    # Generate a service"
	@echo "  make new-project NAME=my-project          # Create a complete project"
	@echo "  make examples                             # See more examples"

# CI/CD friendly targets
ci-test: ## Run tests suitable for CI/CD
	@python3 scripts/validate_templates.py
	@python3 scripts/test_framework.py
	@python3 -m mypy scripts/ --config-file mypy.ini

ci-setup: ## Setup for CI/CD environment
	@pip3 install jinja2 mypy
	@chmod +x scripts/*.sh scripts/*.py
