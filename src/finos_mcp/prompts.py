#!/usr/bin/env python3
# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""MCP prompts, which embed fetched framework content and the document catalogs.

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

from typing import Annotated

from pydantic import Field

from .app import mcp
from .documents.tools import get_framework, list_mitigations, list_risks
from .models import DocumentList
from .security.prompt_safety import (
    UNTRUSTED_CONTENT_DIRECTIVE,
    wrap_untrusted,
)

# How much fetched framework content a prompt embeds. Applied before escaping
# so truncation cannot split an escape sequence.
FRAMEWORK_CONTENT_PROMPT_LIMIT = 2000

# How many catalog entries a prompt embeds. Each is bounded already: an id is
# a filename, a title is at most 512 characters and a description at most 500.
# The count is not, so it is bounded here. Four times today's largest catalog.
CATALOG_PROMPT_MAX_DOCUMENTS = 100


def _one_line(value: str) -> str:
    """`value` with every run of whitespace, line breaks included, as one space."""
    return " ".join(value.split())


def _catalog_entries(listing: DocumentList) -> str:
    """Every listed document as an id, a title and its description.

    The whole catalog rather than a search over it (#208): the model reading
    the prompt chooses which documents apply, then fetches them by id. Each
    field is put on one line, so nothing a document says can start a line and
    pass for another entry's `id:`. That includes the id, which is an upstream
    filename and no more trusted than a title. A document that could not be
    read has no description, and gets no description line.

    At most `CATALOG_PROMPT_MAX_DOCUMENTS` entries: the listing is as long as
    the upstream directory, and a prompt must not be. What was left out is
    stated, so the model knows the catalog it was given is partial.
    """
    entries = []
    for document in listing.documents[:CATALOG_PROMPT_MAX_DOCUMENTS]:
        lines = [f"id: {_one_line(document.id)}", f"title: {_one_line(document.name)}"]
        if document.description:
            lines.append(f"description: {_one_line(document.description)}")
        entries.append("\n".join(lines))
    omitted = len(listing.documents) - len(entries)
    if omitted > 0:
        entries.append(
            f"({omitted} more documents are not shown; "
            f"call list_{listing.document_type}s for the full catalog.)"
        )
    return "\n\n".join(entries)


@mcp.prompt()
async def analyze_framework_compliance(
    framework: Annotated[
        str,
        Field(
            min_length=1,
            max_length=128,
            description="Framework identifier (e.g., eu-ai-act).",
        ),
    ],
    use_case: Annotated[
        str,
        Field(min_length=1, max_length=4000, description="AI use case to analyze."),
    ],
) -> str:
    """Analyze compliance requirements for a specific AI use case against a framework.

    Args:
        framework: Framework identifier (e.g., 'eu-ai-act', 'nist-ai-600-1')
        use_case: Description of the AI use case to analyze

    Returns:
        Prompt for analyzing compliance requirements.
    """
    framework_content = await get_framework(framework)

    # Truncate before escaping so the slice cannot cut an escape sequence in half.
    truncated_content = framework_content.content[:FRAMEWORK_CONTENT_PROMPT_LIMIT]

    return f"""You are an AI governance expert. Analyze the AI use case below for compliance with the requested AI governance framework.

{UNTRUSTED_CONTENT_DIRECTIVE}

FRAMEWORK REQUESTED (caller-supplied):
{wrap_untrusted(framework, "user")}

FRAMEWORK CONTENT (fetched from the governance repository, first {FRAMEWORK_CONTENT_PROMPT_LIMIT} characters):
{wrap_untrusted(truncated_content, "external")}

USE CASE TO ANALYZE (caller-supplied):
{wrap_untrusted(use_case, "user")}

Please provide:
1. Key compliance requirements that apply to this use case
2. Potential risks and mitigation strategies
3. Specific sections of the framework that are most relevant
4. Recommended next steps for ensuring compliance

Focus on practical, actionable guidance."""


@mcp.prompt()
async def risk_assessment_analysis(
    risk_category: Annotated[
        str,
        Field(min_length=1, max_length=128, description="Risk category to assess."),
    ],
    context: Annotated[
        str,
        Field(
            min_length=1,
            max_length=4000,
            description="Scenario context for risk assessment.",
        ),
    ],
) -> str:
    """Generate a risk assessment prompt for a specific AI risk category.

    Args:
        risk_category: Type of risk to assess (e.g., 'bias', 'privacy', 'security')
        context: Context or scenario for the risk assessment

    Returns:
        Prompt for conducting risk assessment.
    """
    catalog = _catalog_entries(await list_risks())

    risk_documentation = (
        f"""RISK CATALOG (every risk document in the governance repository):
{wrap_untrusted(catalog, "external")}

Before assessing, choose the catalog entries that bear on the risk category and scenario, and call get_risk with the id of each to read the full document. Base the assessment on what those documents say, and name the ones you used. If no entry applies, say so."""
        if catalog
        else "The risk catalog could not be loaded, so no risk documentation is available."
    )

    return f"""You are an AI risk assessment specialist. Conduct a thorough risk assessment for the scenario below.

{UNTRUSTED_CONTENT_DIRECTIVE}

RISK CATEGORY (caller-supplied):
{wrap_untrusted(risk_category, "user")}

SCENARIO (caller-supplied):
{wrap_untrusted(context, "user")}

{risk_documentation}

Please provide:
1. Likelihood assessment (High/Medium/Low) with justification
2. Impact assessment (High/Medium/Low) with potential consequences
3. Specific risk factors present in this scenario
4. Recommended mitigation strategies
5. Monitoring and detection approaches

Be specific and actionable in your recommendations."""


@mcp.prompt()
async def mitigation_strategy_prompt(
    risk_type: Annotated[
        str, Field(min_length=1, max_length=128, description="Risk type to mitigate.")
    ],
    system_description: Annotated[
        str,
        Field(
            min_length=1, max_length=4000, description="Description of the AI system."
        ),
    ],
) -> str:
    """Generate a mitigation strategy prompt for a specific risk in an AI system.

    Args:
        risk_type: Type of risk to mitigate
        system_description: Description of the AI system

    Returns:
        Prompt for developing mitigation strategies.
    """
    catalog = _catalog_entries(await list_mitigations())

    mitigation_documentation = (
        f"""MITIGATION CATALOG (every mitigation document in the governance repository):
{wrap_untrusted(catalog, "external")}

Before planning, choose the catalog entries that address the risk type in this system, and call get_mitigation with the id of each to read the full document. Base the plan on what those documents say, and name the ones you used. If no entry applies, say so."""
        if catalog
        else "The mitigation catalog could not be loaded, so no mitigation documentation is available."
    )

    return f"""You are an AI safety engineer tasked with developing mitigation strategies.

{UNTRUSTED_CONTENT_DIRECTIVE}

RISK TYPE (caller-supplied):
{wrap_untrusted(risk_type, "user")}

AI SYSTEM (caller-supplied):
{wrap_untrusted(system_description, "user")}

{mitigation_documentation}

Please develop a comprehensive mitigation plan that includes:
1. Preventive measures to reduce risk likelihood
2. Detective controls to identify when risks occur
3. Corrective actions to respond to incidents
4. Technical implementation details
5. Monitoring and validation approaches
6. Timeline and resource requirements

Prioritize practical, implementable solutions."""
