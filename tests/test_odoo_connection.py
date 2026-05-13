"""Tests for XML-RPC OdooConnection infrastructure.

Unit tests mock urllib; integration tests require a running Odoo server.
"""

import os
import socket
import xmlrpc.client
from unittest.mock import MagicMock, patch

import pytest

from next_mcp_odoo.config import OdooConfig
from next_mcp_odoo.odoo_connection import OdooConnection, OdooConnectionError, get_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**kwargs) -> OdooConfig:
    defaults = dict(
        url=os.getenv("ODOO_URL", "http://localhost:8069"),
        api_key=os.getenv("ODOO_API_KEY", "test-key"),
        database=os.getenv("ODOO_DB", "test_db"),
        log_level="INFO",
        default_limit=10,
        max_limit=100,
    )
    defaults.update(kwargs)
    return OdooConfig(**defaults)


# ---------------------------------------------------------------------------
# OdooConnection initialization
# ---------------------------------------------------------------------------


class TestOdooConnectionInit:
    def test_init_valid_config(self):
        config = _config()
        conn = OdooConnection(config)
        assert conn.config is config
        assert conn.timeout == OdooConnection.DEFAULT_TIMEOUT
        assert not conn.is_connected

    def test_init_custom_timeout(self):
        conn = OdooConnection(_config(), timeout=60)
        assert conn.timeout == 60

    def test_url_parsed_http(self):
        conn = OdooConnection(_config(url="http://myodoo.com:8069"))
        assert conn._url_components["host"] == "myodoo.com"
        assert conn._url_components["port"] == 8069
        assert conn._url_components["scheme"] == "http"

    def test_url_parsed_https(self):
        conn = OdooConnection(_config(url="https://secure.odoo.com"))
        assert conn._url_components["scheme"] == "https"
        assert conn._url_components["port"] == 443

    def test_url_parsed_http_default_port(self):
        conn = OdooConnection(_config(url="http://myodoo.com"))
        assert conn._url_components["port"] == 80

    def test_not_connected_after_init(self):
        conn = OdooConnection(_config())
        assert conn.is_connected is False
        assert conn.is_authenticated is False


# ---------------------------------------------------------------------------
# OdooConnection disconnect
# ---------------------------------------------------------------------------


class TestOdooConnectionDisconnect:
    def test_disconnect_when_not_connected_logs_warning(self, caplog):
        conn = OdooConnection(_config())
        conn.disconnect()
        assert "Not connected" in caplog.text


# ---------------------------------------------------------------------------
# get_connection factory
# ---------------------------------------------------------------------------


class TestGetConnectionFactory:
    def test_factory_defaults_to_xmlrpc(self):
        config = _config()
        conn = get_connection(config)
        assert isinstance(conn, OdooConnection)

    def test_factory_returns_json2_when_protocol_set(self):
        from next_mcp_odoo.json2_connection import OdooJson2Connection

        config = _config(api_protocol="json2")
        conn = get_connection(config)
        assert isinstance(conn, OdooJson2Connection)

    def test_factory_passes_timeout_to_xmlrpc(self):
        config = _config()
        conn = get_connection(config, timeout=45)
        assert conn.timeout == 45

    def test_factory_passes_timeout_to_json2(self):
        from next_mcp_odoo.json2_connection import OdooJson2Connection

        config = _config(api_protocol="json2")
        conn = get_connection(config, timeout=45)
        assert conn.timeout == 45

    def test_factory_accepts_performance_manager(self):
        from next_mcp_odoo.performance import PerformanceManager

        config = _config()
        pm = PerformanceManager(config)
        conn = get_connection(config, performance_manager=pm)
        assert isinstance(conn, OdooConnection)


# ---------------------------------------------------------------------------
# Locale retry behaviour
# ---------------------------------------------------------------------------


class TestLocaleRetry:
    """execute_kw must handle the invalid-locale fault path without mutating config."""

    def _make_conn(self, locale="es_AR") -> OdooConnection:
        conn = OdooConnection(_config(locale=locale))
        conn._authenticated = True
        conn._connected = True
        conn._uid = 1
        conn._database = "test_db"
        conn._auth_method = "api_key"
        conn._locale_disabled = False
        return conn

    def _locale_fault(self):
        f = xmlrpc.client.Fault(1, "Invalid language code: es_AR")
        return f

    def test_locale_injected_in_context(self):
        conn = self._make_conn()
        proxy = MagicMock()
        proxy.execute_kw.return_value = []
        conn._object_proxy = proxy

        conn.execute_kw("res.partner", "search_read", [[]], {})

        call_kwargs = proxy.execute_kw.call_args[0][6]
        assert call_kwargs.get("context", {}).get("lang") == "es_AR"

    def test_invalid_locale_retries_without_lang(self):
        conn = self._make_conn()
        proxy = MagicMock()
        proxy.execute_kw.side_effect = [self._locale_fault(), [{"id": 1}]]
        conn._object_proxy = proxy

        result = conn.execute_kw("res.partner", "search_read", [[]], {})

        assert result == [{"id": 1}]
        assert conn._locale_disabled is True
        # config must NOT be mutated
        assert conn.config.locale == "es_AR"
        # second call must not include lang
        second_kwargs = proxy.execute_kw.call_args[0][6]
        assert "lang" not in second_kwargs.get("context", {})

    def test_invalid_locale_retry_timeout_raises_odoo_error(self):
        conn = self._make_conn()
        proxy = MagicMock()
        proxy.execute_kw.side_effect = [self._locale_fault(), socket.timeout()]
        conn._object_proxy = proxy

        with pytest.raises(OdooConnectionError, match="timeout"):
            conn.execute_kw("res.partner", "search_read", [[]], {})

    def test_invalid_locale_retry_generic_exception_raises_odoo_error(self):
        conn = self._make_conn()
        proxy = MagicMock()
        proxy.execute_kw.side_effect = [self._locale_fault(), OSError("network gone")]
        conn._object_proxy = proxy

        with pytest.raises(OdooConnectionError, match="Operation failed"):
            conn.execute_kw("res.partner", "search_read", [[]], {})

    def test_locale_disabled_skips_injection_on_subsequent_calls(self):
        conn = self._make_conn()
        conn._locale_disabled = True
        proxy = MagicMock()
        proxy.execute_kw.return_value = []
        conn._object_proxy = proxy

        conn.execute_kw("res.partner", "search_read", [[]], {})

        call_kwargs = proxy.execute_kw.call_args[0][6]
        assert "lang" not in call_kwargs.get("context", {})


# ---------------------------------------------------------------------------
# Integration tests — XML-RPC against live Odoo
# ---------------------------------------------------------------------------


@pytest.mark.yolo
class TestOdooConnectionIntegration:
    """Integration tests — require a running Odoo server with XML-RPC MCP module."""

    @pytest.fixture(autouse=True)
    def skip_if_json2(self):
        """Skip XML-RPC integration tests when JSON-2 is the configured protocol."""
        if os.getenv("ODOO_API_PROTOCOL", "xmlrpc") == "json2":
            pytest.skip("XML-RPC integration tests skipped when ODOO_API_PROTOCOL=json2")

    def test_connect(self, test_config_with_server_check):
        conn = OdooConnection(test_config_with_server_check)
        conn.connect()
        assert conn.is_connected is True

    def test_authenticate(self, test_config_with_server_check):
        conn = OdooConnection(test_config_with_server_check)
        conn.connect()
        conn.authenticate()
        assert conn.is_authenticated is True

    def test_search_read(self, test_config_with_server_check):
        conn = OdooConnection(test_config_with_server_check)
        conn.connect()
        conn.authenticate()
        results = conn.search_read("res.partner", [], ["id", "name"], limit=3)
        assert isinstance(results, list)
        assert len(results) <= 3

    def test_search_count(self, test_config_with_server_check):
        conn = OdooConnection(test_config_with_server_check)
        conn.connect()
        conn.authenticate()
        count = conn.search_count("res.partner", [])
        assert isinstance(count, int)

    def test_disconnect(self, test_config_with_server_check):
        conn = OdooConnection(test_config_with_server_check)
        conn.connect()
        conn.disconnect()
        assert conn.is_connected is False
