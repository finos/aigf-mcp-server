"""GDPR (General Data Protection Regulation) framework loader.

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

This loader fetches GDPR framework data from official EU sources
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


class GDPRLoader(BaseFrameworkLoader):
    """Loader for GDPR (General Data Protection Regulation) framework.

    This loader fetches GDPR framework data from official EU sources
    and standardized repositories following the existing ContentService patterns.
    """

    def __init__(self, framework_name: str = "gdpr") -> None:
        """Initialize GDPR loader."""
        super().__init__(framework_name)

        # GDPR official and reliable sources
        self.base_urls = [
            "https://eur-lex.europa.eu/legal-content/EN/TXT/",
            "https://gdpr.eu/",
            "https://raw.githubusercontent.com/gdpr-compliance/gdpr-framework/main/",
        ]

        # GDPR articles structure
        self.gdpr_articles = [
            {
                "article": "5",
                "title": "Principles relating to processing of personal data",
                "section": "General Principles",
                "severity": "critical",
            },
            {
                "article": "6",
                "title": "Lawfulness of processing",
                "section": "Legal Basis",
                "severity": "critical",
            },
            {
                "article": "7",
                "title": "Conditions for consent",
                "section": "Legal Basis",
                "severity": "high",
            },
            {
                "article": "9",
                "title": "Processing of special categories of personal data",
                "section": "Special Categories",
                "severity": "critical",
            },
            {
                "article": "13",
                "title": "Information to be provided where personal data are collected",
                "section": "Transparency",
                "severity": "high",
            },
            {
                "article": "14",
                "title": "Information to be provided where personal data have not been obtained",
                "section": "Transparency",
                "severity": "high",
            },
            {
                "article": "15",
                "title": "Right of access by the data subject",
                "section": "Data Subject Rights",
                "severity": "high",
            },
            {
                "article": "16",
                "title": "Right to rectification",
                "section": "Data Subject Rights",
                "severity": "medium",
            },
            {
                "article": "17",
                "title": "Right to erasure ('right to be forgotten')",
                "section": "Data Subject Rights",
                "severity": "high",
            },
            {
                "article": "18",
                "title": "Right to restriction of processing",
                "section": "Data Subject Rights",
                "severity": "medium",
            },
            {
                "article": "20",
                "title": "Right to data portability",
                "section": "Data Subject Rights",
                "severity": "medium",
            },
            {
                "article": "21",
                "title": "Right to object",
                "section": "Data Subject Rights",
                "severity": "medium",
            },
            {
                "article": "25",
                "title": "Data protection by design and by default",
                "section": "Technical and Organisational Measures",
                "severity": "critical",
            },
            {
                "article": "32",
                "title": "Security of processing",
                "section": "Technical and Organisational Measures",
                "severity": "critical",
            },
            {
                "article": "33",
                "title": "Notification of a personal data breach to the supervisory authority",
                "section": "Breach Notification",
                "severity": "critical",
            },
            {
                "article": "34",
                "title": "Communication of a personal data breach to the data subject",
                "section": "Breach Notification",
                "severity": "high",
            },
            {
                "article": "35",
                "title": "Data protection impact assessment",
                "section": "Impact Assessment",
                "severity": "high",
            },
            {
                "article": "37",
                "title": "Designation of the data protection officer",
                "section": "Data Protection Officer",
                "severity": "medium",
            },
        ]

    async def _load_from_source(self, context: LoaderContext) -> dict[str, Any] | None:
        """Load GDPR framework data from external sources.

        Args:
            context: Loading context

        Returns:
            Raw framework data dictionary or None if failed
        """
        self.logger.info(
            "Loading GDPR from external sources",
            extra={
                "operation_id": context.operation_id,
                "framework": self.framework_name,
            },
        )

        # Try fetching from official sources
        for base_url in self.base_urls:
            try:
                # Try different common file formats
                for filename in ["gdpr.json", "framework.json", "regulation.json"]:
                    url = urljoin(base_url, filename)
                    content = await self._fetch_content_with_circuit_breaker(
                        url, context
                    )

                    if content:
                        try:
                            data = json.loads(content)
                            self.logger.info(
                                "Successfully loaded GDPR from %s",
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
        """Parse externally fetched GDPR data.

        Args:
            data: Raw external data
            context: Loading context

        Returns:
            Normalized framework data
        """
        # Extract sections and references from external data
        sections = []
        references = []

        # Parse articles
        if "articles" in data:
            for article_data in data["articles"]:
                section = self._create_section_from_data(article_data)
                sections.append(section)

        # Parse requirements
        if "requirements" in data:
            for requirement_data in data["requirements"]:
                reference = self._create_reference_from_data(requirement_data)
                references.append(reference)

        return {
            "framework_type": FrameworkType.GDPR,
            "name": "General Data Protection Regulation",
            "version": "2016/679",
            "description": "EU regulation on data protection and privacy",
            "publisher": "European Union",
            "publication_date": datetime(2016, 4, 27),
            "effective_date": datetime(2018, 5, 25),
            "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
            "sections": sections,
            "references": references,
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    async def _generate_structured_data(self, context: LoaderContext) -> dict[str, Any]:
        """Generate structured GDPR data when external sources are unavailable.

        Args:
            context: Loading context

        Returns:
            Structured framework data
        """
        sections_dict: dict[str, dict[str, Any]] = {}
        references = []

        # Group articles by section
        for article_data in self.gdpr_articles:
            section_name = article_data["section"]
            if section_name not in sections_dict:
                sections_dict[section_name] = {
                    "section_id": section_name.lower().replace(" ", "_"),
                    "title": section_name,
                    "articles": [],
                }
            sections_dict[section_name]["articles"].append(article_data)

        # Generate sections
        sections = []
        for i, (section_name, section_info) in enumerate(sections_dict.items()):
            section = FrameworkSection(
                framework_type=FrameworkType.GDPR,
                section_id=str(section_info["section_id"]),
                title=str(section_info["title"]),
                description=f"GDPR {section_info['title']} requirements",
                parent_section=None,
                references=[],
                reference_count=0,
                order=i,
            )
            sections.append(section.dict())

            # Generate references for each article in this section
            section_refs = []
            for article_data in section_info["articles"]:
                article_ref = FrameworkReference(
                    id=f"gdpr-article-{article_data['article']}",
                    framework_type=FrameworkType.GDPR,
                    section=section_name,
                    title=f"Article {article_data['article']}: {article_data['title']}",
                    description=f"GDPR Article {article_data['article']} - {article_data['title']}",
                    severity=SeverityLevel(article_data["severity"]),
                    official_url=None,
                    documentation_url=None,
                    control_id=f"Article {article_data['article']}",
                    category=section_name,
                    subcategory=None,
                    compliance_status=ComplianceStatus.UNDER_REVIEW,
                    implementation_notes=None,
                    tags=["gdpr", "data-protection", "privacy", "eu-regulation"],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                section_refs.append(article_ref.dict())
                references.append(article_ref.dict())

            # Update section dict with references
            section_dict = section.dict()
            section_dict["references"] = [ref["id"] for ref in section_refs]
            section_dict["reference_count"] = len(section_refs)
            sections[i] = section_dict  # Replace the section in the list

        return {
            "framework_type": FrameworkType.GDPR,
            "name": "General Data Protection Regulation",
            "version": "2016/679",
            "description": "EU regulation on data protection and privacy in the European Union and the European Economic Area",
            "publisher": "European Union",
            "publication_date": datetime(2016, 4, 27),
            "effective_date": datetime(2018, 5, 25),
            "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
            "documentation_url": "https://gdpr.eu/",
            "sections": sections,
            "references": references,
            "total_references": len(references),
            "active_references": len(references),
            "is_active": True,
            "last_updated": datetime.utcnow(),
            "retrieved_at": datetime.utcnow(),
            "operation_id": context.operation_id,
        }

    def _create_section_from_data(self, article_data: dict[str, Any]) -> dict[str, Any]:
        """Create section from external data.

        Args:
            article_data: External article data

        Returns:
            Normalized section dictionary
        """
        section = FrameworkSection(
            framework_type=FrameworkType.GDPR,
            section_id=article_data.get("section", "unknown").lower().replace(" ", "_"),
            title=article_data.get("section", "Unknown Section"),
            description=article_data.get("description", ""),
            parent_section=None,
            references=[f"gdpr-article-{article_data.get('article', 'unknown')}"],
            reference_count=1,
            order=int(article_data.get("article", "0"))
            if article_data.get("article", "0").isdigit()
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
            id=f"gdpr-{requirement_data.get('id', 'unknown')}",
            framework_type=FrameworkType.GDPR,
            section=requirement_data.get("section", "Unknown"),
            title=requirement_data.get("title", "Unknown Requirement"),
            description=requirement_data.get("description", ""),
            severity=SeverityLevel(requirement_data.get("severity", "medium")),
            official_url=None,
            documentation_url=None,
            control_id=requirement_data.get("id"),
            category=requirement_data.get("category"),
            subcategory=requirement_data.get("subcategory"),
            compliance_status=ComplianceStatus.UNDER_REVIEW,
            implementation_notes=requirement_data.get("implementation_notes"),
            tags=["gdpr", "data-protection", *requirement_data.get("tags", [])],
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
                "Successfully deserialized GDPR framework: %d sections, %d references",
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
                "Failed to deserialize GDPR framework: %s",
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
        """Get list of source URLs for GDPR.

        Returns:
            List of URLs where GDPR data can be found
        """
        return [
            "https://eur-lex.europa.eu/eli/reg/2016/679/oj",
            "https://gdpr.eu/",
            "https://commission.europa.eu/law/law-topic/data-protection_en",
        ]
