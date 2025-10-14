#!/usr/bin/env bash
set -euo pipefail

if ! command -v kind >/dev/null 2>&1; then
  echo "KinD is not installed. Install https://kind.sigs.k8s.io/ first." >&2
  exit 1
fi

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
CLUSTER_NAME=${CLUSTER_NAME:-microservice-template}
CONFIG_FILE="${ROOT_DIR}/kind/cluster-config.yaml"

echo "Creating KinD cluster..." >&2
kind create cluster --name "${CLUSTER_NAME}" --config "${CONFIG_FILE}" --wait 60s

echo "Building Docker image..." >&2
"${ROOT_DIR}/scripts/docker_build.sh"

echo "Loading image into KinD cluster..." >&2
kind load docker-image microservice-template:latest --name "${CLUSTER_NAME}"

echo "Applying base manifests..." >&2
kubectl apply -k "${ROOT_DIR}/k8s/overlays/dev"

echo "Applying observability stack..." >&2
kubectl apply -k "${ROOT_DIR}/k8s/observability"

echo "Waiting for pods to be ready..." >&2
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=microservice-template --timeout=120s

kubectl get pods -A
