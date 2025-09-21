"""
Cross-framework reference mapping implementation.

Provides static mapping tables and correlation lookups between governance frameworks
following existing project patterns for reference navigation.
"""

from dataclasses import dataclass
from enum import Enum

from ..models import FrameworkType


class MappingStrength(Enum):
    """Strength of mapping between framework controls."""

    EXACT = "exact"  # Direct equivalent control
    STRONG = "strong"  # Very similar control with minor differences
    PARTIAL = "partial"  # Related but not directly equivalent
    WEAK = "weak"  # Loosely related or conceptual similarity


@dataclass
class FrameworkMapping:
    """Mapping between framework controls."""

    source_framework: FrameworkType
    source_control_id: str
    target_framework: FrameworkType
    target_control_id: str
    mapping_strength: MappingStrength
    description: str
    notes: str | None = None


class CrossFrameworkMapper:
    """
    Static cross-framework mapping system.

    Provides manual correlation between framework controls without AI or
    automated analysis - uses predefined mapping tables.
    """

    def __init__(self):
        self._mappings: dict[str, list[FrameworkMapping]] = {}
        self._reverse_mappings: dict[str, list[FrameworkMapping]] = {}
        self._initialize_mappings()

    def _initialize_mappings(self) -> None:
        """Initialize static mapping tables."""
        # NIST AI RMF to EU AI Act mappings
        nist_to_eu_mappings = [
            FrameworkMapping(
                source_framework=FrameworkType.NIST_AI_RMF,
                source_control_id="ai-rmf-1.1",
                target_framework=FrameworkType.EU_AI_ACT,
                target_control_id="art-9-risk-management",
                mapping_strength=MappingStrength.STRONG,
                description="Risk management system requirements",
                notes="Both frameworks require comprehensive risk management systems",
            ),
            FrameworkMapping(
                source_framework=FrameworkType.NIST_AI_RMF,
                source_control_id="ai-rmf-2.1",
                target_framework=FrameworkType.EU_AI_ACT,
                target_control_id="art-10-data-governance",
                mapping_strength=MappingStrength.STRONG,
                description="Data governance and quality requirements",
                notes="Data quality and governance overlap significantly",
            ),
            FrameworkMapping(
                source_framework=FrameworkType.NIST_AI_RMF,
                source_control_id="ai-rmf-3.1",
                target_framework=FrameworkType.EU_AI_ACT,
                target_control_id="art-13-transparency",
                mapping_strength=MappingStrength.PARTIAL,
                description="Transparency and explainability requirements",
                notes="NIST focuses on technical explainability, EU on user transparency",
            ),
        ]

        # NIST AI RMF to OWASP LLM mappings
        nist_to_owasp_mappings = [
            FrameworkMapping(
                source_framework=FrameworkType.NIST_AI_RMF,
                source_control_id="ai-rmf-2.2",
                target_framework=FrameworkType.OWASP_LLM,
                target_control_id="llm01-prompt-injection",
                mapping_strength=MappingStrength.PARTIAL,
                description="Input validation and security",
                notes="NIST input validation relates to OWASP prompt injection prevention",
            ),
            FrameworkMapping(
                source_framework=FrameworkType.NIST_AI_RMF,
                source_control_id="ai-rmf-1.2",
                target_framework=FrameworkType.OWASP_LLM,
                target_control_id="llm02-insecure-output-handling",
                mapping_strength=MappingStrength.STRONG,
                description="Output security and validation",
                notes="Both address secure handling of AI system outputs",
            ),
        ]

        # EU AI Act to OWASP LLM mappings
        eu_to_owasp_mappings = [
            FrameworkMapping(
                source_framework=FrameworkType.EU_AI_ACT,
                source_control_id="art-15-accuracy-monitoring",
                target_framework=FrameworkType.OWASP_LLM,
                target_control_id="llm09-overreliance",
                mapping_strength=MappingStrength.PARTIAL,
                description="System reliability and user awareness",
                notes="EU monitoring requirements relate to OWASP overreliance prevention",
            ),
            FrameworkMapping(
                source_framework=FrameworkType.EU_AI_ACT,
                source_control_id="art-10-data-governance",
                target_framework=FrameworkType.OWASP_LLM,
                target_control_id="llm03-training-data-poisoning",
                mapping_strength=MappingStrength.STRONG,
                description="Data integrity and validation requirements",
                notes="Both frameworks address data quality and security",
            ),
        ]

        # Add all mappings to the mapper
        all_mappings = (
            nist_to_eu_mappings + nist_to_owasp_mappings + eu_to_owasp_mappings
        )

        for mapping in all_mappings:
            # Forward mapping
            source_key = f"{mapping.source_framework.value}:{mapping.source_control_id}"
            if source_key not in self._mappings:
                self._mappings[source_key] = []
            self._mappings[source_key].append(mapping)

            # Reverse mapping for bidirectional lookup
            target_key = f"{mapping.target_framework.value}:{mapping.target_control_id}"
            reverse_mapping = FrameworkMapping(
                source_framework=mapping.target_framework,
                source_control_id=mapping.target_control_id,
                target_framework=mapping.source_framework,
                target_control_id=mapping.source_control_id,
                mapping_strength=mapping.mapping_strength,
                description=f"Reverse: {mapping.description}",
                notes=mapping.notes,
            )
            if target_key not in self._reverse_mappings:
                self._reverse_mappings[target_key] = []
            self._reverse_mappings[target_key].append(reverse_mapping)

    def get_related_controls(
        self,
        framework: FrameworkType,
        control_id: str,
        min_strength: MappingStrength = MappingStrength.WEAK,
    ) -> list[FrameworkMapping]:
        """
        Get related controls in other frameworks.

        Args:
            framework: Source framework
            control_id: Source control ID
            min_strength: Minimum mapping strength to include

        Returns:
            List of related controls from other frameworks
        """
        key = f"{framework.value}:{control_id}"
        mappings = self._mappings.get(key, [])

        # Filter by minimum strength
        strength_order = [
            MappingStrength.EXACT,
            MappingStrength.STRONG,
            MappingStrength.PARTIAL,
            MappingStrength.WEAK,
        ]
        min_index = strength_order.index(min_strength)

        return [
            mapping
            for mapping in mappings
            if strength_order.index(mapping.mapping_strength) <= min_index
        ]

    def get_framework_overlaps(
        self, framework1: FrameworkType, framework2: FrameworkType
    ) -> list[FrameworkMapping]:
        """
        Get all mappings between two specific frameworks.

        Args:
            framework1: First framework
            framework2: Second framework

        Returns:
            List of mappings between the frameworks
        """
        result = []

        # Check all mappings for matches
        for mappings in self._mappings.values():
            for mapping in mappings:
                if (
                    mapping.source_framework == framework1
                    and mapping.target_framework == framework2
                ) or (
                    mapping.source_framework == framework2
                    and mapping.target_framework == framework1
                ):
                    result.append(mapping)

        return result

    def get_supported_frameworks(self) -> set[FrameworkType]:
        """Get all frameworks that have mappings."""
        frameworks = set()
        for mappings in self._mappings.values():
            for mapping in mappings:
                frameworks.add(mapping.source_framework)
                frameworks.add(mapping.target_framework)
        return frameworks

    def get_mapping_statistics(self) -> dict[str, int]:
        """Get statistics about available mappings."""
        total_mappings = sum(len(mappings) for mappings in self._mappings.values())
        frameworks = self.get_supported_frameworks()

        # Count by strength
        strength_counts = {strength.value: 0 for strength in MappingStrength}
        for mappings in self._mappings.values():
            for mapping in mappings:
                strength_counts[mapping.mapping_strength.value] += 1

        return {
            "total_mappings": total_mappings,
            "supported_frameworks": len(frameworks),
            "mapping_strengths": strength_counts,
        }
