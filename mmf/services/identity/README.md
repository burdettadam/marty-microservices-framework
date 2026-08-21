# MMF Identity Service

The identity backend is implemented by the `identity-service` binary in
`crates/mmf-services`. This directory retains the standalone React login and
profile client; it no longer contains a Python service implementation.

The Rust service owns the complete built-in identity contract:

- Basic, API-key, JWT, OAuth2/OIDC, SAML, mTLS, MFA, session, environment, and
  LDAP provider composition;
- Scrypt password verification and provider ports for additional native hash
  implementations;
- signed JWT issue, validation, refresh, and revocation;
- API-key issue, authentication, metadata, expiry, and revocation;
- user persistence ports and deterministic in-memory storage;
- Axum routes, authentication middleware, role/permission guards, health,
  backend/version diagnostics, and plugin diagnostics;
- layered `mmf-config` snapshots and fail-closed secret resolution.

Shared language-neutral behavior lives under `contracts/identity-*.json` and
is executed by Rust tests. The old Python implementation-specific tests were
removed with the implementation.

## Run the backend

```bash
cargo run -p mmf-services --bin identity-service
```

Development defaults retain the example `admin` / `admin123` login. Set
`MMF_ENVIRONMENT=production`; `MMF_JWT_KEY` and `MMF_ADMIN_PASSWORD` then
become mandatory and startup fails if either is absent.

## Run the UI

```bash
cd mmf/services/identity/ui
npm ci
npm run dev
```

The UI calls `/api/authenticate`, `/api/auth/me`, and `/api/auth/validate`.
The provided nginx configuration proxies `/api/` to the Rust identity service.
