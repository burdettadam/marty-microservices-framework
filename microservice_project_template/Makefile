SHELL := /bin/bash
UV := uv

.PHONY: bootstrap install proto format lint typecheck test test-unit test-integration test-e2e test-build ci run docker-build kind-up kind-down clean

bootstrap:
	$(UV) sync --extra dev

install:
	$(UV) sync --extra dev

proto:
	./scripts/generate_proto.sh

format:
	./scripts/format.sh

lint:
	./scripts/lint.sh

typecheck:
	./scripts/typecheck.sh

test:
	./scripts/test.sh

test-unit:
	./scripts/test_unit.sh

test-integration:
	./scripts/test_integration.sh

test-e2e:
	./scripts/test_e2e.sh

test-build:
	./scripts/test_build.sh

ci: proto format lint typecheck test test-build

run:
	./scripts/run_server.sh

docker-build:
	./scripts/docker_build.sh

kind-up:
	./scripts/kind_up.sh

kind-down:
	./scripts/kind_down.sh

clean:
	rm -rf .venv .mypy_cache .pytest_cache .ruff_cache .uv build dist
	rm -f coverage.xml
