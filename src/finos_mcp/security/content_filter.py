"""
Content security validation and filtering.

Provides protection against content injection attacks and ensures
safe content types and security headers for HTTP requests.
"""

import re
import urllib.parse
from typing import Any, ClassVar

from ..logging import get_logger

logger = get_logger(__name__)


class ContentSecurityValidator:
    """Validate content for security threats and filter dangerous content."""

    # Safe MIME types that are allowed
    SAFE_CONTENT_TYPES: ClassVar[set[str]] = {
        "text/plain",
        "text/html",
        "text/markdown",
        "text/yaml",
        "text/csv",
        "application/json",
        "application/xml",
        "application/yaml",
        "text/xml"
    }

    # Dangerous MIME types that should be blocked
    DANGEROUS_CONTENT_TYPES: ClassVar[set[str]] = {
        "application/javascript",
        "text/javascript",
        "application/x-javascript",
        "application/x-executable",
        "application/octet-stream",
        "application/x-msdownload",
        "application/x-sh",
        "text/x-shellscript",
        "application/x-python-code",
        "text/x-python",
        "application/x-php",
        "text/x-php"
    }

    # Patterns that indicate potentially dangerous content
    DANGEROUS_CONTENT_PATTERNS: ClassVar[list[str]] = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
        r'<object[^>]*>.*?</object>',  # Object tags
        r'<embed[^>]*>.*?</embed>',    # Embed tags
        r'javascript:[^"\'\s]*',       # JavaScript URLs
        r'vbscript:[^"\'\s]*',        # VBScript URLs
        r'data:[^,]*base64[^"\'\s]*',  # Data URLs with base64
        r'on\w+\s*=\s*["\'][^"\']*["\']',  # Event handlers (onclick, onload, etc.)
    ]

    # Safe URL schemes
    SAFE_URL_SCHEMES: ClassVar[set[str]] = {'https', 'http', 'mailto'}

    def __init__(self, max_content_size: int = 10_000_000):  # 10MB default
        """Initialize content security validator.

        Args:
            max_content_size: Maximum allowed content size in bytes
        """
        self.max_content_size = max_content_size
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE | re.DOTALL)
            for pattern in self.DANGEROUS_CONTENT_PATTERNS
        ]

    def is_safe_content_type(self, content_type: str) -> bool:
        """Check if a content type is safe.

        Args:
            content_type: MIME type to check

        Returns:
            True if content type is safe, False otherwise
        """
        if not content_type:
            return False

        # Extract the main type (ignore charset and other parameters)
        main_type = content_type.split(';')[0].strip().lower()

        # Block explicitly dangerous types
        if main_type in self.DANGEROUS_CONTENT_TYPES:
            logger.warning(f"Blocked dangerous content type: {main_type}")
            return False

        # Allow explicitly safe types
        if main_type in self.SAFE_CONTENT_TYPES:
            return True

        # For unknown types, be conservative and block
        logger.warning(f"Blocked unknown content type: {main_type}")
        return False

    def validate_content_safety(self, content: str) -> bool:
        """Validate content for security threats.

        Args:
            content: Content to validate

        Returns:
            True if content is safe, False if it contains threats
        """
        if not content:
            return True

        # Check for dangerous patterns
        for pattern in self.compiled_patterns:
            if pattern.search(content):
                logger.warning("Detected dangerous content pattern")
                return False

        return True

    def validate_content_size(self, content: str) -> bool:
        """Validate content size limits.

        Args:
            content: Content to validate

        Returns:
            True if content size is acceptable, False if too large
        """
        if not content:
            return True

        size = len(content.encode('utf-8'))
        if size > self.max_content_size:
            logger.warning(f"Content size {size} exceeds limit {self.max_content_size}")
            return False

        return True

    def is_safe_url(self, url: str) -> bool:
        """Check if a URL is safe.

        Args:
            url: URL to validate

        Returns:
            True if URL is safe, False otherwise
        """
        if not url:
            return False

        try:
            parsed = urllib.parse.urlparse(url.lower())

            # Check scheme
            if parsed.scheme not in self.SAFE_URL_SCHEMES:
                logger.warning(f"Blocked unsafe URL scheme: {parsed.scheme}")
                return False

            # Additional checks for localhost/private IPs
            hostname = parsed.hostname
            if hostname:
                # Block localhost variations
                if hostname in ('localhost', '127.0.0.1'):
                    logger.warning(f"Blocked localhost URL: {hostname}")
                    return False

                # Block private IP ranges
                if re.match(r'^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)', hostname):
                    logger.warning(f"Blocked private IP: {hostname}")
                    return False

            return True

        except Exception as e:
            logger.warning(f"URL parsing failed: {e}")
            return False

    def validate_response_safety(self, response: Any) -> bool:
        """Validate HTTP response for security.

        Args:
            response: HTTP response object with .text and .headers attributes

        Returns:
            True if response is safe, False otherwise
        """
        # Check content type
        content_type = response.headers.get('content-type', '')
        if not self.is_safe_content_type(content_type):
            return False

        # Check content size
        if hasattr(response, 'text'):
            if not self.validate_content_size(response.text):
                return False

            # Check content for dangerous patterns
            if not self.validate_content_safety(response.text):
                return False

        return True

    def validate_framework_content(self, content: dict[str, Any] | list[Any] | str) -> bool:
        """Validate framework content recursively.

        Args:
            content: Framework content dictionary

        Returns:
            True if content is safe, False if it contains threats
        """
        if isinstance(content, dict):
            for key, value in content.items():
                if isinstance(value, str):
                    if not self.validate_content_safety(value):
                        logger.warning(f"Unsafe content in field: {key}")
                        return False
                elif isinstance(value, (dict, list)):
                    if not self.validate_framework_content(value):
                        return False

        elif isinstance(content, list):
            for item in content:
                if not self.validate_framework_content(item):
                    return False

        elif isinstance(content, str):
            return self.validate_content_safety(content)

        return True


class SecurityHeaders:
    """Generate and manage HTTP security headers."""

    # Default Content Security Policy
    DEFAULT_CSP = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    def get_security_headers(
        self,
        custom_csp: str | None = None,
        allow_framing: bool = False
    ) -> dict[str, str]:
        """Get security headers for HTTP responses.

        Args:
            custom_csp: Custom Content Security Policy
            allow_framing: Whether to allow framing (less restrictive)

        Returns:
            Dictionary of security headers
        """
        headers = {
            # Prevent MIME type sniffing
            "X-Content-Type-Options": "nosniff",

            # XSS protection
            "X-XSS-Protection": "1; mode=block",

            # Referrer policy
            "Referrer-Policy": "strict-origin-when-cross-origin",

            # Content Security Policy
            "Content-Security-Policy": custom_csp or self.DEFAULT_CSP,
        }

        # Frame options
        if allow_framing:
            headers["X-Frame-Options"] = "SAMEORIGIN"
        else:
            headers["X-Frame-Options"] = "DENY"

        return headers

    def get_request_headers(self, server_version: str = "1.0.0") -> dict[str, str]:
        """Get security-conscious headers for outgoing requests.

        Args:
            server_version: Server version for User-Agent

        Returns:
            Dictionary of request headers
        """
        return {
            # Safe User-Agent without sensitive information
            "User-Agent": f"finos-mcp/{server_version}",

            # Don't send referrer information
            "Referrer-Policy": "no-referrer",

            # Request only safe content types
            "Accept": "text/plain, text/html, application/json, text/yaml, text/markdown",

            # Don't accept dangerous encodings
            "Accept-Encoding": "gzip, deflate",
        }


# Global instances for easy access
content_security_validator = ContentSecurityValidator()
security_headers = SecurityHeaders()
