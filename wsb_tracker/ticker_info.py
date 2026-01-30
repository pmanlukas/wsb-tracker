"""Ticker information service for fetching security names and types.

Provides two methods:
1. Yahoo Finance API via yfinance library (preferred)
2. Static cache fallback for common tickers

Usage:
    info_service = TickerInfoService()
    info = info_service.get_info("AAPL")
    print(info.name)  # "Apple Inc."
    print(info.security_type)  # "Stock"
"""

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from wsb_tracker.config import get_settings


@dataclass
class TickerInfo:
    """Information about a ticker symbol."""

    ticker: str
    name: str
    security_type: str  # Stock, ETF, Crypto, etc.
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None

    @classmethod
    def unknown(cls, ticker: str) -> "TickerInfo":
        """Create an unknown ticker info."""
        return cls(
            ticker=ticker,
            name=ticker,
            security_type="Unknown",
        )


# Static cache of common WSB tickers
KNOWN_TICKERS: dict[str, dict[str, str]] = {
    # Meme stocks
    "GME": {"name": "GameStop Corp.", "type": "Stock", "sector": "Consumer Cyclical"},
    "AMC": {"name": "AMC Entertainment", "type": "Stock", "sector": "Communication Services"},
    "BB": {"name": "BlackBerry Ltd.", "type": "Stock", "sector": "Technology"},
    "BBBY": {"name": "Bed Bath & Beyond", "type": "Stock", "sector": "Consumer Cyclical"},
    "NOK": {"name": "Nokia Corp.", "type": "Stock", "sector": "Technology"},
    "PLTR": {"name": "Palantir Technologies", "type": "Stock", "sector": "Technology"},
    "WISH": {"name": "ContextLogic Inc.", "type": "Stock", "sector": "Consumer Cyclical"},
    "CLOV": {"name": "Clover Health", "type": "Stock", "sector": "Healthcare"},
    "SOFI": {"name": "SoFi Technologies", "type": "Stock", "sector": "Financial Services"},
    "HOOD": {"name": "Robinhood Markets", "type": "Stock", "sector": "Financial Services"},

    # Tech giants
    "AAPL": {"name": "Apple Inc.", "type": "Stock", "sector": "Technology"},
    "MSFT": {"name": "Microsoft Corp.", "type": "Stock", "sector": "Technology"},
    "GOOGL": {"name": "Alphabet Inc. (Class A)", "type": "Stock", "sector": "Communication Services"},
    "GOOG": {"name": "Alphabet Inc. (Class C)", "type": "Stock", "sector": "Communication Services"},
    "AMZN": {"name": "Amazon.com Inc.", "type": "Stock", "sector": "Consumer Cyclical"},
    "META": {"name": "Meta Platforms Inc.", "type": "Stock", "sector": "Communication Services"},
    "NVDA": {"name": "NVIDIA Corp.", "type": "Stock", "sector": "Technology"},
    "TSLA": {"name": "Tesla Inc.", "type": "Stock", "sector": "Consumer Cyclical"},
    "AMD": {"name": "Advanced Micro Devices", "type": "Stock", "sector": "Technology"},
    "INTC": {"name": "Intel Corp.", "type": "Stock", "sector": "Technology"},
    "NFLX": {"name": "Netflix Inc.", "type": "Stock", "sector": "Communication Services"},

    # Financial
    "JPM": {"name": "JPMorgan Chase & Co.", "type": "Stock", "sector": "Financial Services"},
    "BAC": {"name": "Bank of America Corp.", "type": "Stock", "sector": "Financial Services"},
    "GS": {"name": "Goldman Sachs Group", "type": "Stock", "sector": "Financial Services"},
    "MS": {"name": "Morgan Stanley", "type": "Stock", "sector": "Financial Services"},
    "V": {"name": "Visa Inc.", "type": "Stock", "sector": "Financial Services"},
    "MA": {"name": "Mastercard Inc.", "type": "Stock", "sector": "Financial Services"},
    "PYPL": {"name": "PayPal Holdings", "type": "Stock", "sector": "Financial Services"},
    "SQ": {"name": "Block Inc.", "type": "Stock", "sector": "Financial Services"},
    "COIN": {"name": "Coinbase Global", "type": "Stock", "sector": "Financial Services"},

    # ETFs
    "SPY": {"name": "SPDR S&P 500 ETF", "type": "ETF", "sector": "Index Fund"},
    "QQQ": {"name": "Invesco QQQ Trust", "type": "ETF", "sector": "Index Fund"},
    "IWM": {"name": "iShares Russell 2000 ETF", "type": "ETF", "sector": "Index Fund"},
    "DIA": {"name": "SPDR Dow Jones ETF", "type": "ETF", "sector": "Index Fund"},
    "VTI": {"name": "Vanguard Total Stock Market ETF", "type": "ETF", "sector": "Index Fund"},
    "VOO": {"name": "Vanguard S&P 500 ETF", "type": "ETF", "sector": "Index Fund"},
    "ARKK": {"name": "ARK Innovation ETF", "type": "ETF", "sector": "Thematic"},
    "SOXL": {"name": "Direxion Semiconductor Bull 3X", "type": "ETF", "sector": "Leveraged"},
    "TQQQ": {"name": "ProShares UltraPro QQQ", "type": "ETF", "sector": "Leveraged"},
    "SQQQ": {"name": "ProShares UltraPro Short QQQ", "type": "ETF", "sector": "Leveraged"},
    "UVXY": {"name": "ProShares Ultra VIX Short-Term", "type": "ETF", "sector": "Volatility"},
    "GLD": {"name": "SPDR Gold Shares", "type": "ETF", "sector": "Commodities"},
    "SLV": {"name": "iShares Silver Trust", "type": "ETF", "sector": "Commodities"},
    "USO": {"name": "United States Oil Fund", "type": "ETF", "sector": "Commodities"},
    "XLF": {"name": "Financial Select Sector SPDR", "type": "ETF", "sector": "Sector"},
    "XLE": {"name": "Energy Select Sector SPDR", "type": "ETF", "sector": "Sector"},
    "XLK": {"name": "Technology Select Sector SPDR", "type": "ETF", "sector": "Sector"},

    # Index options (commonly mentioned)
    "SPX": {"name": "S&P 500 Index", "type": "Index", "sector": "Index"},
    "NDX": {"name": "NASDAQ-100 Index", "type": "Index", "sector": "Index"},
    "VIX": {"name": "CBOE Volatility Index", "type": "Index", "sector": "Volatility"},
    "DJI": {"name": "Dow Jones Industrial Average", "type": "Index", "sector": "Index"},

    # Popular individual stocks
    "NIO": {"name": "NIO Inc.", "type": "Stock", "sector": "Consumer Cyclical"},
    "RIVN": {"name": "Rivian Automotive", "type": "Stock", "sector": "Consumer Cyclical"},
    "LCID": {"name": "Lucid Group", "type": "Stock", "sector": "Consumer Cyclical"},
    "F": {"name": "Ford Motor Co.", "type": "Stock", "sector": "Consumer Cyclical"},
    "GM": {"name": "General Motors Co.", "type": "Stock", "sector": "Consumer Cyclical"},
    "DIS": {"name": "Walt Disney Co.", "type": "Stock", "sector": "Communication Services"},
    "BABA": {"name": "Alibaba Group", "type": "Stock", "sector": "Consumer Cyclical"},
    "JD": {"name": "JD.com Inc.", "type": "Stock", "sector": "Consumer Cyclical"},
    "BA": {"name": "Boeing Co.", "type": "Stock", "sector": "Industrials"},
    "CAT": {"name": "Caterpillar Inc.", "type": "Stock", "sector": "Industrials"},
    "WMT": {"name": "Walmart Inc.", "type": "Stock", "sector": "Consumer Defensive"},
    "TGT": {"name": "Target Corp.", "type": "Stock", "sector": "Consumer Defensive"},
    "COST": {"name": "Costco Wholesale Corp.", "type": "Stock", "sector": "Consumer Defensive"},
    "PFE": {"name": "Pfizer Inc.", "type": "Stock", "sector": "Healthcare"},
    "MRNA": {"name": "Moderna Inc.", "type": "Stock", "sector": "Healthcare"},
    "JNJ": {"name": "Johnson & Johnson", "type": "Stock", "sector": "Healthcare"},
    "UNH": {"name": "UnitedHealth Group", "type": "Stock", "sector": "Healthcare"},
    "XOM": {"name": "Exxon Mobil Corp.", "type": "Stock", "sector": "Energy"},
    "CVX": {"name": "Chevron Corp.", "type": "Stock", "sector": "Energy"},
    "OXY": {"name": "Occidental Petroleum", "type": "Stock", "sector": "Energy"},

    # AI/Semiconductor stocks
    "SMCI": {"name": "Super Micro Computer", "type": "Stock", "sector": "Technology"},
    "ARM": {"name": "Arm Holdings plc", "type": "Stock", "sector": "Technology"},
    "AVGO": {"name": "Broadcom Inc.", "type": "Stock", "sector": "Technology"},
    "MU": {"name": "Micron Technology", "type": "Stock", "sector": "Technology"},
    "QCOM": {"name": "Qualcomm Inc.", "type": "Stock", "sector": "Technology"},
    "TSM": {"name": "Taiwan Semiconductor", "type": "Stock", "sector": "Technology"},
    "ASML": {"name": "ASML Holding NV", "type": "Stock", "sector": "Technology"},

    # Crypto-related
    "MSTR": {"name": "MicroStrategy Inc.", "type": "Stock", "sector": "Technology"},
    "MARA": {"name": "Marathon Digital Holdings", "type": "Stock", "sector": "Financial Services"},
    "RIOT": {"name": "Riot Platforms Inc.", "type": "Stock", "sector": "Financial Services"},
    "BITF": {"name": "Bitfarms Ltd.", "type": "Stock", "sector": "Financial Services"},
}


class TickerInfoService:
    """Service for looking up ticker information."""

    def __init__(self, cache_path: Optional[Path] = None) -> None:
        """Initialize the service.

        Args:
            cache_path: Path to cache file. Uses default if not provided.
        """
        settings = get_settings()
        self.cache_path = cache_path or settings.db_path.parent / "ticker_cache.json"
        self._cache: dict[str, TickerInfo] = {}
        self._yfinance_available: Optional[bool] = None
        self._last_api_call = 0.0
        self._api_delay = 0.5  # Minimum delay between API calls

        # Load cache
        self._load_cache()

    def _load_cache(self) -> None:
        """Load ticker cache from file."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path) as f:
                    data = json.load(f)
                    for ticker, info in data.items():
                        self._cache[ticker] = TickerInfo(
                            ticker=ticker,
                            name=info.get("name", ticker),
                            security_type=info.get("security_type", "Unknown"),
                            exchange=info.get("exchange"),
                            sector=info.get("sector"),
                            industry=info.get("industry"),
                        )
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_cache(self) -> None:
        """Save ticker cache to file."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                ticker: {
                    "name": info.name,
                    "security_type": info.security_type,
                    "exchange": info.exchange,
                    "sector": info.sector,
                    "industry": info.industry,
                }
                for ticker, info in self._cache.items()
            }
            with open(self.cache_path, "w") as f:
                json.dump(data, f, indent=2)
        except OSError:
            pass

    def _check_yfinance(self) -> bool:
        """Check if yfinance is available."""
        if self._yfinance_available is None:
            try:
                import yfinance  # noqa: F401

                self._yfinance_available = True
            except ImportError:
                self._yfinance_available = False
        return self._yfinance_available

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self._last_api_call
        if elapsed < self._api_delay:
            time.sleep(self._api_delay - elapsed)
        self._last_api_call = time.time()

    def _fetch_from_yfinance(self, ticker: str) -> Optional[TickerInfo]:
        """Fetch ticker info from Yahoo Finance.

        Args:
            ticker: Ticker symbol

        Returns:
            TickerInfo or None if fetch failed
        """
        if not self._check_yfinance():
            return None

        try:
            import yfinance as yf

            self._rate_limit()
            stock = yf.Ticker(ticker)
            info = stock.info

            # Determine security type
            quote_type = info.get("quoteType", "").upper()
            security_type_map = {
                "EQUITY": "Stock",
                "ETF": "ETF",
                "MUTUALFUND": "Mutual Fund",
                "INDEX": "Index",
                "CURRENCY": "Currency",
                "CRYPTOCURRENCY": "Crypto",
                "FUTURE": "Futures",
                "OPTION": "Options",
            }
            security_type = security_type_map.get(quote_type, "Unknown")

            # Get name
            name = (
                info.get("longName")
                or info.get("shortName")
                or info.get("symbol", ticker)
            )

            return TickerInfo(
                ticker=ticker,
                name=name,
                security_type=security_type,
                exchange=info.get("exchange"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )
        except Exception:
            return None

    def _get_from_static(self, ticker: str) -> Optional[TickerInfo]:
        """Get ticker info from static cache.

        Args:
            ticker: Ticker symbol

        Returns:
            TickerInfo or None if not found
        """
        if ticker in KNOWN_TICKERS:
            data = KNOWN_TICKERS[ticker]
            return TickerInfo(
                ticker=ticker,
                name=data["name"],
                security_type=data["type"],
                sector=data.get("sector"),
            )
        return None

    def get_info(self, ticker: str, use_api: bool = True) -> TickerInfo:
        """Get information for a ticker symbol.

        Tries in order:
        1. In-memory cache
        2. Yahoo Finance API (if use_api=True and yfinance installed)
        3. Static known tickers cache
        4. Returns unknown ticker info

        Args:
            ticker: Ticker symbol (e.g., "AAPL", "GME")
            use_api: Whether to try Yahoo Finance API

        Returns:
            TickerInfo with name and security type
        """
        ticker = ticker.upper().strip().lstrip("$")

        # Check in-memory cache first
        if ticker in self._cache:
            return self._cache[ticker]

        # Try Yahoo Finance
        if use_api:
            info = self._fetch_from_yfinance(ticker)
            if info and info.name != ticker:  # Valid response
                self._cache[ticker] = info
                self._save_cache()
                return info

        # Try static cache
        info = self._get_from_static(ticker)
        if info:
            self._cache[ticker] = info
            return info

        # Return unknown
        return TickerInfo.unknown(ticker)

    def get_batch_info(
        self, tickers: list[str], use_api: bool = True
    ) -> dict[str, TickerInfo]:
        """Get information for multiple tickers.

        Args:
            tickers: List of ticker symbols
            use_api: Whether to try Yahoo Finance API

        Returns:
            Dict mapping ticker to TickerInfo
        """
        result = {}
        for ticker in tickers:
            result[ticker] = self.get_info(ticker, use_api=use_api)
        return result


# Module-level singleton
_ticker_service: Optional[TickerInfoService] = None


def get_ticker_info_service() -> TickerInfoService:
    """Get the singleton ticker info service instance."""
    global _ticker_service
    if _ticker_service is None:
        _ticker_service = TickerInfoService()
    return _ticker_service


def get_ticker_info(ticker: str, use_api: bool = True) -> TickerInfo:
    """Convenience function to get ticker info.

    Args:
        ticker: Ticker symbol
        use_api: Whether to try Yahoo Finance API

    Returns:
        TickerInfo with name and security type
    """
    return get_ticker_info_service().get_info(ticker, use_api=use_api)
