"""Ticker-related API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from wsb_tracker.api.schemas import TickerResponse, TickersResponse, TickerDetailResponse
from wsb_tracker.database import get_database
from wsb_tracker.ticker_info import get_ticker_info_service
from wsb_tracker.tracker import WSBTracker

router = APIRouter()


@router.get("/tickers", response_model=TickersResponse)
async def get_tickers(
    hours: int = Query(24, ge=1, le=720, description="Time window in hours (max 30 days)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum tickers to return"),
) -> TickersResponse:
    """Get top trending tickers.

    Returns tickers sorted by mention count with heat scores, sentiment, and metadata.
    """
    tracker = WSBTracker()
    summaries = tracker.get_top_tickers(hours=hours, limit=limit)

    # Get ticker info for names and types
    info_service = get_ticker_info_service()

    tickers = []
    for s in summaries:
        info = info_service.get_info(s.ticker)
        tickers.append(
            TickerResponse(
                ticker=s.ticker,
                name=info.name,
                type=info.security_type,
                heat_score=round(s.heat_score, 2),
                mention_count=s.mention_count,
                unique_posts=s.unique_posts,
                avg_sentiment=round(s.avg_sentiment, 4),
                sentiment_label=s.sentiment_label.value,
                bullish_ratio=round(s.bullish_ratio, 4),
                trend_pct=s.mention_change_pct,
                dd_count=s.dd_count,
                total_score=s.total_score,
                first_seen=s.first_seen,
                last_seen=s.last_seen,
            )
        )

    return TickersResponse(
        tickers=tickers,
        updated_at=datetime.utcnow(),
        hours=hours,
        total=len(tickers),
    )


@router.get("/tickers/{symbol}", response_model=TickerDetailResponse)
async def get_ticker_detail(
    symbol: str,
    hours: int = Query(24, ge=1, le=720, description="Time window in hours (max 30 days)"),
) -> TickerDetailResponse:
    """Get detailed information for a specific ticker.

    Includes summary statistics and recent mentions.
    """
    symbol = symbol.upper().strip().lstrip("$")

    db = get_database()
    summary = db.get_ticker_summary(symbol, hours=hours)

    if not summary:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not found")

    # Get ticker info
    info_service = get_ticker_info_service()
    info = info_service.get_info(symbol)

    # Get recent mentions
    mentions = db.get_mentions_by_ticker(symbol, hours=hours, limit=20)
    recent_mentions = [
        {
            "post_id": m.post_id,
            "post_title": m.post_title,
            "context": m.context,
            "sentiment": m.sentiment.compound,
            "sentiment_label": m.sentiment.label.value,
            "timestamp": m.timestamp.isoformat(),
            "subreddit": m.subreddit,
            "post_score": m.post_score,
            "is_dd": m.is_dd_post,
        }
        for m in mentions
    ]

    ticker_response = TickerResponse(
        ticker=summary.ticker,
        name=info.name,
        type=info.security_type,
        heat_score=round(summary.heat_score, 2),
        mention_count=summary.mention_count,
        unique_posts=summary.unique_posts,
        avg_sentiment=round(summary.avg_sentiment, 4),
        sentiment_label=summary.sentiment_label.value,
        bullish_ratio=round(summary.bullish_ratio, 4),
        trend_pct=summary.mention_change_pct,
        dd_count=summary.dd_count,
        total_score=summary.total_score,
        first_seen=summary.first_seen,
        last_seen=summary.last_seen,
    )

    return TickerDetailResponse(
        ticker=symbol,
        name=info.name,
        type=info.security_type,
        summary=ticker_response,
        recent_mentions=recent_mentions,
    )
