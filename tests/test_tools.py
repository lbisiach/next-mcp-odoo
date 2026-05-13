"""Tests for MCP tool handlers — including execute_method and discover_model_actions."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP

from next_mcp_odoo.access_control import AccessControlError, AccessController
from next_mcp_odoo.config import OdooConfig
from next_mcp_odoo.error_handling import ValidationError
from next_mcp_odoo.json2_connection import OdooJson2Connection
from next_mcp_odoo.odoo_connection import OdooConnection, OdooConnectionError
from next_mcp_odoo.tools import OdooToolHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _base_config(**kwargs) -> OdooConfig:
    defaults = dict(
        url="http://localhost:8069",
        api_key="test-api-key",
        database="test_db",
        default_limit=10,
        max_limit=100,
    )
    defaults.update(kwargs)
    return OdooConfig(**defaults)


@pytest.fixture
def mock_app():
    """FastMCP app mock that captures registered tools by name."""
    app = MagicMock(spec=FastMCP)
    app._tools = {}

    def tool_decorator(**kwargs):
        def decorator(func):
            app._tools[func.__name__] = func
            return func
        return decorator

    app.tool = tool_decorator
    return app


@pytest.fixture
def mock_xmlrpc_connection():
    conn = MagicMock(spec=OdooConnection)
    conn.is_authenticated = True
    return conn


@pytest.fixture
def mock_json2_connection():
    conn = MagicMock(spec=OdooJson2Connection)
    conn.is_authenticated = True
    # OdooJson2Connection has check_execute_allowed
    conn.check_execute_allowed.return_value = (True, None)
    return conn


@pytest.fixture
def mock_access_controller():
    ctrl = MagicMock(spec=AccessController)
    ctrl.validate_model_access.return_value = None
    return ctrl


@pytest.fixture
def xmlrpc_config():
    return _base_config(api_protocol="xmlrpc")


@pytest.fixture
def json2_config():
    return _base_config(api_protocol="json2", execute_level="business")


@pytest.fixture
def handler(mock_app, mock_xmlrpc_connection, mock_access_controller, xmlrpc_config):
    return OdooToolHandler(mock_app, mock_xmlrpc_connection, mock_access_controller, xmlrpc_config)


@pytest.fixture
def json2_handler(mock_app, mock_json2_connection, mock_access_controller, json2_config):
    return OdooToolHandler(mock_app, mock_json2_connection, mock_access_controller, json2_config)


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_all_tools_registered(self, handler, mock_app):
        expected = {
            "search_records",
            "get_record",
            "list_models",
            "create_record",
            "update_record",
            "delete_record",
            "list_resource_templates",
            "execute_method",
            "discover_model_actions",
        }
        assert expected.issubset(set(mock_app._tools.keys()))

    def test_handler_attributes(self, handler, mock_app, mock_xmlrpc_connection, mock_access_controller, xmlrpc_config):
        assert handler.app is mock_app
        assert handler.connection is mock_xmlrpc_connection
        assert handler.access_controller is mock_access_controller
        assert handler.config is xmlrpc_config


# ---------------------------------------------------------------------------
# search_records
# ---------------------------------------------------------------------------


class TestSearchRecordsTool:
    @pytest.mark.asyncio
    async def test_search_records_success(self, handler, mock_xmlrpc_connection, mock_access_controller, mock_app):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.search_count.return_value = 2
        mock_xmlrpc_connection.search.return_value = [1, 2]
        mock_xmlrpc_connection.read.return_value = [
            {"id": 1, "name": "Partner A"},
            {"id": 2, "name": "Partner B"},
        ]
        mock_xmlrpc_connection.fields_get.return_value = {
            "id": {"type": "integer"}, "name": {"type": "char"}
        }

        result = await handler._handle_search_tool(
            "res.partner", None, None, 10, 0, None, None
        )
        assert result["total"] == 2
        assert len(result["records"]) == 2

    @pytest.mark.asyncio
    async def test_search_records_access_denied(self, handler, mock_access_controller):
        mock_access_controller.validate_model_access.side_effect = AccessControlError(
            "Model not enabled"
        )
        with pytest.raises((AccessControlError, ValidationError)):
            await handler._handle_search_tool("secret.model", None, None, 10, 0, None, None)

    @pytest.mark.asyncio
    async def test_search_records_string_domain_parsed(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.search_count.return_value = 0
        mock_xmlrpc_connection.search.return_value = []
        mock_xmlrpc_connection.read.return_value = []
        mock_xmlrpc_connection.fields_get.return_value = {}

        result = await handler._handle_search_tool(
            "res.partner", '[["active", "=", true]]', None, 10, 0, None, None
        )
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_search_records_python_domain_with_apostrophe(
        self, handler, mock_xmlrpc_connection, mock_access_controller
    ):
        """Regression: domain values containing apostrophes must not be corrupted."""
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.search_count.return_value = 1
        mock_xmlrpc_connection.search.return_value = [1]
        mock_xmlrpc_connection.read.return_value = [{"id": 1, "name": "John's Company"}]
        mock_xmlrpc_connection.fields_get.return_value = {}

        result = await handler._handle_search_tool(
            "res.partner",
            "[['name', '=', \"John's Company\"]]",
            None, 10, 0, None, None,
        )
        assert result["total"] == 1
        # Verify the domain was passed to Odoo intact
        called_domain = mock_xmlrpc_connection.search.call_args[0][1]
        assert called_domain == [["name", "=", "John's Company"]]

    @pytest.mark.asyncio
    async def test_search_records_mixed_syntax_json_booleans(
        self, handler, mock_xmlrpc_connection, mock_access_controller
    ):
        """Mixed syntax: single-quoted list with JSON lowercase boolean keywords."""
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.search_count.return_value = 0
        mock_xmlrpc_connection.search.return_value = []
        mock_xmlrpc_connection.read.return_value = []
        mock_xmlrpc_connection.fields_get.return_value = {}

        result = await handler._handle_search_tool(
            "res.partner", "[['is_company', '=', true]]", None, 10, 0, None, None
        )
        assert result["total"] == 0
        called_domain = mock_xmlrpc_connection.search.call_args[0][1]
        assert called_domain == [["is_company", "=", True]]

    @pytest.mark.asyncio
    async def test_search_records_invalid_domain_raises(self, handler, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection_obj = handler.connection
        mock_xmlrpc_connection_obj.is_authenticated = True

        with pytest.raises(ValidationError):
            await handler._handle_search_tool(
                "res.partner", "not-valid-domain-at-all{", None, 10, 0, None, None
            )

    @pytest.mark.asyncio
    async def test_search_records_not_authenticated(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_xmlrpc_connection.is_authenticated = False
        mock_access_controller.validate_model_access.return_value = None
        with pytest.raises(ValidationError, match="Not authenticated"):
            await handler._handle_search_tool("res.partner", None, None, 10, 0, None, None)


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecordTool:
    @pytest.mark.asyncio
    async def test_get_record_success(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.search_count.return_value = 1
        mock_xmlrpc_connection.read.return_value = [{"id": 1, "name": "Test"}]
        mock_xmlrpc_connection.fields_get.return_value = {
            "id": {"type": "integer"}, "name": {"type": "char"}
        }

        result = await handler._handle_get_record_tool("res.partner", 1, ["id", "name"], None)
        # result is a RecordResult object
        assert result.record["id"] == 1

    @pytest.mark.asyncio
    async def test_get_record_not_found(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.read.return_value = []

        from next_mcp_odoo.error_handling import NotFoundError
        with pytest.raises((NotFoundError, ValidationError)):
            await handler._handle_get_record_tool("res.partner", 9999, ["id", "name"], None)


# ---------------------------------------------------------------------------
# create_record
# ---------------------------------------------------------------------------


class TestCreateRecordTool:
    @pytest.mark.asyncio
    async def test_create_record_success(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.create.return_value = 42
        mock_xmlrpc_connection.read.return_value = [{"id": 42, "display_name": "New"}]
        mock_xmlrpc_connection.build_record_url.return_value = "http://localhost:8069/web#model=res.partner&id=42"

        result = await handler._handle_create_record_tool(
            "res.partner", {"name": "New"}, None
        )
        assert result["success"] is True
        assert result["record"]["id"] == 42

    @pytest.mark.asyncio
    async def test_create_record_access_denied(self, handler, mock_access_controller):
        mock_access_controller.validate_model_access.side_effect = AccessControlError(
            "Create not allowed"
        )
        with pytest.raises((AccessControlError, ValidationError)):
            await handler._handle_create_record_tool("res.partner", {"name": "X"}, None)


# ---------------------------------------------------------------------------
# update_record
# ---------------------------------------------------------------------------


class TestUpdateRecordTool:
    @pytest.mark.asyncio
    async def test_update_record_success(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.read.side_effect = [
            [{"id": 1}],                             # existence check
            [{"id": 1, "display_name": "Updated"}],  # post-write read
        ]
        mock_xmlrpc_connection.write.return_value = True
        mock_xmlrpc_connection.build_record_url.return_value = "http://localhost:8069/web#id=1"

        result = await handler._handle_update_record_tool("res.partner", 1, {"name": "New"}, None)
        assert result["success"] is True
        assert result["record"]["id"] == 1

    @pytest.mark.asyncio
    async def test_update_record_not_found(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.read.return_value = []  # existence check returns empty

        with pytest.raises(ValidationError, match="not found"):
            await handler._handle_update_record_tool("res.partner", 9999, {"name": "X"}, None)


# ---------------------------------------------------------------------------
# delete_record
# ---------------------------------------------------------------------------


class TestDeleteRecordTool:
    @pytest.mark.asyncio
    async def test_delete_record_success(self, handler, mock_xmlrpc_connection, mock_access_controller):
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.read.return_value = [{"id": 1, "display_name": "ToDelete"}]
        mock_xmlrpc_connection.unlink.return_value = True

        result = await handler._handle_delete_record_tool("res.partner", 1, None)
        assert result["deleted_id"] == 1
        assert result["success"] is True


# ---------------------------------------------------------------------------
# execute_method — JSON-2
# ---------------------------------------------------------------------------


class TestExecuteMethodTool:
    """Tests for the new execute_method tool."""

    @pytest.mark.asyncio
    async def test_execute_method_json2_success(self, json2_handler, mock_json2_connection):
        mock_json2_connection.check_execute_allowed.return_value = (True, None)
        mock_json2_connection.execute_kw.return_value = True

        result = await json2_handler._handle_execute_method_tool(
            "account.move", "action_post", [42], {}, None
        )
        assert result.success is True
        assert result.model == "account.move"
        assert result.method == "action_post"
        assert result.ids == [42]

    @pytest.mark.asyncio
    async def test_execute_method_json2_blocked_by_safe_level(self, json2_handler, mock_json2_connection):
        mock_json2_connection.check_execute_allowed.return_value = (
            False,
            "execute_method is not allowed in execute_level=safe",
        )

        with pytest.raises(ValidationError, match="safe"):
            await json2_handler._handle_execute_method_tool(
                "account.move", "action_post", [42], {}, None
            )

    @pytest.mark.asyncio
    async def test_execute_method_json2_blocked_system_model(self, json2_handler, mock_json2_connection):
        mock_json2_connection.check_execute_allowed.return_value = (
            False,
            "Model 'ir.module.module' is a system model.",
        )

        with pytest.raises(ValidationError, match="system model"):
            await json2_handler._handle_execute_method_tool(
                "ir.module.module", "button_immediate_install", [5], {}, None
            )

    @pytest.mark.asyncio
    async def test_execute_method_json2_admin_allows_system(self, mock_app, mock_access_controller):
        config = _base_config(api_protocol="json2", execute_level="admin")
        conn = MagicMock(spec=OdooJson2Connection)
        conn.is_authenticated = True
        conn.check_execute_allowed.return_value = (True, None)
        conn.execute_kw.return_value = True

        handler = OdooToolHandler(mock_app, conn, mock_access_controller, config)
        result = await handler._handle_execute_method_tool(
            "ir.module.module", "button_immediate_install", [5], {}, None
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_method_no_ids_calls_class_method(self, json2_handler, mock_json2_connection):
        """ids=None should call the method with no IDs."""
        mock_json2_connection.check_execute_allowed.return_value = (True, None)
        mock_json2_connection.execute_kw.return_value = {"action": "done"}

        result = await json2_handler._handle_execute_method_tool(
            "account.move", "some_class_method", None, {}, None
        )
        assert result.success is True
        # args should be [] (no ids)
        call_args = mock_json2_connection.execute_kw.call_args
        assert call_args[0][2] == []  # empty args list

    @pytest.mark.asyncio
    async def test_execute_method_connection_error_raises_validation_error(
        self, json2_handler, mock_json2_connection
    ):
        mock_json2_connection.check_execute_allowed.return_value = (True, None)
        mock_json2_connection.execute_kw.side_effect = OdooConnectionError("Timeout")

        with pytest.raises(ValidationError, match="Connection error"):
            await json2_handler._handle_execute_method_tool(
                "account.move", "action_post", [1], {}, None
            )

    @pytest.mark.asyncio
    async def test_execute_method_not_authenticated(self, json2_handler, mock_json2_connection):
        mock_json2_connection.is_authenticated = False

        with pytest.raises(ValidationError, match="Not authenticated"):
            await json2_handler._handle_execute_method_tool(
                "account.move", "action_post", [1], {}, None
            )

    @pytest.mark.asyncio
    async def test_execute_method_xmlrpc_uses_access_controller(
        self, handler, mock_xmlrpc_connection, mock_access_controller
    ):
        """XML-RPC path delegates to access_controller.validate_model_access."""
        mock_access_controller.validate_model_access.return_value = None
        mock_xmlrpc_connection.execute_kw.return_value = True

        result = await handler._handle_execute_method_tool(
            "res.partner", "some_method", [1], {}, None
        )
        assert result.success is True
        mock_access_controller.validate_model_access.assert_called_with("res.partner", "write")

    @pytest.mark.asyncio
    async def test_execute_method_xmlrpc_blocked_by_access_controller(
        self, handler, mock_access_controller
    ):
        mock_access_controller.validate_model_access.side_effect = AccessControlError(
            "Write not allowed"
        )
        with pytest.raises(ValidationError, match="Access denied"):
            await handler._handle_execute_method_tool(
                "res.partner", "some_method", [1], {}, None
            )

    @pytest.mark.asyncio
    async def test_execute_method_with_kwargs(self, json2_handler, mock_json2_connection):
        mock_json2_connection.check_execute_allowed.return_value = (True, None)
        mock_json2_connection.execute_kw.return_value = {"id": 10}

        await json2_handler._handle_execute_method_tool(
            "sale.order",
            "message_post",
            [7],
            {"body": "Hello!", "subtype_xmlid": "mail.mt_note"},
            None,
        )
        call_args = mock_json2_connection.execute_kw.call_args
        assert call_args[0][3] == {"body": "Hello!", "subtype_xmlid": "mail.mt_note"}


# ---------------------------------------------------------------------------
# discover_model_actions
# ---------------------------------------------------------------------------


class TestDiscoverModelActionsTool:
    @pytest.mark.asyncio
    async def test_discover_returns_common_methods(self, handler, mock_xmlrpc_connection):
        mock_xmlrpc_connection.search_read.return_value = []

        result = await handler._handle_discover_model_actions_tool("account.move", None)
        assert result.model == "account.move"
        assert result.total > 0
        action_names = [a.name for a in result.actions]
        assert "message_post" in action_names
        assert "write" in action_names
        assert "unlink" in action_names

    @pytest.mark.asyncio
    async def test_discover_includes_server_actions(self, handler, mock_xmlrpc_connection):
        def side_effect(model, domain, fields, limit=None):
            if model == "ir.actions.server":
                return [{"name": "Validate Invoice", "state": "multi", "binding_model_id": 1}]
            return []

        mock_xmlrpc_connection.search_read.side_effect = side_effect

        result = await handler._handle_discover_model_actions_tool("account.move", None)
        action_names = [a.name for a in result.actions]
        assert "validate_invoice" in action_names

    @pytest.mark.asyncio
    async def test_discover_includes_window_actions(self, handler, mock_xmlrpc_connection):
        def side_effect(model, domain, fields, limit=None):
            if model == "ir.actions.act_window":
                return [{"name": "Create Invoice", "res_model": "account.move"}]
            return []

        mock_xmlrpc_connection.search_read.side_effect = side_effect

        result = await handler._handle_discover_model_actions_tool("account.move", None)
        action_names = [a.name for a in result.actions]
        assert "create_invoice" in action_names

    @pytest.mark.asyncio
    async def test_discover_not_authenticated(self, handler, mock_xmlrpc_connection):
        mock_xmlrpc_connection.is_authenticated = False

        with pytest.raises(ValidationError, match="Not authenticated"):
            await handler._handle_discover_model_actions_tool("account.move", None)

    @pytest.mark.asyncio
    async def test_discover_note_mentions_model(self, handler, mock_xmlrpc_connection):
        mock_xmlrpc_connection.search_read.return_value = []

        result = await handler._handle_discover_model_actions_tool("sale.order", None)
        assert "sale.order" in result.note

    @pytest.mark.asyncio
    async def test_discover_server_actions_error_is_non_fatal(self, handler, mock_xmlrpc_connection):
        """If ir.actions.server query fails, common methods should still be returned."""
        def side_effect(model, domain, fields, limit=None):
            if model == "ir.actions.server":
                raise OdooConnectionError("Permission denied")
            return []

        mock_xmlrpc_connection.search_read.side_effect = side_effect

        result = await handler._handle_discover_model_actions_tool("account.move", None)
        # Common methods still present
        assert result.total > 0
        assert any(a.name == "message_post" for a in result.actions)


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------


class TestListModelsTool:
    @pytest.mark.asyncio
    async def test_list_models_json2_returns_ir_model(self, json2_handler, mock_json2_connection, mock_access_controller):
        mock_access_controller.get_enabled_models.return_value = []
        mock_json2_connection.search_read.return_value = [
            {"model": "res.partner", "name": "Contact"},
            {"model": "account.move", "name": "Invoice"},
        ]

        result = await json2_handler._handle_list_models_tool(None)
        assert "models" in result
