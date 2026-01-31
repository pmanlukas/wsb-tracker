"""Stock price API routes.

Provides endpoints for fetching real-time stock prices and sparkline data.
"""

from typing import Optional

from fastapi import APIRouter, Query

from wsb_tracker.price_service import get_price_service

router = APIRouter()


@router.get("/prices/{ticker}")
async def get_ticker_price(ticker: str) -> dict:
    """Get current price for a single ticker.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')

    Returns:
        Price data including current price, change, volume, etc.
    """
    service = get_price_service()
    price = service.get_price(ticker.upper())
    return price.model_dump()


@router.get("/prices")
async def get_prices_batch(
    tickers: str = Query(..., description="Comma-separated ticker symbols"),
) -> dict:
    """Get prices for multiple tickers in a single request.

    Args:
        tickers: Comma-separated list of ticker symbols (e.g., 'AAPL,GOOGL,MSFT')

    Returns:
        Dict with prices for each ticker and list of requested tickers
    """
    service = get_price_service()
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]

    if not ticker_list:
        return {"prices": {}, "requested": []}

    prices = service.get_prices_batch(ticker_list)

    return {
        "prices": {k: v.model_dump() for k, v in prices.items()},
        "requested": ticker_list,
    }


@router.get("/prices/{ticker}/sparkline")
async def get_sparkline(
    ticker: str,
    days: int = Query(7, ge=1, le=30, description="Number of days of history"),
) -> dict:
    """Get price history for sparkline chart visualization.

    Args:
        ticker: Stock ticker symbol
        days: Number of days of history (1-30, default 7)

    Returns:
        Sparkline data with closing prices
    """
    service = get_price_service()
    sparkline = service.get_sparkline(ticker.upper(), days)
    return sparkline.model_dump()
