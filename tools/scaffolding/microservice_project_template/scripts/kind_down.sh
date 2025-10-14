#!/usr/bin/env bash
set -euo pipefail

if ! command -v kind >/dev/null 2>&1; then
  echo "KinD is not installed." >&2
  exit 0
fi

CLUSTER_NAME=${CLUSTER_NAME:-microservice-template}
kind delete cluster --name "${CLUSTER_NAME}"
