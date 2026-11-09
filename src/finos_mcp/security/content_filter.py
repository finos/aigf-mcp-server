# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""
Content security validation and filtering.

Bounds what is fetched: the size of a body and the host of a URL. A
content-type check and a header builder with a Content Security Policy once
stood here too; no fetch consulted either (#325). A fetched body is not scanned for browser-XSS
patterns: the consumer is a model reading Markdown, the trust boundary is
stated in ``SERVER_TRUST_INSTRUCTIONS``, and the scan refused ordinary prose
such as ``config = "x"`` and was quadratic on long words (#122, #282).
"""

import urllib.parse

from ..logging import get_logger
from .repo_target import why_not_a_fetch_target

logger = get_logger(__name__)


class ContentSecurityValidator:
    """Bound fetched content by size.

    Its URL check, ``is_safe_url``, repeated ``why_not_a_fetch_target``
    with a looser scheme rule, and both ran on every request (#379).
    """

    def __init__(self, max_content_size: int = 10_000_000):  # 10MB default
        """Initialize content security validator.

        Args:
            max_content_size: Maximum allowed content size in bytes
        """
        self.max_content_size = max_content_size


def is_allowed_fetch_target(url: str, allowed_hosts: frozenset[str]) -> bool:
    """Check whether a URL may be fetched, against an explicit host allowlist.

    This is the primary SSRF control for outbound requests.
    why_not_a_fetch_target() blocks internal IP literals, but cannot catch
    encoded forms such as "2130706433" or hostnames that resolve to internal
    addresses, because those only resolve at the DNS layer. An allowlist
    closes that gap: this server only ever talks to a known set of content
    hosts.

    Args:
        url: URL about to be fetched
        allowed_hosts: Exact hostnames permitted as fetch targets

    Returns:
        True if the URL may be fetched, False otherwise
    """
    # The same check the base_url validator applies at startup (#298).
    reason = why_not_a_fetch_target(url)
    if reason:
        logger.warning("Blocked fetch target %s: %s", url, reason)
        return False
    hostname = urllib.parse.urlparse(url).hostname

    # Exact match only. Suffix matching would allow lookalikes such as
    # raw.githubusercontent.com.evil.tld.
    if hostname not in allowed_hosts:
        logger.warning("Blocked non-allowlisted fetch target: %s", hostname)
        return False

    return True


# Global instance for easy access
content_security_validator = ContentSecurityValidator()
