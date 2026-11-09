"""Guards against CI-configuration drift.

A test that never executes is not coverage, a threshold that is always
overridden is not a gate, and a vulnerability suppression nobody re-reads is
not a decision. These tests assert twenty-one invariants:

1. Every directory holding tests is reachable from ``testpaths``, so a bare
   ``pytest`` runs exactly what CI runs.
2. Exactly one coverage floor exists, declared in ``pyproject.toml`` and never
   overridden by a ``--cov-fail-under`` flag at a call site.
3. No test file is parked behind a ``.disabled`` suffix where no runner can
   reach it.
4. Exactly one pip-audit suppression list exists, declared in ``pyproject.toml``
   and never restated as an inline ``--ignore-vuln`` flag at a call site.
5. Exactly one pre-commit configuration exists, so two setup scripts cannot
   install two different hook sets.
6. Exactly one type-checker configuration and one test-runner configuration
   exist, each is the one its tool actually resolves, and no call site
   restates a rule from either.
7. Every call site reaches semgrep through ``scripts/semgrep-isolated.sh``, so
   one pinned semgrep scans with one ruleset.
8. Exactly one pylint configuration exists, it is the one pylint actually
   resolves, and no call site restates its score gate.
9. CI really runs ``pre-commit run --all-files``, and every hook that runs a
   tool this project declares is a ``repo: local`` + ``language: system`` hook,
   so no hook can pin its own second copy of a tool.
10. No collected test file is incapable of failing: each contains at least one
    assertion, no test function returns a value instead of asserting, and no
    test swallows an exception into a ``return``.
11. CI really runs the live functional suite, and a pre-push hook runs it too.
12. Only ``scripts/coverage-summary.sh`` reads coverage.py's
    ``percent_covered``, and every call site that reports a percentage goes
    through it. Invariant 2 forbids the ``--cov-fail-under`` *flag*, so a call
    site that read the number itself could enforce a second floor with ``bc``
    and pass -- which one did, against 75, while ``pyproject.toml`` declared
    82. This closes that acquisition route; it does not close every route, and
    the test's own docstring says which.
13. The branch patterns that un-skip the Dependabot workflow's extra validation
    are the ones ``docs/development.md`` documents, in both directions. The hatch
    matched ``feature/security-*`` and three siblings, three documented
    nowhere, while the convention in use had moved to ``security/*``.
14. The Dependabot workflow's dependency gate can actually fail: its own jq
    filter, run against a report shaped like pip-audit's, must count a
    vulnerable dependency. It used to select on a ``severity`` key pip-audit
    never emits, so the gate deciding whether a dependency bump is safe could
    not fail on a vulnerable dependency.

15. Every thread a test joins with a timeout is constructed ``daemon=True``.
    A timed join declares the joining code willing to continue without the
    thread; a non-daemon thread makes that declaration false, because the
    interpreter still waits for it at exit. This one is a *static* assertion
    and says so in its own docstring: it pins the flag at the construction
    site, which no passing run can do, but it cannot observe interpreter exit
    and does not claim to.

16. The staged-filename guard reads the index and never the working tree, it
    excludes staged deletions so it cannot block its own remedy, and exactly
    one hook enforces that rule. While it walked the working tree it fired on
    vendored library files inside any virtualenv its hardcoded exclusion list
    did not happen to name, which is a guard the contributor cannot satisfy
    and therefore a guard everyone bypasses.

Effective configuration is read through pytest's, coverage's and mypy's own
APIs rather than by parsing ``pyproject.toml``, so these assertions describe
what the tools actually do, not what the file appears to say.

None of these invariants is phrased as a comparison between two configuration
files. Such a comparison reports success the moment one side is deleted or
emptied -- it cannot tell "both agree" apart from "there is nothing left to
disagree about". Each invariant instead names one source of truth and forbids
every other place from restating it.

The suppression-policy assertions are deliberately exercised against synthetic
in-memory documents as well as the real ``pyproject.toml``. The declared list
is currently empty, so a test that only inspected real data would pass without
ever running the rule it claims to enforce. The mypy flag scanner is exercised
the same way, in both directions: a synthetic command carrying a semantic flag
must be rejected, and one carrying only presentational flags must be accepted.
A scanner that found nothing anywhere would otherwise satisfy every
prohibition in this file.
17. The development-only path pattern is assigned in exactly one tracked
    file, ``scripts/dev-only-paths.sh``, so the gate that reads the index and
    the gate that reads a remote's refs cannot disagree about what they
    protect. This was implemented before it was listed here.
18. Every tool declared in the ``dev`` and ``security`` extras is invoked by a
    script, workflow or hook, imported as a library, is a PEP 561 stub, or is
    registered as pending a decision with the issue that owns it. ``safety``
    was declared, run by nothing, and pulled in ``nltk``; when that acquired an
    advisory with no fix, ``pip-audit`` failed every commit on every branch for
    a scanner nobody had ever run. The register is asserted to expire, so it
    cannot decay into an exclusion list.
19. Every machine-readable provenance field names this repository: the four
    ``[project.urls]`` entries published as the wheel's ``Project-URL``
    metadata, and the image's ``org.opencontainers.image.source`` label. All
    four URLs addressed ``finos/finos-mcp-server``, which has never existed, so
    every link PyPI rendered was dead while nothing in a local run, a test or a
    CI gate ever resolved one. Prose that names the upstream project this forks
    is out of scope, and the test says why.
20. Every configuration file names a tool that something declares or invokes,
    and every file under ``config/`` says which tool it configures or why it
    configures none. ``.gitleaks.toml`` configured a secret scanner that was
    never declared, never installed and never run, so this repository looked
    like it was covered by two secret scanners while one ran. Invariant 18 asks
    the same question of *declared* tools and could not see it, because a tool
    can be configured without being declared. Both lists are asserted against
    the tree, so neither outlives what it describes.
21. ``scripts/check-codeowners.sh`` runs in a CI job and in the go-live gate.
    Every ``.github/CODEOWNERS`` line named an unrelated account and the file
    was well-formed, so only GitHub's ``codeowners/errors`` endpoint can tell;
    a unit test can prove only that something asks it.
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
import yaml
from coverage import Coverage

pytestmark = pytest.mark.unit

# Call sites that may invoke pytest with coverage, or pip-audit. Scanned for
# flags that would override a single declared source of truth.
_INVOCATION_GLOBS = (
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "scripts/*.sh",
    ".pre-commit-config.yaml",
)

_COV_FAIL_UNDER_FLAG = "--cov-fail-under"

# coverage.py's own key inside coverage.json. The flag guard above forbids one
# *mechanism* for restating the floor; a call site that reads this key can
# enforce its own floor with `bc` and never mention the flag at all --
# dependabot-security-validation.yml did exactly that against 75.0. A call site
# that cannot obtain the number cannot compare it, so the read is what gets
# forbidden, not the spelling of any one comparison.
_COVERAGE_PERCENT_KEY = "percent_covered"

# The one wrapper allowed to read it, so the call sites that only ever wanted to
# print a percentage still can.
_COVERAGE_SUMMARY_WRAPPER = "scripts/coverage-summary.sh"

# Every call site that reports a coverage percentage. Frozen for the same
# reason as _PIP_AUDIT_CALL_SITES: the prohibition above passes over a file
# that no longer mentions coverage at all, so deleting the reporting instead of
# routing it through the wrapper would look identical to complying. Removing an
# entry here has to be a conscious edit.
_COVERAGE_SUMMARY_CALL_SITES = (
    ".github/workflows/dependabot-security-validation.yml",
    ".github/workflows/security-analysis.yml",
    "scripts/ci-exact-simulation.sh",
)

# The workflow whose extra validation a branch name can switch on, and the file
# that tells a contributor which name does it.
_SECURITY_BRANCH_WORKFLOW = ".github/workflows/dependabot-security-validation.yml"
_DEVELOPMENT_GUIDE = "docs/development.md"

# `[[ "${{ github.head_ref }}" == security/* ]]` -- the head-branch test that
# un-skips the scan job. Deliberately anchored on head_ref: the `branches:`
# filter under `on: pull_request` selects the *base* branch, so the four
# feature/* patterns that used to sit there matched nothing this repository
# opens and were not the hatch at all.
_HEAD_REF_PATTERN = re.compile(r'github\.head_ref\s*\}\}"\s*==\s*([A-Za-z0-9._/*-]+)')

# A branch glob as docs/development.md writes it, in backticks: `security/*`, and
# the older `feature/security-*` the hatch still honours.
_DOCUMENTED_BRANCH_PATTERN = re.compile(r"`([A-Za-z0-9._-]+/[A-Za-z0-9._*-]*\*)`")

_IGNORE_VULN_FLAG = "--ignore-vuln"

# The one wrapper every pip-audit call site must go through.
_PIP_AUDIT_WRAPPER = "scripts/pip-audit-scan.sh"

# Every call site that runs a dependency audit. Frozen deliberately: an empty
# or shrinking set would let "all call sites use the wrapper" pass vacuously,
# so removing an entry here has to be a conscious edit.
_PIP_AUDIT_CALL_SITES = (
    ".github/workflows/security-analysis.yml",
    ".github/workflows/dependabot-security-validation.yml",
    "scripts/ci-local.sh",
    "scripts/ci-exact-simulation.sh",
    "scripts/quality-check.sh",
    "scripts/go-live-gate.sh",
)

# The step whose job is to decide whether a dependency bump is safe to merge.
_PIP_AUDIT_GATE_STEP_ID = "pip-audit"

# `VULNS=$(jq '<filter>' report.json)` inside a workflow step.
_JQ_ASSIGNMENT = re.compile(r"(\w+)=\$\(jq\s+'([^']+)'")

# `if [ "$VULNS" -gt 0 ]; then` -- the shape every failing check in this step
# uses. A variable only matters if crossing its threshold reaches an `exit 1`.
_SHELL_THRESHOLD = 'if [ "${}" -gt 0 ]; then'

# One vulnerable dependency, one clean one, and one pip-audit could not audit,
# in the exact shape pip-audit 2.10.1 emits: pip_audit/_format/json.py writes
# {"id", "fix_versions"} per vulnerability and nothing else. There is no
# "severity" key, which is why a filter selecting on .severity counted zero
# forever. The skipped entry has no "vulns" key at all -- that is what `.vulns
# // []` in the workflow is for, not defensive padding.
_SYNTHETIC_AUDIT_REPORT = {
    "dependencies": [
        {
            "name": "vulnerable-package",
            "version": "1.0.0",
            "vulns": [{"id": "PYSEC-0000-1", "fix_versions": ["1.0.1"]}],
        },
        {"name": "clean-package", "version": "2.0.0", "vulns": []},
        {"name": "finos-mcp-server", "skip_reason": "Dependency not found on PyPI"},
    ],
    "fixes": [],
}

# A raw pip-audit invocation: `python -m pip_audit`, or a bare `pip-audit`
# followed by an actual option or a line continuation. Deliberately narrow so
# that merely *naming* the tool is not mistaken for running it -- this must not
# fire on `grep -q "pip-audit"`, on a banner like "pip-audit - Dependency
# Scanning" where the hyphen is punctuation, or on the wrapper's own path.
_RAW_PIP_AUDIT_INVOCATION = re.compile(
    r"""
      (?: -m \s+ pip_audit \b )
    | (?: (?:^|[\s;&|(]) pip-audit \s+ (?: --? [A-Za-z] | \\ ) )
    """,
    re.MULTILINE | re.VERBOSE,
)

# Both YAML and shell comment with "#", including inside a `run: |` block.
_COMMENT = re.compile(r"#.*$", re.MULTILINE)


# --- type-checker and test-runner configuration ----------------------------

# The single declared configuration for mypy, pytest, ruff and coverage alike.
_PYPROJECT = "pyproject.toml"

# Filenames mypy would resolve *before* pyproject.toml. Their mere existence
# silently demotes the declared configuration to dead text, which is what
# `.mypy.ini` did here: it disabled strict optional and every `disallow_*`
# rule while `[tool.mypy]` in pyproject.toml claimed `strict = true`.
_SHADOWING_MYPY_CONFIG_FILES = ("mypy.ini", ".mypy.ini", "setup.cfg")

# The same hazard for pytest. `pytest*.ini` is a glob rather than a literal:
# the file that actually shipped here was `pytest.fast.ini`, which is not a
# name pytest auto-discovers but is one a developer can be told to pass with
# `-c`, and which pytest then accepts while reading nothing out of it.
_SHADOWING_PYTEST_CONFIG_FILES = ("pytest*.ini", ".pytest.ini", "tox.ini", "setup.cfg")

# Read off mypy's own resolved Options, never off the file. Frozen so that
# weakening the declared configuration fails here rather than quietly
# shrinking what this test checks -- an assertion derived from whatever the
# config happens to say would agree with any config at all.
_REQUIRED_MYPY_STRICTNESS = (
    "check_untyped_defs",
    "disallow_any_generics",
    "disallow_incomplete_defs",
    "disallow_subclassing_any",
    "disallow_untyped_calls",
    "disallow_untyped_decorators",
    "disallow_untyped_defs",
    "extra_checks",
    "strict_equality",
    "strict_optional",
    "warn_redundant_casts",
    "warn_return_any",
    "warn_unused_ignores",
)

# Flags a call site may still pass: they change how results are *presented* or
# where a report is written, never which programs type-check. Everything else
# -- including `--config-file`, which would point mypy at a second source of
# truth -- is a rule, and rules live in _PYPROJECT.
_PRESENTATIONAL_MYPY_FLAGS = frozenset(
    {
        "--show-error-codes",
        "--show-error-context",
        "--txt-report",
        "--no-error-summary",
        "--pretty",
        "--version",
    }
)

# Every file that runs mypy. Frozen for the same reason as the pip-audit list:
# a scanner that discovers its own inputs reports success once it discovers
# nothing, so the set it must find is written down here.
_MYPY_CALL_SITES = (
    ".github/workflows/dependabot-security-validation.yml",
    ".github/workflows/security-analysis.yml",
    ".pre-commit-config.yaml",
    "scripts/ci-exact-simulation.sh",
    "scripts/ci-local.sh",
    "scripts/go-live-gate.sh",
    "scripts/quality-check.sh",
)

# `mypy` in command position: at a line start, or after whitespace or a shell
# metacharacter or an opening quote. Deliberately narrow, and case-sensitive,
# so that naming the tool is not mistaken for running it -- this must not fire
# on `"MyPy type checking"`, on a `("ruff" "mypy" "pylint")` tool list, or on
# the `security-reports/mypy-report` path, and `- id: mypy` in a pre-commit
# hook is matched only so the hook's own `args:` can be read separately.
_MYPY_INVOCATION = re.compile(r"""(?:^|[\s;&|("'])mypy(?:\s|$)""", re.MULTILINE)

_FLAG_TOKEN = re.compile(r"--[A-Za-z][A-Za-z0-9-]*")

# The presentational flags above that take a value, so the token after one is
# not read as a target.
_MYPY_FLAGS_WITH_A_VALUE = frozenset({"--txt-report"})

_SHELL_OPERATORS = frozenset({";", "&&", "||", "|", ")", ">", "2>&1"})

# What mypy checks, declared once as `files` in [tool.mypy]. Until #343 every
# call site named src/finos_mcp, so no test file was ever type-checked.
_DECLARED_MYPY_FILES = ("src/finos_mcp", "tests")


# --- semgrep -----------------------------------------------------------------

# The one wrapper every semgrep call site must go through. It pins the version
# once and builds an isolated venv, which is also what fixed the pre-commit
# hook: pre-commit's own py3.12 environment ships no setuptools, so semgrep's
# opentelemetry import chain died on `pkg_resources` before scanning anything.
_SEMGREP_WRAPPER = "scripts/semgrep-isolated.sh"

# Every file that runs semgrep. Frozen for the same reason as the pip-audit and
# mypy lists: a scanner that discovers its own inputs reports success once it
# discovers nothing.
_SEMGREP_CALL_SITES = (
    ".github/workflows/security-analysis.yml",
    ".github/workflows/dependabot-security-validation.yml",
    ".github/workflows/release.yml",
    ".pre-commit-config.yaml",
    "scripts/ci-exact-simulation.sh",
    "scripts/ci-local.sh",
)

# A raw semgrep invocation: `semgrep` in command position, or `-m semgrep`,
# *not* preceded by the wrapper path. Deliberately narrow so that naming the
# tool is not mistaken for running it -- this must not fire on the wrapper's own
# path, on "Running Semgrep static analysis...", on a semgrep-report.json path,
# or on a `("bandit" "semgrep")` tool list.
_RAW_SEMGREP_INVOCATION = re.compile(
    r"""
      (?: -m \s+ semgrep \b )
    | (?: (?<! [-/\w] ) semgrep \s+ (?: --? [A-Za-z] | \\ ) )
    """,
    re.MULTILINE | re.VERBOSE,
)


# --- pylint ------------------------------------------------------------------

# Filenames pylint resolves *before* pyproject.toml. Their mere existence
# silently demotes the declared configuration to dead text, exactly as
# `.mypy.ini` did for mypy. The deleted `.pylintrc` was 650 lines that changed
# three settings and carried `suggestion-mode`, removed in pylint 4, so every
# run emitted `E0015: Unrecognized option found` into the JSON report CI parses
# while still exiting 0.
_SHADOWING_PYLINT_CONFIG_FILES = ("pylintrc", ".pylintrc", "tox.ini", "setup.cfg")

# The score gate, declared once in [tool.pylint.main]. Frozen here rather than
# read back out of pyproject.toml: an expectation derived from the file under
# test agrees with whatever that file happens to say.
_DECLARED_PYLINT_FAIL_UNDER = 8.5

# Flags that would move a pylint rule back to a call site. --fail-under was at
# three of them, all at 8.0 -- a weaker gate than the declared 8.5 -- and
# --rcfile would point pylint at a second source of truth.
_FORBIDDEN_PYLINT_FLAGS = ("--fail-under", "--rcfile")

_PYLINT_INVOCATION = re.compile(r"""(?:^|[\s;&|("'])pylint(?:\s|$)""", re.MULTILINE)


# --- pre-commit --------------------------------------------------------------

_PRE_COMMIT_CONFIG = ".pre-commit-config.yaml"

# The workflow that must run the hooks, and the command it must run.
_PRE_COMMIT_WORKFLOW = ".github/workflows/security-analysis.yml"
_PRE_COMMIT_COMMAND = "pre_commit run --all-files"

# The functional gate: each opt-in suite, and the flag without which it skips
# itself. Both are needed -- a job that runs the file without setting the flag
# reports a pass having executed nothing. The auth HTTP suite is here because
# nothing ran it, and it failed unnoticed from #323 to #341 (#342).
_GATED_SUITES = (
    ("tests/integration/test_live_mcp_server.py", "FINOS_RUN_LIVE_MCP_TEST"),
    ("tests/integration/test_auth_http_transport.py", "FINOS_RUN_AUTH_HTTP_TEST"),
)

# Hooks that run a tool this project already declares. Each must be a
# `repo: local` + `language: system` hook, so it runs the project's copy with
# the project's configuration rather than a second version pinned by a `rev`.
# Frozen, and checked for presence as well as for locality: a set derived from
# the config would shrink to nothing the moment someone deleted a hook, and
# "every hook in an empty set is local" is true of any configuration at all.
_PROJECT_OWNED_HOOK_IDS = frozenset(
    {
        "bandit",
        "detect-secrets",
        "functional-gate",
        "mypy",
        "pip-audit-scan",
        "pylint",
        "ruff",
        "ruff-format",
        "semgrep",
    }
)

# The one shim every gate resolves its interpreter through.
_PROJECT_PYTHON_SHIM = "scripts/project-python.sh"

# Project-owned hooks that reach the interpreter through their own wrapper
# instead of naming it. Both wrappers resolve via the shim themselves, so the
# rule still holds one level down.
_WRAPPER_DELEGATING_HOOK_IDS = frozenset({"pip-audit-scan", "semgrep"})

# A bare interpreter at the head of a command: `python`, `python3`, `python3.12`.
# Deliberately narrow -- it must not fire on the shim's own filename, which ends
# in `-python.sh`, nor on prose that merely names an interpreter.
_BARE_INTERPRETER = re.compile(
    r"""(?:^|[\s;&|(]) python (?:3(?:\.\d+)?)? (?=\s|$)""",
    re.VERBOSE,
)

# Shell entry points that resolve an interpreter for a whole run. Frozen for the
# same reason as _PIP_AUDIT_CALL_SITES: a set derived from the tree would shrink
# to nothing and pass vacuously.
_INTERPRETER_CALL_SITES = (
    "scripts/ci-exact-simulation.sh",
    "scripts/ci-local.sh",
    "scripts/go-live-gate.sh",
    "scripts/pip-audit-scan.sh",
)

# A workflow step that installs this project must create the virtualenv first.
# The shim is virtualenv-based, so a runner without one has nothing to resolve.
_PROJECT_INSTALL = "pip install -e ."
_VENV_CREATION = "python -m venv venv"

_FILENAME_GUARD_ID = "block-dev-only-files"
_CONTENT_SCAN_ID = "scan-dev-only-references"

# The word the filename guard refuses, as scripts/scan-blocked-filenames.sh
# spells it. Stated here, not derived from the hook id, so renaming the hook
# cannot change what this module looks for.
_FILENAME_GUARD_TOKEN = "claude"

# The script the filename guard delegates to. The guard used to walk the working
# tree with `find`, skipping a hardcoded list of five directory names; a
# virtualenv named anything else still matched the vendored mcp/cli/claude.py
# that every install of the mcp package ships, and reported a CRITICAL SECURITY
# failure on a file the contributor did not write and cannot delete (#84, and
# #56 before it). An enumerated exclusion list can never be complete, so the
# guard reads the index instead, where no ignored path can ever appear.
_BLOCKED_FILENAME_SCANNER = "scripts/scan-blocked-filenames.sh"

# Anything that reaches beyond the index and back into the working tree. `find`
# is how the defect above was actually spelled; `ls-files` without `--cached`
# and a bare glob are the two nearby ways to reintroduce it.
_WORKING_TREE_WALK = re.compile(r"\bfind\b|\bls-files\b")

# The script the content scan delegates to, and the exact set of files it may
# skip. Excluding a thing means naming it, so each of these necessarily contains
# the string the scan greps for. Frozen: a carve-out that grows silently is an
# exemption nobody is checking.
_BLOCKED_REFERENCE_SCANNER = "scripts/scan-blocked-references.sh"
_CONTENT_SCAN_ALLOWLIST = frozenset(
    {
        ".gitignore",
        ".pre-commit-config.yaml",
        "scripts/dev-only-paths.sh",
        _BLOCKED_REFERENCE_SCANNER,
    }
)

# A trailing backslash continues a shell command onto the next line, inside a
# YAML `run: |` block just as in a .sh file.
_LINE_CONTINUATION = "\\"


def _executable_content(path: Path) -> str:
    """Return the file's content with comments stripped.

    Prose that merely names the flag (including the comments explaining why it
    must not appear) is not an invocation, so it must not trip the guard.
    """
    return _COMMENT.sub("", path.read_text(encoding="utf-8"))


def _reads_coverage_percentage(path: Path) -> bool:
    """Whether ``path`` obtains the coverage percentage for itself.

    Comments are stripped first, so the notes explaining why a call site must
    not read the key -- including the ones this change added to two workflows
    -- are prose, not an invocation.
    """
    return _COVERAGE_PERCENT_KEY in _executable_content(path)


def _repo_root(pytestconfig: pytest.Config) -> Path:
    """Return the repository root as pytest resolved it."""
    return Path(pytestconfig.rootpath)


def _directories_containing_tests(tests_dir: Path) -> set[Path]:
    """Return every directory under ``tests/`` that holds a ``test_*.py`` file."""
    return {test_file.parent for test_file in tests_dir.rglob("test_*.py")}


def test_testpaths_reaches_every_directory_containing_tests(
    pytestconfig: pytest.Config,
) -> None:
    """A bare ``pytest`` must collect every test directory in the repo.

    ``tests/security/`` sat outside ``testpaths`` for the whole life of the
    suite: it ran in CI only because every CI call passed an explicit
    ``pytest tests/``. A developer running ``pytest`` saw green while the
    entire security suite was skipped.
    """
    root = _repo_root(pytestconfig)
    testpaths = [root / entry for entry in pytestconfig.getini("testpaths")]
    assert testpaths, "testpaths must be declared so bare pytest matches CI"

    unreachable = sorted(
        directory.relative_to(root).as_posix()
        for directory in _directories_containing_tests(root / "tests")
        if not any(
            directory == testpath or testpath in directory.parents
            for testpath in testpaths
        )
    )

    assert not unreachable, (
        "These directories hold tests that a bare `pytest` never collects: "
        f"{unreachable}. Add them to testpaths in pyproject.toml."
    )


def test_declared_coverage_floor_is_the_effective_one(
    pytestconfig: pytest.Config,
) -> None:
    """Coverage's effective ``fail_under`` must come from ``pyproject.toml``."""
    root = _repo_root(pytestconfig)
    config = Coverage(config_file=str(root / "pyproject.toml")).config

    assert config.fail_under > 0, (
        "pyproject.toml must declare [tool.coverage.report] fail_under "
        "as the single source of truth for the coverage gate"
    )


def test_no_call_site_overrides_the_coverage_floor(
    pytestconfig: pytest.Config,
) -> None:
    """No workflow or script may pass ``--cov-fail-under``.

    Six call sites each carried their own number (65, 65, 65, 65, 75) while
    ``pyproject.toml`` declared a seventh (75) that nothing honoured. A flag at
    a call site silently overrides the declared floor, so the only way to keep
    one number meaningful is to let no call site restate it.
    """
    root = _repo_root(pytestconfig)

    overrides = sorted(
        path.relative_to(root).as_posix()
        for glob in _INVOCATION_GLOBS
        for path in root.glob(glob)
        if _COV_FAIL_UNDER_FLAG in _executable_content(path)
    )

    assert not overrides, (
        "These call sites override the coverage floor declared in "
        f"pyproject.toml: {overrides}. Remove the --cov-fail-under flag so the "
        "declared value is the enforced value."
    )


# The block this guard was written to catch, exactly as it stood at
# dependabot-security-validation.yml:305-317 before it was deleted. Kept here so
# the negative control survives the specimen's removal: once the workflow is
# clean there is nothing left in the tree to prove the guard fires, and a
# reconstructed-from-memory approximation is not the same evidence.
#
# Note which line does the work. The `bc` comparison alone -- line :313 by
# itself -- contains no forbidden token and passes this guard; it is inert
# without the acquisition above it, which is what gets caught.
_DELETED_SECOND_FLOOR = """\
if [ -f "dependabot-coverage-reports/coverage.json" ]; then
  COVERAGE_NUM=$(python -c "import json; \
    print(json.load(open('cov.json'))['totals']['percent_covered'])")
  if (( $(echo "$COVERAGE_NUM < 75.0" | bc -l) )); then
    echo "coverage below required 75%"
    exit 1
  fi
fi
"""


def test_no_call_site_reads_the_coverage_percentage(
    pytestconfig: pytest.Config,
) -> None:
    """Only the summary wrapper may read ``percent_covered``.

    The flag guard above is keyed on a mechanism, so it passed while
    ``dependabot-security-validation.yml`` enforced a second floor of 75 with a
    ``bc`` comparison off ``coverage.json``. This closes that route.

    It does not close every route, and the difference is worth stating rather
    than discovering. A call site that obtains the percentage some other way --
    ``coverage report --format=total``, ``percent_covered_display``, parsing
    pytest's own ``TOTAL`` line -- can still compare it and ``exit 1``, and this
    guard will pass. Measured: a ``coverage report --format=total`` floor passes
    every invariant in this file. What is guarded is the one acquisition path
    that a call site has actually used, not the policy in general; closing the
    policy would mean forbidding call sites from obtaining coverage at all.
    """
    root = _repo_root(pytestconfig)

    readers = sorted(
        path.relative_to(root).as_posix()
        for glob in _INVOCATION_GLOBS
        for path in root.glob(glob)
        if path.relative_to(root).as_posix() != _COVERAGE_SUMMARY_WRAPPER
        and _reads_coverage_percentage(path)
    )

    assert not readers, (
        f"These call sites read {_COVERAGE_PERCENT_KEY} directly: {readers}. "
        f"Call {_COVERAGE_SUMMARY_WRAPPER} instead -- a call site that can read "
        "the coverage percentage can enforce a second floor with it, which is "
        "what pyproject.toml's fail_under exists to prevent."
    )


def test_every_coverage_reporting_call_site_uses_the_summary_wrapper(
    pytestconfig: pytest.Config,
) -> None:
    """Each reporting call site must delegate to the summary wrapper.

    The prohibition above is satisfied just as well by a call site that stops
    reporting coverage entirely, so on its own it cannot tell compliance from
    deletion. Naming the call sites is what makes the wrapper load-bearing --
    and the list is checked for presence first, because "every call site in an
    empty set uses the wrapper" is true of any repository at all.
    """
    root = _repo_root(pytestconfig)

    absent = sorted(
        site for site in _COVERAGE_SUMMARY_CALL_SITES if not (root / site).is_file()
    )
    assert not absent, (
        f"These declared coverage-reporting call sites do not exist: {absent}. "
        "Remove them from _COVERAGE_SUMMARY_CALL_SITES deliberately, or this "
        "check measures nothing."
    )

    assert (root / _COVERAGE_SUMMARY_WRAPPER).is_file(), (
        f"{_COVERAGE_SUMMARY_WRAPPER} must exist: it is the only reader of "
        f"{_COVERAGE_PERCENT_KEY} the drift guard permits."
    )

    offenders = sorted(
        site
        for site in _COVERAGE_SUMMARY_CALL_SITES
        if _COVERAGE_SUMMARY_WRAPPER not in _executable_content(root / site)
    )
    assert not offenders, (
        f"These call sites report coverage without going through "
        f"{_COVERAGE_SUMMARY_WRAPPER}: {offenders}. One place reads the "
        "percentage, and it is the place that cannot enforce a floor with it."
    )


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        ('COVERAGE=$(python -c "...percent_covered...")\n', True),
        ("# never read percent_covered at a call site\n", False),
        ('echo "coverage reported by the wrapper"\n', False),
        ("  # percent_covered\n  jq .totals.percent_covered cov.json\n", True),
        (_DELETED_SECOND_FLOOR, True),
    ],
    ids=[
        "executable",
        "comment-only",
        "unrelated",
        "comment-and-executable",
        "the-deleted-second-floor",
    ],
)
def test_coverage_reader_scanner_reads_synthetic_content(
    tmp_path: Path, document: str, expected: bool
) -> None:
    """The scanner must separate a real read from prose naming the key.

    Both workflows now carry comments explaining why the read is forbidden. A
    scanner that fired on those would have to be silenced with an allowlist,
    and an allowlist is where a real violation eventually hides.
    """
    probe = tmp_path / "call-site.sh"
    probe.write_text(document, encoding="utf-8")

    assert _reads_coverage_percentage(probe) is expected


def test_security_branch_hatch_matches_the_documented_convention(
    pytestconfig: pytest.Config,
) -> None:
    """The branch names that trigger extra validation must be the documented ones.

    The hatch matched ``feature/security-*`` and three siblings while the
    convention in use had moved to ``security/*``: PR #88 replaced a tokenized
    CI runner with a secret-free wrapper -- a genuine security change -- and
    the extra validation silently skipped, because the branch was named
    ``security/secret-free-token-wrapper``. Three of the four patterns were not
    documented anywhere at all, so nobody could have got it right from the
    file. A hatch a contributor cannot predict is a hatch that fires by luck.
    """
    root = _repo_root(pytestconfig)

    workflow = (root / _SECURITY_BRANCH_WORKFLOW).read_text(encoding="utf-8")
    matched = set(_HEAD_REF_PATTERN.findall(workflow))
    assert matched, (
        f"No head_ref branch test found in {_SECURITY_BRANCH_WORKFLOW}, so this "
        "check measures nothing."
    )

    guidance = (root / _DEVELOPMENT_GUIDE).read_text(encoding="utf-8")
    section = guidance.split("## Working on this repository", 1)
    assert len(section) == 2, (
        f"{_DEVELOPMENT_GUIDE} no longer has a 'Working on this repository' section, "
        "which is where the branch convention is documented."
    )
    documented = set(_DOCUMENTED_BRANCH_PATTERN.findall(section[1]))

    assert matched == documented, (
        f"{_SECURITY_BRANCH_WORKFLOW} runs its extra validation for {sorted(matched)} "
        f"while {_DEVELOPMENT_GUIDE} documents {sorted(documented)}. Undocumented: "
        f"{sorted(matched - documented)}; documented but never matched: "
        f"{sorted(documented - matched)}. A contributor picks a branch name from "
        "the guidance, so the two have to say the same thing."
    )


def test_no_test_files_are_parked_behind_a_disabled_suffix(
    pytestconfig: pytest.Config,
) -> None:
    """``.py.disabled`` files are invisible to every runner and to review."""
    root = _repo_root(pytestconfig)

    parked = sorted(
        path.relative_to(root).as_posix()
        for path in (root / "tests").rglob("*.py.disabled")
    )

    assert not parked, (
        f"These test files can never run: {parked}. Restore them to a working "
        "state or delete them; a permanently disabled test is not coverage."
    )


# ---------------------------------------------------------------------------
# pip-audit suppression policy
# ---------------------------------------------------------------------------


def _load_policy_module(root: Path) -> ModuleType:
    """Import ``scripts/pip_audit_policy.py`` by path.

    ``scripts/`` is build tooling, not a package: it is deliberately outside
    ``src/`` so it never ships in the wheel, which means it cannot be imported
    by name.
    """
    module_path = root / "scripts" / "pip_audit_policy.py"
    spec = importlib.util.spec_from_file_location("pip_audit_policy", module_path)
    assert spec is not None and spec.loader is not None, (
        f"{module_path} must exist: it is the single implementation of the "
        "suppression policy that every call site delegates to"
    )
    module = importlib.util.module_from_spec(spec)
    # @dataclass resolves its class's module through sys.modules; without this
    # registration it finds None there and fails while building Suppression.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def policy_module(pytestconfig: pytest.Config) -> ModuleType:
    """The single implementation of the pip-audit suppression policy."""
    return _load_policy_module(_repo_root(pytestconfig))


def _invocation_files(root: Path) -> list[Path]:
    """Every file that may invoke a CI tool, de-duplicated and ordered."""
    return sorted(
        {path for glob in _INVOCATION_GLOBS for path in root.glob(glob)},
        key=lambda path: path.as_posix(),
    )


def test_no_call_site_passes_ignore_vuln_inline(pytestconfig: pytest.Config) -> None:
    """No workflow, script, or hook config may restate the suppression list.

    Six call sites each carried their own ``--ignore-vuln`` flags and had
    already drifted: one of them suppressed ``PYSEC-2022-42969`` that no other
    site knew about, and documented it nowhere. An inline flag is invisible to
    the declared policy, so the only way to keep one list meaningful is to let
    no call site restate it.
    """
    root = _repo_root(pytestconfig)

    inline = sorted(
        path.relative_to(root).as_posix()
        for path in _invocation_files(root)
        if _IGNORE_VULN_FLAG in _executable_content(path)
    )

    assert not inline, (
        "These call sites pass --ignore-vuln inline instead of deriving it "
        f"from [tool.finos.pip-audit] in pyproject.toml: {inline}. Declare the "
        f"suppression there and run the audit through {_PIP_AUDIT_WRAPPER}."
    )


def test_every_pip_audit_call_site_uses_the_wrapper(
    pytestconfig: pytest.Config,
) -> None:
    """Each known audit call site must delegate to the one wrapper.

    Asserted against a frozen list rather than against whatever the tree
    happens to contain: a discovery-only check would report success after the
    last call site was deleted.
    """
    root = _repo_root(pytestconfig)

    assert (root / _PIP_AUDIT_WRAPPER).is_file(), (
        f"{_PIP_AUDIT_WRAPPER} must exist: it is the only place the declared "
        "suppression list is turned into pip-audit flags"
    )

    missing = sorted(
        call_site
        for call_site in _PIP_AUDIT_CALL_SITES
        if not (root / call_site).is_file()
        or _PIP_AUDIT_WRAPPER not in _executable_content(root / call_site)
    )

    assert not missing, (
        f"These call sites do not run the audit through {_PIP_AUDIT_WRAPPER}: "
        f"{missing}. Every audit must derive its flags from the same policy."
    )


def test_no_call_site_invokes_pip_audit_directly(
    pytestconfig: pytest.Config,
) -> None:
    """Only the wrapper may invoke pip-audit itself.

    Catches a *new* call site added outside the frozen list above: it would
    bypass the policy without ever tripping the inline-flag prohibition,
    because passing no ``--ignore-vuln`` at all is its own kind of drift.
    """
    root = _repo_root(pytestconfig)
    wrapper = root / _PIP_AUDIT_WRAPPER

    direct = sorted(
        path.relative_to(root).as_posix()
        for path in _invocation_files(root)
        if path != wrapper
        and _RAW_PIP_AUDIT_INVOCATION.search(_executable_content(path))
    )

    assert not direct, (
        f"These files invoke pip-audit directly instead of via "
        f"{_PIP_AUDIT_WRAPPER}: {direct}. A direct invocation silently opts out "
        "of the declared suppression policy."
    )


def _gate_step_script(workflow: Path, step_id: str) -> str:
    """Return the shell body of the step with ``step_id`` in ``workflow``."""
    document = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    for job in (document.get("jobs") or {}).values():
        for step in job.get("steps", []) or []:
            if isinstance(step, dict) and step.get("id") == step_id:
                return str(step.get("run", ""))
    return ""


def _failing_jq_filters(script: str) -> dict[str, str]:
    """Return the jq filters whose value can reach an ``exit 1`` in ``script``.

    A filter bound to a variable that is only ever printed cannot fail the
    build; only the ones guarding a threshold decide whether a vulnerable
    dependency merges.

    Bounded to the block's own ``fi``. A fixed character window instead of the
    block reached past ``SKIPPED``'s reporting branch into the ``exit 1`` of the
    branch after it, so a filter that only prints counted as one that fails --
    and the whole check then passed on the wrong filter while the real gate was
    broken.
    """
    lines = script.splitlines()
    failing = {}
    for name, jq_filter in _JQ_ASSIGNMENT.findall(script):
        threshold = _SHELL_THRESHOLD.format(name)
        for index, line in enumerate(lines):
            if threshold not in line:
                continue
            indent = len(line) - len(line.lstrip())
            for body in lines[index + 1 :]:
                stripped = body.strip()
                if stripped == "fi" and len(body) - len(body.lstrip()) == indent:
                    break
                if stripped == "exit 1":
                    failing[name] = jq_filter
                    break
    return failing


_REPORTS_THEN_FAILS = """\
COUNT=$(jq '[.a] | length' r.json)
NOTE=$(jq '[.b] | length' r.json)
if [ "$NOTE" -gt 0 ]; then
  jq -r '.b' r.json
fi

if [ "$COUNT" -gt 0 ]; then
  echo "bad"
  exit 1
fi
"""


def test_failing_filter_scanner_reads_a_synthetic_step() -> None:
    """Only the filter guarding its own ``exit 1`` counts as able to fail.

    ``NOTE`` reports and returns; ``COUNT`` fails. A scanner that cannot tell
    them apart reports the gate as healthy whenever anything at all is
    non-zero, which is how the first version of this check passed against a
    deliberately reintroduced bug.
    """
    assert _failing_jq_filters(_REPORTS_THEN_FAILS) == {"COUNT": "[.a] | length"}


def test_pip_audit_gate_can_actually_fail(
    pytestconfig: pytest.Config, tmp_path: Path
) -> None:
    """A vulnerable dependency must trip this step's own failing filter.

    The filter used to select ``.severity == "HIGH" or .severity == "CRITICAL"``
    on each vulnerability. ``pip_audit/_format/json.py`` emits ``id`` and
    ``fix_versions`` and never a ``severity``, so the count was zero for every
    input that has ever existed -- and the other branch printed a warning
    without failing. A dependency-vulnerability gate, in the workflow that
    exists for dependency PRs, that could not fail on a dependency
    vulnerability.

    Run rather than read: the defect was invisible to every lexical check
    because the expression was well-formed. Only feeding it a report proves it
    counts.
    """
    root = _repo_root(pytestconfig)
    jq = shutil.which("jq")
    assert jq, (
        "jq is required: this check runs the workflow's own filter, and "
        "skipping it would leave a gate whose failing branch nothing exercises."
    )

    script = _gate_step_script(
        root / _SECURITY_BRANCH_WORKFLOW, _PIP_AUDIT_GATE_STEP_ID
    )
    assert script, (
        f"No step with id '{_PIP_AUDIT_GATE_STEP_ID}' in "
        f"{_SECURITY_BRANCH_WORKFLOW}, so this check measures nothing."
    )

    filters = _failing_jq_filters(script)
    assert filters, (
        f"No jq filter in '{_PIP_AUDIT_GATE_STEP_ID}' guards an exit 1, so the "
        "step cannot fail on a vulnerability at all."
    )

    report = tmp_path / "pip-audit-report.json"
    report.write_text(json.dumps(_SYNTHETIC_AUDIT_REPORT), encoding="utf-8")

    counts = {}
    for name, jq_filter in filters.items():
        completed = subprocess.run(
            [jq, jq_filter, str(report)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, (
            f"{name}'s filter errored on a well-formed pip-audit report: "
            f"{completed.stderr.strip()}. The skipped entry carries no 'vulns' "
            "key, so the filter must tolerate its absence."
        )
        counts[name] = int(completed.stdout.strip() or 0)

    assert any(count > 0 for count in counts.values()), (
        "No failing check in this step counts the vulnerable dependency in a "
        f"real-shaped pip-audit report: {counts}. Every filter that can reach "
        "exit 1 returned zero, so the gate passes a PR carrying a known "
        "vulnerability. Check the filter against the keys pip-audit actually "
        "emits -- 'id' and 'fix_versions', never 'severity'."
    )


def test_declared_suppression_policy_is_valid_today(
    pytestconfig: pytest.Config, policy_module: ModuleType
) -> None:
    """The real ``pyproject.toml`` policy must satisfy its own rules.

    This is the live-data check. It is paired with the synthetic cases below
    because the declared list is currently empty, and an empty list satisfies
    every rule without exercising any of them.
    """
    root = _repo_root(pytestconfig)
    suppressions = policy_module.load_policy(
        root / "pyproject.toml", today=date.today()
    )

    assert isinstance(suppressions, list)


@pytest.mark.parametrize(
    ("entry", "expected_message"),
    [
        pytest.param("{}", "id", id="missing-id"),
        pytest.param(
            '{ reason = "r", review_by = "2099-01-01" }', "id", id="no-id-key"
        ),
        pytest.param(
            '{ id = "GHSA-aaaa-bbbb-cccc", review_by = "2099-01-01" }',
            "reason",
            id="missing-reason",
        ),
        pytest.param(
            '{ id = "GHSA-aaaa-bbbb-cccc", reason = "   ", review_by = "2099-01-01" }',
            "reason",
            id="blank-reason",
        ),
        pytest.param(
            '{ id = "GHSA-aaaa-bbbb-cccc", reason = "r" }',
            "review_by",
            id="missing-review-by",
        ),
        pytest.param(
            '{ id = "GHSA-aaaa-bbbb-cccc", reason = "r", review_by = "soon" }',
            "review_by",
            id="malformed-review-by",
        ),
    ],
)
def test_suppression_entries_require_id_reason_and_review_by(
    policy_module: ModuleType, entry: str, expected_message: str
) -> None:
    """Every suppression must carry an id, a rationale, and a review date.

    Five of the six call sites carried the same flags with no explanation at
    all, so a reviewer could not tell whether a suppression was still
    justified. Rationale is now structurally required.
    """
    document = f"[tool.finos.pip-audit]\nignore = [\n  {entry},\n]\n"

    with pytest.raises(policy_module.PolicyError) as excinfo:
        policy_module.parse_policy(document, today=date(2026, 8, 16))

    assert expected_message in str(excinfo.value)


def test_expired_review_by_is_rejected(policy_module: ModuleType) -> None:
    """A suppression past its review date must fail the build.

    The protobuf suppression carried ``REVIEW-BY: 2026-04-01`` and was still
    in place on 2026-08-16 -- four and a half months after it should have been
    re-read, and months after the advisory was actually fixed upstream. A date
    nothing enforces is a comment, not a control.
    """
    document = (
        "[tool.finos.pip-audit]\n"
        "ignore = [\n"
        '  { id = "GHSA-7gcm-g887-7qv7", reason = "r", review_by = "2026-04-01" },\n'
        "]\n"
    )

    with pytest.raises(policy_module.PolicyError) as excinfo:
        policy_module.parse_policy(document, today=date(2026, 8, 16))

    message = str(excinfo.value)
    assert "GHSA-7gcm-g887-7qv7" in message
    assert "2026-04-01" in message


def test_unexpired_suppression_is_accepted_and_becomes_flags(
    policy_module: ModuleType,
) -> None:
    """Positive control: a well-formed, in-date entry survives and is emitted.

    Without this, every assertion above would be satisfied by a parser that
    rejected absolutely everything.
    """
    document = (
        "[tool.finos.pip-audit]\n"
        "ignore = [\n"
        '  { id = "GHSA-aaaa-bbbb-cccc", reason = "no fix yet",'
        ' review_by = "2026-12-01" },\n'
        "]\n"
    )

    suppressions = policy_module.parse_policy(document, today=date(2026, 8, 16))

    assert [item.id for item in suppressions] == ["GHSA-aaaa-bbbb-cccc"]
    assert policy_module.ignore_flags(suppressions) == [
        "--ignore-vuln",
        "GHSA-aaaa-bbbb-cccc",
    ]


def test_empty_policy_emits_no_flags(policy_module: ModuleType) -> None:
    """The current, correct state: nothing suppressed, nothing passed."""
    document = "[tool.finos.pip-audit]\nignore = []\n"

    suppressions = policy_module.parse_policy(document, today=date(2026, 8, 16))

    assert suppressions == []
    assert policy_module.ignore_flags(suppressions) == []


def test_duplicate_suppression_ids_are_rejected(policy_module: ModuleType) -> None:
    """Two entries for one advisory mean two rationales that can disagree."""
    entry = '{{ id = "GHSA-aaaa-bbbb-cccc", reason = "{0}", review_by = "2026-12-01" }}'
    document = (
        "[tool.finos.pip-audit]\n"
        "ignore = [\n"
        f"  {entry.format('first')},\n"
        f"  {entry.format('second')},\n"
        "]\n"
    )

    with pytest.raises(policy_module.PolicyError) as excinfo:
        policy_module.parse_policy(document, today=date(2026, 8, 16))

    assert "GHSA-aaaa-bbbb-cccc" in str(excinfo.value)


# ---------------------------------------------------------------------------
# pre-commit configuration
# ---------------------------------------------------------------------------


def test_only_one_pre_commit_config_exists(pytestconfig: pytest.Config) -> None:
    """Two pre-commit configs meant two developers ran two different gates.

    ``scripts/dev-setup.sh`` installed ``config/ci/pre-commit-config.yaml``
    while ``scripts/dev-quick-setup.sh`` installed the root
    ``.pre-commit-config.yaml``. They had drifted apart on the pip-audit hook
    rev (v2.7.3 vs v2.9.0), ruff (v0.6.8 vs v0.12.11), mypy (v1.11.2 vs
    v1.17.1) and more. One file makes that drift structurally impossible.
    """
    root = _repo_root(pytestconfig)

    assert (root / ".pre-commit-config.yaml").is_file(), (
        "the root .pre-commit-config.yaml is the single hook configuration"
    )

    duplicates = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*pre-commit-config.y*ml")
        if path != root / ".pre-commit-config.yaml"
        and ".git" not in path.parts
        and "venv" not in path.parts
    )

    assert not duplicates, (
        f"These duplicate pre-commit configurations must not exist: "
        f"{duplicates}. Point every setup script at .pre-commit-config.yaml."
    )


# ---------------------------------------------------------------------------
# type-checker configuration
# ---------------------------------------------------------------------------


def _mypy_commands(text: str) -> list[str]:
    """Every mypy command line in ``text``, continuation lines joined."""
    lines = text.splitlines()
    commands: list[str] = []

    for index, line in enumerate(lines):
        if not _MYPY_INVOCATION.search(line):
            continue
        cursor = index
        command = [line]
        while lines[cursor].rstrip().endswith(_LINE_CONTINUATION) and cursor + 1 < len(
            lines
        ):
            cursor += 1
            command.append(lines[cursor])
        commands.append(" ".join(command))

    return commands


def _mypy_flags_in_command_lines(text: str) -> set[str]:
    """Return every flag passed on a mypy command line in ``text``.

    Scoped to the command rather than to the whole file on purpose. These same
    files run pytest with ``--strict-markers``/``--strict-config`` and semgrep
    with ``--strict``; a file-wide scan for strictness-shaped tokens would
    report those as mypy drift.
    """
    return {
        flag
        for command in _mypy_commands(text)
        for flag in _FLAG_TOKEN.findall(command)
    }


def _mypy_targets_in_arguments(arguments: list[str]) -> list[str]:
    """The positional arguments in ``arguments``: what mypy is told to check.

    Reading stops at a shell operator, so a command chained after mypy is not
    read as mypy's; a flag in _MYPY_FLAGS_WITH_A_VALUE takes the next token.
    """
    targets: list[str] = []
    takes_value = False
    for token in arguments:
        if token in _SHELL_OPERATORS:
            break
        if takes_value:
            takes_value = False
        elif token.startswith("-"):
            takes_value = token in _MYPY_FLAGS_WITH_A_VALUE
        elif token != _LINE_CONTINUATION:
            targets.append(token)
    return targets


def _mypy_targets(path: Path) -> list[str]:
    """Every target one call site names, however it invokes mypy.

    A pre-commit hook is read from its parsed ``entry`` and ``args``: its
    ``name`` and ``description`` say "mypy" in prose, and a hook that passes
    filenames names the staged files as targets.
    """
    if path.name == ".pre-commit-config.yaml":
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        hooks = [
            hook
            for repo in document.get("repos", [])
            for hook in repo.get("hooks", [])
            if hook.get("id") == "mypy"
        ]
        assert hooks, f"{path.name} has no mypy hook"
        commands = [
            " ".join([hook.get("entry", ""), *hook.get("args", [])]) for hook in hooks
        ]
        staged = [
            "<the staged filenames>"
            for hook in hooks
            if hook.get("pass_filenames", True)
        ]
    else:
        commands = _mypy_commands(_executable_content(path))
        staged = []

    targets: list[str] = []
    for command in commands:
        invocation = _MYPY_INVOCATION.search(command)
        assert invocation is not None, f"no mypy invocation in {command!r}"
        arguments = command[invocation.end() :].split()
        targets += _mypy_targets_in_arguments(
            [token.strip("\"'") for token in arguments]
        )
    return targets + staged


def _mypy_flags_in_pre_commit_hooks(text: str) -> set[str]:
    """Return the ``args`` of every mypy hook in a pre-commit configuration.

    A hook's arguments sit below its ``id`` rather than on a command line, so
    the line scanner above cannot see them. Parsed as YAML rather than grepped
    so that reformatting or reordering a hook cannot hide a flag.
    """
    document = yaml.safe_load(text) or {}
    return {
        flag
        for repo in document.get("repos", [])
        for hook in repo.get("hooks", [])
        if hook.get("id") == "mypy"
        for flag in _FLAG_TOKEN.findall(" ".join(hook.get("args", [])))
    }


def _mypy_flags(path: Path) -> set[str]:
    """Every mypy flag one call site passes, however it invokes mypy."""
    flags = _mypy_flags_in_command_lines(_executable_content(path))
    if path.name == ".pre-commit-config.yaml":
        flags |= _mypy_flags_in_pre_commit_hooks(path.read_text(encoding="utf-8"))
    return flags


def test_declared_mypy_config_is_the_effective_one(
    pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The configuration mypy resolves must be the declared one, and strict.

    ``.mypy.ini`` resolves ahead of ``pyproject.toml``, so for the whole life
    of this repo the ``strict = true`` block in ``pyproject.toml`` configured
    nothing while the effective settings had ``no_strict_optional = True`` and
    not one ``disallow_*`` rule. Both halves matter and are asserted together:
    reading the right file proves nothing if the rules in it are empty, and a
    strict-looking file proves nothing if mypy never opens it.

    Read off mypy's own resolved ``Options`` -- the same approach the coverage
    and pytest invariants above take -- so this describes what mypy does
    rather than what a file appears to say.
    """
    from mypy.main import process_options

    root = _repo_root(pytestconfig)
    monkeypatch.chdir(root)

    _, options = process_options(["src/finos_mcp"])

    assert options.config_file is not None, (
        "mypy resolved no configuration file at all, so every rule in "
        f"{_PYPROJECT} is inert and the defaults apply"
    )
    assert Path(options.config_file).resolve() == (root / _PYPROJECT).resolve(), (
        f"mypy reads {options.config_file}, not the declared {_PYPROJECT}. "
        "A configuration that resolves first makes the declared one dead text."
    )

    weakened = sorted(
        setting
        for setting in _REQUIRED_MYPY_STRICTNESS
        if not getattr(options, setting)
    )
    assert not weakened, (
        f"These rules are off in the effective mypy configuration: {weakened}. "
        f"Restore them in [tool.mypy] in {_PYPROJECT} rather than relaxing "
        "this list -- CI passed for months while untyped function bodies went "
        "unchecked."
    )

    assert options.implicit_reexport is False, (
        "implicit re-export is on, so a name imported into one module is "
        "silently exported from it; --strict turns this off"
    )


def test_only_one_mypy_config_exists(pytestconfig: pytest.Config) -> None:
    """No file may resolve ahead of the declared mypy configuration.

    Deleting ``.mypy.ini`` fixes today's drift; forbidding the filename is
    what stops it coming back. ``setup.cfg`` counts only when it carries a
    ``[mypy]`` section, since the file has other legitimate uses.
    """
    root = _repo_root(pytestconfig)

    assert (root / _PYPROJECT).is_file(), (
        f"{_PYPROJECT} must exist: it is the single declared mypy configuration"
    )

    shadowing = sorted(
        name
        for name in _SHADOWING_MYPY_CONFIG_FILES
        if (root / name).is_file()
        and (
            name != "setup.cfg" or "[mypy]" in (root / name).read_text(encoding="utf-8")
        )
    )

    assert not shadowing, (
        f"These files resolve before {_PYPROJECT} and silently replace it: "
        f"{shadowing}. Move anything worth keeping into [tool.mypy] in "
        f"{_PYPROJECT} and delete them."
    )


def test_every_mypy_call_site_is_known(pytestconfig: pytest.Config) -> None:
    """The frozen call-site list must match the files that really run mypy.

    Without this, the flag prohibition below would pass by scanning nothing:
    a scanner that finds no invocations finds no forbidden flags either. This
    fails in both directions -- a listed file that stopped running mypy, and a
    file that started running it without being listed.
    """
    root = _repo_root(pytestconfig)

    assert _MYPY_CALL_SITES, "the mypy call-site list must not be empty"

    silent = sorted(
        call_site
        for call_site in _MYPY_CALL_SITES
        if not (root / call_site).is_file()
        or not _MYPY_INVOCATION.search(_executable_content(root / call_site))
    )
    assert not silent, (
        f"These files are listed as mypy call sites but do not run mypy: "
        f"{silent}. Remove them from the list, or restore the type check."
    )

    unlisted = sorted(
        path.relative_to(root).as_posix()
        for path in _invocation_files(root)
        if _MYPY_INVOCATION.search(_executable_content(path))
        and path.relative_to(root).as_posix() not in _MYPY_CALL_SITES
    )
    assert not unlisted, (
        f"These files run mypy but are not listed as call sites: {unlisted}. "
        "Add them, so the flag prohibition covers them too."
    )


def test_no_call_site_passes_semantic_mypy_flags(
    pytestconfig: pytest.Config,
) -> None:
    """No call site may restate a rule from the declared configuration.

    Seven call sites ran four different rule sets: five passed
    ``--strict-optional --warn-redundant-casts --warn-unused-ignores``, the
    Dependabot job added ``--disallow-any-generics --disallow-untyped-calls``,
    and ``scripts/go-live-gate.sh`` passed nothing at all -- so the release
    gate ran the weakest rules in the repo. Every one of those flags is
    implied by ``strict = true``, so none of them needs to be at a call site,
    and a rule that lives at a call site is a rule the declared configuration
    does not control.
    """
    root = _repo_root(pytestconfig)

    restated = {
        call_site: sorted(flags)
        for call_site in _MYPY_CALL_SITES
        if (flags := _mypy_flags(root / call_site) - _PRESENTATIONAL_MYPY_FLAGS)
    }

    assert not restated, (
        f"These call sites pass mypy rules instead of deriving them from "
        f"[tool.mypy] in {_PYPROJECT}: {restated}. Only presentational "
        f"flags may appear at a call site: {sorted(_PRESENTATIONAL_MYPY_FLAGS)}."
    )


def test_mypy_checks_the_declared_files_at_every_call_site(
    pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """mypy checks src/finos_mcp and tests, and no call site narrows that.

    Every call site used to name src/finos_mcp, so no test file was ever
    type-checked; run over tests, mypy found a reset of the settings singleton
    that reset nothing (#343). The files are declared once in [tool.mypy], and
    a target named on a command line replaces them, so a call site that names
    one checks less than the declaration says.
    """
    from mypy.main import process_options

    root = _repo_root(pytestconfig)
    monkeypatch.chdir(root)

    _, options = process_options([])
    assert tuple(options.files or ()) == _DECLARED_MYPY_FILES, (
        f"[tool.mypy] in {_PYPROJECT} declares files={options.files}; "
        f"it must be {list(_DECLARED_MYPY_FILES)}"
    )

    # An exclude narrows the declaration too: one entry kept the live
    # functional-gate suite out of the check #343 announced for every test
    # (#346). mypy matches each pattern with re.search on the relative path.
    test_paths = [
        test_file.relative_to(root).as_posix()
        for test_file in (root / "tests").rglob("*.py")
    ]
    excluded = sorted(
        path
        for path in test_paths
        if any(re.search(pattern, path) for pattern in options.exclude)
    )
    assert not excluded, (
        f"[tool.mypy] exclude in {_PYPROJECT} keeps these tests out of mypy: {excluded}"
    )

    narrowed = {
        call_site: targets
        for call_site in _MYPY_CALL_SITES
        if (targets := _mypy_targets(root / call_site))
    }
    assert not narrowed, (
        f"These call sites name what mypy checks: {narrowed}. A target on the "
        f"command line replaces `files` in [tool.mypy]; run a bare `mypy`."
    )


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        pytest.param(["src/finos_mcp", "--pretty"], ["src/finos_mcp"], id="first"),
        pytest.param(["--show-error-codes", "tests"], ["tests"], id="after-a-flag"),
        pytest.param(
            ["--txt-report", "security-reports/mypy-report"],
            [],
            id="a-flag-value-is-not-a-target",
        ),
        pytest.param(["--pretty", "&&", "pytest", "tests"], [], id="chained-command"),
    ],
)
def test_mypy_target_scanner(arguments: list[str], expected: list[str]) -> None:
    assert _mypy_targets_in_arguments(arguments) == expected


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        pytest.param(
            "python -m mypy src/finos_mcp --strict-optional\n",
            {"--strict-optional"},
            id="rule-on-one-line-is-caught",
        ),
        pytest.param(
            "python -m mypy src/finos_mcp \\\n"
            "  --show-error-codes \\\n"
            "  --disallow-untyped-calls\n",
            {"--show-error-codes", "--disallow-untyped-calls"},
            id="rule-on-a-continuation-line-is-caught",
        ),
        pytest.param(
            "python -m mypy src/finos_mcp --show-error-codes\n",
            {"--show-error-codes"},
            id="presentational-only-command-is-read-not-ignored",
        ),
        pytest.param(
            "pytest tests/ --strict-markers --strict-config\n"
            "semgrep --config x.yml --error --strict\n",
            set(),
            id="another-tools-strict-flags-are-not-mypy-drift",
        ),
        pytest.param(
            'required_tools=("ruff" "mypy" "pylint")\n'
            "echo 'MyPy type checking' --strict-optional\n"
            "ls security-reports/mypy-report --strict-optional\n",
            set(),
            id="naming-mypy-is-not-invoking-it",
        ),
    ],
)
def test_mypy_flag_scanner_reads_synthetic_commands(
    document: str, expected: set[str]
) -> None:
    """Positive and negative controls for the scanner the prohibition uses.

    The real call sites are about to carry no forbidden flags at all, which is
    the point of the fix and also means the prohibition above would pass just
    as happily against a scanner that always returned nothing. These synthetic
    commands pin down that it reads what it claims to read, and only that.
    """
    assert _mypy_flags_in_command_lines(document) == expected


def test_mypy_flag_scanner_reads_pre_commit_hook_args() -> None:
    """A pre-commit hook's args are rules too, and must not hide from the scan."""
    document = """
repos:
  - repo: https://github.com/pre-commit/mirrors-mypy
    hooks:
      - id: mypy
        args: [--show-error-codes, --strict-optional]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix, --strict-markers]
"""
    assert _mypy_flags_in_pre_commit_hooks(document) == {
        "--show-error-codes",
        "--strict-optional",
    }


# ---------------------------------------------------------------------------
# test-runner configuration
# ---------------------------------------------------------------------------


def test_only_one_pytest_config_exists(pytestconfig: pytest.Config) -> None:
    """A second pytest configuration is drift even when nothing reads it.

    ``pytest.fast.ini`` declared its settings under ``[tool:pytest]`` -- the
    section name that is valid only in ``setup.cfg``. pytest accepted the file
    as its ``configfile`` and then read *nothing* from it: the documented
    ``pytest -c pytest.fast.ini`` collected the entire suite rather than the
    ``tests/unit`` subset its ``testpaths`` named (515 tests against 278 when
    measured), in asyncio strict mode rather than the auto mode it declared,
    with its ``--maxfail``, ``-x`` and marker list equally ignored. A misnamed
    section buys silence, not an error, which is the same failure mode as a
    ``[tool.mypy]`` block that no mypy run ever opens.
    """
    root = _repo_root(pytestconfig)

    assert pytestconfig.inipath is not None, (
        f"pytest must read its configuration from {_PYPROJECT}; it resolved "
        "no configuration file at all"
    )
    assert pytestconfig.inipath.name == _PYPROJECT, (
        f"pytest must read its configuration from {_PYPROJECT}, not "
        f"{pytestconfig.inipath}"
    )

    duplicates = sorted(
        path.relative_to(root).as_posix()
        for name in _SHADOWING_PYTEST_CONFIG_FILES
        for path in root.glob(name)
        if name != "setup.cfg" or "[tool:pytest]" in path.read_text(encoding="utf-8")
    )

    assert not duplicates, (
        f"These extra pytest configurations must not exist: {duplicates}. "
        "Declare test settings once, in [tool.pytest.ini_options] in "
        f"{_PYPROJECT}."
    )


# ---------------------------------------------------------------------------
# semgrep
# ---------------------------------------------------------------------------


def test_every_semgrep_call_site_is_known(pytestconfig: pytest.Config) -> None:
    """The frozen call-site list must match the files that really run semgrep.

    Without this, the prohibition below would pass by scanning nothing. Fails
    in both directions -- a listed file that stopped running semgrep, and a
    file that started running it without being listed.
    """
    root = _repo_root(pytestconfig)

    assert _SEMGREP_CALL_SITES, "the semgrep call-site list must not be empty"

    silent = sorted(
        call_site
        for call_site in _SEMGREP_CALL_SITES
        if not (root / call_site).is_file()
        or _SEMGREP_WRAPPER not in _executable_content(root / call_site)
    )
    assert not silent, (
        f"These files are listed as semgrep call sites but do not run semgrep "
        f"through {_SEMGREP_WRAPPER}: {silent}. Remove them from the list, or "
        "restore the scan."
    )

    unlisted = sorted(
        path.relative_to(root).as_posix()
        for path in _invocation_files(root)
        if _SEMGREP_WRAPPER in _executable_content(path)
        and path.relative_to(root).as_posix() not in _SEMGREP_CALL_SITES
        and path.name != Path(_SEMGREP_WRAPPER).name
    )
    assert not unlisted, (
        f"These files run semgrep but are not listed as call sites: {unlisted}. "
        "Add them, so the prohibition below covers them too."
    )


def test_no_call_site_invokes_semgrep_directly(pytestconfig: pytest.Config) -> None:
    """Semgrep must be reached through the wrapper, never as a bare tool.

    The pre-commit hook was the one call site that did not: it pinned
    semgrep v1.135.0 through its own ``repo:``/``rev:`` while the wrapper pinned
    1.149.0, so two semgrep versions scanned this repo with the same ruleset
    and different engines. Its isolated py3.12 environment also had no
    setuptools, so it raised ``ModuleNotFoundError: No module named
    'pkg_resources'`` and scanned nothing at all, on every run, undetected.
    """
    root = _repo_root(pytestconfig)

    offenders = {}
    for path in _invocation_files(root):
        if path.name == Path(_SEMGREP_WRAPPER).name:
            continue
        text = _COMMENT.sub("", _executable_content(path))
        # The wrapper's own path ends in "semgrep-isolated.sh"; strip every
        # mention of it before looking for a bare invocation, so routing
        # through the wrapper is never mistaken for bypassing it.
        text = text.replace(_SEMGREP_WRAPPER, "")
        if matches := _RAW_SEMGREP_INVOCATION.findall(text):
            offenders[path.relative_to(root).as_posix()] = len(matches)

    assert not offenders, (
        f"These call sites invoke semgrep directly instead of through "
        f"{_SEMGREP_WRAPPER}: {offenders}. One wrapper means one pinned "
        "version and one isolated environment."
    )


@pytest.mark.parametrize(
    ("document", "expected"),
    [
        pytest.param(
            "semgrep --config config/security/semgrep.yml src/\n",
            1,
            id="bare-invocation-is-caught",
        ),
        pytest.param(
            "python -m semgrep --config x.yml\n",
            1,
            id="module-invocation-is-caught",
        ),
        pytest.param(
            'echo "Running Semgrep static analysis..."\n'
            'required_tools=("bandit" "semgrep" "pylint")\n'
            "jq '.results[]' security-reports/semgrep-report.json\n",
            0,
            id="naming-semgrep-is-not-invoking-it",
        ),
        pytest.param(
            "./scripts/semgrep-isolated.sh --config x.yml src/\n".replace(
                "scripts/semgrep-isolated.sh", ""
            ),
            0,
            id="wrapper-path-stripped-leaves-no-bare-invocation",
        ),
    ],
)
def test_semgrep_scanner_reads_synthetic_commands(document: str, expected: int) -> None:
    """Positive and negative controls for the scanner the prohibition uses.

    Every real call site is about to route through the wrapper, which is the
    point of the fix and also means the prohibition above would pass just as
    happily against a scanner that always found nothing.
    """
    assert len(_RAW_SEMGREP_INVOCATION.findall(document)) == expected


def test_semgrep_ruleset_can_actually_fail(pytestconfig: pytest.Config) -> None:
    """The ruleset must declare at least one ERROR rule.

    Every call site runs semgrep with ``--error``, which makes findings exit
    non-zero. A ruleset with no ERROR-severity rule therefore cannot fail the
    build no matter what the code does, and an emptied ruleset would make the
    whole gate pass forever while still reporting success.
    """
    root = _repo_root(pytestconfig)
    ruleset = root / "config" / "security" / "semgrep.yml"

    assert ruleset.is_file(), f"{ruleset} must exist: it is the semgrep ruleset"

    rules = yaml.safe_load(ruleset.read_text(encoding="utf-8")).get("rules") or []
    assert rules, f"{ruleset} declares no rules, so the semgrep gate scans for nothing"

    errors = [r for r in rules if str(r.get("severity", "")).upper() == "ERROR"]
    assert errors, (
        f"{ruleset} declares no ERROR-severity rule, so --error can never fail "
        "and every semgrep call site would pass unconditionally."
    )


# ---------------------------------------------------------------------------
# pylint configuration
# ---------------------------------------------------------------------------


def test_declared_pylint_config_is_the_effective_one(
    pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The configuration pylint resolves must be the declared one, and the gate in it real.

    Read off pylint's own discovery and its own resolved ``Namespace`` -- the
    same approach the mypy, pytest and coverage invariants above take -- so this
    describes what pylint does rather than what a file appears to say.

    Both halves matter and are asserted together: resolving the right file
    proves nothing if the gate in it is pylint's default, and a file declaring
    8.5 proves nothing if pylint never opens it.
    """
    from pylint.config.config_initialization import _config_initialization
    from pylint.config.find_default_config_files import find_default_config_files
    from pylint.lint.pylinter import PyLinter

    root = _repo_root(pytestconfig)
    monkeypatch.chdir(root)

    discovered = next(find_default_config_files(), None)
    assert discovered is not None, (
        f"pylint resolved no configuration file at all, so every rule in "
        f"{_PYPROJECT} is inert and the defaults apply"
    )
    assert Path(discovered).resolve() == (root / _PYPROJECT).resolve(), (
        f"pylint reads {discovered}, not the declared {_PYPROJECT}. "
        "A configuration that resolves first makes the declared one dead text."
    )

    linter = PyLinter()
    linter.load_default_plugins()
    _config_initialization(
        linter, args_list=["--persistent=n", "dummy"], config_file=discovered
    )

    assert linter.config.fail_under == _DECLARED_PYLINT_FAIL_UNDER, (
        f"pylint resolved fail-under={linter.config.fail_under}, not the "
        f"declared {_DECLARED_PYLINT_FAIL_UNDER}. pylint's own default is 10, "
        "so a value of 10 here means the declared table was never read."
    )


def test_only_one_pylint_config_exists(pytestconfig: pytest.Config) -> None:
    """No file may resolve ahead of the declared pylint configuration.

    Deleting ``.pylintrc`` fixes today's drift; forbidding the filename is what
    stops it coming back. ``tox.ini``/``setup.cfg`` count only when they carry a
    ``[pylint]`` section, since both files have other legitimate uses.
    """
    root = _repo_root(pytestconfig)

    shadowing = sorted(
        name
        for name in _SHADOWING_PYLINT_CONFIG_FILES
        if (root / name).is_file()
        and (
            name not in ("tox.ini", "setup.cfg")
            or "[pylint" in (root / name).read_text(encoding="utf-8")
        )
    )

    assert not shadowing, (
        f"These files resolve before {_PYPROJECT} and silently replace it: "
        f"{shadowing}. Move anything worth keeping into [tool.pylint.*] in "
        f"{_PYPROJECT} and delete them."
    )


def test_no_call_site_restates_the_pylint_score_gate(
    pytestconfig: pytest.Config,
) -> None:
    """No call site may carry --fail-under or --rcfile.

    Three did. The pre-commit hook, ``release.yml`` and ``quality-check.sh`` all
    passed ``--fail-under=8.0`` against a declared 8.5, and in
    ``quality-check.sh`` it was a ``--pylint-min-score`` command-line option --
    so the gate was not merely weaker than CI's, it was whatever the caller
    asked for.
    """
    root = _repo_root(pytestconfig)

    offenders: dict[str, list[str]] = {}
    for path in _invocation_files(root):
        text = _COMMENT.sub("", _executable_content(path))
        if not _PYLINT_INVOCATION.search(text) and "pylint" not in text:
            continue
        if found := sorted(flag for flag in _FORBIDDEN_PYLINT_FLAGS if flag in text):
            offenders[path.relative_to(root).as_posix()] = found

    assert not offenders, (
        f"These call sites restate a pylint rule instead of deriving it from "
        f"[tool.pylint.main] in {_PYPROJECT}: {offenders}."
    )


# ---------------------------------------------------------------------------
# pre-commit execution and hook ownership
# ---------------------------------------------------------------------------


def _pre_commit_hooks(root: Path) -> list[tuple[str, dict[str, object]]]:
    """Every hook in the pre-commit configuration, paired with its repo block."""
    document = (
        yaml.safe_load((root / _PRE_COMMIT_CONFIG).read_text(encoding="utf-8")) or {}
    )
    return [
        (repo.get("repo", ""), hook)
        for repo in document.get("repos", [])
        for hook in repo.get("hooks", [])
    ]


def test_ci_actually_runs_the_pre_commit_hooks(pytestconfig: pytest.Config) -> None:
    """A workflow job must really run ``pre-commit run --all-files``.

    This is the invariant whose absence caused the other two in this file to be
    needed. No workflow ran pre-commit at all, so a hook could be broken on main
    indefinitely: the mypy hook checked types in an environment that could not
    import this package, the semgrep hook raised ``pkg_resources`` before
    scanning a line, and the detect-secrets hook failed on a committed test
    value. Each was found by hand, months apart.

    The workflow is parsed and the step's ``run`` block inspected, rather than
    grepped: a comment mentioning the command, or the command sitting in a job
    that never executes, would satisfy a grep.
    """
    root = _repo_root(pytestconfig)
    workflow = root / _PRE_COMMIT_WORKFLOW

    assert workflow.is_file(), f"{_PRE_COMMIT_WORKFLOW} must exist"

    jobs = (yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}).get("jobs", {})
    assert jobs, f"{_PRE_COMMIT_WORKFLOW} declares no jobs"

    running = sorted(
        name
        for name, job in jobs.items()
        if any(
            _PRE_COMMIT_COMMAND in step.get("run", "")
            for step in job.get("steps", [])
            if isinstance(step, dict)
        )
    )

    assert running, (
        f"No job in {_PRE_COMMIT_WORKFLOW} runs '{_PRE_COMMIT_COMMAND}'. "
        "A hook set nothing executes is not a gate -- which is how two broken "
        "hooks reached main."
    )


def test_every_project_owned_hook_runs_the_projects_own_tool(
    pytestconfig: pytest.Config,
) -> None:
    """Hooks for tools this project declares must be local/system.

    An upstream hook builds its own environment from its own ``rev``: a second
    version of the tool, drifting on its own schedule, with a second place its
    rules can be set. Every failure this configuration has had was that one
    failure -- mypy at v1.17.1 without fastmcp, pip-audit pinned twice at v2.9.0
    and v2.7.3, semgrep at v1.135.0 against the wrapper's 1.149.0, pylint at
    v3.3.8 without fastmcp and with its own weaker --fail-under.

    Presence is asserted alongside locality on purpose. "Every hook in the set
    is local" is true of an empty set, so deleting a hook must fail here rather
    than quietly shrinking what this test checks.
    """
    root = _repo_root(pytestconfig)
    hooks = _pre_commit_hooks(root)

    assert hooks, f"{_PRE_COMMIT_CONFIG} declares no hooks at all"

    by_id = {str(hook.get("id")): (repo, hook) for repo, hook in hooks}

    missing = sorted(_PROJECT_OWNED_HOOK_IDS - by_id.keys())
    assert not missing, (
        f"These hooks are declared project-owned but are absent from "
        f"{_PRE_COMMIT_CONFIG}: {missing}. Restore them, or remove them from "
        "_PROJECT_OWNED_HOOK_IDS deliberately -- a hook that quietly disappears "
        "takes its gate with it."
    )

    foreign = {}
    for hook_id in sorted(_PROJECT_OWNED_HOOK_IDS):
        repo, hook = by_id[hook_id]
        reasons = []
        if repo != "local":
            reasons.append(f"repo={repo!r}")
        if hook.get("language") != "system":
            reasons.append(f"language={hook.get('language')!r}")
        if reasons:
            foreign[hook_id] = reasons

    assert not foreign, (
        f"These hooks run a tool this project already declares, but from an "
        f"environment it does not control: {foreign}. Use repo: local with "
        "language: system so the hook runs the project's own tool."
    )


# ---------------------------------------------------------------------------
# tests that cannot fail
# ---------------------------------------------------------------------------


def _test_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every ``test_*`` function in a module, including methods on Test classes."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


def _own_body(function: ast.AST) -> list[ast.AST]:
    """Every node belonging to ``function`` itself, not to a nested definition.

    ast.walk descends into nested functions, so a helper closure that legitimately
    returns a value would otherwise be blamed on the test that defines it. An
    invariant that accuses correct code is worse than no invariant: it teaches
    people to work around the check.
    """
    nodes: list[ast.AST] = []
    stack = list(ast.iter_child_nodes(function))
    while stack:
        node = stack.pop()
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            continue  # a separate scope; its returns are its own business
        nodes.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return nodes


def _returns_a_value(function: ast.AST) -> list[int]:
    """Line numbers where a test returns something other than None.

    pytest treats a returned value as a pass. `return False` is therefore not a
    failing test, it is a passing test that looks like a failing one, and that is
    what 32 of them did in tests/test_mcp_functionality.py.
    """
    return [
        node.lineno
        for node in _own_body(function)
        if isinstance(node, ast.Return)
        and node.value is not None
        and not (isinstance(node.value, ast.Constant) and node.value.value is None)
    ]


def _swallows_into_return(function: ast.AST) -> list[int]:
    """Line numbers of except handlers that return instead of failing.

    Narrow on purpose: a handler that re-raises, asserts, or calls pytest.fail or
    pytest.skip is doing something legitimate. A handler whose only effect is to
    return turns a crash into a pass.
    """
    offenders = []
    for handler in (n for n in _own_body(function) if isinstance(n, ast.ExceptHandler)):
        body = list(ast.walk(ast.Module(body=handler.body, type_ignores=[])))
        if any(isinstance(node, (ast.Raise, ast.Assert)) for node in body):
            continue
        calls = {
            node.func.attr
            for node in body
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        if calls & {"fail", "skip", "xfail", "exit"}:
            continue
        if any(isinstance(node, ast.Return) for node in body):
            offenders.append(handler.lineno)
    return offenders


def _collected_test_files(root: Path) -> list[Path]:
    """Files pytest actually collects, per python_files in pyproject.toml."""
    return sorted(
        path
        for path in (root / "tests").rglob("test_*.py")
        if "__pycache__" not in path.parts
    )


def test_every_collected_test_file_can_fail(pytestconfig: pytest.Config) -> None:
    """A test file with no assertions cannot fail, so it is not a test file.

    ``tests/test_mcp_functionality.py`` was 535 lines with zero assertions, 32
    ``return True``/``return False`` statements and 11 bare ``except Exception``
    handlers. It reported success no matter what the server did, and it is why a
    framework search that answered nothing, a catalog that could not state its
    own provenance, and search ids that no get_* tool would accept all reached
    main. ``tests/test_id_mapping.py`` was the same, and it was written to test
    precisely the id round-trip that was broken.

    Parsed with ``ast`` rather than grepped, so a docstring mentioning "assert"
    cannot satisfy it.
    """
    root = _repo_root(pytestconfig)
    files = _collected_test_files(root)

    assert len(files) > 10, (
        f"only {len(files)} collected test files found under {root / 'tests'}; "
        "this invariant would pass by scanning almost nothing"
    )

    assertionless = []
    for path in files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        # `assert`, `pytest.raises` and `pytest.fail` are all ways of failing.
        # Counting only bare asserts falsely accused
        # tests/integration/test_static_fallback_sync.py, which compares catalogs
        # and calls pytest.fail with a diff -- a perfectly good failure.
        can_fail = (
            any(isinstance(node, ast.Assert) for node in ast.walk(tree))
            or "pytest.raises" in source
            or "pytest.fail" in source
        )
        if not can_fail:
            assertionless.append(path.relative_to(root).as_posix())

    assert not assertionless, (
        f"These collected test files contain no assertion at all, so nothing in "
        f"them can fail: {assertionless}"
    )


def test_no_test_returns_a_value_instead_of_asserting(
    pytestconfig: pytest.Config,
) -> None:
    """pytest passes a test that returns, so returning is not reporting."""
    root = _repo_root(pytestconfig)

    offenders = {}
    for path in _collected_test_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in _test_functions(tree):
            if lines := _returns_a_value(function):
                offenders[f"{path.relative_to(root).as_posix()}::{function.name}"] = (
                    lines
                )

    assert not offenders, (
        f"These tests return a value rather than asserting, which pytest scores "
        f"as a pass: {offenders}. Replace `return False` with an assertion."
    )


def test_no_test_swallows_an_exception_into_a_return(
    pytestconfig: pytest.Config,
) -> None:
    """`except Exception: return False` converts a crash into a pass."""
    root = _repo_root(pytestconfig)

    offenders = {}
    for path in _collected_test_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in _test_functions(tree):
            if lines := _swallows_into_return(function):
                offenders[f"{path.relative_to(root).as_posix()}::{function.name}"] = (
                    lines
                )

    assert not offenders, (
        f"These tests catch an exception and return instead of failing: "
        f"{offenders}. Let it propagate, or assert on it with pytest.raises."
    )


@pytest.mark.parametrize(
    ("source", "expected_returns", "expected_swallows"),
    [
        pytest.param(
            "def test_a():\n    assert True\n",
            0,
            0,
            id="asserting-test-is-clean",
        ),
        pytest.param(
            "def test_a():\n    return False\n",
            1,
            0,
            id="returning-false-is-caught",
        ),
        pytest.param(
            "def test_a():\n    return None\n",
            0,
            0,
            id="explicit-return-none-is-allowed",
        ),
        pytest.param(
            "def test_a():\n    return\n",
            0,
            0,
            id="bare-return-is-allowed",
        ),
        pytest.param(
            "def test_a():\n"
            "    try:\n        work()\n"
            "    except Exception:\n        return False\n",
            1,
            1,
            id="swallow-into-return-is-caught",
        ),
        pytest.param(
            "def test_a():\n"
            "    try:\n        work()\n"
            "    except Exception:\n        raise\n",
            0,
            0,
            id="re-raising-handler-is-allowed",
        ),
        pytest.param(
            "def test_a():\n"
            "    try:\n        work()\n"
            "    except Exception:\n        pytest.skip('no network')\n",
            0,
            0,
            id="skipping-handler-is-allowed",
        ),
    ],
)
def test_cannot_fail_scanners_read_synthetic_sources(
    source: str, expected_returns: int, expected_swallows: int
) -> None:
    """Positive and negative controls for the two scanners above.

    The real suite is about to contain none of these patterns, which is the point
    of the fix and also means both prohibitions would pass just as happily
    against scanners that always returned nothing.
    """
    function = _test_functions(ast.parse(source))[0]

    assert len(_returns_a_value(function)) == expected_returns
    assert len(_swallows_into_return(function)) == expected_swallows


# ---------------------------------------------------------------------------
# no integration test gates on a wall clock
# ---------------------------------------------------------------------------


_CLOCKS = frozenset({"time", "perf_counter", "monotonic", "monotonic_ns", "time_ns"})


def _is_clock_call(node: ast.AST) -> bool:
    """True for ``time.time()``, ``time.perf_counter()`` and friends.

    Matches the attribute name only, so ``from time import perf_counter``
    followed by a bare ``perf_counter()`` is caught too -- a guard that matches
    one spelling of a call is a guard somebody walks around by writing the other.
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in _CLOCKS
    return isinstance(func, ast.Name) and func.id in _CLOCKS


def _elapsed_assertions_in(function: ast.AST) -> list[int]:
    """Line numbers, inside one test, of asserts on a measured wall-clock span.

    Three spellings, all of which have appeared in this repository:

        start = time.time(); ...; assert time.time() - start < 1.0
        start = time.time(); ...; elapsed = time.time() - start
        start = time.time(); ...; end = time.time(); assert end - start < 1.0

    So the scan collects the names holding a clock reading, then the names
    holding a difference of two of them, then flags any assert mentioning either
    shape. Deliberately *not* matched: ``deadline = time.time() + timeout``
    polling loops, TTL arithmetic and timestamps handed to a constructor. None
    of those is an assertion, and an invariant that accuses correct code is
    worse than no invariant.

    Scoped to one function, and collected in three passes rather than one.
    ``ast.walk`` is breadth-first, not source order, so a single pass would
    decide ``end - start`` was not a duration whenever it happened to reach that
    subtraction before the ``end = time.time()`` binding a level further in --
    and a module-wide pass would let a name bound in one test taint an assert in
    another.
    """
    nodes = list(ast.walk(function))

    def _assignments() -> list[tuple[str, ast.expr]]:
        return [
            (node.targets[0].id, node.value)
            for node in nodes
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ]

    clock_names = {name for name, value in _assignments() if _is_clock_call(value)}

    def _is_elapsed(value: ast.AST) -> bool:
        if not (isinstance(value, ast.BinOp) and isinstance(value.op, ast.Sub)):
            return False
        return all(
            _is_clock_call(side)
            or (isinstance(side, ast.Name) and side.id in clock_names)
            for side in (value.left, value.right)
        )

    elapsed_names = {name for name, value in _assignments() if _is_elapsed(value)}

    return [
        node.lineno
        for node in nodes
        if isinstance(node, ast.Assert)
        and any(
            (isinstance(child, ast.Name) and child.id in elapsed_names)
            or _is_elapsed(child)
            for child in ast.walk(node.test)
        )
    ]


def _elapsed_assertions(tree: ast.AST) -> list[int]:
    """Every wall-clock assertion in a module, gathered test by test."""
    return sorted(
        lineno
        for function in _test_functions(tree)
        for lineno in _elapsed_assertions_in(function)
    )


#: The maturity words a Development Status classifier and a shields.io badge can
#: both express. Keyed by the classifier's own wording so the mapping is read off
#: the standard rather than invented here; PyPI defines seven, and the four a
#: 0.x project can honestly sit in are the ones spelled out.
_MATURITY_BY_CLASSIFIER = {
    "2 - Pre-Alpha": "pre-alpha",
    "3 - Alpha": "alpha",
    "4 - Beta": "beta",
    "5 - Production/Stable": "stable",
}


def test_readme_count_badges_match_their_source_of_truth(
    pytestconfig: pytest.Config,
) -> None:
    """A badge stating a number is a hand-maintained count, and those drift.

    ``MCP tools-11`` and ``frameworks-13 supported`` were both *correct* when
    #147 was filed, which is exactly why they are worth pinning: so was
    ``438/438 tests passing`` in the CHANGELOG, right up until it was not. The
    difference from that one is that both of these have a source of truth in
    the tree already, so they can be checked instead of deleted.

    Neither source needs the network, which is what keeps this in a config-drift
    test. The framework count reads ``STATIC_FRAMEWORK_FILES``, the shipped
    fallback list, and that list is itself compared against the live GitHub
    corpus by ``tests/integration/test_static_fallback_sync.py`` under its own
    workflow. So the chain is badge -> static list (here, offline) -> live
    corpus (there, online), and the residual is only as wide as the window
    between an upstream change and that job noticing it.

    The tool count reads ``PUBLISHED_TOOLS``, which
    ``tests/unit/test_published_surface.py`` declares to be the single source of
    truth for the tool inventory and asserts against the running server.
    """
    root = _repo_root(pytestconfig)
    readme = (root / "README.md").read_text(encoding="utf-8")

    sys.path.insert(0, str(root / "tests" / "unit"))
    try:
        from test_published_surface import (  # type: ignore[import-not-found]
            PUBLISHED_TOOLS,
        )
    finally:
        sys.path.pop(0)
    from finos_mcp.content.static_catalog import STATIC_FRAMEWORK_FILES

    #: badge label -> (the number it must equal, where that number comes from)
    expected = {
        "MCP%20tools": (len(PUBLISHED_TOOLS), "PUBLISHED_TOOLS"),
        "frameworks": (len(STATIC_FRAMEWORK_FILES), "STATIC_FRAMEWORK_FILES"),
    }

    mismatches = []
    for label, (count, source) in expected.items():
        found = re.findall(rf"img\.shields\.io/badge/{label}-(\d+)", readme)
        if len(found) != 1:
            mismatches.append(
                f"expected exactly one {label!r} count badge in README.md, "
                f"found {len(found)}: {found}"
            )
            continue
        if int(found[0]) != count:
            mismatches.append(
                f"README badge says {label}={found[0]} but {source} has {count}"
            )

    assert not mismatches, (
        f"README count badges disagree with the code: {mismatches}. Update the "
        "badge, or if the number really changed, change it at the source first."
    )


def test_no_readme_badge_asserts_a_build_outcome_nothing_observes(
    pytestconfig: pytest.Config,
) -> None:
    """A hardcoded ``passing`` badge is a claim, not a measurement.

    README.md carried ``security-passing``, ``tests-passing`` and
    ``mypy-passing`` as static shields.io images, immediately below a *live*
    workflow-status badge for ``security-analysis.yml`` -- the very workflow
    that runs bandit, semgrep, pytest and mypy. So a red build turned the real
    badge red and left the three static ones reading ``passing``, contradicting
    it in the same paragraph (#147).

    They could not be made honest by pointing them at a workflow either.
    shields.io's status endpoint addresses a workflow *file*, and all four gates
    are jobs inside the one ``security-analysis.yml``, so three per-gate badges
    would render three identical copies of the badge already there.

    Scoped to ``passing``/``failing`` deliberately. ``pre--commit-enabled`` and
    ``document access-direct`` are descriptions of what the project has, not
    assertions about whether a run succeeded, and a guard that swept those up
    would be rejecting correct content.
    """
    root = _repo_root(pytestconfig)
    readme = (root / "README.md").read_text(encoding="utf-8")

    offenders = [
        line.strip()
        for line in readme.splitlines()
        if re.search(r"img\.shields\.io/badge/[^)]*-(passing|failing)-", line)
    ]

    assert not offenders, (
        "These README badges are static images asserting a build outcome that "
        f"nothing observes: {offenders}. The live badge for the workflow that "
        "actually runs these gates is already in the file; a hardcoded twin can "
        "only ever agree with it by luck."
    )


def test_the_readme_status_badge_matches_the_declared_maturity(
    pytestconfig: pytest.Config,
) -> None:
    """The two files a reader checks first must not disagree about maturity.

    ``README.md`` carried ``status-stable-brightgreen`` while ``pyproject.toml``
    declared ``Development Status :: 3 - Alpha`` (#67). Both are claims about the
    same release, and the badge is the one a human sees first while the
    classifier is the one PyPI indexes -- so the disagreement was invisible to
    each file's own reader.

    ``pyproject.toml`` is the source of truth here, not the badge: the classifier
    is a published packaging fact with a fixed vocabulary, while a shields.io URL
    is a string nothing validates. So this asserts the badge follows the
    classifier, and the remedy for a genuine maturity change is to move the
    classifier first.
    """
    root = _repo_root(pytestconfig)

    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    classifiers = pyproject["project"]["classifiers"]
    declared = [c for c in classifiers if c.startswith("Development Status ::")]
    assert len(declared) == 1, (
        f"expected exactly one Development Status classifier, found {declared}"
    )
    suffix = declared[0].split("::", 1)[1].strip()
    assert suffix in _MATURITY_BY_CLASSIFIER, (
        f"unrecognised Development Status {suffix!r}; add it to "
        "_MATURITY_BY_CLASSIFIER with the badge word it corresponds to"
    )
    expected = _MATURITY_BY_CLASSIFIER[suffix]

    readme = (root / "README.md").read_text(encoding="utf-8")
    badges = re.findall(
        r"!\[Status\]\(https://img\.shields\.io/badge/status-([^-)]+)-", readme
    )
    assert len(badges) == 1, (
        f"expected exactly one ![Status] shields.io badge in README.md, found "
        f"{len(badges)}: {badges}. This invariant reads the first field of the "
        "badge path, so a second one would leave the disagreement it exists to "
        "catch unmeasured."
    )

    assert badges[0] == expected, (
        f"README.md advertises status {badges[0]!r} while pyproject.toml declares "
        f"{declared[0]!r}, which is {expected!r}. These are the two files a reader "
        "checks first. Change the classifier if the maturity really moved, then "
        "follow it here."
    )


#: The repository this artefact is built and published from. Not a comparison
#: between two files: this invariant names the identity and requires every
#: machine-readable provenance field to carry it, so deleting one side cannot
#: satisfy it.
#:
#: ``finos/finos-mcp-server``, the identity these fields once carried, has never
#: existed (#78).
_THIS_REPOSITORY = "finos/aigf-mcp-server"

#: Every ``[project.urls]`` key this project publishes, mapped to the path under
#: the repository each must address. Frozen rather than derived from the file,
#: because an invariant that iterates whatever keys happen to be present reports
#: success once they are all deleted.
_EXPECTED_PROJECT_URL_PATHS = {
    "Homepage": "",
    "Repository": "",
    "Documentation": "/blob/main/README.md",
    "Bug Tracker": "/issues",
}


def test_every_published_provenance_field_names_this_repository(
    pytestconfig: pytest.Config,
) -> None:
    """A dead link in package metadata is only ever seen by the person it fails.

    All four ``[project.urls]`` entries addressed
    ``github.com/finos/finos-mcp-server``, which does not exist (#78). These are
    the links PyPI renders on the project page and every package-metadata reader
    resolves, so nothing in a local run, a test suite or a CI gate ever visits
    them -- the first reader to find out is a user who clicked one.

    Scoped to *machine-readable provenance fields*: addresses that answer "where
    did this artefact come from" to a tool, rather than to a reader, and that
    ship inside a built artefact. This guard covers the wheel's ``Project-URL``
    entries; ``test_distribution_notices.py`` covers the packaged SPDX fields
    after #80 aligned their owner and package identity. The Dockerfile's
    ``org.opencontainers.image.source`` label
    was the other until #83 deleted an image that had never been buildable, and
    this invariant covers whatever such fields exist rather than asserting a
    fixed number of them. Deliberately not scoped to every ``github.com`` URL in
    the tree: ``CHANGELOG.md`` and test docstrings name upstream on purpose, and a
    guard that swept those up would need an allowlist that decays into an
    exclusion list.

    This asserts the paths too, not just the owner. ``Documentation`` pointing at
    the repository root instead of the README, or ``Bug Tracker`` at the root
    instead of ``/issues``, is the same failure as the wrong owner -- a link that
    does not go where its key says it goes -- and would survive an owner-only
    check.
    """
    root = _repo_root(pytestconfig)
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    urls = pyproject["project"]["urls"]

    assert set(urls) == set(_EXPECTED_PROJECT_URL_PATHS), (
        f"pyproject.toml publishes [project.urls] keys {sorted(urls)}, but this "
        f"invariant knows {sorted(_EXPECTED_PROJECT_URL_PATHS)}. Add the new key "
        "here with the path it must address, so it is checked rather than "
        "silently unguarded."
    )

    wrong = {
        key: value
        for key, value in urls.items()
        if value
        != f"https://github.com/{_THIS_REPOSITORY}{_EXPECTED_PROJECT_URL_PATHS[key]}"
    }
    assert not wrong, (
        f"These [project.urls] entries do not address {_THIS_REPOSITORY}: {wrong}. "
        "They are published in the wheel as Project-URL metadata and rendered by "
        "PyPI, so a wrong owner or path is a dead link nothing in this repository "
        "resolves."
    )


def test_no_unit_or_integration_test_gates_on_a_measured_wall_clock(
    pytestconfig: pytest.Config,
) -> None:
    """A wall-clock budget is only meaningful when signal and noise are far apart.

    Originally scoped to ``tests/integration/`` alone, on the reasoning that the
    network is what a budget really measures and that in-process tests could
    always set a bound far enough above the measured cost to mean something.
    #134 showed the second half does not hold by itself.
    ``test_cache_json_serialization.py`` asserted ``elapsed < 1.0`` around 10
    in-memory cache round trips per payload size. Nothing there touches the
    network -- and the bound was still arbitrary: measured over 20 runs the
    largest payload took 33.9ms, so the margin was 29x. A GC pause or CPU steal
    of that size on a shared runner is uncommon but not rare, and the failure
    would have been indistinguishable from a real regression.

    So the rule is not about the network, and it is not about the directory:
    only measure time when the failure you are watching for is nowhere near
    the noise. The one assertion that met it,
    ``test_large_input_does_not_trigger_catastrophic_backtracking`` in
    ``tests/security/``, stood at 0.003s measured against a 5.0s bound --
    1500x -- guarding catastrophic regex backtracking, a failure mode with no
    upper bound at all. 29x guarding linear JSON serialization is not the same
    object. ``tests/security/`` was exempt from this scan for that canary
    alone; #282 removed the scan it measured, and the exemption with it, so
    every test directory is now in scope. A new canary must state its measured
    cost beside its bound and be added to this docstring.

    ``TestPerformanceCharacteristics::test_response_times`` asserted
    ``list_time < 1.0`` around a call to ``raw.githubusercontent.com``. It
    measured 1.09s, 1.03s and 1.02s over three consecutive pushes to unchanged
    ``main``. On PR #131's single commit it failed on Python 3.11 in one
    workflow and on 3.13 in another, passing on each of those versions in the
    other workflow, and re-running both on the identical commit turned them
    green. That is not a flaky test, it is a test of GitHub. What replaced it
    counts HTTP requests, a number this repository decides and a runner cannot
    change.
    """
    root = _repo_root(pytestconfig)

    # A floor per directory, not over the total: without it, one of the three
    # vanishing (renamed, moved, excluded by a glob) is invisible because the
    # others still contribute plenty of files.
    files = []
    for name, floor in (("unit", 20), ("integration", 3), ("security", 5)):
        directory = root / "tests" / name
        found = sorted(
            path
            for path in directory.rglob("test_*.py")
            if "__pycache__" not in path.parts
        )
        assert len(found) > floor, (
            f"only {len(found)} test files found under {directory}; this "
            "invariant would pass by scanning almost nothing"
        )
        files.extend(found)

    offenders = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno in _elapsed_assertions(tree):
            offenders.append(f"{path.relative_to(root).as_posix()}:{lineno}")

    assert not offenders, (
        "These assertions gate on a measured wall-clock duration, which belongs "
        "to the runner rather than to this code unless the failure being watched "
        f"for is orders of magnitude away from the noise: {offenders}. Assert on "
        "what this repository decides -- the number of HTTP requests issued, or "
        "the content of the answer. If it really is a blowup canary, measure the "
        "real cost first, say so beside the bound, and name it in this "
        "invariant's docstring."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "def test_a():\n"
            "    t0 = time.time()\n    work()\n"
            "    assert time.time() - t0 < 1.0\n",
            1,
            id="inline-difference-is-caught",
        ),
        pytest.param(
            "def test_a():\n"
            "    t0 = time.time()\n    work()\n"
            "    elapsed = time.time() - t0\n    assert elapsed < 1.0\n",
            1,
            id="named-elapsed-is-caught",
        ),
        pytest.param(
            "def test_a():\n"
            "    start = time.perf_counter()\n    work()\n"
            "    end = time.perf_counter()\n    assert end - start < 0.5\n",
            1,
            id="two-readings-subtracted-is-caught",
        ),
        pytest.param(
            "def test_a():\n"
            "    start = perf_counter()\n    work()\n"
            "    assert perf_counter() - start < 0.5\n",
            1,
            id="bare-imported-clock-is-caught",
        ),
        pytest.param(
            "def test_a():\n"
            "    deadline = time.time() + 5\n"
            "    while time.time() < deadline:\n        poll()\n"
            "    assert done()\n",
            0,
            id="polling-deadline-is-allowed",
        ),
        pytest.param(
            "def test_a():\n"
            "    entry = Entry(retrieved_at=time.time(), ttl=300)\n"
            "    assert entry.ttl == 300\n",
            0,
            id="timestamp-in-a-constructor-is-allowed",
        ),
        pytest.param(
            "def test_a():\n"
            "    t0 = time.time()\n    work()\n"
            "    elapsed = time.time() - t0\n"
            "    logger.info('took %s', elapsed)\n    assert work_done()\n",
            0,
            id="measuring-without-asserting-is-allowed",
        ),
        pytest.param(
            # The second clock reading is bound one level deeper than the
            # subtraction that uses it. ast.walk is breadth-first, so a scanner
            # that collected bindings and tested them in one pass reached
            # `elapsed = end - start` while `end` was still unknown and called
            # it something other than a duration.
            "def test_a():\n"
            "    start = time.time()\n"
            "    if slow:\n        end = time.time()\n"
            "    elapsed = end - start\n    assert elapsed < 1.0\n",
            1,
            id="clock-bound-deeper-than-its-use-is-caught",
        ),
        pytest.param(
            # `elapsed` in the second test is not a clock span. A module-wide
            # pass would have carried the first test's binding into it and
            # accused correct code.
            "def test_a():\n"
            "    t0 = time.time()\n"
            "    elapsed = time.time() - t0\n"
            "    logger.info(elapsed)\n"
            "\n"
            "def test_b():\n"
            "    elapsed = budget_from_config()\n"
            "    assert elapsed < 1.0\n",
            0,
            id="a-name-does-not-leak-between-tests",
        ),
    ],
)
def test_elapsed_assertion_scanner_reads_synthetic_sources(
    source: str, expected: int
) -> None:
    """Positive and negative controls for the scanner above.

    ``tests/integration/`` is about to contain none of these patterns, which is
    the point of the fix and also means the prohibition would pass just as
    happily against a scanner that always returned nothing.
    """
    assert len(_elapsed_assertions(ast.parse(source))) == expected


# ---------------------------------------------------------------------------
# the functional gate is executed
# ---------------------------------------------------------------------------


def test_ci_actually_runs_the_functional_gate(pytestconfig: pytest.Config) -> None:
    """A workflow job must really run the live suite with the flag set.

    The suite existed and asserted 36 things, but was skipped unless
    FINOS_RUN_LIVE_MCP_TEST=1, and only scripts/go-live-gate.sh ever set it. So
    the one suite that drives the real server end to end never ran before a
    merge. Parsed from the YAML rather than grepped, because a comment naming the
    command, or the command sitting in a job that never runs, satisfies a grep.
    """
    root = _repo_root(pytestconfig)
    workflow = root / _PRE_COMMIT_WORKFLOW
    jobs = (yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}).get("jobs", {})
    assert jobs, f"{_PRE_COMMIT_WORKFLOW} declares no jobs"

    for suite, flag in _GATED_SUITES:
        running = []
        for name, job in jobs.items():
            for step in job.get("steps", []):
                if not isinstance(step, dict):
                    continue
                run = step.get("run", "")
                env = {**job.get("env", {}), **(step.get("env") or {})}
                flag_set = str(env.get(flag, "")) == "1" or f"{flag}=1" in run
                if suite in run and flag_set:
                    running.append(name)

        assert running, (
            f"No job in {_PRE_COMMIT_WORKFLOW} runs {suite} with {flag}=1. The "
            "suite skips itself without that flag, so the functional gate would "
            "silently pass without executing it."
        )


def test_a_pre_push_hook_runs_the_functional_gate(pytestconfig: pytest.Config) -> None:
    """Enforcement has to exist somewhere it can actually block.

    Branch protection is unavailable on this repository, so a red CI check is
    advisory. pre-push is the one point that stops the code leaving the machine.
    """
    root = _repo_root(pytestconfig)

    for suite, flag in _GATED_SUITES:
        matching = [
            hook
            for _repo, hook in _pre_commit_hooks(root)
            if suite in str(hook.get("entry", ""))
            and f"{flag}=1" in str(hook.get("entry", ""))
        ]
        assert matching, f"No pre-commit hook runs {suite} with {flag}=1"

        stages = {
            stage
            for hook in matching
            for stage in cast(list[str], hook.get("stages", []))
        }
        assert "pre-push" in stages, (
            f"the hook running {suite} declares stages={sorted(stages)}; it must "
            "run at pre-push, where it can still stop the push"
        )


def test_every_project_owned_hook_resolves_the_interpreter_through_the_shim(
    pytestconfig: pytest.Config,
) -> None:
    """No hook entry may name an interpreter itself.

    Every ``language: system`` entry used to begin with a bare ``python``. macOS
    ships no ``python``, and pre-commit does not prepend a virtualenv's ``bin/``
    to PATH even when it is invoked as ``venv/bin/python -m pre_commit``, so
    ruff, ruff-format, mypy, bandit, pylint and detect-secrets all died with
    ``Executable `python` not found`` before checking a single line (#56).

    ``python3`` is not the fix and must fail here too: on macOS that resolves to
    /usr/bin/python3, Python 3.9, which holds none of this project's tools. A
    hook that found it would report a missing dependency rather than a wrong
    interpreter, and would silently type-check 3.12 code with a 3.9 tool the
    moment anyone pip-installed one there.
    """
    root = _repo_root(pytestconfig)
    by_id = {str(hook.get("id")): hook for _repo, hook in _pre_commit_hooks(root)}

    expected = _PROJECT_OWNED_HOOK_IDS - _WRAPPER_DELEGATING_HOOK_IDS
    missing = sorted(expected - by_id.keys())
    assert not missing, (
        f"These hooks are declared project-owned but are absent from "
        f"{_PRE_COMMIT_CONFIG}: {missing}. A hook that quietly disappears takes "
        "its gate with it, and would make this check pass vacuously."
    )

    offenders = {}
    for hook_id in sorted(expected):
        entry = str(by_id[hook_id].get("entry", ""))
        if _PROJECT_PYTHON_SHIM not in entry:
            offenders[hook_id] = entry
        elif _BARE_INTERPRETER.search(entry):
            offenders[hook_id] = entry

    assert not offenders, (
        f"These hook entries name an interpreter instead of resolving one "
        f"through {_PROJECT_PYTHON_SHIM}: {offenders}. The shim is the single "
        "place that decides which Python runs a gate, and the only place that "
        "refuses to run one contradicting pyproject.toml."
    )


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        ("python -m ruff check", True),
        ("python3 -m mypy", True),
        ("python3.12 -m pylint src/", True),
        ("env FINOS_RUN_LIVE_MCP_TEST=1 python -m pytest -q", True),
        ("scripts/project-python.sh -m ruff check", False),
        ("env FINOS_RUN_LIVE_MCP_TEST=1 scripts/project-python.sh -m pytest", False),
        ("scripts/semgrep-isolated.sh", False),
        ("scripts/pip-audit-scan.sh", False),
    ],
)
def test_bare_interpreter_scanner_reads_synthetic_entries(
    entry: str, expected: bool
) -> None:
    """The scanner must fire on a named interpreter and not on the shim.

    The shim's own filename ends in ``-python.sh``, so a pattern that merely
    looked for ``python`` would flag every correctly-written entry and this
    guard would be reverted as noise rather than believed.
    """
    assert bool(_BARE_INTERPRETER.search(entry)) is expected


def test_the_filename_guard_reads_the_index_not_the_working_tree(
    pytestconfig: pytest.Config,
) -> None:
    """Invariant 16, first half: the guard may only judge staged files.

    A guard nobody can satisfy is a guard everyone bypasses. While this one
    walked the working tree it fired on vendored library files inside whatever
    virtualenv the contributor happened to create, and the documented remedy --
    extend the exclusion list -- was a list of directory *names*, so the next
    differently-named virtualenv reopened it. Reading the index closes the
    class rather than the instance: an ignored or untracked path is not in the
    index, so there is nothing left to exclude, and the hook that carried nine
    exclusions now carries none.
    """
    root = _repo_root(pytestconfig)
    by_id = {str(hook.get("id")): hook for _repo, hook in _pre_commit_hooks(root)}
    guard = by_id.get(_FILENAME_GUARD_ID)
    assert guard is not None, (
        f"{_PRE_COMMIT_CONFIG} declares no {_FILENAME_GUARD_ID} hook, so this "
        "check has nothing to measure."
    )

    entry = str(guard.get("entry", ""))
    assert _BLOCKED_FILENAME_SCANNER in entry, (
        f"{_FILENAME_GUARD_ID} no longer delegates to "
        f"{_BLOCKED_FILENAME_SCANNER}. Its behaviour is covered by "
        "tests/unit/test_blocked_filename_guard.py, which drives that script "
        "against a real index; an inlined entry escapes those tests entirely."
    )
    walk = _WORKING_TREE_WALK.search(entry)
    assert walk is None, (
        f"{_FILENAME_GUARD_ID} reaches into the working tree again via "
        f"{walk.group(0)!r}. Every path outside the index belongs to the "
        "contributor, not to this repository, and firing on one is what sent "
        "the whole hook set out with --no-verify."
    )

    scanner = root / _BLOCKED_FILENAME_SCANNER
    assert scanner.is_file(), f"{_BLOCKED_FILENAME_SCANNER} does not exist."
    body = scanner.read_text(encoding="utf-8")
    assert "--diff-filter=d" in body, (
        f"{_BLOCKED_FILENAME_SCANNER} no longer excludes staged deletions, so a "
        "file matching the rule can never be removed -- the guard blocks its "
        "own remedy. Measured on the pre-#84 hook, which is why the one tracked "
        "file that matched had become permanently unmodifiable."
    )


def test_exactly_one_hook_enforces_the_filename_rule(
    pytestconfig: pytest.Config,
) -> None:
    """Invariant 16, second half: one rule, one hook.

    Two hooks used to match on staged filenames. The absorbed one matched a
    path *segment* starting with the token, a strict subset of the survivor's
    substring rule, so it could never fire alone -- and it was named for
    *content* while it checked names, which is precisely the kind of hook an
    outside contributor cannot reason about. The content rule still has its own
    hook; what is forbidden is a second guard restating this one.
    """
    root = _repo_root(pytestconfig)
    hooks = [hook for _repo, hook in _pre_commit_hooks(root)]

    # Reading staged names is not the rule -- validate-static-fallback does
    # that to spot one source file. Enforcing *this* rule means reading staged
    # names and matching them against the token, or delegating to the scanner
    # that does.
    token = _FILENAME_GUARD_TOKEN
    staged_name_readers = sorted(
        str(hook.get("id"))
        for hook in hooks
        if _BLOCKED_FILENAME_SCANNER in str(hook.get("entry", ""))
        or (
            "--name-only" in str(hook.get("entry", ""))
            and token in str(hook.get("entry", "")).lower()
        )
    )
    assert staged_name_readers == [_FILENAME_GUARD_ID], (
        f"Expected {_FILENAME_GUARD_ID} to be the only hook matching on "
        f"staged filenames, found {staged_name_readers}. A second hook whose "
        "match set is contained in this one's can never fire on its own, and "
        "is one more thing an outsider must be told to ignore."
    )


def test_content_scan_allowlist_holds_only_files_that_still_need_it(
    pytestconfig: pytest.Config,
) -> None:
    """Every exemption must still be earned.

    The scan greps staged files for a literal string that six tracked files
    necessarily contain -- ignore rules, git configuration, the go-live gate's
    tracked-folder pattern, and the hook configuration declaring the scan. With
    the hooks installed that made each of them permanently uneditable, including
    the file that installs the hooks, which is a large part of why
    ``pre-commit install`` was never run here (#56).

    Both directions are asserted. A file listed but absent, or listed but no
    longer containing the pattern, is an exemption nobody is checking -- and it
    would let real content through under a rationale that expired.
    """
    root = _repo_root(pytestconfig)
    by_id = {str(hook.get("id")): hook for _repo, hook in _pre_commit_hooks(root)}
    scan = by_id.get(_CONTENT_SCAN_ID)
    assert scan is not None, (
        f"{_PRE_COMMIT_CONFIG} declares no {_CONTENT_SCAN_ID} hook, so "
        "this check has nothing to measure."
    )
    assert _BLOCKED_REFERENCE_SCANNER in str(scan.get("entry", "")), (
        f"{_CONTENT_SCAN_ID} no longer delegates to "
        f"{_BLOCKED_REFERENCE_SCANNER}. The allowlist lives there; inlining the "
        "logic again puts it back where nobody reads it."
    )

    scanner = root / _BLOCKED_REFERENCE_SCANNER
    assert scanner.is_file(), f"{_BLOCKED_REFERENCE_SCANNER} does not exist"
    source = scanner.read_text(encoding="utf-8")

    # The pattern is read from the scanner rather than restated here: writing it
    # into this file would make the test suite itself an offender.
    pattern_match = re.search(r"^readonly PATTERN='([^']+)'", source, re.MULTILINE)
    assert pattern_match, (
        f"{_BLOCKED_REFERENCE_SCANNER} declares no `readonly PATTERN=`, so this "
        "test cannot tell what it scans for."
    )
    pattern = re.compile(pattern_match.group(1))

    declared = set(re.findall(r'^\s*"([^"]+)"', source, re.MULTILINE))
    listed = declared & _CONTENT_SCAN_ALLOWLIST
    assert listed == _CONTENT_SCAN_ALLOWLIST, (
        "The allowlist in "
        f"{_BLOCKED_REFERENCE_SCANNER} and _CONTENT_SCAN_ALLOWLIST disagree. "
        f"Only in the test: {sorted(_CONTENT_SCAN_ALLOWLIST - declared)}. Both "
        "must be edited together, deliberately."
    )

    missing = sorted(
        name for name in _CONTENT_SCAN_ALLOWLIST if not (root / name).is_file()
    )
    assert not missing, (
        f"These files are exempted from {_CONTENT_SCAN_ID} but do not "
        f"exist: {missing}. Drop them from the allowlist."
    )

    unnecessary = sorted(
        name
        for name in _CONTENT_SCAN_ALLOWLIST
        if not pattern.search((root / name).read_text(encoding="utf-8"))
    )
    assert not unnecessary, (
        f"These files are exempted from {_CONTENT_SCAN_ID} but no longer "
        f"contain the pattern it scans for: {unnecessary}. The exemption has "
        "outlived its reason -- remove it, or the file can accumulate real "
        "references that nothing checks."
    )


def test_every_interpreter_call_site_resolves_through_the_shim(
    pytestconfig: pytest.Config,
) -> None:
    """Shell entry points must not pick an interpreter of their own.

    ``scripts/pip-audit-scan.sh`` used to carry a candidate list ending in
    ``python3.13 python3.12 python3.11 python3``, so whichever environment
    happened to exist won silently. The project virtualenv sat at fastmcp 2.14.5
    against a declared ``>=3.4.7,<4`` for six months and every gate entered
    through it audited that environment without comment (#89).

    Frozen call-site list, checked for presence: "every call site in an empty
    set resolves correctly" is true of any repository at all.
    """
    root = _repo_root(pytestconfig)

    absent = sorted(
        site for site in _INTERPRETER_CALL_SITES if not (root / site).is_file()
    )
    assert not absent, (
        f"These declared interpreter call sites do not exist: {absent}. Remove "
        "them from _INTERPRETER_CALL_SITES deliberately, or this check measures "
        "nothing."
    )

    offenders = sorted(
        site
        for site in _INTERPRETER_CALL_SITES
        if _PROJECT_PYTHON_SHIM not in _executable_content(root / site)
    )
    assert not offenders, (
        f"These scripts resolve an interpreter without going through "
        f"{_PROJECT_PYTHON_SHIM}: {offenders}. One place decides which Python "
        "runs a gate, and it is the only place that checks the resolved "
        "environment against pyproject.toml."
    )


def test_every_workflow_that_installs_the_project_creates_the_virtualenv(
    pytestconfig: pytest.Config,
) -> None:
    """A runner must resolve the interpreter the same way a laptop does.

    ``scripts/project-python.sh`` is virtualenv-based and deliberately has no
    fallback to a bare system interpreter, because that fallback is what let a
    stale environment become the audited artefact for six months (#89). Every
    workflow used to install straight into the runner's Python, so the shim
    would have found nothing to resolve and every gate would have failed on a
    runner while passing locally.

    Asserted per step rather than per file: a new job that installs the project
    and forgets the virtualenv is exactly the regression this catches, and it
    would be invisible in a file-level check that some other job already passes.
    """
    root = _repo_root(pytestconfig)
    workflows = sorted((root / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflows found, so this check measures nothing"

    installing, offenders = 0, []
    for workflow in workflows:
        document = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
        for job_name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps", []) or []:
                if not isinstance(step, dict):
                    continue
                script = str(step.get("run", ""))
                if _PROJECT_INSTALL not in script:
                    continue
                installing += 1
                if _VENV_CREATION not in script and "venv venv" not in script:
                    where = (
                        f"{workflow.name}:{job_name}:{step.get('name', '<unnamed>')}"
                    )
                    offenders.append(where)

    assert installing, (
        "No workflow step installs this project, so this check passed "
        "vacuously. Either the workflows changed shape or the marker "
        f"{_PROJECT_INSTALL!r} no longer matches."
    )
    assert not offenders, (
        f"These workflow steps install the project without first creating the "
        f"virtualenv: {offenders}. scripts/project-python.sh resolves "
        "venv/bin/python and will not fall back to the runner's interpreter, so "
        "every gate in that job would fail to start."
    )


# ---------------------------------------------------------------------------
# threads that outlive the test that joined them
# ---------------------------------------------------------------------------


def _timed_join_non_daemon_threads(source: str) -> tuple[list[int], int]:
    """Line numbers of thread constructions that need ``daemon=True``, and reach.

    A thread joined with a timeout is one the joining code has declared itself
    willing to continue without. If that thread is not a daemon, the declaration
    is false: the interpreter still waits for it at exit, so a stalled worker
    turns a bounded test failure into an unbounded hang after the session is
    over.

    What is deliberately *not* a timed join, because the caller waits however
    long it takes: a bare ``join()``, ``join(None)`` and ``join(timeout=None)``.
    The last two block forever exactly as the bare form does, so flagging them
    would tell an author to fix a thread the code genuinely waits on.

    A timeout counts whether passed positionally or by keyword: ``join(10)`` and
    ``join(timeout=10)`` mean the same thing, and a rule that saw only the
    second would be switched off by a semantically neutral edit.

    ``daemon`` counts however it is set before ``start()`` -- the ``daemon=True``
    keyword or a later ``thread.daemon = True`` -- since both are documented
    idioms. A non-literal (``daemon=flag``) is still rejected: it cannot be
    verified statically, and accepting it would let ``daemon=False`` through
    behind a name.

    Names are paired by how far they actually reach. An attribute such as
    ``self._thread`` is shared across a class -- every server helper here builds
    it in ``__init__`` and joins it in ``__exit__`` -- so it pairs within the
    enclosing ``ClassDef``. A plain local pairs within its own function, because
    two methods each holding a local named ``thread`` share nothing, and pairing
    those at class scope made one method's timed join convict the other's
    correctly bare-joined local. An invariant that accuses correct code is worse
    than no invariant.

    The constructor is recognised under whatever name the module imported it as:
    ``threading.Thread``, ``import threading as th`` giving ``th.Thread``, and
    ``from threading import Thread as T`` giving ``T``. A spelling the rule does
    not know is not merely unchecked, it is uncounted, so it defeats the reach
    floor in the same move.

    Reach is every such call, including ones this rule cannot pair --
    inside a comprehension, an ``append``, or a tuple unpack. Counting only what
    is paired would make the floor in the caller brittle against a refactor that
    changes nothing (rewriting two loop-built threads as a comprehension would
    have dropped the real tree from 7 to 5 and failed a clean tree).

    **Residuals, since a guard closes a route rather than a policy.** Those
    unpairable constructions are counted but not checked, so a thread built in a
    comprehension and later timed-joined is outside this rule; pairing it would
    need alias analysis. A ``threading.Thread`` *subclass* instantiated by its
    own name (``class W(threading.Thread)``, then ``W()``) is invisible here for
    the same reason -- the name says nothing about the base class.

    The third is the price of not accusing correct code. An attribute pairs at
    class scope, but with no enclosing class there is nothing shared to pair
    within, so ``h.thread = Thread(...)`` in one function and
    ``h.thread.join(timeout=5)`` in another are counted and never checked.
    Falling back to module scope would pair them -- and would also convict two
    unrelated functions that each happen to hold a local ``h``. Between a shape
    this misses and a shape it wrongly condemns, this file has already chosen:
    an invariant that accuses correct code is worse than no invariant. The tree
    holds none of these three shapes today.
    """
    tree = ast.parse(source)

    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    def _target_name(node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            base = _target_name(node.value)
            return f"{base}.{node.attr}" if base else None
        return None

    thread_names = {"Thread"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            thread_names.update(
                f"{alias.asname or alias.name}.Thread"
                for alias in node.names
                if alias.name == "threading"
            )
        elif isinstance(node, ast.ImportFrom) and node.module == "threading":
            thread_names.update(
                alias.asname or alias.name
                for alias in node.names
                if alias.name == "Thread"
            )

    def _is_thread_call(node: ast.AST) -> bool:
        return isinstance(node, ast.Call) and _target_name(node.func) in thread_names

    def _key(node: ast.AST, name: str) -> tuple[int, str]:
        """Pair within the class for an attribute, within the function for a local."""
        shared = "." in name
        enclosing_function: ast.AST | None = None
        walker = parents.get(node)
        while walker is not None:
            if isinstance(walker, (ast.FunctionDef, ast.AsyncFunctionDef)):
                enclosing_function = enclosing_function or walker
                if not shared:
                    break
            if isinstance(walker, ast.ClassDef) and shared:
                return (id(walker), name)
            walker = parents.get(walker)
        return (id(enclosing_function or tree), name)

    timed_joins: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
        ):
            continue
        if node.args:
            timeout: ast.expr | None = node.args[0]
        else:
            timeout = next((k.value for k in node.keywords if k.arg == "timeout"), None)
        if timeout is None:
            continue  # a bare join(); the caller waits however long it takes
        if isinstance(timeout, ast.Constant):
            if timeout.value is None:
                continue  # join(None) blocks forever too: the same promise
            if isinstance(timeout.value, (str, bytes)):
                continue  # a separator, so this is str.join, not Thread.join
        name = _target_name(node.func.value)
        if name:
            timed_joins.add(_key(node, name))

    made_daemon: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
        ):
            continue
        for target in node.targets:
            name = _target_name(target)
            if name and name.endswith(".daemon"):
                made_daemon.add(_key(node, name[: -len(".daemon")]))

    constructions = sum(1 for node in ast.walk(tree) if _is_thread_call(node))

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if value is None or not _is_thread_call(value):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [name for name in map(_target_name, targets) if name]
        keys = {_key(node, name) for name in names}
        if not keys & timed_joins or keys & made_daemon:
            continue
        assert isinstance(value, ast.Call)  # narrowed by _is_thread_call above
        daemon = next((k for k in value.keywords if k.arg == "daemon"), None)
        if daemon is None or not (
            isinstance(daemon.value, ast.Constant) and daemon.value.value is True
        ):
            offenders.append(value.lineno)
    return sorted(offenders), constructions


def _scan_threads_in(files: list[Path], root: Path) -> tuple[list[str], int]:
    """Apply the thread rule to each file, reporting offenders and reach.

    Extracted so the synthetic exercise below can run the *same* path the real
    tree runs, rather than only the inner scanner. The two differ exactly where
    a prefilter would sit, which is where this check previously had a hole: a
    substring gate on ``"threading.Thread"`` left ``from threading import
    Thread`` modules both unscanned and uncounted, and no test of the scanner
    alone could see it.
    """
    offenders: list[str] = []
    constructions = 0
    for path in files:
        found, seen = _timed_join_non_daemon_threads(path.read_text(encoding="utf-8"))
        constructions += seen
        offenders.extend(f"{path.relative_to(root)}:{lineno}" for lineno in found)
    return offenders, constructions


def test_every_timed_join_thread_is_a_daemon(pytestconfig: pytest.Config) -> None:
    """A thread the suite is willing to abandon must not outlive the suite.

    ``tests/integration/test_cross_loop_teardown.py`` started its worker thread
    without ``daemon=True`` while joining it with ``timeout=10``. The whole
    purpose of that thread is to host an event loop that dies, so it is the
    least predictable part of the module; a loopback stall would have expired
    the join, failed the test cleanly, and then blocked interpreter exit for as
    long as the request's own timeouts allowed. That presents as a CI timeout
    with no failing test attached to it, which is the least diagnosable failure
    shape available.

    What this asserts and what it does not: it is a *static* assertion that the
    flag is present at the construction site. It cannot observe interpreter
    exit, so it does not prove the flag has the effect claimed above -- it
    prevents the decision from being deleted as noise, which is the failure mode
    a one-word fix in a test helper actually has.
    """
    root = _repo_root(pytestconfig)
    # conftest modules too, not only collected test files: a fixture is the most
    # natural place to start a loopback server and time-join it in teardown, and
    # `test_*.py` globbing would exempt exactly that thread from the rule.
    files = _collected_test_files(root) + sorted(
        path
        for path in (root / "tests").rglob("conftest.py")
        if "__pycache__" not in path.parts
    )
    offenders, constructions = _scan_threads_in(files, root)

    # Reach is 7 today. The floor sits well below that rather than just beneath
    # it: two of the seven are bare-join threads this rule can never check, so a
    # floor of 6 would fail against a clean tree the moment two thread-using
    # helpers were deleted or merged. It exists to catch a scanner that matches
    # nothing, and 4 catches that just as well.
    assert constructions >= 4, (
        f"only {constructions} thread constructions found across {len(files)} "
        "test and conftest files; this invariant would pass by examining "
        "almost nothing"
    )
    assert not offenders, (
        f"These threads are joined with a timeout but are not daemons, so a "
        f"stalled worker blocks interpreter exit after the test has already "
        f"failed: {offenders}. Pass daemon=True at the construction site."
    )


#: Synthetic modules for the thread scanner, exercised in both directions. The
#: real tree is expected to be clean, so a scanner that found nothing anywhere
#: would satisfy the invariant above without ever running its rule.
_THREAD_SOURCES = [
    pytest.param(
        "import threading\nt = threading.Thread(target=f)\nt.join(timeout=10)\n",
        [2],
        id="timed-join-non-daemon-is-flagged",
    ),
    pytest.param(
        "import threading\n"
        "t = threading.Thread(target=f, daemon=True)\n"
        "t.join(timeout=10)\n",
        [],
        id="timed-join-daemon-is-fine",
    ),
    pytest.param(
        "import threading\nt = threading.Thread(target=f)\nt.join()\n",
        [],
        id="bare-join-is-outside-the-rule",
    ),
    pytest.param(
        "import threading\n"
        "class S:\n"
        "    def __init__(self):\n"
        "        self._thread = threading.Thread(target=f)\n"
        "    def stop(self):\n"
        "        self._thread.join(timeout=5)\n",
        [4],
        id="attribute-target-is-flagged",
    ),
    pytest.param(
        "import threading\n"
        "t = threading.Thread(target=f, daemon=flag)\n"
        "t.join(timeout=1)\n",
        [2],
        id="daemon-must-be-a-literal-true",
    ),
    pytest.param(
        "import threading\nt = threading.Thread(target=f)\nt.join(10)\n",
        [2],
        id="positional-timeout-counts-too",
    ),
    pytest.param(
        "from threading import Thread\nt = Thread(target=f)\nt.join(timeout=10)\n",
        [2],
        id="from-import-form-is-flagged",
    ),
    pytest.param(
        "import threading\n"
        "class A:\n"
        "    def __init__(self):\n"
        "        self._thread = threading.Thread(target=f)\n"
        "    def stop(self):\n"
        "        self._thread.join()\n"
        "class B:\n"
        "    def __init__(self):\n"
        "        self._thread = threading.Thread(target=f, daemon=True)\n"
        "    def stop(self):\n"
        "        self._thread.join(timeout=5)\n",
        [],
        id="one-class-timed-join-does-not-convict-anothers-bare-join",
    ),
    pytest.param(
        "import threading\n"
        "class T:\n"
        "    def test_a(self):\n"
        "        thread = threading.Thread(target=f)\n"
        "        thread.join()\n"
        "    def test_b(self):\n"
        "        thread = threading.Thread(target=g, daemon=True)\n"
        "        thread.join(timeout=1)\n",
        [],
        id="two-methods-holding-a-local-of-the-same-name-share-nothing",
    ),
    pytest.param(
        "import threading\nt = threading.Thread(target=f)\nt.join(None)\n",
        [],
        id="join-none-blocks-forever-so-it-is-not-a-timed-join",
    ),
    pytest.param(
        "import threading\nt = threading.Thread(target=f)\nt.join(timeout=None)\n",
        [],
        id="keyword-none-blocks-forever-too",
    ),
    pytest.param(
        "import threading\n"
        "t = threading.Thread(target=f)\n"
        "t.daemon = True\n"
        "t.join(timeout=1)\n",
        [],
        id="daemon-set-by-assignment-is-still-daemon",
    ),
    pytest.param(
        "import threading as th\nt = th.Thread(target=f)\nt.join(timeout=1)\n",
        [2],
        id="module-alias-is-still-threading",
    ),
    pytest.param(
        "from threading import Thread as T\nt = T(target=f)\nt.join(timeout=1)\n",
        [2],
        id="constructor-alias-is-still-Thread",
    ),
    pytest.param(
        "import threading\n"
        "def go():\n"
        "    t = threading.Thread(target=f, daemon=True)\n"
        "    t.join(', ')\n",
        [],
        id="a-string-argument-is-a-separator-not-a-timeout",
    ),
    pytest.param(
        "import threading\n"
        "def go():\n"
        "    t = threading.Thread(target=f)\n"
        "    t.join(', ')\n",
        [],
        id="str-join-does-not-convict-a-thread-of-the-same-name",
    ),
]


@pytest.mark.parametrize(("source", "expected"), _THREAD_SOURCES)
def test_thread_scanner_reads_synthetic_modules(
    source: str, expected: list[int]
) -> None:
    """The scanner must discriminate, not merely return an empty list."""
    assert _timed_join_non_daemon_threads(source)[0] == expected


def test_thread_scan_reaches_a_file_the_dotted_spelling_would_miss(
    tmp_path: Path,
) -> None:
    """The scan itself, not just the scanner, must reach every spelling.

    ``from threading import Thread`` produces no ``threading.Thread`` text, so
    any substring prefilter in front of the scan silently drops such a file --
    and drops it from the reach count too, so the floor that exists to prove the
    rule ran would not notice either. Written to a real file and scanned through
    the real entry point, because a probe that stops at the inner function
    cannot land where the prefilter would.
    """
    offender = tmp_path / "test_from_import_thread.py"
    offender.write_text(
        "from threading import Thread\nt = Thread(target=f)\nt.join(timeout=10)\n",
        encoding="utf-8",
    )

    found, constructions = _scan_threads_in([offender], tmp_path)

    assert constructions == 1, (
        "the scan did not reach the file at all, so its reach count cannot "
        "prove the rule ran"
    )
    assert found == ["test_from_import_thread.py:2"], found


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "import threading\nts = [threading.Thread(target=f) for _ in range(4)]\n",
            1,
            id="comprehension",
        ),
        pytest.param(
            "import threading\nts = []\nts.append(threading.Thread(target=f))\n",
            1,
            id="append",
        ),
        pytest.param(
            "import threading\nt = threading.Thread(target=f)\n",
            1,
            id="plain-assignment",
        ),
    ],
)
def test_thread_scanner_counts_constructions_it_cannot_pair(
    source: str, expected: int
) -> None:
    """Reach must not depend on the spelling, or the floor becomes brittle.

    The floor above exists to prove the rule ran against real code. If it
    counted only constructions this rule can pair with a join, then rewriting
    two loop-built threads as comprehensions -- a refactor that changes nothing
    -- would drop the real tree from 7 countable constructions to 5 and fail the
    floor against a perfectly clean tree.
    """
    assert _timed_join_non_daemon_threads(source)[1] == expected


# ---------------------------------------------------------------------------
# Invariant 17: the two development-only gates share one definition, and the
# ref-reading one is actually wired into the release script.
# ---------------------------------------------------------------------------

# The ref-reading half of the pair. Gate 1 asks "is anything development-only
# tracked" of `git ls-files`, which is HEAD; tag v0.1.0 published a tree of
# eight such files for months while Gate 1 reported PASS (#130).
_PUBLISHED_REF_SCANNER = "scripts/scan-published-refs.sh"
_DEV_ONLY_PATTERN_HOME = "scripts/dev-only-paths.sh"

# Assembled from the name and the operator so this file does not match its own
# search -- the same discipline scripts/scan-blocked-references.sh uses.
_DEV_ONLY_ASSIGNMENT = re.compile(r"\b" + "DEV_ONLY_PATTERN" + r"\s*=")


def test_go_live_gate_reads_the_refs_on_the_remote(
    pytestconfig: pytest.Config,
) -> None:
    """A scanner nothing calls is a scanner that never runs.

    #56 was a defect of this exact shape: the pre-push functional gate was
    declared, correct, and installed nowhere, so the suite it names never ran.
    Read from the executable content so a comment naming the script cannot
    satisfy it.
    """
    root = _repo_root(pytestconfig)
    scanner = root / _PUBLISHED_REF_SCANNER
    assert scanner.is_file(), f"{_PUBLISHED_REF_SCANNER} does not exist"

    gate = _executable_content(root / "scripts/go-live-gate.sh")
    assert _PUBLISHED_REF_SCANNER in gate, (
        f"{_PUBLISHED_REF_SCANNER} exists but scripts/go-live-gate.sh does not "
        "run it, so no release check reads the refs already on the remote -- "
        "which is the whole of #130."
    )


def test_the_development_only_pattern_has_exactly_one_definition(
    pytestconfig: pytest.Config,
) -> None:
    """Two gates, one rule.

    Gate 1 reads the index and Gate 9 reads the remote's refs, but they must
    agree on *what* they are looking for. A second assignment is how they start
    disagreeing: the index gate learns about a new directory and the ref gate
    keeps publishing it. Enumerated from the tracked tree rather than a frozen
    list, so a copy in a file nobody thought of is still caught.
    """
    root = _repo_root(pytestconfig)
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()

    definitions = sorted(
        name
        for name in tracked
        if _DEV_ONLY_ASSIGNMENT.search(
            (root / name).read_text(encoding="utf-8", errors="ignore")
        )
    )
    assert definitions == [_DEV_ONLY_PATTERN_HOME], (
        "The development-only path pattern must be assigned in exactly one "
        f"tracked file, {_DEV_ONLY_PATTERN_HOME}. Found: {definitions}."
    )


# ---------------------------------------------------------------------------
# 18. Every declared tool is actually reachable from something that runs it.
# ---------------------------------------------------------------------------

#: Where a tool can be *invoked* from. A tool named nowhere in these is a tool
#: no developer and no CI job ever runs.
_TOOL_CALL_SITES = ("scripts", ".github/workflows", ".pre-commit-config.yaml")

#: Declared dependency groups that exist to hold *tools*. ``test`` is excluded:
#: it holds libraries a test imports, which invariant 18 already accepts via the
#: import check, and naming it here would say these three are the only groups.
_TOOL_GROUPS = ("dev", "security")

#: Tools declared but not yet invoked, each with the issue that owns the call.
#:
#: This is deliberately **not** an exclusion list. The second assertion below
#: requires every entry to still be declared *and* still unused, so an entry
#: that gets wired up, or whose package is dropped, fails this test until the
#: line is deleted -- the register dies by removal, the way a suppression must.
_TOOLS_PENDING_A_DECISION: dict[str, str] = {}


def _declared_tools(root: Path) -> dict[str, str]:
    """Return ``{distribution name: group}`` for every declared tool."""
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    groups = config["project"]["optional-dependencies"]
    return {
        re.split(r"[<>=!\[;]", requirement)[0].strip(): group
        for group in _TOOL_GROUPS
        for requirement in groups.get(group, ())
    }


def _invocation_spellings(distribution: str) -> set[str]:
    """Return every name a call site could invoke ``distribution`` by.

    A tool is invoked by its *console script*, which need not be its
    distribution name -- ``pip-tools`` is run as ``pip-compile``, ``pytest`` as
    ``py.test``. Restating a match rule instead of asking the package for its
    own entry points is how a guard comes to match one spelling and miss
    another, so the scripts are read from installed metadata.

    **Residual, stated rather than implied:** when a declared tool is *not*
    installed there is no metadata to read, and only the distribution name is
    matched. A tool that is both uninstalled and invoked solely under a
    differently-named console script would be reported unused. Every tool this
    project declares is installed by the ``pip install -e '.[dev,security]'``
    that CI and ``scripts/setup-dev.sh`` both run, so that case is reachable
    only in a partial local install, where the register above is the record.
    """
    spellings = {
        distribution,
        distribution.replace("-", "_"),
        distribution.replace("_", "-"),
    }
    try:
        metadata = importlib.metadata.distribution(distribution)
    except importlib.metadata.PackageNotFoundError:
        return spellings
    spellings.update(
        entry_point.name
        for entry_point in metadata.entry_points
        if entry_point.group == "console_scripts"
    )
    return spellings


def _is_invoked(root: Path, distribution: str) -> bool:
    """True when some script, workflow or hook names the tool."""
    pattern = re.compile(
        r"(?:^|[^A-Za-z0-9_.-])(?:"
        + "|".join(
            re.escape(name) for name in sorted(_invocation_spellings(distribution))
        )
        + r")(?:[^A-Za-z0-9_-]|$)"
    )
    for call_site in _TOOL_CALL_SITES:
        target = root / call_site
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        for candidate in candidates:
            if not candidate.is_file():
                continue
            try:
                if pattern.search(candidate.read_text(encoding="utf-8")):
                    return True
            except (UnicodeDecodeError, OSError):
                continue
    return False


def _is_imported(root: Path, distribution: str) -> bool:
    """True when source or tests import the tool as a library."""
    module = distribution.replace("-", "_")
    pattern = re.compile(rf"^\s*(?:import|from)\s+{re.escape(module)}\b", re.MULTILINE)
    return any(
        pattern.search(path.read_text(encoding="utf-8"))
        for directory in ("src", "tests")
        for path in (root / directory).rglob("*.py")
    )


def _is_a_pytest_plugin_in_use(root: Path, distribution: str) -> bool:
    """True for a ``pytest-*`` plugin that ``[tool.pytest.ini_options]`` configures.

    pytest loads such a plugin from its entry point, so nothing imports or
    invokes it; what shows it is in use is an option of its own in the pytest
    configuration (``asyncio_mode`` for ``pytest-asyncio``). Recognised as a
    class, by the option's prefix, rather than by naming each plugin: the only
    import of ``pytest_asyncio`` in the tree left with a deleted test file
    (#302), and the plugin had been running every async test all along.
    """
    if not distribution.lower().startswith("pytest-"):
        return False
    prefix = distribution[len("pytest-") :].lower().replace("-", "_")
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    options = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {})
    return any(key.lower().startswith(prefix) for key in options)


def _is_type_stub(distribution: str) -> bool:
    """True for a PEP 561 stub-only package, which nothing imports or invokes.

    ``types-PyYAML`` is consumed by mypy through the ``types-`` naming
    convention itself, never by an import or a call site. Recognising the
    *class* keeps it out of the register below; listing it by name would make
    the remedy for a second stub "add one more entry", which is the shape this
    repository has already had to unwind twice.
    """
    return distribution.lower().startswith("types-")


def test_every_declared_tool_is_invoked_or_imported(
    pytestconfig: pytest.Config,
) -> None:
    """A tool nothing runs is a dependency with no benefit and a full CVE surface.

    ``safety`` was declared in the ``security`` extra and invoked by no script,
    no workflow, no hook, no import and no document. It pulled in ``nltk``,
    which acquired an advisory with no fix version, and the ``pip-audit``
    pre-commit hook then failed on **every commit to every branch** -- for a
    scanner nobody had ever run. The cost of an unused tool is not zero; it is
    its entire transitive dependency tree's vulnerability surface.
    """
    root = _repo_root(pytestconfig)
    unused = {
        distribution: group
        for distribution, group in _declared_tools(root).items()
        if not _is_type_stub(distribution)
        and not _is_invoked(root, distribution)
        and not _is_imported(root, distribution)
        and not _is_a_pytest_plugin_in_use(root, distribution)
        and distribution not in _TOOLS_PENDING_A_DECISION
    }
    assert not unused, (
        "every declared tool must be invoked by a script, workflow or hook, "
        "imported as a library, configured as a pytest plugin, or registered "
        "in _TOOLS_PENDING_A_DECISION "
        "with the issue that owns the call. Unused: "
        + ", ".join(
            f"{name} (declared in '{group}')" for name, group in sorted(unused.items())
        )
    )


def _stale_pending_tools(root: Path, register: Iterable[str]) -> dict[str, str]:
    """Return ``{distribution: why}`` for each entry that no longer belongs."""
    declared = _declared_tools(root)
    return {
        distribution: (
            "no longer declared"
            if distribution not in declared
            else "now invoked or imported"
        )
        for distribution in register
        if distribution not in declared
        or _is_invoked(root, distribution)
        or _is_imported(root, distribution)
    }


def test_the_pending_tool_register_dies_by_removal(
    pytestconfig: pytest.Config, tmp_path: Path
) -> None:
    """A register entry must expire when the thing it records stops being true.

    Without this, wiring a registered tool into a script -- or dropping its
    package -- would leave its line here forever, and the register would drift
    into the exclusion list it is written not to be. ``pip-tools`` was the one
    entry, and left this way when #54 dropped the package; the register is
    empty, which is its intended resting state.

    An empty register gives the check nothing to read, so it is first run on a
    small tree where three entries must expire and a fourth must stay (#199).
    """
    (tmp_path / "pyproject.toml").write_text(
        "[project.optional-dependencies]\n"
        'dev = ["invoked-tool>=1", "imported_tool", "idle-tool"]\n',
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "check.sh").write_text(
        "invoked-tool --strict\n", encoding="utf-8"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_it.py").write_text(
        "import imported_tool\n", encoding="utf-8"
    )
    register = ["dropped-tool", "invoked-tool", "imported_tool", "idle-tool"]
    assert _stale_pending_tools(tmp_path, register) == {
        "dropped-tool": "no longer declared",
        "invoked-tool": "now invoked or imported",
        "imported_tool": "now invoked or imported",
    }

    root = _repo_root(pytestconfig)
    stale = _stale_pending_tools(root, _TOOLS_PENDING_A_DECISION)
    assert not stale, (
        "_TOOLS_PENDING_A_DECISION must contain only tools that are still "
        "declared and still unused; delete the resolved entries: "
        + ", ".join(f"{name} ({why})" for name, why in sorted(stale.items()))
    )


# ---------------------------------------------------------------------------
# 20. Every configured tool is one something actually runs.
# ---------------------------------------------------------------------------

#: Configuration file -> the tool it configures.
#:
#: Invariant 18 asks the same question of every tool this project *declares*,
#: and that is exactly the gap this closes: ``.gitleaks.toml`` sat in the tree
#: configuring a secret scanner that was never declared, never installed and
#: never run, so invariant 18 could not see it (#71). A tool can be configured
#: without being declared -- gitleaks and docker are not Python distributions
#: at all -- so the config file is the only surface that names them.
#:
#: Like ``_TOOLS_PENDING_A_DECISION``, this map **dies by removal**: every path
#: here is asserted to exist, so deleting a config without deleting its entry
#: fails. Otherwise a stale entry would sit here describing a file that is gone,
#: and the map would drift into a list of things that used to be true.
_CONFIGURED_TOOLS = {
    ".pre-commit-config.yaml": "pre-commit",
    ".secrets.baseline": "detect-secrets",
    "config/security/bandit.yml": "bandit",
    "config/security/semgrep.yml": "semgrep",
}

#: Files under ``config/`` that configure no tool, each with why not.
#:
#: This is the one place the sweep below can be told to look away, so an entry
#: is a claim about a file, not a way to silence it -- and every path here is
#: asserted to exist, so it dies by removal like the map above. ``config/``
#: once held a third kind of file, dependency data a script installed from;
#: that lock is gone (#167), and tests/unit/test_workflow_triggers.py refuses
#: another one anywhere in the tree.
_CONFIG_DIR_NON_CONFIGURATION = {
    "config/README.md": "documentation describing the directory itself",
}


def test_every_configured_tool_is_declared_or_invoked(
    pytestconfig: pytest.Config,
) -> None:
    """A config file for a tool nothing runs advertises coverage nobody has.

    ``.gitleaks.toml`` declared five secret-detection rules and an allowlist for
    1.8 KB, and no workflow, hook or script had ever run gitleaks (#71). The
    file's only effect was on a reader: it made this repository look like it was
    scanned by two secret scanners when it was scanned by one.

    It could not have run even if something had invoked it. Four of its five
    rules used regex backreferences (``\\1``, ``\\2``), which Go's RE2 engine
    cannot compile, so loading the file panics gitleaks outright -- verified
    against gitleaks 8.30.1. A configuration nobody runs is also a
    configuration nobody has ever validated.

    This asks invariant 18's question of a different surface. Invariant 18
    covers tools *declared* in ``pyproject.toml``; a tool can be configured
    without being declared, and gitleaks was. ``_is_invoked`` is reused rather
    than restated, and its stated residual about console scripts does not reach
    here: a non-Python tool has no entry points, so its binary name is the only
    spelling there is.
    """
    root = _repo_root(pytestconfig)

    missing = [path for path in _CONFIGURED_TOOLS if not (root / path).is_file()]
    assert not missing, (
        f"_CONFIGURED_TOOLS names configuration files that do not exist: {missing}. "
        "The map dies by removal: delete the entry along with the file, so it "
        "cannot decay into a record of tools this project used to configure."
    )

    declared = _declared_tools(root)
    unrun = {
        path: tool
        for path, tool in _CONFIGURED_TOOLS.items()
        if tool not in declared and not _is_invoked(root, tool)
    }
    assert not unrun, (
        f"These files configure a tool that nothing declares or invokes: {unrun}. "
        "A configuration for a tool no script, workflow or hook runs claims "
        "coverage this repository does not have. Wire the tool in, or delete "
        "the configuration."
    )


def test_every_file_under_config_names_the_tool_it_configures(
    pytestconfig: pytest.Config,
) -> None:
    """The map above is only a guard while nothing can arrive outside it.

    ``_CONFIGURED_TOOLS`` is hand-maintained, so on its own the remedy for a new
    unrun tool config would be "do not add it to the map". ``config/`` is small and exists
    to hold configuration, which makes it the one directory where every file can
    be required to say what it is -- either the tool it configures, or why it
    configures none. Both lists are asserted against the tree, so neither can
    outlive what it describes.

    The residual is stated rather than implied: this closes ``config/``, not the
    repository root. A new tool config dropped at the root is still reachable
    only through the map. Root configuration is a small, slow-changing set that
    a reviewer sees in the diff, while ``config/`` is where a new ruleset would
    naturally land.
    """
    root = _repo_root(pytestconfig)
    config_dir = root / "config"

    tracked = subprocess.run(
        ["git", "ls-files", "-z", "config"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = [entry for entry in tracked.split("\0") if entry]
    assert paths, (
        "found no tracked files under config/, so this invariant would pass by "
        "scanning nothing. It exists to check that directory's contents."
    )
    assert config_dir.is_dir(), "config/ is tracked but absent from the worktree"

    absent = [
        path for path in _CONFIG_DIR_NON_CONFIGURATION if not (root / path).is_file()
    ]
    assert not absent, (
        f"_CONFIG_DIR_NON_CONFIGURATION names files that do not exist: {absent}. "
        "It dies by removal for the same reason _CONFIGURED_TOOLS does: an "
        "exemption outliving its file is how a reasoned list becomes a habit."
    )

    unmapped = [
        path
        for path in paths
        if path not in _CONFIG_DIR_NON_CONFIGURATION and path not in _CONFIGURED_TOOLS
    ]
    assert not unmapped, (
        f"These files under config/ are not named by _CONFIGURED_TOOLS: {unmapped}. "
        "Add each one with the tool it configures, so the invariant above checks "
        "that something actually runs it -- or, if it configures no tool, say so "
        "in _CONFIG_DIR_NON_CONFIGURATION."
    )


# ---------------------------------------------------------------------------
# Invariant 21: the CODEOWNERS owner check runs both before a merge and at
# release.
# ---------------------------------------------------------------------------

_CODEOWNERS_CHECK = "scripts/check-codeowners.sh"


def test_codeowners_check_runs_in_ci_and_at_release(
    pytestconfig: pytest.Config,
) -> None:
    """Whether an owner exists is a question only GitHub can answer.

    Every line of ``.github/CODEOWNERS`` named an unrelated account, and
    nothing noticed: the file was syntactically fine, so no local
    tool could tell a real owner from a stranger (#158). The check therefore
    asks GitHub's ``codeowners/errors`` endpoint, and a unit test can only
    prove the check is wired in. Parsed from the YAML with comments stripped,
    so prose naming the script does not count as running it.
    """
    root = _repo_root(pytestconfig)
    assert (root / _CODEOWNERS_CHECK).is_file(), f"{_CODEOWNERS_CHECK} does not exist"

    gate = _executable_content(root / "scripts/go-live-gate.sh")
    assert _CODEOWNERS_CHECK in gate, (
        f"scripts/go-live-gate.sh does not run {_CODEOWNERS_CHECK}, so a release "
        "can go out with review requests routed to an account that is not ours."
    )

    workflow = root / _PRE_COMMIT_WORKFLOW
    document = yaml.safe_load(workflow.read_text(encoding="utf-8")) or {}
    # PyYAML reads the bare key `on` as the boolean True.
    triggers = document.get("on", document.get(True)) or {}
    assert "pull_request" in triggers, (
        f"{_PRE_COMMIT_WORKFLOW} does not run on pull_request, so no job in it "
        "can check CODEOWNERS before a merge."
    )
    jobs = document.get("jobs", {})
    assert jobs, f"{_PRE_COMMIT_WORKFLOW} declares no jobs"
    running = [
        name
        for name, job in jobs.items()
        for step in job.get("steps", [])
        if isinstance(step, dict)
        and _CODEOWNERS_CHECK in _COMMENT.sub("", str(step.get("run", "")))
    ]
    assert running, (
        f"No job in {_PRE_COMMIT_WORKFLOW} runs {_CODEOWNERS_CHECK}, so a pull "
        "request that breaks an owner merges without anything asking GitHub."
    )
