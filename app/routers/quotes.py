"""Delayed stock/ETF quotes for Portfolio's current-value/unrealized-G/L
columns (FRONTEND_SPEC.md §5, previously an explicit open gap — no live
price source was wired up).

Source: Yahoo Finance's undocumented chart endpoint. No API key, no signup
— picked over Stooq/Finnhub specifically because this network's egress
filtering blocks Stooq outright and Finnhub's free tier needs a key. It's
unofficial and could change shape or start blocking without notice; if it
does, every quote degrades to `price: null, error: ...` rather than
breaking the page (holdings render with cost-basis math same as before,
per the spec's "don't fake prices" rule).
"""

import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import requests
from fastapi import APIRouter, Query

from app.schemas import QuoteOut

router = APIRouter(prefix="/quotes", tags=["quotes"])

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
REQUEST_TIMEOUT_SECONDS = 5
CACHE_TTL_SECONDS = 60

# Simple in-process cache so navigating between pages within the TTL window
# doesn't re-hit Yahoo per symbol per page load. Fine for a single-user app;
# not shared across worker processes.
_cache: dict[str, tuple[float, QuoteOut]] = {}


def _fetch_one(symbol: str) -> QuoteOut:
    cached = _cache.get(symbol)
    if cached is not None and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    quote = _fetch_from_yahoo(symbol)
    _cache[symbol] = (time.monotonic(), quote)
    return quote


def _fetch_from_yahoo(symbol: str) -> QuoteOut:
    try:
        resp = requests.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        data = resp.json()
    except (requests.RequestException, ValueError):
        return QuoteOut(symbol=symbol, price=None, as_of=None, error="Price lookup failed — try again shortly")

    chart = data.get("chart", {})
    result = chart.get("result")
    if not result:
        message = (chart.get("error") or {}).get("description") or "No data found for this symbol"
        return QuoteOut(symbol=symbol, price=None, as_of=None, error=message)

    price = result[0].get("meta", {}).get("regularMarketPrice")
    if price is None:
        return QuoteOut(symbol=symbol, price=None, as_of=None, error="No price available for this symbol")

    try:
        price_decimal = Decimal(str(price))
    except InvalidOperation:
        return QuoteOut(symbol=symbol, price=None, as_of=None, error="Unexpected price format")

    return QuoteOut(symbol=symbol, price=price_decimal, as_of=datetime.now(timezone.utc), error=None)


@router.get("", response_model=list[QuoteOut])
def get_quotes(symbols: str = Query(..., description="Comma-separated ticker symbols, e.g. AAPL,MSFT")):
    unique_symbols = list(dict.fromkeys(s.strip().upper() for s in symbols.split(",") if s.strip()))
    return [_fetch_one(s) for s in unique_symbols]
