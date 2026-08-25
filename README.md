# Marty Microservices Framework

MMF is ElevenID's canonical Rust microservice crate platform. The former
`marty-msf` Python distribution is frozen compatibility history and must not be
used by new services.

## Rust platform

The Cargo workspace provides one DRY implementation for shared capabilities:

- `mmf-core` and the `mmf` facade for common contracts and composition;
- `mmf-config`, `mmf-runtime`, and `mmf-platform` for configuration, lifecycle,
  readiness, and deployment models;
- `mmf-security`, `mmf-data`, and `mmf-messaging` for security, persistence,
  caching, events, outbox, and transport ports;
- `mmf-observability`, `mmf-resilience`, and `mmf-workflow` for cross-cutting
  runtime behavior;
- `mmf-plugins`, `mmf-services`, `mmf-push`, `mmf-ml`, `mmf-patterns`,
  `mmf-testkit`, and `mmf-cli` for higher-level capabilities and tooling.

Language-neutral behavior fixtures live in [`contracts`](contracts), and Rust
implementations execute those contracts in CI.

```shell
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
```

Consumers should pin a reviewed immutable repository revision until a governed
crate publication channel is established.

## Production Use

The Rust crates are the supported production platform. The frozen Python
distribution is retained only for migration verification and rollback evidence;
it must not receive new production features or releases.

## Frozen Python distribution

The `mmf` Python tree and `pyproject.toml` remain temporarily so the last
consumer migration can be verified against the existing `v1.0.2` release. The
Python release/tag workflows have been disabled: no later Python distribution
will be published from this repository.

The final Python source deletion requires all of the following:

1. every intended consumer has merged its Rust/shared replacement;
2. language-neutral parity and negative-path contracts pass;
3. organization and release-artifact searches find no supported Python
   package or import consumer;
4. rollback distributions, SBOMs, attestations, checksums, and source history
   have verified retention copies; and
5. branch protections and maintainer review remain intact.

Historical Python documentation and tests are evidence during this gate, not
the production platform. Do not add new Python framework behavior.

## License

Licensed under the GNU Affero General Public License v3.0 only
(`AGPL-3.0-only`). See [LICENSE](LICENSE).
