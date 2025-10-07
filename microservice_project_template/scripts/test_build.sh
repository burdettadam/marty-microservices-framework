#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "${ROOT_DIR}"
rm -rf build dist
uv run pip wheel . --no-deps --wheel-dir build >/dev/null

if [[ -d "build" ]] && ls build/*.whl >/dev/null 2>&1; then
  echo "Build artifact created successfully" >&2
else
  echo "[error] failed to create wheel" >&2
  exit 1
fi
