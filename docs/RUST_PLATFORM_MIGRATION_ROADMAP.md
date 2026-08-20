# MMF Rust Platform Migration Roadmap

**Status:** Active

**Last updated:** 2026-08-20

## Implementation ledger

| Slice | State | Evidence and next deletion gate |
|---|---|---|
| Workspace foundation | Merge queued | `mmf-core`, `mmf-config`, `mmf-runtime`, the `mmf` facade, capability ownership inventory, fail-closed lifecycle/readiness contracts, Rust CI, and the existing 1,633-test Python baseline are green in PR #88 |
| Resilience | Active | `mmf-resilience` now owns validated deadlines, configurable/custom retry backoff, jitter, count/rate circuit breaking, async bulkheads, ordered static/function/cache fallbacks, canonical metrics/errors, and the unified composition order; Rust and Python execute `contracts/resilience-behavior.json` for parity |
| Observability | Active | `mmf-observability` now owns MMF correlation headers, strict W3C trace context, recursive structured-data redaction, bounded Prometheus counter/gauge/histogram/summary semantics, SLI/SLO/error-budget math, deterministic health rollups, metric windows, alert lifecycle/cooldowns/dependencies, anomaly scoring, trend/statistics/correlation/capacity analytics, log/span/business-metric records, dashboard/alert metadata, fail-closed exporter configuration, and provider ports for OpenTelemetry-style instrumentation, system metrics, and notifications. HTTP/gRPC/data/cache/messaging targets share one instrumentation contract; load generation is owned by `mmf-testkit`. Python and Rust execute `contracts/observability-behavior.json` and `contracts/observability-provider-behavior.json` for parity; Python UNKNOWN masking is documented and corrected fail-closed in Rust. |
| Security | Active | `mmf-security` now owns authenticated-user/principal/result models; structured permissions; protected default roles, role lifecycle, assignment and inherited RBAC; nested/regex deny-overrides ABAC; conditioned user/role/group ACLs with glob, time, CIDR, method and resource-attribute matching; composite authorization; deterministic fixed/sliding/token/leaky rate limiting; session lifecycle and hijack policy; audit/threat/vulnerability/mesh models; and explicit JWT/OIDC/session/MFA/KMS/OpenBao/OPA/Oso provider ports. External policy providers fail closed instead of reporting placeholder success, cryptographic kernels remain in `marty-core`, and Python/Rust execute `contracts/security-behavior.json` plus `contracts/authorization-adapter-behavior.json`. Enforcement middleware/provider adapters and consumer cutover remain before deleting the Python authorization family. |
| Data and infrastructure | Active | `mmf-data` owns cache backend/pattern/config/stats semantics, fail-closed JSON/string/bytes serialization, full ordinary and sorted-set cache ports, deterministic TTL behavior, read-model equality/range/set filtering, validated sorting/pagination, generic repositories, migration revisions/schema verification, and validated PostgreSQL identifier/literal/JSONB/insert generation. `mmf-runtime` now owns typed instance/factory registration plus singleton/transient/scoped lifetimes, and `mmf-config` owns hosting detection, deployment/configuration strategies, secret metadata/expiry, and async secret/configuration backend ports. Executable Python pickle is intentionally rejected. Redis/Memcached/SQL/migration/cloud-secret adapters, unified-config consumers, and service cutovers remain before deleting the Python infrastructure family; Python and Rust execute `contracts/data-infrastructure-behavior.json` and `contracts/config-runtime-behavior.json`. |
| Messaging and events | Active | `mmf-messaging` consolidates the core, extended, enhanced-event-bus, and outbox surfaces into one envelope and provider contract; it owns event kinds and registration, rich metadata, routing/filtering, subscriptions, JSON serialization, batch/priority/scheduled delivery, inbox idempotency, transactional-outbox state, deterministic partitioning, retry/DLQ/requeue/replay, health and Kafka/database/NATS/RabbitMQ/Redis/AWS transport ports, while reusing `mmf-resilience` retry configuration; Python and Rust execute `contracts/messaging-behavior.json` before consumer ports and Python deletion |
| Discovery, gateway, mesh and deployment | Active | `mmf-platform` consolidates service endpoints/metadata/health, filtered in-memory discovery, round-robin/weighted/least-connection/random/consistent-hash/locality/adaptive balancing, exact/prefix/regex/wildcard/template gateway routing, route constraints, deployment lifecycle and Kubernetes manifest generation, plus fail-closed Consul/DNS/upstream/Kubernetes/Terraform/GitHub Actions ports; mesh security policy models and ports are reused from `mmf-security` rather than duplicated, and Python/Rust execute `contracts/platform-behavior.json` |
| Built-in identity service | Active | `mmf-services::identity` begins consolidation of the 12.5k-line Python identity family around the canonical `mmf-security` user/session/MFA models; it owns stable authentication status/error behavior, provider orchestration, OAuth2 client and one-time authorization-code state, and fail-closed token/password/API-key/mTLS provider composition, while JWT/TOTP/password/certificate cryptography remains native-provider work owned by `marty-core`; Python and Rust execute `contracts/identity-service-behavior.json` |
| Built-in audit and compliance services | Active | `mmf-services::audit` consolidates the overlapping Python audit and audit-compliance domains while reusing `mmf-security` audit events, threat levels, detection results, and auditor contracts. It owns request context and forwarding policy, compliance frameworks/findings/scans, threat-pattern lifecycle, normalized query models, and explicit repository/destination/native-encryption/scanner/SIEM/report provider ports. Python and Rust execute `contracts/audit-compliance-behavior.json`; persistence, middleware/interceptor, scanner, report, and SIEM consumer cutovers remain before immediate Python deletion. |
| Python resilience deletion | Waiting on consumers | Delete the Python resilience package immediately after production consumers use the published Rust crate and the shared contract plus packaging guards pass |

## Objective

Replace the Python Marty Microservices Framework with a complete Rust platform
without losing intended framework features. The migration is complete only
when every retained feature has implementation-independent behavioral
contracts, one canonical Rust implementation, migrated consumers, and no
production dependency on the Python `marty-msf` package.

This is a feature-preserving platform port, not merely a replacement for the
small subset currently imported by Marty services. Features documented by the
framework, exposed by its modules or CLI, represented by public models, or
covered by maintained tests are presumed intended until a contract and caller
inventory proves otherwise.

## Non-negotiable outcomes

1. Removing Python MMF must not remove a supported microservice capability.
2. Shared behavior has exactly one Rust implementation. Services configure and
   compose it; they do not copy it.
3. Rust services preserve public HTTP, gRPC, event, storage, configuration,
   security, observability, deployment, plugin, and CLI contracts.
4. Optional integrations remain optional Cargo features or adapters. Missing
   required capabilities fail startup or the operation closed.
5. Superseded Python implementation and implementation-specific tests are
   deleted as soon as language-neutral parity, failure, packaging, and consumer
   checks pass.
6. All migration slices land before a single aggregate beta update. Production
   promotion remains a separate decision.

## DRY crate architecture

The Rust workspace will expose a small `mmf` facade and feature-oriented
implementation crates. A capability belongs in the lowest reusable crate and
is re-exported rather than duplicated in a service.

| Crate | Canonical responsibilities |
|---|---|
| `mmf-core` | Stable errors, IDs, clocks, lifecycle states, service/plugin contexts, health/readiness models, ports, and bounded common types |
| `mmf-config` | Layered files and environment overrides, schema validation, secret references, cloud/platform detection, dynamic reload, plugin namespaces, and redacted diagnostics |
| `mmf-runtime` | Axum/Tonic/hybrid service lifecycle, graceful shutdown, dependency composition, middleware/interceptors, standardized errors, health, readiness, and version endpoints |
| `mmf-data` | SQLx relational pools and transactions, migrations, repository helpers, MongoDB adapters, Redis cache/session primitives, key namespacing, TTLs, and pool health |
| `mmf-messaging` | Kafka and test backends, domain/integration/system/plugin events, routing, filtering, subscriptions, transactional outbox, inbox/idempotency, retries, DLQ, replay, scheduling, batching, and priorities |
| `mmf-workflow` | Durable workflows, action/decision/parallel/wait steps, retries, timeouts, recovery, saga orchestration/choreography, compensation, and workflow events |
| `mmf-patterns` | CQRS commands/queries, projections/read models, event stores, snapshots, aggregate support, and data-consistency composition over messaging/workflow ports |
| `mmf-security` | JWT and OAuth2/OIDC, RBAC, ABAC, OPA/policy adapters, zero-trust request context, sessions, MFA/TOTP, rate limits, audit hooks, KMS/OpenBao ports, and normalized security errors |
| `mmf-observability` | OpenTelemetry setup, propagation and correlation, structured redacted logging, Prometheus metrics, traces, SLOs, business metrics, dashboards/alerts metadata, and HTTP/gRPC/data/messaging instrumentation |
| `mmf-resilience` | Deadlines, retries with jitter, circuit breakers, bulkheads, fallbacks, dependency policies, connection-pool supervision, and resilience metrics |
| `mmf-platform` | Service discovery and registration, Consul/DNS adapters, load balancing, gateway primitives, service-mesh policy/configuration, Kubernetes/container metadata, and deployment generation |
| `mmf-plugins` | Discovery, metadata, dependencies, ordering, namespaced configuration, enable/disable, lifecycle, service definitions, health aggregation, and extension points |
| `mmf-push` | Push registry and lifecycle, FCM, SSE, webhook and test adapters, subscriptions, delivery outcomes, retries, and health |
| `mmf-ml` | Feature store, model registry, model serving, model health/versioning, and A/B experiment contracts and adapters |
| `mmf-testkit` | In-memory/test adapters, contract harnesses, service fixtures, fault injection, load/spike/endurance/chaos runners, and deterministic clocks/IDs |
| `mmf-cli` | Service scaffolding and templates; build, test, run, deploy, info, config, API documentation, contract, migration, service-mesh, and plugin commands |
| `mmf` | Ergonomic facade and feature flags only; no second implementation |

### Dependency rules

- `mmf-core` has no dependency on another MMF crate.
- Infrastructure crates depend on stable ports and models, never on an owning
  application service.
- Cross-cutting telemetry and resilience are composed through middleware and
  traits, not copied helpers.
- Optional providers are adapter modules behind Cargo features.
- `marty-core` remains the canonical owner of identity protocol,
  credential-verification, policy, and cryptographic kernels. MMF composes
  those crates but does not reimplement them.
- `marty-ui` service binaries contain only domain-specific routes, use cases,
  repositories, and provider adapters. Generic runtime code must move to MMF.
- A duplication guard will reject service-local implementations of canonical
  MMF health, configuration, migration, event envelope, retry, correlation,
  authorization-context, or secret-reference behavior.

## Intended-feature parity inventory

The following inventory is the minimum migration scope. Each row requires a
contract fixture, direct Rust tests, consumer-level tests, and an explicit
disposition before Python deletion.

| Capability family | Intended behavior to preserve | Rust owner |
|---|---|---|
| Service runtime | REST, gRPC and hybrid services; dependency composition; lifecycle; standardized errors; health/readiness/metrics; graceful shutdown | `mmf-runtime` |
| Configuration and secrets | Hierarchical environment configuration; validation; environment overrides; secret references; Vault/AWS/Azure/GCP/Kubernetes/self-host adapters; plugin namespaces; hot reload | `mmf-config` |
| Data and caching | Async relational pools and transactions; PostgreSQL/MySQL adapters; MongoDB adapters; migrations; repositories; Redis cache/session; cluster/sentinel and health | `mmf-data` |
| Messaging and events | Kafka, database and in-memory test transports; rich metadata; routing/filtering; dynamic subscriptions; transactional outbox; retries; DLQ; replay; batch/scheduled/priority publishing | `mmf-messaging` |
| Workflows and consistency | Durable workflow state; action/decision/parallel/wait/compensation; timeout/retry; saga recovery; CQRS; projections; event sourcing; snapshots | `mmf-workflow`, `mmf-patterns` |
| Security and identity | JWT/OAuth2/OIDC; identity-provider adapters; RBAC/ABAC/OPA; sessions; MFA/TOTP; rate limiting; zero-trust context; security audit; KMS and OpenBao interfaces | `mmf-security` |
| Observability | OpenTelemetry; HTTP/gRPC/database/cache/messaging instrumentation; correlation IDs; Prometheus; tracing; structured logs; SLOs; dashboards and alert metadata | `mmf-observability` |
| Resilience and performance | Deadlines; retries/backoff/jitter; circuit breakers; bulkheads; fallbacks; HTTP/Redis/database pools; dependency health; load and chaos validation | `mmf-resilience`, `mmf-testkit` |
| Discovery, gateway and mesh | Consul and DNS discovery; registration/health; load balancing; gateway routing; mesh policy; Kubernetes, Helm/Kustomize and container deployment contracts | `mmf-platform` |
| Plugins | Package discovery; metadata; dependency graph/order; configuration isolation; lifecycle; dynamic enable/disable; services; health; event subscriptions | `mmf-plugins` |
| Push | Registration and subscription lifecycle; FCM, SSE, webhook and mock delivery; retries; health and delivery results | `mmf-push` |
| Documentation and contracts | OpenAPI/gRPC documentation; API versions; themes/templates; contract generation/execution; CI integration | `mmf-cli`, `mmf-testkit` |
| Developer experience | Service templates; `new`, `templates`, `build`, `test`, `run`, `deploy`, `info`, `config`, `api`, `migrate`, `service-mesh`, and `plugin` commands | `mmf-cli` |
| ML platform | Feature store; model registry; serving; health/version selection; A/B experiments | `mmf-ml` |
| Built-in services | Identity, audit, audit-compliance and biometric service contracts, including their public APIs and events | service crates composed from MMF and `marty-core` |
| Testing | Unit/integration/contract harnesses; deterministic in-memory adapters; load, spike, endurance and chaos tests; fault injection | `mmf-testkit` |

## Delivery order

### Phase 0 — contract capture and workspace foundation

1. Freeze public Python models, CLI help/output, configuration keys, plugin
   contracts, deployment artifacts, events and service APIs as
   language-neutral fixtures.
2. Create the Rust workspace, facade, crate dependency rules, feature flags,
   diagnostics, and duplication guards.
3. Establish CI for formatting, linting, unit/contract tests, minimum supported
   Rust version, dependency policy, and release packaging.

### Phase 1 — reusable service foundation

Implement `mmf-core`, `mmf-config`, `mmf-runtime`, `mmf-observability`,
`mmf-resilience`, and the essential `mmf-data` ports. Extract equivalent code
from existing Rust services instead of maintaining parallel helpers.

### Phase 2 — first consumers and data/messaging

Port the `marty-ui` gateway first, followed by flow and organization. Complete
SQL/Redis migrations, event envelopes, transactional outbox, Kafka, discovery,
security context and provider adapters needed by those services.

### Phase 3 — remaining `marty-ui` services

Continue in descending removable Python size: auth, presentation policy,
trust profile, credential template, applicant, verification,
device-registration, deployment profile and compliance profile. Delete each
Python service only after parity gates pass.

### Phase 4 — complete intended MMF surface

Implement workflow, patterns, plugins, push, platform/mesh, ML, testkit, CLI,
documentation/contract tooling, and built-in identity/audit/compliance/biometric
service contracts even where the current Marty deployment uses only a subset.

### Phase 5 — migrate remaining consumers and remove Python MMF

Migrate Marty plugin, KMS, cache and push consumers plus marty-credentials
logging, database, session, exception and migration consumers. Remove the
Python package, wheel dependency, fallback imports, Python implementation
tests, and obsolete release jobs once the dependency and packaging guards show
no production consumer remains.

### Phase 6 — aggregate acceptance and beta

Run cross-repository unit, contract, integration, security, load, chaos,
packaging and full-stack lifecycle suites. Land all slices first, then perform
one aggregate beta deployment and soak. Do not update production.

## Per-slice deletion gates

- Public route/method/status/schema and gRPC method/status parity.
- Event envelope, ordering, delivery, retry, idempotency, DLQ and replay parity.
- Database schema, migration, transaction, concurrency, Redis key and TTL parity.
- Configuration, secret, feature flag, health/readiness and diagnostics parity.
- Authentication, authorization, rate-limit, audit and fail-closed parity.
- Logs, metrics, traces, propagation, dashboards and alert-contract parity.
- Provider-stub, timeout, retry, circuit-breaker and disconnect behavior.
- CLI command, output, exit-code and generated-project parity where applicable.
- Rust direct tests and public-boundary tests execute the same language-neutral
  fixtures.
- Packaging starts without Python MMF and no superseded implementation remains.

## Completion criteria

The program is complete when all intended-feature rows are either
`native-active` or explicitly retired by an approved evidence record, every
production consumer uses released Rust crates, duplication guards pass, the
Python MMF package and imports are deleted, all migrated `marty-ui` Python
services are removed, and the aggregate beta acceptance suite passes.
