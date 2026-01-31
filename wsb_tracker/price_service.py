"""Stock price fetching service with caching.

Provides real-time and historical stock prices using yfinance.
Includes caching to minimize API calls and improve response times.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import yfinance as yf
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PriceData(BaseModel):
    """Stock price data for a single ticker."""

    ticker: str
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    change_amount: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    prev_close: Optional[float] = None
    updated_at: datetime
    error: Optional[str] = None


class SparklineData(BaseModel):
    """Historical price data for sparkline charts."""

    ticker: str
    prices: list[float]
    days: int
    updated_at: datetime


class PriceService:
    """Fetches and caches stock prices from yfinance."""

    def __init__(self, cache_ttl_minutes: int = 5) -> None:
        """Initialize price service.

        Args:
            cache_ttl_minutes: How long to cache price data (default 5 minutes)
        """
        self._price_cache: dict[str, tuple[PriceData, datetime]] = {}
        self._sparkline_cache: dict[str, tuple[SparklineData, datetime]] = {}
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.sparkline_cache_ttl = timedelta(minutes=15)

    def get_price(self, ticker: str) -> PriceData:
        """Get current price for a ticker with caching.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')

        Returns:
            PriceData with current price info or error
        """
        ticker = ticker.upper()

        # Check cache
        if ticker in self._price_cache:
            data, cached_at = self._price_cache[ticker]
            if datetime.now() - cached_at < self.cache_ttl:
                return data

        # Fetch from yfinance
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Handle case where ticker doesn't exist
            if not info or info.get("regularMarketPrice") is None:
                price_data = PriceData(
                    ticker=ticker,
                    updated_at=datetime.now(),
                    error="Ticker not found or no market data",
                )
            else:
                price_data = PriceData(
                    ticker=ticker,
                    current_price=info.get("currentPrice") or info.get("regularMarketPrice"),
                    change_percent=info.get("regularMarketChangePercent"),
                    change_amount=info.get("regularMarketChange"),
                    volume=info.get("volume"),
                    market_cap=info.get("marketCap"),
                    day_high=info.get("dayHigh"),
                    day_low=info.get("dayLow"),
                    prev_close=info.get("previousClose"),
                    updated_at=datetime.now(),
                )

            self._price_cache[ticker] = (price_data, datetime.now())
            return price_data

        except Exception as e:
            logger.error(f"Error fetching price for {ticker}: {e}")
            return PriceData(
                ticker=ticker,
                updated_at=datetime.now(),
                error=str(e),
            )

    def get_prices_batch(self, tickers: list[str]) -> dict[str, PriceData]:
        """Get prices for multiple tickers.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dict mapping ticker to PriceData
        """
        results = {}
        for ticker in tickers:
            results[ticker.upper()] = self.get_price(ticker)
        return results

    def get_sparkline(self, ticker: str, days: int = 7) -> SparklineData:
        """Get closing prices for sparkline chart.

        Args:
            ticker: Stock ticker symbol
            days: Number of days of history (default 7)

        Returns:
            SparklineData with price history
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_{days}"

        # Check cache
        if cache_key in self._sparkline_cache:
            data, cached_at = self._sparkline_cache[cache_key]
            if datetime.now() - cached_at < self.sparkline_cache_ttl:
                return data

        # Fetch from yfinance
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=f"{days}d")

            if hist.empty:
                prices = []
            else:
                prices = hist["Close"].tolist()

            sparkline = SparklineData(
                ticker=ticker,
                prices=prices,
                days=days,
                updated_at=datetime.now(),
            )

            self._sparkline_cache[cache_key] = (sparkline, datetime.now())
            return sparkline

        except Exception as e:
            logger.error(f"Error fetching sparkline for {ticker}: {e}")
            return SparklineData(
                ticker=ticker,
                prices=[],
                days=days,
                updated_at=datetime.now(),
            )

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._price_cache.clear()
        self._sparkline_cache.clear()


# Singleton instance
_service: Optional[PriceService] = None


def get_price_service() -> PriceService:
    """Get the singleton price service instance."""
    global _service
    if _service is None:
        _service = PriceService()
    return _service


def reset_price_service() -> None:
    """Reset the price service singleton (useful for testing)."""
    global _service
    _service = None
