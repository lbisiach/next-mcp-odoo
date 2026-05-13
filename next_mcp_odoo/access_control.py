"""Access control for Odoo MCP Server.

Supports three modes:
- xmlrpc standard: delegates model-level permissions to the Odoo MCP module REST API
- xmlrpc yolo:     all models accessible, access control scoped to read/write by ODOO_YOLO
- json2:           all models accessible, Odoo native ACL applies; execute_level controls
                   which methods can be called via execute_method
"""

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .config import OdooConfig

logger = logging.getLogger(__name__)


class AccessControlError(Exception):
    pass


@dataclass
class ModelPermissions:
    model: str
    enabled: bool
    can_read: bool = False
    can_write: bool = False
    can_create: bool = False
    can_unlink: bool = False

    def can_perform(self, operation: str) -> bool:
        return {
            "read": self.can_read,
            "write": self.can_write,
            "create": self.can_create,
            "unlink": self.can_unlink,
            "delete": self.can_unlink,
        }.get(operation, False)


@dataclass
class CacheEntry:
    data: Any
    timestamp: datetime

    def is_expired(self, ttl_seconds: int) -> bool:
        return datetime.now() - self.timestamp > timedelta(seconds=ttl_seconds)


# Models that require execute_level=admin in JSON-2 mode
_SYSTEM_MODELS = frozenset({
    "ir.rule", "ir.model", "ir.model.fields", "ir.model.access",
    "ir.module.module", "ir.config_parameter", "ir.sequence",
    "ir.cron", "ir.actions.server", "ir.filters",
    "base.automation", "res.users", "res.groups",
})

_READ_OPERATIONS = frozenset({
    "read", "search", "search_read", "fields_get", "count",
    "search_count", "name_search", "name_get",
})


def _is_system_model(model: str) -> bool:
    return model in _SYSTEM_MODELS or model.startswith("ir.") or model.startswith("base.")


class AccessController:
    """Controls access to Odoo models.

    JSON-2 mode: pure local logic based on execute_level + model category.
    XML-RPC mode: delegates to Odoo MCP module REST API (original behaviour).
    """

    CACHE_TTL = 300
    MODELS_ENDPOINT = "/mcp/models"
    MODEL_ACCESS_ENDPOINT = "/mcp/models/{model}/access"

    def __init__(
        self, config: OdooConfig, database: Optional[str] = None, cache_ttl: int = CACHE_TTL
    ):
        self.config = config
        self.database = database or config.database
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._session_id: Optional[str] = None
        self.base_url = config.url.rstrip("/")

        if config.is_json2:
            logger.info(
                f"AccessController: JSON-2 mode — execute_level={config.execute_level}"
            )
            return

        if config.is_yolo_enabled:
            mode_desc = "READ-ONLY" if config.yolo_mode == "read" else "FULL ACCESS"
            logger.warning(
                f"YOLO mode ({mode_desc}): Access control bypassed! "
                "All models accessible, MCP security disabled."
            )
            return

        if config.api_key:
            logger.info(f"Initialized AccessController for {self.base_url} (API key auth)")
        elif config.uses_credentials:
            logger.info(f"Initialized AccessController for {self.base_url} (session auth)")
        else:
            logger.warning("No authentication configured for MCP access control.")

    # ------------------------------------------------------------------
    # JSON-2 access control
    # ------------------------------------------------------------------

    def _json2_check(self, model: str, operation: str) -> Tuple[bool, Optional[str]]:
        """Local access check for JSON-2 CRUD operations based on execute_level.

        CRUD tools (create, update, delete) delegate model-level permissions
        entirely to Odoo's native ACL. The only MCP-level control here is
        execute_level=safe, which forces a read-only connection regardless of
        what the user can do in Odoo.

        Method-level guardrails (system model check for execute_method) live in
        OdooJson2Connection.check_execute_allowed(), not here.
        """
        # Read operations are always allowed at any level
        if operation in _READ_OPERATIONS:
            return True, None

        if self.config.execute_level == "safe":
            return False, (
                f"Operation '{operation}' not allowed at execute_level=safe. "
                "Set ODOO_EXECUTE_LEVEL=business or admin."
            )

        # business / admin: delegate to Odoo's native ACL
        return True, None

    # ------------------------------------------------------------------
    # YOLO / MCP module access control (XML-RPC mode — original code)
    # ------------------------------------------------------------------

    def _authenticate_session(self) -> None:
        url = f"{self.base_url}/web/session/authenticate"
        body = json.dumps({
            "jsonrpc": "2.0", "method": "call",
            "params": {
                "login": self.config.username,
                "password": self.config.password,
                "db": self.database,
            },
            "id": 1,
        }).encode()
        req = urllib.request.Request(url, data=body)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                cookie_header = response.headers.get("Set-Cookie", "")
                match = re.search(r"session_id=([^;]+)", cookie_header)
                if not match:
                    raise AccessControlError("Session auth failed: no session cookie")
                self._session_id = match.group(1)
                data = json.loads(response.read().decode("utf-8"))
                if "error" in data:
                    self._session_id = None
                    raise AccessControlError("Session auth failed: invalid credentials")
        except urllib.error.HTTPError as e:
            raise AccessControlError(f"Session auth failed: HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise AccessControlError(f"Session auth failed: {e.reason}") from e

    def _ensure_session(self) -> None:
        if not self._session_id:
            self._authenticate_session()

    def _make_request(self, endpoint: str, timeout: int = 30) -> Dict[str, Any]:
        return self._do_request(endpoint, timeout, allow_session_retry=True)

    def _do_request(
        self, endpoint: str, timeout: int, allow_session_retry: bool
    ) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        uses_session = False
        req = urllib.request.Request(url)
        if self.config.api_key:
            req.add_header("X-API-Key", self.config.api_key)
        elif self.config.uses_credentials:
            self._ensure_session()
            req.add_header("Cookie", f"session_id={self._session_id}")
            uses_session = True
        req.add_header("Accept", "application/json")
        if self.database:
            req.add_header("X-Odoo-Database", self.database)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                if not data.get("success", False):
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    raise AccessControlError(f"API error: {error_msg}")
                return data
        except urllib.error.HTTPError as e:
            if e.code == 401:
                if uses_session and allow_session_retry:
                    logger.info("Session expired, re-authenticating...")
                    self._session_id = None
                    return self._do_request(endpoint, timeout, allow_session_retry=False)
                if self.config.api_key:
                    raise AccessControlError(
                        "API key rejected by MCP module. "
                        "Verify ODOO_API_KEY and that the MCP module is installed."
                    ) from e
                raise AccessControlError("MCP REST API authentication failed.") from e
            elif e.code == 403:
                raise AccessControlError("Access denied to MCP endpoints") from e
            elif e.code == 404:
                raise AccessControlError(f"Endpoint not found: {endpoint}") from e
            else:
                raise AccessControlError(f"HTTP error {e.code}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise AccessControlError(f"Connection error: {e.reason}") from e
        except json.JSONDecodeError as e:
            raise AccessControlError(f"Invalid JSON response: {e}") from e
        except AccessControlError:
            raise
        except Exception as e:
            raise AccessControlError(f"Request failed: {e}") from e

    def _get_from_cache(self, key: str) -> Optional[Any]:
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired(self.cache_ttl):
                return entry.data
            del self._cache[key]
        return None

    def _set_cache(self, key: str, data: Any) -> None:
        self._cache[key] = CacheEntry(data=data, timestamp=datetime.now())

    def clear_cache(self) -> None:
        self._cache.clear()

    # ------------------------------------------------------------------
    # Public API (same interface regardless of mode)
    # ------------------------------------------------------------------

    def get_enabled_models(self) -> List[Dict[str, str]]:
        if self.config.is_json2:
            return []  # All models accessible; Odoo native ACL applies
        if self.config.is_yolo_enabled:
            return []
        cache_key = "enabled_models"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        response = self._make_request(self.MODELS_ENDPOINT)
        models = response.get("data", {}).get("models", [])
        self._set_cache(cache_key, models)
        return models

    def is_model_enabled(self, model: str) -> bool:
        if self.config.is_json2 or self.config.is_yolo_enabled:
            return True
        try:
            enabled_models = self.get_enabled_models()
            return any(m["model"] == model for m in enabled_models)
        except AccessControlError as e:
            logger.error(f"Failed to check if model {model} is enabled: {e}")
            return False

    def get_model_permissions(self, model: str) -> ModelPermissions:
        if self.config.is_json2:
            # CRUD permissions reflect execute_level only at the safe/unrestricted
            # boundary. Odoo's native ACL determines the actual per-model access.
            can_write = self.config.execute_level != "safe"
            return ModelPermissions(
                model=model,
                enabled=True,
                can_read=True,
                can_write=can_write,
                can_create=can_write,
                can_unlink=can_write,
            )

        if self.config.is_yolo_enabled:
            if self.config.yolo_mode == "read":
                return ModelPermissions(model=model, enabled=True, can_read=True)
            return ModelPermissions(
                model=model, enabled=True,
                can_read=True, can_write=True, can_create=True, can_unlink=True,
            )

        cache_key = f"permissions_{model}"
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        endpoint = self.MODEL_ACCESS_ENDPOINT.format(model=model)
        response = self._make_request(endpoint)
        data = response.get("data", {})
        permissions = ModelPermissions(
            model=data.get("model", model),
            enabled=data.get("enabled", False),
            can_read=data.get("operations", {}).get("read", False),
            can_write=data.get("operations", {}).get("write", False),
            can_create=data.get("operations", {}).get("create", False),
            can_unlink=data.get("operations", {}).get("unlink", False),
        )
        self._set_cache(cache_key, permissions)
        return permissions

    def check_operation_allowed(self, model: str, operation: str) -> Tuple[bool, Optional[str]]:
        if self.config.is_json2:
            return self._json2_check(model, operation)

        if self.config.is_yolo_enabled:
            read_ops = {"read", "search", "search_read", "fields_get", "count", "search_count"}
            if operation in read_ops:
                return True, None
            if self.config.yolo_mode == "true":
                return True, None
            return False, (
                f"Write operation '{operation}' not allowed in read-only YOLO mode."
            )

        try:
            permissions = self.get_model_permissions(model)
            if not permissions.enabled:
                return False, f"Model '{model}' is not enabled for MCP access"
            if not permissions.can_perform(operation):
                return False, f"Operation '{operation}' not allowed on model '{model}'"
            return True, None
        except AccessControlError as e:
            return False, str(e)

    def validate_model_access(self, model: str, operation: str) -> None:
        allowed, error_msg = self.check_operation_allowed(model, operation)
        if not allowed:
            raise AccessControlError(error_msg or f"Access denied to {model}.{operation}")

    def check_execute_allowed(self, model: str) -> Tuple[bool, Optional[str]]:
        """Check whether execute_method is allowed for the given model.

        Applies execute_level semantics uniformly across all connection modes
        (XML-RPC YOLO, XML-RPC standard, JSON-2).  Previously, XML-RPC paths
        fell back to a write-permission check as a proxy, which ignored
        execute_level=safe and the system-model restriction at execute_level=business.

        Returns:
            (allowed, error_message) — error_message is None when allowed.
        """
        level = self.config.execute_level

        if level == "safe":
            return (
                False,
                "execute_method is not allowed at execute_level=safe. "
                "Set ODOO_EXECUTE_LEVEL=business or admin to enable it.",
            )

        if level == "admin":
            return True, None

        # level == "business": block system/infrastructure models
        if _is_system_model(model):
            return (
                False,
                f"Model '{model}' is a system model. "
                "Set ODOO_EXECUTE_LEVEL=admin to allow operations on system models.",
            )

        return True, None

    def filter_enabled_models(self, models: List[str]) -> List[str]:
        if self.config.is_json2 or self.config.is_yolo_enabled:
            return models
        try:
            enabled_models = self.get_enabled_models()
            enabled_set = {m["model"] for m in enabled_models}
            return [m for m in models if m in enabled_set]
        except AccessControlError as e:
            logger.error(f"Failed to filter models: {e}")
            return []

    def get_all_permissions(self) -> Dict[str, ModelPermissions]:
        permissions = {}
        try:
            enabled_models = self.get_enabled_models()
            for model_info in enabled_models:
                model = model_info["model"]
                try:
                    permissions[model] = self.get_model_permissions(model)
                except AccessControlError as e:
                    logger.warning(f"Failed to get permissions for {model}: {e}")
        except AccessControlError as e:
            logger.error(f"Failed to get all permissions: {e}")
        return permissions
