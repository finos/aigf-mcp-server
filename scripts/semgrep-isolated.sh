#!/usr/bin/env bash
set -euo pipefail

# Run semgrep in an isolated venv to avoid dependency conflicts with app runtime deps.
# Environment variables:
#   SEMGREP_VENV   Override venv path (default: .venv-semgrep)
#   SEMGREP_PYTHON Override python binary used to create venv (default: auto-detect >=3.10)
#   SEMGREP_VERSION Override semgrep version (default: 1.149.0)

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEMGREP_VENV="${SEMGREP_VENV:-$ROOT_DIR/.venv-semgrep}"
SEMGREP_PYTHON="${SEMGREP_PYTHON:-}"
SEMGREP_VERSION="${SEMGREP_VERSION:-1.149.0}"

resolve_semgrep_python() {
  if [[ -n "$SEMGREP_PYTHON" ]]; then
    echo "$SEMGREP_PYTHON"
    return
  fi

  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
      then
        echo "$candidate"
        return
      fi
    fi
  done

  echo "python3"
}

SEMGREP_PYTHON="$(resolve_semgrep_python)"

if [[ ! -x "$SEMGREP_VENV/bin/semgrep" ]]; then
  echo "Creating isolated semgrep environment at $SEMGREP_VENV"
  "$SEMGREP_PYTHON" -m venv "$SEMGREP_VENV"
  "$SEMGREP_VENV/bin/python" -m pip install --upgrade pip
  "$SEMGREP_VENV/bin/pip" install "semgrep==$SEMGREP_VERSION"
fi

exec "$SEMGREP_VENV/bin/semgrep" "$@"
