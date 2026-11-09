# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""What the static-fallback workflow says on failure holds no repair steps (#246).

``.github/workflows/validate-static-fallback.yml`` opened an issue that
repeated the steps of ``docs/static-fallback-maintenance.md``, and its log
message repeated them a third time. The copies went on saying what the guide
had said: run the script and commit ``discovery.py``, which the script does not
edit, and run ``python tests/test_id_mapping.py``, which runs no test.

The steps are in the guide and nowhere else. The tests below read every step of
the workflow that runs on a failed validation and fail on a step written there.

What they do not catch: a step written as a sentence, with no list, no code
fence, no script path and no git command.

The last three tests are #297: the validation step ran without a token and let
the sync test skip, so two skips exited 0, the step's outcome was ``success``
and the run reported "synchronized" while the only scheduled signal that the
catalog is stale had measured nothing. The step must pass the repository's
token and the variable under which the sync test fails instead of skipping.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest
import yaml

from finos_mcp.exceptions import GitHubRateLimitError
from tests.helpers import a_skip_is_a_failure, load_module

_WORKFLOW = ".github/workflows/validate-static-fallback.yml"
_GUIDE = "docs/static-fallback-maintenance.md"
_SYNC_TEST = "tests/integration/test_static_fallback_sync.py"

#: What a repair step looks like, and the name each is reported under. A list
#: item may be the argument of an ``echo``, and a backtick is written with a
#: backslash inside the JavaScript template that holds the issue body.
_STEP_SHAPES = {
    "a numbered list item": re.compile(
        r"""^\s*(?:echo\s+["']?)?\W*\d+\.\s""", re.MULTILINE
    ),
    "a code fence": re.compile(r"(?:\\?`){3}"),
    "a script path": re.compile(r"\bscripts/\S"),
    "a git command": re.compile(r"\bgit\s+[a-z]"),
}


def _failure_texts(root: Path) -> dict[str, str]:
    """The name and text of every step that runs when the validation failed."""
    workflow: dict[Any, Any] = yaml.safe_load(
        (root / _WORKFLOW).read_text(encoding="utf-8")
    )
    texts: dict[str, str] = {}
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "'failure'" not in str(step.get("if", "")):
                continue
            text = step.get("run") or step.get("with", {}).get("script")
            assert text, f"the failure step {step.get('name')!r} has no text to read"
            texts[step["name"]] = text
    return texts


@pytest.mark.unit
def test_the_workflow_has_a_failure_message_and_a_failure_issue(
    pytestconfig: pytest.Config,
) -> None:
    """Without this the two tests below pass over an empty selection."""
    texts = _failure_texts(pytestconfig.rootpath)

    assert len(texts) == 2, sorted(texts)
    assert any("issues.create" in text for text in texts.values()), sorted(texts)


@pytest.mark.unit
def test_a_failure_step_gives_no_repair_steps_of_its_own(
    pytestconfig: pytest.Config,
) -> None:
    found = [
        f"{name}: {shape} ({match.group(0).strip()!r})"
        for name, text in _failure_texts(pytestconfig.rootpath).items()
        for shape, pattern in _STEP_SHAPES.items()
        if (match := pattern.search(text))
    ]

    assert not found, (
        f"{_WORKFLOW} gives repair steps; they belong in {_GUIDE} only:\n"
        + "\n".join(found)
    )


@pytest.mark.unit
def test_a_failure_step_names_the_guide_and_the_guide_exists(
    pytestconfig: pytest.Config,
) -> None:
    root = pytestconfig.rootpath

    assert (root / _GUIDE).is_file(), f"{_GUIDE} does not exist"
    for name, text in _failure_texts(root).items():
        assert _GUIDE in text, f"{name!r} does not say where the repair steps are"


def _sync_test(root: Path) -> ModuleType:
    """The integration module, by path: ``tests/integration`` is not a package."""
    return load_module(root / _SYNC_TEST, "static_fallback_sync")


def _validation_step(root: Path) -> dict[str, Any]:
    workflow: dict[Any, Any] = yaml.safe_load(
        (root / _WORKFLOW).read_text(encoding="utf-8")
    )
    steps = [
        step
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if _SYNC_TEST in str(step.get("run", ""))
    ]
    assert len(steps) == 1, f"{_WORKFLOW} runs {_SYNC_TEST} in {len(steps)} steps"
    return cast("dict[str, Any]", steps[0])


@pytest.mark.unit
def test_the_validation_step_has_a_token_and_may_not_skip(
    pytestconfig: pytest.Config,
) -> None:
    root = pytestconfig.rootpath
    env = _validation_step(root).get("env") or {}
    no_skip = _sync_test(root).NO_SKIP_VARIABLE

    assert env.get("FINOS_MCP_GITHUB_TOKEN") == "${{ secrets.GITHUB_TOKEN }}", env
    assert str(env.get(no_skip, "")).strip(), f"{no_skip} is not set on the step: {env}"


class _Throttled:
    async def fetch_live_listing(self) -> dict[str, list[str]]:
        raise GitHubRateLimitError("API rate limit exceeded for 203.0.113.7.")


@pytest.mark.unit
async def test_a_throttled_listing_fails_under_the_variable_and_skips_without_it(
    pytestconfig: pytest.Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    sync = _sync_test(pytestconfig.rootpath)
    monkeypatch.setattr(sync, "_load_update_script", _Throttled)

    monkeypatch.setenv(sync.NO_SKIP_VARIABLE, "1")
    with (
        a_skip_is_a_failure(),
        pytest.raises(pytest.fail.Exception, match="rate limit") as failed,
    ):
        await sync._live_listing()
    assert sync.NO_SKIP_VARIABLE in str(failed.value), failed.value

    monkeypatch.delenv(sync.NO_SKIP_VARIABLE)
    with pytest.raises(pytest.skip.Exception, match="rate limit"):
        await sync._live_listing()
