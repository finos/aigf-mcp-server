"""
Unit tests for FINOS MCP Server configuration validation.

Tests the Pydantic settings validation, environment variable handling,
and startup validation with various configuration scenarios.
"""

import os
from typing import ClassVar
from unittest.mock import patch

import pytest
from pydantic import ValidationError

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

    # A test here starts as a fresh process does: no settings built yet.
    # validate_settings_on_startup() builds them once and no longer reloads
    # (#300), so a singleton left by an earlier test would be what it reads.
    from finos_mcp.config import _settings_manager

    held = _settings_manager._settings
    _settings_manager._settings = None

    yield

    _settings_manager._settings = held

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
            # What the fetch client refuses is refused here too (#298);
            # tests/unit/test_base_url_checked_at_startup.py lists those.
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
        # clean_env starts this test with no settings built.
        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance
        assert settings1 is settings2

    def test_get_settings_reload(self, clean_env):
        """Test get_settings reload functionality."""
        # clean_env starts this test with no settings built.
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
class TestNetworkTransportRequiresAuth:
    """Networked transports must not start unauthenticated (AIGF-F2, #20)."""

    NETWORK_TRANSPORTS: ClassVar[list[str]] = ["http", "streamable-http", "sse"]

    @staticmethod
    def _enable_auth():
        """Set a complete, valid JWT verifier configuration."""
        os.environ["FINOS_MCP_MCP_AUTH_ENABLED"] = "true"
        os.environ["FINOS_MCP_MCP_AUTH_ISSUER"] = "https://auth.example.com"
        os.environ["FINOS_MCP_MCP_AUTH_AUDIENCE"] = "finos-mcp-server"
        os.environ["FINOS_MCP_MCP_AUTH_JWKS_URI"] = (
            "https://auth.example.com/.well-known/jwks.json"
        )

    @pytest.mark.parametrize("transport", NETWORK_TRANSPORTS)
    def test_network_transport_without_auth_fails_startup(self, transport, clean_env):
        """Every networked transport is rejected when auth is disabled."""
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = transport

        with pytest.raises(SystemExit):
            validate_settings_on_startup()

    @pytest.mark.parametrize("transport", NETWORK_TRANSPORTS)
    def test_network_transport_with_auth_starts(self, transport, clean_env):
        """Auth configured is the supported way to run a networked transport."""
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = transport
        self._enable_auth()

        settings = validate_settings_on_startup()

        assert settings.mcp_transport == transport
        assert settings.mcp_auth_enabled is True

    @pytest.mark.parametrize("transport", NETWORK_TRANSPORTS)
    def test_insecure_override_permits_unauthenticated_transport(
        self, transport, clean_env
    ):
        """The documented development escape hatch works, on every transport."""
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = transport
        os.environ["FINOS_MCP_ALLOW_INSECURE_HTTP"] = "true"

        settings = validate_settings_on_startup()

        assert settings.mcp_transport == transport
        assert settings.mcp_auth_enabled is False
        assert settings.allow_insecure_http is True

    def test_stdio_without_auth_still_starts(self, clean_env):
        """Regression guard: stdio has no network boundary and must be unaffected."""
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = "stdio"

        settings = validate_settings_on_startup()

        assert settings.mcp_transport == "stdio"
        assert settings.mcp_auth_enabled is False
        assert settings.allow_insecure_http is False

    def test_default_configuration_still_starts(self, clean_env):
        """Regression guard: the default (no transport set) is stdio and unaffected."""
        settings = validate_settings_on_startup()

        assert settings.mcp_transport == "stdio"

    def test_error_message_names_both_environment_variables(self, clean_env):
        """A fail-fast message is only useful if it says how to fix it."""
        os.environ["FINOS_MCP_MCP_TRANSPORT"] = "http"

        with pytest.raises(ValueError) as exc_info:
            Settings().validate_startup()

        error_msg = str(exc_info.value)
        assert "FINOS_MCP_MCP_AUTH_ENABLED=true" in error_msg
        assert "FINOS_MCP_ALLOW_INSECURE_HTTP=true" in error_msg
        assert "http" in error_msg


@pytest.mark.unit
class TestTrustedProxyConfiguration:
    """Trusted-proxy allowlist parsing and validation (AIGF-F1, #21).

    An entry here is permission to believe a caller-supplied X-Forwarded-For
    header, which decides whose rate-limit bucket a request lands in. Anything
    that would let a caller choose their own bucket must fail at startup.
    """

    def test_unset_is_valid_and_yields_no_networks(self, clean_env):
        """The default ignores X-Forwarded-For entirely."""
        settings = validate_settings_on_startup()

        assert settings.dos_trusted_proxies is None
        assert settings.dos_trusted_proxy_entries == []
        assert settings.dos_trusted_proxy_networks == []

    def test_valid_cidrs_parse(self, clean_env):
        """A comma-separated list parses to networks, whitespace tolerated."""
        os.environ["FINOS_MCP_DOS_TRUSTED_PROXIES"] = "127.0.0.1/32, 10.0.0.0/8"

        settings = validate_settings_on_startup()

        assert settings.dos_trusted_proxy_entries == ["127.0.0.1/32", "10.0.0.0/8"]
        assert [str(net) for net in settings.dos_trusted_proxy_networks] == [
            "127.0.0.1/32",
            "10.0.0.0/8",
        ]

    def test_bare_address_is_accepted(self, clean_env):
        """A single host is the common case and should not require a /32."""
        os.environ["FINOS_MCP_DOS_TRUSTED_PROXIES"] = "127.0.0.1"

        settings = validate_settings_on_startup()

        assert [str(net) for net in settings.dos_trusted_proxy_networks] == [
            "127.0.0.1/32"
        ]

    def test_ipv6_cidr_is_accepted(self, clean_env):
        """IPv6 proxies are as real as IPv4 ones."""
        os.environ["FINOS_MCP_DOS_TRUSTED_PROXIES"] = "::1/128, fd00::/8"

        settings = validate_settings_on_startup()

        assert len(settings.dos_trusted_proxy_networks) == 2

    def test_malformed_entry_fails_startup(self, clean_env):
        """A typo must not silently drop a proxy from the allowlist."""
        os.environ["FINOS_MCP_DOS_TRUSTED_PROXIES"] = "127.0.0.1/32, not-a-cidr"

        with pytest.raises(ValueError) as exc_info:
            Settings().validate_startup()

        assert "not-a-cidr" in str(exc_info.value)

    @pytest.mark.parametrize("catch_all", ["0.0.0.0/0", "::/0"])
    def test_catch_all_range_fails_startup(self, catch_all, clean_env):
        """Trusting every address would let any caller forge its own bucket."""
        os.environ["FINOS_MCP_DOS_TRUSTED_PROXIES"] = catch_all

        with pytest.raises(ValueError) as exc_info:
            Settings().validate_startup()

        error_msg = str(exc_info.value)
        assert catch_all in error_msg
        assert "FINOS_MCP_DOS_TRUSTED_PROXIES" in error_msg

    def test_catch_all_rejected_even_alongside_valid_entries(self, clean_env):
        """A catch-all is not redeemed by specific entries sitting next to it."""
        os.environ["FINOS_MCP_DOS_TRUSTED_PROXIES"] = "127.0.0.1/32, 0.0.0.0/0"

        with pytest.raises(ValueError):
            Settings().validate_startup()


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
        assert (
            "Base URL 'not-a-url' is refused: documents are fetched over https only"
            in (error_msg)
        )

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
