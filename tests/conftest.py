"""Pytest configuration and fixtures for next-mcp-odoo tests."""

import os
import socket

import pytest
from dotenv import load_dotenv

from next_mcp_odoo.config import OdooConfig

# Load .env file for tests
load_dotenv()


def is_odoo_server_available(host: str = "localhost", port: int = 8069) -> bool:
    """Check if Odoo server is reachable via TCP."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _parse_odoo_host_port() -> tuple:
    from urllib.parse import urlparse

    url = os.getenv("ODOO_URL", "http://localhost:8069")
    parsed = urlparse(url)
    return parsed.hostname or "localhost", parsed.port or 8069


_host, _port = _parse_odoo_host_port()
ODOO_SERVER_AVAILABLE = is_odoo_server_available(_host, _port)

# Detect whether JSON-2 protocol is configured
_PROTOCOL = os.getenv("ODOO_API_PROTOCOL", "xmlrpc")
JSON2_CONFIGURED = _PROTOCOL == "json2" and bool(os.getenv("ODOO_API_KEY"))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "yolo: needs running Odoo instance (vanilla XML-RPC)")
    config.addinivalue_line("markers", "mcp: needs running Odoo with MCP module installed")
    config.addinivalue_line(
        "markers",
        "json2: needs running Odoo 19+ instance with JSON-2 API and ODOO_API_PROTOCOL=json2",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests when the server is not available."""
    if ODOO_SERVER_AVAILABLE:
        return

    skip_no_server = pytest.mark.skip(reason=f"Odoo server not available at {_host}:{_port}")

    for item in items:
        if any(mark in item.keywords for mark in ("yolo", "mcp", "json2")):
            item.add_marker(skip_no_server)


# ---------------------------------------------------------------------------
# Basic fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def rate_limit_delay():
    """Placeholder — no actual delay needed."""
    yield


@pytest.fixture
def odoo_server_required():
    """Skip test if Odoo server is not available."""
    if not ODOO_SERVER_AVAILABLE:
        pytest.skip(f"Odoo server not available at {_host}:{_port}")


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def xmlrpc_config():
    """Minimal XML-RPC OdooConfig (no real server needed)."""
    return OdooConfig(
        url=os.getenv("ODOO_URL", "http://localhost:8069"),
        api_key=os.getenv("ODOO_API_KEY", "test-api-key"),
        database=os.getenv("ODOO_DB", "test_db"),
        api_protocol="xmlrpc",
    )


@pytest.fixture
def json2_config():
    """OdooConfig with JSON-2 protocol (no real server needed)."""
    return OdooConfig(
        url=os.getenv("ODOO_URL", "http://localhost:8069"),
        api_key=os.getenv("ODOO_API_KEY", "test-api-key"),
        database=os.getenv("ODOO_DB", "test_db"),
        api_protocol="json2",
        execute_level="business",
    )


@pytest.fixture
def json2_admin_config():
    """OdooConfig with JSON-2 protocol and admin execute_level."""
    return OdooConfig(
        url=os.getenv("ODOO_URL", "http://localhost:8069"),
        api_key=os.getenv("ODOO_API_KEY", "test-api-key"),
        database=os.getenv("ODOO_DB", "test_db"),
        api_protocol="json2",
        execute_level="admin",
    )


@pytest.fixture
def json2_safe_config():
    """OdooConfig with JSON-2 protocol and safe execute_level."""
    return OdooConfig(
        url=os.getenv("ODOO_URL", "http://localhost:8069"),
        api_key=os.getenv("ODOO_API_KEY", "test-api-key"),
        database=os.getenv("ODOO_DB", "test_db"),
        api_protocol="json2",
        execute_level="safe",
    )


@pytest.fixture
def live_json2_config(odoo_server_required):
    """OdooConfig for a live JSON-2 Odoo 19+ instance (requires running server)."""
    if not JSON2_CONFIGURED:
        pytest.skip("ODOO_API_PROTOCOL=json2 and ODOO_API_KEY not configured")
    return OdooConfig(
        url=os.getenv("ODOO_URL"),
        api_key=os.getenv("ODOO_API_KEY"),
        database=os.getenv("ODOO_DB"),
        api_protocol="json2",
        execute_level=os.getenv("ODOO_EXECUTE_LEVEL", "business"),
    )


@pytest.fixture
def test_config_with_server_check(odoo_server_required):
    """Config used in integration tests — skips if server not available."""
    if not os.getenv("ODOO_URL"):
        pytest.skip("ODOO_URL environment variable not set")
    if not os.getenv("ODOO_API_KEY") and not os.getenv("ODOO_PASSWORD"):
        pytest.skip("Neither ODOO_API_KEY nor ODOO_PASSWORD set")
    return OdooConfig(
        url=os.getenv("ODOO_URL"),
        api_key=os.getenv("ODOO_API_KEY") or None,
        username=os.getenv("ODOO_USER") or None,
        password=os.getenv("ODOO_PASSWORD") or None,
        database=os.getenv("ODOO_DB"),
        api_protocol=os.getenv("ODOO_API_PROTOCOL", "xmlrpc"),
        execute_level=os.getenv("ODOO_EXECUTE_LEVEL", "business"),
    )
