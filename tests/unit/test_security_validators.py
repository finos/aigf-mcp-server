"""
Test suite for security validation functionality.

Tests input validation, sanitization, and security checks.
"""

import pytest

from finos_mcp.security.validators import (
    DocumentIdValidator,
    SearchQueryValidator,
    ValidationError,
    ValidationResult,
    _is_potential_redos_pattern,
    _normalize_search_query,
    comprehensive_validation,
    sanitize_filename,
    validate_content_length,
    validate_document_id,
    validate_search_request,
)


@pytest.mark.unit
class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_creation(self):
        """Test ValidationError can be created and raised."""
        error = ValidationError("Test validation error")
        assert str(error) == "Test validation error"

        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Custom validation message")

        assert str(exc_info.value) == "Custom validation message"


@pytest.mark.unit
class TestSearchQueryValidator:
    """Test SearchQueryValidator pydantic model."""

    def test_valid_search_query(self):
        """Test valid search query validation."""
        validator = SearchQueryValidator(query="machine learning", exact_match=False)

        assert validator.query == "machine learning"
        assert validator.exact_match is False

    def test_search_query_strip_whitespace(self):
        """Test that search queries are stripped of whitespace."""
        validator = SearchQueryValidator(query="  machine learning  ", exact_match=True)

        assert validator.query == "machine learning"
        assert validator.exact_match is True

    def test_empty_search_query_fails(self):
        """Test that empty search queries are rejected."""
        with pytest.raises(ValueError):  # Pydantic will raise validation error
            SearchQueryValidator(query="", exact_match=False)

    def test_search_query_too_long_fails(self):
        """Test that overly long search queries are rejected."""
        long_query = "a" * 501  # Exceeds max length
        with pytest.raises(ValueError):
            SearchQueryValidator(query=long_query, exact_match=False)

    def test_malicious_search_query_fails(self):
        """Test that malicious search queries are rejected."""
        malicious_queries = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
        ]

        for malicious_query in malicious_queries:
            with pytest.raises(ValueError):
                SearchQueryValidator(query=malicious_query, exact_match=False)


@pytest.mark.unit
class TestDocumentIdValidator:
    """Test DocumentIdValidator pydantic model."""

    def test_valid_document_id(self):
        """Test valid document ID validation."""
        validator = DocumentIdValidator(doc_id="mi-1")
        assert validator.doc_id == "mi-1"

    def test_document_id_normalization(self):
        """Test that document IDs are normalized."""
        validator = DocumentIdValidator(doc_id="MI-1")
        assert validator.doc_id == "MI-1"  # DocumentIdValidator doesn't lowercase

    def test_document_id_with_whitespace(self):
        """Test document ID with whitespace."""
        validator = DocumentIdValidator(doc_id="  mi-1  ")
        assert validator.doc_id == "mi-1"

    def test_invalid_document_id_format(self):
        """Test invalid document ID formats."""
        invalid_ids = [
            "",  # Empty
            "../mi-1",  # Path traversal
            "mi-1\x00script",  # Null byte
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValueError):
                DocumentIdValidator(doc_id=invalid_id)


@pytest.mark.unit
class TestValidationFunctions:
    """Test standalone validation functions."""

    def test_validate_search_request_valid(self):
        """Test valid search request validation."""
        result = validate_search_request("machine learning", exact_match=False)

        assert result["query"] == "machine learning"
        assert result["exact_match"] is False

    def test_validate_search_request_invalid(self):
        """Test invalid search request validation."""
        with pytest.raises(ValidationError):
            validate_search_request("<script>alert('xss')</script>")

    def test_validate_document_id_valid(self):
        """Test valid document ID validation."""
        result = validate_document_id("mi-1")
        assert result == "mi-1"

    def test_validate_document_id_invalid(self):
        """Test invalid document ID validation."""
        with pytest.raises(ValidationError):
            validate_document_id("../../../etc/passwd")

    def test_sanitize_filename_basic(self):
        """Test basic filename sanitization."""
        result = sanitize_filename("my-document.md")
        assert result == "my-document.md"

    def test_sanitize_filename_with_dangerous_chars(self):
        """Test filename sanitization with dangerous characters."""
        result = sanitize_filename("../../../dangerous.md")
        # Should remove path traversal characters
        assert "../" not in result
        assert result == "dangerous.md"

    def test_sanitize_filename_with_spaces(self):
        """Test filename sanitization with spaces."""
        result = sanitize_filename("my document with spaces.md")
        # Spaces should be replaced with underscores or preserved based on implementation
        assert "my" in result and "document" in result

    def test_validate_content_length_valid(self):
        """Test content length validation with valid content."""
        content = "This is a normal length content."
        result = validate_content_length(content)
        assert result == content

    def test_validate_content_length_too_long(self):
        """Test content length validation with oversized content."""
        long_content = "a" * 1000001  # Exceeds default max
        with pytest.raises(ValidationError):
            validate_content_length(long_content)

    def test_validate_content_length_custom_limit(self):
        """Test content length validation with custom limit."""
        content = "This is content."
        result = validate_content_length(content, max_length=100)
        assert result == content

        # Test exceeding custom limit
        long_content = "a" * 101
        with pytest.raises(ValidationError):
            validate_content_length(long_content, max_length=100)


@pytest.mark.unit
class TestHelperFunctions:
    """Test internal helper functions."""

    def test_is_potential_redos_pattern_safe(self):
        """Test ReDoS detection with safe patterns."""
        safe_queries = [
            "machine learning",
            "simple query",
            "normal*search",
            "exact match",
        ]

        for query in safe_queries:
            result = _is_potential_redos_pattern(query)
            assert result is False

    def test_is_potential_redos_pattern_dangerous(self):
        """Test ReDoS detection with dangerous patterns."""
        dangerous_queries = [
            "(" * 10 + "a" + ")" * 10,  # Excessive nesting
            "[" * 10 + "a" + "]" * 10,  # Excessive brackets
        ]

        for query in dangerous_queries:
            result = _is_potential_redos_pattern(query)
            assert result is True

    def test_normalize_search_query_basic(self):
        """Test search query normalization."""
        result = _normalize_search_query("  Machine Learning  ")
        assert result == "machine learning"

    def test_normalize_search_query_special_chars(self):
        """Test search query normalization with special characters."""
        result = _normalize_search_query("AI/ML & Data Science!")
        # Should normalize case and handle special chars appropriately
        assert "ai" in result.lower()
        assert "ml" in result.lower()


@pytest.mark.unit
class TestValidationResult:
    """Test ValidationResult model."""

    def test_validation_result_valid(self):
        """Test ValidationResult for valid input."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            sanitized_values={"input": "clean input"},
        )

        assert result.is_valid is True
        assert result.sanitized_values == {"input": "clean input"}
        assert result.errors == []
        assert result.warnings == []

    def test_validation_result_invalid(self):
        """Test ValidationResult for invalid input."""
        result = ValidationResult(
            is_valid=False,
            errors=["Input contains malicious content"],
            warnings=["Potential security issue"],
            sanitized_values={},
        )

        assert result.is_valid is False
        assert result.errors == ["Input contains malicious content"]
        assert result.warnings == ["Potential security issue"]


@pytest.mark.unit
class TestComprehensiveValidation:
    """Test comprehensive validation function."""

    def test_comprehensive_validation_valid_input(self):
        """Test comprehensive validation with valid input."""
        result = comprehensive_validation(query="machine learning", exact_match=False)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True

    def test_comprehensive_validation_invalid_input(self):
        """Test comprehensive validation with invalid input."""
        result = comprehensive_validation(
            query="<script>alert('xss')</script>", exact_match=False
        )

        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_comprehensive_validation_document_id(self):
        """Test comprehensive validation with document ID."""
        result = comprehensive_validation(doc_id="mi-1")

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
