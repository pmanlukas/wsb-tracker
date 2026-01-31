"""API routes for trading ideas and LLM operations."""

from datetime import datetime
import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from wsb_tracker.database import get_database
from wsb_tracker.api.schemas import (
    AnalyzePostRequest,
    AnalyzePostResponse,
    LLMStatusResponse,
    LLMUsageDayResponse,
    LLMUsageResponse,
    OutcomeRequest,
    PerformanceStatsResponse,
    TradingIdeaResponse,
    TradingIdeasFilterOptions,
    TradingIdeasListResponse,
    TradingIdeasSummaryResponse,
)

router = APIRouter(prefix="/trading-ideas", tags=["trading-ideas"])
llm_router = APIRouter(prefix="/llm", tags=["llm"])


def _get_analyzer():
    """Get the LLM analyzer, raising HTTPException if unavailable."""
    try:
        from wsb_tracker.llm_analyzer import get_analyzer
        analyzer = get_analyzer()
        return analyzer
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="LLM analyzer not available. Install with: pip install wsb-tracker[llm]"
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"LLM analyzer error: {str(e)}"
        )


def _idea_to_response(idea: dict) -> TradingIdeaResponse:
    """Convert database idea dict to response model."""
    return TradingIdeaResponse(
        id=idea["id"],
        ticker=idea["ticker"],
        post_id=idea["post_id"],
        mention_id=idea.get("mention_id"),
        has_actionable_idea=idea["has_actionable_idea"],
        direction=idea.get("direction"),
        conviction=idea.get("conviction"),
        timeframe=idea.get("timeframe"),
        entry_price=idea.get("entry_price"),
        target_price=idea.get("target_price"),
        stop_loss=idea.get("stop_loss"),
        catalysts=idea.get("catalysts", []),
        risks=idea.get("risks", []),
        key_points=idea.get("key_points", []),
        post_type=idea.get("post_type"),
        quality_score=idea.get("quality_score"),
        summary=idea.get("summary"),
        model_used=idea.get("model_used"),
        analyzed_at=idea.get("analyzed_at"),
        # Outcome tracking fields
        outcome=idea.get("outcome"),
        outcome_price=idea.get("outcome_price"),
        outcome_date=idea.get("outcome_date"),
        outcome_pnl_percent=idea.get("outcome_pnl_percent"),
        outcome_notes=idea.get("outcome_notes"),
    )


# ==================== TRADING IDEAS ENDPOINTS ====================


@router.get("", response_model=TradingIdeasListResponse)
async def list_trading_ideas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=10, le=100, description="Items per page"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    direction: Optional[str] = Query(None, description="Filter by direction"),
    conviction: Optional[str] = Query(None, description="Filter by conviction level"),
    post_type: Optional[str] = Query(None, description="Filter by post type"),
    min_quality: Optional[float] = Query(None, ge=0, le=1, description="Minimum quality score"),
    actionable_only: bool = Query(False, description="Only return actionable ideas"),
    hours: Optional[int] = Query(None, ge=1, le=720, description="Limit to last N hours"),
):
    """Get paginated list of trading ideas with filtering."""
    db = get_database()

    ideas, total = db.get_trading_ideas_paginated(
        page=page,
        page_size=page_size,
        ticker=ticker,
        direction=direction,
        conviction=conviction,
        post_type=post_type,
        min_quality=min_quality,
        actionable_only=actionable_only,
        hours=hours,
    )

    return TradingIdeasListResponse(
        ideas=[_idea_to_response(idea) for idea in ideas],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total > 0 else 1,
    )


@router.get("/summary", response_model=TradingIdeasSummaryResponse)
async def get_trading_ideas_summary(
    hours: int = Query(24, ge=1, le=720, description="Time window in hours"),
):
    """Get summary statistics for trading ideas."""
    db = get_database()
    summary = db.get_trading_ideas_summary(hours=hours)

    return TradingIdeasSummaryResponse(
        total_ideas=summary["total_ideas"],
        actionable_count=summary["actionable_count"],
        bullish_count=summary["bullish_count"],
        bearish_count=summary["bearish_count"],
        neutral_count=summary["neutral_count"],
        high_conviction_count=summary["high_conviction_count"],
        avg_quality=summary["avg_quality"],
    )


@router.get("/filters", response_model=TradingIdeasFilterOptions)
async def get_filter_options():
    """Get available filter options for trading ideas."""
    return TradingIdeasFilterOptions()


@router.get("/ticker/{ticker}", response_model=list[TradingIdeaResponse])
async def get_trading_ideas_by_ticker(
    ticker: str,
    hours: int = Query(24, ge=1, le=720, description="Time window in hours"),
    limit: int = Query(20, ge=1, le=100, description="Maximum ideas to return"),
):
    """Get trading ideas for a specific ticker."""
    db = get_database()
    ideas = db.get_trading_ideas_by_ticker(ticker.upper(), hours=hours, limit=limit)
    return [_idea_to_response(idea) for idea in ideas]


@router.get("/stats/performance", response_model=PerformanceStatsResponse)
async def get_performance_stats(
    hours: int = Query(720, ge=1, le=8760, description="Lookback period in hours"),
):
    """Get win rate and performance statistics for trading ideas."""
    db = get_database()
    stats = db.get_performance_stats(hours=hours)

    return PerformanceStatsResponse(
        total_ideas=stats["total_ideas"],
        outcomes_recorded=stats["outcomes_recorded"],
        hit_target_count=stats["hit_target_count"],
        hit_stop_count=stats["hit_stop_count"],
        expired_count=stats["expired_count"],
        win_rate=stats["win_rate"],
        win_rate_by_direction=stats["win_rate_by_direction"],
        win_rate_by_conviction=stats["win_rate_by_conviction"],
        avg_pnl_percent=stats["avg_pnl_percent"],
    )


@router.get("/{idea_id}", response_model=TradingIdeaResponse)
async def get_trading_idea(idea_id: int):
    """Get a specific trading idea by ID."""
    db = get_database()
    idea = db.get_trading_idea_by_id(idea_id)

    if not idea:
        raise HTTPException(status_code=404, detail="Trading idea not found")

    return _idea_to_response(idea)


@router.patch("/{idea_id}/outcome", response_model=TradingIdeaResponse)
async def record_outcome(idea_id: int, request: OutcomeRequest):
    """Record the outcome of a trading idea.

    Use this to track whether an idea hit its target, stop, or expired.
    """
    db = get_database()

    # Validate outcome type
    if request.outcome not in ["hit_target", "hit_stop", "expired"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid outcome. Must be 'hit_target', 'hit_stop', or 'expired'"
        )

    # Update the outcome
    updated_idea = db.update_trading_idea_outcome(
        idea_id=idea_id,
        outcome=request.outcome,
        outcome_price=request.outcome_price,
        notes=request.notes or "",
    )

    if not updated_idea:
        raise HTTPException(status_code=404, detail="Trading idea not found")

    return _idea_to_response(updated_idea)


# ==================== LLM ENDPOINTS ====================


@llm_router.get("/status", response_model=LLMStatusResponse)
async def get_llm_status():
    """Get current LLM configuration and status."""
    try:
        analyzer = _get_analyzer()
        status = analyzer.get_status()
        return LLMStatusResponse(
            enabled=status.enabled,
            has_credentials=status.has_credentials,
            model=status.model,
            min_post_score=status.min_post_score,
            analyze_dd_only=status.analyze_dd_only,
            max_daily_calls=status.max_daily_calls,
            today_calls=status.today_calls,
            today_cost=status.today_cost,
            daily_limit_reached=status.daily_limit_reached,
        )
    except HTTPException:
        # Return disabled status if analyzer not available
        from wsb_tracker.config import get_settings
        settings = get_settings()
        return LLMStatusResponse(
            enabled=settings.llm_enabled,
            has_credentials=settings.has_llm_credentials,
            model=settings.llm_model,
            min_post_score=settings.llm_min_post_score,
            analyze_dd_only=settings.llm_analyze_dd_only,
            max_daily_calls=settings.llm_max_daily_calls,
            today_calls=0,
            today_cost=0.0,
            daily_limit_reached=False,
        )


@llm_router.get("/usage", response_model=LLMUsageResponse)
async def get_llm_usage(
    days: int = Query(30, ge=1, le=90, description="Days of usage to return"),
):
    """Get LLM usage statistics."""
    db = get_database()

    today = db.get_llm_usage_today()
    summary = db.get_llm_usage_summary(days=days)
    daily = db.get_llm_usage_stats(days=days)

    return LLMUsageResponse(
        today=today,
        period_summary=summary,
        daily_usage=[
            LLMUsageDayResponse(
                date=row["date"],
                provider=row["provider"],
                model=row["model"],
                calls=row["calls"],
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                estimated_cost_usd=row["estimated_cost_usd"],
            )
            for row in daily
        ],
    )


@llm_router.post("/analyze", response_model=AnalyzePostResponse)
async def analyze_post(request: AnalyzePostRequest):
    """Manually trigger LLM analysis for a post.

    This endpoint allows triggering analysis for posts that were missed
    or to force re-analysis of existing posts.
    """
    analyzer = _get_analyzer()

    if not analyzer.is_available():
        raise HTTPException(
            status_code=503,
            detail="LLM analysis not available. Check credentials and configuration."
        )

    # Check daily limit
    status = analyzer.get_status()
    if status.daily_limit_reached:
        raise HTTPException(
            status_code=429,
            detail=f"Daily LLM call limit reached ({status.max_daily_calls} calls)"
        )

    # We need the post content to analyze
    # For manual analysis, we would need to fetch the post first
    # For now, return an error indicating this needs implementation
    # TODO: Implement fetching post by ID from Reddit
    raise HTTPException(
        status_code=501,
        detail="Manual post analysis not yet implemented. Posts are analyzed automatically during scans."
    )
