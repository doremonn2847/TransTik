"""Entry point: one process serving the REST API, the MCP endpoint and the job worker.

Two listeners:
  PORT        (8765) local only: /api/* for the web app, /mcp for local MCP clients.
  PUBLIC_PORT (8766) what the optional tunnel points at: ONLY /mcp/<secret>, nothing else.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from . import config, db, worker
from .mcp_server import mcp
from .routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

mcp_app = mcp.streamable_http_app(streamable_http_path="/mcp", json_response=True, stateless_http=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    await worker.start()
    async with mcp.session_manager.run():
        yield
    await worker.stop()


app = FastAPI(title="Transcript Desk", version="0.1.0", lifespan=lifespan)
app.include_router(router)
app.mount("/", mcp_app)  # serves /mcp; registered last so /api/* wins


class PublicGate:
    """Tunnel-facing ASGI app: forwards /mcp/<secret> to the MCP app and 404s everything else."""

    def __init__(self, inner, secret: str):
        self.inner, self.secret = inner, secret

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        parts = scope["path"].strip("/").split("/")
        ok = len(parts) == 2 and parts[0] == "mcp" and hmac.compare_digest(parts[1].encode(), self.secret.encode())
        if not ok:
            await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"Not found"})
            return
        # The secret is the access check here, so present the request to the MCP app as a local one.
        headers = [(k, v) for k, v in scope["headers"] if k not in (b"host", b"origin")]
        headers.append((b"host", f"localhost:{config.PORT}".encode()))
        await self.inner({**scope, "path": "/mcp", "raw_path": b"/mcp", "headers": headers}, receive, send)


async def serve() -> None:
    main = uvicorn.Server(uvicorn.Config(app, host=config.HOST, port=config.PORT, log_level="info"))
    gate = uvicorn.Server(uvicorn.Config(PublicGate(mcp_app, config.mcp_secret()), host=config.HOST,
                                         port=config.PUBLIC_PORT, log_level="warning", lifespan="off"))
    await asyncio.gather(main.serve(), gate.serve())


def run() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    run()
