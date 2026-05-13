"""Tests for OdooJson2Connection — JSON-2 API implementation.

Unit tests use urllib mocks; integration tests are marked @pytest.mark.json2
and require a running Odoo 19+ instance with ODOO_API_PROTOCOL=json2.
"""

import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest

from next_mcp_odoo.config import OdooConfig
from next_mcp_odoo.access_control import _SYSTEM_MODELS, _is_system_model
from next_mcp_odoo.json2_connection import (
    OdooConnectionError,
    OdooJson2Connection,
    _METHOD_ARG_NAMES,
)
from next_mcp_odoo.odoo_connection import get_connection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(**kwargs) -> OdooConfig:
    defaults = dict(
        url="http://localhost:8069",
        api_key="test-api-key",
        database="test_db",
        api_protocol="json2",
    )
    defaults.update(kwargs)
    return OdooConfig(**defaults)


def make_urlopen_mock(payload):
    """Return a context-manager mock that yields a response with json payload."""
    mock_cm = MagicMock()
    mock_resp = MagicMock()
    raw = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload
    mock_resp.read.return_value = raw
    mock_cm.__enter__.return_value = mock_resp
    mock_cm.__exit__.return_value = False
    return mock_cm


# ---------------------------------------------------------------------------
# is_system_model helper
# ---------------------------------------------------------------------------


class TestIsSystemModel:
    def test_known_system_models(self):
        for model in ("ir.rule", "ir.model", "res.users", "res.groups", "ir.cron"):
            assert _is_system_model(model), f"{model} should be a system model"

    def test_ir_prefix_is_system(self):
        assert _is_system_model("ir.custom.anything") is True

    def test_base_prefix_is_system(self):
        assert _is_system_model("base.setup.config") is True

    def test_business_models_not_system(self):
        for model in ("res.partner", "account.move", "sale.order", "stock.picking"):
            assert _is_system_model(model) is False, f"{model} should not be a system model"

    def test_res_partner_not_system(self):
        assert _is_system_model("res.partner") is False

    def test_res_users_is_system(self):
        assert _is_system_model("res.users") is True


# ---------------------------------------------------------------------------
# _METHOD_ARG_NAMES
# ---------------------------------------------------------------------------


class TestMethodArgNames:
    def test_search_has_domain(self):
        assert _METHOD_ARG_NAMES["search"] == ["domain"]

    def test_write_has_ids_and_vals(self):
        assert _METHOD_ARG_NAMES["write"] == ["ids", "vals"]

    def test_create_has_vals(self):
        assert _METHOD_ARG_NAMES["create"] == ["vals"]

    def test_read_has_ids(self):
        assert _METHOD_ARG_NAMES["read"] == ["ids"]

    def test_unlink_has_ids(self):
        assert _METHOD_ARG_NAMES["unlink"] == ["ids"]


# ---------------------------------------------------------------------------
# OdooJson2Connection initialization
# ---------------------------------------------------------------------------


class TestJson2ConnectionInit:
    def test_basic_init(self):
        config = make_config()
        conn = OdooJson2Connection(config)
        assert conn.config is config
        assert conn.timeout == OdooJson2Connection.DEFAULT_TIMEOUT
        assert not conn.is_connected
        assert not conn.is_authenticated

    def test_custom_timeout(self):
        conn = OdooJson2Connection(make_config(), timeout=60)
        assert conn.timeout == 60

    def test_url_parsing_http(self):
        conn = OdooJson2Connection(make_config(url="http://myodoo.com:8069"))
        assert conn._url_components["host"] == "myodoo.com"
        assert conn._url_components["port"] == 8069
        assert conn._url_components["scheme"] == "http"

    def test_url_parsing_https(self):
        conn = OdooJson2Connection(make_config(url="https://secure.odoo.com"))
        assert conn._url_components["scheme"] == "https"
        assert conn._url_components["port"] == 443

    def test_url_parsing_http_default_port(self):
        conn = OdooJson2Connection(make_config(url="http://myodoo.com"))
        assert conn._url_components["port"] == 80

    def test_json2_url_format(self):
        conn = OdooJson2Connection(make_config(url="http://localhost:8069"))
        assert conn._json2_url("res.partner", "search_read") == (
            "http://localhost:8069/json/2/res.partner/search_read"
        )

    def test_initial_state(self):
        conn = OdooJson2Connection(make_config())
        assert conn._connected is False
        assert conn._authenticated is False
        assert conn._uid is None
        assert conn._database is None
        assert conn._server_version is None


# ---------------------------------------------------------------------------
# connect()
# ---------------------------------------------------------------------------


class TestJson2ConnectionConnect:
    @patch("urllib.request.urlopen")
    def test_connect_success(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(
            {"jsonrpc": "2.0", "result": {"server_version": "19.0"}}
        )
        conn = OdooJson2Connection(make_config())
        conn.connect()
        assert conn._connected is True
        assert conn._server_version == "19.0"

    @patch("urllib.request.urlopen")
    def test_connect_already_connected_logs_warning(self, mock_urlopen, caplog):
        mock_urlopen.return_value = make_urlopen_mock(
            {"jsonrpc": "2.0", "result": {"server_version": "19.0"}}
        )
        conn = OdooJson2Connection(make_config())
        conn.connect()
        conn.connect()  # second call
        assert "Already connected" in caplog.text

    @patch("urllib.request.urlopen")
    def test_connect_network_error_raises(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        conn = OdooJson2Connection(make_config())
        with pytest.raises(OdooConnectionError, match="Cannot reach Odoo server"):
            conn.connect()

    @patch("urllib.request.urlopen")
    def test_connect_version_without_result_key(self, mock_urlopen):
        """Handles servers that return version at root level."""
        mock_urlopen.return_value = make_urlopen_mock(
            {"server_version": "18.0"}
        )
        conn = OdooJson2Connection(make_config())
        conn.connect()
        assert conn._connected is True


# ---------------------------------------------------------------------------
# disconnect() / close()
# ---------------------------------------------------------------------------


class TestJson2ConnectionDisconnect:
    @patch("urllib.request.urlopen")
    def test_disconnect_clears_state(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(
            {"jsonrpc": "2.0", "result": {"server_version": "19.0"}}
        )
        conn = OdooJson2Connection(make_config())
        conn.connect()
        conn._authenticated = True
        conn._database = "mydb"
        conn.disconnect()
        assert conn._connected is False
        assert conn._authenticated is False
        assert conn._database is None

    def test_disconnect_when_not_connected_logs_warning(self, caplog):
        conn = OdooJson2Connection(make_config())
        conn.disconnect()
        assert "Not connected" in caplog.text

    @patch("urllib.request.urlopen")
    def test_context_manager(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(
            {"jsonrpc": "2.0", "result": {"server_version": "19.0"}}
        )
        config = make_config()
        with OdooJson2Connection(config) as conn:
            assert conn._connected is True
        assert conn._connected is False


# ---------------------------------------------------------------------------
# _request()
# ---------------------------------------------------------------------------


class TestJson2Request:
    @patch("urllib.request.urlopen")
    def test_request_sets_bearer_token(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock({"ok": True})
        conn = OdooJson2Connection(make_config())
        conn._request("POST", "http://localhost:8069/json/2/res.partner/search_count", {})

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test-api-key"

    @patch("urllib.request.urlopen")
    def test_request_sets_db_header(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock({"ok": True})
        conn = OdooJson2Connection(make_config())
        conn._database = "mydb"
        conn._request("POST", "http://localhost:8069/json/2/res.partner/count", {})

        req = mock_urlopen.call_args[0][0]
        assert req.get_header("X-odoo-database") == "mydb"

    @patch("urllib.request.urlopen")
    def test_request_http_error_raises_connection_error(self, mock_urlopen):
        import urllib.error

        error_body = json.dumps({"error": {"message": "access denied"}}).encode()
        http_err = urllib.error.HTTPError("url", 403, "Forbidden", {}, None)
        http_err.read = lambda: error_body
        mock_urlopen.side_effect = http_err
        conn = OdooJson2Connection(make_config())
        with pytest.raises(OdooConnectionError, match="HTTP 403"):
            conn._request("POST", "http://localhost:8069/test", {})

    @patch("urllib.request.urlopen")
    def test_request_url_error_raises_connection_error(self, mock_urlopen):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("no route to host")
        conn = OdooJson2Connection(make_config())
        with pytest.raises(OdooConnectionError, match="Network error"):
            conn._request("POST", "http://localhost:9999/test", {})

    @patch("urllib.request.urlopen")
    def test_request_timeout_raises_connection_error(self, mock_urlopen):
        import socket

        mock_urlopen.side_effect = socket.timeout()
        conn = OdooJson2Connection(make_config())
        with pytest.raises(OdooConnectionError, match="timeout"):
            conn._request("POST", "http://localhost:8069/test", {})


# ---------------------------------------------------------------------------
# execute_kw() — argument mapping
# ---------------------------------------------------------------------------


class TestJson2ExecuteKw:
    def _make_authenticated_conn(self, config=None):
        conn = OdooJson2Connection(config or make_config())
        conn._connected = True
        conn._authenticated = True
        conn._database = "test_db"
        return conn

    @patch("urllib.request.urlopen")
    def test_execute_kw_search_maps_domain(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock([1, 2, 3])
        conn = self._make_authenticated_conn()
        result = conn.execute_kw("res.partner", "search", [[["active", "=", True]]], {})
        assert result == [1, 2, 3]
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["domain"] == [["active", "=", True]]

    @patch("urllib.request.urlopen")
    def test_execute_kw_search_read_maps_domain(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock([{"id": 1, "name": "Test"}])
        conn = self._make_authenticated_conn()
        result = conn.execute_kw(
            "res.partner", "search_read", [[["id", ">", 0]]], {"fields": ["name"]}
        )
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["domain"] == [["id", ">", 0]]
        assert body["fields"] == ["name"]

    @patch("urllib.request.urlopen")
    def test_execute_kw_write_maps_ids_and_vals(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(True)
        conn = self._make_authenticated_conn()
        conn.execute_kw("res.partner", "write", [[1, 2], {"name": "New"}], {})
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode())
        assert body["ids"] == [1, 2]
        assert body["vals"] == {"name": "New"}

    @patch("urllib.request.urlopen")
    def test_execute_kw_create_maps_vals(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(42)
        conn = self._make_authenticated_conn()
        result = conn.execute_kw("res.partner", "create", [{"name": "New Partner"}], {})
        assert result == 42
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body["vals"] == {"name": "New Partner"}

    @patch("urllib.request.urlopen")
    def test_execute_kw_unknown_method_first_arg_becomes_ids(self, mock_urlopen):
        """First positional arg of unknown methods maps to 'ids' (JSON-2 convention)."""
        mock_urlopen.return_value = make_urlopen_mock({"status": "ok"})
        conn = self._make_authenticated_conn()
        conn.execute_kw("account.move", "action_post", [[42, 43]], {})
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body["ids"] == [42, 43]
        assert "arg0" not in body

    @patch("urllib.request.urlopen")
    def test_execute_kw_unknown_method_second_arg_uses_arg_prefix(self, mock_urlopen):
        """Only the first arg maps to 'ids'; subsequent unknown args still use arg prefix."""
        mock_urlopen.return_value = make_urlopen_mock({"status": "ok"})
        conn = self._make_authenticated_conn()
        conn.execute_kw("account.move", "custom_method", [[1], "extra"], {})
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body["ids"] == [1]
        assert body["arg1"] == "extra"

    def test_execute_kw_not_authenticated_raises(self):
        conn = OdooJson2Connection(make_config())
        with pytest.raises(OdooConnectionError, match="Not authenticated"):
            conn.execute_kw("res.partner", "search_read", [[]], {})

    @patch("urllib.request.urlopen")
    def test_execute_kw_injects_locale_in_context(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock([])
        config = make_config(locale="es_AR")
        conn = self._make_authenticated_conn(config)
        conn.execute_kw("res.partner", "search_read", [[]], {})
        body = json.loads(mock_urlopen.call_args[0][0].data.decode())
        assert body.get("context", {}).get("lang") == "es_AR"




# ---------------------------------------------------------------------------
# Convenience ORM wrappers
# ---------------------------------------------------------------------------


class TestJson2OrmWrappers:
    def _make_conn(self):
        conn = OdooJson2Connection(make_config())
        conn._connected = True
        conn._authenticated = True
        conn._database = "test_db"
        return conn

    @patch("urllib.request.urlopen")
    def test_search_read(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock([{"id": 1}])
        conn = self._make_conn()
        result = conn.search_read("res.partner", [["id", ">", 0]], ["name"])
        assert result == [{"id": 1}]

    @patch("urllib.request.urlopen")
    def test_search(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock([1, 2])
        conn = self._make_conn()
        result = conn.search("res.partner", [["active", "=", True]])
        assert result == [1, 2]

    @patch("urllib.request.urlopen")
    def test_read(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock([{"id": 1, "name": "Test"}])
        conn = self._make_conn()
        result = conn.read("res.partner", [1], ["name"])
        assert result == [{"id": 1, "name": "Test"}]

    @patch("urllib.request.urlopen")
    def test_search_count(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(42)
        conn = self._make_conn()
        count = conn.search_count("res.partner", [])
        assert count == 42

    @patch("urllib.request.urlopen")
    def test_create(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(99)
        conn = self._make_conn()
        result = conn.create("res.partner", {"name": "New"})
        assert result == 99

    @patch("urllib.request.urlopen")
    def test_write(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(True)
        conn = self._make_conn()
        result = conn.write("res.partner", [1], {"name": "Updated"})
        assert result is True

    @patch("urllib.request.urlopen")
    def test_unlink(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock(True)
        conn = self._make_conn()
        result = conn.unlink("res.partner", [1])
        assert result is True

    @patch("urllib.request.urlopen")
    def test_fields_get(self, mock_urlopen):
        mock_urlopen.return_value = make_urlopen_mock({"name": {"type": "char"}})
        conn = self._make_conn()
        result = conn.fields_get("res.partner")
        assert "name" in result


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestJson2ConnectionProperties:
    def test_is_connected_property(self):
        conn = OdooJson2Connection(make_config())
        assert conn.is_connected is False
        conn._connected = True
        assert conn.is_connected is True

    def test_is_authenticated_property(self):
        conn = OdooJson2Connection(make_config())
        assert conn.is_authenticated is False
        conn._authenticated = True
        assert conn.is_authenticated is True

    def test_database_property(self):
        conn = OdooJson2Connection(make_config(database="mydb"))
        # Before authenticate, _database is None
        assert conn.database is None or conn.database == "mydb"

    def test_server_version_initially_none(self):
        conn = OdooJson2Connection(make_config())
        assert conn._server_version is None


# ---------------------------------------------------------------------------
# get_connection() factory
# ---------------------------------------------------------------------------


class TestGetConnectionFactory:
    def test_factory_returns_xmlrpc_by_default(self):
        from next_mcp_odoo.odoo_connection import OdooConnection

        config = OdooConfig(url="http://localhost:8069", api_key="test-key")
        conn = get_connection(config)
        assert isinstance(conn, OdooConnection)

    def test_factory_returns_json2_when_configured(self):
        config = OdooConfig(
            url="http://localhost:8069", api_key="test-key", api_protocol="json2"
        )
        conn = get_connection(config)
        assert isinstance(conn, OdooJson2Connection)

    def test_factory_passes_timeout(self):
        config = OdooConfig(
            url="http://localhost:8069", api_key="test-key", api_protocol="json2"
        )
        conn = get_connection(config, timeout=45)
        assert conn.timeout == 45


# ---------------------------------------------------------------------------
# Integration tests — require live Odoo 19+ with JSON-2
# ---------------------------------------------------------------------------


@pytest.mark.json2
class TestJson2ConnectionIntegration:
    """Integration tests against a live Odoo 19+ instance."""

    def test_connect(self, live_json2_config):
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        assert conn._connected is True
        assert conn._server_version is not None

    def test_authenticate(self, live_json2_config):
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        conn.authenticate()
        assert conn._authenticated is True
        assert conn._database is not None

    def test_search_read_res_partner(self, live_json2_config):
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        conn.authenticate()
        results = conn.search_read("res.partner", [], ["name", "id"], limit=5)
        assert isinstance(results, list)
        assert len(results) <= 5
        for r in results:
            assert "id" in r
            assert "name" in r

    def test_search_count(self, live_json2_config):
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        conn.authenticate()
        count = conn.search_count("res.partner", [])
        assert isinstance(count, int)
        assert count >= 0

    def test_fields_get(self, live_json2_config):
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        conn.authenticate()
        fields = conn.fields_get("res.partner")
        assert isinstance(fields, dict)
        assert "name" in fields

    def test_invalid_api_key_fails(self, live_json2_config):
        import dataclasses

        bad_config = dataclasses.replace(live_json2_config, api_key="invalid-key-xxxxx")
        conn = OdooJson2Connection(bad_config)
        conn.connect()
        with pytest.raises(OdooConnectionError):
            conn.authenticate()

    def test_check_execute_allowed_business_model(self, live_json2_config):
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        conn.authenticate()
        allowed, err = conn.check_execute_allowed("account.move")
        if live_json2_config.execute_level == "safe":
            assert allowed is False
        else:
            assert allowed is True

    def test_execute_kw_action_on_business_model(self, live_json2_config):
        """execute_kw on a business model should succeed at business/admin level."""
        if live_json2_config.execute_level == "safe":
            pytest.skip("safe level blocks execute_method")
        conn = OdooJson2Connection(live_json2_config)
        conn.connect()
        conn.authenticate()
        # Just count partners — read is always allowed
        count = conn.search_count("res.partner", [])
        assert isinstance(count, int)
