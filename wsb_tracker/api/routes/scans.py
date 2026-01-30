"""Scan-related API routes."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from wsb_tracker.api.schemas import ScanStartResponse, SnapshotResponse, SnapshotsResponse
from wsb_tracker.api.websocket import manager
from wsb_tracker.database import get_database
from wsb_tracker.tracker import WSBTracker

router = APIRouter()

# Track active scans
_active_scans: dict[str, dict] = {}


async def run_scan_task(scan_id: str, limit: int, subreddits: list[str]) -> None:
    """Background task to run a scan."""
    try:
        _active_scans[scan_id] = {"status": "running", "started_at": datetime.utcnow()}

        # Broadcast scan started
        await manager.broadcast("scan_started", {"scan_id": scan_id})

        # Create tracker with progress callback
        tracker = WSBTracker()

        # Run the scan
        snapshot = tracker.scan(
            subreddits=subreddits,
            limit=limit,
        )

        # Broadcast progress updates periodically during scan
        await manager.broadcast(
            "scan_progress",
            {
                "scan_id": scan_id,
                "posts": snapshot.posts_analyzed,
                "tickers": snapshot.tickers_found,
            },
        )

        # Broadcast scan complete
        await manager.broadcast(
            "scan_complete",
            {
                "scan_id": scan_id,
                "posts_analyzed": snapshot.posts_analyzed,
                "tickers_found": snapshot.tickers_found,
                "duration": snapshot.scan_duration_seconds,
                "top_tickers": [s.ticker for s in snapshot.summaries[:5]],
            },
        )

        _active_scans[scan_id]["status"] = "completed"
        _active_scans[scan_id]["result"] = {
            "posts_analyzed": snapshot.posts_analyzed,
            "tickers_found": snapshot.tickers_found,
        }

    except Exception as e:
        _active_scans[scan_id]["status"] = "failed"
        _active_scans[scan_id]["error"] = str(e)
        await manager.broadcast(
            "scan_error",
            {"scan_id": scan_id, "error": str(e)},
        )


@router.post("/scan", response_model=ScanStartResponse)
async def start_scan(
    background_tasks: BackgroundTasks,
    limit: int = Query(100, ge=10, le=500, description="Posts to scan"),
    subreddits: Optional[str] = Query(None, description="Comma-separated subreddits"),
) -> ScanStartResponse:
    """Start a new scan in the background.

    The scan runs asynchronously. Subscribe to the WebSocket at /ws to receive
    progress updates and completion notifications.
    """
    scan_id = str(uuid.uuid4())[:8]

    # Parse subreddits
    subreddit_list = ["wallstreetbets"]
    if subreddits:
        subreddit_list = [s.strip() for s in subreddits.split(",") if s.strip()]

    # Start background task
    background_tasks.add_task(run_scan_task, scan_id, limit, subreddit_list)

    return ScanStartResponse(
        scan_id=scan_id,
        status="started",
        message=f"Scan started. Connect to /ws to receive updates.",
    )


@router.get("/scan/{scan_id}")
async def get_scan_status(scan_id: str) -> dict:
    """Get the status of a scan."""
    if scan_id not in _active_scans:
        return {"scan_id": scan_id, "status": "not_found"}

    return {"scan_id": scan_id, **_active_scans[scan_id]}


@router.get("/snapshots", response_model=SnapshotsResponse)
async def get_snapshots(
    limit: int = Query(10, ge=1, le=50, description="Maximum snapshots to return"),
) -> SnapshotsResponse:
    """Get recent scan snapshots."""
    db = get_database()

    # Get snapshots from database
    snapshots_data = db.get_snapshots(limit=limit)

    snapshots = []
    for s in snapshots_data:
        # Parse summaries to get top tickers
        try:
            summaries = json.loads(s.get("summaries", "[]"))
            top_tickers = [t.get("ticker", "") for t in summaries[:5]]
        except (json.JSONDecodeError, TypeError):
            top_tickers = []

        # Parse subreddits
        try:
            subreddits = json.loads(s.get("subreddits", '["wallstreetbets"]'))
        except (json.JSONDecodeError, TypeError):
            subreddits = ["wallstreetbets"]

        snapshots.append(
            SnapshotResponse(
                id=s["id"],
                timestamp=s["timestamp"],
                subreddits=subreddits,
                posts_analyzed=s.get("posts_analyzed", 0),
                tickers_found=s.get("tickers_found", 0),
                scan_duration_seconds=s.get("scan_duration_seconds", 0.0),
                source=s.get("source", "unknown"),
                top_tickers=top_tickers,
            )
        )

    return SnapshotsResponse(
        snapshots=snapshots,
        total=len(snapshots),
    )
