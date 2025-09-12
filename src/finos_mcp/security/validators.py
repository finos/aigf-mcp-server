"""Input validation utilities for FINOS MCP Server.

Provides clean separation of concerns:
- Validation: Schema, type, and length checks using Pydantic
- Sanitization: XSS/injection prevention using trusted libraries
- Normalization: Consistent ID/slug generation

Security Strategy:
- pathvalidate: Filename and path validation
- bleach: XSS/HTML sanitization
- python-slugify: Safe ID normalization
- Pydantic: Schema validation and type checking
"""

from typing import Any

import bleach
from pathvalidate import sanitize_filename
from pydantic import BaseModel, Field, field_validator
from slugify import slugify

from ..logging import get_logger

logger = get_logger("validators")


class ValidationError(ValueError):
    """Custom exception for validation errors with user-friendly messages."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(message)


# =============================================================================
# VALIDATION LAYER - Schema, Type, Length Checks
# =============================================================================


class SearchQueryValidator(BaseModel):
    """Schema validation for search queries.

    Handles: type checking, length limits, required fields.
    Does NOT handle: sanitization, normalization, or business logic.
    """

    query: str = Field(..., min_length=1, max_length=500)
    exact_match: bool = Field(default=False)

    @field_validator("query")
    @classmethod
    def validate_query_schema(cls, v: str) -> str:
        """Basic schema validation only."""
        if not v or not v.strip():
            raise ValueError("Search query cannot be empty")

        # Length validation (Pydantic handles min/max, but we add context)
        query = v.strip()
        if len(query) > 500:
            raise ValueError("Search query exceeds 500 character limit")

        return query


class DocumentIdValidator(BaseModel):
    """Schema validation for document IDs.

    Handles: type checking, length limits, basic format.
    Does NOT handle: sanitization or complex business rules.
    """

    doc_id: str = Field(..., min_length=1, max_length=100)

    @field_validator("doc_id")
    @classmethod
    def validate_id_schema(cls, v: str) -> str:
        """Basic schema validation only."""
        if not v or not v.strip():
            raise ValueError("Document ID cannot be empty")

        doc_id = v.strip()
        if len(doc_id) > 100:
            raise ValueError("Document ID exceeds 100 character limit")

        return doc_id


# =============================================================================
# SANITIZATION LAYER - Security-focused cleaning using trusted libraries
# =============================================================================


def sanitize_html_content(content: str) -> str:
    """Sanitize content for XSS/injection attacks using bleach.

    Args:
        content: Raw content that might contain HTML/scripts

    Returns:
        Sanitized content safe for processing
    """
    if not content:
        return ""

    # Use bleach with strict settings - no HTML allowed
    sanitized = bleach.clean(
        content,
        tags=[],  # No HTML tags allowed
        attributes={},  # No attributes allowed
        strip=True,  # Remove tags completely
        strip_comments=True,
    )

    # Remove javascript: and other dangerous protocols
    if "javascript:" in sanitized.lower():
        sanitized = sanitized.replace("javascript:", "").replace("JAVASCRIPT:", "")

    return sanitized.strip()


def sanitize_search_query(query: str) -> str:
    """Sanitize search query for security.

    Args:
        query: Raw search query

    Returns:
        Sanitized query safe for processing

    Raises:
        ValidationError: If query becomes empty after sanitization
    """
    if not query:
        raise ValidationError("Search query cannot be empty")

    # First pass: HTML/XSS sanitization
    sanitized = sanitize_html_content(query)

    if not sanitized.strip():
        raise ValidationError("Search query contains only invalid content")

    return sanitized


def sanitize_document_id(doc_id: str) -> str:
    """Sanitize document ID for security.

    Args:
        doc_id: Raw document ID

    Returns:
        Sanitized ID safe for processing

    Raises:
        ValidationError: If ID becomes invalid after sanitization
    """
    if not doc_id:
        raise ValidationError("Document ID cannot be empty")

    # Check for control characters (excluding tab) BEFORE sanitization
    if any(ord(c) < 32 and c != "\t" for c in doc_id):
        raise ValidationError("Document ID contains invalid control characters")

    # Remove any HTML/script content
    sanitized = sanitize_html_content(doc_id)

    # Check for path traversal attempts
    if (
        "../" in sanitized
        or "..\\" in sanitized
        or "/" in sanitized
        or "\\" in sanitized
    ):
        raise ValidationError("Document ID contains invalid path characters")

    if not sanitized.strip():
        raise ValidationError("Document ID contains only invalid content")

    return sanitized.strip()


def sanitize_file_path(filepath: str) -> str:
    """Sanitize file path using pathvalidate.

    Args:
        filepath: Raw file path

    Returns:
        Sanitized path safe for file operations

    Raises:
        ValidationError: If path is invalid or becomes empty
    """
    if not filepath:
        raise ValidationError("File path cannot be empty")

    try:
        # Use pathvalidate for comprehensive path sanitization
        # Replace invalid chars with underscores instead of removing them
        sanitized = sanitize_filename(filepath, replacement_text="_")

        if not sanitized.strip():
            raise ValidationError("File path contains only invalid characters")

        # Basic validation - avoid recursive validation calls
        if len(sanitized) > 255:
            raise ValidationError("File path too long")

        return sanitized.strip()

    except Exception as e:
        # Avoid infinite recursion by being specific about the error
        if "Invalid file path" in str(e):
            raise e  # Re-raise if it's already our ValidationError
        raise ValidationError(f"Invalid file path: {e!s}") from e


# =============================================================================
# NORMALIZATION LAYER - Consistent formatting using specialized libraries
# =============================================================================


def normalize_search_query(query: str) -> str:
    """Normalize search query for consistent matching.

    Args:
        query: Sanitized search query

    Returns:
        Normalized query for better search results
    """
    if not query:
        return ""

    # Basic whitespace normalization
    normalized = " ".join(query.split())

    # Convert to lowercase for case-insensitive matching
    normalized = normalized.lower()

    return normalized


def normalize_document_id(doc_id: str) -> str:
    """Normalize document ID to consistent format using slugify.

    Args:
        doc_id: Sanitized document ID

    Returns:
        Normalized ID in consistent format
    """
    if not doc_id:
        return ""

    # Use python-slugify for safe, consistent ID generation
    normalized = slugify(
        doc_id, lowercase=True, max_length=100, word_boundary=True, separator="-"
    )

    return normalized


# =============================================================================
# HIGH-LEVEL VALIDATION FUNCTIONS - Clean interfaces for application use
# =============================================================================


def validate_search_request(query: str, exact_match: bool = False) -> dict[str, Any]:
    """Complete validation pipeline for search requests.

    Args:
        query: Raw search query
        exact_match: Whether exact matching is requested

    Returns:
        Dictionary with validated and normalized parameters

    Raises:
        ValidationError: If validation fails at any step
    """
    try:
        # Step 1: Schema validation
        validator = SearchQueryValidator(query=query, exact_match=exact_match)

        # Step 2: Security sanitization
        sanitized_query = sanitize_search_query(validator.query)

        # Step 3: Normalization (only if not exact match)
        if exact_match:
            final_query = sanitized_query
        else:
            final_query = normalize_search_query(sanitized_query)

        return {"query": final_query, "exact_match": validator.exact_match}

    except ValueError as e:
        # Convert Pydantic errors to our ValidationError
        raise ValidationError(str(e)) from e


def validate_document_id(doc_id: str, normalize: bool = True) -> str:
    """Complete validation pipeline for document IDs.

    Args:
        doc_id: Raw document ID
        normalize: Whether to normalize the ID

    Returns:
        Validated and optionally normalized document ID

    Raises:
        ValidationError: If validation fails at any step
    """
    try:
        # Step 1: Schema validation
        validator = DocumentIdValidator(doc_id=doc_id)

        # Step 2: Security sanitization
        sanitized_id = sanitize_document_id(validator.doc_id)

        # Step 3: Optional normalization
        if normalize:
            final_id = normalize_document_id(sanitized_id)
            if not final_id:  # slugify might return empty for some inputs
                final_id = sanitized_id  # fallback to sanitized version
        else:
            final_id = sanitized_id

        return final_id

    except ValueError as e:
        # Convert Pydantic errors to our ValidationError
        raise ValidationError(str(e)) from e


def validate_filename_safe(filename: str) -> str:
    """Complete validation pipeline for filenames.

    Args:
        filename: Raw filename

    Returns:
        Validated and sanitized filename

    Raises:
        ValidationError: If validation fails
    """
    if not filename or not filename.strip():
        raise ValidationError("Filename cannot be empty")

    # Use pathvalidate for comprehensive filename validation
    sanitized = sanitize_file_path(filename.strip())

    if len(sanitized) > 255:
        raise ValidationError("Filename too long (maximum 255 characters)")

    return sanitized


def validate_content_length(content: str, max_length: int = 1000000) -> str:
    """Validate content length to prevent memory issues.

    Args:
        content: Content to validate
        max_length: Maximum allowed length in characters

    Returns:
        Validated content

    Raises:
        ValidationError: If content exceeds length limit
    """
    if len(content) > max_length:
        raise ValidationError(
            f"Content too long (maximum {max_length:,} characters, got {len(content):,})"
        )

    return content


# =============================================================================
# BATCH VALIDATION - For multiple parameters
# =============================================================================


class ValidationResult(BaseModel):
    """Result of comprehensive validation."""

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    sanitized_values: dict[str, Any] = Field(default_factory=dict)


def validate_multiple_inputs(**kwargs: Any) -> ValidationResult:
    """Validate multiple inputs in a single call.

    Supported parameters:
    - query: str
    - doc_id: str
    - filename: str
    - exact_match: bool
    - normalize_id: bool

    Returns:
        ValidationResult with status and sanitized values
    """
    result = ValidationResult(is_valid=True)

    # Extract parameters
    query = kwargs.get("query")
    doc_id = kwargs.get("doc_id")
    filename = kwargs.get("filename")
    exact_match = kwargs.get("exact_match", False)
    normalize_id = kwargs.get("normalize_id", True)

    # Validate query if provided
    if query is not None:
        try:
            validated = validate_search_request(query, exact_match)
            result.sanitized_values.update(validated)
        except ValidationError as e:
            result.is_valid = False
            result.errors.append(f"Query validation failed: {e.message}")

    # Validate document ID if provided
    if doc_id is not None:
        try:
            validated_id = validate_document_id(doc_id, normalize=normalize_id)
            result.sanitized_values["doc_id"] = validated_id
        except ValidationError as e:
            result.is_valid = False
            result.errors.append(f"Document ID validation failed: {e.message}")

    # Validate filename if provided
    if filename is not None:
        try:
            validated_filename = validate_filename_safe(filename)
            result.sanitized_values["filename"] = validated_filename
        except ValidationError as e:
            result.is_valid = False
            result.errors.append(f"Filename validation failed: {e.message}")

    return result
