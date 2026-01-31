"""Mention-related API routes for database explorer."""

from datetime import datetime
from math import ceil
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from wsb_tracker.api.schemas import (
    MentionResponse,
    MentionsListResponse,
    MentionFilterOptions,
    DeleteMentionsRequest,
    DeleteMentionsResponse,
)
from wsb_tracker.database import get_database
from wsb_tracker.models import SentimentLabel

router = APIRouter()


def _get_sentiment_label(compound: float) -> str:
    """Get sentiment label from compound score."""
    if compound > 0.15:
        return SentimentLabel.BULLISH.value
    elif compound < -0.15:
        return SentimentLabel.BEARISH.value
    return SentimentLabel.NEUTRAL.value


@router.get("/mentions", response_model=MentionsListResponse)
async def get_mentions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=10, le=200, description="Items per page"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
    subreddit: Optional[str] = Query(None, description="Filter by subreddit"),
    date_from: Optional[datetime] = Query(None, description="Filter by minimum date"),
    date_to: Optional[datetime] = Query(None, description="Filter by maximum date"),
    sentiment_min: Optional[float] = Query(None, ge=-1.0, le=1.0, description="Minimum sentiment"),
    sentiment_max: Optional[float] = Query(None, ge=-1.0, le=1.0, description="Maximum sentiment"),
    sort_by: str = Query("timestamp", description="Column to sort by"),
    sort_order: str = Query("desc", description="Sort direction (asc/desc)"),
) -> MentionsListResponse:
    """Get paginated mentions with filtering and sorting."""
    db = get_database()

    mentions, total = db.get_mentions_paginated(
        page=page,
        page_size=page_size,
        ticker=ticker,
        subreddit=subreddit,
        date_from=date_from,
        date_to=date_to,
        sentiment_min=sentiment_min,
        sentiment_max=sentiment_max,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    total_pages = ceil(total / page_size) if total > 0 else 1

    return MentionsListResponse(
        mentions=[
            MentionResponse(
                id=m._db_id,  # type: ignore[attr-defined]
                ticker=m.ticker,
                post_id=m.post_id,
                post_title=m.post_title,
                subreddit=m.subreddit,
                sentiment_compound=round(m.sentiment.compound, 4),
                sentiment_label=_get_sentiment_label(m.sentiment.compound),
                context=m.context,
                post_score=m.post_score,
                post_flair=m.post_flair,
                is_dd_post=m.is_dd_post,
                timestamp=m.timestamp,
            )
            for m in mentions
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/mentions/filter-options", response_model=MentionFilterOptions)
async def get_filter_options() -> MentionFilterOptions:
    """Get available filter options (distinct tickers, subreddits)."""
    db = get_database()
    options = db.get_filter_options()

    return MentionFilterOptions(
        tickers=options["tickers"],
        subreddits=options["subreddits"],
    )


@router.get("/mentions/{mention_id}", response_model=MentionResponse)
async def get_mention(mention_id: int) -> MentionResponse:
    """Get a single mention by ID."""
    db = get_database()
    mention = db.get_mention_by_id(mention_id)

    if not mention:
        raise HTTPException(status_code=404, detail=f"Mention {mention_id} not found")

    return MentionResponse(
        id=mention._db_id,  # type: ignore[attr-defined]
        ticker=mention.ticker,
        post_id=mention.post_id,
        post_title=mention.post_title,
        subreddit=mention.subreddit,
        sentiment_compound=round(mention.sentiment.compound, 4),
        sentiment_label=_get_sentiment_label(mention.sentiment.compound),
        context=mention.context,
        post_score=mention.post_score,
        post_flair=mention.post_flair,
        is_dd_post=mention.is_dd_post,
        timestamp=mention.timestamp,
    )


@router.delete("/mentions/{mention_id}")
async def delete_mention(mention_id: int) -> dict:
    """Delete a single mention."""
    db = get_database()
    deleted = db.delete_mention(mention_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Mention {mention_id} not found")

    return {"success": True, "message": f"Mention {mention_id} deleted"}


@router.post("/mentions/delete-bulk", response_model=DeleteMentionsResponse)
async def delete_mentions_bulk(request: DeleteMentionsRequest) -> DeleteMentionsResponse:
    """Delete multiple mentions by ID."""
    if not request.mention_ids:
        raise HTTPException(status_code=400, detail="No mention IDs provided")

    db = get_database()
    deleted_count = db.delete_mentions_bulk(request.mention_ids)

    return DeleteMentionsResponse(
        deleted_count=deleted_count,
        message=f"Deleted {deleted_count} of {len(request.mention_ids)} requested mentions",
    )
