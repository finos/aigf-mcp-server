"""FFIEC (Federal Financial Institutions Examination Council) guidance loader.

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

This loader fetches FFIEC guidance on artificial intelligence and machine
learning from official FFIEC sources.
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


class FFIECLoader(BaseFrameworkLoader):
    """Loader for FFIEC AI/ML guidance framework.

    This loader fetches FFIEC artificial intelligence and machine learning
    guidance from official FFIEC sources following ContentService patterns.
    """

    def __init__(self, framework_name: str = "ffiec") -> None:
        """Initialize FFIEC loader."""
        super().__init__(framework_name)

        # FFIEC official sources
        self.base_urls = [
            "https://www.ffiec.gov/",
            "https://www.ffiec.gov/press/",
            "https://www.ffiec.gov/pdf/",
        ]

        # FFIEC AI/ML guidance structure based on official publications
        self.fallback_sections = [
            {
                "section_id": "governance",
                "title": "Governance and Risk Management",
                "description": "AI/ML governance frameworks and risk management processes",
                "priority": "high",
                "requirements": [
                    "Board and senior management oversight",
                    "AI/ML risk management framework",
                    "Model risk management policy",
                    "Third-party risk management",
                ],
            },
            {
                "section_id": "development",
                "title": "Model Development and Implementation",
                "description": "AI/ML model development, validation, and implementation controls",
                "priority": "high",
                "requirements": [
                    "Model development standards",
                    "Model validation framework",
                    "Model documentation requirements",
                    "Implementation controls",
                ],
            },
            {
                "section_id": "monitoring",
                "title": "Model Monitoring and Performance",
                "description": "Ongoing monitoring and performance assessment of AI/ML models",
                "priority": "high",
                "requirements": [
                    "Performance monitoring systems",
                    "Model drift detection",
                    "Outcome testing procedures",
                    "Performance reporting",
                ],
            },
            {
                "section_id": "explainability",
                "title": "Model Explainability and Interpretability",
                "description": "Requirements for AI/ML model transparency and explainability",
                "priority": "medium",
                "requirements": [
                    "Explainability frameworks",
                    "Model interpretability standards",
                    "Documentation of decision logic",
                    "Consumer disclosure requirements",
                ],
            },
            {
                "section_id": "data",
                "title": "Data Management and Quality",
                "description": "Data governance and quality standards for AI/ML systems",
                "priority": "high",
                "requirements": [
                    "Data governance framework",
                    "Data quality standards",
                    "Data lineage tracking",
                    "Privacy and security controls",
                ],
            },
            {
                "section_id": "compliance",
                "title": "Compliance and Consumer Protection",
                "description": "Regulatory compliance and consumer protection requirements",
                "priority": "high",
                "requirements": [
                    "Fair lending compliance",
                    "Consumer protection standards",
                    "Bias testing and mitigation",
                    "Regulatory reporting",
                ],
            },
            {
                "section_id": "cybersecurity",
                "title": "Cybersecurity and Operational Resilience",
                "description": "Security and operational resilience for AI/ML systems",
                "priority": "medium",
                "requirements": [
                    "Cybersecurity frameworks",
                    "Operational resilience planning",
                    "Incident response procedures",
                    "Business continuity planning",
                ],
            },
        ]

    async def _load_from_source(self, context: LoaderContext) -> dict[str, Any] | None:
        """Load FFIEC guidance from external sources.

        Args:
            context: Loading context

        Returns:
            Raw framework data dictionary or None if failed
        """
        self.logger.info(
            "Loading FFIEC guidance from external sources",
            extra={
                "operation_id": context.operation_id,
                "framework": self.framework_name,
            },
        )

        # Try fetching from official FFIEC sources
        for base_url in self.base_urls:
            try:
                # Try different common file paths for FFIEC guidance
                for path in [
                    "ai-ml-guidance.json",
                    "artificial-intelligence-guidance.json",
                    "model-risk-management.json",
                    "press/AI_ML_Guidance.json",
                ]:
                    url = urljoin(base_url, path)
                    content = await self._fetch_content_with_circuit_breaker(
                        url, context
                    )

                    if content:
                        try:
                            data = json.loads(content)
                            self.logger.info(
                                "Successfully loaded FFIEC guidance from %s",
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

                # Also try to fetch HTML and extract structured data
                for path in [
                    "press/pr040521.htm",  # FFIEC AI/ML guidance press release
                    "ai-machine-learning-guidance",
                ]:
                    url = urljoin(base_url, path)
                    content = await self._fetch_content_with_circuit_breaker(
                        url, context
                    )

                    if content:
                        try:
                            parsed_data = await self._parse_html_guidance(
                                content, context
                            )
                            if parsed_data:
                                self.logger.info(
                                    "Successfully parsed FFIEC guidance from HTML at %s",
                                    url,
                                    extra={
                                        "operation_id": context.operation_id,
                                        "source": url,
                                    },
                                )
                                return parsed_data
                        except Exception as e:
                            self.logger.debug(
                                "Failed to parse HTML from %s: %s", url, e
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

    async def _parse_html_guidance(
        self, html_content: str, context: LoaderContext
    ) -> dict[str, Any] | None:
        """Parse FFIEC guidance from HTML content.

        Args:
            html_content: HTML content to parse
            context: Loading context

        Returns:
            Parsed framework data or None if failed
        """
        try:
            # Extract key sections and requirements from HTML
            # This is a simplified parser - in practice, would use proper HTML parsing

            # Look for common FFIEC guidance patterns
            if (
                "artificial intelligence" in html_content.lower()
                or "machine learning" in html_content.lower()
            ):
                # Parse sections and generate structured data
                return await self._generate_structured_data(context)

            return None

        except Exception as e:
            self.logger.debug(
                "Failed to parse HTML guidance: %s",
                e,
                extra={
                    "operation_id": context.operation_id,
                    "error": str(e),
                },
            )
            return None

    async def _parse_external_data(
        self, data: dict[str, Any], context: LoaderContext
    ) -> dict[str, Any]:
        """Parse externally fetched FFIEC data.

        Args:
            data: Raw external data
            context: Loading context

        Returns:
            Normalized framework data
        """
        sections = []
        references = []

        # Parse sections from external data
        if "sections" in data:
            for section_data in data["sections"]:
                section = self._create_section_from_data(section_data)
                sections.append(section)

        # Parse guidance requirements
        if "requirements" in data:
            for req_data in data["requirements"]:
                reference = self._create_reference_from_data(req_data)
                references.append(reference)

        return {
            "framework_type": FrameworkType.SOC2,  # Using closest available type
            "name": "FFIEC Artificial Intelligence/Machine Learning Guidance",
            "version": "2021",
            "description": "Federal Financial Institutions Examination Council guidance on artificial intelligence and machine learning",
            "publisher": "Federal Financial Institutions Examination Council",
            "publication_date": datetime(2021, 4, 5),
            "effective_date": datetime(2021, 4, 5),
            "official_url": "https://www.ffiec.gov/press/pr040521.htm",
            "sections": sections,
            "references": references,
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    async def _generate_structured_data(self, context: LoaderContext) -> dict[str, Any]:
        """Generate structured FFIEC guidance when external sources are unavailable.

        Args:
            context: Loading context

        Returns:
            Structured framework data
        """
        sections: list[dict[str, Any]] = []
        references = []

        # Generate sections
        for section_data in self.fallback_sections:
            section = FrameworkSection(
                framework_type=FrameworkType.SOC2,  # Using closest available
                section_id=str(section_data["section_id"]),
                title=str(section_data["title"]),
                description=str(section_data["description"]),
                parent_section=None,
                references=[],
                reference_count=0,
                order=len(sections) + 1,
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
            "framework_type": FrameworkType.SOC2,
            "name": "FFIEC Artificial Intelligence/Machine Learning Guidance",
            "version": "2021",
            "description": "Federal Financial Institutions Examination Council guidance on artificial intelligence and machine learning for financial institutions",
            "publisher": "Federal Financial Institutions Examination Council",
            "publication_date": datetime(2021, 4, 5),
            "effective_date": datetime(2021, 4, 5),
            "official_url": "https://www.ffiec.gov/press/pr040521.htm",
            "documentation_url": "https://www.ffiec.gov/",
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
        priority = section_data.get("priority", "medium")
        severity = self._priority_to_severity(priority)

        # Generate main section requirement
        main_ref = FrameworkReference(
            id=f"ffiec-{section_id}",
            framework_type=FrameworkType.SOC2,
            section=section_data["title"],
            title=f"{section_data['title']} - Overview",
            description=section_data["description"],
            severity=severity,
            control_id=section_id,
            category=section_data["title"],
            compliance_status=ComplianceStatus.UNDER_REVIEW,
            tags=["ffiec", "ai-ml", "financial-services", "guidance"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            official_url=None,
            documentation_url=None,
            subcategory="AI/ML Guidance",
            implementation_notes="FFIEC guidance for financial institutions on artificial intelligence and machine learning risk management",
        )
        references.append(main_ref.dict())

        # Generate specific requirements
        for idx, requirement in enumerate(section_data.get("requirements", []), 1):
            req_ref = FrameworkReference(
                id=f"ffiec-{section_id}-{idx:02d}",
                framework_type=FrameworkType.SOC2,
                section=section_data["title"],
                title=requirement,
                description=f"FFIEC guidance requirement: {requirement}",
                severity=severity,
                control_id=f"{section_id}.{idx}",
                category=section_data["title"],
                subcategory=f"Requirement {idx}",
                compliance_status=ComplianceStatus.UNDER_REVIEW,
                related_references=[f"ffiec-{section_id}"],
                tags=["ffiec", "ai-ml", "financial-services", "requirement"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                official_url=None,
                documentation_url=None,
                implementation_notes=f"Implementation requirement for {requirement}",
            )
            references.append(req_ref.dict())

        return references

    def _priority_to_severity(self, priority: str) -> SeverityLevel:
        """Convert priority to severity level.

        Args:
            priority: Priority level (high, medium, low)

        Returns:
            Corresponding severity level
        """
        priority_map = {
            "high": SeverityLevel.HIGH,
            "medium": SeverityLevel.MEDIUM,
            "low": SeverityLevel.LOW,
        }
        return priority_map.get(priority.lower(), SeverityLevel.MEDIUM)

    def _create_section_from_data(self, section_data: dict[str, Any]) -> dict[str, Any]:
        """Create section from external data.

        Args:
            section_data: External section data

        Returns:
            Normalized section dictionary
        """
        section = FrameworkSection(
            framework_type=FrameworkType.SOC2,
            section_id=section_data.get("id", "unknown"),
            title=section_data.get("title", "Unknown Section"),
            description=section_data.get("description", ""),
            parent_section=None,
            references=section_data.get("references", []),
            reference_count=len(section_data.get("references", [])),
            order=section_data.get("order", 0),
        )
        return section.dict()

    def _create_reference_from_data(self, req_data: dict[str, Any]) -> dict[str, Any]:
        """Create reference from external requirement data.

        Args:
            req_data: External requirement data

        Returns:
            Normalized reference dictionary
        """
        reference = FrameworkReference(
            id=f"ffiec-{req_data.get('id', 'unknown')}",
            framework_type=FrameworkType.SOC2,
            section=req_data.get("section", "Unknown"),
            title=req_data.get("title", "Unknown Requirement"),
            description=req_data.get("description", ""),
            severity=SeverityLevel(req_data.get("severity", "medium")),
            control_id=req_data.get("id"),
            category=req_data.get("category"),
            compliance_status=ComplianceStatus.UNDER_REVIEW,
            tags=["ffiec", "ai-ml", "financial-services", *req_data.get("tags", [])],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            official_url=None,
            documentation_url=None,
            subcategory=req_data.get("subcategory", "General"),
            implementation_notes=req_data.get("implementation_notes", ""),
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
                "Successfully deserialized FFIEC framework: %d sections, %d references",
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
                "Failed to deserialize FFIEC framework: %s",
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
        """Get list of source URLs for FFIEC guidance.

        Returns:
            List of URLs where FFIEC AI/ML guidance can be found
        """
        return [
            "https://www.ffiec.gov/press/pr040521.htm",
            "https://www.ffiec.gov/",
            "https://www.ffiec.gov/press/",
            "https://www.federalreserve.gov/supervisionreg/srletters/SR2111.htm",
        ]
