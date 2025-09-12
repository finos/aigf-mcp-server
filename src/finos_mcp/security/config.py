"""
Security validation configuration.

Provides configurable validation levels for different environments.
"""

import os
from enum import Enum
from typing import Any


class ValidationMode(Enum):
    """Validation modes for different environments."""

    STRICT = "strict"  # Production: full validation
    PERMISSIVE = "permissive"  # Development: relaxed validation
    DISABLED = "disabled"  # Testing: no validation


class ValidationConfig:
    """Configurable security validation."""

    def __init__(self, mode: ValidationMode | None = None):
        """Initialize validation config.

        Args:
            mode: Validation mode, auto-detected from environment if None
        """
        self.mode = mode or self._detect_mode()

    def _detect_mode(self) -> ValidationMode:
        """Auto-detect validation mode from environment."""
        # Check environment variables
        env_mode = os.getenv("FINOS_MCP_VALIDATION_MODE", "").lower()

        if env_mode == "disabled":
            return ValidationMode.DISABLED
        elif env_mode == "permissive":
            return ValidationMode.PERMISSIVE
        elif env_mode == "strict":
            return ValidationMode.STRICT

        # Auto-detect from context
        if os.getenv("PYTEST_CURRENT_TEST"):
            return ValidationMode.DISABLED  # Disable in tests
        elif os.getenv("FINOS_MCP_DEBUG_MODE") == "true":
            return ValidationMode.PERMISSIVE  # Relaxed in dev
        else:
            return ValidationMode.STRICT  # Strict in production

    def validate_tool_arguments(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate tool arguments based on current mode.

        Args:
            tool_name: Name of the tool
            arguments: Tool arguments to validate

        Returns:
            Validated arguments (may be modified)

        Raises:
            SecurityValidationError: If validation fails in strict mode
        """
        from ..server import SecurityValidationError

        if self.mode == ValidationMode.DISABLED:
            return arguments

        # Basic validation always runs
        if not isinstance(arguments, dict):
            if self.mode == ValidationMode.STRICT:
                raise SecurityValidationError(
                    f"Tool arguments must be dict for {tool_name}"
                )
            return {}  # Return empty dict in permissive mode

        if len(arguments) > 50:
            if self.mode == ValidationMode.STRICT:
                raise SecurityValidationError(f"Too many arguments for {tool_name}")
            # Truncate in permissive mode
            arguments = dict(list(arguments.items())[:50])

        # Content validation
        validated_args: dict[str, Any] = {}

        for key, value in arguments.items():
            # Key validation
            if not isinstance(key, str):
                if self.mode == ValidationMode.STRICT:
                    raise SecurityValidationError(
                        f"Argument key must be string for {tool_name}"
                    )
                continue  # Skip in permissive mode

            # Simple dangerous key check
            if key.startswith("__") or key.lower() in {"eval", "exec"}:
                if self.mode == ValidationMode.STRICT:
                    raise SecurityValidationError(
                        f"Dangerous key '{key}' not allowed for {tool_name}"
                    )
                continue  # Skip in permissive mode

            # Value validation
            if isinstance(value, str):
                if len(value) > 10000:  # 10KB limit
                    if self.mode == ValidationMode.STRICT:
                        raise SecurityValidationError(
                            f"String too long for {tool_name}"
                        )
                    value = value[:10000]  # Truncate in permissive mode

                # Simple XSS check - only obvious patterns
                if self.mode == ValidationMode.STRICT:
                    dangerous_exact = ["<script>", "javascript:", "eval(", "exec("]
                    if any(danger in value.lower() for danger in dangerous_exact):
                        raise SecurityValidationError(
                            f"Dangerous content in {tool_name}"
                        )

            validated_args[key] = value

        return validated_args

    def is_strict_mode(self) -> bool:
        """Check if running in strict validation mode."""
        return self.mode == ValidationMode.STRICT

    def is_permissive_mode(self) -> bool:
        """Check if running in permissive validation mode."""
        return self.mode == ValidationMode.PERMISSIVE

    def is_disabled(self) -> bool:
        """Check if validation is disabled."""
        return self.mode == ValidationMode.DISABLED


# Global default config instance
_default_config = ValidationConfig()


def get_validation_config() -> ValidationConfig:
    """Get the default validation configuration."""
    return _default_config


def set_validation_config(config: ValidationConfig) -> None:
    """Set the default validation configuration."""
    global _default_config
    _default_config = config
