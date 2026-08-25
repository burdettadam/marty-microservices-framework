# Contributing to Marty Microservices Framework

MMF is a Rust workspace. New shared behavior belongs in the lowest reusable
crate and is re-exported rather than copied into another crate or service.

## Changes

- Add or update a language-neutral fixture under `contracts/` for public
  behavior and negative paths.
- Add direct Rust tests in the owning crate and consumer-boundary tests when a
  production service is affected.
- Keep provider-specific effects behind explicit traits and Cargo features.
- Fail startup or the operation closed when a required provider is missing.
- Do not reintroduce the retired Python `marty-msf` package, source tree,
  imports, build metadata, or release workflows.

Run the complete local gate before opening a pull request:

```shell
cargo fmt --all -- --check
cargo clippy --locked --workspace --all-targets -- -D warnings
cargo test --locked --workspace
```

Use an atomic branch and signed-off commit. Pull requests target `main`, retain
the required CI and merge-queue gates, and describe the behavioral and version
impact.

## License and conduct

Contributions are licensed under AGPL-3.0-only and require a Developer
Certificate of Origin sign-off. See [LICENSE](LICENSE),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and
<https://developercertificate.org/>.
