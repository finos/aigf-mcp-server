#!/usr/bin/env bash
#
# Local-only runner that supplies a GitHub token to the wrapped command.
#
# No credential is stored in this repository. The token is resolved at runtime
# -- from the environment if you exported one, otherwise from the gh CLI's own
# credential -- and verified against the GitHub API before the command runs.
#
# The verification is not ceremony. A revoked token is worse than no token at
# all: GitHub answers 401 where an unauthenticated request would have returned
# 200, so a stale token silently degrades every gate this script fronts. Fail
# loudly here instead of confusingly three layers down.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -eq 0 ]]; then
  cat <<'USAGE'
Usage: scripts/run-local-with-token.sh <command> [args...]
Examples:
  scripts/run-local-with-token.sh ./scripts/ci-local.sh
  scripts/run-local-with-token.sh ./scripts/go-live-gate.sh
  scripts/run-local-with-token.sh ./scripts/test-http-transport.sh

The token comes from $FINOS_MCP_GITHUB_TOKEN if set, otherwise from `gh auth token`.
USAGE
  exit 1
fi

token=""
token_source=""

if [[ -n "${FINOS_MCP_GITHUB_TOKEN:-}" ]]; then
  token="${FINOS_MCP_GITHUB_TOKEN}"
  token_source="the FINOS_MCP_GITHUB_TOKEN exported in your environment"
elif command -v gh >/dev/null 2>&1 && token="$(gh auth token 2>/dev/null)" && [[ -n "${token}" ]]; then
  token_source="the gh CLI credential"
else
  echo "error: no GitHub token available." >&2
  echo "  Run 'gh auth login', or export FINOS_MCP_GITHUB_TOKEN yourself." >&2
  exit 1
fi

# --config - keeps the token out of the process table, where a --header
# argument would have been visible to every other user via ps.
http_status="$(
  printf 'header = "Authorization: token %s"\n' "${token}" |
    curl --silent --show-error --config - \
      --output /dev/null --write-out '%{http_code}' \
      --max-time 10 \
      https://api.github.com/rate_limit
)" || {
  echo "error: could not reach api.github.com to verify the token." >&2
  exit 1
}

if [[ "${http_status}" != "200" ]]; then
  echo "error: ${token_source} was rejected by GitHub (HTTP ${http_status})." >&2
  if [[ "${token_source}" == the\ FINOS_MCP_GITHUB_TOKEN* ]]; then
    echo "  Unset FINOS_MCP_GITHUB_TOKEN to fall back to the gh CLI credential." >&2
  else
    echo "  Run 'gh auth login' to refresh it." >&2
  fi
  echo "  Refusing to continue: a rejected token fails harder than no token." >&2
  exit 1
fi

export FINOS_MCP_GITHUB_TOKEN="${token}"
exec "$@"
