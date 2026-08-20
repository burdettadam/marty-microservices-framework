# Marty Rust CLI

The `marty` executable is provided by the `mmf-cli` Rust crate. It creates and
operates MMF services, generates API documentation and contracts, and plans
deployment, migration, mesh, plugin, security, and database operations without
depending on Python.

## Build and inspect

```sh
cargo build -p mmf-cli --bin marty
cargo run -p mmf-cli -- --help
cargo run -p mmf-cli -- --version
```

Add `--plan` to any command to print its typed JSON plan without executing host
effects:

```sh
marty build --release --plan
marty deploy --environment beta --namespace marty-beta --plan
```

## Create services

```sh
marty templates
marty templates fastapi-service
marty new fastapi-service user-service \
  --author "Marty Team" \
  --description "User management" \
  --port 8080
```

Accepted built-in template names are:

- `fastapi-service`
- `api-gateway-service`
- `config-service`
- `saga-orchestrator`
- `service-discovery`
- `api-versioning`
- `grpc-service`
- `hybrid-service`
- `production-service`
- `minimal-service`

The names preserve the historical CLI contract. Generated services are
Rust-first and can include tests, Docker, Kubernetes, observability guidance,
and CI. Use `--no-docker`, `--no-k8s`, `--no-monitoring`, `--no-testing`, or
`--no-ci-cd` to omit those artifacts.

## Project commands

```sh
marty build [--release] [--locked]
marty build --docker [--tag registry/service:tag] [--push] [--no-cache]
marty test [--unit|--integration|--contract|--e2e] [--coverage]
marty run [--port 8080] [--environment development] [--reload]
marty deploy --environment beta --namespace marty-beta [--dry-run] [--wait]
marty info [--dependencies] [--config] [--status] [--json]
```

Production deploy plans require an immutable image digest. Process execution is
argument-vector based and never invokes a shell command string.

## Configuration

```sh
marty config set --author "Marty Team" --email team@example.test
marty config show
marty config validate --service-path .
marty config validate --plugin marty
marty config reset
```

Configuration persistence and plugin-specific validation use configured
repository/provider adapters. Missing adapters return a non-zero
`ProviderUnavailable` result.

## API documentation and contracts

```sh
marty api docs ./services --output-dir docs/api --theme redoc
marty api create-contract --consumer web --provider identity --type http
marty api grpc-contract identity.proto --consumer gateway --provider identity
marty api list-contracts --provider identity
marty api test-contracts --provider identity --url https://identity.example.test --strict
marty api register-version --service-name identity --version 2.0.0
marty api list-versions --service-name identity
marty api contract-docs --contracts-dir contracts --docs-dir docs/contracts
marty api monitor --providers identity,verification --interval 60 --fail-fast
```

Documentation discovery does not import target applications. It scans FastAPI
source and protobuf files and emits UTF-8 OpenAPI, Postman, gRPC, unified,
gateway, client-example, and index artifacts.

Contract verification reuses `mmf-testkit` strictness semantics. Provider
errors are failures and JUnit output is available for CI.

## Migration and service mesh

```sh
marty migrate helm-to-kustomize \
  --chart-path charts/service \
  --output-path k8s \
  --service-name service
marty migrate generate-overlay --environment beta --namespace marty-beta
marty migrate validate --helm-path charts/service --kustomize-path k8s
marty migrate check-compatibility service --chart-path charts/service

marty service-mesh install --type istio --namespace mmf-system
marty service-mesh apply-policies --type istio --namespace mmf-system
marty service-mesh status --type istio --namespace mmf-system
marty service-mesh generate \
  --project-name identity \
  --type istio \
  --output-dir k8s/service-mesh
```

Mesh models come from `mmf-platform`/`mmf-security`; the CLI does not maintain a
second policy model.

## Plugins, services, security, and database operations

```sh
marty plugin init --name payments --features database,messaging
marty plugin list
marty plugin status payments
marty plugin service-add --plugin payments --name ledger --type business

marty service init grpc-service ledger --grpc-port 50051
marty service list
marty service status ledger

marty security scan --service-path .
marty security policy-test --principal user:alice --resource /api/users --action GET
marty db seed --service-path . --db-password-secret secret://postgres/password
```

Secrets are references, not plaintext CLI values. Registry, policy, database,
cluster, and live-service operations require explicit adapters and fail closed
when unavailable.

## Exit behavior

- `0`: the operation or requested plan completed.
- non-zero: invalid input, conflict, missing resource/provider, unsafe path,
  failed contract, or failed host process.

The CLI never treats an unimplemented provider path as success and never falls
back to Python.
