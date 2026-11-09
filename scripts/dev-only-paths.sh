#!/usr/bin/env bash
# The one definition of "development-only path" this repository has.
#
# Sourced by scripts/go-live-gate.sh (Gate 1, which reads the index) and by
# scripts/scan-published-refs.sh (Gate 9, which reads the refs on a remote).
# Both gates answer the same question about different sets of files, so a
# second copy of this pattern would let them disagree about what they protect.
#
# This file necessarily contains the string the `scan-dev-only-references` hook
# greps for -- naming a thing is how you exclude it -- so it is listed in the
# ALLOWLIST of scripts/scan-blocked-references.sh and in
# _CONTENT_SCAN_ALLOWLIST in tests/unit/test_ci_config_drift.py.

# shellcheck disable=SC2034 -- consumed by the scripts that source this file.
readonly DEV_ONLY_PATTERN='^(\.claude/|skills/|venv/|\.venv/|\.cache/)'
