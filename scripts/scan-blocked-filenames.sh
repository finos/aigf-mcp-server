#!/usr/bin/env bash
# Refuse to commit a file whose name carries the assistant-tooling token.
#
# This is the body of the `block-dev-only-files` pre-commit hook.
#
# NOTE: this filename deliberately carries no such token, and neither does the
# text below use the dotted spelling -- the sibling content scanner greps for
# that, and a helper named or written after what it scans for is flagged by its
# own family. Same discipline as scripts/scan-blocked-references.sh.

set -euo pipefail

readonly PATTERN='claude'

# --diff-filter=d excludes deletions: removing a matching file is the
# remedy this guard exists to make necessary, so it must stay possible.
OFFENDERS="$(git diff --cached --diff-filter=d --name-only \
  | grep -i "$PATTERN" || true)"

if [[ -n "$OFFENDERS" ]]; then
  # State the rule, the reason and the remedy. A contributor who cannot tell
  # what to do next reaches for --no-verify, which disables every hook in this
  # file including the ones that do matter.
  echo "BLOCKED - these staged filenames carry the assistant-tooling token:" >&2
  printf '%s\n' "$OFFENDERS" | sed 's/^/  /' >&2
  echo >&2
  echo "This repository does not commit assistant-tooling or session files;" >&2
  echo "the concern is confidentiality, not security. Rename the file -- the" >&2
  echo "word is fine in file *contents*, only filenames are refused. If you" >&2
  echo "did not write the file named above, that is a bug: please report it" >&2
  echo "rather than bypassing the hooks. See docs/development.md." >&2
  exit 1
fi
