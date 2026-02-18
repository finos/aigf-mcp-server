#!/usr/bin/env bash
set -euo pipefail

# Run semgrep in an isolated venv to avoid dependency conflicts with app runtime deps.
# Environment variables:
#   SEMGREP_VENV   Override venv path (default: .venv-semgrep)
#   SEMGREP_PYTHON Override python binary used to create venv (default: python3)
#   SEMGREP_VERSION Override semgrep version (default: 1.149.0)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEMGREP_VENV="${SEMGREP_VENV:-$ROOT_DIR/.venv-semgrep}"
SEMGREP_PYTHON="${SEMGREP_PYTHON:-python3}"
SEMGREP_VERSION="${SEMGREP_VERSION:-1.149.0}"

if [[ ! -x "$SEMGREP_VENV/bin/semgrep" ]]; then
  echo "Creating isolated semgrep environment at $SEMGREP_VENV"
  "$SEMGREP_PYTHON" -m venv "$SEMGREP_VENV"
  "$SEMGREP_VENV/bin/python" -m pip install --upgrade pip
  "$SEMGREP_VENV/bin/pip" install "semgrep==$SEMGREP_VERSION"
fi

exec "$SEMGREP_VENV/bin/semgrep" "$@"
