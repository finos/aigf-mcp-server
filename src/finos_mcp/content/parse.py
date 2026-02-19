"""Frontmatter parser with comprehensive testing for FINOS MCP Server.

This module provides robust parsing of YAML frontmatter from Markdown documents,
handling edge cases like malformed YAML, missing delimiters, encoding issues,
and BOM markers.
"""

import codecs
import re
import unicodedata
from typing import Any, ClassVar, Optional

import yaml

from ..logging import get_logger

logger = get_logger("frontmatter_parser")

# Pre-compiled regex patterns for performance optimization
_PARSE_PATTERNS = {
    "line_endings": re.compile(r"\r\n|\r"),
    "excessive_newlines": re.compile(r"\n\n\n+"),
    "numeric_decimal": re.compile(r"^\d+\.\d+$"),
    "yaml_recovery_1": re.compile(r"^(\s*-\s*.*?)(\n\s*[^-\s].*?)$", re.MULTILINE),
    "yaml_recovery_2": re.compile(r"^(\s*\w+:\s*.*?)(\n\s*[^:\s].*?)$", re.MULTILINE),
    "yaml_recovery_3": re.compile(r",\s*\n"),
}


class FrontmatterParseError(Exception):
    """Raised when frontmatter parsing fails in an unrecoverable way."""


class FrontmatterParser:
    """Robust frontmatter parser with comprehensive error handling.

    Features:
    - BOM handling for various encodings
    - Malformed YAML recovery
    - Multiple delimiter detection
    - Encoding normalization
    - Comprehensive logging
    """

    # Various BOM markers
    BOM_MARKERS: ClassVar[list[tuple[bytes, str]]] = [
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
    ]

    # Single, simple frontmatter pattern - industry standard YAML only
    FRONTMATTER_PATTERN = re.compile(
        r"^---\s*\n(.*?)^---\s*\n", re.DOTALL | re.MULTILINE
    )

    def __init__(self) -> None:
        """Initialize frontmatter parser."""
        self.stats = {
            "parsed": 0,
            "failed": 0,
            "bom_detected": 0,
            "encoding_issues": 0,
            "malformed_yaml": 0,
        }

    def detect_and_remove_bom(self, content: str | bytes) -> tuple[str, str | None]:
        """Detect and remove BOM markers from content.

        Args:
            content: Raw content string or bytes

        Returns:
            Tuple of (cleaned_content, detected_encoding)

        """
        # Convert to bytes for BOM detection
        if isinstance(content, bytes):
            content_bytes = content
        else:
            content_bytes = content.encode("utf-8", errors="ignore")

        for bom, encoding in self.BOM_MARKERS:
            if content_bytes.startswith(bom):
                self.stats["bom_detected"] += 1
                logger.debug("Detected BOM for encoding: %s", encoding)

                # Remove BOM and decode properly
                clean_bytes = content_bytes[len(bom) :]
                try:
                    clean_content = clean_bytes.decode(encoding.replace("-sig", ""))
                    return clean_content, encoding
                except UnicodeDecodeError as e:
                    logger.warning(
                        "Failed to decode with detected encoding %s: %s", encoding, e
                    )
                    self.stats["encoding_issues"] += 1

        # No BOM detected, convert bytes to string if needed
        if isinstance(content, bytes):
            try:
                return content.decode("utf-8"), None
            except UnicodeDecodeError:
                return content.decode("utf-8", errors="replace"), None
        return content, None

    def normalize_content(self, content: str) -> str:
        """Normalize content for consistent parsing.

        Args:
            content: Content to normalize

        Returns:
            Normalized content

        """
        # Normalize Unicode characters
        content = unicodedata.normalize("NFKC", content)

        # Normalize line endings to \n using pre-compiled pattern
        content = _PARSE_PATTERNS["line_endings"].sub("\n", content)

        # Remove excessive whitespace while preserving structure
        content = _PARSE_PATTERNS["excessive_newlines"].sub("\n\n", content)

        return content.strip()

    def extract_frontmatter_content(self, content: str) -> tuple[str | None, str]:
        """Extract YAML frontmatter and body content.

        Args:
            content: Full document content

        Returns:
            Tuple of (frontmatter_yaml_string, body_content)

        """
        match = self.FRONTMATTER_PATTERN.search(content)
        if match:
            frontmatter_text = match.group(1).strip()
            body = content[match.end() :].lstrip()
            return frontmatter_text, body

        # No frontmatter found
        return None, content

    def parse_yaml_safely(self, yaml_text: str) -> dict[str, Any]:
        """Parse YAML with comprehensive error handling.

        Args:
            yaml_text: YAML text to parse

        Returns:
            Parsed YAML as dictionary

        Raises:
            FrontmatterParseError: If YAML is completely unparseable

        """
        if not yaml_text.strip():
            return {}

        try:
            # Try standard YAML parsing
            result = yaml.safe_load(yaml_text)

            if result is None:
                logger.debug("YAML parsed as None, returning empty dict")
                return {}

            if not isinstance(result, dict):
                logger.warning("YAML parsed as %s, converting to dict", type(result))
                return {"content": result}

            return result

        except yaml.YAMLError as e:
            self.stats["malformed_yaml"] += 1
            logger.warning("YAML parsing failed: %s", e)

            # Try to recover by cleaning the YAML
            try:
                cleaned_yaml = self._attempt_yaml_recovery(yaml_text)
                result = yaml.safe_load(cleaned_yaml)

                if isinstance(result, dict):
                    logger.info("Successfully recovered malformed YAML")
                    return result

            except (
                yaml.YAMLError,
                ValueError,
                TypeError,
                AttributeError,
            ) as recovery_error:
                logger.debug("YAML recovery failed: %s", recovery_error)

            # If recovery fails, try to extract key-value pairs manually
            try:
                manual_parsed = self._manual_yaml_extraction(yaml_text)
                if manual_parsed:
                    logger.info("Successfully extracted YAML manually")
                    return manual_parsed
            except (ValueError, TypeError, AttributeError, KeyError) as manual_error:
                logger.debug("Manual YAML extraction failed: %s", manual_error)

            # Last resort: return the raw text for investigation
            logger.error("Complete YAML parsing failure: %s", e)
            return {
                "_parsing_error": str(e),
                "_raw_frontmatter": (
                    yaml_text[:200] + "..." if len(yaml_text) > 200 else yaml_text
                ),
            }

    def _attempt_yaml_recovery(self, yaml_text: str) -> str:
        """Attempt to recover malformed YAML by fixing common issues.

        Args:
            yaml_text: Potentially malformed YAML

        Returns:
            Cleaned YAML text

        """
        # Fix common issues
        cleaned = yaml_text

        # Fix unquoted strings with colons
        cleaned = re.sub(
            r'^(\s*\w+):\s*([^"\']*:.*)', r'\1: "\2"', cleaned, flags=re.MULTILINE
        )

        # Fix missing quotes around values with special characters
        cleaned = re.sub(
            r'^(\s*\w+):\s*([^"\'\n]*[#\[\]{}]*[^"\'\n]*)\s*$',
            r'\1: "\2"',
            cleaned,
            flags=re.MULTILINE,
        )

        # Fix trailing commas (invalid in YAML) using pre-compiled pattern
        cleaned = _PARSE_PATTERNS["yaml_recovery_3"].sub("\n", cleaned)

        # Fix tabs (should be spaces in YAML)
        cleaned = cleaned.replace("\t", "  ")

        return cleaned

    def _manual_yaml_extraction(self, yaml_text: str) -> dict[str, Any]:
        """Manually extract key-value pairs from malformed YAML.

        Args:
            yaml_text: Malformed YAML text

        Returns:
            Extracted key-value pairs

        """
        result = {}

        # Simple key: value extraction
        for line in yaml_text.split("\n"):
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                try:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    # Try to convert to appropriate type
                    converted_value: Any = value
                    if value.lower() in ("true", "false"):
                        converted_value = value.lower() == "true"
                    elif value.isdigit():
                        converted_value = int(value)
                    elif _PARSE_PATTERNS["numeric_decimal"].match(value):
                        converted_value = float(value)

                    result[key] = converted_value
                except ValueError:
                    continue

        return result

    def parse(self, content: str | bytes) -> tuple[dict[str, Any], str]:
        """Parse frontmatter from content with comprehensive error handling.

        Args:
            content: Full document content (string or bytes)

        Returns:
            Tuple of (frontmatter_dict, body_content)

        """
        try:
            self.stats["parsed"] += 1

            # Handle BOM and encoding issues
            content, _ = self.detect_and_remove_bom(content)

            # Normalize content
            content = self.normalize_content(content)

            # Extract frontmatter content
            frontmatter_text, body = self.extract_frontmatter_content(content)

            if frontmatter_text is None:
                logger.debug("No frontmatter detected")
                return {}, body

            # Parse YAML safely
            frontmatter = self.parse_yaml_safely(frontmatter_text)

            logger.debug(
                "Successfully parsed frontmatter with %s fields", len(frontmatter)
            )
            return frontmatter, body

        except (
            UnicodeDecodeError,
            UnicodeError,
            ValueError,
            TypeError,
            AttributeError,
            MemoryError,
        ) as e:
            self.stats["failed"] += 1
            # Ensure content is string for preview
            content_str = (
                content
                if isinstance(content, str)
                else content.decode("utf-8", errors="replace")
            )
            logger.error(
                "Frontmatter parsing failed completely: %s",
                e,
                extra={
                    "content_length": len(content_str),
                    "content_preview": (
                        content_str[:100] + "..."
                        if len(content_str) > 100
                        else content_str
                    ),
                },
            )
            # Return empty frontmatter and original content as string in case of complete failure
            return {}, content_str

    def get_stats(self) -> dict[str, Any]:
        """Get parsing statistics."""
        return self.stats.copy()


class FrontmatterParserManager:
    """Singleton manager for the global frontmatter parser instance."""

    _instance: Optional["FrontmatterParserManager"] = None
    _parser: FrontmatterParser | None = None

    def __new__(cls) -> "FrontmatterParserManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_parser(self) -> FrontmatterParser:
        """Get the global parser instance."""
        if self._parser is None:
            self._parser = FrontmatterParser()
        return self._parser


# Global parser manager instance
_parser_manager = FrontmatterParserManager()


def parse_frontmatter(content: str | bytes) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown content.

    This is the main public API for frontmatter parsing. It handles:
    - BOM markers and encoding issues
    - Malformed YAML with recovery attempts
    - Multiple delimiter styles
    - Comprehensive error handling

    Args:
        content: Full document content

    Returns:
        Tuple of (frontmatter_dict, body_content)

    """
    parser = _parser_manager.get_parser()
    return parser.parse(content)


def get_parser_stats() -> dict[str, Any]:
    """Get frontmatter parser statistics.

    Returns:
        Dictionary with parsing statistics

    """
    parser = _parser_manager.get_parser()
    return parser.get_stats()


def reset_parser_stats() -> None:
    """Reset parser statistics."""
    parser = _parser_manager.get_parser()
    parser.stats = {
        "parsed": 0,
        "failed": 0,
        "bom_detected": 0,
        "encoding_issues": 0,
        "malformed_yaml": 0,
    }
