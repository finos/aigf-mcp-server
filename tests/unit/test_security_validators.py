"""
Test suite for security validation functionality.

Tests input validation, sanitization, and security checks with proper separation of concerns.
"""

import pytest

from finos_mcp.security.validators import (
    DocumentIdValidator,
    SearchQueryValidator,
    ValidationError,
    ValidationResult,
    normalize_document_id,
    normalize_search_query,
    sanitize_document_id,
    sanitize_file_path,
    sanitize_html_content,
    sanitize_search_query,
    validate_content_length,
    validate_document_id,
    validate_filename_safe,
    validate_multiple_inputs,
    validate_search_request,
)


@pytest.mark.unit
class TestValidationError:
    """Test ValidationError exception."""

    def test_validation_error_creation(self):
        """Test ValidationError can be created and raised."""
        error = ValidationError("Test validation error")
        assert str(error) == "Test validation error"
        assert error.message == "Test validation error"

        error_with_field = ValidationError("Field error", field="test_field")
        assert error_with_field.field == "test_field"

        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Custom validation message")

        assert str(exc_info.value) == "Custom validation message"


@pytest.mark.unit
class TestSchemaValidators:
    """Test Pydantic schema validators."""

    def test_search_query_validator_valid(self):
        """Test SearchQueryValidator with valid input."""
        validator = SearchQueryValidator(query="machine learning", exact_match=False)
        assert validator.query == "machine learning"
        assert validator.exact_match is False

    def test_search_query_validator_strips_whitespace(self):
        """Test SearchQueryValidator strips whitespace."""
        validator = SearchQueryValidator(query="  machine learning  ", exact_match=True)
        assert validator.query == "machine learning"

    def test_search_query_validator_rejects_empty(self):
        """Test SearchQueryValidator rejects empty queries."""
        with pytest.raises(ValueError):
            SearchQueryValidator(query="", exact_match=False)

        with pytest.raises(ValueError):
            SearchQueryValidator(query="   ", exact_match=False)

    def test_search_query_validator_rejects_too_long(self):
        """Test SearchQueryValidator rejects overly long queries."""
        long_query = "a" * 501
        with pytest.raises(ValueError):
            SearchQueryValidator(query=long_query, exact_match=False)

    def test_document_id_validator_valid(self):
        """Test DocumentIdValidator with valid input."""
        validator = DocumentIdValidator(doc_id="mi-1")
        assert validator.doc_id == "mi-1"

        validator = DocumentIdValidator(doc_id="  ri-10  ")
        assert validator.doc_id == "ri-10"

    def test_document_id_validator_rejects_invalid(self):
        """Test DocumentIdValidator rejects invalid input."""
        with pytest.raises(ValueError):
            DocumentIdValidator(doc_id="")

        with pytest.raises(ValueError):
            DocumentIdValidator(doc_id="a" * 101)  # Too long


@pytest.mark.unit
class TestSanitizationLayer:
    """Test sanitization functions using trusted libraries."""

    def test_sanitize_html_content_clean(self):
        """Test HTML sanitization with clean content."""
        result = sanitize_html_content("machine learning")
        assert result == "machine learning"

    def test_sanitize_html_content_xss(self):
        """Test HTML sanitization removes XSS attacks."""
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert('xss')",
            "<iframe src='malicious.com'></iframe>",
        ]

        for dangerous_input in dangerous_inputs:
            result = sanitize_html_content(dangerous_input)
            # Should remove all dangerous content
            assert "<script>" not in result.lower()
            assert "javascript:" not in result.lower()
            assert "<iframe>" not in result.lower()
            assert "onerror" not in result.lower()

    def test_sanitize_search_query_valid(self):
        """Test search query sanitization with valid input."""
        result = sanitize_search_query("machine learning")
        assert result == "machine learning"

    def test_sanitize_search_query_dangerous(self):
        """Test search query sanitization with dangerous input."""
        with pytest.raises(ValidationError):
            sanitize_search_query("")

        # XSS should be removed, leaving clean content
        result = sanitize_search_query("machine <script>alert(1)</script> learning")
        assert "machine" in result
        assert "learning" in result
        assert "<script>" not in result

    def test_sanitize_document_id_valid(self):
        """Test document ID sanitization with valid input."""
        result = sanitize_document_id("mi-1")
        assert result == "mi-1"

    def test_sanitize_document_id_path_traversal(self):
        """Test document ID sanitization blocks path traversal."""
        with pytest.raises(ValidationError):
            sanitize_document_id("../../../etc/passwd")

        with pytest.raises(ValidationError):
            sanitize_document_id("..\\..\\windows\\system32")

    def test_sanitize_document_id_control_chars(self):
        """Test document ID sanitization blocks control characters."""
        with pytest.raises(ValidationError):
            sanitize_document_id("mi-1\x00script")

        with pytest.raises(ValidationError):
            sanitize_document_id("mi-1\x01\x02")

    def test_sanitize_file_path_valid(self):
        """Test file path sanitization with valid paths."""
        result = sanitize_file_path("document.md")
        assert result == "document.md"

    def test_sanitize_file_path_dangerous(self):
        """Test file path sanitization with dangerous paths."""
        # pathvalidate should clean these appropriately
        result = sanitize_file_path('document<>"|?.md')
        assert result  # Should return something valid
        assert "<" not in result
        assert ">" not in result


@pytest.mark.unit
class TestNormalizationLayer:
    """Test normalization functions using specialized libraries."""

    def test_normalize_search_query_basic(self):
        """Test search query normalization."""
        result = normalize_search_query("  Machine Learning  ")
        assert result == "machine learning"

    def test_normalize_search_query_special_chars(self):
        """Test search query normalization preserves useful content."""
        result = normalize_search_query("AI/ML & Data Science!")
        assert "ai/ml" in result
        assert "data" in result
        assert "science" in result

    def test_normalize_document_id_basic(self):
        """Test document ID normalization using slugify."""
        result = normalize_document_id("Mi-1 Document")
        assert result == "mi-1-document"

    def test_normalize_document_id_special_chars(self):
        """Test document ID normalization with special characters."""
        result = normalize_document_id("Mi-1: Data & Analysis!")
        assert "mi-1" in result
        assert "data" in result
        assert "analysis" in result
        # Special chars should be converted to hyphens or removed
        assert ":" not in result
        assert "&" not in result
        assert "!" not in result


@pytest.mark.unit
class TestHighLevelValidation:
    """Test complete validation pipelines."""

    def test_validate_search_request_valid(self):
        """Test complete search request validation with valid input."""
        result = validate_search_request("machine learning", exact_match=False)
        assert result["query"] == "machine learning"
        assert result["exact_match"] is False

    def test_validate_search_request_normalization(self):
        """Test search request validation applies normalization."""
        result = validate_search_request("  MACHINE Learning  ", exact_match=False)
        assert result["query"] == "machine learning"

    def test_validate_search_request_exact_match_no_normalize(self):
        """Test exact match preserves original query."""
        result = validate_search_request("  MACHINE Learning  ", exact_match=True)
        # Should sanitize but not normalize case
        assert "MACHINE Learning" in result["query"]

    def test_validate_search_request_dangerous(self):
        """Test search request validation blocks dangerous input."""
        # This should either sanitize or reject completely
        result = validate_search_request("machine <script>alert(1)</script> learning")
        assert "machine" in result["query"]
        assert "learning" in result["query"]
        assert "<script>" not in result["query"]

    def test_validate_document_id_valid(self):
        """Test complete document ID validation."""
        result = validate_document_id("mi-1", normalize=False)
        assert result == "mi-1"

    def test_validate_document_id_with_normalization(self):
        """Test document ID validation with normalization."""
        result = validate_document_id("Mi-1 Document", normalize=True)
        assert result == "mi-1-document"

    def test_validate_document_id_dangerous(self):
        """Test document ID validation blocks dangerous input."""
        with pytest.raises(ValidationError):
            validate_document_id("../../../etc/passwd")

    def test_validate_filename_valid(self):
        """Test filename validation with valid names."""
        result = validate_filename_safe("document.md")
        assert result == "document.md"

    def test_validate_filename_dangerous(self):
        """Test filename validation with dangerous names."""
        # Should sanitize rather than reject
        result = validate_filename_safe('document<>"|?.md')
        assert result  # Should return something valid
        assert "document" in result
        assert ".md" in result

    def test_validate_content_length_valid(self):
        """Test content length validation."""
        content = "This is normal content."
        result = validate_content_length(content)
        assert result == content

    def test_validate_content_length_too_long(self):
        """Test content length validation rejects oversized content."""
        long_content = "a" * 1000001
        with pytest.raises(ValidationError) as exc_info:
            validate_content_length(long_content)

        assert "too long" in str(exc_info.value).lower()
        assert "1,000,000" in str(exc_info.value)


@pytest.mark.unit
class TestBatchValidation:
    """Test batch validation functionality."""

    def test_validate_multiple_inputs_all_valid(self):
        """Test batch validation with all valid inputs."""
        result = validate_multiple_inputs(
            query="machine learning",
            doc_id="mi-1",
            filename="document.md",
            exact_match=False,
            normalize_id=True,
        )

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert "query" in result.sanitized_values
        assert "doc_id" in result.sanitized_values
        assert "filename" in result.sanitized_values

    def test_validate_multiple_inputs_some_invalid(self):
        """Test batch validation with some invalid inputs."""
        result = validate_multiple_inputs(
            query="valid query",
            doc_id="../invalid",  # This should fail
            filename="document.md",
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        # Should still have valid results for good inputs
        assert "query" in result.sanitized_values
        assert "filename" in result.sanitized_values

    def test_validate_multiple_inputs_partial_params(self):
        """Test batch validation with only some parameters."""
        result = validate_multiple_inputs(query="machine learning")

        assert result.is_valid is True
        assert len(result.errors) == 0
        assert "query" in result.sanitized_values
        assert len(result.sanitized_values) == 2  # query + exact_match


@pytest.mark.unit
class TestValidationResult:
    """Test ValidationResult model."""

    def test_validation_result_valid(self):
        """Test ValidationResult for valid input."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            sanitized_values={"input": "clean input"},
        )

        assert result.is_valid is True
        assert result.sanitized_values == {"input": "clean input"}
        assert result.errors == []

    def test_validation_result_invalid(self):
        """Test ValidationResult for invalid input."""
        result = ValidationResult(
            is_valid=False,
            errors=["Input contains malicious content"],
            sanitized_values={},
        )

        assert result.is_valid is False
        assert result.errors == ["Input contains malicious content"]
