"""Statistics API routes."""

import os

from fastapi import APIRouter

from wsb_tracker.api.schemas import StatsResponse
from wsb_tracker.config import get_settings
from wsb_tracker.database import get_database

router = APIRouter()


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get database statistics."""
    db = get_database()
    stats = db.get_stats()

    # Get database file size
    settings = get_settings()
    db_path = settings.db_path
    db_size_mb = 0.0
    if db_path.exists():
        db_size_mb = round(os.path.getsize(db_path) / (1024 * 1024), 2)

    return StatsResponse(
        total_mentions=stats.get("total_mentions", 0),
        unique_tickers=stats.get("unique_tickers", 0),
        total_posts=stats.get("total_posts", 0),
        total_snapshots=stats.get("total_snapshots", 0),
        total_alerts=stats.get("total_alerts", 0),
        unacknowledged_alerts=stats.get("unacknowledged_alerts", 0),
        oldest_mention=stats.get("oldest_mention"),
        newest_mention=stats.get("newest_mention"),
        database_size_mb=db_size_mb,
    )
