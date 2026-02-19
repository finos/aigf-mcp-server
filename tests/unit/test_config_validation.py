"""
Unit tests for FINOS MCP Server configuration validation.

Tests the Pydantic settings validation, environment variable handling,
and startup validation with various configuration scenarios.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from finos_mcp._version import __version__
from finos_mcp.config import Settings, get_settings, validate_settings_on_startup


@pytest.fixture
def clean_env():
    """Clean environment fixture that removes FINOS_MCP_ variables."""
    original_env = {}
    # Save original environment variables
    for key in os.environ.keys():
        if key.startswith("FINOS_MCP_"):
            original_env[key] = os.environ[key]

    # Clear FINOS_MCP_ variables
    for key in list(os.environ.keys()):
        if key.startswith("FINOS_MCP_"):
            del os.environ[key]

    # Required for startup validation after S-02 hardening.
    os.environ["FINOS_MCP_CACHE_SECRET"] = (
        "test_cache_secret_for_config_validation_32chars"
    )

    yield

    # Restore original environment
    for key in list(os.environ.keys()):
        if key.startswith("FINOS_MCP_"):
            del os.environ[key]

    for key, value in original_env.items():
        os.environ[key] = value


@pytest.mark.unit
class TestSettingsValidation:
    """Test Settings class validation."""

    def test_default_settings(self, clean_env):
        """Test that default settings are valid."""
        settings = Settings()

        assert settings.log_level == "INFO"
        assert settings.http_timeout == 30
        assert (
            settings.base_url
            == "https://raw.githubusercontent.com/finos/ai-governance-framework/main/docs"
        )
        assert settings.enable_cache is True
        assert settings.cache_max_size == 1000
        assert settings.debug_mode is False
        assert settings.server_name == "finos-ai-governance"
        assert settings.server_version == __version__
        assert settings.mcp_transport == "stdio"
        assert settings.mcp_host == "127.0.0.1"
        assert settings.mcp_port == 8000
        assert settings.mcp_auth_enabled is False
        assert settings.mcp_auth_scopes_list == []
        # config_file field removed from Settings model

    def test_environment_variable_override(self, clean_env):
        """Test that environment variables override defaults."""
        os.environ["FINOS_MCP_LOG_LEVEL"] = "DEBUG"
        os.environ["FINOS_MCP_HTTP_TIMEOUT"] = "60"
        os.environ["FINOS_MCP_ENABLE_CACHE"] = "false"
        os.environ["FINOS_MCP_DEBUG_MODE"] = "true"
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = "http"
        os.environ["FINOS_MCP_MCP_HOST"] = "127.0.0.2"
        os.environ["FINOS_MCP_MCP_PORT"] = "18000"

        settings = Settings()

        assert settings.log_level == "DEBUG"
        assert settings.http_timeout == 60
        assert settings.enable_cache is False
        assert settings.debug_mode is True
        assert settings.mcp_transport == "http"
        assert settings.mcp_host == "127.0.0.2"
        assert settings.mcp_port == 18000

    def test_transport_validation_invalid_value(self, clean_env):
        """Test invalid MCP transport value is rejected."""
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = "grpc"
        with pytest.raises(ValidationError):
            Settings()

    def test_mcp_host_validation_invalid_empty(self, clean_env):
        """Test empty MCP host is rejected."""
        os.environ["FINOS_MCP_MCP_HOST"] = "   "
        with pytest.raises(ValidationError):
            Settings()

    def test_log_level_validation_valid(self, clean_env):
        """Test valid log levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in valid_levels:
            os.environ["FINOS_MCP_LOG_LEVEL"] = level
            settings = Settings()
            assert settings.log_level == level.upper()
            del os.environ["FINOS_MCP_LOG_LEVEL"]

    def test_log_level_validation_invalid(self, clean_env):
        """Test invalid log levels are rejected."""
        os.environ["FINOS_MCP_LOG_LEVEL"] = "INVALID"

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error = exc_info.value.errors()[0]
        assert error["type"] == "value_error"
        assert "Log level must be one of" in str(error["ctx"]["error"])

    def test_log_level_case_insensitive(self, clean_env):
        """Test log level validation is case insensitive."""
        os.environ["FINOS_MCP_LOG_LEVEL"] = "debug"
        settings = Settings()
        assert settings.log_level == "DEBUG"

    def test_base_url_validation_valid(self, clean_env):
        """Test valid base URLs."""
        valid_urls = [
            "https://example.com",
            "https://raw.githubusercontent.com/user/repo/main/docs",
        ]

        for url in valid_urls:
            os.environ["FINOS_MCP_BASE_URL"] = url
            settings = Settings()
            assert settings.base_url == url
            del os.environ["FINOS_MCP_BASE_URL"]

    def test_base_url_validation_invalid(self, clean_env):
        """Test invalid base URLs are rejected."""
        invalid_urls = [
            "not-a-url",
            "ftp://example.com",
            "https://",
            "",
            "file:///local/path",
            # Note: localhost URLs are now allowed for development
        ]

        for url in invalid_urls:
            os.environ["FINOS_MCP_BASE_URL"] = url
            with pytest.raises(ValidationError) as exc_info:
                Settings()

            error = exc_info.value.errors()[0]
            assert error["type"] == "value_error"
            del os.environ["FINOS_MCP_BASE_URL"]

    def test_base_url_trailing_slash_removal(self, clean_env):
        """Test trailing slashes are removed from base URL."""
        os.environ["FINOS_MCP_BASE_URL"] = "https://example.com/"
        settings = Settings()
        assert settings.base_url == "https://example.com"

    def test_auth_scope_list_normalization(self, clean_env):
        """Test MCP auth scope normalization and parsing."""
        os.environ["FINOS_MCP_MCP_AUTH_REQUIRED_SCOPES"] = (
            " governance:read, governance:write ,, "
        )
        settings = Settings()
        assert settings.mcp_auth_required_scopes == "governance:read,governance:write"
        assert settings.mcp_auth_scopes_list == ["governance:read", "governance:write"]

    def test_auth_enabled_requires_required_fields(self, clean_env):
        """Test auth-enabled startup validation fails without required settings."""
        os.environ["FINOS_MCP_MCP_AUTH_ENABLED"] = "true"
        with pytest.raises(SystemExit):
            validate_settings_on_startup()

    def test_auth_enabled_with_jwks(self, clean_env):
        """Test auth-enabled configuration with JWKS URI."""
        os.environ["FINOS_MCP_MCP_AUTH_ENABLED"] = "true"
        os.environ["FINOS_MCP_MCP_AUTH_JWKS_URI"] = (
            "https://auth.example.com/.well-known/jwks.json"
        )
        os.environ["FINOS_MCP_MCP_AUTH_ISSUER"] = "https://auth.example.com"
        os.environ["FINOS_MCP_MCP_AUTH_AUDIENCE"] = "finos-mcp-server"

        settings = Settings()
        assert settings.mcp_auth_enabled is True
        assert (
            settings.mcp_auth_jwks_uri
            == "https://auth.example.com/.well-known/jwks.json"
        )
        assert settings.mcp_auth_issuer == "https://auth.example.com"
        assert settings.mcp_auth_audience == "finos-mcp-server"

    def test_auth_enabled_rejects_jwks_and_public_key_together(self, clean_env):
        """Test startup validation rejects conflicting verifier config."""
        os.environ["FINOS_MCP_MCP_AUTH_ENABLED"] = "true"
        os.environ["FINOS_MCP_MCP_AUTH_JWKS_URI"] = "https://auth.example.com/jwks"
        os.environ["FINOS_MCP_MCP_AUTH_PUBLIC_KEY"] = (
            "-----BEGIN PUBLIC KEY-----\\nabc\\n-----END PUBLIC KEY-----"
        )
        os.environ["FINOS_MCP_MCP_AUTH_ISSUER"] = "https://auth.example.com"
        os.environ["FINOS_MCP_MCP_AUTH_AUDIENCE"] = "finos-mcp-server"

        with pytest.raises(SystemExit):
            validate_settings_on_startup()

    def test_http_timeout_validation(self, clean_env):
        """Test HTTP timeout validation."""
        # Valid positive integer
        os.environ["FINOS_MCP_HTTP_TIMEOUT"] = "60"
        settings = Settings()
        assert settings.http_timeout == 60

        # Invalid negative
        os.environ["FINOS_MCP_HTTP_TIMEOUT"] = "-1"
        with pytest.raises(ValidationError):
            Settings()

        # Invalid zero
        os.environ["FINOS_MCP_HTTP_TIMEOUT"] = "0"
        with pytest.raises(ValidationError):
            Settings()

    def test_cache_max_size_validation(self, clean_env):
        """Test cache max size validation."""
        # Valid positive integer
        os.environ["FINOS_MCP_CACHE_MAX_SIZE"] = "5000"
        settings = Settings()
        assert settings.cache_max_size == 5000

        # Invalid negative
        os.environ["FINOS_MCP_CACHE_MAX_SIZE"] = "-1"
        with pytest.raises(ValidationError):
            Settings()

        # Invalid zero
        os.environ["FINOS_MCP_CACHE_MAX_SIZE"] = "0"
        with pytest.raises(ValidationError):
            Settings()

    # Config file tests removed - functionality no longer exists


@pytest.mark.unit
class TestSettingsProperties:
    """Test Settings derived properties."""

    def test_mitigations_url(self, clean_env):
        """Test mitigations URL property."""
        settings = Settings()
        expected = f"{settings.base_url}/_mitigations"
        assert settings.mitigations_url == expected

    def test_risks_url(self, clean_env):
        """Test risks URL property."""
        settings = Settings()
        expected = f"{settings.base_url}/_risks"
        assert settings.risks_url == expected

    def test_logging_config_normal_mode(self, clean_env):
        """Test logging configuration in normal mode."""
        settings = Settings()
        config = settings.logging_config

        assert "level" in config
        assert "format" in config
        assert "datefmt" not in config or config["datefmt"] is None

    def test_logging_config_debug_mode(self, clean_env):
        """Test logging configuration in debug mode."""
        os.environ["FINOS_MCP_DEBUG_MODE"] = "true"
        settings = Settings()
        config = settings.logging_config

        assert "level" in config
        assert "format" in config
        assert "datefmt" in config
        assert config["datefmt"] is not None


@pytest.mark.unit
class TestStartupValidation:
    """Test startup validation functions."""

    def test_startup_validation_success(self, clean_env):
        """Test successful startup validation."""
        # Should not raise any exceptions
        settings = validate_settings_on_startup()
        assert isinstance(settings, Settings)

    def test_startup_validation_invalid_config(self, clean_env):
        """Test startup validation with invalid configuration."""
        os.environ["FINOS_MCP_BASE_URL"] = "invalid-url"

        with pytest.raises(SystemExit):
            validate_settings_on_startup()

    def test_get_settings_singleton(self, clean_env):
        """Test that get_settings returns singleton."""
        # Reset global settings
        from finos_mcp import config

        config.settings = None

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance
        assert settings1 is settings2

    def test_get_settings_reload(self, clean_env):
        """Test get_settings reload functionality."""
        from finos_mcp import config

        config.settings = None

        # Get initial settings
        settings1 = get_settings()

        # Change environment and reload
        os.environ["FINOS_MCP_LOG_LEVEL"] = "DEBUG"
        settings2 = get_settings(reload=True)

        # Should be different instances with different values
        assert settings1 is not settings2
        assert settings1.log_level == "INFO"
        assert settings2.log_level == "DEBUG"

    @patch("finos_mcp.config.logging.basicConfig")
    def test_configure_logging_called(self, mock_basic_config, clean_env):
        """Test that logging configuration is called during startup."""
        validate_settings_on_startup()
        mock_basic_config.assert_called_once()

    def test_startup_validation_with_custom_values(self, clean_env):
        """Test startup validation with various custom values."""
        os.environ["FINOS_MCP_LOG_LEVEL"] = "WARNING"
        os.environ["FINOS_MCP_HTTP_TIMEOUT"] = "120"
        os.environ["FINOS_MCP_BASE_URL"] = "https://custom.example.com/docs"
        os.environ["FINOS_MCP_ENABLE_CACHE"] = "false"
        os.environ["FINOS_MCP_DEBUG_MODE"] = "true"

        settings = validate_settings_on_startup()

        assert settings.log_level == "WARNING"
        assert settings.http_timeout == 120
        assert settings.base_url == "https://custom.example.com/docs"
        assert settings.enable_cache is False
        assert settings.debug_mode is True


@pytest.mark.unit
class TestConfigValidationErrorMessages:
    """Test configuration error message quality."""

    def test_helpful_error_message_invalid_log_level(self, clean_env):
        """Test helpful error message for invalid log level."""
        os.environ["FINOS_MCP_LOG_LEVEL"] = "INVALID"

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_msg = str(exc_info.value)
        assert "Log level must be one of" in error_msg
        assert "DEBUG" in error_msg
        assert "INFO" in error_msg
        assert "WARNING" in error_msg

    def test_helpful_error_message_invalid_url(self, clean_env):
        """Test helpful error message for invalid URL."""
        os.environ["FINOS_MCP_BASE_URL"] = "not-a-url"

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_msg = str(exc_info.value)
        assert "Base URL must be a valid HTTP or HTTPS URL" in error_msg

    def test_startup_validation_error_handling(self, clean_env):
        """Test startup validation error handling and messages."""
        os.environ["FINOS_MCP_LOG_LEVEL"] = "INVALID"

        with patch("sys.stderr") as mock_stderr:
            with pytest.raises(SystemExit):
                validate_settings_on_startup()

        # Should have printed helpful error message
        assert mock_stderr.write.called
        stderr_output = "".join(call[0][0] for call in mock_stderr.write.call_args_list)
        assert "Configuration Error" in stderr_output
        assert "Check your environment variables" in stderr_output
