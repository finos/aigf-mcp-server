# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The secret settings are ``SecretStr`` and never printed (#289).

``github_token`` and ``mcp_auth_public_key`` were plain strings:
``repr(settings)`` showed both, and a GitHub token the prefix check refused
was echoed in full on stderr, because pydantic appends the input value to a
validator's ``ValueError`` and the startup handler prints the message with
a bare ``print`` the redacting formatter never sees. (``cache_secret`` was
the third until #302 removed the setting.)

Decided on 2026-10-13: the prefix check goes, a token is required
only to be non-blank; GitHub answers a wrong one with 401 and discovery
falls back. The prefix list stays for log redaction (#290).
"""

from __future__ import annotations

import pytest

from finos_mcp.config import GITHUB_TOKEN_PREFIXES, Settings

pytestmark = pytest.mark.unit

TOKEN = "ghp_" + "t" * 36  # pragma: allowlist secret
CLASSIC = "a1b2c3d4" * 5  # a 40-hex classic token, which the prefix check refused
PEM = "-----BEGIN PUBLIC KEY-----\nMIIB\n-----END PUBLIC KEY-----"


def _settings(**values: object) -> Settings:
    return Settings(github_token=TOKEN, mcp_auth_public_key=PEM, **values)


@pytest.mark.parametrize("show", [repr, str])
def test_no_secret_appears_in_the_settings_text(show) -> None:
    text = show(_settings())
    for value in (TOKEN, "MIIB"):
        assert value not in text, f"{value[:8]}... is shown by {show.__name__}"


def test_the_values_are_read_through_get_secret_value() -> None:
    settings = _settings()
    assert settings.github_token is not None
    assert settings.github_token.get_secret_value() == TOKEN
    assert settings.mcp_auth_public_key is not None
    assert settings.mcp_auth_public_key.get_secret_value() == PEM


def test_a_classic_token_without_a_prefix_is_accepted() -> None:
    token = Settings(github_token=CLASSIC).github_token
    assert token is not None
    assert token.get_secret_value() == CLASSIC


@pytest.mark.parametrize("blank", ["", "   "])
def test_a_blank_token_is_not_set(blank: str) -> None:
    assert Settings(github_token=blank).github_token is None


def test_whitespace_around_a_token_is_removed() -> None:
    token = Settings(github_token=f"  {TOKEN}\n").github_token
    assert token is not None
    assert token.get_secret_value() == TOKEN


def test_a_validation_error_on_another_field_does_not_echo_a_secret() -> None:
    with pytest.raises(ValueError) as refused:
        _settings(log_level="LOUD")
    assert TOKEN not in str(refused.value)


def test_the_prefix_list_is_kept_for_redaction() -> None:
    assert "ghp_" in GITHUB_TOKEN_PREFIXES
    assert "github_pat_" in GITHUB_TOKEN_PREFIXES


@pytest.mark.parametrize("quote", ['"', "'"])
def test_one_pair_of_quotes_around_a_token_is_removed(quote: str) -> None:
    """A token written in quotes was sent with them, and GitHub refused it (#369).

    A shell or a dotenv file keeps quotes that are nested or escaped, and the
    401 at the first request did not say why.
    """
    token = Settings(github_token=f"{quote}{TOKEN}{quote}").github_token
    assert token is not None
    assert token.get_secret_value() == TOKEN


@pytest.mark.parametrize("written", ['"' + TOKEN, TOKEN + "'", '"' + TOKEN + "'"])
def test_an_unmatched_quote_is_kept(written: str) -> None:
    token = Settings(github_token=written).github_token
    assert token is not None
    assert token.get_secret_value() == written


@pytest.mark.parametrize("quoted_blank", ['""', "' '"])
def test_a_quoted_blank_token_is_not_set(quoted_blank: str) -> None:
    assert Settings(github_token=quoted_blank).github_token is None
