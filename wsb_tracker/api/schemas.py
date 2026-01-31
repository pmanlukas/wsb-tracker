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


# ==================== MENTION SCHEMAS ====================


class MentionResponse(BaseModel):
    """Single mention response with all fields."""

    id: int
    ticker: str
    post_id: str
    post_title: str
    subreddit: str
    sentiment_compound: float
    sentiment_label: str
    context: str
    post_score: int
    post_flair: Optional[str]
    is_dd_post: bool
    timestamp: datetime


class MentionsListResponse(BaseModel):
    """Paginated mentions response."""

    mentions: list[MentionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MentionFilterOptions(BaseModel):
    """Available filter options for mentions."""

    tickers: list[str]
    subreddits: list[str]


class DeleteMentionsRequest(BaseModel):
    """Request to delete specific mentions."""

    mention_ids: list[int]


class DeleteMentionsResponse(BaseModel):
    """Response after deleting mentions."""

    deleted_count: int
    message: str


# ==================== SETTINGS SCHEMAS ====================


class ScanSettingsRequest(BaseModel):
    """Request to update scan settings."""

    subreddits: list[str]
    scan_limit: int
    request_delay: float
    min_score: int
    scan_sort: str


class ScanSettingsResponse(BaseModel):
    """Current scan settings response."""

    subreddits: list[str]
    scan_limit: int
    request_delay: float
    min_score: int
    scan_sort: str
    available_sorts: list[str] = ["hot", "new", "rising", "top"]


# ==================== TRADING IDEAS SCHEMAS ====================


class TradingIdeaResponse(BaseModel):
    """Single trading idea response."""

    id: int
    ticker: str
    post_id: str
    mention_id: Optional[int] = None
    has_actionable_idea: bool
    direction: Optional[str] = None  # bullish/bearish/neutral
    conviction: Optional[str] = None  # high/medium/low
    timeframe: Optional[str] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    catalysts: list[str] = []
    risks: list[str] = []
    key_points: list[str] = []
    post_type: Optional[str] = None
    quality_score: Optional[float] = None
    summary: Optional[str] = None
    model_used: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    # Outcome tracking fields
    outcome: Optional[str] = None  # hit_target/hit_stop/expired
    outcome_price: Optional[float] = None
    outcome_date: Optional[datetime] = None
    outcome_pnl_percent: Optional[float] = None
    outcome_notes: Optional[str] = None


class TradingIdeasListResponse(BaseModel):
    """Paginated trading ideas response."""

    ideas: list[TradingIdeaResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class TradingIdeasSummaryResponse(BaseModel):
    """Trading ideas summary statistics."""

    total_ideas: int
    actionable_count: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    high_conviction_count: int
    avg_quality: float


class TradingIdeasFilterOptions(BaseModel):
    """Filter options for trading ideas."""

    directions: list[str] = ["bullish", "bearish", "neutral"]
    convictions: list[str] = ["high", "medium", "low"]
    post_types: list[str] = ["dd", "yolo", "gain_loss", "meme", "news", "discussion", "question", "other"]
    timeframes: list[str] = ["intraday", "swing", "weeks", "months", "long_term"]


class OutcomeRequest(BaseModel):
    """Request to record outcome of a trading idea."""

    outcome: str  # hit_target/hit_stop/expired
    outcome_price: float
    notes: Optional[str] = None


class PerformanceStatsResponse(BaseModel):
    """Performance statistics for trading ideas."""

    total_ideas: int
    outcomes_recorded: int
    hit_target_count: int
    hit_stop_count: int
    expired_count: int
    win_rate: float
    win_rate_by_direction: dict[str, float]
    win_rate_by_conviction: dict[str, float]
    avg_pnl_percent: float


# ==================== LLM USAGE SCHEMAS ====================


class LLMUsageDayResponse(BaseModel):
    """LLM usage for a single day."""

    date: str
    provider: str
    model: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float


class LLMUsageResponse(BaseModel):
    """LLM usage statistics response."""

    today: dict
    period_summary: dict
    daily_usage: list[LLMUsageDayResponse]


class LLMStatusResponse(BaseModel):
    """LLM configuration and status response."""

    enabled: bool
    has_credentials: bool
    model: str
    min_post_score: int
    analyze_dd_only: bool
    max_daily_calls: int
    today_calls: int
    today_cost: float
    daily_limit_reached: bool


class AnalyzePostRequest(BaseModel):
    """Request to manually analyze a post."""

    post_id: str
    ticker: Optional[str] = None
    force: bool = False


class AnalyzePostResponse(BaseModel):
    """Response from manual post analysis."""

    success: bool
    ideas_count: int
    ideas: list[TradingIdeaResponse] = []
    tokens_used: int = 0
    cached: bool = False
    error: Optional[str] = None
