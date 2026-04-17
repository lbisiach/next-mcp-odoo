"""Security utilities for next-mcp-odoo.

Provides:
- Path denylist for call_web_controller
- Method denylist / private-method guard for execute_method
- Prompt-injection scanner for record data returned to the LLM
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# call_web_controller — blocked paths
# ---------------------------------------------------------------------------

# Exact paths that must never be called via call_web_controller.
# /web/dataset/call_kw and call_button are generic ORM bridges that would
# allow a caller to bypass the execute_level access controls entirely.
BLOCKED_CONTROLLER_PATHS: frozenset[str] = frozenset(
    {
        "/web/dataset/call_kw",
        "/web/dataset/call_button",
        "/web/dataset/resequence",
        "/web/action/load",
    }
)

# Path *prefixes* that are always blocked.
# /web/database/* exposes drop/backup/restore of the whole database.
# /xmlrpc/* provides a raw XML-RPC gateway that bypasses our checks.
BLOCKED_CONTROLLER_PREFIXES: tuple[str, ...] = (
    "/web/database/",
    "/xmlrpc/",
    "/longpolling/",
    "/websocket",
)


def check_controller_path(path: str) -> tuple[bool, str]:
    """Validate a web controller path.

    Returns:
        (allowed, reason)  — reason is empty string when allowed.
    """
    if path in BLOCKED_CONTROLLER_PATHS:
        return (
            False,
            f"Path '{path}' is blocked. Use execute_method for ORM operations.",
        )
    for prefix in BLOCKED_CONTROLLER_PREFIXES:
        if path.startswith(prefix):
            return (
                False,
                f"Path prefix '{prefix}' is blocked for security reasons.",
            )
    return True, ""


# ---------------------------------------------------------------------------
# execute_method — blocked / dangerous methods
# ---------------------------------------------------------------------------

# Methods that are blocked regardless of execute_level.
# These can install arbitrary modules, run server-side Python eval, or
# perform irreversible system operations.
BLOCKED_METHODS: frozenset[str] = frozenset(
    {
        # Module lifecycle — can install/replace arbitrary Python code
        "button_immediate_install",
        "button_immediate_upgrade",
        "button_immediate_uninstall",
        "button_immediate_uninstall_wizard",
        "module_uninstall",
        # Template rendering that uses Python eval() in Odoo
        "render_template",
        "render_field",
        "_render",
        # base.automation / ir.actions.server code execution
        "execute_code",
        "_execute_action",
        "run",  # ir.actions.server.run — executes arbitrary server action code
    }
)


def check_method_name(method: str) -> tuple[bool, str]:
    """Validate a method name for execute_method.

    Blocks:
    - Private/protected methods (starting with ``_``)
    - Methods in BLOCKED_METHODS

    Returns:
        (allowed, reason)
    """
    if method.startswith("_"):
        return (
            False,
            f"Method '{method}' is not allowed. "
            "Private methods (starting with '_') cannot be called via MCP.",
        )
    if method in BLOCKED_METHODS:
        return (
            False,
            f"Method '{method}' is blocked for security reasons. "
            "It can execute arbitrary server-side code or perform irreversible system operations.",
        )
    return True, ""


# ---------------------------------------------------------------------------
# Prompt injection scanner
# ---------------------------------------------------------------------------

# Patterns that commonly appear in prompt-injection payloads embedded in data.
# This is a best-effort heuristic — it cannot catch all injections, but it
# flags the most obvious attempts so the LLM host can be warned.
_INJECTION_PATTERNS: list[re.Pattern] = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"forget\s+(your|all|the)\s+(previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior)\s+(instructions?|rules?)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(new|different|another|unrestricted)", re.IGNORECASE),
    re.compile(r"new\s+system\s+(prompt|instruction)", re.IGNORECASE),
    re.compile(r"<\s*/?system\s*>", re.IGNORECASE),
    re.compile(r"\[INST\]|\[/INST\]|\[SYS\]|\[/SYS\]"),
    re.compile(r"act\s+as\s+(a\s+)?(different|new|evil|unfiltered|unrestricted|jailbreak)", re.IGNORECASE),
    re.compile(r"(execute|run|perform)\s+(the\s+)?following\s+(instructions?|commands?|actions?)", re.IGNORECASE),
    re.compile(r"your\s+(new\s+)?(task|role|goal|purpose)\s+is\s+now", re.IGNORECASE),
]


def scan_for_prompt_injection(data: Any, max_depth: int = 4) -> list[str]:
    """Recursively scan data for prompt injection patterns.

    Args:
        data:      Any JSON-serialisable value (dict, list, str, …)
        max_depth: How deep into nested structures to scan

    Returns:
        List of suspicious string snippets (empty = clean).
    """
    findings: list[str] = []
    _scan_value(data, findings, max_depth)
    return findings


def _scan_value(value: Any, findings: list[str], depth: int) -> None:
    if depth <= 0:
        return
    if isinstance(value, str) and len(value) > 10:
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(value):
                findings.append(value[:300])
                return  # one hit per string is enough
    elif isinstance(value, dict):
        for v in value.values():
            _scan_value(v, findings, depth - 1)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _scan_value(item, findings, depth - 1)
