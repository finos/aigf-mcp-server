"""ISO 42001 AI Management System framework loader.

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

This loader fetches ISO 42001 AI Management System framework data from
official and reliable sources.
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


class ISO42001Loader(BaseFrameworkLoader):
    """Loader for ISO 42001 AI Management System framework.

    This loader fetches ISO 42001 framework data from official ISO sources
    and standardized repositories following the existing ContentService patterns.
    """

    def __init__(self, framework_name: str = "iso42001") -> None:
        """Initialize ISO 42001 loader."""
        super().__init__(framework_name)

        # ISO 42001 official and reliable sources
        self.base_urls = [
            "https://raw.githubusercontent.com/iso-standards/iso-42001/main/",
            "https://www.iso.org/standard/",
            "https://standards.iso.org/iso-iec/42001/",
        ]

        # Fallback structured data for ISO 42001 if external sources unavailable
        self.fallback_sections = [
            {
                "section_id": "4",
                "title": "Context of the Organization",
                "description": "Understanding the organization and its context",
                "subsections": ["4.1", "4.2", "4.3", "4.4"],
            },
            {
                "section_id": "5",
                "title": "Leadership",
                "description": "Leadership and commitment for AI management",
                "subsections": ["5.1", "5.2", "5.3"],
            },
            {
                "section_id": "6",
                "title": "Planning",
                "description": "Actions to address risks and opportunities",
                "subsections": ["6.1", "6.2", "6.3"],
            },
            {
                "section_id": "7",
                "title": "Support",
                "description": "Resources, competence, awareness, and communication",
                "subsections": ["7.1", "7.2", "7.3", "7.4", "7.5"],
            },
            {
                "section_id": "8",
                "title": "Operation",
                "description": "AI system lifecycle and operational planning",
                "subsections": ["8.1", "8.2", "8.3", "8.4", "8.5"],
            },
            {
                "section_id": "9",
                "title": "Performance Evaluation",
                "description": "Monitoring, measurement, analysis and evaluation",
                "subsections": ["9.1", "9.2", "9.3"],
            },
            {
                "section_id": "10",
                "title": "Improvement",
                "description": "Continual improvement processes",
                "subsections": ["10.1", "10.2", "10.3"],
            },
        ]

    async def _load_from_source(self, context: LoaderContext) -> dict[str, Any] | None:
        """Load ISO 42001 framework data from external sources.

        Args:
            context: Loading context

        Returns:
            Raw framework data dictionary or None if failed
        """
        self.logger.info(
            "Loading ISO 42001 from external sources",
            extra={
                "operation_id": context.operation_id,
                "framework": self.framework_name,
            },
        )

        # Try fetching from official sources
        for base_url in self.base_urls:
            try:
                # Try different common file formats
                for filename in ["iso-42001.json", "framework.json", "standard.json"]:
                    url = urljoin(base_url, filename)
                    content = await self._fetch_content_with_circuit_breaker(
                        url, context
                    )

                    if content:
                        try:
                            data = json.loads(content)
                            self.logger.info(
                                "Successfully loaded ISO 42001 from %s",
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
        """Parse externally fetched ISO 42001 data.

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

        # Parse controls/requirements
        if "controls" in data:
            for control_data in data["controls"]:
                reference = self._create_reference_from_data(control_data)
                references.append(reference)

        return {
            "framework_type": FrameworkType.ISO_27001,  # Using closest available type
            "name": "ISO/IEC 42001:2023",
            "version": "2023",
            "description": "Information technology — Artificial intelligence — Management system",
            "publisher": "International Organization for Standardization",
            "publication_date": datetime(2023, 12, 15),
            "effective_date": datetime(2023, 12, 15),
            "official_url": "https://www.iso.org/standard/81230.html",
            "sections": sections,
            "references": references,
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    async def _generate_structured_data(self, context: LoaderContext) -> dict[str, Any]:
        """Generate structured ISO 42001 data when external sources are unavailable.

        Args:
            context: Loading context

        Returns:
            Structured framework data
        """
        sections = []
        references = []

        # Generate sections
        for section_data in self.fallback_sections:
            section_id_str = str(section_data["section_id"])
            title_str = str(section_data["title"])
            description_str = str(section_data["description"])

            section = FrameworkSection(
                framework_type=FrameworkType.ISO_27001,  # Using closest available
                section_id=section_id_str,
                title=title_str,
                description=description_str,
                parent_section=None,
                references=[],
                reference_count=0,
                order=int(section_id_str.split(".")[0]),
            )
            section_dict = section.dict()
            sections.append(section_dict)

            # Generate references for each section
            section_refs = await self._generate_section_references(
                section_data, context
            )
            references.extend(section_refs)
            section_dict["references"] = [ref["id"] for ref in section_refs]
            section_dict["reference_count"] = len(section_refs)

        return {
            "framework_type": FrameworkType.ISO_27001,
            "name": "ISO/IEC 42001:2023",
            "version": "2023",
            "description": "Information technology — Artificial intelligence — Management system",
            "publisher": "International Organization for Standardization",
            "publication_date": datetime(2023, 12, 15),
            "effective_date": datetime(2023, 12, 15),
            "official_url": "https://www.iso.org/standard/81230.html",
            "documentation_url": "https://www.iso.org/obp/ui/en/#iso:std:iso-iec:42001:ed-1:v1:en",
            "sections": sections,
            "references": references,
            "total_references": len(references),
            "active_references": len(references),
            "is_active": True,
            "last_updated": datetime.utcnow(),
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    async def _generate_section_references(
        self, section_data: dict[str, Any], context: LoaderContext
    ) -> list[dict[str, Any]]:
        """Generate references for a section.

        Args:
            section_data: Section configuration
            context: Loading context

        Returns:
            List of reference dictionaries
        """
        references = []
        section_id = section_data["section_id"]
        base_severity = self._get_section_severity(section_id)

        # Generate main section requirement
        main_ref = FrameworkReference(
            id=f"iso42001-{section_id}",
            framework_type=FrameworkType.ISO_27001,
            section=section_data["title"],
            title=f"{section_id} {section_data['title']}",
            description=section_data["description"],
            severity=base_severity,
            official_url=None,
            documentation_url=None,
            control_id=section_id,
            category=section_data["title"],
            subcategory=None,
            compliance_status=ComplianceStatus.UNDER_REVIEW,
            implementation_notes=None,
            tags=["iso42001", "ai-management", "standard"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        references.append(main_ref.dict())

        # Generate subsection requirements
        for subsection_id in section_data.get("subsections", []):
            subsection_ref = FrameworkReference(
                id=f"iso42001-{subsection_id}",
                framework_type=FrameworkType.ISO_27001,
                section=section_data["title"],
                title=f"{subsection_id} {self._get_subsection_title(subsection_id)}",
                description=f"Requirement {subsection_id} under {section_data['title']}",
                severity=base_severity,
                official_url=None,
                documentation_url=None,
                control_id=subsection_id,
                category=section_data["title"],
                subcategory=subsection_id,
                compliance_status=ComplianceStatus.UNDER_REVIEW,
                implementation_notes=None,
                related_references=[f"iso42001-{section_id}"],
                tags=["iso42001", "ai-management", "standard", "subsection"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            references.append(subsection_ref.dict())

        return references

    def _get_section_severity(self, section_id: str) -> SeverityLevel:
        """Get severity level for section based on section ID.

        Args:
            section_id: Section identifier

        Returns:
            Appropriate severity level
        """
        # Critical sections for AI management
        if section_id in ["5", "6", "8"]:  # Leadership, Planning, Operation
            return SeverityLevel.HIGH
        elif section_id in ["4", "9"]:  # Context, Performance Evaluation
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _get_subsection_title(self, subsection_id: str) -> str:
        """Get title for subsection based on ID.

        Args:
            subsection_id: Subsection identifier

        Returns:
            Subsection title
        """
        titles = {
            "4.1": "Understanding the Organization and its Context",
            "4.2": "Understanding the Needs and Expectations of Interested Parties",
            "4.3": "Determining the Scope of the AI Management System",
            "4.4": "AI Management System",
            "5.1": "Leadership and Commitment",
            "5.2": "AI Policy",
            "5.3": "Organizational Roles, Responsibilities and Authorities",
            "6.1": "Actions to Address Risks and Opportunities",
            "6.2": "AI Objectives and Planning to Achieve Them",
            "6.3": "Planning of Changes",
            "7.1": "Resources",
            "7.2": "Competence",
            "7.3": "Awareness",
            "7.4": "Communication",
            "7.5": "Documented Information",
            "8.1": "Operational Planning and Control",
            "8.2": "AI System Development or Acquisition",
            "8.3": "AI System Deployment",
            "8.4": "AI System Monitoring",
            "8.5": "AI System Change Management",
            "9.1": "Monitoring, Measurement, Analysis and Evaluation",
            "9.2": "Internal Audit",
            "9.3": "Management Review",
            "10.1": "Nonconformity and Corrective Action",
            "10.2": "Continual Improvement",
            "10.3": "Learning and Improvement",
        }
        return titles.get(subsection_id, f"Requirement {subsection_id}")

    def _create_section_from_data(self, section_data: dict[str, Any]) -> dict[str, Any]:
        """Create section from external data.

        Args:
            section_data: External section data

        Returns:
            Normalized section dictionary
        """
        section = FrameworkSection(
            framework_type=FrameworkType.ISO_27001,
            section_id=section_data.get("id", "unknown"),
            title=section_data.get("title", "Unknown Section"),
            description=section_data.get("description", ""),
            parent_section=section_data.get("parent_section"),
            references=section_data.get("references", []),
            reference_count=len(section_data.get("references", [])),
            order=section_data.get("order", 0),
        )
        return section.dict()

    def _create_reference_from_data(
        self, control_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Create reference from external data.

        Args:
            control_data: External control data

        Returns:
            Normalized reference dictionary
        """
        reference = FrameworkReference(
            id=f"iso42001-{control_data.get('id', 'unknown')}",
            framework_type=FrameworkType.ISO_27001,
            section=control_data.get("section", "Unknown"),
            title=control_data.get("title", "Unknown Control"),
            description=control_data.get("description", ""),
            severity=SeverityLevel(control_data.get("severity", "medium")),
            official_url=None,
            documentation_url=None,
            control_id=control_data.get("id"),
            category=control_data.get("category"),
            subcategory=control_data.get("subcategory"),
            compliance_status=ComplianceStatus.UNDER_REVIEW,
            implementation_notes=control_data.get("implementation_notes"),
            tags=["iso42001", "ai-management", *control_data.get("tags", [])],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
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
                "Successfully deserialized ISO 42001 framework: %d sections, %d references",
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
                "Failed to deserialize ISO 42001 framework: %s",
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
        """Get list of source URLs for ISO 42001.

        Returns:
            List of URLs where ISO 42001 data can be found
        """
        return [
            "https://www.iso.org/standard/81230.html",
            "https://www.iso.org/obp/ui/en/#iso:std:iso-iec:42001:ed-1:v1:en",
            "https://standards.iso.org/iso-iec/42001/",
        ]
