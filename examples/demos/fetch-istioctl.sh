#!/usr/bin/env bash
set -euo pipefail

readonly ISTIO_VERSION="1.27.2"
readonly ISTIOCTL_SHA256="c62bd13f00050dd8cc94ebaacbe41bd8076aba47606ccce98f4b3d9f7a2680b9"
readonly REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly DESTINATION="$REPOSITORY_ROOT/examples/demos/istio-${ISTIO_VERSION}/bin/istioctl"

if [[ "$(uname -s)" != "Linux" || "$(uname -m)" != "x86_64" ]]; then
  echo "The checked-in demo binary was Linux x86_64; install istioctl ${ISTIO_VERSION} for this platform manually." >&2
  exit 1
fi

temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

archive="$temporary_directory/istio.tar.gz"
curl --fail --location --silent --show-error \
  "https://github.com/istio/istio/releases/download/${ISTIO_VERSION}/istio-${ISTIO_VERSION}-linux-amd64.tar.gz" \
  --output "$archive"
tar --extract --gzip --file "$archive" --directory "$temporary_directory" \
  "istio-${ISTIO_VERSION}/bin/istioctl"

downloaded="$temporary_directory/istio-${ISTIO_VERSION}/bin/istioctl"
echo "${ISTIOCTL_SHA256}  ${downloaded}" | sha256sum --check --strict
install --mode 0755 "$downloaded" "$DESTINATION"
echo "Installed istioctl ${ISTIO_VERSION} at ${DESTINATION}"
