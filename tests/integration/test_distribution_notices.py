"""Verify the ownership notices that a user actually receives in a wheel.

Build from the index's file inventory and current contents, in a temporary
directory: no stale egg-info, build output, or source-tree modifications. The
version override replaces Git metadata in that copy, not package metadata.
"""

import os
import re
import shutil
import subprocess
import sys
from email.parser import Parser
from pathlib import Path
from zipfile import ZipFile

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def distribution_files(
    pytestconfig: pytest.Config, tmp_path_factory: pytest.TempPathFactory
) -> dict[str, bytes]:
    root = Path(str(pytestconfig.rootpath))
    work = tmp_path_factory.mktemp("distribution-notices")
    source = work / "source"
    source.mkdir()
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.split("\0")
    for name in filter(None, tracked):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--wheel-dir",
            str(work / "wheels"),
            ".",
        ],
        cwd=source,
        env={**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": "0.0.0"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"notice verification could not build the wheel: {result.stdout}\n{result.stderr}"
    )
    wheels = list((work / "wheels").glob("*.whl"))
    assert len(wheels) == 1, f"expected one built wheel, found {wheels}"
    with ZipFile(wheels[0]) as wheel:
        return {name: wheel.read(name) for name in wheel.namelist()}


@pytest.mark.parametrize(
    "filename", ["LICENSE", "NOTICE", "LICENSE.spdx", "FINOS-LICENSE.md"]
)
def test_wheel_ships_declared_license_files(
    distribution_files: dict[str, bytes], filename: str
) -> None:
    metadata = next(
        content.decode()
        for name, content in distribution_files.items()
        if name.endswith(".dist-info/METADATA")
    )
    declared = Parser().parsestr(metadata).get_all("License-File", [])
    assert filename in declared, f"wheel METADATA omits License-File: {filename}"
    matches = [
        name
        for name in distribution_files
        if name.endswith(f".dist-info/licenses/{filename}")
    ]
    assert len(matches) == 1, (
        f"wheel omits the declared license file {filename}: {matches}"
    )


@pytest.mark.parametrize("filename", ["LICENSE", "NOTICE", "LICENSE.spdx"])
def test_wheel_notices_identify_the_software_owner(
    distribution_files: dict[str, bytes], filename: str
) -> None:
    content = next(
        data.decode()
        for name, data in distribution_files.items()
        if name.endswith(f"/licenses/{filename}")
    )
    # FINOS holds every credit (#399, reversing #80). NOTICE keeps FINOS's
    # upstream wording; LICENSE and LICENSE.spdx use the short form.
    assert "FINOS" in content and "Hugo Calderon" not in content, (
        f"{filename} does not give the software copyright to FINOS alone"
    )
    assert re.search(r"Copyright 2025 (- )?FINOS", content), (
        f"{filename} omits the FINOS software copyright"
    )


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("Creator", "Organization: FINOS (info@finos.org)"),
        ("PackageName", "finos-ai-governance-mcp-server"),
        ("PackageOriginator", "Organization: FINOS (info@finos.org)"),
        ("PackageHomePage", "https://github.com/finos/aigf-mcp-server"),
        ("PackageLicenseDeclared", "Apache-2.0"),
        ("PackageLicenseConcluded", "Apache-2.0"),
        ("PackageCopyrightText", "Copyright 2025 FINOS"),
    ],
)
def test_wheel_spdx_describes_this_package(
    distribution_files: dict[str, bytes], field: str, expected: str
) -> None:
    content = next(
        data.decode()
        for name, data in distribution_files.items()
        if name.endswith("/licenses/LICENSE.spdx")
    )
    values = [
        line.partition(": ")[2]
        for line in content.splitlines()
        if line.startswith(f"{field}: ")
    ]
    assert values == [expected], f"SPDX {field} must describe this package: {values}"


def test_wheel_preserves_finos_content_attribution(
    distribution_files: dict[str, bytes],
) -> None:
    notice = next(
        data.decode()
        for name, data in distribution_files.items()
        if name.endswith("/licenses/NOTICE")
    )
    assert "FINOS and contributors" in notice, "NOTICE omits FINOS content attribution"
    assert "https://github.com/finos/ai-governance-framework" in notice, (
        "NOTICE omits the content source"
    )
    assert "https://creativecommons.org/licenses/by/4.0/" in notice, (
        "NOTICE omits the content license"
    )
