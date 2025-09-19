"""
Framework Data Loader

Loads and validates governance framework data from YAML files.
Supports dynamic framework discovery and data validation.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import yaml

from .models import (
    ComplianceStatus,
    FrameworkReference,
    FrameworkSection,
    FrameworkType,
    GovernanceFramework,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class FrameworkDataLoader:
    """Loads and validates framework data from external sources."""

    def __init__(self, base_url: str = "https://raw.githubusercontent.com/finos/ai-governance-framework/main/"):
        """Initialize framework data loader.

        Args:
            base_url: Base URL for framework data repository
        """
        self.base_url = base_url.rstrip("/") + "/"
        self.loaded_frameworks: dict[FrameworkType, GovernanceFramework] = {}
        self.framework_files = {
            FrameworkType.NIST_AI_RMF: "nist-ai-600-1.yml",
            FrameworkType.EU_AI_ACT: "eu-ai-act.yml",
            FrameworkType.OWASP_LLM: "owasp-llm.yml",
            FrameworkType.ISO_27001: "iso-27001.yml",
            FrameworkType.GDPR: "gdpr.yml",
            FrameworkType.CCPA: "ccpa.yml",
            FrameworkType.SOC2: "soc2.yml",
        }
        self.cache_dir = Path(".framework_cache")
        self.cache_dir.mkdir(exist_ok=True)

    async def load_all_frameworks(self) -> dict[FrameworkType, GovernanceFramework]:
        """Load all supported frameworks.

        Returns:
            Dictionary mapping framework types to framework data
        """
        logger.info("Loading all governance frameworks...")

        # Load frameworks concurrently
        tasks = []
        for framework_type in FrameworkType:
            tasks.append(self.load_framework(framework_type))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        loaded_count = 0
        for framework_type, result in zip(FrameworkType, results, strict=False):
            if isinstance(result, Exception):
                logger.error(f"Failed to load framework {framework_type}: {result}")
            else:
                self.loaded_frameworks[framework_type] = result
                loaded_count += 1

        logger.info(f"Successfully loaded {loaded_count}/{len(FrameworkType)} frameworks")
        return self.loaded_frameworks

    async def load_framework(self, framework_type: FrameworkType) -> GovernanceFramework:
        """Load a specific framework.

        Args:
            framework_type: Framework to load

        Returns:
            Loaded framework data
        """
        logger.info(f"Loading framework: {framework_type}")

        try:
            # Get framework file path
            filename = self.framework_files.get(framework_type)
            if not filename:
                raise ValueError(f"No file mapping for framework: {framework_type}")

            # Load framework data
            raw_data = await self._fetch_framework_data(filename)

            # Parse and validate framework
            framework = self._parse_framework_data(framework_type, raw_data)

            logger.info(f"Loaded framework {framework_type}: {len(framework.references)} references, {len(framework.sections)} sections")
            return framework

        except Exception as e:
            logger.error(f"Failed to load framework {framework_type}: {e}")
            raise

    async def _fetch_framework_data(self, filename: str) -> dict[str, Any]:
        """Fetch framework data from remote source or cache.

        Args:
            filename: Framework filename

        Returns:
            Raw framework data
        """
        cache_file = self.cache_dir / filename

        # Try to load from cache first
        if cache_file.exists():
            try:
                with open(cache_file, encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                logger.debug(f"Loaded framework data from cache: {filename}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load cached data for {filename}: {e}")

        # Fetch from remote source
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = urljoin(self.base_url, filename)
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        data = yaml.safe_load(content)

                        # Cache the data
                        try:
                            with open(cache_file, 'w', encoding='utf-8') as f:
                                yaml.dump(data, f, default_flow_style=False)
                            logger.debug(f"Cached framework data: {filename}")
                        except Exception as e:
                            logger.warning(f"Failed to cache data for {filename}: {e}")

                        return data
                    else:
                        raise ValueError(f"HTTP {response.status} for {url}")

        except ImportError:
            # Fallback to synchronous requests if aiohttp not available
            import requests
            url = urljoin(self.base_url, filename)
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = yaml.safe_load(response.content)

            # Cache the data
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False)
            except Exception as e:
                logger.warning(f"Failed to cache data for {filename}: {e}")

            return data

    def _parse_framework_data(self, framework_type: FrameworkType, raw_data: dict[str, Any]) -> GovernanceFramework:
        """Parse raw framework data into structured models.

        Args:
            framework_type: Framework type
            raw_data: Raw YAML data

        Returns:
            Parsed framework
        """
        try:
            # Extract framework metadata
            metadata = raw_data.get("framework", {})

            framework = GovernanceFramework(
                framework_type=framework_type,
                name=metadata.get("name", framework_type.value),
                version=metadata.get("version", "1.0"),
                description=metadata.get("description", ""),
                publisher=metadata.get("publisher", ""),
                publication_date=self._parse_date(metadata.get("publication_date")),
                effective_date=self._parse_date(metadata.get("effective_date")),
                official_url=metadata.get("official_url"),
                documentation_url=metadata.get("documentation_url"),
            )

            # Parse sections
            sections_data = raw_data.get("sections", {})
            framework.sections = self._parse_sections(framework_type, sections_data)

            # Parse references
            references_data = raw_data.get("references", {})
            framework.references = self._parse_references(framework_type, references_data, framework.sections)

            # Update statistics
            framework.total_references = len(framework.references)
            framework.active_references = len([ref for ref in framework.references if ref.compliance_status != ComplianceStatus.NOT_APPLICABLE])

            # Link references to sections
            self._link_references_to_sections(framework)

            return framework

        except Exception as e:
            logger.error(f"Failed to parse framework data for {framework_type}: {e}")
            raise

    def _parse_sections(self, framework_type: FrameworkType, sections_data: dict[str, Any]) -> list[FrameworkSection]:
        """Parse framework sections.

        Args:
            framework_type: Framework type
            sections_data: Raw sections data

        Returns:
            List of parsed sections
        """
        sections = []

        for section_id, section_info in sections_data.items():
            if isinstance(section_info, str):
                # Simple section with just title
                section = FrameworkSection(
                    framework_type=framework_type,
                    section_id=section_id,
                    title=section_info,
                    order=len(sections)
                )
            elif isinstance(section_info, dict):
                # Complex section with metadata
                section = FrameworkSection(
                    framework_type=framework_type,
                    section_id=section_id,
                    title=section_info.get("title", section_id),
                    description=section_info.get("description"),
                    parent_section=section_info.get("parent"),
                    order=section_info.get("order", len(sections)),
                    is_active=section_info.get("active", True)
                )
            else:
                logger.warning(f"Invalid section format for {section_id}: {type(section_info)}")
                continue

            sections.append(section)

        return sections

    def _parse_references(self, framework_type: FrameworkType, references_data: dict[str, Any], sections: list[FrameworkSection]) -> list[FrameworkReference]:
        """Parse framework references.

        Args:
            framework_type: Framework type
            references_data: Raw references data
            sections: Framework sections

        Returns:
            List of parsed references
        """
        references = []
        section_map = {s.section_id: s for s in sections}

        for ref_id, ref_info in references_data.items():
            try:
                if isinstance(ref_info, str):
                    # Simple reference with just URL
                    reference = FrameworkReference(
                        id=ref_id,
                        framework_type=framework_type,
                        section="general",
                        title=ref_id,
                        description=f"Reference to {ref_info}",
                        official_url=ref_info if ref_info.startswith(('http://', 'https://')) else None,
                    )
                elif isinstance(ref_info, dict):
                    # Complex reference with metadata
                    reference = FrameworkReference(
                        id=ref_id,
                        framework_type=framework_type,
                        section=ref_info.get("section", "general"),
                        title=ref_info.get("title", ref_id),
                        description=ref_info.get("description", ""),
                        severity=SeverityLevel(ref_info.get("severity", "medium")),
                        official_url=ref_info.get("url"),
                        documentation_url=ref_info.get("documentation"),
                        control_id=ref_info.get("control_id"),
                        category=ref_info.get("category"),
                        subcategory=ref_info.get("subcategory"),
                        related_references=ref_info.get("related", []),
                        tags=ref_info.get("tags", []),
                    )
                else:
                    logger.warning(f"Invalid reference format for {ref_id}: {type(ref_info)}")
                    continue

                # Validate section exists
                if reference.section not in section_map:
                    logger.warning(f"Reference {ref_id} has invalid section: {reference.section}")
                    reference.section = "general"

                references.append(reference)

            except Exception as e:
                logger.error(f"Failed to parse reference {ref_id}: {e}")
                continue

        return references

    def _link_references_to_sections(self, framework: GovernanceFramework) -> None:
        """Link references to their sections.

        Args:
            framework: Framework to update
        """
        section_map = {s.section_id: s for s in framework.sections}

        for reference in framework.references:
            section = section_map.get(reference.section)
            if section:
                if reference.id not in section.references:
                    section.references.append(reference.id)
                section.reference_count = len(section.references)

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse date string to datetime.

        Args:
            date_str: Date string

        Returns:
            Parsed datetime or None
        """
        if not date_str:
            return None

        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

            logger.warning(f"Failed to parse date: {date_str}")
            return None

        except Exception as e:
            logger.error(f"Error parsing date {date_str}: {e}")
            return None

    def get_framework(self, framework_type: FrameworkType) -> GovernanceFramework | None:
        """Get a loaded framework.

        Args:
            framework_type: Framework type

        Returns:
            Framework data or None if not loaded
        """
        return self.loaded_frameworks.get(framework_type)

    def get_all_frameworks(self) -> dict[FrameworkType, GovernanceFramework]:
        """Get all loaded frameworks.

        Returns:
            All loaded frameworks
        """
        return self.loaded_frameworks.copy()

    def clear_cache(self) -> None:
        """Clear the framework data cache."""
        try:
            import shutil
            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(exist_ok=True)
            logger.info("Framework cache cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
