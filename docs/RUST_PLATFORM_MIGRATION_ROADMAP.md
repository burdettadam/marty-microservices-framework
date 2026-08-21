# MMF Rust Platform Migration Roadmap

**Status:** Active

**Last updated:** 2026-08-20

## Implementation ledger

| Slice | State | Evidence and next deletion gate |
|---|---|---|
| Workspace foundation | Merge queued | `mmf-core`, `mmf-config`, `mmf-runtime`, the `mmf` facade, capability ownership inventory, fail-closed lifecycle/readiness contracts, Rust CI, and the existing 1,633-test Python baseline are green in PR #88 |
| Resilience | Active | `mmf-resilience` now owns validated deadlines, configurable/custom retry backoff, jitter, count/rate circuit breaking, async bulkheads, ordered static/function/cache fallbacks, canonical metrics/errors, and the unified composition order; Rust and Python execute `contracts/resilience-behavior.json` for parity |
| Observability | Active | `mmf-observability` now owns MMF correlation headers, strict W3C trace context, recursive structured-data redaction, bounded Prometheus counter/gauge/histogram/summary semantics, SLI/SLO/error-budget math, deterministic health rollups, metric windows, alert lifecycle/cooldowns/dependencies, anomaly scoring, trend/statistics/correlation/capacity analytics, log/span/business-metric records, dashboard/alert metadata, fail-closed exporter configuration, and provider ports for OpenTelemetry-style instrumentation, system metrics, and notifications. HTTP/gRPC/data/cache/messaging targets share one instrumentation contract; load generation is owned by `mmf-testkit`. Python and Rust execute `contracts/observability-behavior.json` and `contracts/observability-provider-behavior.json` for parity; Python UNKNOWN masking is documented and corrected fail-closed in Rust. |
| Security | Active; Python MFA, OAuth2/OIDC, mTLS, sessions, request-security middleware, ECDH session keys, and built-in identity cryptography deleted | `mmf-security` owns authenticated-user/principal/result models; authorization and rate limiting; audit/threat/mesh models; MFA/TOTP; OAuth2/OIDC; reusable mTLS; the first-party HS256/384/512 JWT codec; and one canonical session platform. Wave 24 consolidated the earlier duplicate Rust session records into `ManagedSession`, added lifecycle/limits/extension/cleanup/analytics/events, redacted access/refresh/ID-token vaults, memory and real Redis stores with secondary indexes/TTLs/health checks, typed request context and normalized fail-closed errors, and the provider-neutral rate-limit → session → authentication → authorization pipeline with security headers, native audit hooks and health diagnostics. The canonical rate limiter now has atomic Redis implementations and health checks for token-bucket, sliding-window, fixed-window and leaky-bucket strategies; configured Redis failures never fall back to local state in production. P-256, P-384 and P-521 ECDH plus HKDF-SHA256 now execute exact Python-oracle golden vectors through a provider-neutral port and preserve uncompressed-point and RFC 7468 `SubjectPublicKeyInfo` PEM export. Default, maximum-requested, idle and absolute timeout semantics remain distinct. `contracts/session-platform-behavior.json` and `contracts/redis-runtime-behavior.json` cover manager, middleware, pipeline, Redis key, token, failure, rate-limit and ECDH behavior, while the existing cross-language security fixture remains the shared lifecycle oracle. After 50 direct security tests, 25 dependent Rust tests, strict clippy, 1,249 surviving Python tests and 60 Python contracts passed, 2,450 physical production lines and 1,021 implementation-specific test lines of superseded Python were deleted. JWT verification pins type and algorithm, checks signatures in constant time, requires issuer/audience/time/JTI claims, and rejects reserved-claim overrides. Rust also rejects executable pickle session serialization, malformed backend records, missing providers and insecure production configuration. Remaining security work is limited to other capability consumers and provider families tracked by their own rows; no Python session implementation remains. |
| Cedar authorization | Rust kernel complete; gateway consumer cutover next | Wave 25 adds one schema-required, size-bounded Cedar 4.8 adapter to `mmf-security`. Policy syntax and schema validation occur before startup succeeds; entity, context and request validation fail closed; Cedar's deny-overrides decision is preserved; determining policies and normalized evaluation failures are exposed; and the adapter implements the existing provider-neutral `PolicyProvider` port. Rust executes the Cedar cases in `contracts/gateway-runtime-behavior.json`, including allow, implicit deny, explicit forbid, malformed policy/schema and invalid typed context. Marty UI still owns its Python Cedar wiring until the gateway slice consumes this adapter and its 432-route contract passes. |
| Data and infrastructure | Active; production Redis cache adapter complete | `mmf-data` owns cache backend/pattern/config/stats semantics, fail-closed JSON/string/bytes serialization, full ordinary and sorted-set cache behavior, deterministic TTL behavior, read-model equality/range/set filtering, validated sorting/pagination, generic repositories, migration revisions/schema verification, and validated PostgreSQL identifier/literal/JSONB/insert generation. The canonical Redis adapter now implements every ordinary and sorted-set cache operation, enforces configured namespaces/key prefixes, requires TLS in production, verifies startup health, uses bounded `SCAN` instead of database-wide `KEYS`/`FLUSHDB`, and propagates provider failures instead of returning false, `None`, or empty success-like results. Direct tests cover configuration and the provider-neutral cache contract without requiring Redis; `MMF_REDIS_TEST_URL` enables live TTL, sorted-set, statistics, key-scan, deletion, and namespace-isolation acceptance. `mmf-runtime` owns typed instance/factory registration plus singleton/transient/scoped lifetimes and the canonical required-component readiness gate. Required backends register as unknown, block activation until every one is healthy, and immediately make live readiness false if any becomes degraded, unknown or unhealthy; optional degraded components may preserve readiness while still degrading aggregate health. Lexicographically stable failure details and bounded component names execute `contracts/runtime-readiness.json`, with five runtime tests and strict Clippy green. `mmf-config` owns hosting detection, deployment/configuration strategies, secret metadata/expiry, and async secret/configuration backend ports. Executable Python pickle is intentionally rejected. Memcached, relational/MongoDB, cluster/sentinel, migration-provider and cloud-secret adapters, unified-config consumers, and service cutovers remain before deleting the Python infrastructure family; Python and Rust execute `contracts/data-infrastructure-behavior.json` and `contracts/config-runtime-behavior.json`. |
| Messaging and events | Active; PostgreSQL outbox/inbox adapter complete | `mmf-messaging` consolidates the core, extended, enhanced-event-bus and outbox surfaces into one envelope and provider contract; it owns event kinds and registration, rich metadata, routing/filtering, subscriptions, JSON serialization, batch/priority/scheduled delivery, inbox idempotency, transactional-outbox state, deterministic partitioning, retry/DLQ/requeue/replay, health and Kafka/database/NATS/RabbitMQ/Redis/AWS transport ports while reusing `mmf-resilience` retry configuration. The optional `postgres` feature now owns an advisory-locked outbox/inbox schema, caller-transaction enqueue, source-service and tenant isolation, stable partitions, `SKIP LOCKED` claims, per-attempt fencing leases, crash recovery, bounded retry/dead-letter/requeue/replay, duplicate inbox rejection, expired-payload scrubbing, retention cleanup and health. Focused source and optional `MMF_POSTGRES_TEST_URL` live acceptance gates compile and pass; no local endpoint was available, so the live path was skipped here. Python and Rust execute `contracts/messaging-behavior.json` before remaining transports, consumer ports and Python deletion. |
| Discovery, gateway, mesh and deployment | Active; proxy and HTTP/gRPC transport kernels complete | `mmf-platform` consolidates service endpoints/metadata/health, filtered discovery, all seven load-balancing strategies, route matching/constraints, deployment lifecycle and Kubernetes manifests. Wave 25 adds the canonical reverse-proxy executor over existing discovery, upstream and `mmf-resilience` ports: bounded request/response bodies, route deadlines, idempotent-method retries only, trusted identity-header stripping/reinjection, repeated query values with legacy incoming-key precedence, path rewriting, response-header filtering, and MIP error normalization. The same crate owns reusable protocol-version negotiation, content-type policy, weak ETag decisions, exact request fingerprints, provider-neutral idempotency leases/stores, and deterministic in-memory and atomic Redis stores with replay, conflict, in-progress, expiry, completion, owner-token safe-abort and health semantics. It now owns canonical Tonic client and server TLS composition: bounded plaintext-development, server-TLS and mutual-TLS clients, native or private-CA trust, SNI, secret-file loading, eager/lazy startup, HTTP/2 keepalive, and mandatory client-certificate verification for workload servers. `mmf-security` owns the shared exact method-to-SPIFFE authorization policy and constant-time service-secret comparison. Missing identities are unauthenticated; wrong identities and unlisted methods are forbidden; malformed policy or partial server credentials fail closed under `contracts/workload-grpc-security.json`. Credentialed targets, TLS downgrade, partial identities and ambiguous trust continue to fail closed under `contracts/grpc-client-behavior.json`. Focused security/platform tests and strict Clippy pass. `contracts/platform-behavior.json`, `contracts/gateway-runtime-behavior.json`, `contracts/http-runtime-behavior.json`, and `contracts/redis-runtime-behavior.json` remain the other language-neutral oracles. Mesh policy models are reused from `mmf-security`; rate limiting remains canonical there. Marty UI supplies only MIP policy, certificate parsing through `marty-crypto`, and generated service clients, and must consume these shared primitives rather than retain service-local transport or authorization constructors. Gateway/Flow cutover and obsolete transport deletion are the next gates. |
| Built-in identity service | Rust-native; Python backend deleted | Wave 23 moved all intended service configuration, 11-provider composition, auth orchestration, password/token/API-key adapters, persistence, Axum HTTP routes and middleware, authorization guards, plugin diagnostics, and the deployable service binary into `mmf-services`, while reusable JWT and identity models remain in `mmf-security` and configuration/secret layering remains in `mmf-config`. Four language-neutral fixtures cover configuration, use cases, persistence, routes, middleware, and failure behavior. Native adapters use Scrypt password hashes, password policy/expiry/lockout, configurable 256-bit-or-greater API-key entropy/limits/expiry/rotation/usage metadata, signed HMAC JWTs, typed revocation storage, and production startup refuses absent key/password secrets. The root container and Kubernetes manifest now run Rust; the React login/profile UI is retained and consumes real JWTs. Petstore consumers now call the Rust `/auth/validate` boundary through a fail-closed HTTP adapter and its example stack includes the Rust service, with no local JWT cryptography. After full Rust workspace tests/clippy/docs, UI TypeScript/lint, Python CI, binary compilation, crate-content gates, and consumer import analysis, 76 superseded Python files totaling 12,248 physical lines were deleted, including implementation-specific tests, unused framework adapters, and five obsolete demos. The deleted Python oracle had 259 passing/9 skipped tests and four pre-existing stale failures; Rust corrects the success-without-user and unimplemented token-validation paths fail closed. Live core-security memory/Redis session adapters remain separately tracked as a consumer cutover. |
| Built-in audit and compliance services | Active | `mmf-services::audit` consolidates the overlapping Python audit and audit-compliance domains while reusing `mmf-security` audit events, threat levels, detection results, and auditor contracts. It owns request context and forwarding policy, compliance frameworks/findings/scans, threat-pattern lifecycle, normalized query models, and explicit repository/destination/native-encryption/scanner/SIEM/report provider ports. Python and Rust execute `contracts/audit-compliance-behavior.json`; persistence, middleware/interceptor, scanner, report, and SIEM consumer cutovers remain before immediate Python deletion. |
| Workflow and consistency patterns | Active | `mmf-workflow` consolidates both Python saga models and the workflow package into one validated durable state machine for action, decision, parallel, loop, wait and compensation steps; dependencies, retry scheduling, timeouts, pause/resume/cancel, reverse compensation, repository and action-provider ports are explicit. `mmf-patterns` owns CQRS command/query routing and idempotency, optimistic-concurrency event streams, aggregate replay, snapshots, projections/checkpoints, consistency policy and 2PC lifecycle. It reuses `mmf-messaging` outbox/inbox/DLQ, `mmf-data` read models and `mmf-workflow` sagas instead of duplicating them. Python and Rust execute `contracts/workflow-patterns-behavior.json`; provider adapters and consumer cutover remain before deleting the duplicate Python implementations. |
| Test tooling | Active | `mmf-testkit` owns deterministic clocks/IDs/fault schedules, event collection, test result models, validated load/stress/spike/endurance/scalability/volume/baseline plans, aggregate latency/throughput/error metrics, HTTP/gRPC/event/message/database/GraphQL/WebSocket contract models and strictness-aware verification, safe provider-neutral chaos experiment lifecycle with mandatory recovery/cleanup, steady-state probes, request and test-database ports. Real HTTP, process, container, Kubernetes and database effects remain adapters; the core never executes destructive shell commands. Rust executes `contracts/testkit-behavior.json`; Python contracts and consumer cutover remain before deleting the Python testing family. |
| Push delivery | Active; Python implementation deleted | `mmf-push` is the single implementation for the six-channel push model, fail-closed registry/routing and token lookup, FCM payloads/batches/retries/credential-provider contract, SSE subscriptions/targeting/limits/heartbeats/stale cleanup, signed and filtered webhook delivery over shared `mmf-resilience` circuits/backoff, deterministic mocks, token lifecycle normalization/redacted events, adapter health, and provider ports. The legacy Python oracle and Rust both passed `contracts/push-behavior.json`; the 2,186-line Python push core and adapter family was then deleted because repository consumer inventory was empty. External FCM OAuth/HTTP and webhook HTTP effects remain provider adapters, not duplicate orchestration. |
| ML platform | Active; Python implementation deleted | `mmf-ml` owns the complete ML domain model, feature and feature-group registration, online/offline feature storage, schema validation, numerical/categorical statistics, model versions/latest aliases/status/lineage, training lifecycle, provider-neutral loading/inference/unloading, deterministic prediction caching, serving metrics/status, and A/B experiment contracts. Runtime inference is an explicit fail-closed provider instead of simulated random framework branches, and model artifacts remain redacted from serialization. The legacy Python oracle and Rust both passed `contracts/ml-behavior.json`; all 1,255 physical lines in the isolated Python ML package were then deleted. |
| Plugin platform | Active; identity consumer cut over | `mmf-plugins` now owns service and gateway-middleware plugin kinds, metadata/context/routes/services, namespaced typed configuration and provider ports, discovery and loader ports, registry conflict checks, missing-dependency and cycle rejection, deterministic dependency/start/reverse-stop ordering, lifecycle state enforcement, dynamic enable/disable, service status, health, event subscriptions, and safe unload rules. Rust executes `contracts/plugins-behavior.json`; Python executes the surviving model/config vectors. The built-in identity service now exposes plugin/version diagnostics through `mmf-plugins`; remaining Python plugin-manager consumers and provider adapters still require cutover before Python core/config deletion. |
| Documentation, contracts and developer CLI | Active; Python implementation deleted | `mmf-cli` owns FastAPI/protobuf discovery, OpenAPI 3.0.3, Postman, gRPC, unified and gateway documentation, API-version/deprecation state, UTF-8 rendering, reusable template variables/filters/conditions/loops/includes/macros, the complete historical command catalog, Rust-first scaffolds for all ten intended template families, explicit process/filesystem ports, migration and mesh generation, plugin scaffolding, and contract registry/execution/Markdown/JUnit/monitoring semantics. It reuses `mmf-testkit` contract verification, `mmf-platform` deployment/mesh models and `mmf-plugins` metadata. The legacy oracle and Rust passed `contracts/cli-documentation-behavior.json`; 773 physical Python lines and the obsolete Jinja assets were deleted after an empty consumer audit. Rust intentionally corrects the legacy Windows locale-encoding crash, undefined gRPC-client-template variable and unary-only streaming classification. Provider-specific live contract, registry, cluster, database and policy effects remain explicit fail-closed adapters rather than duplicate command logic. Package contents validate locally; release order must publish `mmf-testkit`, `mmf-platform`, and `mmf-plugins` before `mmf-cli`. |
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
| `mmf-security` | JWT and OAuth2/OIDC, RBAC, ABAC, schema-validated Cedar and OPA/policy adapters, zero-trust request context, sessions, MFA/TOTP, rate limits, audit hooks, KMS/OpenBao ports, and normalized security errors |
| `mmf-observability` | OpenTelemetry setup, propagation and correlation, structured redacted logging, Prometheus metrics, traces, SLOs, business metrics, dashboards/alerts metadata, and HTTP/gRPC/data/messaging instrumentation |
| `mmf-resilience` | Deadlines, retries with jitter, circuit breakers, bulkheads, fallbacks, dependency policies, connection-pool supervision, and resilience metrics |
| `mmf-platform` | Service discovery and registration, Consul/DNS adapters, load balancing, route matching and reverse-proxy execution, protocol-version/content-type/ETag/idempotency HTTP kernels, canonical bounded Tonic channel and TLS/mTLS composition, service-mesh policy/configuration, Kubernetes/container metadata, and deployment generation |
| `mmf-plugins` | Discovery, metadata, dependencies, ordering, namespaced configuration, enable/disable, lifecycle, service definitions, health aggregation, and extension points |
| `mmf-push` | Push registry and lifecycle, FCM, SSE, webhook and test adapters, subscriptions, delivery outcomes, retries, and health |
| `mmf-ml` | Feature store, model registry, model serving, model health/versioning, and A/B experiment contracts and adapters |
| `mmf-testkit` | In-memory/test adapters, contract harnesses, service fixtures, fault injection, load/spike/endurance/chaos runners, and deterministic clocks/IDs |
| `mmf-cli` | Rust-first service/plugin scaffolding and template customization; command parsing/planning and scoped host effects; build, test, run, deploy, info, config, API documentation/versioning, contract, migration, service-mesh, security, database and plugin commands. Reuses `mmf-testkit`, `mmf-platform`, and `mmf-plugins` models instead of copying them. |
| `mmf` | Ergonomic facade and feature flags only; no second implementation |

### Dependency rules

- `mmf-core` has no dependency on another MMF crate.
- Infrastructure crates depend on stable ports and models, never on an owning
  application service.
- Cross-cutting telemetry and resilience are composed through middleware and
  traits, not copied helpers.
- Optional providers are adapter modules behind Cargo features.
- `marty-core` remains the canonical owner of credential protocols,
  credential verification, product key/signature/certificate kernels, and
  policy decisions. Reusable framework authentication, authorization,
  session, rate-limit, and RFC 6238 MFA behavior belongs to `mmf-security` and
  is not duplicated in service crates.
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
| Data and caching | Async relational pools and transactions; PostgreSQL/MySQL adapters; MongoDB adapters; migrations; repositories; namespaced Redis cache/session (direct adapter complete); cluster/sentinel and pool health | `mmf-data` |
| Messaging and events | Kafka, database and in-memory test transports; rich metadata; routing/filtering; dynamic subscriptions; transactional PostgreSQL outbox/inbox (adapter complete); retries; DLQ; replay; batch/scheduled/priority publishing | `mmf-messaging` |
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

Port the `marty-ui` gateway first, followed by flow and organization. The
gateway's 432-route public contract is frozen and its generic reverse-proxy,
Cedar, protocol-version, content-type, ETag, and idempotency prerequisites are
implemented in MMF Wave 25. Complete the Rust gateway consumer and its
Redis/gRPC adapters, run route/middleware/failure parity, and delete the superseded Python
gateway before moving to flow. Then complete SQL/Redis migrations, event
envelopes, transactional outbox, Kafka, discovery, security context and
provider adapters needed by the following services.

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
