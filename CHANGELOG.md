# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.0] - 2026-04-17

### Added
- **JSON-2 protocol support** (`ODOO_API_PROTOCOL=json2`) for Odoo 19+ native API
- **`execute_method` tool** — call any business action on any model (validate invoices, confirm orders, send messages, install modules, etc.)
- **`discover_model_actions` tool** — discover available methods and actions for a model at runtime, independent of Odoo version
- **`execute_level` access control** (`ODOO_EXECUTE_LEVEL=safe|business|admin`) — model-category based access control without per-method allowlists
- `get_connection()` factory — transparently returns `OdooConnection` (XML-RPC) or `OdooJson2Connection` (JSON-2) based on config
- `OdooJson2Connection` — full JSON-2 implementation with same public interface as XML-RPC connection
- `is_system_model()` — identifies system/infrastructure models (`ir.*`, `base.*`, `res.users`, etc.) that require `admin` level
- `list_models` now queries `ir.model` directly in JSON-2 mode (no whitelist needed)
- Full test suite — 221 tests covering unit, integration (JSON-2 against live Odoo 19), and access control

### Changed
- Package renamed from `mcp-server-odoo` to `next-mcp-odoo` to avoid PyPI conflict
- Python module renamed from `mcp_server_odoo` to `next_mcp_odoo`
- `SERVER_VERSION` bumped to `0.6.0`

### Fixed
- JSON-2 `execute_kw`: first unknown positional arg now correctly maps to `ids` (not `arg0`)
- JSON-2 `execute_kw`: `copy` method now uses `ids` (not `id`) for consistency with JSON-2 API
- `list_models` returns actual models in JSON-2 mode instead of empty list

## [0.5.0] - Base (mcp-server-odoo)

Initial fork from [mcp-server-odoo](https://github.com/ivnvxd/mcp-server-odoo) v0.5.x.
Includes XML-RPC support, YOLO mode, MCP module integration, resources, and standard CRUD tools.
