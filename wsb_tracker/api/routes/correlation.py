"""API routes for ticker correlation analysis."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from wsb_tracker.database import get_database


router = APIRouter(prefix="/correlation", tags=["correlation"])


# ==================== RESPONSE MODELS ====================


class TickerCorrelation(BaseModel):
    """Sentiment correlation between two tickers."""

    ticker_a: str
    ticker_b: str
    correlation: float
    shared_periods: int
    avg_sentiment_a: float
    avg_sentiment_b: float


class TickerCooccurrence(BaseModel):
    """Co-occurrence data for two tickers."""

    ticker_a: str
    ticker_b: str
    cooccurrence_count: int
    avg_combined_sentiment: float
    sample_post_ids: list[str] = []


class CorrelationResponse(BaseModel):
    """Response for correlation pairs."""

    correlations: list[TickerCorrelation]
    hours: int
    generated_at: datetime


class CooccurrenceResponse(BaseModel):
    """Response for co-occurrence pairs."""

    cooccurrences: list[TickerCooccurrence]
    hours: int
    generated_at: datetime


class CorrelationMatrixResponse(BaseModel):
    """Response for correlation heatmap data."""

    tickers: list[str]
    matrix: list[list[float]]
    hours: int
    generated_at: datetime


# ==================== ENDPOINTS ====================


@router.get("", response_model=CorrelationResponse)
async def get_correlations(
    hours: int = Query(24, ge=1, le=720, description="Time window in hours"),
    min_mentions: int = Query(5, ge=1, description="Min mentions per ticker"),
    min_shared_periods: int = Query(3, ge=1, description="Min overlapping time periods"),
    limit: int = Query(50, ge=1, le=200, description="Max pairs to return"),
    ticker: Optional[str] = Query(None, description="Filter to specific ticker"),
):
    """Get sentiment correlations between ticker pairs.

    Returns pairs sorted by absolute correlation strength.
    Positive correlation means sentiments move together.
    Negative correlation means sentiments move oppositely.
    """
    db = get_database()
    correlations_data = db.get_ticker_sentiment_correlation(
        hours=hours,
        min_mentions=min_mentions,
        min_shared_periods=min_shared_periods,
        limit=limit,
        ticker=ticker.upper() if ticker else None,
    )

    correlations = [
        TickerCorrelation(
            ticker_a=c["ticker_a"],
            ticker_b=c["ticker_b"],
            correlation=c["correlation"],
            shared_periods=c["shared_periods"],
            avg_sentiment_a=c["avg_sentiment_a"],
            avg_sentiment_b=c["avg_sentiment_b"],
        )
        for c in correlations_data
    ]

    return CorrelationResponse(
        correlations=correlations,
        hours=hours,
        generated_at=datetime.utcnow(),
    )


@router.get("/cooccurrence", response_model=CooccurrenceResponse)
async def get_cooccurrences(
    hours: int = Query(24, ge=1, le=720, description="Time window in hours"),
    min_cooccurrences: int = Query(2, ge=1, description="Min co-occurrences"),
    limit: int = Query(50, ge=1, le=200, description="Max pairs to return"),
    ticker: Optional[str] = Query(None, description="Filter to specific ticker"),
):
    """Get tickers frequently mentioned together in same posts.

    Returns pairs sorted by co-occurrence count.
    """
    db = get_database()
    cooccurrences_data = db.get_ticker_cooccurrence(
        hours=hours,
        min_cooccurrences=min_cooccurrences,
        limit=limit,
        ticker=ticker.upper() if ticker else None,
    )

    cooccurrences = [
        TickerCooccurrence(
            ticker_a=c["ticker_a"],
            ticker_b=c["ticker_b"],
            cooccurrence_count=c["cooccurrence_count"],
            avg_combined_sentiment=c["avg_combined_sentiment"],
            sample_post_ids=c["sample_post_ids"],
        )
        for c in cooccurrences_data
    ]

    return CooccurrenceResponse(
        cooccurrences=cooccurrences,
        hours=hours,
        generated_at=datetime.utcnow(),
    )


@router.get("/matrix", response_model=CorrelationMatrixResponse)
async def get_correlation_matrix(
    hours: int = Query(24, ge=1, le=720, description="Time window in hours"),
    limit: int = Query(15, ge=5, le=30, description="Top N tickers to include"),
):
    """Get correlation matrix for top tickers (for heatmap visualization).

    Returns an NxN matrix where matrix[i][j] is the correlation
    between tickers[i] and tickers[j].
    """
    db = get_database()

    # Get top tickers by mention count
    top_tickers_data = db.get_top_tickers(hours=hours, limit=limit)
    tickers = [t["ticker"] for t in top_tickers_data]

    if not tickers:
        return CorrelationMatrixResponse(
            tickers=[],
            matrix=[],
            hours=hours,
            generated_at=datetime.utcnow(),
        )

    # Get correlation matrix
    matrix_data = db.get_correlation_matrix(tickers=tickers, hours=hours)

    # Convert to 2D array format for frontend
    matrix = []
    for ticker_a in tickers:
        row = []
        for ticker_b in tickers:
            if ticker_a == ticker_b:
                row.append(1.0)  # Self-correlation
            elif ticker_a in matrix_data and ticker_b in matrix_data.get(ticker_a, {}):
                row.append(matrix_data[ticker_a][ticker_b])
            elif ticker_b in matrix_data and ticker_a in matrix_data.get(ticker_b, {}):
                row.append(matrix_data[ticker_b][ticker_a])
            else:
                row.append(0.0)  # No data
        matrix.append(row)

    return CorrelationMatrixResponse(
        tickers=tickers,
        matrix=matrix,
        hours=hours,
        generated_at=datetime.utcnow(),
    )
