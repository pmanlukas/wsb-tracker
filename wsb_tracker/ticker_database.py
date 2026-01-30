"""
Local database of valid trading symbols from authoritative sources.

This module provides a SQLite-backed database of valid tickers, populated from:
- GitHub US-Stock-Symbols repository (primary source)
- NASDAQ FTP (fallback)
- Manually curated ETFs, indices, commodities, forex, and crypto symbols
"""
import sqlite3
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TickerRecord:
    """A validated ticker record from the database."""
    symbol: str
    name: str
    exchange: str
    asset_type: str  # Stock, ETF, Index, Crypto, Commodity, Forex, Bond
    is_active: bool
    last_updated: datetime


class TickerDatabase:
    """Local database of valid trading symbols."""

    # GitHub mirror of US Stock Symbols (more reliable than FTP)
    GITHUB_SYMBOLS = "https://raw.githubusercontent.com/rreichel3/US-Stock-Symbols/main/all/all_tickers.txt"

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".wsb_tracker" / "tickers.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the ticker database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tickers (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    exchange TEXT,
                    asset_type TEXT,
                    is_active INTEGER DEFAULT 1,
                    last_updated TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON tickers(symbol)")

    def is_valid_ticker(self, symbol: str) -> bool:
        """Check if a symbol exists in the database."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT 1 FROM tickers WHERE symbol = ? AND is_active = 1",
                (symbol.upper(),)
            ).fetchone()
            return result is not None

    def get_ticker_info(self, symbol: str) -> Optional[TickerRecord]:
        """Get full info for a ticker."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT symbol, name, exchange, asset_type, is_active, last_updated "
                "FROM tickers WHERE symbol = ?",
                (symbol.upper(),)
            ).fetchone()
            if row:
                return TickerRecord(
                    symbol=row[0],
                    name=row[1] or "",
                    exchange=row[2] or "",
                    asset_type=row[3] or "",
                    is_active=bool(row[4]),
                    last_updated=datetime.fromisoformat(row[5]) if row[5] else datetime.now()
                )
            return None

    def get_ticker_count(self) -> int:
        """Get total number of tickers in database."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("SELECT COUNT(*) FROM tickers").fetchone()
            return result[0] if result else 0

    def needs_refresh(self, max_age_hours: int = 24) -> bool:
        """Check if database needs refreshing."""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT value FROM metadata WHERE key = 'last_refresh'"
            ).fetchone()
            if not result:
                return True
            try:
                last_refresh = datetime.fromisoformat(result[0])
                return datetime.now() - last_refresh > timedelta(hours=max_age_hours)
            except (ValueError, TypeError):
                return True

    def refresh(self) -> int:
        """
        Refresh ticker database from authoritative sources.
        Returns the number of tickers loaded.
        """
        logger.info("Refreshing ticker database...")

        tickers: list[TickerRecord] = []

        # Source 1: GitHub US Stock Symbols (most reliable)
        github_tickers = self._fetch_github_symbols()
        tickers.extend(github_tickers)
        logger.info(f"Fetched {len(github_tickers)} tickers from GitHub")

        # Source 2: Add common ETFs, indices, crypto, commodities, forex
        additional = self._get_additional_symbols()
        tickers.extend(additional)
        logger.info(f"Added {len(additional)} additional symbols")

        # Bulk insert
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM tickers")
            conn.executemany(
                "INSERT OR REPLACE INTO tickers VALUES (?, ?, ?, ?, ?, ?)",
                [(t.symbol, t.name, t.exchange, t.asset_type,
                  int(t.is_active), t.last_updated.isoformat()) for t in tickers]
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata VALUES ('last_refresh', ?)",
                (datetime.now().isoformat(),)
            )

        logger.info(f"Loaded {len(tickers)} tickers into database")
        return len(tickers)

    def _fetch_github_symbols(self) -> list[TickerRecord]:
        """Fetch symbols from GitHub US-Stock-Symbols repo."""
        try:
            with urllib.request.urlopen(self.GITHUB_SYMBOLS, timeout=30) as resp:
                content = resp.read().decode('utf-8')
                now = datetime.now()
                return [
                    TickerRecord(
                        symbol=line.strip().upper(),
                        name="",  # GitHub list doesn't include names
                        exchange="US",
                        asset_type="Stock",
                        is_active=True,
                        last_updated=now
                    )
                    for line in content.splitlines()
                    if line.strip() and not line.startswith('#')
                ]
        except Exception as e:
            logger.warning(f"Failed to fetch from GitHub: {e}")
            return []

    def _get_additional_symbols(self) -> list[TickerRecord]:
        """Add ETFs, indices, crypto, commodities, forex that may not be in stock lists."""
        now = datetime.now()
        additional = [
            # ========== MAJOR ETFs ==========
            ("SPY", "SPDR S&P 500 ETF", "NYSE", "ETF"),
            ("QQQ", "Invesco QQQ Trust", "NASDAQ", "ETF"),
            ("IWM", "iShares Russell 2000 ETF", "NYSE", "ETF"),
            ("DIA", "SPDR Dow Jones Industrial Average ETF", "NYSE", "ETF"),
            ("VTI", "Vanguard Total Stock Market ETF", "NYSE", "ETF"),
            ("VOO", "Vanguard S&P 500 ETF", "NYSE", "ETF"),
            # Volatility ETFs
            ("VXX", "iPath Series B S&P 500 VIX", "NYSE", "ETF"),
            ("UVXY", "ProShares Ultra VIX", "NYSE", "ETF"),
            ("SVXY", "ProShares Short VIX", "NYSE", "ETF"),
            # Leveraged ETFs
            ("SQQQ", "ProShares UltraPro Short QQQ", "NASDAQ", "ETF"),
            ("TQQQ", "ProShares UltraPro QQQ", "NASDAQ", "ETF"),
            ("SPXU", "ProShares UltraPro Short S&P 500", "NYSE", "ETF"),
            ("SPXL", "Direxion Daily S&P 500 Bull 3X", "NYSE", "ETF"),
            ("SOXL", "Direxion Daily Semiconductor Bull 3X", "NYSE", "ETF"),
            ("SOXS", "Direxion Daily Semiconductor Bear 3X", "NYSE", "ETF"),

            # ========== COMMODITIES ETFs ==========
            # Precious Metals
            ("GLD", "SPDR Gold Shares", "NYSE", "Commodity"),
            ("IAU", "iShares Gold Trust", "NYSE", "Commodity"),
            ("SLV", "iShares Silver Trust", "NYSE", "Commodity"),
            ("PSLV", "Sprott Physical Silver Trust", "NYSE", "Commodity"),
            ("PHYS", "Sprott Physical Gold Trust", "NYSE", "Commodity"),
            ("PPLT", "abrdn Physical Platinum Shares ETF", "NYSE", "Commodity"),
            ("PALL", "abrdn Physical Palladium Shares ETF", "NYSE", "Commodity"),
            ("GDX", "VanEck Gold Miners ETF", "NYSE", "Commodity"),
            ("GDXJ", "VanEck Junior Gold Miners ETF", "NYSE", "Commodity"),
            ("SIL", "Global X Silver Miners ETF", "NYSE", "Commodity"),
            # Oil & Gas
            ("USO", "United States Oil Fund", "NYSE", "Commodity"),
            ("UCO", "ProShares Ultra Bloomberg Crude Oil", "NYSE", "Commodity"),
            ("SCO", "ProShares UltraShort Bloomberg Crude Oil", "NYSE", "Commodity"),
            ("BNO", "United States Brent Oil Fund", "NYSE", "Commodity"),
            ("UNG", "United States Natural Gas Fund", "NYSE", "Commodity"),
            ("BOIL", "ProShares Ultra Bloomberg Natural Gas", "NYSE", "Commodity"),
            ("KOLD", "ProShares UltraShort Bloomberg Natural Gas", "NYSE", "Commodity"),
            ("XLE", "Energy Select Sector SPDR Fund", "NYSE", "Commodity"),
            ("OIH", "VanEck Oil Services ETF", "NYSE", "Commodity"),
            # Agriculture
            ("DBA", "Invesco DB Agriculture Fund", "NYSE", "Commodity"),
            ("CORN", "Teucrium Corn Fund", "NYSE", "Commodity"),
            ("WEAT", "Teucrium Wheat Fund", "NYSE", "Commodity"),
            ("SOYB", "Teucrium Soybean Fund", "NYSE", "Commodity"),
            ("COW", "iPath Series B Bloomberg Livestock ETN", "NYSE", "Commodity"),
            ("JO", "iPath Series B Bloomberg Coffee ETN", "NYSE", "Commodity"),
            ("NIB", "iPath Series B Bloomberg Cocoa ETN", "NYSE", "Commodity"),
            ("SGG", "iPath Series B Bloomberg Sugar ETN", "NYSE", "Commodity"),
            # Industrial Metals
            ("CPER", "United States Copper Index Fund", "NYSE", "Commodity"),
            ("DBB", "Invesco DB Base Metals Fund", "NYSE", "Commodity"),
            ("URA", "Global X Uranium ETF", "NYSE", "Commodity"),
            ("URNM", "Sprott Uranium Miners ETF", "NYSE", "Commodity"),
            ("LIT", "Global X Lithium & Battery Tech ETF", "NYSE", "Commodity"),

            # ========== COMMODITY FUTURES SYMBOLS ==========
            ("CL", "Crude Oil Futures", "NYMEX", "Commodity"),
            ("GC", "Gold Futures", "COMEX", "Commodity"),
            ("SI", "Silver Futures", "COMEX", "Commodity"),
            ("NG", "Natural Gas Futures", "NYMEX", "Commodity"),
            ("HG", "Copper Futures", "COMEX", "Commodity"),
            ("PL", "Platinum Futures", "NYMEX", "Commodity"),
            ("PA", "Palladium Futures", "NYMEX", "Commodity"),
            ("ZC", "Corn Futures", "CBOT", "Commodity"),
            ("ZW", "Wheat Futures", "CBOT", "Commodity"),
            ("ZS", "Soybean Futures", "CBOT", "Commodity"),
            ("KC", "Coffee Futures", "ICE", "Commodity"),
            ("CC", "Cocoa Futures", "ICE", "Commodity"),
            ("SB", "Sugar Futures", "ICE", "Commodity"),
            ("CT", "Cotton Futures", "ICE", "Commodity"),
            ("LE", "Live Cattle Futures", "CME", "Commodity"),
            ("HE", "Lean Hogs Futures", "CME", "Commodity"),

            # ========== FOREX / CURRENCIES ==========
            # Major Currency ETFs
            ("UUP", "Invesco DB US Dollar Index Bullish Fund", "NYSE", "Forex"),
            ("UDN", "Invesco DB US Dollar Index Bearish Fund", "NYSE", "Forex"),
            ("FXE", "Invesco CurrencyShares Euro Trust", "NYSE", "Forex"),
            ("FXY", "Invesco CurrencyShares Japanese Yen Trust", "NYSE", "Forex"),
            ("FXB", "Invesco CurrencyShares British Pound Trust", "NYSE", "Forex"),
            ("FXA", "Invesco CurrencyShares Australian Dollar Trust", "NYSE", "Forex"),
            ("FXC", "Invesco CurrencyShares Canadian Dollar Trust", "NYSE", "Forex"),
            ("FXF", "Invesco CurrencyShares Swiss Franc Trust", "NYSE", "Forex"),
            # Currency Pairs (commonly mentioned)
            ("EURUSD", "Euro / US Dollar", "FOREX", "Forex"),
            ("GBPUSD", "British Pound / US Dollar", "FOREX", "Forex"),
            ("USDJPY", "US Dollar / Japanese Yen", "FOREX", "Forex"),
            ("USDCAD", "US Dollar / Canadian Dollar", "FOREX", "Forex"),
            ("AUDUSD", "Australian Dollar / US Dollar", "FOREX", "Forex"),
            ("USDCHF", "US Dollar / Swiss Franc", "FOREX", "Forex"),
            ("NZDUSD", "New Zealand Dollar / US Dollar", "FOREX", "Forex"),
            ("EURGBP", "Euro / British Pound", "FOREX", "Forex"),
            ("EURJPY", "Euro / Japanese Yen", "FOREX", "Forex"),
            ("GBPJPY", "British Pound / Japanese Yen", "FOREX", "Forex"),
            # Dollar Index
            ("DXY", "US Dollar Index", "ICE", "Forex"),
            ("DX", "US Dollar Index Futures", "ICE", "Forex"),
            # Currency Futures
            ("6E", "Euro FX Futures", "CME", "Forex"),
            ("6J", "Japanese Yen Futures", "CME", "Forex"),
            ("6B", "British Pound Futures", "CME", "Forex"),
            ("6A", "Australian Dollar Futures", "CME", "Forex"),
            ("6C", "Canadian Dollar Futures", "CME", "Forex"),
            ("6S", "Swiss Franc Futures", "CME", "Forex"),

            # ========== INDICES ==========
            ("SPX", "S&P 500 Index", "INDEX", "Index"),
            ("VIX", "CBOE Volatility Index", "INDEX", "Index"),
            ("DJI", "Dow Jones Industrial Average", "INDEX", "Index"),
            ("DJIA", "Dow Jones Industrial Average", "INDEX", "Index"),
            ("NDX", "NASDAQ-100 Index", "INDEX", "Index"),
            ("RUT", "Russell 2000 Index", "INDEX", "Index"),
            ("SOX", "PHLX Semiconductor Index", "INDEX", "Index"),
            ("TNX", "10-Year Treasury Yield", "INDEX", "Index"),
            ("TYX", "30-Year Treasury Yield", "INDEX", "Index"),
            ("IRX", "13-Week Treasury Bill", "INDEX", "Index"),
            # Index Futures
            ("ES", "E-mini S&P 500 Futures", "CME", "Index"),
            ("NQ", "E-mini NASDAQ-100 Futures", "CME", "Index"),
            ("YM", "E-mini Dow Futures", "CBOT", "Index"),
            ("RTY", "E-mini Russell 2000 Futures", "CME", "Index"),
            ("MES", "Micro E-mini S&P 500 Futures", "CME", "Index"),
            ("MNQ", "Micro E-mini NASDAQ-100 Futures", "CME", "Index"),

            # ========== BONDS / TREASURIES ==========
            ("TLT", "iShares 20+ Year Treasury Bond ETF", "NASDAQ", "Bond"),
            ("TLH", "iShares 10-20 Year Treasury Bond ETF", "NYSE", "Bond"),
            ("IEF", "iShares 7-10 Year Treasury Bond ETF", "NASDAQ", "Bond"),
            ("SHY", "iShares 1-3 Year Treasury Bond ETF", "NASDAQ", "Bond"),
            ("BND", "Vanguard Total Bond Market ETF", "NASDAQ", "Bond"),
            ("AGG", "iShares Core US Aggregate Bond ETF", "NYSE", "Bond"),
            ("HYG", "iShares iBoxx High Yield Corporate Bond ETF", "NYSE", "Bond"),
            ("JNK", "SPDR Bloomberg High Yield Bond ETF", "NYSE", "Bond"),
            ("LQD", "iShares iBoxx Investment Grade Corporate Bond ETF", "NYSE", "Bond"),
            ("TMF", "Direxion Daily 20+ Year Treasury Bull 3X", "NYSE", "Bond"),
            ("TMV", "Direxion Daily 20+ Year Treasury Bear 3X", "NYSE", "Bond"),
            ("TBT", "ProShares UltraShort 20+ Year Treasury", "NYSE", "Bond"),
            # Treasury Futures
            ("ZB", "30-Year Treasury Bond Futures", "CBOT", "Bond"),
            ("ZN", "10-Year Treasury Note Futures", "CBOT", "Bond"),
            ("ZF", "5-Year Treasury Note Futures", "CBOT", "Bond"),
            ("ZT", "2-Year Treasury Note Futures", "CBOT", "Bond"),

            # ========== CRYPTOCURRENCIES ==========
            # Major Crypto
            ("BTC", "Bitcoin", "CRYPTO", "Crypto"),
            ("ETH", "Ethereum", "CRYPTO", "Crypto"),
            ("SOL", "Solana", "CRYPTO", "Crypto"),
            ("XRP", "Ripple", "CRYPTO", "Crypto"),
            ("ADA", "Cardano", "CRYPTO", "Crypto"),
            ("DOGE", "Dogecoin", "CRYPTO", "Crypto"),
            ("SHIB", "Shiba Inu", "CRYPTO", "Crypto"),
            ("AVAX", "Avalanche", "CRYPTO", "Crypto"),
            ("DOT", "Polkadot", "CRYPTO", "Crypto"),
            ("MATIC", "Polygon", "CRYPTO", "Crypto"),
            ("LINK", "Chainlink", "CRYPTO", "Crypto"),
            ("LTC", "Litecoin", "CRYPTO", "Crypto"),
            ("UNI", "Uniswap", "CRYPTO", "Crypto"),
            ("ATOM", "Cosmos", "CRYPTO", "Crypto"),
            ("XLM", "Stellar", "CRYPTO", "Crypto"),
            ("ALGO", "Algorand", "CRYPTO", "Crypto"),
            ("FTM", "Fantom", "CRYPTO", "Crypto"),
            ("NEAR", "Near Protocol", "CRYPTO", "Crypto"),
            ("APE", "ApeCoin", "CRYPTO", "Crypto"),
            ("SAND", "The Sandbox", "CRYPTO", "Crypto"),
            ("MANA", "Decentraland", "CRYPTO", "Crypto"),
            ("CRO", "Cronos", "CRYPTO", "Crypto"),
            # Bitcoin/Crypto ETFs
            ("BITO", "ProShares Bitcoin Strategy ETF", "NYSE", "Crypto"),
            ("GBTC", "Grayscale Bitcoin Trust", "OTC", "Crypto"),
            ("ETHE", "Grayscale Ethereum Trust", "OTC", "Crypto"),
            ("IBIT", "iShares Bitcoin Trust ETF", "NASDAQ", "Crypto"),
            ("FBTC", "Fidelity Wise Origin Bitcoin Fund", "NYSE", "Crypto"),
            ("ARKB", "ARK 21Shares Bitcoin ETF", "NYSE", "Crypto"),
            # Crypto Futures
            ("BTCUSD", "Bitcoin / US Dollar", "CRYPTO", "Crypto"),
            ("ETHUSD", "Ethereum / US Dollar", "CRYPTO", "Crypto"),
        ]
        return [
            TickerRecord(
                symbol=s,
                name=n,
                exchange=e,
                asset_type=t,
                is_active=True,
                last_updated=now
            )
            for s, n, e, t in additional
        ]


# Module-level singleton
_db: Optional[TickerDatabase] = None


def get_ticker_database() -> TickerDatabase:
    """Get or create the ticker database singleton."""
    global _db
    if _db is None:
        _db = TickerDatabase()
        if _db.needs_refresh():
            _db.refresh()
    return _db


def is_valid_ticker(symbol: str) -> bool:
    """Quick check if a symbol is a valid ticker."""
    return get_ticker_database().is_valid_ticker(symbol)
