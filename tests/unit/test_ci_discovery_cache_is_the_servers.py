# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0
"""A workflow that caches the discovery list file caches the one the server writes (#406).

Since #293 the server writes its list file under ``~/.cache/finos-mcp`` unless
``FINOS_MCP_DISCOVERY_CACHE_DIR`` names a directory. Two jobs cached
``.cache/discovery`` and never set the variable, so the cache step saved an
empty directory and every run listed the repository through the API.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.unit

_SETTING = "FINOS_MCP_DISCOVERY_CACHE_DIR"


def _discovery_cache_jobs(root: Path) -> list[tuple[str, str, dict[str, Any]]]:
    """Each (workflow, job, job) whose steps cache a discovery directory."""
    found = []
    for workflow in sorted((root / ".github" / "workflows").glob("*.yml")):
        document = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for name, job in (document.get("jobs") or {}).items():
            for step in job.get("steps", []):
                path = str((step.get("with") or {}).get("path", ""))
                if str(step.get("uses", "")).startswith("actions/cache") and (
                    "discovery" in path
                ):
                    found.append((workflow.name, name, job))
    return found


def test_every_cached_discovery_directory_is_where_the_server_writes(
    pytestconfig: pytest.Config,
) -> None:
    root = Path(str(pytestconfig.rootpath))
    jobs = _discovery_cache_jobs(root)
    assert len(jobs) >= 2, f"expected the two discovery-cache jobs, found {jobs}"

    wrong = []
    for workflow, name, job in jobs:
        steps = job["steps"]
        (cached,) = [
            str(step["with"]["path"])
            for step in steps
            if str(step.get("uses", "")).startswith("actions/cache")
            and "discovery" in str((step.get("with") or {}).get("path", ""))
        ]
        settings = [
            str(env[_SETTING])
            for env in [job.get("env") or {}] + [s.get("env") or {} for s in steps]
            if _SETTING in env
        ]
        if not settings or not all(s.rstrip("/").endswith(cached) for s in settings):
            wrong.append(
                f"{workflow}:{name} caches {cached!r}, sets {_SETTING}={settings}"
            )
    assert not wrong, (
        f"These jobs cache a directory the server does not write to: {wrong}. "
        f"Set {_SETTING} to the cached path on the step that starts the server."
    )
