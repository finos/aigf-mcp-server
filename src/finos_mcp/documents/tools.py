#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""The six read tools: list and get, for frameworks, risks and mitigations.

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
from typing import Annotated, NamedTuple

from pydantic import Field

from ..app import mcp
from ..content.github_api import DIRECTORIES, ContentDirectory, GitHubFileInfo
from ..content.parse import (
    document_id_from_filename,
    filename_stem,
    frontmatter_title,
    parse_yaml_document,
    safe_title_fragment,
    yaml_title_from_document,
)
from ..documents.format import (
    _format_framework_name,
    _framework_document,
    _resolve_document_names,
    _resolve_framework_names,
)
from ..exceptions import (
    DocumentThrottledError,
    DocumentUnavailableError,
    GitHubRateLimitError,
    ToolExecutionError,
    UnknownDocumentError,
)
from ..logging import get_logger
from ..models import (
    DocumentContent,
    DocumentInfo,
    DocumentList,
    Framework,
    FrameworkContent,
    FrameworkList,
)
from ..safety import (
    _exceeds_resource_limit,
    _rate_limited_message,
    _section_headings,
)
from ..service import _discovery_manager, get_service

logger = get_logger("documents.tools")

#: What a client is shown when a listing stops on something nobody planned
#: for. The exception's own words stay in the log.
_LISTING_FAILED = "The listing failed before it finished. Retry later."


def _listing_failed(tool_name: str, error: Exception) -> ToolExecutionError:
    """A tool error for a listing that did not finish (#296).

    The list tools used to answer any exception, past discovery, from the
    static lists as ``static_fallback``: a fault in name resolution after a
    healthy listing was answered with 24 static names labelled as a GitHub
    outage. Discovery is the one place that picks the catalog; it never
    raises for a GitHub it cannot reach, so what reaches here is a defect.
    """
    logger.error("Failed to %s: %s", tool_name, error)
    return ToolExecutionError(tool_name, _LISTING_FAILED)


@mcp.tool()
async def list_frameworks() -> FrameworkList:
    """List all available AI governance frameworks from the FINOS repository.

    Use this tool to discover what AI governance frameworks are available for analysis,
    compliance checking, or reference. This is typically the first step when helping
    users understand regulatory requirements or compliance gaps.

    Examples of available frameworks (call this tool for the full, current list):
    - NIST AI 600-1 (US federal AI governance)
    - EU AI Act (European Union AI regulation)
    - ISO 42001 (international AI management standard)
    - OWASP LLM Top 10 (AI security best practices)
    - OWASP ML Security Top 10 (machine learning security best practices)

    Each entry is named and described by the document itself, so this reads
    every document in the catalog rather than only the file listing -- one
    cached fetch per document. A document that cannot be read keeps a name
    derived from its filename and has no description, so the listing is always
    complete.

    Returns:
        FrameworkList: Structured list with framework IDs, names, and descriptions.
        'description' is the framework file's own description, or null.
        Use the 'id' field from results with get_framework() for detailed content.
    """
    try:
        discovery_manager = _discovery_manager
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()

        # Convert framework YAML files to Framework objects
        frameworks = []
        framework_names = await _resolve_framework_names(
            [f.filename for f in discovery_result.framework_files]
        )
        for file_info, listed in zip(
            discovery_result.framework_files, framework_names, strict=True
        ):
            # Extract ID from filename (remove extension)
            framework_id = file_info.filename.replace(".yml", "").replace(".yaml", "")

            frameworks.append(
                Framework(
                    id=framework_id, name=listed.name, description=listed.description
                )
            )

        return FrameworkList(
            frameworks=frameworks,
            total_count=len(frameworks),
            source=discovery_result.source,
        )
    except Exception as e:
        raise _listing_failed("list_frameworks", e) from e


@mcp.tool()
async def get_framework(
    framework_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="Framework identifier from list_frameworks() (e.g. nist-ai-600-1).",
        ),
    ],
) -> FrameworkContent:
    """Get the complete content of a specific AI governance framework.

    Use this tool to retrieve detailed framework content for compliance analysis,
    requirement extraction, or regulatory guidance. The content includes structured
    requirements, controls, and implementation guidance.

    Args:
        framework_id: Framework identifier from list_frameworks().
                  Examples: 'nist-ai-600-1', 'eu-ai-act', 'iso-42001', 'owasp-llm'

    Common use cases:
    - Analyzing compliance requirements for a specific regulation
    - Extracting risk assessment criteria
    - Understanding implementation guidelines
    - Comparing regulatory approaches across frameworks

    Returns:
        FrameworkContent: The framework as a Markdown document -- its title,
        description and source, then each entry with its id, name and link --
        and the number of entries as `entry_count`.

    An id that no document has is an error, not a document: the message
    says to call list_frameworks() for the valid ids.
    A document that exists and cannot be served is an error too: the
    message says whether it could not be loaded, is too large, or is empty.
    """
    try:
        service = await get_service()

        # First, discover to find the correct filename.
        discovery_manager = _discovery_manager
        discovery_service = await discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()
        framework_filenames = [
            file_info.filename for file_info in discovery_result.framework_files
        ]

        # Find the framework file by ID
        target_filename = None
        for filename in framework_filenames:
            file_id = filename.replace(".yml", "").replace(".yaml", "")
            if file_id == framework_id:
                target_filename = filename
                break

        if not target_filename:
            raise UnknownDocumentError(
                safe_title_fragment(framework_id), "framework", "list_frameworks"
            )

        # Get the document content
        doc = await service.get_document("framework", target_filename)

        if not doc:
            raise DocumentUnavailableError(
                safe_title_fragment(framework_id),
                "framework",
                DocumentUnavailableError.NOT_LOADED,
            )

        content = doc.get("content", "")
        if not content.strip():
            raise DocumentUnavailableError(
                safe_title_fragment(framework_id),
                "framework",
                DocumentUnavailableError.EMPTY,
            )
        # The framework's own declared name, not the hardcoded map's guess.
        # Resolved once and used for both the title field and the body
        # heading, so the two cannot disagree (#118).
        # Parsed once, and off the event loop. Halving two parses to one
        # was only half the fix: yaml.safe_load on a 770KB mapping -- well
        # under the 1MB resource cap -- measures ~0.8s, and under the HTTP
        # transport every other in-flight request stalls for that long.
        # ContentService already offloads the equivalent frontmatter parse
        # via to_thread for exactly this reason.
        parsed = await asyncio.to_thread(parse_yaml_document, content)
        title = yaml_title_from_document(parsed) or _format_framework_name(framework_id)
        # Off the loop for the same reason as the parse above: this reads
        # the file into a node tree, a second pass of about the cost of the
        # first.
        document = await asyncio.to_thread(_framework_document, content, title)
        if _exceeds_resource_limit(document.body, f"framework:{framework_id}"):
            raise DocumentUnavailableError(
                safe_title_fragment(framework_id),
                "framework",
                DocumentUnavailableError.TOO_LARGE,
            )

        return FrameworkContent(
            framework_id=framework_id,
            title=title,
            content=document.body,
            # The entries the body lists. This counted the file's top-level
            # keys: 4 for a framework of 306 articles (#192).
            entry_count=document.entries,
        )
    except (UnknownDocumentError, DocumentUnavailableError):
        # Raised, not returned as content: a record saying "not found" or
        # "could not be loaded" is a successful result, and a caller reads
        # that as the document (#193, #216).
        raise
    except GitHubRateLimitError as e:
        # Raised, not returned as content. Returning it would make the throttle
        # indistinguishable from a document whose body happens to say this, and
        # the search helpers call this tool -- a returned message is a string
        # they would search for matches instead of a failure they must report.
        logger.warning("Rate limited loading framework %s: %s", framework_id, e)
        raise DocumentThrottledError(
            _rate_limited_message("framework", framework_id, e.retry_after),
            e.retry_after,
        ) from e
    except Exception as e:
        # The exception's own words stay in the log. They were written for
        # whoever runs the server, not for a client.
        logger.error("Failed to get framework content: %s", e)
        raise DocumentUnavailableError(
            safe_title_fragment(framework_id),
            "framework",
            DocumentUnavailableError.NOT_LOADED,
        ) from e


class _Kind(NamedTuple):
    """What tells a risk tool from a mitigation tool (#314).

    The four tools over these documents were one body written twice, so
    #193 and #216 were each fixed three times. Everything that differs
    between the two kinds is here; the bodies are ``_list_documents`` and
    ``_get_document`` below.
    """

    doc_type: str
    #: The tool a client calls for the valid ids.
    listing_tool: str
    #: How the throttle explanation names one document.
    phrase: str
    #: The prefixes the corpus writes before the number when it refers to a
    #: document of this kind (#337). Mitigations were once ``ct-`` files and
    #: the documents still link to them that way.
    short_prefixes: tuple[str, ...]

    @property
    def directory(self) -> ContentDirectory:
        """Where the documents are, and the filename prefix of their ids (#380)."""
        return DIRECTORIES[self.doc_type]


_RISK = _Kind("risk", "list_risks", "risk document", ("ri-",))
_MITIGATION = _Kind(
    "mitigation", "list_mitigations", "mitigation document", ("mi-", "ct-")
)


def _names_the_document(requested: str, document_id: str, kind: _Kind) -> bool:
    """Whether ``requested`` is ``document_id`` in a form the corpus writes (#337).

    The published id is ``10_prompt-injection``. The documents refer to it as
    ``ri-10``, and the filename is ``ri-10_prompt-injection.md``, so the
    number alone identifies the document and a client that read one document
    knows the number of the next. Accepted, case-insensitively: the id, the
    id behind one of the kind's prefixes, and the number alone or behind a
    prefix. A number matches whole, so ``1`` is not ``10``.
    """
    asked = requested.strip().lower()
    for prefix in kind.short_prefixes:
        if asked.startswith(prefix):
            asked = asked[len(prefix) :]
            break
    if asked.isdigit():
        return document_id.partition("_")[0] == asked
    return asked == document_id.lower()


async def _list_documents(kind: _Kind) -> DocumentList:
    """The listing both list tools publish: each document named by itself."""
    try:
        discovery_service = await _discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()
        files: list[GitHubFileInfo] = discovery_result.files_in(kind.directory)
        listed = await _resolve_document_names(
            kind.doc_type, [f.filename for f in files]
        )
        documents = [
            DocumentInfo(
                id=document_id_from_filename(file_info.filename, kind.directory.prefix),
                name=entry.name,
                filename=file_info.filename,
                description=entry.description,
            )
            for file_info, entry in zip(files, listed, strict=True)
        ]
        return DocumentList(
            documents=documents,
            total_count=len(documents),
            document_type=kind.doc_type,
            source=discovery_result.source,
        )
    except Exception as e:
        raise _listing_failed(kind.listing_tool, e) from e


async def _get_document(kind: _Kind, document_id: str) -> DocumentContent:
    """Resolve the id, fetch, check, and build the document both get tools publish.

    An id that no document has is an error, not a document (#193). A
    document that exists and cannot be served is an error too (#216), and
    the message says which of three things happened. A GitHub throttle is
    raised with an explanation a client can act on, never returned as a
    body the search helpers would read as one.
    """
    try:
        service = await get_service()
        discovery_service = await _discovery_manager.get_discovery_service()
        discovery_result = await discovery_service.discover_content()
        files: list[GitHubFileInfo] = discovery_result.files_in(kind.directory)
        matches = [
            file_info.filename
            for file_info in files
            if _names_the_document(
                document_id,
                document_id_from_filename(file_info.filename, kind.directory.prefix),
                kind,
            )
        ]
        if len(matches) != 1:
            # None, or a short id two files share (#349): serving the first
            # in listing order would answer with a document the caller may
            # not have meant, and that order can change between listings.
            raise UnknownDocumentError(
                safe_title_fragment(document_id),
                kind.doc_type,
                kind.listing_tool,
                [
                    document_id_from_filename(name, kind.directory.prefix)
                    for name in matches
                ],
            )
        target_filename = matches[0]
        # From here on the id is the published one, whatever form the caller
        # wrote: the record and the log name the document as the listing does.
        document_id = document_id_from_filename(target_filename, kind.directory.prefix)

        doc = await service.get_document(kind.doc_type, target_filename)
        if not doc:
            raise DocumentUnavailableError(
                safe_title_fragment(document_id),
                kind.doc_type,
                DocumentUnavailableError.NOT_LOADED,
            )

        content = doc.get("content", "")
        if not content.strip():
            # A document that is frontmatter-only, or whose body fetched
            # empty. Its declared title over an empty body reads as a
            # document that says nothing.
            raise DocumentUnavailableError(
                safe_title_fragment(document_id),
                kind.doc_type,
                DocumentUnavailableError.EMPTY,
            )
        if _exceeds_resource_limit(content, f"{kind.doc_type}:{document_id}"):
            raise DocumentUnavailableError(
                safe_title_fragment(document_id),
                kind.doc_type,
                DocumentUnavailableError.TOO_LARGE,
            )
        # The frontmatter title, not the filename. get_document returns the
        # parsed frontmatter under "metadata"; reading a top-level "title"
        # key it never sets made this fallback unconditional (#118).
        title = frontmatter_title(doc.get("metadata")) or safe_title_fragment(
            filename_stem(target_filename)
        )
        return DocumentContent(
            document_id=document_id,
            title=title,
            content=content,
            sections=_section_headings(content),
        )

    except (UnknownDocumentError, DocumentUnavailableError):
        # Raised, not returned as content: a record saying "not found" or
        # "could not be loaded" is a successful result, and a caller reads
        # that as the document (#193, #216).
        raise
    except GitHubRateLimitError as e:
        logger.warning("Rate limited loading %s %s: %s", kind.doc_type, document_id, e)
        raise DocumentThrottledError(
            _rate_limited_message(kind.phrase, document_id, e.retry_after),
            e.retry_after,
        ) from e
    except Exception as e:
        # The exception's own words stay in the log. They were written for
        # whoever runs the server, not for a client.
        logger.error(
            "Failed to get %s content for %s: %s", kind.doc_type, document_id, e
        )
        raise DocumentUnavailableError(
            safe_title_fragment(document_id),
            kind.doc_type,
            DocumentUnavailableError.NOT_LOADED,
        ) from e


@mcp.tool()
async def list_risks() -> DocumentList:
    """List all available AI governance risk documents for threat assessment and security planning.

    Use this tool to discover security risks, privacy threats, and compliance vulnerabilities
    in AI systems. Each risk document provides detailed threat analysis, impact assessment,
    and contextual information for risk management decisions.

    Each entry is named and described by the document itself, so this reads
    every document in the catalog rather than only the file listing -- one
    cached fetch per document. A document that cannot be read keeps a name
    derived from its filename and has no description, so the listing is always
    complete.

    Returns:
        DocumentList: Structured list of risk documents with ids, names and descriptions.
        'description' is the opening of the document's own summary, or null.
        Use the 'id' field from results with get_risk() for the full document.
    """
    return await _list_documents(_RISK)


@mcp.tool()
async def list_mitigations() -> DocumentList:
    """List all available AI governance mitigation strategies for risk reduction and security controls.

    Use this tool to discover security controls, privacy safeguards, and compliance measures
    for AI systems. Each mitigation document provides actionable controls, implementation guidance,
    and best practices for reducing identified risks and threats.

    Each entry is named and described by the document itself, so this reads
    every document in the catalog rather than only the file listing -- one
    cached fetch per document. A document that cannot be read keeps a name
    derived from its filename and has no description, so the listing is always
    complete.

    Returns:
        DocumentList: Structured list of mitigation documents with ids, names and descriptions.
        'description' is the opening of the document's own purpose section, or null.
        Use the 'id' field from results with get_mitigation() for the full document.
    """
    return await _list_documents(_MITIGATION)


@mcp.tool()
async def get_risk(
    risk_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description=(
                "Risk document identifier from list_risks(), e.g. "
                "10_prompt-injection; the short form the documents use, "
                "ri-10 or 10, is accepted too."
            ),
        ),
    ],
) -> DocumentContent:
    """Get the complete content of a specific AI governance risk document for detailed threat analysis.

    Use this tool to retrieve comprehensive risk information including threat descriptions,
    impact assessments, likelihood analysis, and contextual details. Essential for security
    assessments, compliance audits, and risk management planning.

    Args:
        risk_id: Risk document identifier from list_risks(), or the short
                 form the documents use to refer to it: ri-10 or 10.
                Examples: '9_data-poisoning', '10_prompt-injection',
                          '16_bias-and-discrimination'

    Returns:
        DocumentContent: Complete risk document with threat details, impact analysis, and assessment metadata.
        Includes structured content suitable for risk registers and security documentation.

    An id that no document has is an error, not a document: the message
    says to call list_risks() for the valid ids.
    A document that exists and cannot be served is an error too: the
    message says whether it could not be loaded, is too large, or is empty.
    """
    return await _get_document(_RISK, risk_id)


@mcp.tool()
async def get_mitigation(
    mitigation_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=256,
            description=(
                "Mitigation document identifier from list_mitigations(), e.g. "
                "13_providing-citations-and-source-traceability-for-ai-generated-information; "
                "the short form the documents use, mi-13, ct-13 or 13, is "
                "accepted too."
            ),
        ),
    ],
) -> DocumentContent:
    """Get the complete content of a specific AI governance mitigation strategy for risk control implementation.

    Use this tool to retrieve detailed mitigation instructions including security controls,
    implementation steps, monitoring procedures, and effectiveness measures. Critical for
    security implementation, compliance remediation, and risk reduction planning.

    Args:
        mitigation_id: Mitigation document identifier from list_mitigations(),
                       or the short form the documents use: mi-13, ct-13 or 13.
                      Examples: '10_ai-model-version-pinning',
                                '14_encryption-of-ai-data-at-rest'

    Returns:
        DocumentContent: Complete mitigation strategy with implementation guidance, control procedures, and monitoring details.
        Includes actionable steps suitable for security implementation and compliance documentation.

    An id that no document has is an error, not a document: the message
    says to call list_mitigations() for the valid ids.
    A document that exists and cannot be served is an error too: the
    message says whether it could not be loaded, is too large, or is empty.
    """
    return await _get_document(_MITIGATION, mitigation_id)
