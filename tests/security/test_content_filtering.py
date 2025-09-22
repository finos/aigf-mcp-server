"""
Security tests for content filtering and security headers.

Tests to ensure proper content validation and security headers prevent
content injection and other security vulnerabilities.
"""

import pytest
from unittest.mock import patch, MagicMock
import httpx

from src.finos_mcp.security.content_filter import ContentSecurityValidator


class TestContentTypeValidation:
    """Test MIME type and content validation."""

    @pytest.fixture
    def content_validator(self):
        """Create ContentSecurityValidator instance for testing."""
        return ContentSecurityValidator()

    def test_validates_safe_content_types(self, content_validator):
        """Test that safe content types are allowed."""
        safe_types = [
            "text/plain",
            "text/html",
            "application/json",
            "text/yaml",
            "text/markdown",
            "application/xml"
        ]

        for content_type in safe_types:
            assert content_validator.is_safe_content_type(content_type) is True

    def test_blocks_dangerous_content_types(self, content_validator):
        """Test that dangerous content types are blocked."""
        dangerous_types = [
            "application/javascript",
            "text/javascript",
            "application/x-executable",
            "application/octet-stream",
            "application/x-msdownload",
            "application/x-sh",
            "text/x-shellscript"
        ]

        for content_type in dangerous_types:
            assert content_validator.is_safe_content_type(content_type) is False

    def test_validates_content_against_injection(self, content_validator):
        """Test that content is validated against injection attacks."""
        safe_content = "This is normal text content for documentation."
        assert content_validator.validate_content_safety(safe_content) is True

        # Test script injection
        script_content = "<script>alert('xss')</script>"
        assert content_validator.validate_content_safety(script_content) is False

        # Test iframe injection
        iframe_content = "<iframe src='javascript:alert(1)'></iframe>"
        assert content_validator.validate_content_safety(iframe_content) is False

        # Test object/embed injection
        object_content = "<object data='malicious.swf'></object>"
        assert content_validator.validate_content_safety(object_content) is False

    def test_validates_url_schemes(self, content_validator):
        """Test that URL schemes are properly validated."""
        safe_urls = [
            "https://example.com/doc.html",
            "http://trusted-site.org/content",
            "mailto:contact@example.com"
        ]

        dangerous_urls = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "ftp://malicious-site.com/backdoor"
        ]

        for url in safe_urls:
            assert content_validator.is_safe_url(url) is True

        for url in dangerous_urls:
            assert content_validator.is_safe_url(url) is False

    def test_content_size_validation(self, content_validator):
        """Test that content size limits are enforced."""
        # Normal size content should pass
        normal_content = "x" * 1000  # 1KB
        assert content_validator.validate_content_size(normal_content) is True

        # Oversized content should be rejected
        oversized_content = "x" * 20_000_000  # 20MB
        assert content_validator.validate_content_size(oversized_content) is False


class TestSecurityHeaders:
    """Test HTTP security headers implementation."""

    @pytest.fixture
    def security_headers(self):
        """Create security headers configuration."""
        from src.finos_mcp.security.content_filter import SecurityHeaders
        return SecurityHeaders()

    def test_generates_required_security_headers(self, security_headers):
        """Test that all required security headers are generated."""
        headers = security_headers.get_security_headers()

        # Check for essential security headers
        assert "X-Content-Type-Options" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in headers
        assert headers["X-XSS-Protection"] == "1; mode=block"

        assert "Referrer-Policy" in headers
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

        assert "Content-Security-Policy" in headers
        # CSP should be restrictive
        csp = headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src" in csp
        assert "object-src 'none'" in csp

    def test_csp_policy_is_restrictive(self, security_headers):
        """Test that Content Security Policy is appropriately restrictive."""
        headers = security_headers.get_security_headers()
        csp = headers["Content-Security-Policy"]

        # Should block inline scripts and eval (but style-src may allow unsafe-inline)
        script_src = [part.strip() for part in csp.split(';') if 'script-src' in part]
        if script_src:
            assert "'unsafe-inline'" not in script_src[0]
        assert "'unsafe-eval'" not in csp

        # Should restrict object sources
        assert "object-src 'none'" in csp

        # Should have frame ancestors policy
        assert "frame-ancestors" in csp

    def test_headers_can_be_customized(self, security_headers):
        """Test that security headers can be customized for specific needs."""
        custom_csp = "default-src 'self'; script-src 'self' 'unsafe-inline'"
        custom_headers = security_headers.get_security_headers(
            custom_csp=custom_csp,
            allow_framing=True
        )

        assert custom_headers["Content-Security-Policy"] == custom_csp
        assert custom_headers["X-Frame-Options"] == "SAMEORIGIN"  # Less restrictive when allowing framing


class TestHTTPClientSecurity:
    """Test HTTP client security integration."""

    def test_http_client_security_headers_generation(self):
        """Test that security headers are properly generated for HTTP requests."""
        from src.finos_mcp.security.content_filter import SecurityHeaders

        security_headers = SecurityHeaders()
        request_headers = security_headers.get_request_headers("1.0.0")

        # Should include security-conscious headers
        assert "User-Agent" in request_headers
        assert request_headers["User-Agent"] == "finos-mcp/1.0.0"

        # Should not include sensitive information in User-Agent
        assert "internal" not in request_headers["User-Agent"].lower()
        assert "debug" not in request_headers["User-Agent"].lower()

        # Should include referrer policy
        assert "Referrer-Policy" in request_headers
        assert request_headers["Referrer-Policy"] == "no-referrer"

        # Should restrict accepted content types
        assert "Accept" in request_headers
        accept_header = request_headers["Accept"]
        assert "application/json" in accept_header
        assert "text/plain" in accept_header
        assert "javascript" not in accept_header.lower()

    def test_response_content_validation(self):
        """Test that response content is validated for security."""
        from src.finos_mcp.security.content_filter import ContentSecurityValidator

        validator = ContentSecurityValidator()

        # Test malicious response content detection
        malicious_responses = [
            "<script>window.location='http://evil.com'</script>",
            "<iframe src='javascript:void(0)'></iframe>",
            "<object data='malicious.swf'></object>",
            "<embed src='evil.swf'></embed>"
        ]

        for content in malicious_responses:
            mock_response = MagicMock()
            mock_response.text = content
            mock_response.headers = {"content-type": "text/html"}

            assert validator.validate_response_safety(mock_response) is False

    def test_content_type_header_validation(self):
        """Test that Content-Type headers are properly validated."""
        from src.finos_mcp.security.content_filter import ContentSecurityValidator

        validator = ContentSecurityValidator()

        # Test safe responses
        safe_response = MagicMock()
        safe_response.text = "Safe documentation content"
        safe_response.headers = {"content-type": "text/plain"}
        assert validator.validate_response_safety(safe_response) is True

        # Test dangerous content type
        dangerous_response = MagicMock()
        dangerous_response.text = "alert('xss')"
        dangerous_response.headers = {"content-type": "application/javascript"}
        assert validator.validate_response_safety(dangerous_response) is False


class TestContentFilteringIntegration:
    """Test content filtering integration with the MCP server."""

    def test_filters_content_in_framework_loading(self):
        """Test that content filtering is applied when loading framework data."""
        from src.finos_mcp.security.content_filter import ContentSecurityValidator

        validator = ContentSecurityValidator()

        # Simulate framework content with embedded scripts
        framework_content = {
            "name": "Test Framework",
            "description": "Framework with <script>alert('xss')</script> embedded",
            "sections": [
                {
                    "title": "Section 1",
                    "content": "Normal content"
                },
                {
                    "title": "Section 2",
                    "content": "<iframe src='javascript:void(0)'></iframe>"
                }
            ]
        }

        # Should detect and flag unsafe content
        assert validator.validate_framework_content(framework_content) is False

        # Safe content should pass
        safe_content = {
            "name": "Safe Framework",
            "description": "This is safe documentation content",
            "sections": [
                {
                    "title": "Introduction",
                    "content": "This section contains normal text"
                }
            ]
        }

        assert validator.validate_framework_content(safe_content) is True
