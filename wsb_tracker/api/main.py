"""FastAPI application entry point."""

import os
import socket
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from wsb_tracker import __version__
from wsb_tracker.api.routes import tickers, scans, alerts, stats, mentions, settings, trading_ideas, prices, correlation
from wsb_tracker.api.websocket import router as ws_router
from wsb_tracker.config import get_settings, reset_settings
from wsb_tracker.database import get_database


def _check_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def _check_existing_wsb_server(host: str, port: int) -> bool:
    """Check if WSB Tracker API is already running on this port."""
    try:
        import httpx
        response = httpx.get(f"http://{host}:{port}/api/health", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            return data.get("status") == "healthy"
    except Exception:
        pass
    return False


# Pre-flight port check when running via uvicorn directly
# Parse command line to extract host/port if running via uvicorn
def _get_uvicorn_bind_info() -> tuple[str, int] | None:
    """Extract host and port from uvicorn command line args."""
    if not any("uvicorn" in arg for arg in sys.argv):
        return None

    host = "127.0.0.1"
    port = 8000

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--host", "-h") and i + 1 < len(args):
            # Skip -h if it looks like --help
            if args[i + 1] not in ("elp", "-help"):
                host = args[i + 1]
            i += 2
        elif arg.startswith("--host="):
            host = arg.split("=", 1)[1]
            i += 1
        elif arg in ("--port", "-p") and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                pass
            i += 2
        elif arg.startswith("--port="):
            try:
                port = int(arg.split("=", 1)[1])
            except ValueError:
                pass
            i += 1
        else:
            i += 1

    return (host, port)


# Only run port check if not explicitly disabled and running via uvicorn
if os.environ.get("_WSB_SKIP_PORT_CHECK") != "1":
    _bind_info = _get_uvicorn_bind_info()
    if _bind_info is not None:
        _uvicorn_host, _uvicorn_port = _bind_info
        if not _check_port_available(_uvicorn_host, _uvicorn_port):
            if _check_existing_wsb_server(_uvicorn_host, _uvicorn_port):
                print(f"\n{'='*60}")
                print(f"⚠️  WSB Tracker API is already running on port {_uvicorn_port}!")
                print(f"{'='*60}")
                print(f"\nThe server is healthy at: http://{_uvicorn_host}:{_uvicorn_port}")
                print(f"API docs at: http://{_uvicorn_host}:{_uvicorn_port}/docs")
                print(f"\nIf you want to restart, stop the existing server first (Ctrl+C).")
                print()
            else:
                print(f"\n{'='*60}")
                print(f"❌ Port {_uvicorn_port} is already in use!")
                print(f"{'='*60}")
                print(f"\nAnother application is using this port.")
                print(f"\nOptions:")
                print(f"  • Use a different port: uvicorn wsb_tracker.api.main:app --port {_uvicorn_port + 1}")
                print(f"  • Check what's using the port: lsof -i :{_uvicorn_port}")
                print()
            sys.exit(1)

# Force settings reload to ensure .env is loaded at import time
reset_settings()
_startup_settings = get_settings()

# Also reset LLM analyzer singleton if it exists
try:
    from wsb_tracker.llm_analyzer import reset_analyzer
    reset_analyzer()
except ImportError:
    pass

# Frontend dist path
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    import logging
    logger = logging.getLogger(__name__)

    # Startup: ensure database is initialized
    db = get_database()
    _ = db  # Database initializes on first access

    # Log LLM status at startup
    settings = get_settings()
    logger.info(f"LLM Settings at startup:")
    logger.info(f"  llm_enabled: {settings.llm_enabled}")
    logger.info(f"  has_llm_credentials: {settings.has_llm_credentials}")
    if settings.llm_enabled and settings.has_llm_credentials:
        logger.info(f"  LLM analysis is ACTIVE with model: {settings.llm_model}")
    else:
        if not settings.llm_enabled:
            logger.info("  LLM analysis is DISABLED (set WSB_LLM_ENABLED=true to enable)")
        elif not settings.has_llm_credentials:
            logger.info("  LLM analysis missing credentials (set ANTHROPIC_API_KEY or WSB_ANTHROPIC_API_KEY)")

    yield

    # Shutdown: cleanup if needed
    pass


app = FastAPI(
    title="WSB Tracker API",
    description="Track stock ticker mentions on r/wallstreetbets with sentiment analysis",
    version=__version__,
    lifespan=lifespan,
)

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(tickers.router, prefix="/api", tags=["tickers"])
app.include_router(scans.router, prefix="/api", tags=["scans"])
app.include_router(alerts.router, prefix="/api", tags=["alerts"])
app.include_router(stats.router, prefix="/api", tags=["stats"])
app.include_router(mentions.router, prefix="/api", tags=["mentions"])
app.include_router(settings.router, prefix="/api", tags=["settings"])
app.include_router(trading_ideas.router, prefix="/api", tags=["trading-ideas"])
app.include_router(trading_ideas.llm_router, prefix="/api", tags=["llm"])
app.include_router(prices.router, prefix="/api", tags=["prices"])
app.include_router(correlation.router, prefix="/api", tags=["correlation"])
app.include_router(ws_router, tags=["websocket"])


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


# Serve static frontend files in production
if FRONTEND_DIST.exists():
    # Mount assets directory for JS/CSS files
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    # Serve static files like vite.svg, favicon, etc.
    @app.get("/vite.svg")
    async def vite_svg() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "vite.svg")

    # SPA fallback - serve index.html for all non-API routes
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str) -> FileResponse:
        """Serve the SPA for any non-API route."""
        # Check if it's a file request in the dist folder
        file_path = FRONTEND_DIST / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html for SPA routing
        return FileResponse(FRONTEND_DIST / "index.html")
