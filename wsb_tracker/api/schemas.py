"""Pydantic schemas for API responses."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TickerResponse(BaseModel):
    """Single ticker summary response."""

    ticker: str
    name: str
    type: str
    heat_score: float
    mention_count: int
    unique_posts: int
    avg_sentiment: float
    sentiment_label: str
    bullish_ratio: float
    trend_pct: Optional[float] = None
    dd_count: int
    total_score: int
    first_seen: datetime
    last_seen: datetime


class TickersResponse(BaseModel):
    """List of tickers response."""

    tickers: list[TickerResponse]
    updated_at: datetime
    hours: int
    total: int


class TickerDetailResponse(BaseModel):
    """Detailed ticker response with recent mentions."""

    ticker: str
    name: str
    type: str
    summary: TickerResponse
    recent_mentions: list[dict]


class SnapshotResponse(BaseModel):
    """Scan snapshot response."""

    id: int
    timestamp: datetime
    subreddits: list[str]
    posts_analyzed: int
    tickers_found: int
    scan_duration_seconds: float
    source: str
    top_tickers: list[str]


class SnapshotsResponse(BaseModel):
    """List of snapshots response."""

    snapshots: list[SnapshotResponse]
    total: int


class ScanStartResponse(BaseModel):
    """Response when starting a scan."""

    scan_id: str
    status: str
    message: str


class AlertResponse(BaseModel):
    """Alert response."""

    id: str
    ticker: str
    alert_type: str
    message: str
    heat_score: float
    sentiment: float
    triggered_at: datetime
    acknowledged: bool


class AlertsResponse(BaseModel):
    """List of alerts response."""

    alerts: list[AlertResponse]
    total: int
    unacknowledged: int


class StatsResponse(BaseModel):
    """Database statistics response."""

    total_mentions: int
    unique_tickers: int
    total_posts: int
    total_snapshots: int
    total_alerts: int
    unacknowledged_alerts: int
    oldest_mention: Optional[datetime] = None
    newest_mention: Optional[datetime] = None
    database_size_mb: float


class WebSocketEvent(BaseModel):
    """WebSocket event message."""

    event: str
    data: dict


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: Optional[str] = None
