"""Configuration settings for FINOS MCP Server.

Copyright 2024 Hugo Calderon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

This module provides Pydantic-based configuration management with environment variable
support and validation. Settings are loaded from environment variables with optional
.env file support.
"""

import logging
from typing import Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic.types import PositiveInt
from pydantic_settings import BaseSettings

try:
    from ._version import __version__
except ImportError:
    __version__ = "unknown"


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables with FINOS_MCP_ prefix.
    Example: FINOS_MCP_LOG_LEVEL=DEBUG
    """

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Network Configuration
    http_timeout: PositiveInt = Field(
        default=30,
        ge=5,
        le=300,
        description="HTTP client timeout in seconds (5-300s range for security)",
    )

    # Repository Configuration
    base_url: str = Field(
        default="https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs",
        description="Base URL for FINOS AI Governance Framework repository",
    )

    # Cache Configuration
    enable_cache: bool = Field(
        default=True,
        description="Enable in-memory caching of fetched documents",
    )

    cache_max_size: PositiveInt = Field(
        default=1000,
        ge=10,
        le=50000,
        description="Maximum number of documents to cache in memory (10-50000 range)",
    )

    cache_ttl_seconds: PositiveInt = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default time-to-live for cached documents in seconds (1min-24hrs)",
    )

    # Removed cache_cleanup_interval - automatic cleanup is sufficient

    # Development Configuration
    debug_mode: bool = Field(
        default=False,
        description="Enable debug mode with additional logging and error details",
    )

    # Server Configuration
    server_name: str = Field(
        default="finos-ai-governance",
        description="MCP server name identifier",
    )

    server_version: str = Field(
        default=__version__,
        description="MCP server version",
    )

    # GitHub API Configuration
    github_token: str | None = Field(
        default=None,
        description="GitHub personal access token for API access (optional, increases rate limits)",
    )

    # Simplified GitHub API Configuration
    github_api_timeout: int = Field(
        default=30,
        description="GitHub API request timeout in seconds",
    )

    # SHA-based Version Tracking
    enable_sha_validation: bool = Field(
        default=True,
        description="Enable SHA-based content change detection to extend cache lifetime",
    )

    check_static_fallback: bool = Field(
        default=True,
        description="Check if static fallback lists are outdated and log warnings",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "env_prefix": "FINOS_MCP_",
    }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is supported by Python logging."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v.upper()

    @field_validator("github_token")
    @classmethod
    def validate_github_token(cls, v: str | None) -> str | None:
        """Simple GitHub token validation."""
        if v is None or v.strip() == "":
            return None
        token = v.strip()
        # Basic validation - just check it looks like a GitHub token
        if not (
            token.startswith(
                ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "ghv_", "github_pat_")
            )
        ):
            raise ValueError("Invalid GitHub token format")
        return token

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Simple base URL validation."""
        parsed = urlparse(v)
        if not parsed.scheme or parsed.scheme not in ["http", "https"]:
            raise ValueError("Base URL must be a valid HTTP or HTTPS URL")
        if not parsed.netloc:
            raise ValueError("Base URL must include a domain")
        return v.rstrip("/")

    @property
    def mitigations_url(self) -> str:
        """Get the full URL for mitigations directory."""
        return f"{self.base_url}/_mitigations"

    @property
    def risks_url(self) -> str:
        """Get the full URL for risks directory."""
        return f"{self.base_url}/_risks"

    @property
    def frameworks_url(self) -> str:
        """Get the full URL for frameworks directory."""
        return f"{self.base_url}/_data"

    @property
    def logging_config(self) -> dict[str, str | int | None]:
        """Get logging configuration dictionary."""
        return {
            "level": getattr(logging, self.log_level),
            "format": (
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                if self.debug_mode
                else "%(name)s - %(levelname)s - %(message)s"
            ),
            "datefmt": "%Y-%m-%d %H:%M:%S" if self.debug_mode else None,
        }

    def configure_logging(self) -> None:
        """Configure Python logging based on settings."""
        # Use mypy type ignore for basicConfig due to dynamic configuration
        logging_config = self.logging_config
        logging.basicConfig(**logging_config)  # type: ignore[arg-type]

        if self.debug_mode:
            # Enable debug logging for httpx in debug mode
            logging.getLogger("httpx").setLevel(logging.DEBUG)

    def validate_startup(self) -> None:
        """Validate configuration at startup.

        Raises:
            ValueError: If configuration is invalid for startup.

        """
        errors = []

        # Test network connectivity (basic validation)
        try:
            parsed = urlparse(self.base_url)
            if not parsed.netloc:
                errors.append("Invalid base_url: missing domain")
        except (ValueError, TypeError, AttributeError) as e:
            errors.append(f"Invalid base_url: {e}")

        # Validate cache settings make sense
        if self.cache_max_size <= 0:
            errors.append("cache_max_size must be positive")

        if self.http_timeout <= 0:
            errors.append("http_timeout must be positive")

        # Additional security-focused validations
        if self.cache_max_size > 100000:
            errors.append("cache_max_size too large (potential memory exhaustion)")

        if self.cache_ttl_seconds > 604800:  # 7 days
            errors.append("cache_ttl_seconds too large (potential stale data)")

        if self.github_api_timeout < 5:
            errors.append("github_api_timeout too small (minimum 5 seconds)")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {err}" for err in errors
            )
            raise ValueError(error_msg)


class SettingsManager:
    """Singleton manager for the global settings instance."""

    _instance: Optional["SettingsManager"] = None
    _settings: Settings | None = None

    def __new__(cls) -> "SettingsManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_settings(self, reload: bool = False) -> Settings:
        """Get application settings singleton.

        Args:
            reload: If True, reload settings from environment/files.

        Returns:
            Settings instance.

        Raises:
            ValueError: If settings are invalid.

        """
        if self._settings is None or reload:
            try:
                self._settings = Settings()
                self._settings.validate_startup()
                self._settings.configure_logging()
            except (ValueError, TypeError, OSError, ImportError) as e:
                raise ValueError(f"Failed to load configuration: {e}") from e

        return self._settings


# Global settings manager instance
_settings_manager = SettingsManager()


def get_settings(reload: bool = False) -> Settings:
    """Get application settings singleton.

    Args:
        reload: If True, reload settings from environment/files.

    Returns:
        Settings instance.

    Raises:
        ValueError: If settings are invalid.

    """
    return _settings_manager.get_settings(reload)


def validate_settings_on_startup() -> Settings:
    """Validate and configure settings during application startup.

    This function should be called early in the application lifecycle
    to ensure configuration is valid and logging is properly configured.

    Returns:
        Validated Settings instance.

    Raises:
        SystemExit: If configuration is critically invalid.

    """
    try:
        app_settings = get_settings(reload=True)
        logger = logging.getLogger("finos-ai-governance-mcp")
        logger.info("Configuration loaded successfully")
        logger.debug("Base URL: %s", app_settings.base_url)
        logger.debug("HTTP timeout: %ss", app_settings.http_timeout)
        logger.debug("Cache enabled: %s", app_settings.enable_cache)

        # Security status logging
        if app_settings.github_token:
            logger.info("GitHub token configured - enhanced rate limits active")
            logger.debug("Rate limiting: Enhanced mode (5000 requests/hour)")
        else:
            logger.warning(
                "No GitHub token configured - limited to 60 requests/hour. "
                "Consider adding FINOS_MCP_GITHUB_TOKEN for better reliability"
            )
        logger.debug("Debug mode: %s", app_settings.debug_mode)

        return app_settings

    except ValueError as e:
        # Print to stderr since logging might not be configured yet
        print(f"❌ Configuration Error: {e}", file=__import__("sys").stderr)
        print(
            "\n💡 Check your environment variables or .env file configuration.",
            file=__import__("sys").stderr,
        )
        print(
            "   Run with FINOS_MCP_DEBUG_MODE=true for more details.",
            file=__import__("sys").stderr,
        )
        raise SystemExit(1) from e
    except (RuntimeError, ImportError, OSError, MemoryError) as e:
        print(f"❌ Unexpected configuration error: {e}", file=__import__("sys").stderr)
        raise SystemExit(1) from e
