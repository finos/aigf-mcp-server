"""
Framework Data Loader

Loads and validates governance framework data from YAML files.
Supports dynamic framework discovery and data validation.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import yaml
from pydantic import HttpUrl

from ..logging import get_logger
from .loaders.loader_registry import get_loader_registry
from .models import (
    ComplianceStatus,
    FrameworkReference,
    FrameworkSection,
    FrameworkType,
    GovernanceFramework,
    SeverityLevel,
)

logger = get_logger(__name__)


class FrameworkDataLoader:
    """Loads and validates framework data from external sources."""

    def __init__(
        self,
        base_url: str = "https://raw.githubusercontent.com/finos/ai-governance-framework/main/",
        enable_dynamic_loading: bool = True,
    ):
        """Initialize framework data loader.

        Args:
            base_url: Base URL for framework data repository
            enable_dynamic_loading: Whether to use dynamic loaders when available
        """
        self.base_url = base_url.rstrip("/") + "/"
        self.enable_dynamic_loading = enable_dynamic_loading
        self.loaded_frameworks: dict[FrameworkType, GovernanceFramework] = {}

        # Framework file mappings for static YAML fallback
        self.framework_files = {
            FrameworkType.NIST_AI_RMF: "nist-ai-600-1.yml",
            FrameworkType.EU_AI_ACT: "eu-ai-act.yml",
            FrameworkType.OWASP_LLM: "owasp-llm.yml",
            FrameworkType.ISO_27001: "iso-27001.yml",
            FrameworkType.GDPR: "gdpr.yml",
            FrameworkType.CCPA: "ccpa.yml",
            FrameworkType.SOC2: "soc2.yml",
        }

        # Framework to dynamic loader name mapping
        self.dynamic_loader_mapping = {
            FrameworkType.ISO_27001: "iso42001",  # Using ISO 42001 loader for ISO 27001
            FrameworkType.SOC2: "ffiec",  # Using FFIEC loader patterns for SOC2
            FrameworkType.GDPR: "gdpr",  # Using dedicated GDPR loader
            FrameworkType.CCPA: "ccpa",  # Using dedicated CCPA loader
        }

        self.cache_dir = Path(".framework_cache")
        self.cache_dir.mkdir(exist_ok=True)

        # Lazy initialization of loader registry
        self._loader_registry = None

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
            elif isinstance(result, GovernanceFramework):
                self.loaded_frameworks[framework_type] = result
                loaded_count += 1

        logger.info(
            f"Successfully loaded {loaded_count}/{len(FrameworkType)} frameworks"
        )
        return self.loaded_frameworks

    async def _get_loader_registry(self):
        """Get loader registry with lazy initialization."""
        if self._loader_registry is None:
            self._loader_registry = await get_loader_registry()
        return self._loader_registry

    async def load_framework(
        self, framework_type: FrameworkType
    ) -> GovernanceFramework:
        """Load a specific framework with dynamic loader integration.

        Args:
            framework_type: Framework to load

        Returns:
            Loaded framework data
        """
        logger.info(f"Loading framework: {framework_type}")

        try:
            # Try dynamic loading first if enabled and available
            if self.enable_dynamic_loading:
                loader_name = self.dynamic_loader_mapping.get(framework_type)
                if loader_name:
                    framework = await self._load_with_dynamic_loader(
                        framework_type, loader_name
                    )
                    if framework:
                        logger.info(
                            f"Loaded framework {framework_type} via dynamic loader '{loader_name}': "
                            f"{len(framework.references)} references, {len(framework.sections)} sections"
                        )
                        return framework
                    else:
                        logger.warning(
                            f"Dynamic loader '{loader_name}' failed for {framework_type}, "
                            "falling back to static YAML loading"
                        )

            # Fallback to static YAML loading
            framework = await self._load_with_static_yaml(framework_type)
            logger.info(
                f"Loaded framework {framework_type} via static YAML: "
                f"{len(framework.references)} references, {len(framework.sections)} sections"
            )
            return framework

        except Exception as e:
            logger.error(f"Failed to load framework {framework_type}: {e}")
            raise

    async def _load_with_dynamic_loader(
        self, framework_type: FrameworkType, loader_name: str
    ) -> GovernanceFramework | None:
        """Load framework using dynamic loader.

        Args:
            framework_type: Framework type to load
            loader_name: Name of the dynamic loader

        Returns:
            Loaded framework or None if failed
        """
        try:
            registry = await self._get_loader_registry()
            loader = await registry.get_loader(loader_name)

            if not loader:
                logger.warning(f"No loader found for '{loader_name}'")
                return None

            framework = await loader.load_framework()

            if framework and isinstance(framework, GovernanceFramework):
                # If loader returns GovernanceFramework directly
                return framework
            elif framework and isinstance(framework, dict):
                # If loader returns raw data, parse it into GovernanceFramework
                return self._parse_framework_data(framework_type, framework)
            else:
                logger.warning(
                    f"Dynamic loader '{loader_name}' returned unexpected data type: {type(framework)}"
                )
                return None

        except Exception as e:
            logger.error(
                f"Error using dynamic loader '{loader_name}' for {framework_type}: {e}",
                extra={
                    "framework_type": framework_type.value,
                    "loader_name": loader_name,
                    "error": str(e),
                },
            )
            return None

    async def _load_with_static_yaml(
        self, framework_type: FrameworkType
    ) -> GovernanceFramework:
        """Load framework using static YAML method.

        Args:
            framework_type: Framework type to load

        Returns:
            Loaded framework data
        """
        # Get framework file path
        filename = self.framework_files.get(framework_type)
        if not filename:
            raise ValueError(f"No file mapping for framework: {framework_type}")

        # Load framework data
        raw_data = await self._fetch_framework_data(filename)

        # Parse and validate framework
        return self._parse_framework_data(framework_type, raw_data)

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
                with open(cache_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                logger.debug(f"Loaded framework data from cache: {filename}")
                return data
            except Exception as e:
                logger.warning(f"Failed to load cached data for {filename}: {e}")

        # Fetch from remote source
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                url = urljoin(self.base_url, filename)
                response = await client.get(url, timeout=30.0)

                if response.status_code == 200:
                    content = response.text
                    data = yaml.safe_load(content)

                    # Cache the data
                    try:
                        with open(cache_file, "w", encoding="utf-8") as f:
                            yaml.dump(data, f, default_flow_style=False)
                        logger.debug(f"Cached framework data: {filename}")
                    except Exception as e:
                        logger.warning(f"Failed to cache data for {filename}: {e}")

                    return data
                else:
                    raise ValueError(f"HTTP {response.status_code} for {url}")

        except ImportError:
            # Fallback to synchronous httpx if async not available
            import httpx

            url = urljoin(self.base_url, filename)
            with httpx.Client() as client:
                response = client.get(url, timeout=30.0)
                response.raise_for_status()
                data = yaml.safe_load(response.content)

            # Cache the data
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False)
                logger.debug(f"Cached framework data: {filename}")
            except Exception as e:
                logger.warning(f"Failed to cache data for {filename}: {e}")

            return data
        except Exception as e:
            logger.error(f"Failed to fetch framework data from {filename}: {e}")
            raise

    def _parse_framework_data(
        self, framework_type: FrameworkType, raw_data: dict[str, Any]
    ) -> GovernanceFramework:
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
            framework.references = self._parse_references(
                framework_type, references_data, framework.sections
            )

            # Update statistics
            framework.total_references = len(framework.references)
            framework.active_references = len(
                [
                    ref
                    for ref in framework.references
                    if ref.compliance_status != ComplianceStatus.NOT_APPLICABLE
                ]
            )

            # Link references to sections
            self._link_references_to_sections(framework)

            return framework

        except Exception as e:
            logger.error(f"Failed to parse framework data for {framework_type}: {e}")
            raise

    def _parse_sections(
        self, framework_type: FrameworkType, sections_data: dict[str, Any]
    ) -> list[FrameworkSection]:
        """Parse framework sections.

        Args:
            framework_type: Framework type
            sections_data: Raw sections data

        Returns:
            List of parsed sections
        """
        sections: list[FrameworkSection] = []

        for section_id, section_info in sections_data.items():
            if isinstance(section_info, str):
                # Simple section with just title
                section = FrameworkSection(
                    framework_type=framework_type,
                    section_id=section_id,
                    title=section_info,
                    description=None,
                    parent_section=None,
                    order=len(sections),
                    is_active=True,
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
                    is_active=section_info.get("active", True),
                )
            else:
                logger.warning(
                    f"Invalid section format for {section_id}: {type(section_info)}"
                )
                continue

            sections.append(section)

        return sections

    def _parse_references(
        self,
        framework_type: FrameworkType,
        references_data: dict[str, Any],
        sections: list[FrameworkSection],
    ) -> list[FrameworkReference]:
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
                        official_url=HttpUrl(ref_info)
                        if ref_info.startswith(("http://", "https://"))
                        else None,
                        documentation_url=None,
                        control_id=None,
                        category=None,
                        subcategory=None,
                        implementation_notes=None,
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
                        official_url=HttpUrl(url)
                        if (url := ref_info.get("url"))
                        and isinstance(url, str)
                        and url.startswith(("http://", "https://"))
                        else None,
                        documentation_url=HttpUrl(doc_url)
                        if (doc_url := ref_info.get("documentation"))
                        and isinstance(doc_url, str)
                        and doc_url.startswith(("http://", "https://"))
                        else None,
                        control_id=ref_info.get("control_id"),
                        category=ref_info.get("category"),
                        subcategory=ref_info.get("subcategory"),
                        related_references=ref_info.get("related", []),
                        tags=ref_info.get("tags", []),
                        implementation_notes=ref_info.get("implementation_notes"),
                    )
                else:
                    logger.warning(
                        f"Invalid reference format for {ref_id}: {type(ref_info)}"
                    )
                    continue

                # Validate section exists
                if reference.section not in section_map:
                    logger.warning(
                        f"Reference {ref_id} has invalid section: {reference.section}"
                    )
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

    def get_framework(
        self, framework_type: FrameworkType
    ) -> GovernanceFramework | None:
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

    async def invalidate_framework_cache(
        self, framework_type: FrameworkType | None = None
    ) -> None:
        """Invalidate framework cache with intelligent cache invalidation.

        Args:
            framework_type: Specific framework to invalidate, or None for all
        """
        try:
            if framework_type:
                # Invalidate specific framework
                self.loaded_frameworks.pop(framework_type, None)

                # Clear corresponding cache files
                filename = self.framework_files.get(framework_type)
                if filename:
                    cache_file = self.cache_dir / filename
                    if cache_file.exists():
                        cache_file.unlink()
                        logger.info(f"Cleared cache for framework: {framework_type}")

                # Invalidate dynamic loader cache if applicable
                if self.enable_dynamic_loading:
                    loader_name = self.dynamic_loader_mapping.get(framework_type)
                    if loader_name:
                        try:
                            await self._get_loader_registry()
                            # Note: The registry doesn't have individual cache invalidation yet
                            # This is a placeholder for future enhancement
                            logger.debug(
                                f"Framework {framework_type} uses dynamic loader '{loader_name}'"
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to invalidate dynamic loader cache: {e}"
                            )
            else:
                # Clear all framework cache
                self.loaded_frameworks.clear()
                self._clear_all_cache_files()
                logger.info("All framework cache cleared")

        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")

    def _clear_all_cache_files(self) -> None:
        """Clear all framework cache files."""
        try:
            import shutil

            if self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                self.cache_dir.mkdir(exist_ok=True)
                logger.info("All framework cache files cleared")
        except Exception as e:
            logger.error(f"Failed to clear cache files: {e}")

    async def get_loader_health_status(self) -> dict[str, Any]:
        """Get health status of all dynamic loaders.

        Returns:
            Health status information for dynamic loaders
        """
        try:
            if not self.enable_dynamic_loading:
                return {
                    "dynamic_loading_enabled": False,
                    "message": "Dynamic loading is disabled",
                }

            registry = await self._get_loader_registry()
            health_status = await registry.health_check_all()

            # Add mapping information
            health_status["framework_mappings"] = {
                framework_type.value: loader_name
                for framework_type, loader_name in self.dynamic_loader_mapping.items()
            }
            health_status["dynamic_loading_enabled"] = True

            return health_status

        except Exception as e:
            logger.error(f"Failed to get loader health status: {e}")
            return {
                "dynamic_loading_enabled": self.enable_dynamic_loading,
                "error": str(e),
                "healthy": False,
            }

    async def close(self) -> None:
        """Close data loader and cleanup resources."""
        logger.info("Shutting down framework data loader")

        try:
            # Close loader registry if initialized
            if self._loader_registry:
                await self._loader_registry.close_all()
                logger.debug("Loader registry closed")
        except Exception as e:
            logger.warning(f"Error closing loader registry: {e}")

        # Clear loaded frameworks
        self.loaded_frameworks.clear()

        logger.info("Framework data loader shutdown complete")

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
