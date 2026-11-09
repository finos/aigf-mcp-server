# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Single source of truth for the repository this server fetches content from.

Content reaches this server over two paths: the GitHub contents API (higher rate
limits, tried first) and raw.githubusercontent.com (fallback). Only the second
used to honour ``FINOS_MCP_BASE_URL``; the first hardcoded
``finos/ai-governance-framework``, as did the discovery service and its static
fallback URLs, which also pinned the literal ``main`` branch. A server pointed at
a fork therefore kept serving upstream content, silently, because the API path
wins whenever it succeeds.

This module derives every one of those coordinates - owner, repository, ref and
the path prefix inside the repository - from the single configured base URL, so
the two paths cannot disagree. There is nothing to cross-validate: there is only
one setting.

Hosts other than raw.githubusercontent.com (a GitHub Enterprise instance or an
internal mirror) cannot be addressed through api.github.com at all, so the API
optimisation is reported as unavailable for them rather than silently falling
back to the upstream repository.

Known limitation: a ref containing a slash (``release/2024``) is
indistinguishable from a path prefix in a raw URL - GitHub resolves that
ambiguity server-side and a client cannot. The third path segment is taken as the
ref, and the resolved coordinates are logged at startup so the mismatch is
visible rather than silent.
"""

import ipaddress
from dataclasses import dataclass
from urllib.parse import quote, urlparse

# Exact hostnames. Suffix matching would accept lookalikes such as
# raw.githubusercontent.com.evil.tld, for the same reason
# is_allowed_fetch_target() matches exactly.
RAW_CONTENT_HOST = "raw.githubusercontent.com"
GITHUB_API_HOST = "api.github.com"

# Segments that must never appear in a derived path, in any position.
_UNSAFE_SEGMENTS = frozenset({"", ".", ".."})


def why_not_a_fetch_target(url: str) -> str | None:
    """Return why the content client never requests ``url``, or None.

    The one statement of what a document URL must be: ``https``, with a
    host that is neither ``localhost`` nor a non-public address literal.
    ``is_allowed_fetch_target`` consults it before every request, and the
    ``base_url`` validator consults it at startup (#298), so a base URL
    every fetch would refuse is refused before the server serves anything,
    with this reason. It lives here, not in ``content_filter``, because
    ``config`` imports this module and the filter's logger reads ``config``.
    Encoded literals such as ``2130706433`` pass here and are stopped by
    the allowlist.
    """
    try:
        parsed = urlparse(url)
    except ValueError as error:
        return f"it does not parse as a URL ({error})"
    if parsed.scheme != "https":
        return "documents are fetched over https only" + (
            f", not {parsed.scheme}" if parsed.scheme else ""
        )
    hostname = parsed.hostname
    if not hostname:
        return "it names no host"
    if hostname == "localhost":
        return "its host is localhost"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return f"its host {hostname} is not a public address"
    return None


@dataclass(frozen=True)
class RepoTarget:
    """Resolved coordinates of the repository serving governance content.

    Attributes:
        raw_base_url: Normalized base URL for raw content, without trailing slash.
        owner: Repository owner, or None when the API is not addressable.
        repo: Repository name, or None when the API is not addressable.
        ref: Branch, tag or commit, or None when the API is not addressable.
        path_prefix: Path inside the repository that raw_base_url already points
            at (``docs`` upstream); empty when content sits at the repo root.
    """

    raw_base_url: str
    owner: str | None
    repo: str | None
    ref: str | None
    path_prefix: str

    @property
    def github_api_available(self) -> bool:
        """Whether this target can be addressed through the GitHub contents API."""
        return bool(self.owner and self.repo and self.ref)

    def repo_path(self, subdir: str, filename: str = "") -> str:
        """Return the path of a document relative to the repository root."""
        parts = [part for part in (self.path_prefix, subdir, filename) if part]
        return "/".join(parts)

    def api_contents_url(self, subdir: str, filename: str = "") -> str:
        """Return the GitHub contents API URL of a document or directory.

        The ref is pinned explicitly: without it the API serves the repository's
        default branch, which would reintroduce the divergence this module
        exists to remove whenever base_url names a non-default branch.

        Raises:
            ValueError: If this target is not addressable through the API.
        """
        if not self.github_api_available:
            raise ValueError(
                f"base_url host is not {RAW_CONTENT_HOST}, so the GitHub contents "
                "API cannot address it; use raw URLs for this target"
            )
        path = quote(self.repo_path(subdir, filename))
        return (
            f"https://{GITHUB_API_HOST}/repos/{self.owner}/{self.repo}"
            f"/contents/{path}?ref={quote(self.ref or '', safe='')}"
        )


def resolve_repo_target(base_url: str) -> RepoTarget:
    """Derive the repository target from a configured base URL.

    Args:
        base_url: Value of the ``base_url`` setting.

    Returns:
        The resolved target. Non-GitHub hosts resolve with owner, repo and ref
        unset, which disables the API path rather than defaulting it upstream.

    Raises:
        ValueError: If base_url is not a usable HTTP(S) URL, or names
            raw.githubusercontent.com without addressing a repository.
    """
    normalized = base_url.rstrip("/")
    parsed = urlparse(normalized)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"base_url is not a usable HTTP or HTTPS URL: {base_url!r}")

    # urlparse lowercases the hostname, so this comparison is case-insensitive.
    if parsed.hostname != RAW_CONTENT_HOST:
        return RepoTarget(
            raw_base_url=normalized,
            owner=None,
            repo=None,
            ref=None,
            path_prefix="",
        )

    segments = parsed.path.split("/")[1:] if parsed.path.startswith("/") else []
    if len(segments) < 3:
        raise ValueError(
            f"base_url {base_url!r} names {RAW_CONTENT_HOST} but does not address a "
            "repository; expected https://raw.githubusercontent.com/<owner>/<repo>/<ref>[/<path>]"
        )
    # Empty and relative segments are rejected everywhere, not just in the
    # owner/repo/ref positions: they would also let a configured prefix walk out
    # of the repository subtree the API URLs are built from.
    unsafe = [segment for segment in segments if segment in _UNSAFE_SEGMENTS]
    if unsafe:
        raise ValueError(
            f"base_url {base_url!r} contains an empty or relative path segment"
        )

    owner, repo, ref, *prefix_segments = segments
    return RepoTarget(
        raw_base_url=normalized,
        owner=owner,
        repo=repo,
        ref=ref,
        path_prefix="/".join(prefix_segments),
    )
