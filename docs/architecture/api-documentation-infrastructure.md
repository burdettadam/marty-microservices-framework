# API Documentation and Contract Infrastructure

## Ownership

`mmf-cli` is the single implementation of MMF documentation generation, API
versioning, contract-management workflows, template customization, and the
`marty` developer command surface. `mmf-testkit` remains the canonical owner of
contract models and response verification. `mmf-platform` owns deployment and
service-mesh models, while `mmf-plugins` owns plugin metadata and lifecycle.

The former `mmf.framework.documentation` Python package and its Jinja assets
were deleted after the shared behavioral fixture passed and repository consumer
inventory was empty.

## Documentation pipeline

The Rust pipeline accepts source documents rather than importing application
modules:

1. FastAPI source discovery extracts service metadata and route declarations.
2. protobuf discovery extracts every service, RPC, and unary/client/server/
   bidirectional streaming shape.
3. matching REST and gRPC services are merged by service name.
4. generation emits OpenAPI 3.0.3, Postman, gRPC HTML/client examples, unified
   HTML, gRPC-gateway YAML, and an index.
5. a scoped host adapter writes UTF-8 artifacts and rejects path traversal or
   unapproved overwrites.

The generator supports Redoc, Swagger UI, and Stoplight theme contracts,
schema/example toggles, contact/license/server metadata, deprecation dates, and
migration guides. Custom filesystem and process effects are behind explicit
ports and fail closed when unavailable.

## API versions

`VersionRegistry` owns active/deprecated version records, creation timestamps,
deprecation dates, and migration guides. Unknown deprecation transitions return
a typed error. The registry has deterministic JSON serialization so storage can
be supplied by a file, database, or service adapter without another versioning
implementation.

## Contracts

`mmf-cli` reuses `mmf-testkit::Contract` and `verify_response` for HTTP, gRPC,
event, message-queue, GraphQL, WebSocket, and database contracts. It adds:

- duplicate-safe registration and filtering;
- protobuf-to-gRPC contract generation;
- fail-closed executor ports for live providers;
- strictness-aware test summaries;
- Markdown and JUnit reports for local and CI use;
- monitoring configuration and normalized failure events.

Provider failures are failed interactions. Missing providers never create an
empty successful report.

## Template and CLI architecture

The template engine preserves variables, globals, required/optional values,
slug/snake/Pascal/kebab filters, conditionals, loops, includes, macros, and
composition. Include depth, unknown variables, duplicate names, unsafe paths,
and invalid project names fail closed.

Built-in scaffolds cover the intended service families:

- FastAPI-equivalent REST, gRPC, hybrid, production, and minimal services;
- API gateway, configuration, discovery, and API-versioning infrastructure;
- saga orchestration.

The historical names remain accepted, but generated projects are Rust-first and
include Cargo configuration, health behavior, tests, containers, Kubernetes,
observability guidance, and CI according to feature toggles.

The `marty` binary parses every intended command family into typed operations.
Build/test/run/deploy, docs, scaffolding, overlay/mesh generation, and plugin
creation have scoped native host paths. Live contract providers, registries,
clusters, databases, and policy engines are adapters; if one is not configured,
the command returns `ProviderUnavailable`. `--plan` emits the typed operation
without causing effects.

## Behavioral evidence

Both implementations were evaluated against
`contracts/cli-documentation-behavior.json` before Python deletion. Rust retains
the legacy OpenAPI/Postman/gateway/version behavior and deliberately corrects:

- Windows locale writes that crashed on the legacy Unicode templates;
- an undefined `method` variable in the gRPC client template;
- labeling all streaming protobuf RPCs as unary.

The fixture is language-neutral and the Rust suite covers malformed input,
unsafe paths, unavailable providers, duplicate contracts, production deployment
pinning, and all template/command families.
