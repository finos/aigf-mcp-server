"""
Framework correlations and equivalency system.

Provides comprehensive correlation analysis between governance frameworks
for compliance navigation and gap analysis.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..models import FrameworkType
from .cross_reference import CrossFrameworkMapper


class CorrelationType(Enum):
    """Type of correlation between frameworks."""

    DIRECT = "direct"  # Direct control-to-control mapping
    THEMATIC = "thematic"  # Similar themes or topics
    PROCEDURAL = "procedural"  # Similar procedures or processes
    OUTCOME = "outcome"  # Similar desired outcomes


@dataclass
class FrameworkCorrelation:
    """Correlation between framework areas."""

    framework1: FrameworkType
    framework2: FrameworkType
    topic: str
    correlation_type: CorrelationType
    strength: float  # 0.0 to 1.0
    description: str
    related_controls: list[str]


class FrameworkCorrelations:
    """
    Framework correlation and equivalency analysis system.

    Provides static correlation analysis between governance frameworks
    without AI - uses manual correlation tables and mapping analysis.
    """

    def __init__(self):
        self._mapper = CrossFrameworkMapper()
        self._correlations: list[FrameworkCorrelation] = []
        self._initialize_correlations()

    def _initialize_correlations(self) -> None:
        """Initialize framework correlation data."""
        # NIST AI RMF to EU AI Act correlations
        self._correlations.extend(
            [
                FrameworkCorrelation(
                    framework1=FrameworkType.NIST_AI_RMF,
                    framework2=FrameworkType.EU_AI_ACT,
                    topic="Risk Management",
                    correlation_type=CorrelationType.DIRECT,
                    strength=0.85,
                    description="Both frameworks require comprehensive risk management systems",
                    related_controls=["ai-rmf-1.1", "art-9-risk-management"],
                ),
                FrameworkCorrelation(
                    framework1=FrameworkType.NIST_AI_RMF,
                    framework2=FrameworkType.EU_AI_ACT,
                    topic="Data Governance",
                    correlation_type=CorrelationType.DIRECT,
                    strength=0.80,
                    description="Data quality and governance requirements overlap",
                    related_controls=["ai-rmf-2.1", "art-10-data-governance"],
                ),
                FrameworkCorrelation(
                    framework1=FrameworkType.NIST_AI_RMF,
                    framework2=FrameworkType.EU_AI_ACT,
                    topic="Transparency",
                    correlation_type=CorrelationType.THEMATIC,
                    strength=0.70,
                    description="Both address transparency but with different emphasis",
                    related_controls=["ai-rmf-3.1", "art-13-transparency"],
                ),
            ]
        )

        # NIST AI RMF to OWASP LLM correlations
        self._correlations.extend(
            [
                FrameworkCorrelation(
                    framework1=FrameworkType.NIST_AI_RMF,
                    framework2=FrameworkType.OWASP_LLM,
                    topic="Input Security",
                    correlation_type=CorrelationType.PROCEDURAL,
                    strength=0.75,
                    description="Input validation and security measures",
                    related_controls=["ai-rmf-2.2", "llm01-prompt-injection"],
                ),
                FrameworkCorrelation(
                    framework1=FrameworkType.NIST_AI_RMF,
                    framework2=FrameworkType.OWASP_LLM,
                    topic="Output Security",
                    correlation_type=CorrelationType.DIRECT,
                    strength=0.80,
                    description="Secure handling of AI system outputs",
                    related_controls=["ai-rmf-1.2", "llm02-insecure-output-handling"],
                ),
            ]
        )

        # EU AI Act to OWASP LLM correlations
        self._correlations.extend(
            [
                FrameworkCorrelation(
                    framework1=FrameworkType.EU_AI_ACT,
                    framework2=FrameworkType.OWASP_LLM,
                    topic="System Reliability",
                    correlation_type=CorrelationType.OUTCOME,
                    strength=0.65,
                    description="Ensuring system reliability and preventing overreliance",
                    related_controls=[
                        "art-15-accuracy-monitoring",
                        "llm09-overreliance",
                    ],
                ),
                FrameworkCorrelation(
                    framework1=FrameworkType.EU_AI_ACT,
                    framework2=FrameworkType.OWASP_LLM,
                    topic="Data Integrity",
                    correlation_type=CorrelationType.DIRECT,
                    strength=0.85,
                    description="Data quality and integrity requirements",
                    related_controls=[
                        "art-10-data-governance",
                        "llm03-training-data-poisoning",
                    ],
                ),
            ]
        )

    def get_framework_correlations(
        self,
        framework1: FrameworkType,
        framework2: FrameworkType | None = None,
        min_strength: float = 0.5,
    ) -> list[FrameworkCorrelation]:
        """
        Get correlations between frameworks.

        Args:
            framework1: Primary framework
            framework2: Optional second framework (if None, get all correlations)
            min_strength: Minimum correlation strength (0.0-1.0)

        Returns:
            List of framework correlations
        """
        result = []
        for correlation in self._correlations:
            # Check if correlation involves the specified framework(s)
            involves_framework1 = (
                correlation.framework1 == framework1
                or correlation.framework2 == framework1
            )

            if framework2 is None:
                # Return all correlations involving framework1
                if involves_framework1 and correlation.strength >= min_strength:
                    result.append(correlation)
            else:
                # Return correlations between specific frameworks
                involves_framework2 = (
                    correlation.framework1 == framework2
                    or correlation.framework2 == framework2
                )
                if (
                    involves_framework1
                    and involves_framework2
                    and correlation.strength >= min_strength
                ):
                    result.append(correlation)

        return result

    def get_related_frameworks(
        self, framework: FrameworkType, min_strength: float = 0.5
    ) -> dict[FrameworkType, list[FrameworkCorrelation]]:
        """
        Get all frameworks related to the specified framework.

        Args:
            framework: Source framework
            min_strength: Minimum correlation strength

        Returns:
            Dictionary mapping related frameworks to their correlations
        """
        result: dict[FrameworkType, list[FrameworkCorrelation]] = {}

        for correlation in self._correlations:
            if correlation.strength < min_strength:
                continue

            related_framework = None
            if correlation.framework1 == framework:
                related_framework = correlation.framework2
            elif correlation.framework2 == framework:
                related_framework = correlation.framework1

            if related_framework:
                if related_framework not in result:
                    result[related_framework] = []
                result[related_framework].append(correlation)

        return result

    def get_correlation_summary(
        self, framework1: FrameworkType, framework2: FrameworkType
    ) -> dict[str, Any]:
        """
        Get a summary of correlations between two frameworks.

        Args:
            framework1: First framework
            framework2: Second framework

        Returns:
            Correlation summary with statistics and details
        """
        correlations = self.get_framework_correlations(framework1, framework2)
        mappings = self._mapper.get_framework_overlaps(framework1, framework2)

        if not correlations:
            return {
                "frameworks": [framework1.value, framework2.value],
                "correlation_exists": False,
                "summary": "No correlations found between these frameworks",
            }

        # Calculate statistics
        avg_strength = sum(c.strength for c in correlations) / len(correlations)
        correlation_types = list({c.correlation_type.value for c in correlations})
        topics = [c.topic for c in correlations]

        return {
            "frameworks": [framework1.value, framework2.value],
            "correlation_exists": True,
            "total_correlations": len(correlations),
            "total_mappings": len(mappings),
            "average_strength": round(avg_strength, 2),
            "correlation_types": correlation_types,
            "topics": topics,
            "strongest_correlation": max(correlations, key=lambda c: c.strength).topic,
            "summary": f"Found {len(correlations)} correlations with average strength {avg_strength:.1f}",
        }

    def find_compliance_gaps(
        self,
        source_framework: FrameworkType,
        target_frameworks: list[FrameworkType],
        min_coverage: float = 0.7,
    ) -> dict[str, Any]:
        """
        Identify potential compliance gaps when mapping between frameworks.

        Args:
            source_framework: Framework being mapped from
            target_frameworks: Frameworks being mapped to
            min_coverage: Minimum correlation strength for adequate coverage

        Returns:
            Gap analysis results
        """
        gaps = []
        coverage_summary = {}

        for target_framework in target_frameworks:
            correlations = self.get_framework_correlations(
                source_framework, target_framework
            )
            strong_correlations = [
                c for c in correlations if c.strength >= min_coverage
            ]

            coverage_ratio = (
                len(strong_correlations) / len(correlations) if correlations else 0
            )
            coverage_summary[target_framework.value] = {
                "total_correlations": len(correlations),
                "strong_correlations": len(strong_correlations),
                "coverage_ratio": round(coverage_ratio, 2),
            }

            # Identify potential gaps
            weak_correlations = [c for c in correlations if c.strength < min_coverage]
            for correlation in weak_correlations:
                gaps.append(
                    {
                        "target_framework": target_framework.value,
                        "topic": correlation.topic,
                        "strength": correlation.strength,
                        "gap_severity": "high"
                        if correlation.strength < 0.5
                        else "medium",
                        "description": correlation.description,
                    }
                )

        return {
            "source_framework": source_framework.value,
            "target_frameworks": [f.value for f in target_frameworks],
            "coverage_summary": coverage_summary,
            "potential_gaps": gaps,
            "overall_coverage": sum(
                info["coverage_ratio"] for info in coverage_summary.values()
            )
            / len(coverage_summary)
            if coverage_summary
            else 0,
        }

    def get_supported_frameworks(self) -> set[FrameworkType]:
        """Get all frameworks with correlation data."""
        frameworks = set()
        for correlation in self._correlations:
            frameworks.add(correlation.framework1)
            frameworks.add(correlation.framework2)
        return frameworks


# Global instance
_framework_correlations: FrameworkCorrelations | None = None


def get_framework_correlations() -> FrameworkCorrelations:
    """Get the global framework correlations instance."""
    global _framework_correlations
    if _framework_correlations is None:
        _framework_correlations = FrameworkCorrelations()
    return _framework_correlations
