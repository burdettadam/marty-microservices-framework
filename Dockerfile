FROM rust:1.93-bookworm AS build

WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
RUN cargo build --locked --release -p mmf-services --bin identity-service

FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

COPY --from=build /src/target/release/identity-service /usr/local/bin/identity-service

ENV MMF_BIND=0.0.0.0:8000
EXPOSE 8000
USER appuser

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD curl --fail --silent http://localhost:8000/health >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/identity-service"]
