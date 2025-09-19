"""
Framework Query Engine

Advanced search and analysis engine for governance framework data.
Supports cross-framework queries, compliance analysis, and relationship mapping.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any

from .models import (
    ComplianceStatus,
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

    def _build_search_indices(self) -> None:
        """Build search indices for fast querying."""
        logger.info("Building framework search indices...")

        # Text search index
        self.text_index: dict[str, set[str]] = defaultdict(set)  # word -> reference IDs
        self.reference_index: dict[str, FrameworkReference] = {}  # reference ID -> reference
        self.section_index: dict[str, FrameworkSection] = {}  # section ID -> section

        # Tag and category indices
        self.tag_index: dict[str, set[str]] = defaultdict(set)  # tag -> reference IDs
        self.category_index: dict[str, set[str]] = defaultdict(set)  # category -> reference IDs
        self.severity_index: dict[SeverityLevel, set[str]] = defaultdict(set)  # severity -> reference IDs
        self.compliance_index: dict[ComplianceStatus, set[str]] = defaultdict(set)  # status -> reference IDs

        # Framework indices
        self.framework_reference_index: dict[FrameworkType, set[str]] = defaultdict(set)  # framework -> reference IDs
        self.framework_section_index: dict[FrameworkType, set[str]] = defaultdict(set)  # framework -> section IDs

        for framework_type, framework in self.frameworks.items():
            # Index references
            for reference in framework.references:
                ref_id = f"{framework_type}:{reference.id}"
                self.reference_index[ref_id] = reference
                self.framework_reference_index[framework_type].add(ref_id)

                # Text indexing
                text_content = f"{reference.title} {reference.description} {reference.section}"
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

        logger.info(f"Built search indices: {len(self.reference_index)} references, {len(self.section_index)} sections")

    def _tokenize_text(self, text: str) -> set[str]:
        """Tokenize text for search indexing.

        Args:
            text: Text to tokenize

        Returns:
            Set of normalized tokens
        """
        # Remove punctuation and split on whitespace
        words = re.findall(r'\b\w+\b', text.lower())

        # Filter out short words and common stop words
        stop_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'a', 'an'}
        return {word for word in words if len(word) > 2 and word not in stop_words}

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
                if (datetime.utcnow() - cached_result.query.query_text if hasattr(cached_result.query, 'query_text') else datetime.utcnow()).total_seconds() < self.cache_ttl:
                    logger.debug(f"Returning cached search result for: {query.query_text}")
                    cached_result.cache_hit = True
                    return cached_result

            # Execute search
            matching_ref_ids = await self._execute_search(query)
            matching_sec_ids = await self._execute_section_search(query)

            # Apply pagination
            total_results = len(matching_ref_ids) + len(matching_sec_ids)
            paginated_ref_ids = matching_ref_ids[query.offset:query.offset + query.limit]
            remaining_limit = query.limit - len(paginated_ref_ids)
            paginated_sec_ids = matching_sec_ids[query.offset:query.offset + remaining_limit] if remaining_limit > 0 else []

            # Build result objects
            references = [self.reference_index[ref_id] for ref_id in paginated_ref_ids]
            sections = [self.section_index[sec_id] for sec_id in paginated_sec_ids]

            # Calculate analytics
            framework_coverage = self._calculate_framework_coverage(matching_ref_ids)
            compliance_summary = self._calculate_compliance_summary(matching_ref_ids)
            severity_distribution = self._calculate_severity_distribution(matching_ref_ids)

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
                next_offset=query.offset + query.limit if total_results > query.offset + query.limit else None,
                framework_coverage=framework_coverage,
                compliance_summary=compliance_summary,
                severity_distribution=severity_distribution,
            )

            # Cache result
            self.search_cache[cache_key] = result

            logger.info(f"Search completed: {total_results} results in {search_time_ms:.2f}ms")
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
            text_matches = self._search_text(query.query_text, query.exact_match, query.case_sensitive)
            # Filter to references only
            text_matches = {ref_id for ref_id in text_matches if ref_id in self.reference_index}
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
            text_matches = self._search_text(query.query_text, query.exact_match, query.case_sensitive)
            # Filter to sections only
            text_matches = {sec_id for sec_id in text_matches if sec_id in self.section_index}
            matching_ids = matching_ids.intersection(text_matches)

        # Section filter
        if query.sections:
            section_filter = set()
            for section_name in query.sections:
                for sec_id, section in self.section_index.items():
                    if section.section_id.lower() == section_name.lower() or section.title.lower() == section_name.lower():
                        section_filter.add(sec_id)
            matching_ids = matching_ids.intersection(section_filter)

        return list(matching_ids)

    def _search_text(self, query_text: str, exact_match: bool, case_sensitive: bool) -> set[str]:
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
                text_content = f"{getattr(item, 'title', '')} {getattr(item, 'description', '')}"
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

    def _sort_results(self, matching_ids: list[str], query: FrameworkQuery) -> list[str]:
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
                    severity_order = {SeverityLevel.CRITICAL: 0, SeverityLevel.HIGH: 1, SeverityLevel.MEDIUM: 2, SeverityLevel.LOW: 3, SeverityLevel.INFO: 4}
                    return (severity_order.get(reference.severity, 5),)
                elif query.sort_by == "updated":
                    return (reference.updated_at,)
                else:  # relevance (default)
                    # Simple relevance scoring based on text matches
                    relevance_score = 0
                    if query.query_text:
                        query_words = self._tokenize_text(query.query_text)
                        text_content = f"{reference.title} {reference.description}".lower()
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

    def _calculate_framework_coverage(self, matching_ref_ids: list[str]) -> dict[FrameworkType, int]:
        """Calculate framework coverage in results.

        Args:
            matching_ref_ids: Matching reference IDs

        Returns:
            Framework coverage counts
        """
        coverage = defaultdict(int)
        for ref_id in matching_ref_ids:
            if ref_id in self.reference_index:
                reference = self.reference_index[ref_id]
                coverage[reference.framework_type] += 1
        return dict(coverage)

    def _calculate_compliance_summary(self, matching_ref_ids: list[str]) -> dict[ComplianceStatus, int]:
        """Calculate compliance status distribution.

        Args:
            matching_ref_ids: Matching reference IDs

        Returns:
            Compliance status counts
        """
        summary = defaultdict(int)
        for ref_id in matching_ref_ids:
            if ref_id in self.reference_index:
                reference = self.reference_index[ref_id]
                summary[reference.compliance_status] += 1
        return dict(summary)

    def _calculate_severity_distribution(self, matching_ref_ids: list[str]) -> dict[SeverityLevel, int]:
        """Calculate severity distribution.

        Args:
            matching_ref_ids: Matching reference IDs

        Returns:
            Severity level counts
        """
        distribution = defaultdict(int)
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
        compliance_coverage = defaultdict(int)
        for framework in self.frameworks.values():
            for reference in framework.references:
                compliance_coverage[reference.compliance_status] += 1

        compliant_count = compliance_coverage.get(ComplianceStatus.COMPLIANT, 0) + compliance_coverage.get(ComplianceStatus.PARTIAL, 0)
        compliance_percentage = (compliant_count / total_references * 100) if total_references > 0 else 0

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
