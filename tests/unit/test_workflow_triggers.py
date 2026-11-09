"""Guards that every workflow trigger and every Dependabot route reaches a real branch.

Three workflows filtered on ``develop`` and ``hotfix/*``, branches this
repository has never had: no ref on either remote, no pull request based on
one, and no workflow run from one (#76). The same audit found that
``.github/dependabot.yml`` could not route a single update anywhere -- it
failed GitHub's own schema in eight places, and every entry targeted a branch
that does not exist and that no workflow's ``pull_request`` filter selects --
and that the Dependabot workflow's manual trigger validated nothing.

Each test below closes one of those routes at the seam where it failed: the
trigger filters, the detection script as bash actually runs it, and the
Dependabot configuration against the workflows that must receive its pull
requests. Schema validity itself is the ``check-dependabot`` pre-commit hook.

``test_dependabot_has_no_pip_compile_lock_to_recompile`` guards a route of a
different kind: a tracked pip-compile lock, which made Dependabot's ``pip``
updates fail before any pull request (#54).
``test_every_install_resolves_from_pyproject_alone`` and
``test_no_requirements_file_is_tracked`` keep requirements files out of the
tree and out of every install command (#167).
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name

_WORKFLOWS = ".github/workflows"
_CI_WORKFLOW = ".github/workflows/security-analysis.yml"
_DEVELOPMENT_GUIDE = "docs/development.md"

# The one branch pull requests are opened against. docs/development.md: "Branch
# from `origin/main`", and `main` is the production branch.
_BASE_BRANCH = "main"

# The table row in docs/development.md that tells a contributor which pushes and
# pull requests run the functional gate.
_TRIGGER_ROW_MARKER = "`functional-gate` job"


def _repo_root(pytestconfig: pytest.Config) -> Path:
    return Path(str(pytestconfig.rootpath))


def _load_yaml(path: Path) -> dict[Any, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} is not a YAML mapping"
    return loaded


def _triggers(workflow: dict[Any, Any]) -> dict[str, Any]:
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    if isinstance(triggers, str):
        return {triggers: None}
    if isinstance(triggers, list):
        return dict.fromkeys(triggers)
    assert isinstance(triggers, dict), f"unreadable `on:` block: {triggers!r}"
    return triggers


def _branch_filters(root: Path, event: str) -> dict[str, list[str]]:
    """Every workflow's ``branches:`` filter for *event*, keyed by file name.

    ``branches-ignore:`` is refused rather than skipped: it names the branches a
    trigger does *not* fire on, so no check here could say what it selects.
    """
    filters: dict[str, list[str]] = {}
    for path in sorted((root / _WORKFLOWS).glob("*.y*ml")):
        config = _triggers(_load_yaml(path)).get(event)
        assert not (isinstance(config, dict) and "branches-ignore" in config), (
            f"{path.name} filters {event} with branches-ignore, which these checks "
            "cannot read; list the branches it should run on instead"
        )
        if isinstance(config, dict) and "branches" in config:
            filters[path.name] = [str(branch) for branch in config["branches"]]
    return filters


def _documented_triggers(root: Path) -> tuple[set[str], set[str]]:
    """The push and pull-request branches the development guide promises."""
    guide = (root / _DEVELOPMENT_GUIDE).read_text(encoding="utf-8")
    rows = [line for line in guide.splitlines() if _TRIGGER_ROW_MARKER in line]
    assert len(rows) == 1, (
        f"expected one {_TRIGGER_ROW_MARKER!r} row in {_DEVELOPMENT_GUIDE}, "
        f"found {len(rows)}"
    )
    when = rows[0].rsplit("|", 2)[1]
    match = re.search(r"every push to (.+?), and every PR to (.+)$", when.strip())
    assert match, (
        f"the trigger row no longer reads 'every push to .., and every PR to ..': {when!r}"
    )
    push, pull_request = (
        set(re.findall(r"`([^`]+)`", part)) for part in match.groups()
    )
    return push, pull_request


def test_pull_requests_are_filtered_only_on_the_branch_they_target(
    pytestconfig: pytest.Config,
) -> None:
    """A ``pull_request`` filter selects the *base* branch, and only ``main`` is one.

    ``develop`` sat in two of these lists without ever having existed. It
    selected nothing, and read as though a second integration branch were in
    use.
    """
    filters = _branch_filters(_repo_root(pytestconfig), "pull_request")
    assert filters, "no workflow filters pull_request by branch, so this checks nothing"

    stray = {
        name: sorted(set(branches) - {_BASE_BRANCH})
        for name, branches in filters.items()
        if set(branches) != {_BASE_BRANCH}
    }
    assert not stray, (
        f"pull_request filters name base branches other than {_BASE_BRANCH!r}: "
        f"{stray}. Pull requests here are only ever opened against {_BASE_BRANCH!r}."
    )


def test_push_filters_are_the_branches_the_guide_documents(
    pytestconfig: pytest.Config,
) -> None:
    """Every pushed branch that triggers CI is one the guide names, and the reverse.

    ``hotfix/*`` and ``develop`` triggered on push without existing, and the
    guide repeated them, so the documentation could not reveal it either.

    What this cannot close: a glob added to the workflow *and* the guide passes,
    because whether any branch ever matches it is a fact about the remote, not
    the tree. The long-lived-branch check covers bare names; a pattern needs a
    reviewer to ask which branches it has actually matched.
    """
    root = _repo_root(pytestconfig)
    push_filters = _branch_filters(root, "push")
    assert push_filters, "no workflow filters push by branch, so this checks nothing"
    triggered = {branch for branches in push_filters.values() for branch in branches}

    long_lived = {branch for branch in triggered if "*" not in branch} - {_BASE_BRANCH}
    assert not long_lived, (
        f"push filters name long-lived branches {sorted(long_lived)}; {_BASE_BRANCH!r} "
        "is the only one this repository keeps, and everything else is a pattern."
    )

    documented_push, documented_pull_request = _documented_triggers(root)

    assert triggered == documented_push, (
        f"workflows run on pushes to {sorted(triggered)} while {_DEVELOPMENT_GUIDE} "
        f"documents {sorted(documented_push)}. Undocumented: "
        f"{sorted(triggered - documented_push)}; documented but never triggered: "
        f"{sorted(documented_push - triggered)}."
    )
    assert documented_pull_request == {_BASE_BRANCH}, (
        f"{_DEVELOPMENT_GUIDE} says pull requests to {sorted(documented_pull_request)} "
        f"run the gate; only {_BASE_BRANCH!r} is ever a base branch."
    )


# The workflow whose extra validation the detection step switches on or off,
# and that step's id.
_VALIDATION_WORKFLOW = ".github/workflows/dependabot-security-validation.yml"
_DETECT_JOB = "detect-dependabot"
_DETECT_STEP_ID = "check"

_EXPRESSION = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")


def _detection_script(root: Path) -> str:
    workflow = _load_yaml(root / _VALIDATION_WORKFLOW)
    steps = workflow["jobs"][_DETECT_JOB]["steps"]
    scripts = [step["run"] for step in steps if step.get("id") == _DETECT_STEP_ID]
    assert len(scripts) == 1, (
        f"expected one step with id {_DETECT_STEP_ID!r}, found {len(scripts)}"
    )
    return str(scripts[0])


def _run_detection(
    script: str, context: dict[str, str], tmp_path: Path
) -> dict[str, str]:
    """Run the step the way the runner does: expressions substituted, then bash -e."""

    def substitute(match: re.Match[str]) -> str:
        expression = match.group(1)
        assert expression in context, (
            f"the detection step reads ${{{{ {expression} }}}}, which this test "
            "does not model; add it to every case so none passes by omission"
        )
        return context[expression]

    output = tmp_path / "github_output"
    output.touch()
    result = subprocess.run(
        ["bash", "-e", "-c", _EXPRESSION.sub(substitute, script)],
        env={"GITHUB_OUTPUT": str(output), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"detection step failed: {result.stderr}"
    return dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines()
    )


@pytest.mark.parametrize(
    ("event_name", "actor", "head_ref", "expected"),
    [
        # The manual trigger declared "validate on demand" and skipped every job.
        ("workflow_dispatch", "a-maintainer", "", "true"),
        ("pull_request", "dependabot[bot]", "dependabot/pip/httpx-0.28.1", "true"),
        ("pull_request", "a-maintainer", "security/secret-free-token-wrapper", "true"),
        ("pull_request", "a-maintainer", "feature/security-headers", "true"),
        ("pull_request", "a-maintainer", "fix/workflow-triggers-76", "false"),
        ("pull_request", "a-maintainer", "feature/security", "false"),
    ],
)
def test_detection_step_validates_exactly_the_routes_it_promises(
    pytestconfig: pytest.Config,
    tmp_path: Path,
    event_name: str,
    actor: str,
    head_ref: str,
    expected: str,
) -> None:
    """Dependabot, the documented security branches, and a manual run validate; nothing else does."""
    outputs = _run_detection(
        _detection_script(_repo_root(pytestconfig)),
        {
            "github.event_name": event_name,
            "github.actor": actor,
            "github.head_ref": head_ref,
        },
        tmp_path,
    )

    assert outputs.get("should-validate") == expected, (
        f"{event_name} by {actor} from {head_ref!r}: should-validate="
        f"{outputs.get('should-validate')!r}, expected {expected!r}. Outputs: {outputs}"
    )


def test_every_declared_dispatch_input_is_read(pytestconfig: pytest.Config) -> None:
    """A ``workflow_dispatch`` input nothing reads is a control that does nothing.

    The Dependabot workflow asked for a ``pr_number`` "to validate" and never
    read it, so a manual run looked targeted while checking out the default
    branch.
    """
    root = _repo_root(pytestconfig)
    unread: dict[str, list[str]] = {}
    dispatchable = 0
    for path in sorted((root / _WORKFLOWS).glob("*.y*ml")):
        triggers = _triggers(_load_yaml(path))
        if "workflow_dispatch" not in triggers:
            continue
        dispatchable += 1
        inputs = (triggers["workflow_dispatch"] or {}).get("inputs") or {}
        text = path.read_text(encoding="utf-8")
        missing = [
            name
            for name in inputs
            if not re.search(
                rf"\b(?:github\.event\.)?inputs\.{re.escape(name)}\b", text
            )
        ]
        if missing:
            unread[path.name] = missing

    assert dispatchable, "no workflow can be dispatched, so this checks nothing"
    assert not unread, f"workflow_dispatch inputs declared and never read: {unread}"


_DEPENDABOT_CONFIG = ".github/dependabot.yml"
_TITLE_WORKFLOW = ".github/workflows/conventional-commits.yml"

# `type` or `type(scope)`, the part of a pull-request title before the colon.
_TITLE_PREFIX = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[a-z-]+)\))?$")


def _scanned_directories(update: dict[str, Any]) -> list[str]:
    """Where an entry looks: its ``directory``, or each of its ``directories``."""
    if "directory" in update:
        return [update["directory"]]
    return list(update.get("directories", []))


def _dependabot_updates(root: Path) -> dict[str, dict[str, Any]]:
    """Each ``updates`` entry, keyed by position so two alike entries stay distinct."""
    updates = _load_yaml(root / _DEPENDABOT_CONFIG).get("updates")
    assert isinstance(updates, list) and updates, (
        f"{_DEPENDABOT_CONFIG} declares no updates"
    )
    return {
        f"updates[{index}] ({update.get('package-ecosystem')} in "
        f"{', '.join(_scanned_directories(update)) or 'no directory'})": update
        for index, update in enumerate(updates)
    }


def _colliding_entries(
    updates: Iterable[dict[str, Any]],
) -> list[tuple[Any, Any, Any]]:
    """Each ecosystem, directory and target branch that more than one entry names.

    An entry that names no target branch opens its pull requests against the
    default one, so it collides with an entry that names that branch.

    Directories are compared as written. ``/tools`` and ``/tools/``, or a glob
    and a path it matches, are not seen as the same place.
    """
    keys = [
        (
            update.get("package-ecosystem"),
            directory,
            update.get("target-branch", _BASE_BRANCH),
        )
        for update in updates
        # An entry that names no directory still collides with another like it.
        for directory in list[str | None](_scanned_directories(update)) or [None]
    ]
    return sorted({key for key in keys if keys.count(key) > 1}, key=str)


def test_every_dependabot_pull_request_reaches_the_workflows_that_gate_it(
    pytestconfig: pytest.Config,
) -> None:
    """Dependabot must open its pull requests where the gating workflows listen.

    All three entries targeted ``feature/*-updates`` branches that never
    existed, and neither workflow's ``pull_request`` filter selected them, so
    even a valid configuration could never have been validated.
    """
    root = _repo_root(pytestconfig)
    filters = _branch_filters(root, "pull_request")
    gated_by = {Path(_VALIDATION_WORKFLOW).name, Path(_CI_WORKFLOW).name}
    assert gated_by <= filters.keys(), (
        f"expected pull_request filters in {sorted(gated_by)}"
    )

    unreached = {
        label: update.get("target-branch", _BASE_BRANCH)
        for label, update in _dependabot_updates(root).items()
        if any(
            update.get("target-branch", _BASE_BRANCH) not in filters[name]
            for name in gated_by
        )
    }
    assert not unreached, (
        f"Dependabot targets base branches no gating workflow selects: {unreached}. "
        f"Omit target-branch so its pull requests go to {_BASE_BRANCH!r}."
    )


def test_dependabot_entries_do_not_collide(pytestconfig: pytest.Config) -> None:
    """GitHub rejects two entries for one ecosystem, directory and target branch.

    The two ``pip`` entries were distinct only through their nonexistent target
    branches, so pointing both at ``main`` would have made the file invalid again.
    """
    duplicates = _colliding_entries(
        _dependabot_updates(_repo_root(pytestconfig)).values()
    )
    assert not duplicates, f"duplicate Dependabot entries: {duplicates}"


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        (
            [
                {"package-ecosystem": "pip", "directory": "/"},
                {"package-ecosystem": "pip", "directory": "/"},
            ],
            [("pip", "/", "main")],
        ),
        (
            [
                {"package-ecosystem": "pip", "directory": "/"},
                {"package-ecosystem": "pip", "directory": "/", "target-branch": "main"},
            ],
            [("pip", "/", "main")],
        ),
        # An entry that lists its directories scans each of them. Reading only
        # `directory` saw None here and compared nothing (#199).
        (
            [
                {"package-ecosystem": "pip", "directory": "/"},
                {"package-ecosystem": "pip", "directories": ["/tools", "/"]},
            ],
            [("pip", "/", "main")],
        ),
        (
            [
                {"package-ecosystem": "pip", "directories": ["/a", "/b"]},
                {"package-ecosystem": "pip", "directories": ["/b", "/c"]},
            ],
            [("pip", "/b", "main")],
        ),
        (
            [{"package-ecosystem": "pip"}, {"package-ecosystem": "pip"}],
            [("pip", None, "main")],
        ),
        (
            [
                {"package-ecosystem": "pip", "directories": ["/a", "/b"]},
                {"package-ecosystem": "pip", "directories": ["/c"]},
                {"package-ecosystem": "github-actions", "directories": ["/a"]},
                {
                    "package-ecosystem": "pip",
                    "directory": "/a",
                    "target-branch": "release",
                },
            ],
            [],
        ),
    ],
)
def test_the_collision_check_reads_synthetic_entries(
    updates: list[dict[str, Any]], expected: list[tuple[Any, Any, Any]]
) -> None:
    assert _colliding_entries(updates) == expected


def test_an_entry_is_labelled_with_every_directory_it_scans(tmp_path: Path) -> None:
    """A ``directories`` entry used to be reported as "in None" (#199)."""
    config = tmp_path / _DEPENDABOT_CONFIG
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "updates": [
                    {"package-ecosystem": "pip", "directory": "/"},
                    {"package-ecosystem": "pip", "directories": ["/a", "/b"]},
                    {"package-ecosystem": "pip"},
                ],
            }
        ),
        encoding="utf-8",
    )
    assert list(_dependabot_updates(tmp_path)) == [
        "updates[0] (pip in /)",
        "updates[1] (pip in /a, /b)",
        "updates[2] (pip in no directory)",
    ]


def _allowed_title_words(root: Path, field: str) -> set[str]:
    steps = _load_yaml(root / _TITLE_WORKFLOW)["jobs"]["conventional-commits"]["steps"]
    values = [step["with"][field] for step in steps if field in step.get("with", {})]
    assert len(values) == 1, f"expected one {field!r} list in {_TITLE_WORKFLOW}"
    return set(str(values[0]).split())


def _title_prefixes(update: dict[str, Any]) -> list[str]:
    """What Dependabot writes before ``: bump ...`` for this entry.

    A production dependency takes ``prefix``; a development one takes
    ``prefix-development``, falling back to ``prefix``. With ``include: scope``
    Dependabot appends ``(deps)`` or ``(deps-dev)`` respectively. With no
    ``commit-message`` it writes a bare ``Bump ...``, which has no type at all.
    Only ``pip`` distinguishes development dependencies here.
    """
    message = update.get("commit-message")
    if not message:
        return [""]
    production = str(message.get("prefix", ""))
    kinds = [(production, "deps")]
    if update.get("package-ecosystem") == "pip":
        kinds.append((str(message.get("prefix-development", production)), "deps-dev"))
    if message.get("include") == "scope":
        return [f"{prefix}({scope})" for prefix, scope in kinds]
    return [prefix for prefix, _ in kinds]


def test_dependabot_titles_pass_the_conventional_commits_check(
    pytestconfig: pytest.Config,
) -> None:
    """Every title Dependabot can write must pass the check every pull request runs.

    The configuration asked for ``security(deps): ...``, ``ci-security(deps): ...``
    and ``deps-dev(...)`` titles; ``security`` and ``ci-security`` are not allowed
    types and ``deps-dev`` is not an allowed scope, so each such pull request
    would have opened with a red check.
    """
    root = _repo_root(pytestconfig)
    types = _allowed_title_words(root, "types")
    scopes = _allowed_title_words(root, "scopes")
    assert "chore" in types and "deps" in scopes, (
        "the allowed-title lists did not parse"
    )

    rejected: dict[str, list[str]] = {}
    for label, update in _dependabot_updates(root).items():
        for prefix in _title_prefixes(update):
            match = _TITLE_PREFIX.match(prefix)
            if (
                not match
                or match["type"] not in types
                or (match["scope"] is not None and match["scope"] not in scopes)
            ):
                rejected.setdefault(label, []).append(prefix or "<no prefix>")

    assert not rejected, (
        f"Dependabot would open pull requests titled with {rejected}, which "
        f"{_TITLE_WORKFLOW} rejects (types {sorted(types)}, scopes {sorted(scopes)})."
    )


def test_the_guide_lists_the_scopes_the_title_check_allows(
    pytestconfig: pytest.Config,
) -> None:
    """``docs/development.md`` names the scope list the title check holds (#371)."""
    root = _repo_root(pytestconfig)
    guide = (root / "docs" / "development.md").read_text(encoding="utf-8")
    sentence = re.search(r"must be one of (.*?)\.\s", guide, re.DOTALL)
    assert sentence, "docs/development.md no longer lists the title scopes"

    assert set(re.findall(r"`([a-z-]+)`", sentence[1])) == _allowed_title_words(
        root, "scopes"
    )


def test_dependabot_may_propose_every_github_actions_update(
    pytestconfig: pytest.Config,
) -> None:
    """No ``github-actions`` entry may hold back any update, major or otherwise.

    ``actions/checkout`` and ``actions/setup-python`` were held at ``@v4`` by an
    ``ignore`` on their semver-major updates while GitHub removed the runtimes
    they declared (node20 and node16), so every job ran them forced onto Node 24
    and no pull request would ever have proposed the fix (#165). GitHub retires
    an action major's runtime on its own schedule, not because of a choice made
    here, so the Dependabot pull request is where the deliberate review happens.

    Every file setting that holds an update back is refused outright rather
    than parsed: ``ignore`` blocks a major through ``semver-major``, through a
    missing ``update-types`` or through a ``versions`` range; ``allow`` blocks
    every dependency it does not name; ``exclude-paths`` hides the workflows it
    lists; and ``open-pull-requests-limit: 0`` turns version updates off. Some
    entry must also scan exactly ``/``, where Dependabot reads
    ``.github/workflows``, or an entry pointed elsewhere would satisfy the floor
    and scan nothing. A glob such as ``/**`` is refused too, conservatively.

    The ``pip`` ignores are kept on purpose: a library major only rots by
    choice. GitHub's documentation disagrees on whether they also hold back
    security updates, so the backstop there is pip-audit, which fails CI on a
    known vulnerability whatever Dependabot ignores.

    Residual: a Dependabot pull request left unmerged still leaves a pin on a
    removed runtime, and so does a ``@dependabot ignore`` comment, which GitHub
    stores outside this file. ``cooldown`` is allowed: it delays a major by at
    most 90 days rather than holding it. Nothing offline can read an action's
    runtime, so the "Node.js ... is deprecated" annotation is the only signal.
    """
    entries = {
        label: update
        for label, update in _dependabot_updates(_repo_root(pytestconfig)).items()
        if update.get("package-ecosystem") == "github-actions"
    }
    assert len(entries) >= 1, (
        f"{_DEPENDABOT_CONFIG} has no github-actions entry, so this checks nothing"
    )

    filtered = {
        f"{label}.{key}": update[key]
        for label, update in entries.items()
        for key in ("ignore", "allow", "exclude-paths")
        if key in update
    }
    assert not filtered, (
        f"Dependabot is told to skip github-actions updates: {filtered}. A held-back "
        "action major silently outlives the runtime it declares; delete the filter."
    )

    scanned = [
        label
        for label, update in entries.items()
        if "/" in _scanned_directories(update)
    ]
    assert scanned, (
        f"no github-actions entry scans '/', so Dependabot never reads "
        f".github/workflows: {sorted(entries)}"
    )

    disabled = [
        label
        for label, update in entries.items()
        if update.get("open-pull-requests-limit") == 0
    ]
    assert not disabled, (
        f"open-pull-requests-limit: 0 turns off github-actions version updates in {disabled}"
    )


# The header pip-compile writes into every file it generates. It sits within
# the first hundred bytes, so a fixed prefix is read rather than the whole file.
_PIP_COMPILE_HEADER = b"autogenerated by pip-compile"
_HEADER_BYTES = 512

# Tracked `.in` files that are not requirement files. Every other `.in` is
# refused, so one that lists no requirement has to be named here.
# setuptools' sdist manifest is the usual case.
_NOT_A_PIP_COMPILE_INPUT = {"MANIFEST.in"}


def _tracked_files(root: Path) -> list[str]:
    """Every tracked path.

    Dependabot clones the commit on ``main``; the index is what the next
    commit will hold, and the nearest thing to it a test can read.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    ).stdout
    tracked = [path.decode("utf-8") for path in listed.split(b"\0") if path]
    assert _DEPENDABOT_CONFIG in tracked, (
        f"git ls-files did not list {_DEPENDABOT_CONFIG}, so the listing cannot "
        "be trusted to show what Dependabot clones"
    )
    return tracked


def _file_head(path: Path) -> bytes:
    """The first bytes of a tracked file, as they sit in the working tree.

    Read as bytes and with no ``try``: a file that cannot be decoded or cannot
    be opened must not become a file this guard quietly skips.
    """
    with path.open("rb") as handle:
        return handle.read(_HEADER_BYTES)


def test_dependabot_has_no_pip_compile_lock_to_recompile(
    pytestconfig: pytest.Config,
) -> None:
    """No tracked file may be a pip-compile input or a pip-compile output.

    ``requirements-lock.txt`` was compiled from ``requirements.in`` on Python
    3.12 and no install path read it (#54). Dependabot did: its ``pip`` job
    re-ran pip-compile on the file under Python 3.10.20, which
    ``requires-python`` admits and no CI job tests. The lock pinned
    ``aiofile==3.12.3``, which needs Python 3.11; pip-compile discarded the
    pin, the resolve did not complete, and each of the three updates one
    weekly run attempted (pyyaml, bleach, python-slugify) ended in
    ``unknown_error`` with no pull request. The lock's own test stayed green
    throughout and nothing watches the Dependabot Updates workflow.

    Every workflow installs with ``pip install -e .`` and resolves from
    ``pyproject.toml``, so the build is not reproducible and no compiled lock
    may suggest that it is. An input is refused as well as an output: it
    exists only to have a lock compiled from it.

    This reads pip-compile's header, so a lock written by another tool, or one
    whose header was edited away, is not seen here.
    ``test_no_requirements_file_is_tracked`` reads the content instead and
    covers both.
    """
    root = _repo_root(pytestconfig)
    tracked = _tracked_files(root)
    assert any(
        update.get("package-ecosystem") == "pip"
        for update in _dependabot_updates(root).values()
    ), f"{_DEPENDABOT_CONFIG} has no pip entry, so this guards nothing"

    inputs = sorted(
        path
        for path in tracked
        if path.endswith(".in") and Path(path).name not in _NOT_A_PIP_COMPILE_INPUT
    )
    assert not inputs, (
        f"`.in` files are tracked: {inputs}. A pip-compile input belongs in "
        "pyproject.toml instead; any other `.in` file belongs in "
        "_NOT_A_PIP_COMPILE_INPUT."
    )

    compiled = sorted(
        path for path in tracked if _PIP_COMPILE_HEADER in _file_head(root / path)
    )
    assert not compiled, (
        f"pip-compile output is tracked: {compiled}. Dependabot re-runs "
        "pip-compile on it, and a resolve that fails there fails the update (#54)."
    )


# Where an install command can run from or be printed by, each with the fewest
# installs and the fewest editable installs it must yield. Every tracked file
# under these paths is read, comments and messages included, since a script
# that tells a developer to run a command pip rejects is wrong as well.
#
# Measured on 2026-10-05: scripts/ yields 17 installs, 7 editable; .github/
# yields 21 and 9. The floors are per surface, so a scan that stopped reading
# one cannot hide behind the other, and low enough that deleting one script
# does not trip them.
_MIN_INSTALLS = {"scripts/": (10, 4), ".github/": (14, 6)}

# A hook may install too. None does today, so this surface has no floor.
_INSTALL_SURFACES = (*_MIN_INSTALLS, ".pre-commit-config.yaml")

# `pip install`, `pip3 install`, `python -m pip install`, `uv pip install`,
# `pip --quiet install`, `pip --cache-dir /tmp/c install` and
# `"$VENV/bin/pip" install` all end in this. The arguments are whatever
# follows, so two installs on one line are two matches.
_PIP_INSTALL = re.compile(
    r"""\bpip[\d.]*["']?(?:\s+-\S+(?:\s+[^\s-]\S*)?)*?\s+install\b"""
)

# Where one shell command stops and the next, or a trailing comment, starts. A
# quoted string is consumed whole, so the `;` of an environment marker in
# `"pkg; python_version < '3.11'"` does not end the command early.
_COMMAND_END = re.compile(r"""'[^']*'|"[^"]*"|(?P<end>&&|\|\||[;|]|\s#)""")

# One shell word: quoted and bare runs with no space between them, so
# `"$ROOT"[dev]` is one word. A backtick ends it, as in Markdown and messages.
_SHELL_WORD = re.compile(r"""(?:'[^']*'|"[^"]*"|[^\s'"`])+""")

# pip's short options that take a value. In a cluster such as `-qr` or `-Ue`
# the first of these consumes the rest of the word, or the next word.
_SHORT_OPTIONS_WITH_A_VALUE = "rcetifC"

# A positional argument that is a local path rather than a package name.
_LOCAL_PATH = re.compile(r"[./~$]")

# Punctuation that follows `]` when a command is quoted in prose: "(run
# `pip install -e .[dev]`)." No extras list ends in any of it.
_PROSE_AFTER_EXTRAS = re.compile(r"(?<=\])[).,:]+$")

_PATH_WITH_EXTRAS = re.compile(r"(?P<path>[^\[\]]+)(?:\[(?P<extras>[^\[\]]*)\])?")


def _install_commands(text: str) -> list[str]:
    """The arguments of each ``pip install`` in *text*, one entry per command."""
    commands = []
    for line in text.replace("\\\n", " ").splitlines():
        for match in _PIP_INSTALL.finditer(line):
            arguments = line[match.end() :]
            end = next(
                (
                    found.start()
                    for found in _COMMAND_END.finditer(arguments)
                    if found["end"]
                ),
                len(arguments),
            )
            commands.append(arguments[:end])
    return commands


def _short_option(word: str) -> tuple[str, str] | None:
    """The value-taking short option in *word* and whatever is attached to it."""
    if not word.startswith("-") or word.startswith("--"):
        return None
    for index, letter in enumerate(word[1:], start=1):
        if letter in _SHORT_OPTIONS_WITH_A_VALUE:
            return letter, word[index + 1 :].lstrip("=")
        if not letter.isalpha():
            return None
    return None


def _abbreviates(word: str, option: str) -> bool:
    """Whether *word* is *option* or a prefix of it.

    pip accepts a prefix that is unambiguous (``--requirem``, ``--cons``,
    ``--ed``) and rejects one that is not (``--req``). Both are refused here:
    neither belongs in a script.
    """
    name = word.partition("=")[0]
    return len(name) > len("--x") and option.startswith(name)


def _read_install(arguments: str) -> tuple[list[str], list[str]]:
    """The requirements-file options and the local targets of one install.

    A target is the value of ``-e``, or a positional local path with extras
    (``pip install '.[dev]'``), which pip resolves from the same manifest.
    """
    words = [
        word.group().replace("'", "").replace('"', "")
        for word in _SHELL_WORD.finditer(arguments)
    ]
    requirement_options = []
    targets = []
    following_an_option = -1
    for index, word in enumerate(words):
        following = words[index + 1] if index + 1 < len(words) else ""
        short = _short_option(word)
        if short is not None and short[0] in "rc":
            requirement_options.append(word)
        elif _abbreviates(word, "--requirement") or _abbreviates(word, "--constraint"):
            requirement_options.append(word)
        elif short is not None and short[0] == "e":
            targets.append(short[1] or following)
        elif _abbreviates(word, "--editable"):
            targets.append(word.partition("=")[2] or following)
        elif _LOCAL_PATH.match(word) and "[" in word and following_an_option != index:
            targets.append(word)
        if word.startswith("-") and "=" not in word:
            following_an_option = index + 1
    return requirement_options, [
        _PROSE_AFTER_EXTRAS.sub("", target) for target in targets
    ]


def _install_faults(arguments: str, declared_extras: set[str]) -> list[str]:
    """Why this install resolves from something other than ``pyproject.toml``."""
    requirement_options, targets = _read_install(arguments)
    faults = [
        f"installs from a requirements file ({option})"
        for option in requirement_options
    ]
    for target in targets:
        parsed = _PATH_WITH_EXTRAS.fullmatch(target)
        if parsed is None:
            faults.append(f"target {target!r} is not `path` or `path[extras]`")
            continue
        if parsed["extras"] is None:
            continue
        extras = {extra.strip() for extra in parsed["extras"].split(",")}
        if "" in extras:
            faults.append(f"target {target!r} has an empty extras entry")
            continue
        undeclared = sorted(
            extra for extra in extras if canonicalize_name(extra) not in declared_extras
        )
        if undeclared:
            faults.append(f"target {target!r} names undeclared extras {undeclared}")
    return faults


def _declared_extras(root: Path) -> set[str]:
    with (root / "pyproject.toml").open("rb") as handle:
        extras = tomllib.load(handle)["project"]["optional-dependencies"]
    assert extras, "pyproject.toml declares no extras, so no extras check can fail"
    return {canonicalize_name(extra) for extra in extras}


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (" -e .", []),
        (" -e .[security,dev] > /dev/null 2>&1", []),
        (""" -e "${PROJECT_ROOT}[security,dev]" """, []),
        (" --upgrade pip setuptools", []),
        (" -e .[Dev,SECURITY]", []),
        (" -e .[security,dev]).", []),
        (""" "pkg; python_version < '3.11'" lxml""", []),
        (
            ' -r "$PROJECT_ROOT/config/dependencies/requirements.lock"',
            ["installs from a requirements file (-r)"],
        ),
        (" -qr requirements.txt", ["installs from a requirements file (-qr)"]),
        (" -Urrequirements.txt", ["installs from a requirements file"]),
        (" --requirement=requirements.txt", ["installs from a requirements file"]),
        (" --req requirements.txt", ["installs from a requirements file (--req)"]),
        (" -c constraints.txt -e .", ["installs from a requirements file (-c)"]),
        (' -e "[$PROJECT_ROOT]"', ["is not `path` or `path[extras]`"]),
        (' -e"[$PROJECT_ROOT]"', ["is not `path` or `path[extras]`"]),
        (" -qe '[x]'", ["is not `path` or `path[extras]`"]),
        (" --editable=.[]", ["has an empty extras entry"]),
        (" -e '.[dev,docs]'", ["names undeclared extras ['docs']"]),
        (" '.[docs]'", ["names undeclared extras ['docs']"]),
        (" --no-deps ./pkg[dev] uvicorn[standard]", []),
        (' -e "$ROOT"[docs]', ["names undeclared extras ['docs']"]),
    ],
)
def test_install_fault_scanner_reads_synthetic_commands(
    arguments: str, expected: list[str]
) -> None:
    """The scanner must refuse each spelling it exists for, and pass the valid ones."""
    faults = _install_faults(arguments, {"dev", "security", "test"})
    assert len(faults) == len(expected), faults
    for fault, fragment in zip(faults, expected, strict=True):
        assert fragment in fault


def test_install_command_scanner_splits_commands_and_joins_continuations() -> None:
    """One entry per command: a later ``python -c`` is not an install's ``-c``."""
    text = (
        "python -m pip install --upgrade pip && python -c 'import x'\n"
        "pip3 install -e \\\n    .[dev]  # editable\n"
        "uv pip --quiet install lxml; pip-audit -r nothing\n"
        '"$VENV/bin/pip" install "a; b" -r x | tee log\n'
        "pip install -U pip; pip --cache-dir /tmp/c install -r y && pip install z\n"
    )
    assert _install_commands(text) == [
        " --upgrade pip ",
        " -e      .[dev] ",
        " lxml",
        ' "a; b" -r x ',
        " -U pip",
        " -r y ",
        " z",
    ]


def test_every_install_resolves_from_pyproject_alone(
    pytestconfig: pytest.Config,
) -> None:
    """No script, workflow or hook installs from a requirements file.

    ``scripts/dev-setup.sh`` ran ``pip install -r config/dependencies/
    requirements.lock`` when the file existed, a list of 67 pins that still
    held ``black`` and ``pip-tools`` after this project dropped both, and
    ``pip install -e "[$PROJECT_ROOT]"`` when it did not, which pip rejects
    (#167). Every other path that installs the project runs ``pip install -e
    .``, with or without extras, so the one script that read a lock built an
    environment no gate builds, and deleting the lock alone would have broken
    the script.

    ``-r`` and ``-c`` are therefore refused outright, and a local target,
    editable or not, must be ``path`` or ``path[extras]``. The extras must be ones
    ``pyproject.toml`` declares: pip only warns about an unknown extra and
    installs without it, which is a quieter way to build the wrong environment.

    Residual: this reads ``pip install`` only, so ``pip download -r``,
    ``pip-sync`` or a tool that is not pip is not seen. Neither is
    ``PIP_REQUIREMENT`` or ``PIP_CONSTRAINT`` in the environment, nor an
    install assembled from a shell variable. A non-editable install of a named
    package (``pip install lxml``, the pinned ``semgrep`` in
    ``scripts/semgrep-isolated.sh``) is left alone.
    """
    root = _repo_root(pytestconfig)
    declared = _declared_extras(root)
    commands = [
        (path, arguments)
        for path in _tracked_files(root)
        if path.startswith(_INSTALL_SURFACES)
        for arguments in _install_commands((root / path).read_text(encoding="utf-8"))
    ]
    for surface, (fewest_installs, fewest_editable) in _MIN_INSTALLS.items():
        found = [arguments for path, arguments in commands if path.startswith(surface)]
        assert len(found) >= fewest_installs, (
            f"only {len(found)} install commands were found under {surface}, "
            "so this scan has stopped reading them"
        )
        editable = [arguments for arguments in found if _read_install(arguments)[1]]
        assert len(editable) >= fewest_editable, (
            f"only {len(editable)} editable installs were found under {surface}, "
            "so this scan has stopped reading their targets"
        )

    faults = {
        f"{path}: pip install{arguments}": found
        for path, arguments in commands
        if (found := _install_faults(arguments, declared))
    }
    assert not faults, (
        f"These installs do not resolve from pyproject.toml alone: {faults}. "
        "Install the project with `pip install -e 'path[extras]'`, naming "
        "extras pyproject.toml declares."
    )


# A trailing comment, and the per-requirement hashes pip-compile can write.
# Both are removed before a line is parsed as a requirement.
_INLINE_COMMENT = re.compile(r"(?:^|\s)#.*")
_HASH_OPTION = re.compile(r"\s--hash[=\s]\S+")

# Lines only a requirements file carries: another file to read (`-r base.txt`,
# `-rbase.txt`), an editable requirement, or a VCS link (`git+https://...`).
_REQUIREMENT_OPTION = re.compile(
    r"-[rce]|--(?:requirement|constraint|editable)(?:[\s=]|$)|[a-z]+\+[a-z]+://"
)

# A requirement given as a bare URL or local path. pip accepts one per line,
# but a list of links is not evidence of a manifest on its own.
_URL_OR_PATH = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://|\.{0,2}/")

# Measured on 2026-10-05: 188 of 188 tracked files decode as UTF-8.
_MIN_FILES_READ = 120


def _is_requirements_manifest(text: str) -> bool:
    """Whether *text* reads as a pip requirements file, whatever it is called.

    Every line that is not blank, a comment, a pip option or a bare URL or
    path must parse as a requirement. At least one line must be evidence: a
    requirement with a version or a URL, or ``-r``, ``-c`` or ``-e``. So a
    list of bare words or of links is not a manifest.
    """
    evidence = 0
    for raw in text.replace("\\\n", " ").splitlines():
        line = _HASH_OPTION.sub("", _INLINE_COMMENT.sub("", raw)).strip()
        if _REQUIREMENT_OPTION.match(line):
            evidence += 1
        elif not line or line.startswith("-") or _URL_OR_PATH.match(line):
            continue
        else:
            try:
                requirement = Requirement(line)
            except InvalidRequirement:
                return False
            if requirement.specifier or requirement.url:
                evidence += 1
    return evidence > 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("fastmcp>=4.0.10,<5\nmcp>=2.0.0,<3\n", True),
        ("annotated-types==0.7.0\n# Note: installed separately\nblack==25.1.0\n", True),
        (
            "--index-url https://example.invalid/simple\n"
            "httpx==0.28.1 \\\n    --hash=sha256:ab\n",
            True,
        ),
        ('aiofile==3.12.3 ; python_version >= "3.11"  # via x\ntenacity\n', True),
        ("pkg @ https://example.invalid/pkg.whl\n", True),
        ("-r base.txt\n-e .[dev]\n", True),
        ("-e git+https://example.invalid/a/b@v1#egg=b\n", True),
        ("-rbase.txt\n", True),
        ("git+https://example.invalid/a/b@v1\n", True),
        ("https://example.invalid/x-1.0.whl\n./local/pkg\nhttpx==1\n", True),
        ("https://example.invalid/a\nhttps://example.invalid/b\n", False),
        ("tenacity\nbleach\n", False),
        ("", False),
        ("# only a comment\n", False),
        ("- a markdown list\n- of two items\n", False),
        ("httpx==0.28.1\nThis line is prose.\n", False),
        ('[project]\ndependencies = ["httpx>=0.28.0"]\n', False),
    ],
)
def test_manifest_scanner_reads_synthetic_files(text: str, expected: bool) -> None:
    """The classifier must see each shape a requirements file takes, and no other."""
    assert _is_requirements_manifest(text) is expected


def test_no_requirements_file_is_tracked(pytestconfig: pytest.Config) -> None:
    """No tracked file may be a pip requirements file.

    Two were, and neither had pip-compile's header, so the guard above saw
    neither (#167). ``config/dependencies/requirements.lock`` was a list of 67
    pins with no recorded generator that ``scripts/dev-setup.sh`` installed;
    it still pinned ``black`` and ``pip-tools`` after ``pyproject.toml``
    dropped both. Root ``requirements.txt`` repeated the nine runtime ranges
    in ``pyproject.toml``; nothing in this repository read it, and Dependabot
    rewrote it beside ``pyproject.toml`` on every update.

    The file is recognised by what it contains, not by its name: the stale lock
    was not called ``requirements.txt``, and a rule keyed on names would have
    passed it.

    Residual: a file that does not decode as UTF-8 is not a manifest here, and
    a lock in another format (``poetry.lock``, ``uv.lock``, ``Pipfile.lock``)
    is TOML or JSON and is not seen. A one-line file such as ``python>=3.10``
    would be refused; none is tracked.
    """
    root = _repo_root(pytestconfig)
    read = 0
    manifests = []
    for path in _tracked_files(root):
        try:
            text = (root / path).read_bytes().decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        read += 1
        if _is_requirements_manifest(text):
            manifests.append(path)
    assert read >= _MIN_FILES_READ, (
        f"only {read} tracked files decoded as text, so this scan has stopped "
        "reading the tree"
    )
    assert not manifests, (
        f"Requirements files are tracked: {manifests}. pyproject.toml declares "
        "this project's dependencies and extras; a requirements file beside it "
        "is a second answer to which version is installed, and nothing keeps "
        "the two in step."
    )


_GO_LIVE_GATE = "scripts/go-live-gate.sh"


def _workflows_running(root: Path, script: str) -> dict[str, dict[str, Any]]:
    """Triggers of every workflow with a step whose ``run:`` invokes *script*."""
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((root / _WORKFLOWS).glob("*.y*ml")):
        workflow = _load_yaml(path)
        for job in (workflow.get("jobs") or {}).values():
            for step in job.get("steps", []) or []:
                lines = str(step.get("run", "")).splitlines()
                # A comment that names the script is not a step that runs it.
                if any(script in line.split("#", 1)[0] for line in lines):
                    found[path.name] = _triggers(workflow)
    return found


def test_the_go_live_gate_runs_in_ci_on_demand_and_on_a_schedule(
    pytestconfig: pytest.Config,
) -> None:
    """Something other than a person on release day runs the whole go-live gate.

    Gate 6 was broken from the mcp 2 migration (#162) until #181 and no check
    failed: the gate was run only by hand, and nobody had a reason to (#195).

    What this cannot close: that the scheduled run is read when it fails, and
    that the runner can reach what gates 5 to 11 ask the network for.
    """
    running = _workflows_running(_repo_root(pytestconfig), _GO_LIVE_GATE)
    assert running, f"no workflow step runs {_GO_LIVE_GATE}"
    missing = {
        name: sorted({"workflow_dispatch", "schedule"} - set(triggers))
        for name, triggers in running.items()
    }
    assert any(not absent for absent in missing.values()), (
        f"no workflow runs {_GO_LIVE_GATE} both on demand and on a schedule; "
        f"missing triggers per workflow: {missing}"
    )


def test_a_pull_request_that_edits_the_security_policy_runs_the_go_live_gate(
    pytestconfig: pytest.Config,
) -> None:
    """Gate 11 reads ``SECURITY.md``, so a change to that file must start it.

    The path filter named the gate's scripts only. A pull request that put the
    policy in the form for the other visibility passed the unit tests, which
    accept either form, and reached main without the gate having run (#257).

    ``fnmatch`` stands in for GitHub's path matching. For a file at the
    repository root the two agree on a pattern that includes; a ``!`` pattern
    excludes, which ``fnmatch`` does not know, so the filter may hold none
    (#268).
    """
    running = _workflows_running(_repo_root(pytestconfig), _GO_LIVE_GATE)
    on_pull_request = {
        name: triggers["pull_request"] or {}
        for name, triggers in running.items()
        if "pull_request" in triggers
    }
    assert on_pull_request, f"no workflow runs {_GO_LIVE_GATE} on a pull request"
    for name, config in on_pull_request.items():
        assert "paths-ignore" not in config, (
            f"{name} filters pull requests with paths-ignore, which this check "
            "cannot read; list the paths it should run on instead"
        )
        paths = config.get("paths")
        negated = [pattern for pattern in paths or [] if pattern.startswith("!")]
        assert not negated, (
            f"{name} excludes {negated} from its pull-request paths, which this "
            "check cannot read; list the paths it should run on instead"
        )
        assert paths is None or any(
            fnmatch.fnmatch("SECURITY.md", pattern) for pattern in paths
        ), (
            f"{name} runs {_GO_LIVE_GATE} on a pull request only for {paths}, so "
            "a pull request that edits SECURITY.md does not run the gate that "
            "compares it with the repository's visibility"
        )
