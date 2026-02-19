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
from typing import Literal, Optional
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
    mcp_transport: Literal["stdio", "http", "streamable-http", "sse"] = Field(
        default="stdio",
        description="MCP server transport mode",
    )
    mcp_host: str = Field(
        default="127.0.0.1",
        description="Host binding for HTTP/SSE transports",
    )
    mcp_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="Port binding for HTTP/SSE transports (1-65535)",
    )

    # MCP Authentication Configuration
    mcp_auth_enabled: bool = Field(
        default=False,
        description="Enable JWT authentication at the MCP server boundary",
    )
    mcp_auth_jwks_uri: str | None = Field(
        default=None,
        description="JWKS endpoint for JWT signature validation",
    )
    mcp_auth_public_key: str | None = Field(
        default=None,
        description="PEM-encoded public key for JWT validation (use instead of JWKS URI)",
    )
    mcp_auth_issuer: str | None = Field(
        default=None,
        description="Expected JWT issuer claim (iss)",
    )
    mcp_auth_audience: str | None = Field(
        default=None,
        description="Expected JWT audience claim (aud)",
    )
    mcp_auth_required_scopes: str | None = Field(
        default=None,
        description="Comma-separated required OAuth scopes (e.g. governance:read,governance:write)",
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

    # Cache Security
    cache_secret: str | None = Field(
        default=None,
        description=(
            "HMAC secret key for cache integrity verification (required in production). "
            "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
        ),
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

    @field_validator("mcp_auth_jwks_uri")
    @classmethod
    def validate_mcp_auth_jwks_uri(cls, v: str | None) -> str | None:
        """Validate optional JWKS URL when provided."""
        if v is None or v.strip() == "":
            return None
        parsed = urlparse(v.strip())
        if not parsed.scheme or parsed.scheme not in ["http", "https"]:
            raise ValueError("MCP auth JWKS URI must be a valid HTTP or HTTPS URL")
        if not parsed.netloc:
            raise ValueError("MCP auth JWKS URI must include a domain")
        return v.strip().rstrip("/")

    @field_validator("mcp_auth_required_scopes")
    @classmethod
    def validate_mcp_auth_required_scopes(cls, v: str | None) -> str | None:
        """Normalize optional comma-separated scope list."""
        if v is None:
            return None
        normalized = ",".join(scope.strip() for scope in v.split(",") if scope.strip())
        return normalized or None

    @field_validator("mcp_host")
    @classmethod
    def validate_mcp_host(cls, v: str) -> str:
        """Validate optional MCP host setting."""
        host = v.strip()
        if not host:
            raise ValueError("MCP host cannot be empty")
        return host

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
    def mcp_auth_scopes_list(self) -> list[str]:
        """Return auth required scopes as a normalized list."""
        if not self.mcp_auth_required_scopes:
            return []
        return [
            scope.strip()
            for scope in self.mcp_auth_required_scopes.split(",")
            if scope.strip()
        ]

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

        # Cache secret is required for HMAC integrity; validate at startup so
        # operators discover misconfigurations immediately rather than on first
        # cache operation.
        if not self.cache_secret:
            errors.append(
                "FINOS_MCP_CACHE_SECRET is required. "
                "Generate with: python -c 'import secrets; print(secrets.token_hex(32))'"
            )
        elif len(self.cache_secret) < 32:
            errors.append(
                "FINOS_MCP_CACHE_SECRET must be at least 32 characters. "
                f"Current length: {len(self.cache_secret)}"
            )

        if self.mcp_transport != "stdio":
            if not self.mcp_host:
                errors.append("mcp_host is required when mcp_transport is not stdio")
            if self.mcp_port < 1 or self.mcp_port > 65535:
                errors.append(
                    "mcp_port must be between 1 and 65535 for non-stdio transports"
                )

        if self.mcp_auth_enabled:
            if not self.mcp_auth_issuer:
                errors.append("mcp_auth_issuer is required when mcp_auth_enabled=true")
            if not self.mcp_auth_audience:
                errors.append(
                    "mcp_auth_audience is required when mcp_auth_enabled=true"
                )
            if not self.mcp_auth_jwks_uri and not self.mcp_auth_public_key:
                errors.append(
                    "Either mcp_auth_jwks_uri or mcp_auth_public_key is required when mcp_auth_enabled=true"
                )
            if self.mcp_auth_jwks_uri and self.mcp_auth_public_key:
                errors.append(
                    "Configure only one of mcp_auth_jwks_uri or mcp_auth_public_key (not both)"
                )

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
        logger.info("MCP transport: %s", app_settings.mcp_transport)
        if app_settings.mcp_transport != "stdio":
            logger.info(
                "MCP bind address: %s:%s", app_settings.mcp_host, app_settings.mcp_port
            )
        logger.info("MCP auth enabled: %s", app_settings.mcp_auth_enabled)
        if app_settings.mcp_auth_enabled:
            logger.info(
                "MCP auth issuer configured: %s", bool(app_settings.mcp_auth_issuer)
            )
            logger.info(
                "MCP auth audience configured: %s", bool(app_settings.mcp_auth_audience)
            )
            logger.info(
                "MCP auth required scopes: %s", app_settings.mcp_auth_scopes_list
            )

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
