#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""Structured output models. FastMCP derives each tool's ``outputSchema`` from these.

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

from typing import Literal

from pydantic import BaseModel, Field

#: Where a listing came from (#333). ``github_api`` for a listing just made,
#: ``cache`` for the list file while fresh, ``expired_cache`` for the list file
#: past its time when GitHub cannot be asked, ``static_fallback`` for the
#: catalog built into the server. One ``Literal`` on every model that carries
#: it, so the published schema holds the four values as an enum and a fifth
#: cannot ship unnoticed.
ListingSource = Literal["github_api", "cache", "expired_cache", "static_fallback"]


# Structured output models
class Framework(BaseModel):
    """Framework information."""

    id: str
    name: str
    #: The framework file's own ``description``, or ``None`` when the file could
    #: not be read or declares none. Never generated from the name (#191).
    description: str | None = None


class FrameworkList(BaseModel):
    """List of available frameworks."""

    frameworks: list[Framework]
    total_count: int
    # The same provenance DocumentList reports. Without it, list_frameworks
    # answered source=None and a caller could not tell a live catalog from the
    # shipped static one -- the question that matters most when the answer feeds
    # a compliance decision, and the one that makes a rate-limited server
    # indistinguishable from a healthy one. No default: a list built without
    # one claimed a live listing (#333).
    source: ListingSource


class FrameworkContent(BaseModel):
    """Framework content with metadata."""

    framework_id: str
    #: The framework's own declared name. Added in #118: this model had no
    #: title at all, so a client had only the id to show. Sourced from the
    #: document's top-level YAML ``title``, falling back to the name map in
    #: ``_format_framework_name`` when a document declares none.
    #:
    #: That map used to contradict the corpus for 10 of the 13 frameworks and
    #: was realigned in the same change, so the fallback is correct today -- but
    #: it is a hardcoded copy and will drift again. #121 tracks sourcing it from
    #: the documents; the live gate catches the drift meanwhile.
    title: str
    content: str
    #: The number of entries the body lists. Named for what it counts: it was
    #: ``sections``, the name ``DocumentContent`` gives its list of section
    #: titles, so one field name carried two types across sibling tools (#339).
    entry_count: int


class SearchResult(BaseModel):
    """Search result item."""

    # The id list_frameworks reports and get_framework accepts, so a search
    # result feeds straight back into get_framework.
    document_id: str
    section: str
    #: The passage around the first place the framework says the phrase.
    content: str
    #: How many times the framework says the phrase, as whole words and
    #: outside link targets. A count, not a score: results are not ordered
    #: by it (#208).
    occurrences: int = Field(ge=1)


class SearchResults(BaseModel):
    """Search results collection."""

    query: str
    #: In catalog order, the order ``list_frameworks`` gives.
    results: list[SearchResult]
    #: Every framework that says the phrase, including those ``limit`` cut.
    total_found: int


class DocumentInfo(BaseModel):
    """Document information."""

    id: str
    name: str
    filename: str
    #: The first paragraph of the document's opening Summary or Purpose section,
    #: or ``None`` when the document could not be read or does not open with
    #: one. Never generated from the name (#191).
    description: str | None = None


class DocumentList(BaseModel):
    """List of documents."""

    documents: list[DocumentInfo]
    total_count: int
    document_type: str
    source: ListingSource


class DocumentContent(BaseModel):
    """Document content with metadata."""

    #: The id as the list tool publishes it, whatever form the caller used:
    #: ``ri-10`` and ``10`` both give ``10_prompt-injection``. A document that cannot be
    #: served is raised, not returned (#193, #216), so no record carries a
    #: rejected id; in the raised message the caller's id passes through
    #: ``safe_title_fragment`` first, since that message is what a client
    #: renders.
    document_id: str
    title: str
    content: str
    sections: list[str]


class ServiceHealth(BaseModel):
    """Service health status."""

    status: str
    uptime_seconds: float
    version: str
    healthy_services: int
    total_services: int


class CacheStats(BaseModel):
    """Cache statistics."""

    total_requests: int
    cache_hits: int
    cache_misses: int
    hit_rate: float
