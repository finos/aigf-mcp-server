#!/usr/bin/env bash
# Print the test coverage percentage from a coverage.py JSON report.
#
# This is the ONLY place a call site may read coverage.py's `percent_covered`.
# tests/unit/test_ci_config_drift.py forbids the read everywhere else, and that
# prohibition is the point: a call site that can obtain the number can enforce
# a floor with it. dependabot-security-validation.yml did exactly that -- it
# compared against 75.0 with `bc` while pyproject.toml declared 82 -- and the
# invariant written to prevent a second floor missed it, because that invariant
# forbids the `--cov-fail-under` *flag* rather than the policy. A call site with
# no access to the number has no number to compare.
#
# The floor is not this script's business. pytest-cov enforces
# [tool.coverage.report] fail_under from pyproject.toml and fails the run
# itself; this script only reports, and deliberately has no threshold argument.
#
# Usage:
#   scripts/coverage-summary.sh <coverage.json>
#
# Prints `<percentage>%` to stdout, or `unknown` if the report is missing or
# unreadable -- matching what the three call sites this replaces already did
# with `2>/dev/null || echo "unknown"`. Reporting is not a gate, so an absent
# report must not fail the step that only wanted to print a number.
#
# Environment:
#   PYTHON_BIN  Python interpreter to use. Passed straight through to
#               scripts/project-python.sh, which resolves and validates the
#               interpreter for every gate in this repository.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

REPORT="${1:-}"
if [[ -z "$REPORT" ]]; then
  echo "coverage-summary: usage: coverage-summary.sh <coverage.json>" >&2
  exit 2
fi

if [[ ! -f "$REPORT" ]]; then
  echo "coverage-summary: no report at $REPORT" >&2
  echo "unknown"
  exit 0
fi

# An unresolvable interpreter is an environment problem, not a coverage
# problem. Report it and print `unknown` rather than failing a step whose only
# job was to display a number.
if ! PYTHON_BIN="$("$ROOT_DIR/scripts/project-python.sh" --print-interpreter)"; then
  echo "coverage-summary: no usable project interpreter" >&2
  echo "unknown"
  exit 0
fi

"$PYTHON_BIN" - "$REPORT" <<'PY' || echo "unknown"
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    print(f"{json.load(handle)['totals']['percent_covered']:.1f}%")
PY
