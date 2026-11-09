#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The framework search tool.

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

import asyncio
from typing import Annotated

from pydantic import Field

from ..app import mcp
from ..documents.tools import list_frameworks
from ..exceptions import (
    DocumentUnavailableError,
    GitHubRateLimitError,
    SearchFailedError,
    UnknownDocumentError,
)
from ..logging import get_logger
from ..models import SearchResult, SearchResults
from ..search.engine import _search_single_framework

logger = get_logger("search.tools")


@mcp.tool()
async def search_frameworks(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=512,
            description=(
                "The exact phrase to find in the framework documents. Case is "
                "ignored; hyphens and underscores count as spaces."
            ),
        ),
    ],
    limit: Annotated[
        int,
        Field(
            ge=1,
            le=20,
            description=(
                "Maximum number of frameworks to return (1-20), taken in catalog "
                "order. At most one passage per framework. total_found counts "
                "every framework that says the phrase, including those this "
                "limit left out."
            ),
        ),
    ] = 5,
) -> SearchResults:
    """Find an exact phrase in the text of the AI governance frameworks.

    Frameworks only: this tool does not search risks or mitigations. To find a
    risk or a mitigation, call list_risks or list_mitigations, choose from the
    titles and descriptions, then read it with get_risk or get_mitigation.

    The query is matched as one phrase of whole words. Case is ignored, and
    hyphens and underscores count as spaces, so "third party" finds
    "third-party". Words of the query that appear apart are not a match, and
    neither is a word inside a longer one. Link addresses are not searched.

    Returns one result per framework that says the phrase, in the order
    list_frameworks gives them. Results are not ranked. Each has the
    framework's document_id (pass it to get_framework), the section and
    passage around the first occurrence, and occurrences, the number of times
    that framework says the phrase. If nothing is found, no framework says
    that phrase: try a shorter phrase or a single word.

    A search that could not run is an error, not an empty result. A framework
    that cannot be read is left out, and the search fails if none can be read.

    Args:
        query: The exact phrase to find. Examples:
               - "risk management"
               - "human oversight"
               - "supply chain"
               - "transparency"
        limit: Maximum number of frameworks to return (default: 5, max: 20),
               taken in catalog order. total_found counts every framework
               that says the phrase, including those this limit left out.

    Returns:
        SearchResults: The frameworks that say the phrase, in catalog order.
    """
    try:
        # Get all frameworks first
        frameworks_list = await list_frameworks()

        total_frameworks = len(frameworks_list.frameworks)
        logger.info(
            "Starting search across %d frameworks for query: %r",
            total_frameworks,
            query,
        )

        # Use asyncio.gather for parallel processing (official MCP best practice)
        search_tasks = [
            _search_single_framework(framework, query)
            for framework in frameworks_list.frameworks
        ]

        # gather returns in the order of its arguments, which is catalog order,
        # and that is the order the results are served in.
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        logger.info("Completed parallel search across %d frameworks", total_frameworks)

        found: list[SearchResult] = []
        unread = 0
        for framework, result in zip(
            frameworks_list.frameworks, search_results, strict=True
        ):
            if isinstance(result, SearchResult):
                found.append(result)
            elif isinstance(result, (DocumentUnavailableError, UnknownDocumentError)):
                # A framework that cannot be served is left out and the others
                # answer (#216). Only these two: they are what get_framework
                # raises for a document, where anything else is a search that
                # did not finish.
                unread += 1
                logger.warning(
                    "Left framework %s out of the search: %s", framework.id, result
                )
            elif isinstance(result, BaseException):
                # gather(return_exceptions=True) turned a raise into a value.
                # Logging it here would answer "0 results" for "we were
                # throttled" or "the search broke", so it is raised again.
                raise result

        if unread == total_frameworks:
            # Nothing was searched, so "0 results" would be a claim about
            # documents nobody read.
            raise SearchFailedError(SearchFailedError.NOTHING_READ)

        return SearchResults(query=query, results=found[:limit], total_found=len(found))

    except (GitHubRateLimitError, SearchFailedError):
        # Each carries the sentence the client is shown.
        raise
    except Exception as e:
        # An empty result here said "no framework has this phrase" for a
        # search that did not run (#224). The exception's own words stay in
        # the log. They were written for whoever runs the server.
        logger.error("Failed to search frameworks: %s", e)
        raise SearchFailedError(SearchFailedError.UNEXPECTED) from e
