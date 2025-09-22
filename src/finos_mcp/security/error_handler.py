"""
Secure error handling to prevent information disclosure.

Provides safe error responses while maintaining internal debugging capabilities.
"""

import re
import uuid
from datetime import datetime
from typing import Any, ClassVar

from ..logging import get_logger

logger = get_logger(__name__)


class SecureErrorHandler:
    """Handle errors securely to prevent information disclosure."""

    # Patterns that indicate sensitive information
    SENSITIVE_PATTERNS: ClassVar[list[str]] = [
        r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',  # Email addresses
        r'\b(?:api_?key|password|token|secret)\s*[:=]?\s*[\'"]?[a-zA-Z0-9_-]+[\'"]?',  # API keys/passwords
        r'(?:api key|password|token)\s+[a-zA-Z0-9_-]+',  # API keys with spaces
        r'/(?:var|home|etc|usr)/[a-zA-Z0-9/_.-]*',  # File paths
        r'\b(?:0x)?[0-9a-fA-F]{8,}\b',  # Memory addresses
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP addresses
        r':\d+',  # Port numbers when after hostnames
        r'\.py:\d+',  # Python file line numbers
        r'line \d+',  # Line number references
        r'at [a-zA-Z0-9_.-]+\.[a-zA-Z0-9_]+:\d+',  # Stack trace locations
        r'[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+:\d+',  # File:line references
        r'Database[a-zA-Z0-9_.]*\.py',  # Python database files
        r'timeout after \d+[a-z]*',  # Timeout details
        r'connection.*failed.*host',  # Connection details
        r'sk_[a-zA-Z0-9_]+',  # Secret keys starting with sk_
    ]

    # Generic error messages for different categories
    SAFE_ERROR_MESSAGES: ClassVar[dict[str, str]] = {
        'validation': 'Invalid input provided. Please check your request and try again.',
        'authentication': 'Authentication failed. Please verify your credentials.',
        'authorization': 'Access denied. You do not have permission to perform this action.',
        'not_found': 'The requested resource was not found.',
        'server_error': 'An internal server error occurred. Please try again later.',
        'timeout': 'The request timed out. Please try again.',
        'rate_limit': 'Too many requests. Please slow down and try again later.',
        'default': 'An error occurred while processing your request.'
    }

    def __init__(self):
        """Initialize secure error handler."""
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.SENSITIVE_PATTERNS
        ]

    def sanitize_error_message(self, error_message: str) -> str:
        """Sanitize error message by removing sensitive information.

        Args:
            error_message: Original error message

        Returns:
            Sanitized error message safe for external consumption
        """
        if not error_message:
            return self.SAFE_ERROR_MESSAGES['default']

        sanitized = str(error_message)

        # Remove sensitive patterns
        for pattern in self.compiled_patterns:
            sanitized = pattern.sub('[REDACTED]', sanitized)

        # If too much was redacted or message becomes unclear, use generic message
        if sanitized.count('[REDACTED]') > 0 or len(sanitized.strip()) < 15:
            return self._categorize_error(error_message)

        return sanitized

    def _categorize_error(self, error_message: str) -> str:
        """Categorize error and return appropriate safe message."""
        message_lower = error_message.lower()

        if any(word in message_lower for word in ['validation', 'invalid', 'malformed']):
            return self.SAFE_ERROR_MESSAGES['validation']
        elif any(word in message_lower for word in ['auth', 'credential', 'login']):
            return self.SAFE_ERROR_MESSAGES['authentication']
        elif any(word in message_lower for word in ['permission', 'forbidden', 'access']):
            return self.SAFE_ERROR_MESSAGES['authorization']
        elif any(word in message_lower for word in ['not found', 'missing']):
            return self.SAFE_ERROR_MESSAGES['not_found']
        elif any(word in message_lower for word in ['timeout', 'timed out']):
            return self.SAFE_ERROR_MESSAGES['timeout']
        elif any(word in message_lower for word in ['rate', 'limit', 'throttle']):
            return self.SAFE_ERROR_MESSAGES['rate_limit']
        elif any(word in message_lower for word in ['database', 'connection', 'host', 'file']):
            return self.SAFE_ERROR_MESSAGES['server_error']
        else:
            return self.SAFE_ERROR_MESSAGES['server_error']

    def create_safe_error_response(
        self,
        original_error: str,
        correlation_id: str | None = None
    ) -> str:
        """Create a safe error response for external consumption.

        Args:
            original_error: The original error message
            correlation_id: Optional correlation ID for debugging

        Returns:
            Safe error message with correlation ID
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())[:8]

        safe_message = self.sanitize_error_message(original_error)

        return f"{safe_message} (Request ID: {correlation_id})"

    def log_error_internally(
        self,
        original_error: str,
        correlation_id: str,
        additional_context: dict[str, Any] | None = None
    ) -> None:
        """Log error with full details internally for debugging.

        Args:
            original_error: Original error with full details
            correlation_id: Correlation ID for request tracking
            additional_context: Additional context for debugging
        """
        context = additional_context or {}

        logger.error(
            f"Internal error details [{correlation_id}] - {original_error}",
            extra={
                "correlation_id": correlation_id,
                "timestamp": datetime.utcnow().isoformat(),
                **context
            }
        )

    def handle_tool_error(
        self,
        error: Exception,
        tool_name: str,
        parameters: dict[str, Any],
        correlation_id: str | None = None
    ) -> str:
        """Handle tool execution error securely.

        Args:
            error: The exception that occurred
            tool_name: Name of the tool that failed
            parameters: Tool parameters (will be sanitized for logging)
            correlation_id: Request correlation ID

        Returns:
            Safe error message for external response
        """
        if not correlation_id:
            correlation_id = str(uuid.uuid4())[:8]

        # Log full details internally
        sanitized_params = self._sanitize_parameters(parameters)
        self.log_error_internally(
            f"Tool '{tool_name}' failed: {error!s}",
            correlation_id,
            {
                "tool_name": tool_name,
                "parameters": sanitized_params,
                "error_type": type(error).__name__
            }
        )

        # Return safe message externally
        return self.create_safe_error_response(str(error), correlation_id)

    def _sanitize_parameters(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Sanitize parameters for logging by removing sensitive values."""
        sanitized = {}

        for key, value in parameters.items():
            key_lower = key.lower()

            # Remove sensitive parameter values
            if any(sensitive in key_lower for sensitive in ['password', 'token', 'key', 'secret']):
                sanitized[key] = '[REDACTED]'
            elif isinstance(value, str) and len(value) > 100:
                # Truncate very long strings that might contain sensitive data
                sanitized[key] = value[:50] + '...[TRUNCATED]'
            elif isinstance(value, str):
                # Apply sanitization to string values
                sanitized[key] = self.sanitize_error_message(value)
            else:
                sanitized[key] = value

        return sanitized


# Global instance for easy access
secure_error_handler = SecureErrorHandler()
