#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Error and validation helpers shared by every tool, resource and prompt.

Copyright 2025 FINOS

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from .logging import get_logger
from .security.request_validator import request_size_validator

logger = get_logger("safety")


def _rate_limited_message(kind: str, doc_id: str, retry_after: int | None) -> str:
    """Explain a GitHub throttle to the caller, in terms it can act on.

    Written for a model that will relay this to a person. It has to say three
    things the previous "Failed to load content for X" said none of: that the
    document exists, that the failure is temporary, and what makes it stop.
    Built from the retry time alone: the inner error's text carried the log's
    "GitHub content discovery failed:" prefix into the sentence (#334).
    """
    resets = (
        f"The limit resets in {retry_after} seconds."
        if retry_after is not None
        else "GitHub did not say when the limit resets."
    )
    return (
        f"The {kind} '{doc_id}' could not be retrieved right now because GitHub "
        f"is rate limiting content requests. {resets} "
        "This is a temporary throttle, not a missing or invalid document -- the "
        "same request will succeed once the limit resets. Retry shortly, or set "
        "FINOS_MCP_GITHUB_TOKEN to raise the hourly limit well above the "
        "unauthenticated 60 requests per hour."
    )


def _exceeds_resource_limit(content: str, document_id: str) -> bool:
    """Whether a document body is over the size this server returns."""
    try:
        request_size_validator.validate_resource_size(content)
    except ValueError as e:
        logger.warning("Document payload too large for %s: %s", document_id, e)
        return True
    return False


def _section_headings(content: str) -> list[str]:
    """The Markdown headings of a document body, in order."""
    return [
        line.strip("#").strip() for line in content.split("\n") if line.startswith("#")
    ]
