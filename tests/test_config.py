"""Tests for the configuration module — including JSON-2 and execute_level additions."""

import os
import tempfile
from pathlib import Path
from typing import Literal

import pytest

from next_mcp_odoo.config import OdooConfig, get_config, load_config, reset_config, set_config


@pytest.fixture(autouse=True)
def reset_config_fixture():
    """Reset the config singleton before and after each test."""
    reset_config()
    yield
    reset_config()


# ---------------------------------------------------------------------------
# Basic OdooConfig validation
# ---------------------------------------------------------------------------


class TestOdooConfig:
    """Tests for OdooConfig field validation."""

    def test_valid_config_with_api_key(self):
        config = OdooConfig(url="http://localhost:8069", api_key="test-api-key")
        assert config.api_key == "test-api-key"
        assert config.uses_api_key is True
        assert config.uses_credentials is False

    def test_valid_config_with_credentials(self):
        config = OdooConfig(
            url="https://odoo.example.com",
            username="testuser",
            password="testpass",
            database="test_db",
        )
        assert config.uses_api_key is False
        assert config.uses_credentials is True

    def test_missing_url_raises_error(self):
        with pytest.raises(ValueError, match="ODOO_URL is required"):
            OdooConfig(url="", api_key="test-key")

    def test_invalid_url_format_raises_error(self):
        with pytest.raises(ValueError, match="ODOO_URL must start with http"):
            OdooConfig(url="invalid-url", api_key="test-key")

    def test_missing_authentication_raises_error(self):
        with pytest.raises(ValueError, match="Authentication required"):
            OdooConfig(url="http://localhost:8069")

    def test_incomplete_credentials_raises_error(self):
        with pytest.raises(ValueError, match="Authentication required"):
            OdooConfig(url="http://localhost:8069", username="user")

    def test_invalid_default_limit(self):
        with pytest.raises(ValueError, match="ODOO_MCP_DEFAULT_LIMIT must be positive"):
            OdooConfig(url="http://localhost:8069", api_key="test-key", default_limit=0)

    def test_invalid_max_limit(self):
        with pytest.raises(ValueError, match="ODOO_MCP_MAX_LIMIT must be positive"):
            OdooConfig(url="http://localhost:8069", api_key="test-key", max_limit=-1)

    def test_default_exceeds_max_limit(self):
        with pytest.raises(ValueError, match="cannot exceed ODOO_MCP_MAX_LIMIT"):
            OdooConfig(
                url="http://localhost:8069", api_key="test-key", default_limit=100, max_limit=50
            )

    def test_invalid_log_level(self):
        with pytest.raises(ValueError, match="Invalid log level"):
            OdooConfig(url="http://localhost:8069", api_key="test-key", log_level="INVALID")

    def test_log_level_case_insensitive(self):
        config = OdooConfig(url="http://localhost:8069", api_key="test-key", log_level="debug")
        assert config.log_level == "debug"


# ---------------------------------------------------------------------------
# JSON-2 protocol field
# ---------------------------------------------------------------------------


class TestApiProtocolConfig:
    """Tests for the api_protocol configuration field."""

    def test_default_protocol_is_xmlrpc(self):
        config = OdooConfig(url="http://localhost:8069", api_key="test-key")
        assert config.api_protocol == "xmlrpc"
        assert config.is_json2 is False

    def test_json2_protocol_requires_api_key(self):
        with pytest.raises(ValueError, match="JSON-2 protocol requires an API key"):
            OdooConfig(
                url="http://localhost:8069",
                username="admin",
                password="admin",
                database="db",
                api_protocol="json2",
            )

    def test_json2_protocol_with_api_key_succeeds(self):
        config = OdooConfig(
            url="http://localhost:8069",
            api_key="test-key",
            api_protocol="json2",
        )
        assert config.api_protocol == "json2"
        assert config.is_json2 is True

    def test_invalid_api_protocol_raises_error(self):
        with pytest.raises(ValueError, match="Invalid API protocol"):
            OdooConfig(
                url="http://localhost:8069",
                api_key="test-key",
                api_protocol="grpc",  # type: ignore[arg-type]
            )

    def test_xmlrpc_protocol_explicit(self):
        config = OdooConfig(
            url="http://localhost:8069", api_key="test-key", api_protocol="xmlrpc"
        )
        assert config.api_protocol == "xmlrpc"
        assert config.is_json2 is False


# ---------------------------------------------------------------------------
# execute_level field
# ---------------------------------------------------------------------------


class TestExecuteLevelConfig:
    """Tests for the execute_level configuration field."""

    def test_default_execute_level_is_business(self):
        config = OdooConfig(url="http://localhost:8069", api_key="test-key")
        assert config.execute_level == "business"

    def test_execute_level_safe(self):
        config = OdooConfig(
            url="http://localhost:8069", api_key="test-key", execute_level="safe"
        )
        assert config.execute_level == "safe"

    def test_execute_level_admin(self):
        config = OdooConfig(
            url="http://localhost:8069", api_key="test-key", execute_level="admin"
        )
        assert config.execute_level == "admin"

    def test_invalid_execute_level_raises_error(self):
        with pytest.raises(ValueError, match="Invalid execute"):
            OdooConfig(
                url="http://localhost:8069",
                api_key="test-key",
                execute_level="superadmin",  # type: ignore[arg-type]
            )

    def test_execute_level_from_env(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://localhost:8069")
        monkeypatch.setenv("ODOO_API_KEY", "test-key")
        monkeypatch.setenv("ODOO_EXECUTE_LEVEL", "admin")
        config = load_config()
        assert config.execute_level == "admin"

    def test_api_protocol_from_env(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://localhost:8069")
        monkeypatch.setenv("ODOO_API_KEY", "test-key")
        monkeypatch.setenv("ODOO_API_PROTOCOL", "json2")
        config = load_config()
        assert config.api_protocol == "json2"
        assert config.is_json2 is True


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_config_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://test.odoo.com")
        monkeypatch.setenv("ODOO_API_KEY", "env-api-key")
        monkeypatch.setenv("ODOO_DB", "test_db")
        monkeypatch.setenv("ODOO_MCP_LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("ODOO_MCP_DEFAULT_LIMIT", "20")
        monkeypatch.setenv("ODOO_MCP_MAX_LIMIT", "200")

        config = load_config()

        assert config.url == "http://test.odoo.com"
        assert config.api_key == "env-api-key"
        assert config.database == "test_db"
        assert config.log_level == "DEBUG"
        assert config.default_limit == 20
        assert config.max_limit == 200

    def test_load_config_from_env_file(self, monkeypatch):
        for key in [
            "ODOO_URL", "ODOO_API_KEY", "ODOO_USER", "ODOO_PASSWORD",
            "ODOO_MCP_DEFAULT_LIMIT", "ODOO_MCP_MAX_LIMIT", "ODOO_API_PROTOCOL",
        ]:
            monkeypatch.delenv(key, raising=False)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("ODOO_URL=http://file.odoo.com\n")
            f.write("ODOO_USER=fileuser\n")
            f.write("ODOO_PASSWORD=filepass\n")
            f.write("ODOO_MCP_DEFAULT_LIMIT=30\n")
            env_file = f.name

        try:
            config = load_config(Path(env_file))
            assert config.url == "http://file.odoo.com"
            assert config.username == "fileuser"
            assert config.password == "filepass"
            assert config.default_limit == 30
        finally:
            os.unlink(env_file)

    def test_env_vars_override_env_file(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://env.odoo.com")
        monkeypatch.setenv("ODOO_API_KEY", "env-key")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("ODOO_URL=http://file.odoo.com\n")
            f.write("ODOO_API_KEY=file-key\n")
            env_file = f.name

        try:
            config = load_config(Path(env_file))
            assert config.url == "http://env.odoo.com"
            assert config.api_key == "env-key"
        finally:
            os.unlink(env_file)

    def test_load_config_invalid_integer(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://localhost:8069")
        monkeypatch.setenv("ODOO_API_KEY", "test-key")
        monkeypatch.setenv("ODOO_MCP_DEFAULT_LIMIT", "not-a-number")
        with pytest.raises(ValueError, match="must be a valid integer"):
            load_config()

    def test_load_config_with_empty_strings(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://localhost:8069")
        monkeypatch.setenv("ODOO_API_KEY", "  ")
        monkeypatch.setenv("ODOO_USER", "user")
        monkeypatch.setenv("ODOO_PASSWORD", "pass")
        monkeypatch.setenv("ODOO_DB", "")
        monkeypatch.setenv("ODOO_API_PROTOCOL", "xmlrpc")

        config = load_config()

        assert config.api_key is None
        assert config.database is None
        assert config.uses_credentials is True


# ---------------------------------------------------------------------------
# Config singleton
# ---------------------------------------------------------------------------


class TestConfigSingleton:
    """Tests for get_config / set_config / reset_config."""

    def test_get_config_loads_once(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("ODOO_URL", "http://singleton.odoo.com")
        monkeypatch.setenv("ODOO_API_KEY", "singleton-key")

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2
        assert config1.url == "http://singleton.odoo.com"

    def test_set_config(self):
        reset_config()
        custom_config = OdooConfig(url="http://custom.odoo.com", api_key="custom-key")
        set_config(custom_config)
        assert get_config() is custom_config

    def test_reset_config(self, monkeypatch):
        monkeypatch.setenv("ODOO_URL", "http://first.odoo.com")
        monkeypatch.setenv("ODOO_API_KEY", "first-key")
        config1 = get_config()

        reset_config()
        monkeypatch.setenv("ODOO_URL", "http://second.odoo.com")
        monkeypatch.setenv("ODOO_API_KEY", "second-key")
        config2 = get_config()

        assert config1 is not config2
        assert config2.url == "http://second.odoo.com"


# ---------------------------------------------------------------------------
# YOLO mode
# ---------------------------------------------------------------------------


class TestYoloMode:
    """Tests for YOLO mode (XML-RPC legacy mode)."""

    def test_yolo_mode_default_off(self):
        config = OdooConfig(url="http://localhost:8069", api_key="test")
        assert config.yolo_mode == "off"
        assert config.is_yolo_enabled is False
        assert config.is_write_allowed is False

    def test_yolo_mode_read_only(self):
        config = OdooConfig(
            url="http://localhost:8069", username="admin", password="admin", yolo_mode="read"
        )
        assert config.is_yolo_enabled is True
        assert config.is_write_allowed is False

    def test_yolo_mode_full_access(self):
        config = OdooConfig(
            url="http://localhost:8069", username="admin", password="admin", yolo_mode="true"
        )
        assert config.is_yolo_enabled is True
        assert config.is_write_allowed is True

    def test_invalid_yolo_mode(self):
        with pytest.raises(ValueError, match="Invalid YOLO mode"):
            OdooConfig(
                url="http://localhost:8069",
                username="admin",
                password="admin",
                yolo_mode="invalid",
            )

    def test_yolo_mode_auth_requirements(self):
        # YOLO mode without username should fail
        with pytest.raises(ValueError, match="YOLO mode requires"):
            OdooConfig(
                url="http://localhost:8069",
                api_key="test-key",
                yolo_mode="read",
            )

    def test_json2_and_yolo_incompatible(self):
        """JSON-2 and YOLO mode should not be used together."""
        with pytest.raises(ValueError):
            OdooConfig(
                url="http://localhost:8069",
                api_key="test-key",
                username="admin",
                api_protocol="json2",
                yolo_mode="true",
            )
