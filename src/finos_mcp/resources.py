#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""MCP resources: the same documents, addressed by URI instead of by tool call.

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

import functools
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated

from fastmcp.resources import FunctionResource, Resource
from fastmcp.server.providers import Provider
from fastmcp.utilities.components import FastMCPComponent
from fastmcp.utilities.versions import VersionSpec
from mcp.shared.exceptions import MCPError
from mcp.types import INTERNAL_ERROR, INVALID_PARAMS
from pydantic import Field

from .app import mcp
from .content.parse import document_id_from_filename, filename_stem
from .documents.format import _format_framework_name
from .documents.tools import get_framework, get_mitigation, get_risk
from .exceptions import (
    DocumentUnavailableError,
    GitHubRateLimitError,
    UnknownDocumentError,
)
from .logging import get_logger
from .service import _discovery_manager

logger = get_logger("resources")

# Each kind's description, said once for its template and its listed
# resources (#383).
_FRAMEWORK_DESCRIPTION = "Framework content from FINOS AI governance corpus."
_RISK_DESCRIPTION = "Risk documentation from FINOS AI governance corpus."
_MITIGATION_DESCRIPTION = "Mitigation documentation from FINOS AI governance corpus."


def _refusal(error: Exception, fallback_message: str) -> MCPError:
    """The JSON-RPC error a resource read answers with when it has no document.

    The body of a resource is the document, so a failure returned as text is
    served as one (#216). The get tools raise two errors written for a
    client, passed on as they are. Anything else is an exception nobody
    planned for, whose words were written for whoever runs the server:
    fastmcp would hand them to the client, so the client gets the fallback
    sentence and the log keeps the words. A pattern-matching sanitiser once
    stood here; it could redact a path from a sentence no client should see
    at all (#322).
    """
    if isinstance(error, DocumentUnavailableError | GitHubRateLimitError):
        return MCPError(code=INTERNAL_ERROR, message=str(error))
    return MCPError(code=INTERNAL_ERROR, message=fallback_message)


@mcp.resource(
    "finos://frameworks/{framework_id}",
    name="Framework Document",
    description=_FRAMEWORK_DESCRIPTION,
    mime_type="text/markdown",
)
async def get_framework_resource(
    framework_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="Framework identifier from list_frameworks().",
        ),
    ],
) -> str:
    """Get framework content as a resource.

    Args:
        framework_id: Framework identifier

    Returns:
        Framework content as text.
    """
    try:
        content = await get_framework(framework_id)
        return content.content
    except UnknownDocumentError as e:
        # The body of a resource is the document. Returned as text, this
        # message would be served as one (#193). The code is the one fastmcp
        # gives a URI that no template matches.
        raise MCPError(code=INVALID_PARAMS, message=e.message) from e
    except Exception as e:
        logger.error("Failed to get framework resource %s: %s", framework_id, e)
        raise _refusal(e, "Error loading framework resource.") from e


@mcp.resource(
    "finos://risks/{risk_id}",
    name="Risk Document",
    description=_RISK_DESCRIPTION,
    mime_type="text/markdown",
)
async def get_risk_resource(
    risk_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description="Risk identifier from list_risks().",
        ),
    ],
) -> str:
    """Get risk document as a resource.

    Args:
        risk_id: Risk document identifier

    Returns:
        Risk document content as text.
    """
    try:
        content = await get_risk(risk_id)
        return content.content
    except UnknownDocumentError as e:
        # The body of a resource is the document. Returned as text, this
        # message would be served as one (#193). The code is the one fastmcp
        # gives a URI that no template matches.
        raise MCPError(code=INVALID_PARAMS, message=e.message) from e
    except Exception as e:
        logger.error("Failed to get risk resource %s: %s", risk_id, e)
        raise _refusal(e, "Error loading risk resource.") from e


@mcp.resource(
    "finos://mitigations/{mitigation_id}",
    name="Mitigation Document",
    description=_MITIGATION_DESCRIPTION,
    mime_type="text/markdown",
)
async def get_mitigation_resource(
    mitigation_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description="Mitigation identifier from list_mitigations().",
        ),
    ],
) -> str:
    """Get mitigation document as a resource.

    Args:
        mitigation_id: Mitigation document identifier

    Returns:
        Mitigation document content as text.
    """
    try:
        content = await get_mitigation(mitigation_id)
        return content.content
    except UnknownDocumentError as e:
        # The body of a resource is the document. Returned as text, this
        # message would be served as one (#193). The code is the one fastmcp
        # gives a URI that no template matches.
        raise MCPError(code=INVALID_PARAMS, message=e.message) from e
    except Exception as e:
        logger.error("Failed to get mitigation resource %s: %s", mitigation_id, e)
        raise _refusal(e, "Error loading mitigation resource.") from e


def _document_resource(
    uri: str,
    read: Callable[[], Awaitable[str]],
    name: str,
    description: str,
) -> Resource:
    """One document as a plain resource, read through its template's handler.

    The description is passed, not left to fastmcp: it would take the
    reader's ``__doc__``, and a ``functools.partial``'s is its own (#383).
    """
    return FunctionResource.from_function(
        fn=read,
        uri=uri,
        name=name,
        description=description,
        mime_type="text/markdown",
    )


class DocumentResources(Provider):
    """``resources/list`` names every document the list tools name (#338).

    The three templates above say what a URI looks like; a client that
    discovers content through ``resources/list`` saw nothing, since the
    server published no plain resource. Each document is one here, read
    through the same handler as its template, so a read has one body.

    The list is built from the discovery listing alone (#348), so a risk or
    mitigation is named by its filename stem, ``ri-10_prompt-injection``, as
    the corpus cross-references it; title-casing gave ``Ri 10_Prompt
    Injection`` and ``Llm`` (#384). A framework keeps its declared title. Clients ask for this list when they connect; the list tools
    read every document to take its own title and description, and on a cold
    cache that was about 60 fetches before a connection got its answer. One
    listing also fails whole or not at all, so no kind of document is lost
    because another failed (#347). The list tools still publish the
    documents' own names.

    A listing that fails answers an empty list and one WARNING, not an error:
    a connection should not fail for what the list tools report in their own
    words on their own call.

    The listing runs for ``resources/list`` only. Two fastmcp defaults would
    run it elsewhere, and both are overridden below: the lookup behind a
    read filters the provider's whole listing for the URI, so this provider
    answers no URI and the template serves the read, through the very handler
    each listed resource names as its reader (fastmcp's path screening runs
    on that route, not on a resource a provider hands back); and the startup
    check for task-enabled components lists everything to find them, which
    would ask for the listing before the first request is served, so this
    provider says it has none.
    """

    async def _get_resource(
        self, uri: str, version: VersionSpec | None = None
    ) -> Resource | None:
        return None

    async def get_tasks(self) -> Sequence[FastMCPComponent]:
        return []

    async def _list_resources(self) -> Sequence[Resource]:
        try:
            discovery_service = await _discovery_manager.get_discovery_service()
            discovered = await discovery_service.discover_content()
        except Exception as error:
            logger.warning("resources/list names no document: %s", error)
            return []
        resources = []
        for file in discovered.framework_files:
            framework_id = file.filename.replace(".yml", "").replace(".yaml", "")
            resources.append(
                _document_resource(
                    f"finos://frameworks/{framework_id}",
                    functools.partial(
                        get_framework_resource, framework_id=framework_id
                    ),
                    _format_framework_name(framework_id),
                    _FRAMEWORK_DESCRIPTION,
                )
            )
        for file in discovered.risk_files:
            risk_id = document_id_from_filename(file.filename, "ri-")
            resources.append(
                _document_resource(
                    f"finos://risks/{risk_id}",
                    functools.partial(get_risk_resource, risk_id=risk_id),
                    filename_stem(file.filename),
                    _RISK_DESCRIPTION,
                )
            )
        for file in discovered.mitigation_files:
            mitigation_id = document_id_from_filename(file.filename, "mi-")
            resources.append(
                _document_resource(
                    f"finos://mitigations/{mitigation_id}",
                    functools.partial(
                        get_mitigation_resource, mitigation_id=mitigation_id
                    ),
                    filename_stem(file.filename),
                    _MITIGATION_DESCRIPTION,
                )
            )
        return resources


mcp.add_provider(DocumentResources())
