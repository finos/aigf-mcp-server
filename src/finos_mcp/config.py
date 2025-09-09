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
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic.types import PositiveInt
from pydantic_settings import BaseSettings


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
        description="HTTP client timeout in seconds",
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
        description="Maximum number of documents to cache in memory",
    )

    cache_ttl_seconds: PositiveInt = Field(
        default=3600,
        description="Default time-to-live for cached documents in seconds (1 hour)",
    )

    cache_cleanup_interval: PositiveInt = Field(
        default=60,
        description="Background cleanup interval for expired cache entries in seconds",
    )

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
        default="0.1.0-dev",
        description="MCP server version",
    )

    # GitHub API Configuration
    github_token: str | None = Field(
        default=None,
        description="GitHub personal access token for API access (optional, increases rate limits)",
    )

    # GitHub API Rate Limiting Configuration
    github_api_delay_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=60.0,
        description="Minimum delay between GitHub API requests (seconds)",
    )

    github_api_max_retries: PositiveInt = Field(
        default=3,
        le=10,
        description="Maximum number of retries for failed GitHub API requests",
    )

    github_api_backoff_factor: float = Field(
        default=2.0,
        ge=1.1,
        le=5.0,
        description="Exponential backoff factor for GitHub API retries",
    )

    github_api_rate_limit_buffer: PositiveInt = Field(
        default=10,
        le=100,
        description="Buffer of API calls to reserve when near rate limit",
    )

    # Custom Configuration File Path
    config_file: Path | None = Field(
        default=None,
        description="Path to additional configuration file",
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
        """Validate GitHub token format for security."""
        if v is None or v.strip() == "":
            return None

        # Basic format validation for GitHub personal access tokens
        token = v.strip()

        # Classic tokens start with 'ghp_' and are 40 characters total
        # Fine-grained tokens start with 'github_pat_' and are longer
        if token.startswith("ghp_"):
            if len(token) != 40:
                raise ValueError(
                    "GitHub classic token (ghp_) must be exactly 40 characters"
                )
            if not token[4:].replace("_", "").isalnum():
                raise ValueError("GitHub token contains invalid characters")
        elif token.startswith("github_pat_"):
            if len(token) < 50:  # Fine-grained tokens are longer
                raise ValueError("GitHub fine-grained token appears too short")
        else:
            raise ValueError(
                "GitHub token must start with 'ghp_' (classic) or 'github_pat_' (fine-grained). "
                "Create at: https://github.com/settings/tokens"
            )

        return token

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL is a proper HTTP/HTTPS URL."""
        parsed = urlparse(v)
        if not parsed.scheme or parsed.scheme not in ["http", "https"]:
            raise ValueError("Base URL must be a valid HTTP or HTTPS URL")
        if not parsed.netloc:
            raise ValueError("Base URL must include a domain")
        return v.rstrip("/")  # Remove trailing slash for consistency

    @field_validator("config_file", mode="before")
    @classmethod
    def validate_config_file(cls, v: str | None) -> Path | None:
        """Validate config file path exists if provided."""
        if v is None:
            return v

        path = Path(v) if isinstance(v, str) else v

        if not path.exists():
            raise ValueError(f"Configuration file does not exist: {path}")
        if not path.is_file():
            raise ValueError(f"Configuration path is not a file: {path}")

        return path

    @property
    def mitigations_url(self) -> str:
        """Get the full URL for mitigations directory."""
        return f"{self.base_url}/_mitigations"

    @property
    def risks_url(self) -> str:
        """Get the full URL for risks directory."""
        return f"{self.base_url}/_risks"

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
