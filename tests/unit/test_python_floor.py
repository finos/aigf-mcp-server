"""Guards that the Python floor the project declares is one the project tests.

``pyproject.toml`` declared ``requires-python = ">=3.10"`` while both CI
matrices started at 3.11, and two test modules and two scripts imported
``tomllib``, which 3.10 does not have: the suite could not be collected on an
interpreter the package metadata invited (#174). Dependabot resolved on 3.10
for the same reason.

The floor is read from ``requires-python`` and every other statement of it is
compared with that: the CI matrix, the classifiers, the ruff and mypy targets,
and each place a document, script or workflow tells a reader which Python they
need.

Residual: the prose scan knows the spellings in ``_FLOOR_CLAIM``, and counts
one only when the line it starts on names Python, so that ``fastmcp 3.2+`` is
not read as a floor. A floor stated another way ("needs 3.10 at least", a bare
"- Python 3.10") is not seen.

The CI matrix is two lists since #238: one version on a pull request, every
version on any other event. "What CI tests" below means the second list. The
matrix in ``dependabot-security-validation.yml`` must include all of it.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.specifiers import SpecifierSet
from packaging.version import Version

_WORKFLOWS = ".github/workflows"
_CI_WORKFLOW = ".github/workflows/security-analysis.yml"
_CI_JOB = "security-scan"
_DEPENDABOT_WORKFLOW = ".github/workflows/dependabot-security-validation.yml"

# The CI matrix: one list for a pull request, another for every other event.
_EVENT_MATRIX = re.compile(
    r"\$\{\{ github\.event_name == 'pull_request' "
    r"&& fromJSON\('(?P<pull_request>\[[^']*\])'\) "
    r"\|\| fromJSON\('(?P<otherwise>\[[^']*\])'\) \}\}"
)

_CLASSIFIER = re.compile(r"Programming Language :: Python :: (3\.\d+)$")

_MAJOR_MINOR = re.compile(r"(?P<major>\d+)\.(?P<minor>\d+)")

# Where a reader is told which Python they need: every Markdown file at the
# repository root, and these directories. The tests are left out by location and
# the point-in-time record by name: both quote past floors on purpose.
_CLAIM_SURFACES = (":(glob)*.md", "docs/", "scripts/", ".github/")
_POINT_IN_TIME_RECORDS = {"CHANGELOG.md"}

# `3.11+`, the badge's `3.11%2B`, `3.11 or newer`, `>=3.11`, and the
# `sys.version_info >= (3, 11)` a script checks before it starts.
_FLOOR_CLAIM = re.compile(
    r"""
      \b3\.(?P<suffixed>\d+)(?:\+|%2B|\s+or\s+(?:newer|later|higher|above))
    | >=\s*3\.(?P<specifier>\d+)\b(?!\.\d)
    | version_info\s*>=\s*\(\s*3\s*,\s*(?P<tuple>\d+)\s*\)
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Fewer claims than this and the scan has stopped reading the files that state
# the floor, not found them all correct.
_MIN_CLAIMS = 12


def _repo_root(pytestconfig: pytest.Config) -> Path:
    return Path(str(pytestconfig.rootpath))


def _pyproject(root: Path) -> dict[str, Any]:
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _floor(root: Path) -> tuple[int, int]:
    """The lowest interpreter ``requires-python`` admits, as ``(3, minor)``."""
    declared = _pyproject(root)["project"]["requires-python"]
    specifiers = list(SpecifierSet(declared))
    assert len(specifiers) == 1 and specifiers[0].operator == ">=", (
        f"requires-python is {declared!r}; these checks read a single `>=3.N` floor"
    )
    # `>=3.11.0` is the same floor as `>=3.11`. `>=3.11.4`, `>=3.11rc1` and
    # `>=3` are not a minor version the other statements can be compared with.
    version = Version(specifiers[0].version)
    release = version.release
    assert (
        str(version) == ".".join(map(str, release))
        and len(release) >= 2
        and not any(release[2:])
    ), (
        f"requires-python is {declared!r}; the floor must be a plain `3.N`, with "
        "no patch release, pre-release or other suffix"
    )
    assert release[0] == 3, f"requires-python is {declared!r}, not a Python 3 floor"
    return 3, release[1]


def _version(value: object) -> tuple[int, int]:
    # An unquoted 3.10 in YAML is the float 3.1, here and in setup-python alike.
    version = _MAJOR_MINOR.fullmatch(str(value))
    assert version, (
        f"{value!r} is not a `major.minor` Python version, so it cannot be "
        "compared with the floor"
    )
    return int(version["major"]), int(version["minor"])


def _python_versions(node: object) -> list[tuple[int, int]]:
    """Every literal ``python-version`` under *node*; expressions are skipped."""
    found: list[tuple[int, int]] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "python-version":
                values = value if isinstance(value, list) else [value]
                found += [_version(item) for item in values if "${{" not in str(item)]
            else:
                found += _python_versions(value)
    elif isinstance(node, list):
        for item in node:
            found += _python_versions(item)
    return found


def _ci_matrices(root: Path) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """What the CI job runs on a pull request, and on every other event (#238)."""
    workflow = yaml.safe_load((root / _CI_WORKFLOW).read_text(encoding="utf-8"))
    matrix = workflow["jobs"][_CI_JOB]["strategy"]["matrix"]["python-version"]
    shape = _EVENT_MATRIX.fullmatch(str(matrix))
    assert shape, (
        f"the {_CI_JOB} matrix in {_CI_WORKFLOW} is no longer one list for pull "
        f"requests and another for every other event: {matrix!r}"
    )
    on_pull_request, otherwise = (
        [_version(item) for item in json.loads(shape[name])]
        for name in ("pull_request", "otherwise")
    )
    assert on_pull_request and otherwise, (
        f"{_CI_WORKFLOW} job {_CI_JOB} tests no Python version on some event"
    )
    return on_pull_request, otherwise


def _ci_matrix(root: Path) -> list[tuple[int, int]]:
    """Every version CI tests: the list a push, the schedule and a dispatch run."""
    return _ci_matrices(root)[1]


def _claims(text: str) -> list[tuple[int, int]]:
    """Every Python floor *text* states, as ``(line number, minor version)``.

    The whole text is searched, not each line, so that "3.10 or" wrapped onto
    "newer" is still read.
    """
    claims: list[tuple[int, int]] = []
    for match in _FLOOR_CLAIM.finditer(text):
        start = text.rfind("\n", 0, match.start()) + 1
        end = text.find("\n", match.start())
        line = text[start : end if end != -1 else len(text)]
        if match["tuple"] is None and "python" not in line.lower():
            continue
        minor = next(group for group in match.groups() if group is not None)
        claims.append((text.count("\n", 0, match.start()) + 1, int(minor)))
    return claims


def _declaring(tmp_path: Path, requires_python: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nrequires-python = "{requires_python}"\n', encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize(
    ("declared", "message"),
    [
        (">=3.11.4", r"must be a plain `3\.N`"),
        (">=3", r"must be a plain `3\.N`"),
        (">=3.11rc1", r"must be a plain `3\.N`"),
        (">=3.11.dev0", r"must be a plain `3\.N`"),
        (">=3.11.post2", r"must be a plain `3\.N`"),
        (">=1!3.11", r"must be a plain `3\.N`"),
        (">=3.11,<4", r"read a single `>=3\.N` floor"),
        ("~=3.11", r"read a single `>=3\.N` floor"),
        (">=4.0", "not a Python 3 floor"),
    ],
)
def test_a_floor_these_checks_cannot_read_fails_with_a_message(
    tmp_path: Path, declared: str, message: str
) -> None:
    """``>=3.11.4`` used to end the run with a bare ``ValueError`` (#199)."""
    with pytest.raises(AssertionError, match=message):
        _floor(_declaring(tmp_path, declared))


@pytest.mark.parametrize("declared", [">=3.11", ">=3.11.0", ">= 3.11"])
def test_a_floor_is_read_however_it_is_spelled(tmp_path: Path, declared: str) -> None:
    assert _floor(_declaring(tmp_path, declared)) == (3, 11)


@pytest.mark.parametrize("value", ["3.x", "3", "3.11.4", "pypy-3.11", ""])
def test_a_version_these_checks_cannot_read_fails_with_a_message(value: str) -> None:
    """``python-version: '3.x'`` used to end the run with a bare ``ValueError``."""
    with pytest.raises(AssertionError, match=r"is not a `major\.minor` Python version"):
        _version(value)


def test_the_declared_floor_is_the_lowest_interpreter_ci_tests(
    pytestconfig: pytest.Config,
) -> None:
    root = _repo_root(pytestconfig)
    floor = _floor(root)

    assert min(_ci_matrix(root)) == floor, (
        f"requires-python admits {floor} but the {_CI_JOB} matrix in "
        f"{_CI_WORKFLOW} starts at {min(_ci_matrix(root))}"
    )

    below = {
        path.name: sorted(version for version in versions if version < floor)
        for path in sorted((root / _WORKFLOWS).glob("*.y*ml"))
        if (versions := _python_versions(yaml.safe_load(path.read_text("utf-8"))))
        and min(versions) < floor
    }
    assert not below, f"workflows run on a Python below the floor {floor}: {below}"


def test_only_a_pull_request_runs_fewer_versions_than_ci_tests(
    pytestconfig: pytest.Config,
) -> None:
    """A pull request runs one of the versions; something else still runs all (#238).

    Each version takes minutes, which a private repository is billed for, so a
    pull request runs one. That is safe only while the rest still run somewhere:
    on every push to ``main``, weekly and on demand here, and on all of them
    for the pull requests the Dependabot workflow validates. The two tests
    around this one hold the full list to the floor and to the classifiers.

    What this cannot close: that anyone reads the run on ``main`` when a
    version the pull request skipped fails there.
    """
    root = _repo_root(pytestconfig)
    on_pull_request, everywhere_else = _ci_matrices(root)

    assert len(on_pull_request) == 1 and on_pull_request[0] in everywhere_else, (
        f"a pull request must run one of {everywhere_else}; it runs {on_pull_request}"
    )

    workflow = yaml.safe_load((root / _CI_WORKFLOW).read_text(encoding="utf-8"))
    # PyYAML reads the bare key `on` as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert {"schedule", "workflow_dispatch"} <= set(triggers), (
        f"{_CI_WORKFLOW} no longer runs weekly and on demand: {sorted(triggers)}"
    )
    push = triggers.get("push") or {}
    assert "main" in push.get("branches", []) and not (
        {"paths", "paths-ignore", "branches-ignore"} & set(push)
    ), (
        "every push to main must run the full list, because a pull request "
        f"does not; the push trigger is {push}"
    )

    dependabot = yaml.safe_load((root / _DEPENDABOT_WORKFLOW).read_text("utf-8"))
    assert set(everywhere_else) <= set(_python_versions(dependabot)), (
        f"{_DEPENDABOT_WORKFLOW} runs {sorted(set(_python_versions(dependabot)))}, "
        f"not every version CI tests {everywhere_else}; a dependency update "
        "would then be tested on one version only"
    )


def test_classifiers_and_tool_targets_name_what_ci_tests(
    pytestconfig: pytest.Config,
) -> None:
    root = _repo_root(pytestconfig)
    pyproject = _pyproject(root)
    floor = _floor(root)

    classified = sorted(
        _version(match[1])
        for classifier in pyproject["project"]["classifiers"]
        if (match := _CLASSIFIER.search(classifier))
    )
    assert classified == sorted(_ci_matrix(root)), (
        f"classifiers advertise {classified} but CI tests {sorted(_ci_matrix(root))}"
    )

    ruff_target = pyproject["tool"]["ruff"]["target-version"]
    assert ruff_target == f"py3{floor[1]}", (
        f"ruff target-version is {ruff_target!r} but the floor is {floor}"
    )
    mypy_target = pyproject["tool"]["mypy"]["python_version"]
    assert _version(mypy_target) == floor, (
        f"mypy python_version is {mypy_target!r} but the floor is {floor}"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Need Python 3.10+", [10]),
        ("badge/python-3.10%2B-blue", [10]),
        ("Python 3.11 or newer is required", [11]),
        ("Requires Python 3.9  or later.", [9]),
        ("SEMGREP_PYTHON (default: auto-detect >=3.10)", [10]),
        ("python --version  # Should be 3.10+", [10]),
        ("Requires Python 3.10 or\n        newer.", [10]),
        ("Python 3.12\nand then 3.10+", []),
        ("Works with fastmcp 3.2+ too.", []),
        ("OpenSSL 3.0+ and semgrep>=3.1", []),
        ("requires-python >= 3.12", [12]),
        ("exit(0 if sys.version_info >= (3, 10) else 1)", [10]),
        ("sys.version_info>=(3,13)", [13]),
        ("Python 3.10+ on Linux, 3.11+ on macOS", [10, 11]),
        ("python3.12 -m venv venv", []),
        ("the system python3 is 3.9", []),
        ("python-version: [3.11, 3.12, 3.13]", []),
        ("semgrep 1.149.0, fastmcp>=4.0.10", []),
        ("a declared fastmcp>=3.4.7,<4", []),
        ("13.10+ and v3.10.2", []),
    ],
)
def test_floor_claim_scanner_reads_synthetic_text(
    text: str, expected: list[int]
) -> None:
    assert [minor for _, minor in _claims(text)] == expected


def test_every_stated_python_floor_is_the_declared_one(
    pytestconfig: pytest.Config,
) -> None:
    root = _repo_root(pytestconfig)
    floor = _floor(root)
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", *_CLAIM_SURFACES],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")

    seen = 0
    wrong: list[str] = []
    for name in filter(None, listed.split("\0")):
        if name in _POINT_IN_TIME_RECORDS:
            continue
        try:
            text = (root / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for number, minor in _claims(text):
            seen += 1
            if (3, minor) != floor:
                wrong.append(f"{name}:{number} says 3.{minor}")

    assert seen >= _MIN_CLAIMS, (
        f"only {seen} Python floor claims found under {_CLAIM_SURFACES}; "
        f"expected at least {_MIN_CLAIMS}"
    )
    assert not wrong, f"the floor is 3.{floor[1]} but: {wrong}"
