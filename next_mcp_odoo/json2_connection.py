"""Odoo JSON-2 API connection management.

Implements the same public interface as OdooConnection but uses the
native JSON-2 HTTP API introduced in Odoo 19 instead of XML-RPC.

Endpoint format: POST {base_url}/json/2/{model}/{method}
Authentication:  Authorization: Bearer {api_key}
Database:        X-Odoo-Database: {db}  (header, required for multi-DB)

All method arguments must be named (no positional args in JSON-2).
"""

import json
import logging
import socket
import urllib.error
import urllib.request
import xmlrpc.client
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

from .config import OdooConfig
from .error_sanitizer import ErrorSanitizer
from .performance import PerformanceManager

logger = logging.getLogger(__name__)


class OdooConnectionError(Exception):
    """Base exception for Odoo connection errors."""
    pass


# Mapping from ORM method name to its positional argument names in JSON-2.
# JSON-2 requires all arguments to be named — this table converts the
# positional args that execute_kw callers pass into the correct named params.
_METHOD_ARG_NAMES: Dict[str, List[str]] = {
    "search": ["domain"],
    "read": ["ids"],
    "search_read": ["domain"],
    "search_count": ["domain"],
    "create": ["vals"],
    "write": ["ids", "vals"],
    "unlink": ["ids"],
    "fields_get": [],
    "fields_view_get": ["view_id", "view_type"],
    "name_get": ["ids"],
    "name_search": ["name"],
    "web_search_read": ["domain"],
    "copy": ["ids"],
    "action_archive": ["ids"],
    "action_unarchive": ["ids"],
}

class OdooJson2Connection:
    """Manages JSON-2 API connections to Odoo 19+.

    Provides the same public interface as OdooConnection so that
    server.py, tools.py and resources.py can use either implementation
    transparently via duck typing.
    """

    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        config: OdooConfig,
        timeout: int = DEFAULT_TIMEOUT,
        performance_manager: Optional[PerformanceManager] = None,
    ):
        self.config = config
        self.timeout = timeout
        self._url_components = self._parse_url(config.url)
        self._performance_manager = performance_manager or PerformanceManager(config)

        # Connection / auth state
        self._connected = False
        self._authenticated = False
        self._uid: Optional[int] = None        # Not used in JSON-2 but kept for interface compat
        self._database: Optional[str] = None
        self._auth_method: Optional[str] = None
        self._server_version: Optional[str] = None

        logger.info(f"Initialized OdooJson2Connection for {self._url_components['host']}")

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def _parse_url(self, url: str) -> Dict[str, Any]:
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                raise OdooConnectionError(f"Invalid URL scheme: {parsed.scheme}")
            if not parsed.hostname:
                raise OdooConnectionError("Invalid URL: missing hostname")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            return {
                "scheme": parsed.scheme,
                "host": parsed.hostname,
                "port": port,
                "base_url": url.rstrip("/"),
            }
        except Exception as e:
            raise OdooConnectionError(f"Failed to parse URL: {e}") from e

    def _base_url(self) -> str:
        return self._url_components["base_url"]

    def _json2_url(self, model: str, method: str) -> str:
        return f"{self._base_url()}/json/2/{model}/{method}"

    # ------------------------------------------------------------------
    # HTTP request helper
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        url: str,
        body: Optional[Dict[str, Any]] = None,
        database: Optional[str] = None,
        require_auth: bool = True,
    ) -> Any:
        """Make an HTTP request to the Odoo JSON-2 API.

        Args:
            method:       HTTP verb (GET, POST, …)
            url:          Full URL
            body:         JSON body (will be serialised)
            database:     Override DB header (uses self._database by default)
            require_auth: Whether to include the Bearer token

        Returns:
            Parsed JSON response body

        Raises:
            OdooConnectionError: On any HTTP / network error
        """
        data = json.dumps(body or {}).encode("utf-8") if body is not None else b"{}"
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")

        if require_auth and self.config.api_key:
            req.add_header("Authorization", f"Bearer {self.config.api_key}")

        db = database or self._database
        if db:
            req.add_header("X-Odoo-Database", db)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode("utf-8")
                error_data = json.loads(error_body)
                msg = (
                    error_data.get("error", {}).get("message")
                    or error_data.get("error")
                    or error_body[:300]
                )
            except Exception:
                msg = str(e)
            sanitized = ErrorSanitizer.sanitize_message(str(msg))
            raise OdooConnectionError(f"HTTP {e.code}: {sanitized}") from e
        except urllib.error.URLError as e:
            raise OdooConnectionError(f"Network error: {e.reason}") from e
        except socket.timeout:
            raise OdooConnectionError(f"Connection timeout after {self.timeout}s") from None
        except json.JSONDecodeError as e:
            raise OdooConnectionError(f"Invalid JSON response: {e}") from e

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Verify the Odoo server is reachable and retrieve its version.

        Uses the standard /web/webclient/version_info endpoint which
        works without authentication in all Odoo versions.

        Raises:
            OdooConnectionError: If the server is unreachable
        """
        if self._connected:
            logger.warning("Already connected to Odoo")
            return

        try:
            url = f"{self._base_url()}/web/webclient/version_info"
            body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": {}}).encode("utf-8")
            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = data.get("result", data)
                self._server_version = result.get("server_version")
        except OdooConnectionError:
            raise
        except Exception as e:
            raise OdooConnectionError(f"Cannot reach Odoo server at {self._base_url()}: {e}") from e

        self._connected = True
        logger.info(
            f"Connected to Odoo {self._server_version or 'unknown'} at {self._base_url()}"
        )

    def disconnect(self, suppress_logging: bool = False) -> None:
        """Clear connection state."""
        if not self._connected:
            if not suppress_logging:
                logger.warning("Not connected to Odoo")
            return

        self._connected = False
        self._authenticated = False
        self._uid = None
        self._database = None
        self._auth_method = None

        if not suppress_logging:
            logger.info("Disconnected from Odoo (JSON-2)")

    def close(self) -> None:
        self.disconnect()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False

    def __del__(self):
        try:
            if hasattr(self, "_connected") and self._connected:
                self.disconnect(suppress_logging=True)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Database resolution
    # ------------------------------------------------------------------

    def list_databases(self) -> List[str]:
        """List databases via XML-RPC /xmlrpc/db (bootstrap only).

        JSON-2 is per-database and has no DB listing endpoint; we fall
        back to the server-wide XML-RPC db service for this purpose.
        """
        if not self._connected:
            raise OdooConnectionError("Not connected to Odoo")
        try:
            db_url = f"{self._base_url()}/xmlrpc/db"
            proxy = xmlrpc.client.ServerProxy(db_url)
            databases = proxy.list()
            logger.info(f"Found {len(databases)} databases: {databases}")
            return databases  # type: ignore[return-value]
        except Exception as e:
            raise OdooConnectionError(f"Failed to list databases: {e}") from e

    def database_exists(self, db_name: str) -> bool:
        return db_name in self.list_databases()

    def auto_select_database(self) -> str:
        if self.config.database:
            logger.info(f"Using configured database: {self.config.database}")
            return self.config.database

        try:
            databases = self.list_databases()
        except Exception as e:
            raise OdooConnectionError(
                f"Cannot list databases. Set ODOO_DB explicitly. ({e})"
            ) from e

        if not databases:
            raise OdooConnectionError("No databases found on Odoo server")
        if len(databases) == 1:
            logger.info(f"Auto-selected database: {databases[0]}")
            return databases[0]
        if "odoo" in databases:
            logger.info("Auto-selected 'odoo' database")
            return "odoo"

        raise OdooConnectionError(
            f"Multiple databases found: {databases}. Set ODOO_DB in configuration."
        )

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, database: Optional[str] = None) -> None:
        """Authenticate using the configured API key.

        Resolves the target database, then makes a lightweight JSON-2
        call to verify the Bearer token is accepted.

        Raises:
            OdooConnectionError: If not connected or authentication fails
        """
        if not self._connected:
            raise OdooConnectionError("Not connected to Odoo")

        if not self.config.api_key:
            raise OdooConnectionError(
                "JSON-2 requires an API key. "
                "Set ODOO_API_KEY (Odoo: Preferences → Account Security → New API Key)"
            )

        db_name = database or self.auto_select_database()

        # Verify the key with a lightweight call: count users (res.users)
        try:
            result = self._request(
                "POST",
                self._json2_url("res.users", "search_count"),
                {"domain": [["id", ">", 0]]},
                database=db_name,
            )
            # If we got here without an HTTP error, the key is valid
            _ = result  # result is an integer (count), we don't need it
        except OdooConnectionError as e:
            raise OdooConnectionError(f"JSON-2 authentication failed: {e}") from e

        self._database = db_name
        self._auth_method = "api_key"
        self._authenticated = True
        logger.info(f"JSON-2: Authenticated for database '{db_name}'")

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def check_health(self) -> Tuple[bool, str]:
        if not self._connected or not self._authenticated:
            return False, "Not connected"
        try:
            count = self._request(
                "POST",
                self._json2_url("res.users", "search_count"),
                {"domain": [["id", ">", 0]]},
            )
            version = self._server_version or "unknown"
            return True, f"Connected to Odoo {version} via JSON-2 (users: {count})"
        except Exception as e:
            return False, f"Health check failed: {e}"

    def test_connection(self) -> bool:
        if not self._connected:
            try:
                self.connect()
            except Exception as e:
                logger.error(f"Failed to connect: {e}")
                return False
        is_healthy, _ = self.check_health()
        return is_healthy

    # ------------------------------------------------------------------
    # Web controller calls (Discuss, mail, etc.)
    # ------------------------------------------------------------------

    def call_web_controller(
        self, path: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Call an Odoo web controller endpoint via authenticated POST.

        Used for endpoints that are HTTP controllers rather than ORM methods,
        e.g. /discuss/channel/create_direct_message, /mail/message/post, etc.

        Args:
            path:   URL path starting with '/' (e.g. '/discuss/channel/create_direct_message')
            params: JSON body to send as request params

        Returns:
            Parsed JSON response

        Raises:
            OdooConnectionError: If not authenticated or request fails
        """
        if not self._authenticated:
            raise OdooConnectionError("Not authenticated. Call authenticate() first.")

        url = f"{self._base_url()}{path}"
        # Odoo web controllers expect JSON-RPC envelope
        body = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": params or {},
        }
        result = self._request("POST", url, body)
        # Unwrap JSON-RPC envelope if present
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        if isinstance(result, dict) and "error" in result:
            err = result["error"]
            msg = err.get("data", {}).get("message") or err.get("message") or str(err)
            raise OdooConnectionError(f"Controller error: {msg}")
        return result

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute_kw(
        self, model: str, method: str, args: List[Any], kwargs: Dict[str, Any]
    ) -> Any:
        """Execute an ORM method via JSON-2.

        Converts the positional args list to named parameters using the
        _METHOD_ARG_NAMES table, then POSTs to /json/2/<model>/<method>.

        Args:
            model:  Odoo model (e.g. 'res.partner')
            method: ORM method (e.g. 'search_read')
            args:   Positional arguments (mapped to names)
            kwargs: Keyword arguments (merged into request body)

        Returns:
            Parsed JSON response from Odoo

        Raises:
            OdooConnectionError: If not authenticated or call fails
        """
        if not self._authenticated:
            raise OdooConnectionError("Not authenticated. Call authenticate() first.")

        # Map positional args to named params
        body: Dict[str, Any] = {}
        arg_names = _METHOD_ARG_NAMES.get(method, [])
        for i, arg in enumerate(args):
            if i < len(arg_names):
                body[arg_names[i]] = arg
            elif i == 0:
                # First unknown positional arg is always the ids list in JSON-2
                # (e.g. action_post, button_confirm, message_post, etc.)
                body["ids"] = arg
            else:
                body[f"arg{i}"] = arg

        # Inject locale into context
        if self.config.locale:
            if "context" not in kwargs:
                kwargs["context"] = {}
            kwargs["context"].setdefault("lang", self.config.locale)

        body.update(kwargs)

        try:
            logger.debug(f"JSON-2: {method} on {model} body={body}")
            with self._performance_manager.monitor.track_operation(f"json2_{method}_{model}"):
                result = self._request("POST", self._json2_url(model, method), body)
            logger.debug("JSON-2: operation completed")
            return result
        except OdooConnectionError:
            raise
        except Exception as e:
            sanitized = ErrorSanitizer.sanitize_message(str(e))
            raise OdooConnectionError(f"Operation failed: {sanitized}") from e

    def execute(self, model: str, method: str, *args) -> Any:
        return self.execute_kw(model, method, list(args), {})

    # ------------------------------------------------------------------
    # High-level ORM helpers (same interface as OdooConnection)
    # ------------------------------------------------------------------

    def search(self, model: str, domain: List[Any], **kwargs) -> List[int]:
        return self.execute_kw(model, "search", [domain], kwargs)

    def read(
        self, model: str, ids: List[int], fields: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        with self._performance_manager.monitor.track_operation(f"read_{model}"):
            return self.execute_kw(model, "read", [ids], kwargs)

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: Optional[List[str]] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        if fields:
            kwargs["fields"] = fields
        return self.execute_kw(model, "search_read", [domain], kwargs)

    def fields_get(
        self, model: str, attributes: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        cached = self._performance_manager.get_cached_fields(model)
        if cached and not attributes:
            return cached

        kwargs: Dict[str, Any] = {}
        if attributes:
            kwargs["attributes"] = attributes

        with self._performance_manager.monitor.track_operation(f"fields_get_{model}"):
            fields = self.execute_kw(model, "fields_get", [], kwargs)

        if not attributes:
            self._performance_manager.cache_fields(model, fields)

        return fields

    def search_count(self, model: str, domain: List[Any]) -> int:
        return self.execute_kw(model, "search_count", [domain], {})

    def create(self, model: str, values: Dict[str, Any]) -> int:
        try:
            with self._performance_manager.monitor.track_operation(f"create_{model}"):
                record_id = self.execute_kw(model, "create", [values], {})
                self._performance_manager.invalidate_record_cache(model)
                logger.info(f"Created {model} record with ID {record_id}")
                return record_id
        except Exception as e:
            logger.error(f"Failed to create {model} record: {e}")
            raise

    def write(self, model: str, ids: List[int], values: Dict[str, Any]) -> bool:
        try:
            with self._performance_manager.monitor.track_operation(f"write_{model}"):
                result = self.execute_kw(model, "write", [ids, values], {})
                for record_id in ids:
                    self._performance_manager.invalidate_record_cache(model, record_id)
                logger.info(f"Updated {len(ids)} {model} record(s)")
                return result
        except Exception as e:
            logger.error(f"Failed to update {model} records: {e}")
            raise

    def unlink(self, model: str, ids: List[int]) -> bool:
        try:
            with self._performance_manager.monitor.track_operation(f"unlink_{model}"):
                result = self.execute_kw(model, "unlink", [ids], {})
                for record_id in ids:
                    self._performance_manager.invalidate_record_cache(model, record_id)
                logger.info(f"Deleted {len(ids)} {model} record(s)")
                return result
        except Exception as e:
            logger.error(f"Failed to delete {model} records: {e}")
            raise

    def validate_database_access(self, db_name: str) -> bool:
        return self.database_exists(db_name)

    # ------------------------------------------------------------------
    # Version / URL helpers
    # ------------------------------------------------------------------

    def get_server_version(self) -> Optional[Dict[str, Any]]:
        if not self._connected:
            return None
        try:
            url = f"{self._base_url()}/web/webclient/version_info"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("result", data)
        except Exception as e:
            logger.error(f"Failed to get server version: {e}")
            return None

    def _get_major_version(self) -> Optional[int]:
        if not self._server_version:
            return None
        try:
            version = self._server_version
            if "~" in version:
                version = version.split("~", 1)[1]
            return int(version.split(".")[0])
        except (ValueError, IndexError):
            return None

    def build_record_url(self, model: str, record_id: int) -> str:
        base_url = self._url_components["base_url"]
        major = self._get_major_version()
        if major is not None and major >= 18:
            return f"{base_url}/odoo/{model}/{record_id}"
        return f"{base_url}/web#id={record_id}&model={model}&view_type=form"

    # ------------------------------------------------------------------
    # Properties (interface compatibility with OdooConnection)
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    @property
    def uid(self) -> Optional[int]:
        return self._uid

    @property
    def database(self) -> Optional[str]:
        return self._database

    @property
    def auth_method(self) -> Optional[str]:
        return self._auth_method

    @property
    def server_version(self) -> Optional[str]:
        return self._server_version

    @property
    def performance_manager(self) -> PerformanceManager:
        return self._performance_manager


@contextmanager
def create_json2_connection(
    config: OdooConfig, timeout: int = OdooJson2Connection.DEFAULT_TIMEOUT
):
    """Context manager that yields a connected + authenticated JSON-2 connection."""
    conn = OdooJson2Connection(config, timeout)
    try:
        conn.connect()
        yield conn
    finally:
        conn.disconnect()
