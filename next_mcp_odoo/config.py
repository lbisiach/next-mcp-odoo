"""Configuration management for Odoo MCP Server."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Optional

from dotenv import load_dotenv


@dataclass
class OdooConfig:
    """Configuration for Odoo connection and MCP server settings."""

    # Required fields
    url: str

    # Authentication (one method required)
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None

    # Optional fields with defaults
    database: Optional[str] = None
    log_level: str = "INFO"
    default_limit: int = 10
    max_limit: int = 100
    max_smart_fields: int = 15
    locale: Optional[str] = None

    # MCP transport configuration
    transport: Literal["stdio", "streamable-http"] = "stdio"
    host: str = "localhost"
    port: int = 8000

    # YOLO mode configuration (XML-RPC only)
    yolo_mode: str = "off"  # "off", "read", or "true"

    # API protocol selection
    # xmlrpc: standard XML-RPC (Odoo 14-19, requires MCP module in standard mode)
    # json2: native JSON-2 API (Odoo 19+, requires only API key, no extra module)
    api_protocol: Literal["xmlrpc", "json2"] = "xmlrpc"

    # Execute level for execute_method tool (json2 and yolo modes)
    # safe:     read-only operations only
    # business: any method on business models (default)
    # admin:    any method including system models (ir.*, res.users, etc.)
    execute_level: Literal["safe", "business", "admin"] = "business"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.url:
            raise ValueError("ODOO_URL is required")

        if not self.url.startswith(("http://", "https://")):
            raise ValueError("ODOO_URL must start with http:// or https://")

        # Validate YOLO mode
        valid_yolo_modes = {"off", "read", "true"}
        if self.yolo_mode not in valid_yolo_modes:
            raise ValueError(
                f"Invalid YOLO mode: {self.yolo_mode}. "
                f"Must be one of: {', '.join(valid_yolo_modes)}"
            )

        # Validate protocol
        valid_protocols = {"xmlrpc", "json2"}
        if self.api_protocol not in valid_protocols:
            raise ValueError(
                f"Invalid API protocol: {self.api_protocol}. "
                f"Must be one of: {', '.join(valid_protocols)}"
            )

        # JSON-2 requires API key
        if self.api_protocol == "json2" and not self.api_key:
            raise ValueError(
                "JSON-2 protocol requires an API key (ODOO_API_KEY). "
                "Create one in Odoo: Preferences → Account Security → New API Key"
            )

        # JSON-2 does not support YOLO mode (it's native Odoo, no custom module needed)
        if self.api_protocol == "json2" and self.yolo_mode != "off":
            raise ValueError(
                "YOLO mode is only available with xmlrpc protocol. "
                "JSON-2 connects directly to Odoo without needing a custom module."
            )

        # Validate execute_level
        valid_levels = {"safe", "business", "admin"}
        if self.execute_level not in valid_levels:
            raise ValueError(
                f"Invalid execute level: {self.execute_level}. "
                f"Must be one of: {', '.join(valid_levels)}"
            )

        # Validate authentication
        has_api_key = bool(self.api_key)
        has_credentials = bool(self.username and self.password)

        if self.is_yolo_enabled:
            if not has_credentials and not (has_api_key and self.username):
                raise ValueError("YOLO mode requires either username/password or username/API key")
        elif self.api_protocol == "json2":
            pass  # Already checked api_key above
        else:
            if not has_api_key and not has_credentials:
                raise ValueError(
                    "Authentication required: provide either ODOO_API_KEY or "
                    "both ODOO_USER and ODOO_PASSWORD"
                )

        # Validate numeric fields
        if self.default_limit <= 0:
            raise ValueError("ODOO_MCP_DEFAULT_LIMIT must be positive")

        if self.max_limit <= 0:
            raise ValueError("ODOO_MCP_MAX_LIMIT must be positive")

        if self.default_limit > self.max_limit:
            raise ValueError("ODOO_MCP_DEFAULT_LIMIT cannot exceed ODOO_MCP_MAX_LIMIT")

        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid log level: {self.log_level}. "
                f"Must be one of: {', '.join(valid_log_levels)}"
            )

        # Validate transport
        valid_transports = {"stdio", "streamable-http"}
        if self.transport not in valid_transports:
            raise ValueError(
                f"Invalid transport: {self.transport}. "
                f"Must be one of: {', '.join(valid_transports)}"
            )

        if self.port <= 0 or self.port > 65535:
            raise ValueError("Port must be between 1 and 65535")

    @property
    def uses_api_key(self) -> bool:
        return bool(self.api_key)

    @property
    def uses_credentials(self) -> bool:
        return bool(self.username and self.password)

    @property
    def is_yolo_enabled(self) -> bool:
        return self.yolo_mode != "off"

    @property
    def is_write_allowed(self) -> bool:
        return self.yolo_mode == "true"

    @property
    def is_json2(self) -> bool:
        """Check if using JSON-2 protocol."""
        return self.api_protocol == "json2"

    def get_endpoint_paths(self) -> Dict[str, str]:
        """Get appropriate XML-RPC endpoint paths based on mode."""
        if self.is_yolo_enabled:
            return {"db": "/xmlrpc/db", "common": "/xmlrpc/2/common", "object": "/xmlrpc/2/object"}
        else:
            return {
                "db": "/xmlrpc/db",
                "common": "/mcp/xmlrpc/common",
                "object": "/mcp/xmlrpc/object",
            }

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "OdooConfig":
        return load_config(env_file)


def load_config(env_file: Optional[Path] = None) -> OdooConfig:
    """Load configuration from environment variables and .env file."""
    if env_file:
        if not env_file.exists():
            raise ValueError(
                f"Configuration file not found: {env_file}\n"
                "Please create a .env file based on .env.example"
            )
        load_dotenv(env_file)
    else:
        default_env = Path(".env")
        env_loaded = False

        if default_env.exists():
            load_dotenv(default_env)
            env_loaded = True

        if not env_loaded and not os.getenv("ODOO_URL"):
            raise ValueError(
                "No .env file found and ODOO_URL not set in environment.\n"
                "Please create a .env file based on .env.example or set environment variables."
            )

    def get_int_env(key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"{key} must be a valid integer") from None

    def get_yolo_mode() -> str:
        yolo_env = os.getenv("ODOO_YOLO", "off").strip().lower()
        if yolo_env in ["", "false", "0", "off", "no"]:
            return "off"
        elif yolo_env in ["read", "readonly", "read-only"]:
            return "read"
        elif yolo_env in ["true", "1", "yes", "full"]:
            return "true"
        else:
            return yolo_env

    config = OdooConfig(
        url=os.getenv("ODOO_URL", "").strip(),
        api_key=os.getenv("ODOO_API_KEY", "").strip() or None,
        username=os.getenv("ODOO_USER", "").strip() or None,
        password=os.getenv("ODOO_PASSWORD", "").strip() or None,
        database=os.getenv("ODOO_DB", "").strip() or None,
        log_level=os.getenv("ODOO_MCP_LOG_LEVEL", "INFO").strip(),
        default_limit=get_int_env("ODOO_MCP_DEFAULT_LIMIT", 10),
        max_limit=get_int_env("ODOO_MCP_MAX_LIMIT", 100),
        max_smart_fields=get_int_env("ODOO_MCP_MAX_SMART_FIELDS", 15),
        transport=os.getenv("ODOO_MCP_TRANSPORT", "stdio").strip(),
        host=os.getenv("ODOO_MCP_HOST", "localhost").strip(),
        port=get_int_env("ODOO_MCP_PORT", 8000),
        locale=os.getenv("ODOO_LOCALE", "").strip() or None,
        yolo_mode=get_yolo_mode(),
        api_protocol=os.getenv("ODOO_API_PROTOCOL", "xmlrpc").strip().lower(),
        execute_level=os.getenv("ODOO_EXECUTE_LEVEL", "business").strip().lower(),
    )

    return config


_config: Optional[OdooConfig] = None


def get_config() -> OdooConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: OdooConfig) -> None:
    global _config
    _config = config


def reset_config() -> None:
    global _config
    _config = None
