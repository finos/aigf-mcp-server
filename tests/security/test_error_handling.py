"""
Security tests for error handling and information disclosure prevention.

Tests to ensure secure error handling that doesn't leak internal system details.
"""

from unittest.mock import patch

import pytest

from finos_mcp.security.error_handler import SecureErrorHandler


class TestSecureErrorHandling:
    """Test secure error handling prevents information disclosure."""

    @pytest.fixture
    def error_handler(self):
        """Create SecureErrorHandler instance for testing."""
        return SecureErrorHandler()

    def test_error_messages_are_user_friendly(self, error_handler):
        """Test that error messages are safe and user-friendly."""

        # Test various internal errors get converted to safe messages
        internal_errors = [
            "Database connection pool exhausted at DatabaseManager.py:156",
            "File not found: /var/lib/internal/secrets.json",
            "Authentication failed for user admin@internal.company.com",
            "Memory allocation failed in C extension at 0x7f8b8c000000",
        ]

        expected_safe_messages = [
            "An internal server error occurred. Please try again later.",
            "The requested resource was not found.",
            "Authentication failed. Please verify your credentials.",
            "An internal server error occurred. Please try again later.",
        ]

        for internal_error, expected_safe in zip(
            internal_errors, expected_safe_messages, strict=False
        ):
            safe_message = error_handler.sanitize_error_message(internal_error)

            # Safe message should not contain internal details
            assert "DatabaseManager.py" not in safe_message
            assert "/var/lib" not in safe_message
            assert "admin@internal.company.com" not in safe_message
            assert "0x7f8b8c000000" not in safe_message

            # Should be a generic safe message
            assert safe_message == expected_safe

    def test_correlation_ids_for_debugging(self, error_handler):
        """Test that correlation IDs are provided for debugging without exposing details."""
        error_response = error_handler.create_safe_error_response(
            original_error="Database connection failed: timeout after 30s",
            correlation_id="req_12345",
        )

        # Should contain correlation ID for support/debugging
        assert "req_12345" in error_response

        # Should contain safe generic message and correlation ID
        assert (
            "An internal server error occurred. Please try again later."
            in error_response
            or "The request timed out. Please try again." in error_response
        )


class TestErrorLogging:
    """Test that error logging is secure but maintains debugging capability."""

    @pytest.fixture
    def error_handler(self):
        """Create SecureErrorHandler instance for testing."""
        return SecureErrorHandler()

    @patch("finos_mcp.security.error_handler.logger")
    def test_internal_logging_preserves_details(self, mock_logger, error_handler):
        """Test that internal logs preserve error details for debugging."""
        original_error = (
            "Database connection failed: timeout after 30s on host db.internal.com"
        )
        correlation_id = "req_12345"

        error_handler.log_error_internally(original_error, correlation_id)

        # Internal logging should preserve full details
        mock_logger.error.assert_called()
        call_args = mock_logger.error.call_args[0]
        # Structured lazy logging uses a format string plus args.
        assert "Internal error details" in call_args[0]
        assert correlation_id in call_args
        assert original_error in call_args

    def test_no_sensitive_data_in_external_responses(self, error_handler):
        """Test that external error responses never contain sensitive data."""
        # Test data containing fake sensitive information for security validation
        sensitive_errors = [
            "User john.doe@company.com authentication failed",
            "API key sk_live_abc123def456 is invalid",
            "Database query failed: SELECT * FROM users WHERE password='secret123'",  # pragma: allowlist secret
            "File access denied: /home/admin/.ssh/id_rsa",
        ]

        expected_responses = [
            "Authentication failed. Please verify your credentials.",
            "Invalid input provided. Please check your request and try again.",
            "An internal server error occurred. Please try again later.",
            "Access denied. You do not have permission to perform this action.",
        ]

        for sensitive_error, expected in zip(
            sensitive_errors, expected_responses, strict=False
        ):
            external_response = error_handler.create_safe_error_response(
                sensitive_error, "req_123"
            )

            # Should not contain any sensitive data
            assert "john.doe@company.com" not in external_response
            assert "sk_live_abc123def456" not in external_response
            assert "password='secret123'" not in external_response
            assert "/home/admin/.ssh/id_rsa" not in external_response

            # Should contain expected safe message and request ID
            assert expected in external_response
            assert "req_123" in external_response
