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

        # Early return for disabled validation
        if self.mode == ValidationMode.DISABLED:
            return arguments if isinstance(arguments, dict) else {}

        # Validate arguments type
        if not isinstance(arguments, dict):
            if self.mode == ValidationMode.STRICT:  # type: ignore[unreachable]
                raise SecurityValidationError(
                    f"Tool arguments must be dict for {tool_name}"
                )
            # Permissive mode: return empty dict
            return {}

        # Perform content validation based on mode
        is_strict = self.mode == ValidationMode.STRICT
        return self._validate_argument_content(arguments, tool_name, is_strict)

    def _validate_argument_content(
        self, arguments: dict[str, Any], tool_name: str, is_strict: bool
    ) -> dict[str, Any]:
        """Validate argument content based on validation mode."""
        from ..server import SecurityValidationError

        working_args = arguments

        # Size validation
        if len(working_args) > 50:
            if is_strict:
                raise SecurityValidationError(f"Too many arguments for {tool_name}")
            # Truncate in permissive mode
            working_args = dict(list(working_args.items())[:50])

        # Content validation
        validated_args: dict[str, Any] = {}

        for key, value in working_args.items():
            # Key type validation
            if not isinstance(key, str):
                if is_strict:  # type: ignore[unreachable]
                    raise SecurityValidationError(
                        f"Argument key must be string for {tool_name}"
                    )
                continue  # Skip in permissive mode

            # Dangerous key validation
            if key.startswith("__") or key.lower() in {"eval", "exec"}:
                if is_strict:
                    raise SecurityValidationError(
                        f"Dangerous key '{key}' not allowed for {tool_name}"
                    )
                continue  # Skip in permissive mode

            # Value validation
            processed_value = self._validate_argument_value(value, tool_name, is_strict)
            validated_args[key] = processed_value

        return validated_args

    def _validate_argument_value(
        self, value: Any, tool_name: str, is_strict: bool
    ) -> Any:
        """Validate a single argument value."""
        from ..server import SecurityValidationError

        if not isinstance(value, str):
            return value

        # Length validation
        if len(value) > 10000:  # 10KB limit
            if is_strict:
                raise SecurityValidationError(f"String too long for {tool_name}")
            return value[:10000]  # Truncate in permissive mode

        # Content safety validation - only in strict mode
        if is_strict:
            dangerous_exact = ["<script>", "javascript:", "eval(", "exec("]
            if any(danger in value.lower() for danger in dangerous_exact):
                raise SecurityValidationError(f"Dangerous content in {tool_name}")

        return value

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
