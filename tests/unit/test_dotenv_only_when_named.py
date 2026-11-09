# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A dotenv file is read only when ``FINOS_MCP_ENV_FILE`` names it (#283).

``Settings`` read ``.env`` from the working directory on every transport. On
stdio the working directory is the client's choice, often a project the user
opened, so a ``.env`` there was not the operator's: measured, one holding
``DATABASE_URL=x`` stopped startup, and one holding ``FINOS_MCP_BASE_URL``
moved the content host and widened the outbound allowlist to it.

Decided on 2026-10-13: no file is read unless the variable names
one; a named file that does not exist stops startup rather than being
skipped; an unread ``.env`` beside the server is announced once at startup;
an unknown name in a named file still stops startup (#194).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from finos_mcp import config
from finos_mcp.config import ENV_FILE_VARIABLE, Settings
from finos_mcp.content.fetch import HTTPClient

pytestmark = pytest.mark.unit

OTHER_HOST_DOCS = "https://other.example/a/b/c/docs"
DEFAULT_BASE_URL = (
    "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs"
)
DEFAULT_HOSTS = frozenset({"raw.githubusercontent.com", "api.github.com"})


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A working directory holding someone else's ``.env``, on stdio."""
    (tmp_path / ".env").write_text(
        f"FINOS_MCP_BASE_URL={OTHER_HOST_DOCS}\nDATABASE_URL=x\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(ENV_FILE_VARIABLE, raising=False)
    monkeypatch.delenv("FINOS_MCP_BASE_URL", raising=False)
    monkeypatch.setenv("FINOS_MCP_MCP_TRANSPORT", "stdio")
    return tmp_path


async def test_a_dotenv_file_in_the_working_directory_is_not_read(
    project: Path,
) -> None:
    settings = Settings()

    assert settings.base_url == DEFAULT_BASE_URL, (
        "a .env file the operator did not name moved the content host"
    )
    client = HTTPClient(settings=settings)
    try:
        assert client._allowed_fetch_hosts == DEFAULT_HOSTS
    finally:
        await client.close()


def test_a_named_file_is_read(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    named = project / "server.env"
    named.write_text(f"FINOS_MCP_BASE_URL={OTHER_HOST_DOCS}\n", encoding="utf-8")
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(named))

    assert Settings().base_url == OTHER_HOST_DOCS


def test_the_environment_wins_over_the_named_file(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    named = project / "server.env"
    named.write_text("FINOS_MCP_LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(named))
    monkeypatch.setenv("FINOS_MCP_LOG_LEVEL", "DEBUG")

    assert Settings().log_level == "DEBUG"


def test_a_named_file_that_does_not_exist_stops_startup(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = project / "missing.env"
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(missing))

    with pytest.raises(ValueError, match=r"missing\.env") as refused:
        Settings()
    assert ENV_FILE_VARIABLE in str(refused.value), (
        "the refusal does not say which variable named the file"
    )


def test_an_unknown_name_in_the_named_file_still_stops_startup(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    named = project / "server.env"
    named.write_text("FINOS_MCP_NOT_A_SETTING=1\n", encoding="utf-8")
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(named))

    with pytest.raises(ValidationError, match="not_a_setting"):
        Settings()


def test_a_name_without_the_prefix_in_the_named_file_is_ignored(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shared env file may hold other programs' names (#283, #368).

    ``DATABASE_URL=x`` in the named file stopped startup with
    ``extra_forbidden``. ``LOG_LEVEL`` is a setting's name without the
    prefix, and is not read as that setting either.
    """
    named = project / "server.env"
    named.write_text(
        "DATABASE_URL=x\nLOG_LEVEL=ERROR\nFINOS_MCP_LOG_LEVEL=DEBUG\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(named))
    monkeypatch.delenv("FINOS_MCP_LOG_LEVEL", raising=False)

    assert Settings().log_level == "DEBUG"


def test_an_unknown_name_beside_the_same_name_without_the_prefix_still_stops_startup(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dropping ``NOT_A_SETTING`` must not drop ``FINOS_MCP_NOT_A_SETTING``."""
    named = project / "server.env"
    named.write_text("NOT_A_SETTING=1\nFINOS_MCP_NOT_A_SETTING=1\n", encoding="utf-8")
    monkeypatch.setenv(ENV_FILE_VARIABLE, str(named))

    with pytest.raises(ValidationError, match="not_a_setting"):
        Settings()


def test_an_unread_dotenv_file_is_announced_once_at_startup(
    project: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    manager = config._settings_manager
    monkeypatch.setattr(manager, "_settings", None)

    with caplog.at_level(logging.WARNING, logger="finos-ai-governance-mcp"):
        manager.get_settings(reload=True)

    about_the_file = [
        record.getMessage()
        for record in caplog.records
        if ".env" in record.getMessage()
    ]
    assert len(about_the_file) == 1, about_the_file
    assert ENV_FILE_VARIABLE in about_the_file[0], (
        "the warning does not say how to have the file read"
    )
    assert about_the_file[0].startswith("A .env file"), about_the_file[0]


def test_no_announcement_without_a_dotenv_file(
    project: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    (project / ".env").unlink()
    manager = config._settings_manager
    monkeypatch.setattr(manager, "_settings", None)

    with caplog.at_level(logging.WARNING, logger="finos-ai-governance-mcp"):
        manager.get_settings(reload=True)

    assert not [r for r in caplog.records if ".env" in r.getMessage()]
