"""Tests for the access control module.

Covers both JSON-2 mode (local execute_level logic) and XML-RPC/YOLO mode
(REST API delegation — tested with mocked urllib).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from next_mcp_odoo.access_control import (
    AccessControlError,
    AccessController,
    ModelPermissions,
    _is_system_model,
)
from next_mcp_odoo.config import OdooConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(**kwargs) -> OdooConfig:
    defaults = dict(url="http://localhost:8069", api_key="test-key", database="test_db")
    defaults.update(kwargs)
    return OdooConfig(**defaults)


def _json2_config(**kwargs) -> OdooConfig:
    return _config(api_protocol="json2", **kwargs)


def _urlopen_mock(payload):
    """Build a context-manager mock for urllib.request.urlopen."""
    cm = MagicMock()
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.headers = {}
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


# ---------------------------------------------------------------------------
# _is_system_model helper
# ---------------------------------------------------------------------------


class TestIsSystemModelHelper:
    def test_ir_models_are_system(self):
        assert _is_system_model("ir.model")
        assert _is_system_model("ir.rule")
        assert _is_system_model("ir.cron")

    def test_ir_prefix_is_system(self):
        assert _is_system_model("ir.anything")

    def test_base_prefix_is_system(self):
        assert _is_system_model("base.setup.config")

    def test_res_users_is_system(self):
        assert _is_system_model("res.users")

    def test_res_groups_is_system(self):
        assert _is_system_model("res.groups")

    def test_business_models_not_system(self):
        for model in ("res.partner", "account.move", "sale.order", "stock.picking", "mrp.production"):
            assert not _is_system_model(model), f"{model} should not be system"


# ---------------------------------------------------------------------------
# AccessController init
# ---------------------------------------------------------------------------


class TestAccessControllerInit:
    def test_json2_mode_init(self):
        config = _json2_config(execute_level="business")
        ctrl = AccessController(config)
        assert ctrl.config is config

    def test_xmlrpc_mode_init_with_api_key(self, caplog):
        config = _config(api_protocol="xmlrpc")
        ctrl = AccessController(config)
        assert ctrl.config is config

    def test_json2_mode_no_session(self):
        ctrl = AccessController(_json2_config())
        assert ctrl._session_id is None

    def test_yolo_mode_logs_warning(self, caplog):
        config = OdooConfig(
            url="http://localhost:8069",
            username="admin",
            password="admin",
            database="db",
            yolo_mode="true",
        )
        AccessController(config)
        assert "YOLO" in caplog.text


# ---------------------------------------------------------------------------
# JSON-2: _json2_check
# ---------------------------------------------------------------------------


class TestJson2Check:
    def _ctrl(self, level: str) -> AccessController:
        return AccessController(_json2_config(execute_level=level))

    # Read ops are always allowed regardless of level
    def test_read_always_allowed_at_safe(self):
        ctrl = self._ctrl("safe")
        for op in ("read", "search", "search_read", "search_count", "fields_get"):
            allowed, err = ctrl._json2_check("res.partner", op)
            assert allowed, f"op={op} should be allowed at safe level"
            assert err is None

    def test_read_always_allowed_at_business(self):
        ctrl = self._ctrl("business")
        allowed, _ = ctrl._json2_check("ir.rule", "read")
        assert allowed

    def test_read_always_allowed_at_admin(self):
        ctrl = self._ctrl("admin")
        allowed, _ = ctrl._json2_check("ir.rule", "read")
        assert allowed

    def test_safe_blocks_write(self):
        ctrl = self._ctrl("safe")
        allowed, err = ctrl._json2_check("res.partner", "write")
        assert not allowed
        assert "safe" in err.lower()

    def test_safe_blocks_create(self):
        ctrl = self._ctrl("safe")
        allowed, err = ctrl._json2_check("res.partner", "create")
        assert not allowed

    def test_business_allows_write_on_business_model(self):
        ctrl = self._ctrl("business")
        allowed, err = ctrl._json2_check("res.partner", "write")
        assert allowed

    def test_business_blocks_write_on_system_model(self):
        ctrl = self._ctrl("business")
        allowed, err = ctrl._json2_check("ir.model", "write")
        assert not allowed
        assert "system model" in err.lower()

    def test_business_blocks_unlink_on_res_users(self):
        ctrl = self._ctrl("business")
        allowed, err = ctrl._json2_check("res.users", "unlink")
        assert not allowed

    def test_admin_allows_write_on_system_model(self):
        ctrl = self._ctrl("admin")
        allowed, err = ctrl._json2_check("ir.model", "write")
        assert allowed
        assert err is None

    def test_admin_allows_write_on_ir_module(self):
        ctrl = self._ctrl("admin")
        allowed, _ = ctrl._json2_check("ir.module.module", "write")
        assert allowed


# ---------------------------------------------------------------------------
# JSON-2: get_model_permissions
# ---------------------------------------------------------------------------


class TestJson2GetModelPermissions:
    def _perms(self, model: str, level: str) -> ModelPermissions:
        ctrl = AccessController(_json2_config(execute_level=level))
        return ctrl.get_model_permissions(model)

    def test_safe_read_only(self):
        p = self._perms("res.partner", "safe")
        assert p.can_read is True
        assert p.can_write is False
        assert p.can_create is False
        assert p.can_unlink is False

    def test_business_business_model_full(self):
        p = self._perms("res.partner", "business")
        assert p.can_read is True
        assert p.can_write is True
        assert p.can_create is True
        assert p.can_unlink is True

    def test_business_system_model_read_only(self):
        p = self._perms("ir.rule", "business")
        assert p.can_read is True
        assert p.can_write is False
        assert p.can_create is False

    def test_admin_system_model_full(self):
        p = self._perms("ir.rule", "admin")
        assert p.can_read is True
        assert p.can_write is True
        assert p.can_create is True
        assert p.can_unlink is True

    def test_enabled_always_true_for_json2(self):
        p = self._perms("res.partner", "business")
        assert p.enabled is True


# ---------------------------------------------------------------------------
# JSON-2: check_operation_allowed
# ---------------------------------------------------------------------------


class TestJson2CheckOperationAllowed:
    def test_read_allowed_at_safe(self):
        ctrl = AccessController(_json2_config(execute_level="safe"))
        allowed, _ = ctrl.check_operation_allowed("res.partner", "read")
        assert allowed

    def test_write_blocked_at_safe(self):
        ctrl = AccessController(_json2_config(execute_level="safe"))
        allowed, _ = ctrl.check_operation_allowed("res.partner", "write")
        assert not allowed

    def test_write_on_system_model_blocked_at_business(self):
        ctrl = AccessController(_json2_config(execute_level="business"))
        allowed, msg = ctrl.check_operation_allowed("ir.cron", "write")
        assert not allowed
        assert msg

    def test_write_on_business_model_allowed_at_business(self):
        ctrl = AccessController(_json2_config(execute_level="business"))
        allowed, _ = ctrl.check_operation_allowed("account.move", "write")
        assert allowed

    def test_validate_model_access_raises_on_denial(self):
        ctrl = AccessController(_json2_config(execute_level="safe"))
        with pytest.raises(AccessControlError):
            ctrl.validate_model_access("res.partner", "write")

    def test_validate_model_access_passes_on_read(self):
        ctrl = AccessController(_json2_config(execute_level="safe"))
        ctrl.validate_model_access("res.partner", "read")  # should not raise


# ---------------------------------------------------------------------------
# JSON-2: is_model_enabled / get_enabled_models
# ---------------------------------------------------------------------------


class TestJson2ModelEnabled:
    def test_all_models_enabled_in_json2(self):
        ctrl = AccessController(_json2_config())
        assert ctrl.is_model_enabled("res.partner") is True
        assert ctrl.is_model_enabled("ir.rule") is True

    def test_get_enabled_models_returns_empty_list_for_json2(self):
        """JSON-2 returns [] (means 'all allowed')."""
        ctrl = AccessController(_json2_config())
        assert ctrl.get_enabled_models() == []

    def test_filter_enabled_models_returns_all_for_json2(self):
        ctrl = AccessController(_json2_config())
        models = ["res.partner", "account.move", "ir.model"]
        assert ctrl.filter_enabled_models(models) == models


# ---------------------------------------------------------------------------
# XML-RPC mode: REST API delegation (mocked urllib)
# ---------------------------------------------------------------------------


class TestXmlrpcMakeRequest:
    @pytest.fixture
    def ctrl(self):
        config = _config(api_protocol="xmlrpc")
        return AccessController(config)

    @patch("urllib.request.urlopen")
    def test_make_request_success(self, mock_urlopen, ctrl):
        mock_urlopen.return_value = _urlopen_mock(
            {"success": True, "data": {"test": "value"}}
        )
        result = ctrl._make_request("/test/endpoint")
        assert result["success"] is True

    @patch("urllib.request.urlopen")
    def test_make_request_api_error(self, mock_urlopen, ctrl):
        mock_urlopen.return_value = _urlopen_mock(
            {"success": False, "error": {"message": "Not found"}}
        )
        with pytest.raises(AccessControlError, match="API error: Not found"):
            ctrl._make_request("/test/endpoint")

    @patch("urllib.request.urlopen")
    def test_make_request_http_401_api_key(self, mock_urlopen, ctrl):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError("url", 401, "Unauthorized", {}, None)
        with pytest.raises(AccessControlError, match="API key rejected"):
            ctrl._make_request("/mcp/models")

    @patch("urllib.request.urlopen")
    def test_make_request_http_403(self, mock_urlopen, ctrl):
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError("url", 403, "Forbidden", {}, None)
        with pytest.raises(AccessControlError, match="Access denied"):
            ctrl._make_request("/mcp/models")

    @patch("urllib.request.urlopen")
    def test_get_enabled_models_success(self, mock_urlopen, ctrl):
        mock_urlopen.return_value = _urlopen_mock(
            {
                "success": True,
                "data": {
                    "models": [
                        {"model": "res.partner", "name": "Contact"},
                        {"model": "account.move", "name": "Invoice"},
                    ]
                },
            }
        )
        models = ctrl.get_enabled_models()
        assert len(models) == 2
        assert models[0]["model"] == "res.partner"

    @patch("urllib.request.urlopen")
    def test_get_model_permissions_xmlrpc(self, mock_urlopen, ctrl):
        mock_urlopen.return_value = _urlopen_mock(
            {
                "success": True,
                "data": {
                    "model": "res.partner",
                    "enabled": True,
                    "operations": {
                        "read": True,
                        "write": True,
                        "create": False,
                        "unlink": False,
                    },
                },
            }
        )
        perms = ctrl.get_model_permissions("res.partner")
        assert perms.can_read is True
        assert perms.can_write is True
        assert perms.can_create is False
        assert perms.can_unlink is False


# ---------------------------------------------------------------------------
# YOLO mode access control
# ---------------------------------------------------------------------------


class TestYoloAccessControl:
    @pytest.fixture
    def read_only_yolo_ctrl(self):
        config = OdooConfig(
            url="http://localhost:8069",
            username="admin",
            password="admin",
            database="db",
            yolo_mode="read",
        )
        return AccessController(config)

    @pytest.fixture
    def full_yolo_ctrl(self):
        config = OdooConfig(
            url="http://localhost:8069",
            username="admin",
            password="admin",
            database="db",
            yolo_mode="true",
        )
        return AccessController(config)

    def test_read_only_yolo_allows_read(self, read_only_yolo_ctrl):
        allowed, _ = read_only_yolo_ctrl.check_operation_allowed("res.partner", "read")
        assert allowed

    def test_read_only_yolo_blocks_write(self, read_only_yolo_ctrl):
        allowed, msg = read_only_yolo_ctrl.check_operation_allowed("res.partner", "write")
        assert not allowed

    def test_full_yolo_allows_write(self, full_yolo_ctrl):
        allowed, _ = full_yolo_ctrl.check_operation_allowed("res.partner", "write")
        assert allowed

    def test_full_yolo_allows_unlink(self, full_yolo_ctrl):
        allowed, _ = full_yolo_ctrl.check_operation_allowed("res.partner", "unlink")
        assert allowed

    def test_yolo_get_model_permissions_read_only(self, read_only_yolo_ctrl):
        perms = read_only_yolo_ctrl.get_model_permissions("res.partner")
        assert perms.can_read is True
        assert perms.can_write is False

    def test_yolo_get_model_permissions_full(self, full_yolo_ctrl):
        perms = full_yolo_ctrl.get_model_permissions("any.model")
        assert perms.can_read is True
        assert perms.can_write is True
        assert perms.can_create is True
        assert perms.can_unlink is True
