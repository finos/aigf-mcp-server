# Prompts and Resources Reference

The server's 3 prompts and its resources, one per document under 3 URI forms.
The 9 tools are documented one by one
in the [MCP Tools Reference](api/mcp-tools.md).

## MCP Prompts (3)

**Prompt injection boundaries**: every span a prompt does not author itself is enclosed in a
labelled block — `<untrusted_user_input>` for caller arguments, `<untrusted_external_content>` for
content fetched from the governance repository — below a standing directive that such content is
data to be analyzed and never instruction. Delimiter characters in the enclosed text are escaped,
so no argument or upstream document can terminate its own block.

### `analyze_framework_compliance`
**Purpose**: Analyze compliance requirements across AI governance frameworks
**Usage**: Available as MCP prompt template for compliance analysis
**Parameters**: `framework` (a framework identifier such as `eu-ai-act`) and `use_case` (the AI use case to analyze)
**Returns**: Prompt text asking for the requirements that apply, the risks and mitigations, the most relevant sections of the framework and next steps

### `risk_assessment_analysis`
**Purpose**: Conduct comprehensive AI risk assessment using FINOS methodology
**Usage**: Available as MCP prompt template for risk evaluation
**Parameters**: `risk_category` (the risk category to assess) and `context` (the scenario)
**Returns**: Prompt text asking for likelihood and impact (High/Medium/Low), the risk factors present, mitigations and monitoring

### `mitigation_strategy_prompt`
**Purpose**: Develop comprehensive mitigation strategies for identified AI risks
**Usage**: Available as MCP prompt template for mitigation planning
**Parameters**: `risk_type` (the risk to mitigate) and `system_description` (the AI system)
**Returns**: Prompt text asking for a mitigation plan: preventive, detective and corrective measures, implementation details, monitoring, and timeline and resources

---

## MCP Resources

`resources/list` names every document in the catalog: one resource per
framework, risk and mitigation, served as `text/markdown`. A risk or mitigation
is named by its filename stem, such as `ri-10_prompt-injection`, and a
framework by its title, such as `EU AI Act`. Each has its template's
description, such as "Risk documentation
from FINOS AI governance corpus.": the list is built from the discovery
listing alone and reads no document, so a client's connect does not wait on
one fetch per document. The list tools give each document's own title and
description. The three URI forms below are also published as
resource templates, so a client that knows an id can build the URI without
listing. A read is served by the same code as the matching `get_*` tool. A
listing that cannot be built is answered as an empty list with one WARNING in
the server log; the templates stay, and the list tools report the failure in
their own words.

### `finos://frameworks/{id}`
**Purpose**: URI-based access to framework content
**Usage**: Direct resource access via MCP resource protocol
**Examples**:
- `finos://frameworks/nist-ai-600-1`
- `finos://frameworks/eu-ai-act`
- `finos://frameworks/iso-42001`

### `finos://risks/{id}`
**Purpose**: URI-based access to risk documents
**Usage**: Direct resource access via MCP resource protocol
**Examples**:
- `finos://risks/10_prompt-injection`
- `finos://risks/9_data-poisoning`

### `finos://mitigations/{id}`
**Purpose**: URI-based access to mitigation documents
**Usage**: Direct resource access via MCP resource protocol
**Examples**:
- `finos://mitigations/1_ai-data-leakage-prevention-and-detection`
- `finos://mitigations/10_ai-model-version-pinning`

---

## Tool Output Format

All tools return structured Pydantic models with type safety and validation. This follows the MCP 2025-06-18 specification for consistent tool integration and structured output.

## Error Handling

A tool that fails returns a result with `isError: true` and one text block
that says what happened:
- An id no document has: the text names the listing tool that holds the valid ids
- A document that could not be loaded, is too large or is empty: the text says which
- A GitHub rate limit: the text says the throttle is temporary

When GitHub cannot be reached, the listing tools answer from the list file the
server last wrote (`expired_cache`), or from the built-in catalog when there is
none (`static_fallback`), and say which in `source`. [Response Schemas](api/response-schemas.md#error-response-examples)
shows each result as a client receives it.

---

For integration examples, see the [Integration Guide](api/integration-guide.md).
