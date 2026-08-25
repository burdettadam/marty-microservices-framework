# Security Policy

## Supported Versions

| Version | Status |
|---------|--------|
| 0.1.x Rust crates | Active development; security issues addressed on a best-effort basis |
| 1.0.x Python package | Retired; no supported runtime or release channel |

A formal stable-support window will be published before a 1.0 Rust release.

## Reporting a Vulnerability

**Please do not file public GitHub issues for security vulnerabilities.**

To report a security issue privately:

1. Open a **GitHub Security Advisory** on this repository using the "Security" tab → "Advisories" → "New draft security advisory" (preferred).
2. Alternatively, email the maintainers at the address listed in the repository's GitHub profile.

Please include:

- A description of the vulnerability and the affected component
- Steps to reproduce or a proof-of-concept
- Any suggested remediation if you have one

## Response Timeline

- **Acknowledgement:** within 5 business days
- **Initial assessment:** within 10 business days
- **Fix or mitigation plan:** communicated before any public disclosure

We follow coordinated disclosure. We ask that you give us a reasonable window (typically 90 days) to remediate before publishing details publicly.

## Scope

This policy covers:

- All crates under `crates/`
- Language-neutral behavior and security fixtures under `contracts/`
- The Rust identity-service container build
- CI, dependency, and supply-chain configuration in this repository

Issues in third-party dependencies should also be reported to their upstream
projects. Please report an MMF exposure privately even when the root cause is
upstream.

## Out of Scope

- Theoretical attacks with no practical impact
- Issues requiring physical access to a host running the framework
- Social engineering
