"""Guards that a release carries the version of the tag that started it.

``release.yml`` names the release from the pushed tag, and ``setuptools_scm``
names the built files from git. Two defects came from letting those disagree:

- Started by hand, the workflow built a branch with no tag on it and named the
  release from a typed ``version`` input. Release ``v0.0.0-ci.2`` was created
  with files named ``0.1.1rc2.dev113`` (#252).
- The workflow's pattern accepts ``v0.0.0-ci.3``, a name ``setuptools_scm``
  stops on, so every install and build of a commit carrying it fails (#253).

- The release was marked a prerelease when the tag held a ``-``. ``v1.2.3.rc1``
  builds the release candidate ``1.2.3rc1`` and has none, and ``v1.2.3-1``
  builds the post-release ``1.2.3.post1`` and has one (#256).

- The two files were attached to the release with nothing a deployer could
  verify them against (#272).

The hand start is gone, and ``scripts/check-release-tag.py`` checks the tag
name with the rule the build uses and then the names of the built files. It
also says whether the version is a prerelease, and the release job reads that
answer instead of the tag's spelling. The build job attests the checked files
before it hands them on. These
tests run the script and read the workflow for the steps that call it, for
their order, for the attestation, and for what the release job does with the files.

What this does not close: the workflow itself is not run here, so a step that
is present and fails on a runner for another reason is found only by the
rehearsal in ``docs/release-process.md``. That includes the two ``${{ }}``
expressions that carry the prerelease answer between jobs: their text is
compared here, and GitHub evaluating them is seen only on a runner. The tag table below was measured
against ``setuptools_scm`` by hand; ``setuptools_scm`` is not installed in the
test environment, so a change in its parsing is not seen here either.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from tests.helpers import load_module

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _ROOT / "scripts" / "check-release-tag.py"
_WORKFLOW = _ROOT / ".github" / "workflows" / "release.yml"

_NAME = "finos_ai_governance_mcp_server"


def _load_script() -> ModuleType:
    return load_module(_SCRIPT, "check_release_tag")


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *arguments],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def _dist(directory: Path, *versions: str, wheel: bool = True) -> Path:
    """Write the files a build of each version leaves behind."""
    dist = directory / "dist"
    dist.mkdir(parents=True)
    for version in versions:
        (dist / f"{_NAME}-{version}.tar.gz").touch()
        if wheel:
            (dist / f"{_NAME}-{version}-py3-none-any.whl").touch()
    return dist


# Each accepted tag with the version ``python -m setuptools_scm`` printed for a
# commit carrying it, measured on 2026-10-11.
_ACCEPTED = [
    ("v9.9.9", "9.9.9"),
    ("v9.9.10-rc.1", "9.9.10rc1"),
    ("v1.2.3-RC1", "1.2.3rc1"),
    ("v1.2.3-1", "1.2.3.post1"),
    ("v1.2.3.post1", "1.2.3.post1"),
    ("v1.2.3.dev", "1.2.3.dev0"),
    ("v1.2.3.1", "1.2.3.1"),
]

# Names the workflow's pattern accepts and ``setuptools_scm`` stopped on with
# ``Can't parse version from tag``, measured the same day.
_UNPARSEABLE = ["v0.0.0-ci.3", "v1.2.3-rc.1.2", "v1.2.3.x"]

# Names the pattern itself refuses. The last two are versions Python can parse:
# without the anchoring they would reach ``$GITHUB_OUTPUT`` with a second line.
_NOT_A_TAG = [
    "1.2.3",
    "v1.2",
    "v1.2.3rc1",
    "V1.2.3",
    "v1.2.3-rc-1",
    "",
    "v1.2.3+local",
    "v1.2.3\n",
    "v1.2.3\nx=1",
]


@pytest.mark.parametrize(("tag", "version"), _ACCEPTED)
def test_an_accepted_tag_gives_the_version_the_build_gives(
    tag: str, version: str
) -> None:
    assert str(_load_script().release_version(tag)) == version


@pytest.mark.parametrize("tag", _UNPARSEABLE)
def test_a_tag_the_build_cannot_parse_is_refused_and_says_so(tag: str) -> None:
    """#253: these passed the workflow's check and stopped the build."""
    with pytest.raises(ValueError, match="not a version the build can parse"):
        _load_script().release_version(tag)


@pytest.mark.parametrize("tag", _NOT_A_TAG)
def test_a_name_that_is_not_a_release_tag_is_refused(tag: str) -> None:
    with pytest.raises(ValueError, match="is not a release tag"):
        _load_script().release_version(tag)


def test_the_command_exits_by_the_tag_alone_when_no_files_are_named() -> None:
    accepted = _run("v9.9.10-rc.1")
    assert (accepted.returncode, accepted.stdout.strip()) == (
        0,
        "v9.9.10-rc.1 is version 9.9.10rc1",
    )

    refused = _run("v0.0.0-ci.3")
    assert refused.returncode == 1
    assert refused.stdout == ""
    assert (
        "Refusing to release: 'v0.0.0-ci.3' is not a version the build"
        in refused.stderr
    )


def test_files_built_for_the_tag_pass(tmp_path: Path) -> None:
    dist = _dist(tmp_path, "9.9.10rc1")
    result = _run("v9.9.10-rc.1", "--dist", str(dist))
    assert (result.returncode, result.stderr) == (0, "")


def test_files_named_for_another_version_are_refused(tmp_path: Path) -> None:
    """#252: release ``v0.0.0-ci.2`` carried files named ``0.1.1rc2.dev113``.

    The names here are the ones a build gave on a commit with no tag, and on a
    commit carrying both ``v9.9.9`` and the pushed ``v9.9.9-rc.1``.
    """
    script = _load_script()
    untagged = _dist(tmp_path, "0.1.1rc2.dev113")
    with pytest.raises(
        ValueError, match=r"tag v0\.1\.1-rc\.2 is version 0\.1\.1rc2, but"
    ):
        script.check_files("v0.1.1-rc.2", untagged)

    two_tags = _dist(tmp_path / "two-tags", "9.9.9")
    result = _run("v9.9.9-rc.1", "--dist", str(two_tags))
    assert result.returncode == 1
    assert (
        "tag v9.9.9-rc.1 is version 9.9.9rc1, but the build produced" in result.stderr
    )
    assert f"{_NAME}-9.9.9.tar.gz" in result.stderr
    assert f"{_NAME}-9.9.9-py3-none-any.whl" in result.stderr


def test_one_wrongly_named_file_is_enough_to_refuse(tmp_path: Path) -> None:
    script = _load_script()
    dist = _dist(tmp_path, "1.2.3", wheel=False)
    (dist / f"{_NAME}-1.2.3+dirty-py3-none-any.whl").touch()
    with pytest.raises(ValueError, match="but the build produced") as raised:
        script.check_files("v1.2.3", dist)
    assert f"{_NAME}-1.2.3.tar.gz" not in str(raised.value)


def test_a_build_that_left_no_pair_of_files_is_refused(tmp_path: Path) -> None:
    """An empty directory has no wrongly named file in it, and is not a release."""
    script = _load_script()
    expected = "must hold one source archive and one wheel"

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match=f"{expected}, found no file"):
        script.check_files("v1.2.3", empty)

    with pytest.raises(ValueError, match=expected):
        script.check_files(
            "v1.2.3", _dist(tmp_path / "archive-only", "1.2.3", wheel=False)
        )

    with pytest.raises(ValueError, match=expected):
        script.check_files("v1.2.3", _dist(tmp_path / "two-builds", "1.2.3", "1.2.4"))

    with pytest.raises(ValueError, match="is not a directory"):
        script.check_files("v1.2.3", tmp_path / "absent")

    stray = _dist(tmp_path / "stray", "1.2.3")
    (stray / "notes.txt").touch()
    with pytest.raises(ValueError, match=r"notes\.txt in .* is neither"):
        script.check_files("v1.2.3", stray)


def test_the_files_are_not_checked_against_a_tag_that_is_refused(
    tmp_path: Path,
) -> None:
    result = _run("v0.0.0-ci.3", "--dist", str(_dist(tmp_path, "0.0.0")))
    assert result.returncode == 1
    assert "not a version the build can parse" in result.stderr


# The table from #256, with a plain version and a suffix-less ``.dev`` added.
# The answer is ``packaging``'s ``Version.is_prerelease`` for the version the
# tag builds, which is true for a development version too.
_PRERELEASE = [
    ("v1.2.3", "false"),
    ("v1.2.3-rc.1", "true"),
    ("v1.2.3.rc1", "true"),
    ("v1.2.3.dev1", "true"),
    ("v1.2.3.dev", "true"),
    ("v1.2.3-1", "false"),
    ("v1.2.3.post1", "false"),
]


@pytest.mark.parametrize(("tag", "prerelease"), _PRERELEASE)
def test_the_command_writes_whether_the_version_is_a_prerelease(
    tag: str, prerelease: str, tmp_path: Path
) -> None:
    """#256: a hyphen marked ``v1.2.3-1`` and missed ``v1.2.3.rc1``."""
    output = tmp_path / "github-output"
    result = _run(tag, "--github-output", str(output))
    assert (result.returncode, result.stderr) == (0, "")
    assert output.read_text(encoding="utf-8") == f"prerelease={prerelease}\n"


def test_the_answer_is_added_to_what_the_file_already_holds(tmp_path: Path) -> None:
    """``$GITHUB_OUTPUT`` is shared by every command of a step."""
    output = tmp_path / "github-output"
    output.write_text("earlier=1\n", encoding="utf-8")
    assert _run("v1.2.3-rc.1", "--github-output", str(output)).returncode == 0
    assert output.read_text(encoding="utf-8") == "earlier=1\nprerelease=true\n"


def test_a_refused_tag_writes_no_answer(tmp_path: Path) -> None:
    output = tmp_path / "github-output"
    result = _run("v0.0.0-ci.3", "--github-output", str(output))
    assert result.returncode == 1
    assert "not a version the build can parse" in result.stderr
    assert not output.exists()

    wrong_files = _dist(tmp_path, "9.9.9")
    result = _run(
        "v9.9.9-rc.1", "--dist", str(wrong_files), "--github-output", str(output)
    )
    assert result.returncode == 1
    assert "but the build produced" in result.stderr
    assert not output.exists()


def test_the_answer_is_written_when_the_files_are_checked_too(tmp_path: Path) -> None:
    output = tmp_path / "github-output"
    dist = _dist(tmp_path, "9.9.10rc1")
    result = _run("v9.9.10-rc.1", "--dist", str(dist), "--github-output", str(output))
    assert (result.returncode, result.stderr) == (0, "")
    assert output.read_text(encoding="utf-8") == "prerelease=true\n"


def _workflow() -> dict[Any, Any]:
    loaded = yaml.safe_load(_WORKFLOW.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{_WORKFLOW} is not a YAML mapping"
    return loaded


# A `#` starts a comment at the start of a line or after a space. The one in
# `${GITHUB_REF#refs/tags/}` does not, and text after it is still code.
_COMMENT = re.compile(r"(^|\s)#.*$", re.MULTILINE)


def _code(text: str) -> str:
    return _COMMENT.sub("", text)


def _commands(job: dict[str, Any]) -> list[str]:
    """Each step's ``run`` text without its comments; empty for a ``uses`` step."""
    return [_code(str(step.get("run", ""))).strip() for step in job["steps"]]


def _needs(job: dict[str, Any]) -> list[str]:
    needs = job.get("needs", [])
    return [needs] if isinstance(needs, str) else list(needs)


def _always_runs_as_written(step: dict[str, Any]) -> None:
    changed = sorted({"if", "continue-on-error", "shell"} & set(step))
    assert not changed, (
        f"step {step.get('name')!r} sets {changed}, so it can be skipped, can fail "
        "without stopping the job, or does not run the command it shows"
    )


def _only_step(commands: list[str], needle: str) -> int:
    found = [index for index, command in enumerate(commands) if needle in command]
    assert len(found) == 1, f"expected one step running {needle!r}, found {len(found)}"
    return found[0]


def test_a_release_starts_only_from_a_pushed_version_tag() -> None:
    """#252: the hand start built whatever branch it was started on."""
    workflow = _workflow()
    # YAML 1.1 reads a bare `on:` key as the boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers == {"push": {"tags": ["v*"]}}, (
        f"release.yml must start on a pushed v* tag and nothing else, found {triggers!r}"
    )
    code = _code(_WORKFLOW.read_text(encoding="utf-8"))
    assert "inputs." not in code, (
        "release.yml reads an input that no trigger can supply"
    )


def test_no_job_can_be_skipped_or_fail_quietly() -> None:
    """A check that stops its job stops the release only if the jobs are chained."""
    jobs = _workflow()["jobs"]
    assert list(jobs) == ["validate", "build", "release"]
    for name, job in jobs.items():
        loose = sorted({"if", "continue-on-error"} & set(job))
        assert not loose, (
            f"the {name} job sets {loose}, so a failed check need not stop it"
        )
    assert _needs(jobs["validate"]) == []
    assert _needs(jobs["build"]) == ["validate"]
    assert sorted(_needs(jobs["release"])) == ["build", "validate"]


def test_the_tag_name_is_checked_before_anything_is_installed() -> None:
    """#253: the project install stops on the same tag, without naming a rule.

    ``pip install -e .`` derives the version from the tag, so a check placed
    after it never runs for a name ``setuptools_scm`` cannot parse.
    """
    steps = _workflow()["jobs"]["validate"]["steps"]
    commands = _commands({"steps": steps})
    check = _only_step(commands, "scripts/check-release-tag.py")
    assert commands[check].splitlines() == [
        "python -m pip install packaging",
        'python scripts/check-release-tag.py "$GITHUB_REF_NAME" '
        '--github-output "$GITHUB_OUTPUT"',
    ]
    _always_runs_as_written(steps[check])
    earlier = [command for command in commands[:check] if command]
    assert not earlier, f"these commands run before the tag name is checked: {earlier}"
    assert check < _only_step(commands, "pip install -e ."), (
        "the project is installed before the tag name is checked"
    )


def _attestations(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        step
        for step in steps
        if str(step.get("uses", "")).startswith("actions/attest-build-provenance@")
    ]


def test_the_built_files_are_checked_attested_and_then_uploaded() -> None:
    """#252, #272: the files are read after the build, and no command touches them after.

    The attestation step runs between the check and the upload. It is a
    ``uses`` step with no command of its own, so it can read the files and
    not rewrite them.
    """
    steps = _workflow()["jobs"]["build"]["steps"]
    commands = _commands({"steps": steps})
    check = _only_step(commands, "scripts/check-release-tag.py")
    assert commands[check] == (
        'python scripts/check-release-tag.py "$GITHUB_REF_NAME" --dist dist'
    )
    assert _only_step(commands, "python -m build") < check, (
        "the files are checked unbuilt"
    )
    _always_runs_as_written(steps[check])

    assert check + 2 < len(steps), (
        "fewer than two steps follow the check, so the files are not both "
        "attested and uploaded"
    )
    attest = steps[check + 1]
    assert _attestations([attest]) == [attest], (
        f"the step after the check is {attest.get('name')!r}, not the attestation: "
        "the files can change between being checked and being attested"
    )
    assert "run" not in attest, "the attestation step runs a command of its own"
    _always_runs_as_written(attest)
    assert attest["with"] == {"subject-path": "dist/*"}

    upload = steps[check + 2]
    assert str(upload.get("uses", "")).startswith("actions/upload-artifact@"), (
        f"the step after the attestation is {upload.get('name')!r}, not the "
        "upload: the files can change between being attested and being uploaded"
    )
    _always_runs_as_written(upload)
    assert upload["with"]["path"] == "dist/"
    assert check + 3 == len(steps), "a step runs after the upload"


def test_the_attestation_is_made_once_with_the_permissions_it_needs() -> None:
    """#272: the files were attached with nothing a deployer could verify them against.

    The action signs with the workflow's OIDC token and writes the attestation
    through the API, so the workflow must grant ``id-token: write`` and
    ``attestations: write``. A job-level ``permissions`` block replaces the
    workflow's, so none may set one.

    What this does not close: GitHub makes attestations for a private
    repository only on an Enterprise Cloud plan, so on this repository the step
    fails, and the release with it, until the repository is public. That is
    seen only on a runner.
    """
    workflow = _workflow()
    permissions = workflow.get("permissions", {})
    for scope in ("id-token", "attestations"):
        assert permissions.get(scope) == "write", (
            f"release.yml must grant {scope}: write at the workflow level, "
            f"found {permissions!r}"
        )

    jobs = workflow["jobs"]
    overriding = sorted(name for name, job in jobs.items() if "permissions" in job)
    assert not overriding, (
        f"these jobs set their own permissions, dropping the workflow's: {overriding}"
    )

    per_job = {name: len(_attestations(job["steps"])) for name, job in jobs.items()}
    assert per_job == {"validate": 0, "build": 1, "release": 0}, (
        "the files are attested once, in the job that built and checked them"
    )


def test_the_release_attaches_the_checked_files_under_the_pushed_tag() -> None:
    """The release job publishes what the build job checked, and builds nothing."""
    jobs = _workflow()["jobs"]
    uploads = [
        step["with"]
        for step in jobs["build"]["steps"]
        if str(step.get("uses", "")).startswith("actions/upload-artifact@")
    ]
    assert len(uploads) == 1, (
        f"expected one upload in the build job, found {len(uploads)}"
    )

    steps = jobs["release"]["steps"]
    downloads = [
        step["with"]
        for step in steps
        if str(step.get("uses", "")).startswith("actions/download-artifact@")
    ]
    assert downloads == [{"name": uploads[0]["name"], "path": "dist/"}], (
        "the release job attaches files other than the ones the build job checked"
    )

    commands = _commands({"steps": steps})
    writers = [
        command
        for command in commands
        if re.search(r"\bdist\b", command) or "-m build" in command
    ]
    assert not writers, f"a release-job command builds or touches dist/: {writers}"

    named = _only_step(commands, "GITHUB_OUTPUT")
    assert steps[named].get("id") == "version"
    assert 'VERSION="${GITHUB_REF#refs/tags/}"\n' in commands[named]
    _always_runs_as_written(steps[named])

    releases = [
        step for step in steps if str(step.get("uses", "")).startswith("softprops/")
    ]
    assert len(releases) == 1, f"expected one release step, found {len(releases)}"
    release = releases[0]
    _always_runs_as_written(release)
    assert release["with"]["tag_name"] == "${{ steps.version.outputs.tag_name }}"
    assert release["with"]["name"] == "Release ${{ steps.version.outputs.version }}"
    assert release["with"]["files"].split() == ["dist/*.tar.gz", "dist/*.whl"]


def test_the_release_job_matches_the_tag_with_the_scripts_pattern() -> None:
    """The release job has no Python, so it repeats the pattern; the two must agree."""
    commands = _commands(_workflow()["jobs"]["release"])
    command = commands[_only_step(commands, "GITHUB_OUTPUT")]
    patterns = re.findall(r'\[\[ ! "\$VERSION" =~ (\S+) \]\]', command)
    assert len(patterns) == 1, (
        f"expected one pattern match on $VERSION, found {patterns}"
    )
    assert patterns[0] == f"^{_load_script()._TAG.pattern}$"
    refusal = command.index("exit 1")
    assert command.index("[[ !") < refusal < command.index(">> "), (
        "the name is written to $GITHUB_OUTPUT before it is matched"
    )


def test_the_release_is_a_prerelease_when_the_version_is_one() -> None:
    """#256: the flag is the script's answer, carried from the validate job.

    Anything but the script's ``false`` gives a prerelease, so an answer that
    went missing between the jobs cannot publish a release candidate as the
    latest release; a full release would then be marked a prerelease instead.
    """
    jobs = _workflow()["jobs"]
    steps = jobs["validate"]["steps"]
    check = steps[_only_step(_commands({"steps": steps}), "--github-output")]
    assert check.get("id") == "tag", (
        f"the step that writes the answer has id {check.get('id')!r}"
    )
    assert jobs["validate"].get("outputs") == {
        "prerelease": "${{ steps.tag.outputs.prerelease }}"
    }

    flags = [
        step["with"].get("prerelease")
        for step in jobs["release"]["steps"]
        if str(step.get("uses", "")).startswith("softprops/")
    ]
    assert flags == ["${{ needs.validate.outputs.prerelease != 'false' }}"]
    assert "validate" in _needs(jobs["release"]), (
        "the release job reads an output of a job it does not need"
    )
    code = _code(_WORKFLOW.read_text(encoding="utf-8"))
    assert "contains(" not in code, (
        "release.yml calls contains(), which is how a hyphen in the tag decided"
    )
