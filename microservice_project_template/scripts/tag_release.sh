#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <semver>" >&2
  exit 1
fi

VERSION="${1}"
TAG="v${VERSION}"

git tag -a "${TAG}" -m "Release ${TAG}"
git push origin "${TAG}"
