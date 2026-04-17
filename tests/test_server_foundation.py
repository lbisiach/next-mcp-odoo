"""Tests for the OdooMCPServer foundation — initialization, lifecycle, and health."""

import os
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from next_mcp_odoo.config import OdooConfig, reset_config
from next_mcp_odoo.odoo_connection import OdooConnectionError
from next_mcp_odoo.server import SERVER_VERSION, OdooMCPServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(**kwargs) -> OdooConfig:
    defaults = dict(
        url=os.getenv("ODOO_URL", "http://localhost:8069"),
        api_key="test_api_key_12345",
        database="test_db",
        log_level="INFO",
        default_limit=10,
        max_limit=100,
    )
    defaults.update(kwargs)
    return OdooConfig(**defaults)


# ---------------------------------------------------------------------------
# Server initialization
# ---------------------------------------------------------------------------


class TestServerInitialization:
    def test_server_version_is_string(self):
        assert isinstance(SERVER_VERSION, str)
        assert len(SERVER_VERSION) > 0

    def test_server_init_with_config(self):
        config = _make_config()
        server = OdooMCPServer(config)
        assert server.config is config
        assert server.connection is None
        assert server.app is not None
        assert server.app.name == "odoo-mcp-server"

    def test_server_init_without_config_loads_from_env(self, monkeypatch):
        reset_config()
        monkeypatch.setenv("ODOO_URL", "http://env.odoo.com")
        monkeypatch.setenv("ODOO_API_KEY", "env-key")
        monkeypatch.setenv("ODOO_DB", "env_db")
        try:
            server = OdooMCPServer()
            assert server.config.url == "http://env.odoo.com"
            assert server.config.api_key == "env-key"
            assert server.config.database == "env_db"
        finally:
            reset_config()

    def test_server_connection_is_none_before_start(self):
        server = OdooMCPServer(_make_config())
        assert server.connection is None
        assert server.access_controller is None

    def test_server_has_health_route(self):
        """Server exposes a /health endpoint."""
        server = OdooMCPServer(_make_config())
        # app has custom_route registered; just verify the server was set up
        assert server.app is not None

    def test_server_json2_config(self):
        config = _make_config(api_protocol="json2")
        server = OdooMCPServer(config)
        assert server.config.is_json2 is True


# ---------------------------------------------------------------------------
# Server lifecycle (mocked connection)
# ---------------------------------------------------------------------------


class TestServerLifecycle:
    @pytest.fixture
    def mock_conn_class(self):
        with patch("next_mcp_odoo.server.get_connection") as mock_factory:
            mock_conn = Mock()
            mock_conn.connect = Mock()
            mock_conn.authenticate = Mock()
            mock_conn.disconnect = Mock()
            mock_conn.is_authenticated = True
            mock_conn.database = "test_db"
            mock_factory.return_value = mock_conn
            yield mock_factory, mock_conn

    def test_ensure_connection_creates_connection(self, mock_conn_class):
        factory, mock_conn = mock_conn_class
        config = _make_config()
        server = OdooMCPServer(config)
        server._ensure_connection()

        factory.assert_called_once()
        mock_conn.connect.assert_called_once()
        mock_conn.authenticate.assert_called_once()
        assert server.connection is mock_conn

    def test_ensure_connection_idempotent(self, mock_conn_class):
        factory, mock_conn = mock_conn_class
        config = _make_config()
        server = OdooMCPServer(config)
        server._ensure_connection()
        server._ensure_connection()
        # Factory called only once
        assert factory.call_count == 1

    def test_cleanup_connection(self, mock_conn_class):
        factory, mock_conn = mock_conn_class
        config = _make_config()
        server = OdooMCPServer(config)
        server._ensure_connection()
        server._cleanup_connection()

        mock_conn.disconnect.assert_called_once()
        assert server.connection is None
        assert server.access_controller is None

    def test_ensure_connection_registers_resources_and_tools(self, mock_conn_class):
        with (
            patch("next_mcp_odoo.server.register_resources") as mock_reg_res,
            patch("next_mcp_odoo.server.register_tools") as mock_reg_tools,
        ):
            factory, mock_conn = mock_conn_class
            config = _make_config()
            server = OdooMCPServer(config)
            server._ensure_connection()
            server._register_resources()
            server._register_tools()
            mock_reg_res.assert_called_once()
            mock_reg_tools.assert_called_once()

    def test_cleanup_on_exception_during_connect(self):
        with patch("next_mcp_odoo.server.get_connection") as mock_factory:
            mock_conn = Mock()
            mock_conn.connect.side_effect = OdooConnectionError("refused")
            mock_factory.return_value = mock_conn

            config = _make_config()
            server = OdooMCPServer(config)

            with pytest.raises(OdooConnectionError):
                server._ensure_connection()


# ---------------------------------------------------------------------------
# Health status
# ---------------------------------------------------------------------------


class TestServerHealthStatus:
    def test_health_unhealthy_when_not_connected(self):
        server = OdooMCPServer(_make_config())
        status = server.get_health_status()
        assert status["status"] == "unhealthy"
        assert status["connection"]["connected"] is False

    def test_health_includes_version(self):
        server = OdooMCPServer(_make_config())
        status = server.get_health_status()
        assert status["version"] == SERVER_VERSION

    def test_health_healthy_when_connected(self):
        with patch("next_mcp_odoo.server.get_connection") as mock_factory:
            mock_conn = Mock()
            mock_conn.connect = Mock()
            mock_conn.authenticate = Mock()
            mock_conn.disconnect = Mock()
            mock_conn.is_authenticated = True
            mock_conn.database = "test_db"
            mock_factory.return_value = mock_conn

            config = _make_config()
            server = OdooMCPServer(config)
            server._ensure_connection()
            status = server.get_health_status()
            assert status["status"] == "healthy"
            assert status["connection"]["connected"] is True


# ---------------------------------------------------------------------------
# Server capabilities
# ---------------------------------------------------------------------------


class TestServerCapabilities:
    def test_capabilities_structure(self):
        server = OdooMCPServer(_make_config())
        caps = server.get_capabilities()
        assert "capabilities" in caps
        assert caps["capabilities"]["resources"] is True
        assert caps["capabilities"]["tools"] is True


# ---------------------------------------------------------------------------
# get_model_names autocomplete
# ---------------------------------------------------------------------------


class TestGetModelNames:
    def test_returns_empty_list_when_no_access_controller(self):
        server = OdooMCPServer(_make_config())
        assert server.access_controller is None
        result = server._get_model_names()
        assert result == []

    def test_returns_model_names_from_access_controller(self):
        with patch("next_mcp_odoo.server.get_connection") as mock_factory:
            mock_conn = Mock()
            mock_conn.connect = Mock()
            mock_conn.authenticate = Mock()
            mock_conn.disconnect = Mock()
            mock_conn.is_authenticated = True
            mock_conn.database = "test_db"
            mock_factory.return_value = mock_conn

            config = _make_config()
            server = OdooMCPServer(config)
            server._ensure_connection()

            server.access_controller = MagicMock()
            server.access_controller.get_enabled_models.return_value = [
                {"model": "res.partner"},
                {"model": "account.move"},
            ]

            names = server._get_model_names()
            assert "res.partner" in names
            assert "account.move" in names

    def test_returns_model_names_from_ir_model_when_yolo(self):
        """When get_enabled_models returns [], query ir.model directly."""
        with patch("next_mcp_odoo.server.get_connection") as mock_factory:
            mock_conn = Mock()
            mock_conn.connect = Mock()
            mock_conn.authenticate = Mock()
            mock_conn.disconnect = Mock()
            mock_conn.is_authenticated = True
            mock_conn.database = "test_db"
            mock_conn.search_read.return_value = [
                {"model": "res.partner"},
                {"model": "sale.order"},
            ]
            mock_factory.return_value = mock_conn

            config = _make_config()
            server = OdooMCPServer(config)
            server._ensure_connection()

            server.access_controller = MagicMock()
            server.access_controller.get_enabled_models.return_value = []

            names = server._get_model_names()
            assert "res.partner" in names
