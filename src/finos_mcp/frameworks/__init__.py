"""
FINOS Framework Integration Module

This module provides governance framework integration capabilities for the FINOS MCP Server.
Supports multiple governance frameworks including NIST AI RMF, EU AI Act, OWASP LLM Top 10, etc.

Architecture:
- models.py: Unified Pydantic data models for all frameworks
- data_loader.py: Framework data loading and validation
- query_engine.py: Cross-framework search and analysis
- validator.py: Framework data integrity validation
"""

from .models import (
    ComplianceMapping,
    FrameworkQuery,
    FrameworkReference,
    FrameworkSearchResult,
    FrameworkSection,
    GovernanceFramework,
)

__all__ = [
    "ComplianceMapping",
    "FrameworkQuery",
    "FrameworkReference",
    "FrameworkSearchResult",
    "FrameworkSection",
    "GovernanceFramework",
]
