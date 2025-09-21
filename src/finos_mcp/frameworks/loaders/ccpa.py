"""CCPA (California Consumer Privacy Act) framework loader.

Copyright 2024 Hugo Calderon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This loader fetches CCPA framework data from official California sources
and standardized repositories.
"""

import json
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from ..models import (
    ComplianceStatus,
    FrameworkReference,
    FrameworkSection,
    FrameworkType,
    GovernanceFramework,
    SeverityLevel,
)
from .base_loader import BaseFrameworkLoader, LoaderContext


class CCPALoader(BaseFrameworkLoader):
    """Loader for CCPA (California Consumer Privacy Act) framework.

    This loader fetches CCPA framework data from official California sources
    and standardized repositories following the existing ContentService patterns.
    """

    def __init__(self, framework_name: str = "ccpa") -> None:
        """Initialize CCPA loader."""
        super().__init__(framework_name)

        # CCPA official and reliable sources
        self.base_urls = [
            "https://oag.ca.gov/privacy/ccpa/",
            "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml",
            "https://raw.githubusercontent.com/ccpa-compliance/ccpa-framework/main/",
        ]

        # CCPA sections structure
        self.ccpa_sections = [
            {
                "section": "1798.100",
                "title": "Consumer's Right to Know",
                "category": "Consumer Rights",
                "description": "Right to know about personal information collected",
                "severity": "high",
            },
            {
                "section": "1798.105",
                "title": "Consumer's Right to Delete",
                "category": "Consumer Rights",
                "description": "Right to delete personal information",
                "severity": "high",
            },
            {
                "section": "1798.106",
                "title": "Consumer's Right to Correct",
                "category": "Consumer Rights",
                "description": "Right to correct inaccurate personal information",
                "severity": "medium",
            },
            {
                "section": "1798.110",
                "title": "Consumer's Right to Know Categories",
                "category": "Consumer Rights",
                "description": "Right to know categories of personal information",
                "severity": "high",
            },
            {
                "section": "1798.115",
                "title": "Consumer's Right to Know Business Purposes",
                "category": "Consumer Rights",
                "description": "Right to know business purposes for collecting personal information",
                "severity": "medium",
            },
            {
                "section": "1798.120",
                "title": "Consumer's Right to Opt-Out",
                "category": "Consumer Rights",
                "description": "Right to opt-out of the sale of personal information",
                "severity": "critical",
            },
            {
                "section": "1798.121",
                "title": "Consumer's Right to Limit Use",
                "category": "Consumer Rights",
                "description": "Right to limit use and disclosure of sensitive personal information",
                "severity": "high",
            },
            {
                "section": "1798.125",
                "title": "Non-Discrimination",
                "category": "Consumer Protection",
                "description": "Prohibition on discrimination for exercising CCPA rights",
                "severity": "critical",
            },
            {
                "section": "1798.130",
                "title": "Notice at Collection",
                "category": "Transparency",
                "description": "Requirements for notice at collection of personal information",
                "severity": "critical",
            },
            {
                "section": "1798.135",
                "title": "Methods for Submitting Requests",
                "category": "Implementation",
                "description": "Methods for consumers to submit requests",
                "severity": "high",
            },
            {
                "section": "1798.140",
                "title": "Definitions",
                "category": "Definitions",
                "description": "Key definitions for CCPA terms",
                "severity": "medium",
            },
            {
                "section": "1798.145",
                "title": "Exemptions",
                "category": "Exemptions",
                "description": "Exemptions from CCPA requirements",
                "severity": "medium",
            },
            {
                "section": "1798.150",
                "title": "Personal Information Security",
                "category": "Security",
                "description": "Requirements for personal information security",
                "severity": "critical",
            },
            {
                "section": "1798.155",
                "title": "Administrative Enforcement",
                "category": "Enforcement",
                "description": "Administrative enforcement provisions",
                "severity": "high",
            },
        ]

    async def _load_from_source(self, context: LoaderContext) -> dict[str, Any] | None:
        """Load CCPA framework data from external sources.

        Args:
            context: Loading context

        Returns:
            Raw framework data dictionary or None if failed
        """
        self.logger.info(
            "Loading CCPA from external sources",
            extra={
                "operation_id": context.operation_id,
                "framework": self.framework_name,
            },
        )

        # Try fetching from official sources
        for base_url in self.base_urls:
            try:
                # Try different common file formats
                for filename in ["ccpa.json", "framework.json", "privacy-act.json"]:
                    url = urljoin(base_url, filename)
                    content = await self._fetch_content_with_circuit_breaker(
                        url, context
                    )

                    if content:
                        try:
                            data = json.loads(content)
                            self.logger.info(
                                "Successfully loaded CCPA from %s",
                                url,
                                extra={
                                    "operation_id": context.operation_id,
                                    "source": url,
                                },
                            )
                            return await self._parse_external_data(data, context)

                        except json.JSONDecodeError as e:
                            self.logger.debug(
                                "Failed to parse JSON from %s: %s", url, e
                            )
                            continue

            except Exception as e:
                self.logger.debug(
                    "Error fetching from %s: %s",
                    base_url,
                    e,
                    extra={
                        "operation_id": context.operation_id,
                        "source": base_url,
                        "error": str(e),
                    },
                )
                continue

        # Fallback to structured data generation
        self.logger.info(
            "External sources unavailable, using structured fallback data",
            extra={
                "operation_id": context.operation_id,
                "framework": self.framework_name,
            },
        )

        return await self._generate_structured_data(context)

    async def _parse_external_data(
        self, data: dict[str, Any], context: LoaderContext
    ) -> dict[str, Any]:
        """Parse externally fetched CCPA data.

        Args:
            data: Raw external data
            context: Loading context

        Returns:
            Normalized framework data
        """
        # Extract sections and references from external data
        sections = []
        references = []

        # Parse sections
        if "sections" in data:
            for section_data in data["sections"]:
                section = self._create_section_from_data(section_data)
                sections.append(section)

        # Parse requirements
        if "requirements" in data:
            for requirement_data in data["requirements"]:
                reference = self._create_reference_from_data(requirement_data)
                references.append(reference)

        return {
            "framework_type": FrameworkType.CCPA,
            "name": "California Consumer Privacy Act",
            "version": "2020 (CPRA amended)",
            "description": "California state privacy law providing consumer privacy rights",
            "publisher": "State of California",
            "publication_date": datetime(2018, 6, 28),
            "effective_date": datetime(2020, 1, 1),
            "official_url": "https://oag.ca.gov/privacy/ccpa",
            "sections": sections,
            "references": references,
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    async def _generate_structured_data(self, context: LoaderContext) -> dict[str, Any]:
        """Generate structured CCPA data when external sources are unavailable.

        Args:
            context: Loading context

        Returns:
            Structured framework data
        """
        sections_dict: dict[str, dict[str, Any]] = {}
        references: list[dict[str, Any]] = []

        # Group sections by category
        for section_data in self.ccpa_sections:
            category = section_data["category"]
            if category not in sections_dict:
                sections_dict[category] = {
                    "section_id": category.lower().replace(" ", "_"),
                    "title": category,
                    "sections": [],
                }
            sections_dict[category]["sections"].append(section_data)

        # Generate sections
        sections = []
        for i, (category, category_info) in enumerate(sections_dict.items()):
            section = FrameworkSection(
                framework_type=FrameworkType.CCPA,
                section_id=category_info["section_id"],
                title=category_info["title"],
                description=f"CCPA {category_info['title']} provisions",
                parent_section=None,
                references=[],
                reference_count=0,
                order=i,
            )
            sections.append(section.dict())

            # Generate references for each section in this category
            section_refs = []
            for section_data in category_info["sections"]:
                section_ref = FrameworkReference(
                    id=f"ccpa-{section_data['section'].replace('.', '-')}",
                    framework_type=FrameworkType.CCPA,
                    section=category,
                    title=f"Section {section_data['section']}: {section_data['title']}",
                    description=f"CCPA {section_data['description']}",
                    severity=SeverityLevel(section_data["severity"]),
                    control_id=section_data["section"],
                    category=category,
                    compliance_status=ComplianceStatus.UNDER_REVIEW,
                    tags=["ccpa", "privacy", "california", "consumer-rights"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    official_url=None,
                    documentation_url=None,
                    subcategory=section_data["title"],
                    implementation_notes=f"Implementation guidance for CCPA {section_data['title']}",
                )
                section_refs.append(section_ref.dict())
                references.append(section_ref.dict())

            # Update section dict with references
            section_dict = section.dict()
            section_dict["references"] = [ref["id"] for ref in section_refs]
            section_dict["reference_count"] = len(section_refs)
            sections[i] = section_dict  # Replace the section in the list

        return {
            "framework_type": FrameworkType.CCPA,
            "name": "California Consumer Privacy Act",
            "version": "2020 (CPRA amended)",
            "description": "California state privacy law that grants California residents specific rights regarding their personal information",
            "publisher": "State of California",
            "publication_date": datetime(2018, 6, 28),
            "effective_date": datetime(2020, 1, 1),
            "official_url": "https://oag.ca.gov/privacy/ccpa",
            "documentation_url": "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=3.&part=4.&lawCode=CIV&title=1.81.5",
            "sections": sections,
            "references": references,
            "total_references": len(references),
            "active_references": len(references),
            "is_active": True,
            "last_updated": datetime.utcnow(),
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    def _create_section_from_data(self, section_data: dict[str, Any]) -> dict[str, Any]:
        """Create section from external data.

        Args:
            section_data: External section data

        Returns:
            Normalized section dictionary
        """
        section = FrameworkSection(
            framework_type=FrameworkType.CCPA,
            section_id=section_data.get("category", "unknown")
            .lower()
            .replace(" ", "_"),
            title=section_data.get("category", "Unknown Section"),
            description=section_data.get("description", ""),
            parent_section=None,
            references=[
                f"ccpa-{section_data.get('section', 'unknown').replace('.', '-')}"
            ],
            reference_count=1,
            order=int(section_data.get("section", "0").split(".")[1])
            if "." in section_data.get("section", "0")
            else 0,
        )
        return section.dict()

    def _create_reference_from_data(
        self, requirement_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create reference from external data.

        Args:
            requirement_data: External requirement data

        Returns:
            Normalized reference dictionary
        """
        reference = FrameworkReference(
            id=f"ccpa-{requirement_data.get('id', 'unknown')}",
            framework_type=FrameworkType.CCPA,
            section=requirement_data.get("section", "Unknown"),
            title=requirement_data.get("title", "Unknown Requirement"),
            description=requirement_data.get("description", ""),
            severity=SeverityLevel(requirement_data.get("severity", "medium")),
            control_id=requirement_data.get("id"),
            category=requirement_data.get("category"),
            compliance_status=ComplianceStatus.UNDER_REVIEW,
            tags=["ccpa", "privacy", "california", *requirement_data.get("tags", [])],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            official_url=None,
            documentation_url=None,
            subcategory=requirement_data.get("subcategory", "General"),
            implementation_notes=requirement_data.get("implementation_notes", ""),
        )
        return reference.dict()

    async def _deserialize_framework(
        self, data: dict[str, Any], context: LoaderContext
    ) -> GovernanceFramework | None:
        """Deserialize raw data into GovernanceFramework model.

        Args:
            data: Raw framework data
            context: Loading context

        Returns:
            GovernanceFramework instance or None if failed
        """
        try:
            # Convert string dates back to datetime objects
            if isinstance(data.get("publication_date"), str):
                data["publication_date"] = datetime.fromisoformat(
                    data["publication_date"].replace("Z", "+00:00")
                )
            if isinstance(data.get("effective_date"), str):
                data["effective_date"] = datetime.fromisoformat(
                    data["effective_date"].replace("Z", "+00:00")
                )
            if isinstance(data.get("last_updated"), str):
                data["last_updated"] = datetime.fromisoformat(
                    data["last_updated"].replace("Z", "+00:00")
                )

            # Convert sections and references from dicts to model instances
            sections = []
            for section_data in data.get("sections", []):
                try:
                    section = FrameworkSection(**section_data)
                    sections.append(section)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse section {section_data.get('section_id')}: {e}"
                    )

            references = []
            for ref_data in data.get("references", []):
                try:
                    reference = FrameworkReference(**ref_data)
                    references.append(reference)
                except Exception as e:
                    self.logger.warning(
                        f"Failed to parse reference {ref_data.get('id')}: {e}"
                    )

            # Create framework instance
            framework = GovernanceFramework(
                framework_type=FrameworkType(data["framework_type"]),
                name=data["name"],
                version=data["version"],
                description=data["description"],
                publisher=data["publisher"],
                publication_date=data.get("publication_date"),
                effective_date=data.get("effective_date"),
                official_url=data.get("official_url"),
                documentation_url=data.get("documentation_url"),
                sections=sections,
                references=references,
                total_references=len(references),
                active_references=len(references),
                is_active=data.get("is_active", True),
                last_updated=data.get("last_updated", datetime.utcnow()),
            )

            self.logger.info(
                "Successfully deserialized CCPA framework: %d sections, %d references",
                len(sections),
                len(references),
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "sections": len(sections),
                    "references": len(references),
                },
            )

            return framework

        except Exception as e:
            self.logger.error(
                "Failed to deserialize CCPA framework: %s",
                e,
                extra={
                    "operation_id": context.operation_id,
                    "framework": self.framework_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            return None

    def get_source_urls(self) -> list[str]:
        """Get list of source URLs for CCPA.

        Returns:
            List of URLs where CCPA data can be found
        """
        return [
            "https://oag.ca.gov/privacy/ccpa",
            "https://leginfo.legislature.ca.gov/faces/codes_displayText.xhtml?division=3.&part=4.&lawCode=CIV&title=1.81.5",
            "https://cppa.ca.gov/",
        ]
