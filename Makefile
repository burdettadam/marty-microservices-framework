.PHONY: help check fmt lint test build clean

help: ## Show supported Rust workspace commands
	@echo "Marty Microservices Framework"
	@echo "  make check  - formatting, strict lint, and tests"
	@echo "  make build  - build the locked workspace"
	@echo "  make clean  - remove Cargo build output"

check: fmt lint test ## Run the complete local gate

fmt: ## Check Rust formatting
	cargo fmt --all -- --check

lint: ## Run strict workspace linting
	cargo clippy --locked --workspace --all-targets -- -D warnings

test: ## Run all Rust and language-neutral contract tests
	cargo test --locked --workspace

build: ## Build the locked workspace
	cargo build --locked --workspace

clean: ## Remove generated Cargo output
	cargo clean
