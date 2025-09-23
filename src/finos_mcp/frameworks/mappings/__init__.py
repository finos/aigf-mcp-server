"""
Framework cross-reference mappings package.

Provides manual correlation and equivalency mapping between governance frameworks
for cross-framework navigation and compliance analysis.
"""

from .cross_reference import CrossFrameworkMapper, FrameworkMapping
from .framework_correlations import FrameworkCorrelations, get_framework_correlations

__all__ = [
    "CrossFrameworkMapper",
    "FrameworkCorrelations",
    "FrameworkMapping",
    "get_framework_correlations",
]
