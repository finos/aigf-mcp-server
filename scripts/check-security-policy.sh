#!/usr/bin/env bash
# Refuse a SECURITY.md that describes the reporting route of the other
# visibility.
#
# Usage: scripts/check-security-policy.sh [OWNER/REPO]
#   OWNER/REPO  defaults to $GITHUB_REPOSITORY, then to the repository the
#               remote ${GO_LIVE_REMOTE:-origin} points at.
#
# Environment:
#   GO_LIVE_VISIBILITY  private or public: the form to expect, named without
#                       asking GitHub. public means the reporting form is
#                       available (a public repository with private reporting
#                       enabled); private means it is not.
#
# GitHub private vulnerability reporting exists only on a public repository,
# and only once it is enabled there. SECURITY.md says the form is not
# available, or links it; each sentence is false on the other side (#138).
# Only GitHub knows, so this asks it: the visibility, and on a public
# repository whether private reporting is enabled. A public repository with
# reporting disabled expects the "not available" form (#389).
#
# This is the body of Gate 11 in scripts/go-live-gate.sh.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! PYTHON_BIN="$("$ROOT_DIR/scripts/project-python.sh" --print-interpreter)"; then
  exit 1
fi

VISIBILITY="${GO_LIVE_VISIBILITY:-}"
if [ -n "$VISIBILITY" ]; then
  # The caller named the visibility, so GitHub is not asked anything.
  exec "$PYTHON_BIN" "$ROOT_DIR/scripts/security_policy_route.py" \
    "$VISIBILITY" "$ROOT_DIR/SECURITY.md"
fi

REPO="${1:-${GITHUB_REPOSITORY:-}}"
if [ -z "$REPO" ]; then
  REPO="$(gh repo view "$(git remote get-url "${GO_LIVE_REMOTE:-origin}")" \
    --json nameWithOwner --jq .nameWithOwner)"
fi

API_LOG="$(mktemp)"
trap 'rm -f "$API_LOG"' EXIT

# Failure here is fatal: "I could not ask" is not "the repository is private".
if ! PRIVATE="$(gh api "repos/$REPO" --jq .private 2>"$API_LOG")"; then
  echo "BLOCKED - could not read the visibility of $REPO." >&2
  sed 's/^/  /' "$API_LOG" >&2
  exit 1
fi
case "$PRIVATE" in
  true) VISIBILITY=private ;;
  false)
    # This endpoint answers 404 on a private repository, so it is asked only here.
    if ! ENABLED="$(gh api "repos/$REPO/private-vulnerability-reporting" \
      --jq .enabled 2>"$API_LOG")"; then
      echo "BLOCKED - could not read whether private vulnerability reporting is" >&2
      echo "enabled on $REPO." >&2
      sed 's/^/  /' "$API_LOG" >&2
      exit 1
    fi
    if [ "$ENABLED" = true ]; then
      VISIBILITY=public
      echo "$REPO is public and private vulnerability reporting is enabled."
    else
      VISIBILITY=private
      echo "$REPO is public and private vulnerability reporting is not enabled."
    fi
    ;;
  *)
    echo "BLOCKED - GitHub answered '$PRIVATE' for the 'private' field of $REPO." >&2
    exit 1
    ;;
esac

"$PYTHON_BIN" "$ROOT_DIR/scripts/security_policy_route.py" \
  "$VISIBILITY" "$ROOT_DIR/SECURITY.md"
