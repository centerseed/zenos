"""Entrypoint for python -m zenos.interface.mcp.

Usage:
  MCP_TRANSPORT=stdio  python -m zenos.interface.mcp   # stdio (default)
  MCP_TRANSPORT=sse PORT=8080  python -m zenos.interface.mcp
  MCP_TRANSPORT=dual PORT=8080 python -m zenos.interface.mcp
"""

from __future__ import annotations

import logging
import os

from starlette.responses import JSONResponse

from zenos.interface.mcp import mcp, ApiKeyMiddleware, SseApiKeyPropagator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

transport = os.environ.get("MCP_TRANSPORT", "dual")

if transport in ("dual", "sse", "http", "streamable-http"):
    port = int(os.environ.get("PORT", "8080"))

    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from zenos.interface.admin_api import admin_routes
    from zenos.interface.crm_dashboard_api import crm_dashboard_routes
    from zenos.interface.dashboard_api import dashboard_routes
    from zenos.interface.ext_ingestion_api import app as ext_ingestion_app
    from zenos.interface.federation_api import routes as federation_routes
    from zenos.interface.marketing_dashboard_api import marketing_dashboard_routes

    if transport == "dual":
        stream_http_app = mcp.http_app(
            transport="streamable-http",
            path="/mcp",
            stateless_http=True,
        )
        sse_http_app = SseApiKeyPropagator(mcp.http_app(transport="sse", path="/sse"))

        class _PathTransportRouter:
            def __init__(self, stream_app, sse_app):
                self.stream_app = stream_app
                self.sse_app = sse_app

            async def __call__(self, scope, receive, send):
                path = scope.get("path", "")
                if path.startswith("/sse") or path.startswith("/messages/"):
                    return await self.sse_app(scope, receive, send)
                if path.startswith("/mcp"):
                    return await self.stream_app(scope, receive, send)
                response = JSONResponse({"error": "NOT_FOUND"}, status_code=404)
                return await response(scope, receive, send)

        routed_mcp_app = _PathTransportRouter(stream_http_app, sse_http_app)
        mcp_routes = [Mount("/", app=ApiKeyMiddleware(routed_mcp_app))]
        lifespan_app = stream_http_app
    elif transport == "sse":
        http_app = SseApiKeyPropagator(mcp.http_app(transport="sse", path="/sse"))
        mcp_routes = [Mount("/", app=ApiKeyMiddleware(http_app))]
        lifespan_app = http_app
    else:
        http_app = mcp.http_app(
            transport="streamable-http",
            path="/mcp",
            stateless_http=True,
        )
        mcp_routes = [Mount("/", app=ApiKeyMiddleware(http_app))]
        lifespan_app = http_app

    app = Starlette(
        routes=[
            *[Route(r.path, r.endpoint, methods=r.methods) for r in admin_routes],
            *[Route(r.path, r.endpoint, methods=r.methods) for r in dashboard_routes],
            *[Route(r.path, r.endpoint, methods=r.methods) for r in crm_dashboard_routes],
            *[Route(r.path, r.endpoint, methods=r.methods) for r in marketing_dashboard_routes],
            *[Route(r.path, r.endpoint, methods=r.methods) for r in federation_routes],
            Mount("/api/ext", app=ApiKeyMiddleware(ext_ingestion_app)),
            *mcp_routes,
        ],
        lifespan=lifespan_app.lifespan,
    )

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
else:
    mcp.run(transport="stdio")
