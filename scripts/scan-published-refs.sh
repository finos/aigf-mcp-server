#!/usr/bin/env bash
# Refuse to go live while a ref on the remote publishes development-only files.
#
# This is the body of Gate 9 in scripts/go-live-gate.sh.
#
# Gate 1 asks the same question of `git ls-files`, which is HEAD and nothing
# else. Cleaning HEAD does not clean what has already been pushed: tag v0.1.0
# published a tree of eight development-only files for months, one of them
# headed DO NOT COMMIT TO PUBLIC REPOSITORY, while Gate 1 reported PASS (#130).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The pattern is defined once, in the file both gates read.
# shellcheck source=scripts/dev-only-paths.sh
source "$ROOT_DIR/scripts/dev-only-paths.sh"

REMOTE="${1:-origin}"

# A namespace of our own. Fetching into refs/remotes/ would collide with the
# contributor's own tracking refs, and --prune inside a private namespace can
# only ever discard refs this script put there.
readonly SCAN_NS="refs/finos-refscan"

FETCH_LOG="$(mktemp)"

cleanup() {
  git for-each-ref --format='delete %(refname)' "$SCAN_NS" \
    | git update-ref --stdin
  rm -f "$FETCH_LOG"
}
trap cleanup EXIT

# One fetch for every ref the remote advertises -- branches, tags and the
# pull-request refs GitHub maintains. Failure here is fatal: a gate that could
# not reach the remote has not checked it, and reporting PASS for "I did not
# look" is the exact failure #130 is about.
if ! git fetch --quiet --prune "$REMOTE" "+refs/*:$SCAN_NS/*" >"$FETCH_LOG" 2>&1; then
  echo "BLOCKED - could not fetch refs from '$REMOTE'." >&2
  # git's own words. A bad URL, expired credentials and a network outage are
  # three problems with three different remedies, and "could not fetch" alone
  # does not tell them apart.
  sed 's/^/  /' "$FETCH_LOG" >&2
  echo >&2
  echo "This gate cannot report on refs it has not read. Restore access to" >&2
  echo "the remote and run it again." >&2
  exit 1
fi

# Two classes of offender, told apart by what can be done about them.
#   refs/heads/* and refs/tags/*  -- anyone who can push can delete these, so
#                                    an offender here is a fixable defect.
#   everything else               -- refs/pull/N/head is maintained by GitHub,
#                                    which refuses pushes to it, and there is
#                                    no way to delete a pull request. An
#                                    offender here is reported, not fixed.
BLOCKING=""
MANUAL=""

while IFS= read -r scan_ref; do
  [[ -z "$scan_ref" ]] && continue
  # refs/finos-refscan/tags/v0.1.0 -> refs/tags/v0.1.0, the name on the remote.
  remote_ref="refs/${scan_ref#"$SCAN_NS"/}"

  # stderr is deliberately not suppressed: `|| true` keeps a ref that cannot
  # be read from stopping the scan, and without the complaint such a ref would
  # be indistinguishable from a clean one -- silence is what #130 looked like.
  hits="$(git ls-tree -r --name-only "$scan_ref" \
    | grep -E "$DEV_ONLY_PATTERN" || true)"
  [[ -z "$hits" ]] && continue

  entry="$remote_ref"$'\n'"$(printf '%s\n' "$hits" | sed 's/^/    /')"$'\n'
  case "$remote_ref" in
    refs/heads/* | refs/tags/*) BLOCKING+="$entry" ;;
    *) MANUAL+="$entry" ;;
  esac
done < <(git for-each-ref --format='%(refname)' "$SCAN_NS")

# Reported before the failure, so that a run which stops at the blocking class
# still leaves the whole picture behind.
if [[ -n "$MANUAL" ]]; then
  echo "MANUAL GATE - these refs on '$REMOTE' publish development-only files"
  echo "and cannot be deleted by pushing:"
  printf '%s' "$MANUAL" | sed 's/^/  /'
  echo
  echo "GitHub maintains refs/pull/N/head and refuses pushes to it, and a pull"
  echo "request cannot be deleted. Making this repository public publishes"
  echo "every file listed above. Decide that deliberately before going live."
  echo
fi

if [[ -n "$BLOCKING" ]]; then
  echo "BLOCKED - these refs on '$REMOTE' publish development-only files:" >&2
  printf '%s' "$BLOCKING" | sed 's/^/  /' >&2
  echo >&2
  echo "Delete or re-cut the ref, then run this gate again. A branch or tag" >&2
  echo "is deletable by anyone who can push, so none of these has to stay." >&2
  exit 1
fi

echo "No branch or tag on '$REMOTE' publishes development-only files."
