"""Extract and validate stock ticker symbols from text.

This module identifies potential stock tickers in Reddit posts using:
1. High confidence: $TICKER format (cashtag)
2. Contextual patterns: "buying X", "calls on X", etc.
3. Standalone: ALL CAPS words validated against authoritative database

Validation is performed against:
- Local SQLite database of ~10,000 valid US tickers
- OpenFIGI API for unknown high-confidence matches
"""

import re
import logging
from dataclasses import dataclass
from typing import Optional

from wsb_tracker.ticker_database import get_ticker_database, is_valid_ticker as db_is_valid
from wsb_tracker.openfigi import validate_ticker_openfigi

logger = logging.getLogger(__name__)


@dataclass
class TickerMatch:
    """A matched ticker symbol with metadata.

    Attributes:
        ticker: The extracted ticker symbol (uppercase)
        start: Start index in original text
        end: End index in original text
        context: Surrounding text (~100 chars each side)
        confidence: Extraction confidence (0.0 to 1.0)
        has_dollar_sign: Whether it was a $TICKER format
    """
    ticker: str
    start: int
    end: int
    context: str
    confidence: float
    has_dollar_sign: bool


class TickerExtractor:
    """Extract stock ticker symbols from text with database validation.

    The extractor uses multiple strategies:
    1. $TICKER format: Highest confidence (0.95)
    2. Contextual patterns: Medium confidence (0.8)
    3. Standalone ALL CAPS: Lower confidence (0.6)

    All extracted tickers are validated against:
    - Local database of ~10,000 valid US tickers (stocks, ETFs, commodities, forex, crypto)
    - OpenFIGI API for high-confidence matches not in local database

    Usage:
        extractor = TickerExtractor()
        matches = extractor.extract("$GME to the moon! Buying more AAPL tomorrow.")
        for match in matches:
            print(f"{match.ticker}: {match.confidence}")
    """

    # Common words that look like tickers but aren't
    EXCLUSIONS: frozenset[str] = frozenset({
        # WSB Slang
        "YOLO", "FOMO", "HODL", "BTFD", "GTFO", "LMAO", "ROFL", "TLDR",
        "IMHO", "IMO", "FYI", "AFAIK", "TBH", "ICYMI", "IIRC", "GOAT",
        "MOASS", "FUD", "FWIW", "LMFAO", "STFU", "WTF", "OMG", "SMH",
        "TFW", "MFW", "ITT", "IIUC", "IANAL", "YMMV",

        # Reddit/Internet terms
        "OP", "TL", "DR", "EDIT", "UPDATE", "PSA", "AMA", "ELI",
        "TIL", "DAE", "CMV", "AITA", "TIFU", "IRL", "NSFW", "SFW",
        "OC", "META", "MOD", "MODS", "FAQ", "RIP", "GIF", "JPEG",
        "PNG", "PDF", "HTML", "CSS", "API", "URL", "HTTP", "HTTPS",

        # Financial/trading terms that aren't tickers
        "CEO", "CFO", "CTO", "COO", "IPO", "SEC", "FDA", "FED",
        "GDP", "ETF", "ITM", "OTM", "ATM", "EPS", "PE", "PB",
        "RSI", "MACD", "SMA", "EMA", "VWAP", "ATH", "ATL",
        "DD", "TA", "FA", "PT", "SI", "IV", "DTE", "OI",
        "EOD", "EOW", "AH", "PM", "RTH", "SPAC", "IPO",
        "LEAPS", "FD", "FDS", "LEAP", "PUTS", "CALLS",
        "LONG", "SHORT", "BULL", "BEAR", "BUY", "SELL",
        "HOLD", "DIP", "RUN", "MOON", "TANK", "PUMP", "DUMP",
        "GAIN", "LOSS", "ROI", "YOY", "QOQ", "MOM", "WOW",
        "CAGR", "NAV", "AUM", "FCF", "EBITDA", "GAAP",

        # Country/Currency codes
        "USA", "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF",
        "CNY", "HKD", "SGD", "NZD", "KRW", "INR", "BRL", "MXN",
        "UK", "EU", "US", "CN", "JP", "DE", "FR", "IT", "ES",

        # Time references
        "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG",
        "SEP", "OCT", "NOV", "DEC", "MON", "TUE", "WED", "THU",
        "FRI", "SAT", "SUN", "AM", "PM", "EST", "PST", "CST",
        "UTC", "GMT", "EDT", "PDT", "CDT", "MDT", "MST",

        # Very common short words (2-3 letters) - always exclude
        # These may match obscure international tickers but are almost always false positives
        "MY", "IN", "OF", "AT", "TO", "BY", "IF", "OR", "AS", "IS", "IT",
        "NO", "BE", "WE", "AN", "SO", "UP", "ON", "DO", "GO", "HE", "ME",
        "US", "AM", "AX", "OX", "EX",
        # 2-letter words that are valid tickers but cause too many false positives
        # These will only be recognized with $ prefix (e.g., $AI, $CC)
        "AI", "CC", "FL", "IP", "HR", "PR", "ED", "CL", "WY", "TV", "OS",
        "PC", "IT", "UK", "EU", "OK", "AC", "DC", "DJ", "CD", "HD", "PS",

        # Common words that could be mistaken for tickers
        "ARE", "THE", "FOR", "AND", "NOT", "ALL", "CAN", "HAS",
        "HIS", "HER", "NEW", "NOW", "OLD", "OUR", "OUT", "OWN",
        "SAY", "SHE", "TOO", "TWO", "WAY", "WHO", "BOY", "DID",
        "GET", "GOT", "HAD", "HIM", "HOW", "ITS", "LET", "MAN",
        "PUT", "RUN", "SEE", "SET", "TOP", "TRY", "USE", "WAS",
        "WIN", "WON", "YET", "BIG", "FAT", "LOW", "MAX", "MIN",
        "ONE", "TEN", "SIX", "RED", "HOT", "ICE", "CAR", "DOG",
        "CAT", "BAD", "GAS", "OIL", "TAX", "LAW", "WAR", "PAY",
        "JOB", "AGE", "EYE", "DAY", "END", "BOX", "CUT", "DUE",
        "FEW", "GAP", "GUN", "HIT", "KEY", "LAY", "MIX", "NET",
        "ODD", "PER", "RAW", "ROW", "SKY", "SUM", "TEA", "TIP",
        "VIA", "WEB", "YES", "ZIP", "ACE", "ADD", "AID", "AIM",
        "AIR", "ARM", "ART", "ASK", "BAR", "BAT", "BED", "BET",
        "BIT", "BUS", "CAP", "COP", "CRY", "CUP", "DIG", "DOT",
        "DRY", "EAR", "EAT", "EGG", "ERA", "FAN", "FAR", "FAT",
        "FIT", "FIX", "FLY", "FOX", "FUN", "GAL", "GAY", "HAT",
        "HIT", "HOP", "HUG", "ICY", "ILL", "INK", "JAM", "JAW",
        "JET", "JOY", "KEG", "KID", "KIT", "LAB", "LAP", "LEG",
        "LID", "LIP", "LOG", "LOT", "MAD", "MAP", "MAT", "MIX",
        "MOB", "MUD", "MUG", "NAP", "NIT", "NUN", "NUT", "OAK",
        "OAT", "ODD", "ORB", "OWL", "PAD", "PAN", "PAT", "PAW",
        "PEA", "PEN", "PET", "PIE", "PIG", "PIN", "PIT", "POD",
        "POP", "POT", "PUB", "PUN", "RAG", "RAM", "RAP", "RAT",
        "RAY", "REP", "RIB", "RIG", "RIM", "ROB", "ROD", "ROT",
        "RUB", "RUG", "SAD", "SAP", "SAT", "SAW", "SAX", "SEA",
        "SIP", "SIT", "SKI", "SOB", "SOD", "SON", "SOP", "SOT",
        "SOW", "SOY", "SPA", "SPY", "STY", "SUB", "SUM", "SUN",
        "TAB", "TAG", "TAN", "TAP", "TAR", "TAT", "TEE", "TEN",
        "TIE", "TIN", "TOE", "TON", "TOO", "TOW", "TOY", "TUB",
        "TUG", "URN", "VAN", "VAT", "VET", "VOW", "WAD", "WAG",
        "WAN", "WED", "WET", "WIG", "WIT", "WOE", "WOK", "WON",
        "WOO", "YAK", "YAM", "YAP", "YAW", "YEA", "YEN", "YES",
        "YEW", "YIN", "ZIP", "ZIT", "ZOO",

        # Longer common words that may match obscure tickers
        "THESE", "THOSE", "ABOUT", "AFTER", "FIRST", "BEING",
        "OTHER", "WHICH", "THEIR", "THERE", "WHERE", "WOULD",
        "COULD", "SHOULD", "EVERY", "STILL", "WHILE", "THINK",
        "THING", "DOING", "GOING", "NEVER", "SINCE", "UNTIL",

        # Other common false positives
        "LIKE", "JUST", "WILL", "LOOK", "MAKE", "KNOW", "TIME",
        "YEAR", "GOOD", "SOME", "THEM", "THAN", "BEEN", "CALL",
        "ONLY", "COME", "MADE", "FIND", "LONG", "DOWN", "EVEN",
        "BACK", "MOST", "OVER", "SUCH", "INTO", "LAST", "LIFE",
        "WORK", "PART", "TAKE", "GIVE", "MORE", "WANT", "WELL",
        "ALSO", "PLAY", "VERY", "KEEP", "WENT", "SAME", "TOLD",
        "MUST", "NEED", "FEEL", "HIGH", "LEFT", "EACH", "BOTH",
        "NEXT", "USED", "WORD", "DAYS", "WEEK", "LMAO", "YEAH",
        "SURE", "DAMN", "SHIT", "FUCK", "NICE", "COOL", "DUDE",
        "GUYS", "GIRL", "OKAY", "SEEN", "LOVE", "HATE", "HOPE",
        "HELP", "HARD", "EASY", "FAST", "SLOW", "HUGE", "TINY",
        "RICH", "POOR", "FREE", "PAID", "SAFE", "RISK", "REAL",
        "FAKE", "TRUE", "BEST", "MOVE", "NEWS", "POST", "LINK",
        "HERE", "THEN", "WHEN", "WHAT", "WERE", "HAVE", "THAT",
        "WITH", "THIS", "FROM", "YOUR", "THEY", "BEEN", "WERE",
    })

    # Known valid tickers that might be filtered (override exclusions)
    KNOWN_TICKERS: frozenset[str] = frozenset({
        # Single-letter tickers (require $ prefix)
        "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
        "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",

        # Popular meme stocks
        "GME", "AMC", "BB", "BBBY", "NOK", "PLTR", "WISH", "CLOV", "SOFI",
        "HOOD", "RBLX", "RIVN", "LCID", "NIO", "XPEV", "LI",

        # Major tech
        "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA",
        "AMD", "INTC", "NFLX", "PYPL", "SQ", "SHOP", "UBER", "LYFT",
        "SNAP", "PINS", "TWTR", "SPOT", "ZOOM", "ZM", "DOCU", "CRM",
        "ORCL", "IBM", "HPQ", "DELL", "CSCO", "QCOM", "AVGO", "TXN",
        "MU", "WDC", "STX", "AMAT", "LRCX", "KLAC", "ASML", "TSM",

        # Finance
        "JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC",
        "BK", "STT", "SCHW", "BLK", "SPGI", "ICE", "CME", "MCO",
        "V", "MA", "AXP", "COF", "DFS", "SYF",

        # ETFs
        "SPY", "QQQ", "IWM", "DIA", "VTI", "VOO", "ARKK", "ARKG",
        "XLF", "XLE", "XLK", "XLV", "XLI", "XLY", "XLP", "XLU",
        "GLD", "SLV", "USO", "UNG", "TLT", "HYG", "LQD", "JNK",
        "VXX", "UVXY", "SVXY", "SQQQ", "TQQQ", "SPXU", "UPRO",

        # Healthcare/Pharma
        "JNJ", "PFE", "MRK", "ABBV", "BMY", "LLY", "AMGN", "GILD",
        "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "UNH", "CVS", "CI",

        # Consumer
        "WMT", "TGT", "COST", "HD", "LOW", "DG", "DLTR", "KR",
        "MCD", "SBUX", "YUM", "CMG", "DPZ", "DNUT", "WEN", "QSR",
        "NKE", "LULU", "GPS", "TJX", "ROST", "BBY", "ULTA", "EL",

        # Industrial
        "BA", "CAT", "DE", "MMM", "HON", "GE", "RTX", "LMT", "NOC",
        "UPS", "FDX", "UAL", "DAL", "AAL", "LUV", "JBLU",

        # Energy
        "XOM", "CVX", "COP", "EOG", "PXD", "OXY", "SLB", "HAL",
        "MPC", "VLO", "PSX", "HES", "DVN", "APA", "FANG",

        # Telecom/Media
        "DIS", "CMCSA", "NFLX", "WBD", "PARA", "FOX", "FOXA",
        "VZ", "TMUS", "CHTR", "LUMN",

        # Valid 2-letter US tickers - only with $ prefix due to false positive risk
        # These are NOT in KNOWN_TICKERS because standalone 2-letter matches are too noisy
        # They will only be detected with $AI, $CC etc. format
    })

    # Regex patterns
    DOLLAR_TICKER_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
    STANDALONE_TICKER_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

    # Contextual patterns (buying X, calls on X, etc.)
    CONTEXTUAL_PATTERNS = [
        re.compile(r'\b(?:buying|bought|buy|long|calls?\s+on|puts?\s+on)\s+([A-Z]{1,5})\b', re.I),
        re.compile(r'\b([A-Z]{1,5})\s+(?:calls?|puts?|options?|shares?|stock)\b', re.I),
        re.compile(r'\b(?:sold|selling|sell|short)\s+([A-Z]{1,5})\b', re.I),
    ]

    # Context extraction window (characters)
    CONTEXT_WINDOW = 100

    def __init__(
        self,
        additional_exclusions: Optional[set[str]] = None,
        additional_known: Optional[set[str]] = None,
        use_database: bool = True,
        use_openfigi: bool = True,
    ) -> None:
        """Initialize extractor with optional custom lists.

        Args:
            additional_exclusions: Extra terms to filter out
            additional_known: Extra valid tickers to recognize
            use_database: Whether to validate against local ticker database
            use_openfigi: Whether to use OpenFIGI API for unknown tickers
        """
        self.exclusions = set(self.EXCLUSIONS)
        self.known_tickers = set(self.KNOWN_TICKERS)
        self.use_database = use_database
        self.use_openfigi = use_openfigi

        if additional_exclusions:
            self.exclusions.update(t.upper() for t in additional_exclusions)
        if additional_known:
            self.known_tickers.update(t.upper() for t in additional_known)

        # Initialize database if enabled
        if self.use_database:
            try:
                db = get_ticker_database()
                if db.needs_refresh():
                    logger.info("Ticker database needs refresh, updating...")
                    db.refresh()
            except Exception as e:
                logger.warning(f"Failed to initialize ticker database: {e}")
                self.use_database = False

    def extract(self, text: str) -> list[TickerMatch]:
        """Extract all valid ticker symbols from text.

        Uses multiple strategies with different confidence levels:
        1. $TICKER format: 0.95 confidence
        2. Contextual patterns: 0.8 confidence
        3. Standalone ALL CAPS: 0.6 confidence (requires validation)

        Args:
            text: Input text to extract tickers from

        Returns:
            List of TickerMatch objects, deduplicated by ticker symbol
        """
        matches: dict[str, TickerMatch] = {}

        # Pass 1: $TICKER format (highest confidence)
        for match in self.DOLLAR_TICKER_PATTERN.finditer(text):
            ticker = match.group(1).upper()
            confidence = 0.95
            if self._is_valid_ticker(ticker, has_dollar=True, confidence=confidence):
                if ticker not in matches:
                    matches[ticker] = TickerMatch(
                        ticker=ticker,
                        start=match.start(),
                        end=match.end(),
                        context=self._get_context(text, match.start(), match.end()),
                        confidence=confidence,
                        has_dollar_sign=True,
                    )

        # Pass 2: Contextual patterns (medium confidence)
        for pattern in self.CONTEXTUAL_PATTERNS:
            for match in pattern.finditer(text):
                ticker = match.group(1).upper()
                confidence = 0.8
                if ticker not in matches and self._is_valid_ticker(ticker, has_dollar=False, confidence=confidence):
                    matches[ticker] = TickerMatch(
                        ticker=ticker,
                        start=match.start(),
                        end=match.end(),
                        context=self._get_context(text, match.start(), match.end()),
                        confidence=confidence,
                        has_dollar_sign=False,
                    )

        # Pass 3: Standalone ALL CAPS (lower confidence - database validation only, no API)
        for match in self.STANDALONE_TICKER_PATTERN.finditer(text):
            ticker = match.group(1).upper()
            confidence = 0.6
            # For low-confidence matches, only validate against local database (no API calls)
            if ticker not in matches and self._is_valid_ticker(ticker, has_dollar=False, confidence=confidence):
                matches[ticker] = TickerMatch(
                    ticker=ticker,
                    start=match.start(),
                    end=match.end(),
                    context=self._get_context(text, match.start(), match.end()),
                    confidence=confidence,
                    has_dollar_sign=False,
                )

        return list(matches.values())

    def extract_unique(self, text: str) -> set[str]:
        """Extract unique ticker symbols only.

        Args:
            text: Input text to extract tickers from

        Returns:
            Set of unique ticker symbols
        """
        return {match.ticker for match in self.extract(text)}

    def _is_valid_ticker(self, ticker: str, has_dollar: bool, confidence: float = 0.5) -> bool:
        """Validate a potential ticker symbol against authoritative sources.

        Args:
            ticker: Potential ticker symbol (uppercase)
            has_dollar: Whether it had a $ prefix
            confidence: Extraction confidence (used to decide on API validation)

        Returns:
            True if the ticker is a valid security symbol
        """
        # Must be 1-5 uppercase letters
        if not ticker.isalpha() or not ticker.isupper():
            return False

        if len(ticker) < 1 or len(ticker) > 5:
            return False

        # Single-letter and 2-letter tickers only valid with $ prefix
        # They're too often false positives otherwise (AI, CC, HR, etc.)
        if len(ticker) <= 2 and not has_dollar:
            return False

        # Exclude common false positives, UNLESS it has a $ prefix
        # (e.g., standalone "AI" is excluded, but "$AI" is valid)
        if ticker in self.exclusions and not has_dollar:
            return False

        # Layer 1: Check local database (fast, ~10,000 valid symbols)
        if self.use_database:
            if db_is_valid(ticker):
                return True

        # If database validation is disabled, fall back to known tickers list
        if not self.use_database and ticker in self.known_tickers:
            return True

        # Layer 2: For high-confidence matches, try OpenFIGI API
        if self.use_openfigi and confidence >= 0.8:
            figi_result = validate_ticker_openfigi(ticker)
            if figi_result:
                logger.debug(f"Validated {ticker} via OpenFIGI: {figi_result.name}")
                return True

        # Not found in any authoritative source
        return False

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around a match.

        Args:
            text: Full text
            start: Match start index
            end: Match end index

        Returns:
            Context string with ellipsis if truncated
        """
        ctx_start = max(0, start - self.CONTEXT_WINDOW)
        ctx_end = min(len(text), end + self.CONTEXT_WINDOW)

        context = text[ctx_start:ctx_end].strip()

        # Clean up whitespace
        context = re.sub(r'\s+', ' ', context)

        # Add ellipsis if truncated
        if ctx_start > 0:
            context = "..." + context
        if ctx_end < len(text):
            context = context + "..."

        return context[:500]

    def add_exclusion(self, ticker: str) -> None:
        """Add a term to the exclusion list.

        Args:
            ticker: Term to exclude
        """
        self.exclusions.add(ticker.upper())

    def add_known_ticker(self, ticker: str) -> None:
        """Add a ticker to the known valid list.

        Args:
            ticker: Ticker to add
        """
        self.known_tickers.add(ticker.upper())


# Module-level singleton
_extractor: Optional[TickerExtractor] = None


def get_extractor() -> TickerExtractor:
    """Get or create global extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = TickerExtractor()
    return _extractor


def extract_tickers(text: str) -> list[TickerMatch]:
    """Extract tickers using global extractor.

    Convenience function for simple usage.

    Args:
        text: Input text to extract tickers from

    Returns:
        List of TickerMatch objects
    """
    return get_extractor().extract(text)


def extract_ticker_symbols(text: str) -> set[str]:
    """Extract unique ticker symbols using global extractor.

    Convenience function for simple usage.

    Args:
        text: Input text to extract tickers from

    Returns:
        Set of unique ticker symbols
    """
    return get_extractor().extract_unique(text)
