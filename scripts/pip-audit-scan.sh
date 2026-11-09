#!/usr/bin/env bash
# Run pip-audit with the suppression list declared in pyproject.toml.
#
# This is the ONLY place the declared policy becomes pip-audit flags. Every
# call site -- both GitHub workflows, ci-local.sh, ci-exact-simulation.sh,
# quality-check.sh, go-live-gate.sh and the pre-commit hook -- delegates here
# instead of restating `--ignore-vuln` inline, so the six copies that had
# already drifted apart cannot come back.
#
# Any arguments are passed straight through to pip-audit, so each caller keeps
# its own reporting flags (--format, --output, --local, ...).
#
# Environment:
#   PYTHON_BIN  Python interpreter to use. Passed straight through to
#               scripts/project-python.sh, which resolves and validates the
#               interpreter for every gate in this repository.
#
# This script used to carry its own candidate list, ending in
# `python3.13 python3.12 python3.11 python3`. That fallback is why #89
# happened: whichever environment existed won silently, so a project venv
# holding fastmcp 2.14.5 against a declared >=3.4.7,<4 was audited for six
# months without comment. Resolution now lives in exactly one place, and it
# refuses to run an interpreter that contradicts pyproject.toml.
#
# Diagnostics go to stderr: quality-check.sh captures this script's stdout.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_SCRIPT="$ROOT_DIR/scripts/pip_audit_policy.py"

# One resolution, reused for both the policy load and the audit itself, so the
# satisfaction check runs once per scan rather than once per invocation.
if ! PYTHON_BIN="$("$ROOT_DIR/scripts/project-python.sh" --print-interpreter)"; then
  echo "pip-audit-scan: refusing to audit -- no usable project interpreter." >&2
  exit 1
fi

# Validation happens here, before pip-audit runs. A policy that fails to load
# must abort the scan rather than silently degrade to "no suppressions": an
# audit that quietly ignores its own policy is not a gate.
if ! POLICY_FLAGS="$("$PYTHON_BIN" "$POLICY_SCRIPT" --pyproject "$ROOT_DIR/pyproject.toml" --print-flags)"; then
  echo "pip-audit-scan: refusing to audit with an invalid suppression policy" >&2
  exit 1
fi

IGNORE_FLAGS=()
while IFS= read -r flag; do
  [[ -n "$flag" ]] && IGNORE_FLAGS+=("$flag")
done <<<"$POLICY_FLAGS"

# ${arr[@]+"${arr[@]}"} keeps an empty array from tripping `set -u` on bash 3.2,
# which is what macOS still ships as /bin/bash. An empty list is the expected
# state: nothing suppressed, nothing passed.
# Two argv tokens per suppression: "--ignore-vuln" and the advisory id.
echo "pip-audit-scan: $(( ${#IGNORE_FLAGS[@]} / 2 )) suppression(s) from pyproject.toml" >&2

exec "$PYTHON_BIN" -m pip_audit \
  ${IGNORE_FLAGS[@]+"${IGNORE_FLAGS[@]}"} \
  "$@"
