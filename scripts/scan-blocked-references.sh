#!/usr/bin/env bash
# Refuse to commit files that reference the assistant-tooling directory.
#
# This is the body of the `scan-dev-only-references` pre-commit hook. It used to be a
# single `bash -c` one-liner inside .pre-commit-config.yaml, which is why the
# defect below survived: the entry was long enough that nobody read it, and its
# behaviour was only discoverable by tripping it.
#
# The hook greps staged files for a literal string. Four tracked files in this
# repository necessarily contain that string, because their whole purpose is to
# exclude the thing it names -- the ignore rules, the go-live gate's
# tracked-folder pattern, the hook configuration that declares this very hook,
# and this script. With the hooks installed, every one of those files was permanently
# uneditable, including the file that installs the hooks.
#
# That circularity is a large part of why `pre-commit install` was never run in
# this repository, so the enforcement point .pre-commit-config.yaml names as the
# only one it has did not exist at all (#56). The allowlist below is the fix,
# and it is deliberately a list of exact paths rather than a pattern: a glob
# would silently widen, and a hook that quietly stops scanning still reports
# Passed.
#
# NOTE: this filename deliberately contains no "claude". The companion
# block-dev-only-files hook refuses a staged filename with that word, so a helper named
# after what it scans for would be flagged by its own sibling.
#
# The fate of this hook family is #84's question, not this script's. This only
# makes it possible to satisfy.

set -euo pipefail

# The token these files may legitimately name. Assembled from the leading dot
# and the word so the two are visible separately -- it is the same string the
# hook has always grepped for.
readonly PATTERN='\.claude'

# Every tracked file that must name the pattern in order to exclude it. Keep in
# sync with _CONTENT_SCAN_ALLOWLIST in tests/unit/test_ci_config_drift.py, which
# asserts each entry still exists and still needs to be here -- an allowlist
# entry for a file that no longer contains the pattern is an exemption nobody
# is checking.
readonly ALLOWLIST=(
  ".pre-commit-config.yaml"               # declares this hook and its siblings
  ".gitignore"                            # ignores the directory
  "scripts/dev-only-paths.sh"             # the one DEV_ONLY_PATTERN definition
  "scripts/scan-blocked-references.sh"    # this file: it holds the pattern
)

is_allowed() {
  local candidate="$1" allowed
  for allowed in "${ALLOWLIST[@]}"; do
    [[ "$candidate" == "$allowed" ]] && return 0
  done
  return 1
}

STAGED=()
while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  # A staged deletion has no working-tree file left to grep.
  [[ -f "$file" ]] || continue
  is_allowed "$file" && continue
  STAGED+=("$file")
done < <(git diff --cached --name-only)

# No files to scan is not a pass to announce -- it is nothing happening.
if [[ ${#STAGED[@]} -eq 0 ]]; then
  exit 0
fi

OFFENDERS="$(grep -l "$PATTERN" "${STAGED[@]}" 2>/dev/null || true)"

if [[ -n "$OFFENDERS" ]]; then
  echo "BLOCKED - Files contain assistant-tooling references!" >&2
  # -H because grep omits the filename when given exactly one file, and a
  # line number with no file is not a diagnosis.
  # shellcheck disable=SC2086 -- OFFENDERS is a newline-separated list.
  grep -Hn "$PATTERN" ${OFFENDERS} 2>/dev/null | head -10 >&2
  echo >&2
  echo "If one of these files must name the pattern in order to exclude it," >&2
  echo "add it to ALLOWLIST in scripts/scan-blocked-references.sh and to" >&2
  echo "_CONTENT_SCAN_ALLOWLIST in tests/unit/test_ci_config_drift.py." >&2
  exit 1
fi
