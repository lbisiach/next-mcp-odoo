# MCP Server for Odoo

[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

An MCP server that lets AI assistants (Claude, Cursor, Copilot, Windsurf, Zed, and any MCP-compatible client) interact with Odoo ERP systems through natural language.

**No Odoo module required.** Connects directly to any standard Odoo instance via XML-RPC (Odoo 14+) or the native JSON-2 API (Odoo 19+).

## How It Works

```
AI Client (Claude, Cursor, Copilot, ...)
        |
        | MCP Protocol (stdio or HTTP)
        |
   next-mcp-odoo          <- runs on your local machine
        |
        | XML-RPC (Odoo 14-19)  or  JSON-2 (Odoo 19+)
        |
   Odoo Instance
```

The server runs on your local machine alongside the AI client. It receives tool calls via the MCP protocol, translates them into Odoo API requests, and returns results formatted for LLM consumption.

Authentication happens at the Odoo level — the server acts as the user whose API key (or username/password) you configure. All Odoo access rules apply.

### Connection Modes

There are three ways to connect, controlled by environment variables:

**XML-RPC + YOLO mode** (`ODOO_YOLO=read` or `ODOO_YOLO=true`)

Connects to any standard Odoo instance (version 14+) using the built-in XML-RPC endpoints. No extra module needed. Access control is handled by the server itself: `read` restricts to read-only operations, `true` allows full CRUD and method execution. Requires username + password (or username + API key).

**JSON-2 mode** (`ODOO_API_PROTOCOL=json2`)

Uses Odoo's native JSON-2 API, available from Odoo 19+. Requires only an API key — no extra module needed. Access control is governed by `ODOO_EXECUTE_LEVEL` (see Configuration). This is the recommended mode for Odoo 19+ instances.

**Standard mode** (default XML-RPC)

Requires the [Odoo MCP module](https://apps.odoo.com/apps/modules/19.0/mcp_server) installed on the Odoo instance. Access control is managed inside Odoo: you configure which models are accessible and what operations are allowed per model. Use this when you need fine-grained access control managed by Odoo administrators.

## Features

- Search records across any Odoo model with domain filters, pagination, and sorting
- Retrieve individual records by ID
- Create, update, and delete records with permission checks
- Execute any business method: validate invoices, confirm orders, send chatter messages, register payments, and anything else Odoo exposes
- Discover available actions for a model at runtime, resolving correct method names across Odoo versions
- Call HTTP web controller endpoints directly (JSON-2 mode only)
- Smart field selection: automatically picks the most relevant fields per model, skipping binary, HTML, and expensive computed fields
- Datetime normalization: converts Odoo's internal datetime formats to ISO 8601
- Prompt injection detection: warns when record data contains patterns that resemble prompt injection attempts
- Multi-language support via `ODOO_LOCALE`
- Model name autocomplete for MCP clients that support it

## Installation

### Prerequisites

- Python 3.10 or higher
- Access to an Odoo instance (see Connection Modes above)
- UV package manager (recommended)

### Install UV

UV runs on your local machine where the AI client is installed, not on the Odoo server.

macOS/Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows:

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After installation, restart your terminal to ensure UV is in your PATH.

### Installing via MCP Settings (Recommended)

Add this configuration to your MCP settings file:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

<details>
<summary>Claude Desktop</summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```
</details>

<details>
<summary>Claude Code</summary>

Add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```

Or use the CLI:

```bash
claude mcp add odoo \
  --env ODOO_URL=https://your-odoo-instance.com \
  --env ODOO_API_KEY=your-api-key-here \
  --env ODOO_DB=your-database-name \
  -- uvx next-mcp-odoo
```
</details>

<details>
<summary>Cursor</summary>

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```
</details>

<details>
<summary>VS Code (with GitHub Copilot)</summary>

Add to `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "odoo": {
      "type": "stdio",
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```

Note: VS Code uses `"servers"` as the root key, not `"mcpServers"`.
</details>

<details>
<summary>Windsurf</summary>

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "https://your-odoo-instance.com",
        "ODOO_API_KEY": "your-api-key-here",
        "ODOO_DB": "your-database-name"
      }
    }
  }
}
```
</details>

<details>
<summary>Zed</summary>

Add to `~/.config/zed/settings.json`:

```json
{
  "context_servers": {
    "odoo": {
      "command": {
        "path": "uvx",
        "args": ["next-mcp-odoo"],
        "env": {
          "ODOO_URL": "https://your-odoo-instance.com",
          "ODOO_API_KEY": "your-api-key-here",
          "ODOO_DB": "your-database-name"
        }
      }
    }
  }
}
```
</details>

### Alternative Installation Methods

<details>
<summary>Using Docker</summary>

Run with Docker — no Python installation required:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "ODOO_URL=http://host.docker.internal:8069",
        "-e", "ODOO_API_KEY=your-api-key-here",
        "lbisiach/next-mcp-odoo"
      ]
    }
  }
}
```

Use `host.docker.internal` instead of `localhost` to reach Odoo running on the host machine.

For HTTP transport:

```bash
docker run --rm -p 8000:8000 \
  -e ODOO_URL=http://host.docker.internal:8069 \
  -e ODOO_API_KEY=your-api-key-here \
  lbisiach/next-mcp-odoo --transport streamable-http --host 0.0.0.0
```
</details>

<details>
<summary>Using pip</summary>

```bash
pip install next-mcp-odoo
# or
pipx install next-mcp-odoo
```

Then use `next-mcp-odoo` as the command in your MCP configuration.
</details>

<details>
<summary>From source</summary>

```bash
git clone https://github.com/lbisiach/next-mcp-odoo.git
cd next-mcp-odoo
pip install -e .
```
</details>

## Configuration

### Environment Variables

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `ODOO_URL` | Yes | Your Odoo instance URL | `https://mycompany.odoo.com` |
| `ODOO_API_KEY` | Yes* | API key for authentication | `0ef5b399...` |
| `ODOO_USER` | Yes* | Username (if not using API key) | `admin` |
| `ODOO_PASSWORD` | Yes* | Password (required with `ODOO_USER`) | `admin` |
| `ODOO_DB` | No | Database name (auto-detected if not set) | `mycompany` |
| `ODOO_API_PROTOCOL` | No | API protocol: `xmlrpc` (default) or `json2` | `json2` |
| `ODOO_EXECUTE_LEVEL` | No | Method execution level (see below) | `business` |
| `ODOO_LOCALE` | No | Language/locale for Odoo responses | `es_ES` |
| `ODOO_YOLO` | No | YOLO mode for XML-RPC without the MCP module | `off`, `read`, `true` |

`ODOO_API_KEY` is required for JSON-2. For XML-RPC: either `ODOO_API_KEY` or `ODOO_USER` + `ODOO_PASSWORD`. YOLO mode requires `ODOO_USER` + `ODOO_PASSWORD` (or `ODOO_USER` + `ODOO_API_KEY`).

### ODOO_EXECUTE_LEVEL

Controls what `execute_method` and `call_web_controller` can call. Does not affect CRUD tools (create, update, delete), which are governed by Odoo's native access rules.

| Level | What is allowed |
|-------|----------------|
| `safe` | Read-only. `execute_method` and `call_web_controller` are disabled. |
| `business` | Any method on business models (`sale.*`, `account.*`, `mail.*`, etc.). System models (`ir.*`, `res.users`, `res.groups`, etc.) require `admin`. **Default.** |
| `admin` | Any method on any model, including system and infrastructure models. |

Private methods (names starting with `_`) and methods that execute arbitrary server-side code (`render_template`, `execute_code`, etc.) are always blocked regardless of `execute_level`.

### Advanced Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ODOO_MCP_DEFAULT_LIMIT` | `10` | Default number of records returned per search |
| `ODOO_MCP_MAX_LIMIT` | `100` | Maximum record limit per request |
| `ODOO_MCP_MAX_SMART_FIELDS` | `15` | Maximum fields returned by smart field selection |
| `ODOO_MCP_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ODOO_MCP_LOG_JSON` | `false` | Enable structured JSON log output |
| `ODOO_MCP_LOG_FILE` | — | Path for rotating log file (10 MB, 5 backups) |
| `ODOO_MCP_TRANSPORT` | `stdio` | Transport: `stdio` or `streamable-http` |
| `ODOO_MCP_HOST` | `localhost` | Host to bind for HTTP transport |
| `ODOO_MCP_PORT` | `8000` | Port to bind for HTTP transport |

### Transport

**stdio** (default): Standard input/output. Used by all desktop AI clients.

```bash
uvx next-mcp-odoo
```

**streamable-http**: HTTP transport for remote access or REST-style clients.

```bash
uvx next-mcp-odoo --transport streamable-http --host 0.0.0.0 --port 8000
```

The MCP endpoint will be available at `http://localhost:8000/mcp/`.

Note: SSE transport was deprecated in MCP protocol version 2025-03-26. Use `streamable-http` for HTTP-based communication. Requires MCP library v1.9.4 or higher.

## Setting up Odoo

### Generate an API Key

1. Go to Settings > Users & Companies > Users
2. Select your user
3. Under the API Keys tab, create a new key
4. Copy the key for your MCP configuration

### JSON-2 Mode (Odoo 19+, No Module Required)

JSON-2 is Odoo's native API from version 19+. It requires only an API key.

```env
ODOO_URL=https://myodoo.example.com
ODOO_API_KEY=your-api-key-here
ODOO_API_PROTOCOL=json2
ODOO_DB=mydb
ODOO_EXECUTE_LEVEL=business
```

### YOLO Mode (Any Odoo Version, No Module Required)

YOLO mode connects to the standard XML-RPC endpoints that every Odoo instance exposes. No module installation needed. Access control is enforced by the server based on the `ODOO_YOLO` value.

`ODOO_YOLO=read` — read-only access (search, read, count):

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_USER": "admin",
        "ODOO_PASSWORD": "admin",
        "ODOO_DB": "mydb",
        "ODOO_YOLO": "read"
      }
    }
  }
}
```

`ODOO_YOLO=true` — full CRUD and method execution:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "uvx",
      "args": ["next-mcp-odoo"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_USER": "admin",
        "ODOO_PASSWORD": "admin",
        "ODOO_DB": "mydb",
        "ODOO_YOLO": "true"
      }
    }
  }
}
```

In YOLO mode, access control is entirely at the Odoo user level — the server does not restrict models or operations beyond the `read`/`true` boundary. The Odoo user's own permissions still apply.

### Standard Mode (Optional — Requires the MCP Module)

Install the [mcp_server](https://apps.odoo.com/apps/modules/19.0/mcp_server) module only if you need per-model access control managed inside Odoo (e.g., different permissions for different users or models without relying on Odoo's native ACL).

1. Download and install the module in your Odoo instance
2. Go to Settings > MCP Server > Enabled Models
3. Add the models you want to expose and configure read/write/create/delete permissions per model

### Protocol Comparison

| | XML-RPC YOLO | JSON-2 | XML-RPC Standard |
|-|-------------|--------|-----------------|
| Odoo versions | 14-19+ | 19+ | 16+ |
| Module required | No | No | Yes |
| Auth | user + password (or user + API key) | API key only | API key or user + password |
| Access control | Server-side (read or full) | execute_level + Odoo native ACL | Odoo MCP module per-model config |
| `execute_method` | Available (`ODOO_YOLO=true`) | Available (via `execute_level`) | Not available (module controls this) |

## Available Tools

### search_records

Search for records in any Odoo model.

```json
{
  "model": "res.partner",
  "domain": [["is_company", "=", true], ["country_id.code", "=", "ES"]],
  "fields": ["name", "email", "phone"],
  "limit": 10,
  "offset": 0,
  "order": "name asc"
}
```

Field selection:
- Omit `fields` or set to `null`: returns a smart selection of the most relevant fields
- List of field names: returns only those fields
- `["__all__"]`: returns all fields (may be slow or cause serialization errors on some models)

### get_record

Retrieve a specific record by ID.

```json
{
  "model": "res.partner",
  "record_id": 42,
  "fields": ["name", "email", "street", "city"]
}
```

Same field selection options as `search_records`. When using smart defaults, the response includes metadata showing how many total fields are available on the model.

### list_models

List all models accessible through the current connection mode, with their allowed operations.

### create_record

Create a new record.

```json
{
  "model": "res.partner",
  "values": {
    "name": "Acme Corporation",
    "email": "contact@acme.com",
    "is_company": true
  }
}
```

### update_record

Update an existing record.

```json
{
  "model": "res.partner",
  "record_id": 42,
  "values": {
    "phone": "+1234567890",
    "website": "https://example.com"
  }
}
```

### delete_record

Delete a record.

```json
{
  "model": "res.partner",
  "record_id": 42
}
```

### execute_method

Execute any method or business action on an Odoo model. This is the primary tool for triggering Odoo workflow transitions and business logic: validating invoices, confirming orders, posting chatter messages, registering payments, archiving records, etc.

```json
{
  "model": "account.move",
  "method": "action_post",
  "ids": [42]
}
```

```json
{
  "model": "sale.order",
  "method": "message_post",
  "ids": [7],
  "kwargs": { "body": "Order reviewed and approved." }
}
```

Parameters:
- `model`: Odoo model name
- `method`: method to call
- `ids`: list of record IDs (omit for class-level methods)
- `kwargs`: named arguments passed to the method

Access is governed by `ODOO_EXECUTE_LEVEL`. Private methods and known-dangerous methods are always blocked.

### discover_model_actions

Discover available methods and actions for a model. Queries Odoo's action registry at runtime, so results always reflect the current Odoo version — no hardcoded method names. Use this before `execute_method` when you are unsure of the correct method name.

```json
{
  "model": "account.move"
}
```

Returns server actions, window actions, and common ORM methods bound to the model.

### call_web_controller

Call an Odoo HTTP web controller endpoint. For features exposed as HTTP controllers rather than ORM methods, such as Discuss direct messages.

```json
{
  "path": "/discuss/channel/create_direct_message",
  "params": { "partner_ids": [42] }
}
```

Only available with `ODOO_API_PROTOCOL=json2`. Sensitive system paths (`/web/database/*`, `/xmlrpc/*`, etc.) are blocked.

### list_resource_templates

List the available resource URI patterns.

## Resources

Resources provide direct read access to Odoo data via URI:

| URI Pattern | Description |
|------------|-------------|
| `odoo://{model}/record/{id}` | Retrieve a specific record by ID |
| `odoo://{model}/search` | First 10 records in a model |
| `odoo://{model}/count` | Total record count for a model |
| `odoo://{model}/fields` | Field definitions and metadata for a model |

Resources do not support query parameters. For filtering, pagination, and field selection, use the `search_records` tool.

## Smart Field Selection

When the `fields` parameter is omitted, the server scores each field on the model and returns the top 15 by default (`ODOO_MCP_MAX_SMART_FIELDS`).

Scoring logic:
- `id`, `name`, `display_name`, `active`: always included
- Required fields: high priority
- Stored, searchable fields: prefer over computed/non-stored
- Business-relevant patterns (`state`, `amount`, `date`, `partner`, `email`, `phone`, etc.): bonus
- Binary, HTML, image, one2many, many2many fields: excluded entirely
- Non-stored computed fields: low priority

The response includes metadata showing how many fields were returned versus how many are available on the model.

## Usage Examples

Once configured, you can ask the AI assistant:

Search and retrieve:
- "Show me all customers from Spain"
- "Find products with stock below 10 units"
- "List today's sales orders over $1000"
- "Search for unpaid invoices from last month"
- "Count how many active employees we have"

Create and manage:
- "Create a new customer contact for Acme Corporation"
- "Add a new product called 'Premium Widget' with price $99.99"
- "Update the phone number for customer John Doe to +1-555-0123"
- "Change the status of order SO/2024/001 to confirmed"

Business actions:
- "Validate invoice INV/2024/001"
- "Confirm sale order SO/2024/005"
- "Send a message to the team on purchase order PO/2024/010"
- "Register payment for invoice 42"
- "Archive all inactive customers"

## Security

- Always use HTTPS for production instances
- Keep API keys secure and rotate them regularly
- Each API key is tied to an Odoo user — that user's access rules apply
- `execute_level` limits what business methods can be called at the MCP layer
- Private methods and known-dangerous methods (e.g., `render_template`, `execute_code`) are blocked regardless of `execute_level`
- Record data returned from Odoo is scanned for prompt injection patterns

## Troubleshooting

<details>
<summary>Connection Issues</summary>

1. Verify your Odoo URL is correct and accessible
2. Check that your firewall allows connections to the Odoo port
3. If using Standard mode (with the MCP module), verify it is installed by visiting `https://your-odoo.com/mcp/health`
</details>

<details>
<summary>Authentication Errors</summary>

1. Verify your API key is active (Settings > Users > API Keys)
2. Check that the user has appropriate permissions in Odoo
3. For YOLO mode, make sure `ODOO_USER` and `ODOO_PASSWORD` are both set
4. Ensure 2FA is not enabled for username/password auth
</details>

<details>
<summary>Model Access Errors</summary>

- YOLO mode: verify the Odoo user has access to that model in Odoo's native security settings
- JSON-2 mode: check `ODOO_EXECUTE_LEVEL` — system models (`ir.*`, `res.users`) require `admin`
- Standard mode (MCP module): go to Settings > MCP Server > Enabled Models and verify the model is listed with the correct permissions
</details>

<details>
<summary>"spawn uvx ENOENT" Error</summary>

UV is not installed or not in your PATH.

Install UV (see Installation section), then restart your terminal.

On macOS, Claude Desktop does not inherit your shell PATH. Try launching Claude from Terminal:

```bash
open -a "Claude"
```

Or find the full path to uvx and use it in the config:

```bash
which uvx
# /Users/yourname/.local/bin/uvx
```

```json
{
  "command": "/Users/yourname/.local/bin/uvx",
  "args": ["next-mcp-odoo"]
}
```
</details>

<details>
<summary>Database Configuration Issues</summary>

Some Odoo instances restrict database listing for security. Specify `ODOO_DB` explicitly:

```json
{
  "env": {
    "ODOO_URL": "https://your-odoo.com",
    "ODOO_API_KEY": "your-key",
    "ODOO_DB": "your-database-name"
  }
}
```
</details>

<details>
<summary>"SSL: CERTIFICATE_VERIFY_FAILED" Error</summary>

Add the SSL certificate path to your environment configuration:

```json
{
  "env": {
    "ODOO_URL": "https://your-odoo.com",
    "ODOO_API_KEY": "your-key",
    "SSL_CERT_FILE": "/etc/ssl/cert.pem"
  }
}
```
</details>

<details>
<summary>Debug Mode</summary>

Enable debug logging:

```json
{
  "env": {
    "ODOO_MCP_LOG_LEVEL": "DEBUG"
  }
}
```
</details>

## Development

<details>
<summary>Running from source</summary>

```bash
git clone https://github.com/lbisiach/next-mcp-odoo.git
cd next-mcp-odoo
pip install -e ".[dev]"

# Run tests
uv run python -m pytest

# Run the server
python -m next_mcp_odoo

# Check version
python -m next_mcp_odoo --version
```
</details>

<details>
<summary>Testing with MCP Inspector</summary>

```bash
npx @modelcontextprotocol/inspector uvx next-mcp-odoo
```
</details>

## Testing

```bash
# Unit tests (no Odoo needed)
uv run python -m pytest tests/ -v

# Run specific modules
uv run python -m pytest tests/test_tools.py tests/test_security.py -v
```

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) — see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome. See the [CONTRIBUTING](CONTRIBUTING.md) guide for details.

## Acknowledgements

This project is based on and extends [mcp-server-odoo](https://github.com/ivnvxd/mcp-server-odoo) by [@ivnvxd](https://github.com/ivnvxd). The original project provides XML-RPC support for Odoo through the MCP protocol. `next-mcp-odoo` adds native JSON-2 API support (Odoo 19+), the `execute_method` and `discover_model_actions` tools, `execute_level` access control, YOLO mode for module-free access, and security hardening.

## Support

If you find this project helpful, a star on GitHub is appreciated.
