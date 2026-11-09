#!/usr/bin/env bash
# Run a command with the interpreter this project declares.
#
# This is the ONLY place that answers "which Python runs a gate". Every
# language: system pre-commit hook, and every wrapper script that needs an
# interpreter, delegates here instead of naming one itself.
#
# .pre-commit-config.yaml opens by listing four incidents -- mypy at v1.17.1
# without fastmcp, pip-audit pinned twice, semgrep without setuptools, pylint
# at a weaker --fail-under. All four were one failure: a tool resolved from
# somewhere other than the single declared source. #40/#41/#43 fixed that for
# tool *configuration* by collapsing it into pyproject.toml. This fixes it for
# the *interpreter*, which is the other half of "which tool actually ran".
#
# Two defects made that concrete, and both are covered by the two halves below:
#
#   #56 Every hook entry invoked a bare `python`. macOS ships no `python`, and
#       pre-commit does not prepend a venv's bin/ to PATH even when invoked as
#       `venv/bin/python -m pre_commit`, so ruff, ruff-format, mypy, bandit,
#       pylint and detect-secrets all died with "Executable `python` not
#       found". `python3` is not the fix: on macOS that is /usr/bin/python3,
#       Python 3.9, holding none of this project's tools.
#
#   #89 Resolution fell through to bare system interpreters, so whichever
#       environment happened to exist won silently. The project venv sat at
#       fastmcp 2.14.5 against a declared >=3.4.7,<4 for six months and every
#       gate entered through it measured that environment without comment.
#
# Usage -- a drop-in replacement for `python`:
#   scripts/project-python.sh -m ruff check --force-exclude
#
# Or, for a shell script that then invokes the interpreter many times itself,
# resolve once and reuse -- the checks below run per invocation, so a script
# with a dozen tool calls should not pay for them a dozen times:
#   PYTHON_BIN="$(scripts/project-python.sh --print-interpreter)"
#
# Environment:
#   PYTHON_BIN                          Explicit interpreter. Honoured as given.
#   ALLOW_INSECURE_INTERPRETER_MISMATCH Set to 1 to downgrade a declared-vs-
#                                       installed mismatch from fatal to a
#                                       warning. Default off, per the
#                                       ALLOW_INSECURE_* convention -- an
#                                       escape hatch that defaults open is not
#                                       a gate.
#
# Diagnostics go to stderr. scripts/quality-check.sh captures the stdout of
# this family of scripts, and the caller's stdout must be the tool's stdout and
# nothing else.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENVIRONMENT_CHECK="$ROOT_DIR/scripts/project_environment.py"
PYPROJECT="$ROOT_DIR/pyproject.toml"

usable() {
  [[ -n "${1:-}" && -x "$1" ]] && "$1" -c "import sys" >/dev/null 2>&1
}

# Resolution is virtualenv-based on purpose, and there is deliberately no
# fallback to a bare system interpreter. A fallback is what let the wrong
# environment win without saying so: the candidate list this replaces ended in
# `python3.13 python3.12 python3.11 python3`, so a missing venv produced a
# silent downgrade rather than an error. Failing here is recoverable in one
# command; auditing the wrong environment is not detectable at all.
resolve_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "$PYTHON_BIN"
    return
  fi
  if [[ -x "$ROOT_DIR/venv/bin/python" ]]; then
    echo "$ROOT_DIR/venv/bin/python"
    return
  fi
  # An activated virtualenv other than the project's own. Second, not first:
  # the project's venv is what every script and document names, so it wins when
  # both exist.
  if [[ -n "${VIRTUAL_ENV:-}" && -x "$VIRTUAL_ENV/bin/python" ]]; then
    echo "$VIRTUAL_ENV/bin/python"
    return
  fi
  echo ""
}

RESOLVED="$(resolve_python)"

if [[ -z "$RESOLVED" ]]; then
  echo "project-python: no project virtualenv found." >&2
  echo "project-python: looked for \$PYTHON_BIN, $ROOT_DIR/venv/bin/python and \$VIRTUAL_ENV/bin/python." >&2
  echo "project-python: create one --" >&2
  echo "    python3.12 -m venv venv && venv/bin/pip install -e '.[security,dev,test]'" >&2
  exit 1
fi

if ! usable "$RESOLVED"; then
  echo "project-python: $RESOLVED is not an executable Python interpreter." >&2
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "project-python: it came from PYTHON_BIN, which is honoured as given --" \
         "failing beats silently substituting an interpreter you did not ask for." >&2
  fi
  exit 1
fi

# The check runs *in* the resolved interpreter, because the environment worth
# measuring is the one about to run the tool.
if ! "$RESOLVED" "$ENVIRONMENT_CHECK" --pyproject "$PYPROJECT"; then
  if [[ "${ALLOW_INSECURE_INTERPRETER_MISMATCH:-}" == "1" ]]; then
    echo "project-python: continuing anyway -- ALLOW_INSECURE_INTERPRETER_MISMATCH=1." >&2
    echo "project-python: whatever this gate reports describes the environment above, not the declared one." >&2
  else
    exit 1
  fi
fi

# --print-interpreter resolves and validates exactly as above, then hands the
# path back instead of running anything. Deliberately after the checks, so a
# caller cannot use it to obtain an interpreter this script would have refused.
if [[ "${1:-}" == "--print-interpreter" ]]; then
  if [[ $# -gt 1 ]]; then
    echo "project-python: --print-interpreter takes no further arguments." >&2
    exit 2
  fi
  echo "$RESOLVED"
  exit 0
fi

exec "$RESOLVED" "$@"
