"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from wsb_tracker import __version__
from wsb_tracker.api.routes import tickers, scans, alerts, stats
from wsb_tracker.api.websocket import router as ws_router
from wsb_tracker.database import get_database


# Frontend dist path
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup: ensure database is initialized
    db = get_database()
    _ = db  # Database initializes on first access

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
