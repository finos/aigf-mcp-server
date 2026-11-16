# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Complete relationship metadata reads, independent of best-effort titles."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from itertools import chain
from typing import TYPE_CHECKING

from ..exceptions import GitHubRateLimitError, ToolExecutionError
from ..logging import get_logger

if TYPE_CHECKING:
    from ..content.service import ContentService

logger = get_logger("documents.relationships")

_METADATA_FETCH_CONCURRENCY = 4


async def mitigation_metadata(
    service: "ContentService", filenames: list[str]
) -> AsyncIterator[object]:
    """Read every mitigation through the document cache, in catalog order.

    Probe serially so an unavailable backend costs one failed read. Then use
    fixed-size batches to bound both in-flight reads and allocated tasks. An
    unread document stops later batches, but every result in the current batch
    is inspected so throttling retains its retry guidance. Malformed metadata
    is left for the caller to validate after the complete read.
    """
    batches = chain(
        (filenames[:1],),
        (
            filenames[start : start + _METADATA_FETCH_CONCURRENCY]
            for start in range(1, len(filenames), _METADATA_FETCH_CONCURRENCY)
        ),
    )
    for batch in batches:
        documents = await asyncio.gather(
            *(service.get_document("mitigation", filename) for filename in batch),
            return_exceptions=True,
        )
        for document in documents:
            if isinstance(document, GitHubRateLimitError) or (
                isinstance(document, BaseException)
                and not isinstance(document, Exception)
            ):
                raise document
        unread = {
            filename: str(document)
            if isinstance(document, Exception)
            else "Document unavailable"
            for filename, document in zip(batch, documents, strict=True)
            if not isinstance(document, Mapping)
        }
        if unread:
            logger.warning(
                "Could not read mitigation relationship metadata: %s", unread
            )
            raise ToolExecutionError(
                "get_risk",
                "The mitigation relationships could not be loaded completely. Retry later.",
            )
        for document in documents:
            if isinstance(document, Mapping):
                yield document.get("metadata", {})
