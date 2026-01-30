"""
OpenFIGI API integration for ticker validation.

OpenFIGI is a free API (no rate limits) that provides global instrument coverage.
Used as a fallback for tickers not found in the local database.
"""
import urllib.request
import json
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"


@dataclass
class FIGIResult:
    """Result from OpenFIGI API lookup."""
    ticker: str
    name: str
    exchange: str
    security_type: str
    figi: str


# Cache for API results (persists for session)
_figi_cache: dict[str, Optional[FIGIResult]] = {}
_invalid_cache: set[str] = set()


def validate_ticker_openfigi(ticker: str) -> Optional[FIGIResult]:
    """
    Validate a ticker against OpenFIGI.

    Returns FIGIResult if valid, None if not found.
    Results are cached for the session.
    """
    ticker = ticker.upper()

    # Check caches first
    if ticker in _invalid_cache:
        return None
    if ticker in _figi_cache:
        return _figi_cache[ticker]

    try:
        # Prepare request
        data = json.dumps([{"idType": "TICKER", "idValue": ticker}]).encode()
        req = urllib.request.Request(
            OPENFIGI_URL,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())

        # Parse response
        if result and result[0].get("data"):
            item = result[0]["data"][0]
            figi_result = FIGIResult(
                ticker=ticker,
                name=item.get("name", ""),
                exchange=item.get("exchCode", ""),
                security_type=item.get("securityType", ""),
                figi=item.get("figi", "")
            )
            _figi_cache[ticker] = figi_result
            return figi_result
        else:
            _invalid_cache.add(ticker)
            return None

    except Exception as e:
        logger.debug(f"OpenFIGI lookup failed for {ticker}: {e}")
        return None


def batch_validate_openfigi(tickers: list[str]) -> dict[str, Optional[FIGIResult]]:
    """
    Validate multiple tickers in one API call.

    OpenFIGI supports up to 100 tickers per request.
    Results are cached for future lookups.
    """
    results: dict[str, Optional[FIGIResult]] = {}
    uncached = []

    # Return cached results and collect uncached tickers
    for t in tickers:
        t_upper = t.upper()
        if t_upper in _figi_cache:
            results[t_upper] = _figi_cache[t_upper]
        elif t_upper in _invalid_cache:
            results[t_upper] = None
        else:
            uncached.append(t_upper)

    if not uncached:
        return results

    # Batch query (max 100 per request)
    for i in range(0, len(uncached), 100):
        batch = uncached[i:i + 100]
        try:
            data = json.dumps([
                {"idType": "TICKER", "idValue": t} for t in batch
            ]).encode()
            req = urllib.request.Request(
                OPENFIGI_URL,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                api_results = json.loads(resp.read().decode())

            for ticker, result in zip(batch, api_results):
                if result.get("data"):
                    item = result["data"][0]
                    figi_result = FIGIResult(
                        ticker=ticker,
                        name=item.get("name", ""),
                        exchange=item.get("exchCode", ""),
                        security_type=item.get("securityType", ""),
                        figi=item.get("figi", "")
                    )
                    _figi_cache[ticker] = figi_result
                    results[ticker] = figi_result
                else:
                    _invalid_cache.add(ticker)
                    results[ticker] = None

        except Exception as e:
            logger.warning(f"Batch OpenFIGI lookup failed: {e}")
            # Mark all as None on error
            for t in batch:
                results[t] = None

    return results


def clear_cache():
    """Clear the validation caches."""
    global _figi_cache, _invalid_cache
    _figi_cache = {}
    _invalid_cache = set()
