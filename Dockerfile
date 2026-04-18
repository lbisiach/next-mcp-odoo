FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml README.md ./
COPY next_mcp_odoo/ next_mcp_odoo/
RUN uv pip install --system --no-cache .

FROM python:3.12-slim-bookworm

RUN useradd -m -u 1000 mcp

COPY --from=builder --chown=mcp:mcp /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder --chown=mcp:mcp /usr/local/bin/next-mcp-odoo /usr/local/bin/

ENV PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.title="next-mcp-odoo"
LABEL org.opencontainers.image.description="MCP Server for Odoo ERP — XML-RPC (Odoo 14-19) and JSON-2 (Odoo 19+)"
LABEL org.opencontainers.image.url="https://github.com/lbisiach/next-mcp-odoo"
LABEL org.opencontainers.image.source="https://github.com/lbisiach/next-mcp-odoo"
LABEL org.opencontainers.image.licenses="MPL-2.0"

USER mcp

ENTRYPOINT ["next-mcp-odoo"]
