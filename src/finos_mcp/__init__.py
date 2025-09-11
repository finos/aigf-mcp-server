"""FINOS AI Governance Framework MCP Server Package

A Model Context Protocol server that provides access to AI governance content from
the FINOS AI Governance Framework repository, specifically exposing risks and mitigations.

This package provides structured access to:
- 17 AI governance mitigation strategies (mi-1 through mi-17)
- 23 AI governance risk assessments (ri-1 through ri-23)

The server implements the MCP protocol for seamless integration with AI assistants
and applications that need access to enterprise-grade AI governance knowledge.
"""

# Dynamic version from setuptools_scm
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"
__author__ = "Hugo Calderon"
__email__ = "hugocalderon@example.com"
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

# Version info tuple for programmatic access
version_info = tuple(int(x) if x.isdigit() else x for x in __version__.split(".") if x)


def get_version() -> str:
    """Return the version string."""
    return __version__


def get_package_info() -> dict[str, str]:
    """Return package information as a dictionary."""
    return {
        "name": "finos_mcp",
        "version": __version__,
        "author": __author__,
        "email": __email__,
        "license": __license__,
        "description": __description__,
    }
