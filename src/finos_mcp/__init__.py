# Copyright 2025 FINOS
# SPDX-License-Identifier: Apache-2.0

"""FINOS AI Governance Framework MCP Server Package

A Model Context Protocol server that provides access to AI governance content from
the FINOS AI Governance Framework repository: its risk and mitigation documents
and the frameworks it indexes, listed from the repository on each call so the
counts follow the repository and are not stated here.

The server implements the MCP protocol for seamless integration with AI assistants
and applications that need access to enterprise-grade AI governance knowledge.
"""

# Dynamic version from setuptools_scm
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"
__author__ = "FINOS"
__email__ = "info@finos.org"
__license__ = "Apache-2.0"
__description__ = "Model Context Protocol server for FINOS AI Governance Framework"

# Package metadata for introspection
__all__ = [
    "__author__",
    "__description__",
    "__email__",
    "__license__",
    "__version__",
]
