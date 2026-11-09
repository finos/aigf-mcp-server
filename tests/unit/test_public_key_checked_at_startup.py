# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""A static public key that cannot verify a token stops startup (#287).

``FINOS_MCP_MCP_AUTH_PUBLIC_KEY`` was checked for presence only; fastmcp
imported it at the first token and reported the failure at DEBUG, so the
server started and refused every token with a bare 401. Measured: a PEM
with a literal ``\\n`` (the form ``.env.example`` shows and a shell export
produces), ``not a key``, three spaces and an EC key each started the
server and failed every token; a private key started and accepted tokens.
This is the startup-versus-first-use gap #259 closed for the JWKS URI.

Decided on 2026-10-13: a literal ``\\n`` is converted to a line
break, since a PEM cannot legitimately contain the two characters; the rest
are refused at startup with the reason.
"""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from finos_mcp.config import Settings

pytestmark = pytest.mark.unit

_PUBLIC = (
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)


@pytest.fixture(scope="module")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def rsa_public_pem(rsa_key: rsa.RSAPrivateKey) -> str:
    return rsa_key.public_key().public_bytes(*_PUBLIC).decode()


@pytest.fixture(scope="module")
def rsa_private_pem(rsa_key: rsa.RSAPrivateKey) -> str:
    return rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@pytest.fixture(scope="module")
def ec_public_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.public_key().public_bytes(*_PUBLIC).decode()


def _settings(public_key: str) -> Settings:
    return Settings(
        mcp_auth_enabled=True,
        mcp_auth_public_key=public_key,
        mcp_auth_issuer="https://issuer.public-key.test",
        mcp_auth_audience="finos-mcp-server",
    )


def _refusal(public_key: str) -> str:
    with pytest.raises(ValueError, match="mcp_auth_public_key") as refused:
        _settings(public_key).validate_startup()
    return str(refused.value)


def test_a_generated_rsa_public_key_passes(rsa_public_pem: str) -> None:
    _settings(rsa_public_pem).validate_startup()


def test_a_literal_backslash_n_is_converted(rsa_public_pem: str) -> None:
    """The form ``.env.example`` shows: one line, ``\\n`` written out."""
    one_line = rsa_public_pem.strip().replace("\n", "\\n")
    settings = _settings(one_line)
    settings.validate_startup()
    assert settings.mcp_auth_public_key is not None
    assert settings.mcp_auth_public_key.get_secret_value() == rsa_public_pem.strip()


def test_text_that_is_not_a_key_is_refused_with_the_reason() -> None:
    assert "does not load" in _refusal("not a key")


def test_blank_text_is_refused() -> None:
    _refusal("   ")


def test_an_ec_key_is_refused_because_tokens_are_rs256(ec_public_pem: str) -> None:
    assert "not an RSA public key" in _refusal(ec_public_pem)


def test_a_private_key_is_refused_by_name(rsa_private_pem: str) -> None:
    assert "private key" in _refusal(rsa_private_pem)
