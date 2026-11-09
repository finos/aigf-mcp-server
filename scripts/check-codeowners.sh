#!/usr/bin/env bash
# Refuse a CODEOWNERS file that GitHub cannot resolve.
#
# Usage: scripts/check-codeowners.sh [REF] [OWNER/REPO]
#   REF         commit, branch or tag to check; defaults to HEAD. It must
#               already be pushed -- GitHub can only read what it has.
#   OWNER/REPO  defaults to $GITHUB_REPOSITORY, then to the repository the
#               remote ${GO_LIVE_REMOTE:-origin} points at -- the same remote
#               Gate 9 reads, not whichever one gh would guess.
#
# Every line of .github/CODEOWNERS once named an unrelated account with no
# access here, and nothing noticed: the file was well-formed,
# so no local tool can tell a real owner from a stranger (#158). Only GitHub's
# codeowners/errors endpoint knows who the owners resolve to, so this asks it.
#
# This is the body of Gate 10 in scripts/go-live-gate.sh, and the CODEOWNERS
# Owners job in security-analysis.yml runs it on every run of that workflow.

set -euo pipefail

REF="${1:-$(git rev-parse HEAD)}"
REPO="${2:-${GITHUB_REPOSITORY:-}}"
if [ -z "$REPO" ]; then
  REPO="$(gh repo view "$(git remote get-url "${GO_LIVE_REMOTE:-origin}")" \
    --json nameWithOwner --jq .nameWithOwner)"
fi

API_LOG="$(mktemp)"
trap 'rm -f "$API_LOG"' EXIT

# Failure here is fatal. A missing file, an unpushed ref and a bad token all
# answer 404 or 401, and "I could not ask" is not "there were no errors".
if ! ERRORS="$(gh api "repos/$REPO/codeowners/errors?ref=$REF" \
  --jq '.errors[] | "  line \(.line): \(.kind): \(.source | rtrimstr("\n"))"' \
  2>"$API_LOG")"; then
  echo "BLOCKED - could not read CODEOWNERS errors for $REPO at $REF." >&2
  sed 's/^/  /' "$API_LOG" >&2
  echo "Is the ref pushed, does it contain .github/CODEOWNERS, and can gh reach" >&2
  echo "the API? This check cannot pass on a file it has not read." >&2
  exit 1
fi

if [ -n "$ERRORS" ]; then
  echo "FAIL - GitHub cannot resolve CODEOWNERS for $REPO at $REF:" >&2
  echo "$ERRORS" >&2
  exit 1
fi

echo "CODEOWNERS for $REPO at $REF resolves with no errors."
