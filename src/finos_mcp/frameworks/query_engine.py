"""
Framework Query Engine

Advanced search and analysis engine for governance framework data.
Supports cross-framework queries, compliance analysis, and relationship mapping.
"""

import csv
import json
import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime
from io import StringIO
from typing import Any

from .models import (
    ComplianceStatus,
    ExportFilter,
    ExportFormat,
    ExportRequest,
    ExportResult,
    FrameworkAnalytics,
    FrameworkQuery,
    FrameworkReference,
    FrameworkSearchResult,
    FrameworkSection,
    FrameworkType,
    GovernanceFramework,
    SeverityLevel,
)

logger = logging.getLogger(__name__)


class FrameworkQueryEngine:
    """Advanced query engine for framework data analysis."""

    def __init__(self, frameworks: dict[FrameworkType, GovernanceFramework]):
        """Initialize query engine with framework data.

        Args:
            frameworks: Loaded framework data
        """
        self.frameworks = frameworks
        self.search_cache: dict[str, FrameworkSearchResult] = {}
        self.analytics_cache: FrameworkAnalytics | None = None
        self.cache_ttl = 300  # 5 minutes

        # Build search indices
        self._build_search_indices()

        # Export tracking
        self.export_history: list[str] = []

    def _build_search_indices(self) -> None:
        """Build search indices for fast querying."""
        logger.info("Building framework search indices...")

        # Text search index
        self.text_index: dict[str, set[str]] = defaultdict(set)  # word -> reference IDs
        self.reference_index: dict[
            str, FrameworkReference
        ] = {}  # reference ID -> reference
        self.section_index: dict[str, FrameworkSection] = {}  # section ID -> section

        # Tag and category indices
        self.tag_index: dict[str, set[str]] = defaultdict(set)  # tag -> reference IDs
        self.category_index: dict[str, set[str]] = defaultdict(
            set
        )  # category -> reference IDs
        self.severity_index: dict[SeverityLevel, set[str]] = defaultdict(
            set
        )  # severity -> reference IDs
        self.compliance_index: dict[ComplianceStatus, set[str]] = defaultdict(
            set
        )  # status -> reference IDs

        # Framework indices
        self.framework_reference_index: dict[FrameworkType, set[str]] = defaultdict(
            set
        )  # framework -> reference IDs
        self.framework_section_index: dict[FrameworkType, set[str]] = defaultdict(
            set
        )  # framework -> section IDs

        for framework_type, framework in self.frameworks.items():
            # Index references
            for reference in framework.references:
                ref_id = f"{framework_type}:{reference.id}"
                self.reference_index[ref_id] = reference
                self.framework_reference_index[framework_type].add(ref_id)

                # Text indexing
                text_content = (
                    f"{reference.title} {reference.description} {reference.section}"
                )
                words = self._tokenize_text(text_content)
                for word in words:
                    self.text_index[word].add(ref_id)

                # Tag indexing
                for tag in reference.tags:
                    self.tag_index[tag.lower()].add(ref_id)

                # Category indexing
                if reference.category:
                    self.category_index[reference.category.lower()].add(ref_id)
                if reference.subcategory:
                    self.category_index[reference.subcategory.lower()].add(ref_id)

                # Attribute indexing
                self.severity_index[reference.severity].add(ref_id)
                self.compliance_index[reference.compliance_status].add(ref_id)

            # Index sections
            for section in framework.sections:
                sec_id = f"{framework_type}:{section.section_id}"
                self.section_index[sec_id] = section
                self.framework_section_index[framework_type].add(sec_id)

                # Text indexing for sections
                text_content = f"{section.title} {section.description or ''}"
                words = self._tokenize_text(text_content)
                for word in words:
                    self.text_index[word].add(sec_id)

        logger.info(
            f"Built search indices: {len(self.reference_index)} references, {len(self.section_index)} sections"
        )

    def _tokenize_text(self, text: str) -> set[str]:
        """Tokenize text for search indexing.

        Args:
            text: Text to tokenize

        Returns:
            Set of normalized tokens
        """
        # Remove punctuation and split on whitespace
        words = re.findall(r"\b\w+\b", text.lower())

        # Filter out short words and common stop words
        stop_words = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "a",
            "an",
        }
        return {word for word in words if len(word) > 2 and word not in stop_words}

    def _advanced_text_search(
        self, search_terms: list[str], exclude_terms: list[str] | None = None
    ) -> set[str]:
        """Perform advanced full-text search with include/exclude terms.

        Args:
            search_terms: Terms that must be present
            exclude_terms: Terms that must not be present

        Returns:
            Set of matching item IDs
        """
        if not search_terms:
            return set()

        exclude_terms = exclude_terms or []
        matching_ids = set()

        # Find items containing all search terms
        for term in search_terms:
            term_tokens = self._tokenize_text(term)
            term_matches = set()

            for token in term_tokens:
                term_matches.update(self.text_index.get(token, set()))

            if not matching_ids:
                matching_ids = term_matches
            else:
                matching_ids = matching_ids.intersection(term_matches)

        # Remove items containing exclude terms
        if exclude_terms and matching_ids:
            exclude_ids = set()
            for exclude_term in exclude_terms:
                exclude_tokens = self._tokenize_text(exclude_term)
                for token in exclude_tokens:
                    exclude_ids.update(self.text_index.get(token, set()))
            matching_ids = matching_ids - exclude_ids

        return matching_ids

    def _filter_by_categories(
        self, matching_ids: set[str], categories: list[str]
    ) -> set[str]:
        """Filter items by categories and subcategories.

        Args:
            matching_ids: Current matching IDs
            categories: Categories to filter by

        Returns:
            Filtered IDs
        """
        if not categories:
            return matching_ids

        category_matches = set()
        for category in categories:
            category_lower = category.lower()
            # Check both category and subcategory indices
            category_matches.update(self.category_index.get(category_lower, set()))

        return matching_ids.intersection(category_matches)

    def _filter_by_date_range(
        self,
        matching_ids: set[str],
        updated_after: datetime | None = None,
        updated_before: datetime | None = None,
    ) -> set[str]:
        """Filter items by update date range.

        Args:
            matching_ids: Current matching IDs
            updated_after: Include items updated after this date
            updated_before: Include items updated before this date

        Returns:
            Filtered IDs
        """
        if not updated_after and not updated_before:
            return matching_ids

        filtered_ids = set()
        for item_id in matching_ids:
            item = self.reference_index.get(item_id) or self.section_index.get(item_id)
            if not item:
                continue

            updated_at = getattr(item, "updated_at", None)
            if not updated_at:
                continue

            # Check date range
            if updated_after and updated_at < updated_after:
                continue
            if updated_before and updated_at > updated_before:
                continue

            filtered_ids.add(item_id)

        return filtered_ids

    async def search(self, query: FrameworkQuery) -> FrameworkSearchResult:
        """Execute framework search query.

        Args:
            query: Search query parameters

        Returns:
            Search results
        """
        start_time = datetime.utcnow()

        try:
            # Check cache
            cache_key = self._get_cache_key(query)
            if cache_key in self.search_cache:
                cached_result = self.search_cache[cache_key]
                # Simple cache without TTL for now - can be enhanced later
                logger.debug(f"Returning cached search result for: {query.query_text}")
                cached_result.cache_hit = True
                return cached_result

            # Execute search
            matching_ref_ids = await self._execute_search(query)
            matching_sec_ids = await self._execute_section_search(query)

            # Apply pagination
            total_results = len(matching_ref_ids) + len(matching_sec_ids)
            paginated_ref_ids = matching_ref_ids[
                query.offset : query.offset + query.limit
            ]
            remaining_limit = query.limit - len(paginated_ref_ids)
            paginated_sec_ids = (
                matching_sec_ids[query.offset : query.offset + remaining_limit]
                if remaining_limit > 0
                else []
            )

            # Build result objects
            references = [self.reference_index[ref_id] for ref_id in paginated_ref_ids]
            sections = [self.section_index[sec_id] for sec_id in paginated_sec_ids]

            # Calculate analytics
            framework_coverage = self._calculate_framework_coverage(matching_ref_ids)
            compliance_summary = self._calculate_compliance_summary(matching_ref_ids)
            severity_distribution = self._calculate_severity_distribution(
                matching_ref_ids
            )

            # Build search result
            search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = FrameworkSearchResult(
                query=query,
                total_results=total_results,
                returned_results=len(references) + len(sections),
                references=references,
                sections=sections,
                search_time_ms=search_time_ms,
                cache_hit=False,
                has_more=total_results > query.offset + query.limit,
                next_offset=query.offset + query.limit
                if total_results > query.offset + query.limit
                else None,
                framework_coverage=framework_coverage,
                compliance_summary=compliance_summary,
                severity_distribution=severity_distribution,
            )

            # Cache result
            self.search_cache[cache_key] = result

            logger.info(
                f"Search completed: {total_results} results in {search_time_ms:.2f}ms"
            )
            return result

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def _execute_search(self, query: FrameworkQuery) -> list[str]:
        """Execute reference search.

        Args:
            query: Search query

        Returns:
            List of matching reference IDs
        """
        matching_ids: set[str] = set()

        # Framework filter
        if query.framework_types:
            framework_ids = set()
            for framework_type in query.framework_types:
                framework_ids.update(self.framework_reference_index[framework_type])
            matching_ids = framework_ids
        else:
            # Start with all references
            matching_ids = set(self.reference_index.keys())

        # Text search
        if query.query_text:
            text_matches = self._search_text(
                query.query_text, query.exact_match, query.case_sensitive
            )
            # Filter to references only
            text_matches = {
                ref_id for ref_id in text_matches if ref_id in self.reference_index
            }
            matching_ids = matching_ids.intersection(text_matches)

        # Apply filters
        matching_ids = self._apply_filters(matching_ids, query)

        # Sort results
        sorted_ids = self._sort_results(list(matching_ids), query)

        return sorted_ids

    async def _execute_section_search(self, query: FrameworkQuery) -> list[str]:
        """Execute section search.

        Args:
            query: Search query

        Returns:
            List of matching section IDs
        """
        matching_ids: set[str] = set()

        # Framework filter
        if query.framework_types:
            framework_ids = set()
            for framework_type in query.framework_types:
                framework_ids.update(self.framework_section_index[framework_type])
            matching_ids = framework_ids
        else:
            # Start with all sections
            matching_ids = set(self.section_index.keys())

        # Text search
        if query.query_text:
            text_matches = self._search_text(
                query.query_text, query.exact_match, query.case_sensitive
            )
            # Filter to sections only
            text_matches = {
                sec_id for sec_id in text_matches if sec_id in self.section_index
            }
            matching_ids = matching_ids.intersection(text_matches)

        # Section filter
        if query.sections:
            section_filter = set()
            for section_name in query.sections:
                for sec_id, section in self.section_index.items():
                    if (
                        section.section_id.lower() == section_name.lower()
                        or section.title.lower() == section_name.lower()
                    ):
                        section_filter.add(sec_id)
            matching_ids = matching_ids.intersection(section_filter)

        return list(matching_ids)

    def _search_text(
        self, query_text: str, exact_match: bool, case_sensitive: bool
    ) -> set[str]:
        """Perform text search.

        Args:
            query_text: Search text
            exact_match: Whether to perform exact matching
            case_sensitive: Whether search is case sensitive

        Returns:
            Set of matching IDs
        """
        if not case_sensitive:
            query_text = query_text.lower()

        if exact_match:
            # Exact phrase matching
            matching_ids = set()
            for item_id, item in {**self.reference_index, **self.section_index}.items():
                text_content = (
                    f"{getattr(item, 'title', '')} {getattr(item, 'description', '')}"
                )
                if not case_sensitive:
                    text_content = text_content.lower()
                if query_text in text_content:
                    matching_ids.add(item_id)
            return matching_ids
        else:
            # Token-based search
            query_words = self._tokenize_text(query_text)
            if not query_words:
                return set()

            # Find items matching any query word
            matching_ids = set()
            for word in query_words:
                matching_ids.update(self.text_index.get(word, set()))

            return matching_ids

    def _apply_filters(self, matching_ids: set[str], query: FrameworkQuery) -> set[str]:
        """Apply search filters.

        Args:
            matching_ids: Current matching IDs
            query: Search query

        Returns:
            Filtered IDs
        """
        # Severity filter
        if query.severity_levels:
            severity_matches = set()
            for severity in query.severity_levels:
                severity_matches.update(self.severity_index[severity])
            matching_ids = matching_ids.intersection(severity_matches)

        # Compliance status filter
        if query.compliance_status:
            compliance_matches = set()
            for status in query.compliance_status:
                compliance_matches.update(self.compliance_index[status])
            matching_ids = matching_ids.intersection(compliance_matches)

        # Tag filter
        if query.tags:
            tag_matches = set()
            for tag in query.tags:
                tag_matches.update(self.tag_index.get(tag.lower(), set()))
            matching_ids = matching_ids.intersection(tag_matches)

        # Section filter (for references)
        if query.sections:
            section_matches = set()
            for ref_id in matching_ids:
                if ref_id in self.reference_index:
                    reference = self.reference_index[ref_id]
                    if reference.section.lower() in [s.lower() for s in query.sections]:
                        section_matches.add(ref_id)
            matching_ids = matching_ids.intersection(section_matches)

        return matching_ids

    def _sort_results(
        self, matching_ids: list[str], query: FrameworkQuery
    ) -> list[str]:
        """Sort search results.

        Args:
            matching_ids: Matching IDs to sort
            query: Search query

        Returns:
            Sorted IDs
        """

        def sort_key(item_id: str) -> tuple[Any, ...]:
            if item_id in self.reference_index:
                reference = self.reference_index[item_id]
                if query.sort_by == "title":
                    return (reference.title,)
                elif query.sort_by == "severity":
                    severity_order = {
                        SeverityLevel.CRITICAL: 0,
                        SeverityLevel.HIGH: 1,
                        SeverityLevel.MEDIUM: 2,
                        SeverityLevel.LOW: 3,
                        SeverityLevel.INFO: 4,
                    }
                    return (severity_order.get(reference.severity, 5),)
                elif query.sort_by == "updated":
                    return (reference.updated_at,)
                else:  # relevance (default)
                    # Simple relevance scoring based on text matches
                    relevance_score = 0
                    if query.query_text:
                        query_words = self._tokenize_text(query.query_text)
                        text_content = (
                            f"{reference.title} {reference.description}".lower()
                        )
                        for word in query_words:
                            relevance_score += text_content.count(word)
                    return (-relevance_score,)  # Negative for descending order
            else:
                # Section sorting
                section = self.section_index[item_id]
                if query.sort_by == "title":
                    return (section.title,)
                else:
                    return (section.order,)

        reverse = query.sort_order == "desc"
        return sorted(matching_ids, key=sort_key, reverse=reverse)

    def _calculate_framework_coverage(
        self, matching_ref_ids: list[str]
    ) -> dict[FrameworkType, int]:
        """Calculate framework coverage in results.

        Args:
            matching_ref_ids: Matching reference IDs

        Returns:
            Framework coverage counts
        """
        coverage: dict[FrameworkType, int] = defaultdict(int)
        for ref_id in matching_ref_ids:
            if ref_id in self.reference_index:
                reference = self.reference_index[ref_id]
                coverage[reference.framework_type] += 1
        return dict(coverage)

    def _calculate_compliance_summary(
        self, matching_ref_ids: list[str]
    ) -> dict[ComplianceStatus, int]:
        """Calculate compliance status distribution.

        Args:
            matching_ref_ids: Matching reference IDs

        Returns:
            Compliance status counts
        """
        summary: dict[ComplianceStatus, int] = defaultdict(int)
        for ref_id in matching_ref_ids:
            if ref_id in self.reference_index:
                reference = self.reference_index[ref_id]
                summary[reference.compliance_status] += 1
        return dict(summary)

    def _calculate_severity_distribution(
        self, matching_ref_ids: list[str]
    ) -> dict[SeverityLevel, int]:
        """Calculate severity distribution.

        Args:
            matching_ref_ids: Matching reference IDs

        Returns:
            Severity level counts
        """
        distribution: dict[SeverityLevel, int] = defaultdict(int)
        for ref_id in matching_ref_ids:
            if ref_id in self.reference_index:
                reference = self.reference_index[ref_id]
                distribution[reference.severity] += 1
        return dict(distribution)

    def _get_cache_key(self, query: FrameworkQuery) -> str:
        """Generate cache key for query.

        Args:
            query: Search query

        Returns:
            Cache key string
        """
        import hashlib

        query_str = f"{query.query_text}:{sorted(query.framework_types)}:{sorted(query.sections)}:{sorted(query.tags)}:{query.exact_match}:{query.case_sensitive}"
        return hashlib.sha256(query_str.encode()).hexdigest()

    async def get_analytics(self) -> FrameworkAnalytics:
        """Get framework analytics.

        Returns:
            Analytics data
        """
        if self.analytics_cache:
            return self.analytics_cache

        logger.info("Calculating framework analytics...")

        # Overall statistics
        total_frameworks = len(self.frameworks)
        total_references = sum(len(f.references) for f in self.frameworks.values())
        total_sections = sum(len(f.sections) for f in self.frameworks.values())

        # Framework breakdown
        framework_stats = {}
        for framework_type, framework in self.frameworks.items():
            framework_stats[framework_type] = {
                "references": len(framework.references),
                "sections": len(framework.sections),
                "active_references": framework.active_references,
                "last_updated": framework.last_updated.isoformat(),
            }

        # Compliance metrics
        compliance_coverage: dict[ComplianceStatus, int] = defaultdict(int)
        for framework in self.frameworks.values():
            for reference in framework.references:
                compliance_coverage[reference.compliance_status] += 1

        compliant_count = compliance_coverage.get(
            ComplianceStatus.COMPLIANT, 0
        ) + compliance_coverage.get(ComplianceStatus.PARTIAL, 0)
        compliance_percentage = (
            (compliant_count / total_references * 100) if total_references > 0 else 0
        )

        # Build analytics
        analytics = FrameworkAnalytics(
            total_frameworks=total_frameworks,
            total_references=total_references,
            total_sections=total_sections,
            framework_stats=framework_stats,
            compliance_coverage=dict(compliance_coverage),
            compliance_percentage=compliance_percentage,
        )

        self.analytics_cache = analytics
        return analytics

    def clear_cache(self) -> None:
        """Clear query cache."""
        self.search_cache.clear()
        self.analytics_cache = None
        logger.info("Query cache cleared")

    async def advanced_search(
        self, export_filter: ExportFilter
    ) -> FrameworkSearchResult:
        """Execute advanced search with enhanced filtering capabilities.

        Args:
            export_filter: Advanced filtering criteria

        Returns:
            Search results
        """
        start_time = datetime.utcnow()

        try:
            # Start with all items or filter by frameworks
            if export_filter.framework_types:
                matching_ref_ids = set()
                matching_sec_ids = set()
                for framework_type in export_filter.framework_types:
                    matching_ref_ids.update(
                        self.framework_reference_index[framework_type]
                    )
                    matching_sec_ids.update(
                        self.framework_section_index[framework_type]
                    )
            else:
                matching_ref_ids = set(self.reference_index.keys())
                matching_sec_ids = set(self.section_index.keys())

            # Advanced text search
            if export_filter.search_terms:
                text_matches = self._advanced_text_search(
                    export_filter.search_terms, export_filter.exclude_terms
                )
                matching_ref_ids = matching_ref_ids.intersection(
                    {id for id in text_matches if id in self.reference_index}
                )
                matching_sec_ids = matching_sec_ids.intersection(
                    {id for id in text_matches if id in self.section_index}
                )

            # Category filtering
            if export_filter.categories:
                matching_ref_ids = self._filter_by_categories(
                    matching_ref_ids, export_filter.categories
                )

            # Apply additional filters for references
            if export_filter.severity_levels:
                severity_matches = set()
                for severity in export_filter.severity_levels:
                    severity_matches.update(self.severity_index[severity])
                matching_ref_ids = matching_ref_ids.intersection(severity_matches)

            if export_filter.compliance_status:
                compliance_matches = set()
                for status in export_filter.compliance_status:
                    compliance_matches.update(self.compliance_index[status])
                matching_ref_ids = matching_ref_ids.intersection(compliance_matches)

            if export_filter.tags:
                tag_matches = set()
                for tag in export_filter.tags:
                    tag_matches.update(self.tag_index.get(tag.lower(), set()))
                matching_ref_ids = matching_ref_ids.intersection(tag_matches)

            if export_filter.sections:
                section_matches = set()
                for ref_id in matching_ref_ids:
                    if ref_id in self.reference_index:
                        reference = self.reference_index[ref_id]
                        if reference.section.lower() in [
                            s.lower() for s in export_filter.sections
                        ]:
                            section_matches.add(ref_id)
                matching_ref_ids = matching_ref_ids.intersection(section_matches)

            # Date filtering
            if export_filter.updated_after or export_filter.updated_before:
                matching_ref_ids = self._filter_by_date_range(
                    matching_ref_ids,
                    export_filter.updated_after,
                    export_filter.updated_before,
                )
                matching_sec_ids = self._filter_by_date_range(
                    matching_sec_ids,
                    export_filter.updated_after,
                    export_filter.updated_before,
                )

            # Build result objects
            references = [self.reference_index[ref_id] for ref_id in matching_ref_ids]
            sections = [self.section_index[sec_id] for sec_id in matching_sec_ids]

            # Calculate analytics
            framework_coverage = self._calculate_framework_coverage(
                list(matching_ref_ids)
            )
            compliance_summary = self._calculate_compliance_summary(
                list(matching_ref_ids)
            )
            severity_distribution = self._calculate_severity_distribution(
                list(matching_ref_ids)
            )

            # Build search result
            search_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            result = FrameworkSearchResult(
                query=FrameworkQuery(query_text="advanced_search"),
                total_results=len(references) + len(sections),
                returned_results=len(references) + len(sections),
                references=references,
                sections=sections,
                search_time_ms=search_time_ms,
                cache_hit=False,
                has_more=False,
                framework_coverage=framework_coverage,
                compliance_summary=compliance_summary,
                severity_distribution=severity_distribution,
            )

            logger.info(
                f"Advanced search completed: {result.total_results} results in {search_time_ms:.2f}ms"
            )
            return result

        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            raise

    async def export_data(self, export_request: ExportRequest) -> ExportResult:
        """Export framework data in specified format.

        Args:
            export_request: Export configuration

        Returns:
            Export result with content
        """
        start_time = datetime.utcnow()
        export_id = str(uuid.uuid4())

        try:
            logger.info(
                f"Starting export {export_id} in {export_request.format.value} format"
            )

            # Get filtered data using advanced search
            search_result = await self.advanced_search(export_request.filters)

            # Generate export content
            if export_request.format == ExportFormat.JSON:
                content = self._export_json(search_result, export_request)
            elif export_request.format == ExportFormat.CSV:
                content = self._export_csv(search_result, export_request)
            elif export_request.format == ExportFormat.MARKDOWN:
                content = self._export_markdown(search_result, export_request)
            else:
                raise ValueError(f"Unsupported export format: {export_request.format}")

            # Calculate statistics
            export_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            content_size = len(content.encode("utf-8"))

            # Validate content
            is_valid, validation_errors = self._validate_export_content(
                content, export_request.format
            )

            # Create export result
            result = ExportResult(
                export_id=export_id,
                request=export_request,
                content=content,
                content_size=content_size,
                total_items=search_result.total_results,
                total_frameworks=len(search_result.framework_coverage),
                total_references=len(search_result.references),
                total_sections=len(search_result.sections),
                export_time_ms=export_time_ms,
                is_valid=is_valid,
                validation_errors=validation_errors,
            )

            # Track export
            self.export_history.append(export_id)
            if len(self.export_history) > 100:  # Keep last 100 exports
                self.export_history = self.export_history[-100:]

            logger.info(
                f"Export {export_id} completed: {content_size} bytes in {export_time_ms:.2f}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Export {export_id} failed: {e}")
            raise

    def _export_json(
        self, search_result: FrameworkSearchResult, export_request: ExportRequest
    ) -> str:
        """Export search results as JSON.

        Args:
            search_result: Search results to export
            export_request: Export configuration

        Returns:
            JSON content
        """
        export_data = {
            "metadata": {
                "export_timestamp": datetime.utcnow().isoformat(),
                "total_results": search_result.total_results,
                "frameworks_included": len(search_result.framework_coverage),
                "search_time_ms": search_result.search_time_ms,
            }
        }

        if export_request.include_summary:
            export_data["summary"] = {
                "framework_coverage": {
                    ft.value: count
                    for ft, count in search_result.framework_coverage.items()
                },
                "compliance_summary": {
                    cs.value: count
                    for cs, count in search_result.compliance_summary.items()
                },
                "severity_distribution": {
                    sl.value: count
                    for sl, count in search_result.severity_distribution.items()
                },
            }

        if export_request.include_analytics:
            analytics = self.analytics_cache
            if analytics:
                export_data["analytics"] = {
                    "total_frameworks": analytics.total_frameworks,
                    "total_references": analytics.total_references,
                    "compliance_percentage": analytics.compliance_percentage,
                }

        # Export references
        export_data["references"] = []
        for ref in search_result.references:
            ref_data = {
                "id": ref.id,
                "framework_type": ref.framework_type.value,
                "section": ref.section,
                "title": ref.title,
                "severity": ref.severity.value,
                "compliance_status": ref.compliance_status.value,
            }

            if export_request.filters.include_descriptions:
                ref_data["description"] = ref.description

            if export_request.filters.include_urls:
                if ref.official_url:
                    ref_data["official_url"] = str(ref.official_url)
                if ref.documentation_url:
                    ref_data["documentation_url"] = str(ref.documentation_url)

            if export_request.filters.include_metadata:
                ref_data.update(
                    {
                        "category": ref.category,
                        "subcategory": ref.subcategory,
                        "tags": ref.tags,
                        "created_at": ref.created_at.isoformat(),
                        "updated_at": ref.updated_at.isoformat(),
                    }
                )

            export_data["references"].append(ref_data)

        # Export sections
        export_data["sections"] = []
        for section in search_result.sections:
            section_data = {
                "section_id": section.section_id,
                "framework_type": section.framework_type.value,
                "title": section.title,
                "reference_count": section.reference_count,
                "order": section.order,
            }

            if export_request.filters.include_descriptions and section.description:
                section_data["description"] = section.description

            export_data["sections"].append(section_data)

        return json.dumps(export_data, indent=2, ensure_ascii=False)

    def _export_csv(
        self, search_result: FrameworkSearchResult, export_request: ExportRequest
    ) -> str:
        """Export search results as CSV.

        Args:
            search_result: Search results to export
            export_request: Export configuration

        Returns:
            CSV content
        """
        output = StringIO()
        writer = csv.writer(output, delimiter=export_request.csv_delimiter)

        # Define headers
        headers = [
            "type",
            "id",
            "framework_type",
            "title",
            "section",
            "severity",
            "compliance_status",
        ]

        if export_request.filters.include_descriptions:
            headers.append("description")

        if export_request.filters.include_urls:
            headers.extend(["official_url", "documentation_url"])

        if export_request.filters.include_metadata:
            headers.extend(
                ["category", "subcategory", "tags", "created_at", "updated_at"]
            )

        # Write headers
        if export_request.csv_include_headers:
            writer.writerow(headers)

        # Write references
        for ref in search_result.references:
            row = [
                "reference",
                ref.id,
                ref.framework_type.value,
                ref.title,
                ref.section,
                ref.severity.value,
                ref.compliance_status.value,
            ]

            if export_request.filters.include_descriptions:
                row.append(ref.description)

            if export_request.filters.include_urls:
                row.extend(
                    [
                        str(ref.official_url) if ref.official_url else "",
                        str(ref.documentation_url) if ref.documentation_url else "",
                    ]
                )

            if export_request.filters.include_metadata:
                row.extend(
                    [
                        ref.category or "",
                        ref.subcategory or "",
                        ";".join(ref.tags),
                        ref.created_at.isoformat(),
                        ref.updated_at.isoformat(),
                    ]
                )

            writer.writerow(row)

        # Write sections
        for section in search_result.sections:
            row = [
                "section",
                section.section_id,
                section.framework_type.value,
                section.title,
                "",
                "",
                "",  # Empty for section-only fields
            ]

            if export_request.filters.include_descriptions:
                row.append(section.description or "")

            if export_request.filters.include_urls:
                row.extend(["", ""])  # No URLs for sections

            if export_request.filters.include_metadata:
                row.extend(
                    [
                        "",
                        "",  # No category/subcategory for sections
                        "",  # No tags for sections
                        "",  # No created_at for sections
                        "",  # No updated_at for sections
                    ]
                )

            writer.writerow(row)

        return output.getvalue()

    def _export_markdown(
        self, search_result: FrameworkSearchResult, export_request: ExportRequest
    ) -> str:
        """Export search results as Markdown.

        Args:
            search_result: Search results to export
            export_request: Export configuration

        Returns:
            Markdown content
        """
        lines = []

        # Title and metadata
        lines.extend(
            [
                "# Framework Export Report",
                "",
                f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"**Total Results:** {search_result.total_results}",
                f"**Frameworks:** {len(search_result.framework_coverage)}",
                f"**Search Time:** {search_result.search_time_ms:.1f}ms",
                "",
            ]
        )

        # Table of contents
        if export_request.markdown_include_toc:
            lines.extend(
                [
                    "## Table of Contents",
                    "",
                    "- [Summary](#summary)",
                    "- [Framework References](#framework-references)",
                    "- [Framework Sections](#framework-sections)",
                    "",
                ]
            )

        # Summary
        if export_request.include_summary:
            lines.extend(
                [
                    "## Summary",
                    "",
                    "### Framework Coverage",
                    "",
                ]
            )

            for framework_type, count in search_result.framework_coverage.items():
                framework_name = self.frameworks[framework_type].name
                lines.append(f"- **{framework_name}:** {count} items")

            lines.extend(
                [
                    "",
                    "### Compliance Summary",
                    "",
                ]
            )

            for status, count in search_result.compliance_summary.items():
                lines.append(f"- **{status.value.title()}:** {count} items")

            lines.extend(
                [
                    "",
                    "### Severity Distribution",
                    "",
                ]
            )

            for severity, count in search_result.severity_distribution.items():
                lines.append(f"- **{severity.value.title()}:** {count} items")

            lines.append("")

        # Framework References
        if search_result.references:
            lines.extend(
                [
                    "## Framework References",
                    "",
                ]
            )

            for ref in search_result.references:
                framework_name = self.frameworks[ref.framework_type].name
                lines.extend(
                    [
                        f"### {ref.title}",
                        "",
                        f"**Framework:** {framework_name}",
                        f"**Section:** {ref.section}",
                        f"**Severity:** {ref.severity.value.title()}",
                        f"**Compliance Status:** {ref.compliance_status.value.title()}",
                    ]
                )

                if export_request.filters.include_descriptions:
                    lines.extend(
                        [
                            "",
                            f"**Description:** {ref.description}",
                        ]
                    )

                if export_request.filters.include_urls and ref.official_url:
                    if export_request.markdown_include_links:
                        lines.append(
                            f"**URL:** [{ref.official_url}]({ref.official_url})"
                        )
                    else:
                        lines.append(f"**URL:** {ref.official_url}")

                if export_request.filters.include_metadata:
                    if ref.category:
                        lines.append(f"**Category:** {ref.category}")
                    if ref.subcategory:
                        lines.append(f"**Subcategory:** {ref.subcategory}")
                    if ref.tags:
                        lines.append(f"**Tags:** {', '.join(ref.tags)}")

                lines.extend(["", "---", ""])

        # Framework Sections
        if search_result.sections:
            lines.extend(
                [
                    "## Framework Sections",
                    "",
                ]
            )

            for section in search_result.sections:
                framework_name = self.frameworks[section.framework_type].name
                lines.extend(
                    [
                        f"### {section.title}",
                        "",
                        f"**Framework:** {framework_name}",
                        f"**Section ID:** {section.section_id}",
                        f"**References:** {section.reference_count}",
                    ]
                )

                if export_request.filters.include_descriptions and section.description:
                    lines.extend(
                        [
                            "",
                            f"**Description:** {section.description}",
                        ]
                    )

                lines.extend(["", "---", ""])

        return "\n".join(lines)

    def _validate_export_content(
        self, content: str, format: ExportFormat
    ) -> tuple[bool, list[str]]:
        """Validate exported content.

        Args:
            content: Content to validate
            format: Export format

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        if not content:
            errors.append("Export content is empty")
            return False, errors

        if format == ExportFormat.JSON:
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid JSON: {e}")

        elif format == ExportFormat.CSV:
            try:
                # Try to parse CSV
                csv.reader(StringIO(content))
            except Exception as e:
                errors.append(f"Invalid CSV: {e}")

        # Check content size
        content_size = len(content.encode("utf-8"))
        if content_size > 100 * 1024 * 1024:  # 100MB limit
            errors.append(f"Export content too large: {content_size} bytes")

        return len(errors) == 0, errors
