# FINOS AI Governance MCP Server

<!-- Core Project Badges -->
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![MCP SDK](https://img.shields.io/badge/MCP%20SDK-2.x-green)
![Status](https://img.shields.io/badge/status-alpha-orange)

<!-- Quality & CI Badges -->
![GitHub Actions](https://img.shields.io/github/actions/workflow/status/finos/aigf-mcp-server/security-analysis.yml?branch=main&label=CI)

<!-- Tools & Features -->
![MCP Tools](https://img.shields.io/badge/MCP%20tools-9-blue)
![Document Access](https://img.shields.io/badge/document%20access-direct-blue)
![Framework Support](https://img.shields.io/badge/frameworks-13%20supported-green)
![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen)

**AI governance framework document access through the Model Context Protocol.**

The FINOS AI Governance MCP Server gives an MCP client, such as Claude, VS Code
or Cursor, the documents of the
[FINOS AI Governance Framework](https://github.com/finos/ai-governance-framework):
its frameworks, risks and mitigations, read from the framework's repository.

---

## Quick Start

```bash
# Clone the repository into aigf-mcp-server
git clone https://github.com/finos/aigf-mcp-server.git aigf-mcp-server
cd aigf-mcp-server

# Python 3.11 or newer is required. Check what python3 is:
python3 --version
# Below 3.11 (the macOS system python3 is 3.9)? Install a newer Python, for
# example `brew install python@3.12` on macOS or the installer from
# https://www.python.org/downloads/, and type python3.12 where python3 is
# written below. On 3.9 the install stops with an error about a dependency
# or setuptools that does not mention the version.

# Install into a virtual environment: a current Python refuses a pip install
# outside one (externally-managed-environment). On Windows, type
# venv\Scripts\ where venv/bin/ is written.
python3 -m venv venv
venv/bin/pip install .

# Check the install. This prints the installed version.
venv/bin/python -c "import finos_mcp; print(finos_mcp.__version__)"
```

You do not start the server yourself: your MCP client starts
`venv/bin/finos-mcp` when it needs it. The **[Setup Guide](docs/README.md)**
shows the configuration for Claude Desktop, Claude Code, VS Code and Cursor,
and how to give the server a GitHub token, which is strongly recommended.

---

## Available MCP Tools

<!-- tool-table:begin - written by scripts/generate-tool-table.py, do not edit by hand -->

### Framework Access Tools (3)

| Tool | What it does |
|------|--------------|
| `list_frameworks` | List all available AI governance frameworks from the FINOS repository. |
| `get_framework` | Get the complete content of a specific AI governance framework. |
| `search_frameworks` | Find an exact phrase in the text of the AI governance frameworks. |

### Risk & Mitigation Tools (4)

| Tool | What it does |
|------|--------------|
| `list_risks` | List all available AI governance risk documents for threat assessment and security planning. |
| `list_mitigations` | List all available AI governance mitigation strategies for risk reduction and security controls. |
| `get_risk` | Get the complete content of a specific AI governance risk document for detailed threat analysis. |
| `get_mitigation` | Get the complete content of a specific AI governance mitigation strategy for risk control implementation. |

### System Monitoring Tools (2)

| Tool | What it does |
|------|--------------|
| `get_service_health` | Get real service health status by querying each subsystem. |
| `get_cache_stats` | Get cache statistics. |

<!-- tool-table:end -->

A client lists the documents, chooses from their names and descriptions, then
gets the ones it needs. Parameters, responses and errors for each tool, and
that workflow, are in the [MCP Tools Reference](docs/api/mcp-tools.md).

---

## Supported Content

### AI Governance Frameworks
| Framework | Description | Focus Area |
|-----------|-------------|------------|
| NIST AI 600-1 | NIST AI RMF: Generative Artificial Intelligence Profile | Risks particular to generative AI, mapped to the AI RMF |
| EU AI Act | European Union Artificial Intelligence Act | AI regulation and compliance in EU |
| ISO 42001 | AI Management Systems Standard | AI management and governance |
| FFIEC IT Examination Handbook | Federal Financial Institutions Examination Council IT guidance | Financial services IT risk management |
| NIST SP 800-53 | Security and Privacy Controls for Information Systems | Cybersecurity controls and privacy |
| OWASP LLM Top 10 | Top 10 security vulnerabilities for LLM applications | AI/LLM security risks |
| OWASP ML Security Top 10 | Top 10 risks for machine learning systems | ML security and operational risks |
| OWASP Top 10 for Agentic Applications | Top 10 risks for agentic AI applications | Autonomous agent security |
| Agent Threat Rules (ATR) | Threat rules for AI agent systems | Agent threat modelling |
| Canada AI & Financial-Sector Regulatory References | Canadian AI and financial-sector regulatory references | Canadian regulatory compliance |
| UK Financial Services AI Regulations | UK financial services AI regulations | UK regulatory compliance |
| IOSCO Supervisory Toolkit for AI Use in Capital Markets | Securities-regulator supervisory guidance | Market supervision |
| SR 11-7 | US Federal Reserve model risk management guidance | Model risk management |

---

## Risk and Mitigation Types

The framework gives each risk and each mitigation a `type` in the document's
frontmatter. The labels are the framework's own, from its
[site configuration](https://github.com/finos/ai-governance-framework/blob/main/docs/_config.yml);
the counts were taken on 2026-11-05 and change as the framework grows.

| Risk type | Code | Risks |
|-----------|------|-------|
| Operational | `OP` | 11 |
| Security | `SEC` | 10 |
| Regulatory and Compliance | `RC` | 3 |

| Mitigation type | Code | Mitigations |
|-----------------|------|-------------|
| Preventative | `PREV` | 17 |
| Detective | `DET` | 8 |

The documents are the work of the FINOS AI Governance Framework project,
licensed CC BY 4.0; this server does not write them. A risk or mitigation is
served as its Markdown body without the front matter; a framework, which
upstream keeps as YAML, is rendered as a Markdown document.

---

## Documentation

- **[Setup Guide](docs/README.md)**: connect your MCP client
- **[MCP Tools Reference](docs/api/mcp-tools.md)**: the 9 tools and the list, choose, get workflow
- **[Prompts and Resources Reference](docs/tools-reference.md)**: the 3 prompts and the resources, one per document under 3 URI forms
- **[Troubleshooting](docs/troubleshooting.md)**: common problems and their fixes
- **[Deployment Guide](docs/deployment.md)**: every setting, running on HTTP, authentication, health checks, upgrading
- **[API Documentation](docs/api/README.md)**: response schemas, architecture and integration
- **[Development](docs/development.md)**: working on the code and the gates that must pass
- **[Release Process](docs/release-process.md)**: the version scheme and how a release is cut

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution process, and
[Development](docs/development.md) for the development install and the checks
a pull request must pass. Every contributor needs a Contributor License
Agreement on file with FINOS before a pull request can be merged; EasyCLA
checks it on each pull request. Everyone taking part follows the FINOS
[Code of Conduct](https://community.finos.org/docs/governance/code-of-conduct).

---

## Need Help

- [Report an issue](https://github.com/finos/aigf-mcp-server/issues)
- [Troubleshooting](docs/troubleshooting.md)
- Questions about the project: help@finos.org

---

## License

[![Software License](https://img.shields.io/badge/software-Apache%202.0-blue.svg)](LICENSE)
[![Content License](https://img.shields.io/badge/content-CC%20BY%204.0-green.svg)](FINOS-LICENSE.md)

Copyright 2025 FINOS

- **Software**: distributed under the Apache License, Version 2.0
  (SPDX-License-Identifier: Apache-2.0)
- **FINOS Content**: the framework documents the server delivers are licensed
  under CC BY 4.0
