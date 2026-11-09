# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The token verifier: fastmcp's ``JWTVerifier`` with this server's refusals.

fastmcp checks the signature, the issuer, the audience and the scopes, and
``exp`` only when the claim is present. This server requires more of a
token, and the requirements live here, in one subclass, so ``app.py`` builds
the verifier the same way on both key sources and the CALM authentication
control can name what is checked.

- A token without ``sub`` is refused: rate limits and the call log are keyed
  on the subject, and fastmcp would otherwise name the caller ``unknown``
  and share one bucket among all such callers. ``client_id`` or ``azp`` do
  not stand in for it (#320).
- A token without ``exp`` is refused: expiry is the only revocation this
  server has (#286).
- ``nbf`` is honoured when present, as RFC 7519 requires: a token not yet
  valid is refused (#286).
- The JWKS is fetched at most once a minute; meanwhile tokens are checked
  against the last set fetched (#285).
"""

from __future__ import annotations

import time
from typing import Any

from fastmcp.server.auth import AccessToken, JWTVerifier

from ..logging import get_logger

logger = get_logger("jwt_verifier")


#: Seconds between two fetches of the JWKS. fastmcp fetches for every token
#: whose key id it does not hold, so without this a stream of forged tokens
#: with distinct key ids is a stream of connections to the identity provider,
#: on every route, the health URLs included (#285).
JWKS_FETCH_INTERVAL_SECONDS = 60.0


class FinosJWTVerifier(JWTVerifier):
    """``JWTVerifier`` that also refuses what fastmcp lets through."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._jwks_last_attempt = float("-inf")
        self._jwks_last_document: dict[str, Any] | None = None

    async def _fetch_jwks(self) -> dict[str, Any]:
        """Fetch the key set at most once per interval.

        Inside the interval the last set fetched is answered instead, so a
        known key id is still served and an unknown one is refused without a
        request; with no set held (the one attempt failed), the fetch is
        refused outright until the interval has passed.
        """
        now = time.monotonic()
        if now - self._jwks_last_attempt < JWKS_FETCH_INTERVAL_SECONDS:
            if self._jwks_last_document is None:
                raise ValueError(
                    "JWKS fetch attempted within the last "
                    f"{JWKS_FETCH_INTERVAL_SECONDS:.0f} s and failed; not asking again yet"
                )
            return self._jwks_last_document
        self._jwks_last_attempt = now
        self._jwks_last_document = await super()._fetch_jwks()
        return self._jwks_last_document

    async def load_access_token(self, token: str) -> AccessToken | None:
        accepted = await super().load_access_token(token)
        if accepted is None:
            return None
        claims = accepted.claims or {}

        if not claims.get("sub"):
            logger.warning(
                "Bearer token rejected for client %s: no sub claim",
                accepted.client_id,
            )
            return None

        if "exp" not in claims:
            logger.warning(
                "Bearer token rejected for client %s: no exp claim",
                accepted.client_id,
            )
            return None

        nbf = claims.get("nbf")
        if nbf is not None and (not isinstance(nbf, int | float) or nbf > time.time()):
            logger.warning(
                "Bearer token rejected for client %s: not valid before %r",
                accepted.client_id,
                nbf,
            )
            return None

        return accepted
