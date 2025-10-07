#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker not available, skipping image build." >&2
  exit 0
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

cd "${ROOT_DIR}"

echo "Building Docker image..." >&2
docker build -t microservice-template:latest -t microservice-template:dev .

echo "Docker image built successfully!" >&2
echo "Image tags: microservice-template:latest, microservice-template:dev" >&2
