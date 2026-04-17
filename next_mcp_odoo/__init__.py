"""MCP Server for Odoo - Model Context Protocol server for Odoo ERP systems."""

__version__ = "0.6.0"
__author__ = "Andrey Ivanov"
__license__ = "MPL-2.0"

from .access_control import AccessControlError, AccessController, ModelPermissions
from .config import OdooConfig, load_config
from .json2_connection import OdooJson2Connection
from .odoo_connection import OdooConnection, OdooConnectionError, create_connection, get_connection
from .server import OdooMCPServer

__all__ = [
    "OdooMCPServer",
    "OdooConfig",
    "load_config",
    "OdooConnection",
    "OdooJson2Connection",
    "OdooConnectionError",
    "create_connection",
    "get_connection",
    "AccessController",
    "AccessControlError",
    "ModelPermissions",
    "__version__",
]
