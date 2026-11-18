"""Authenticated ingestion endpoint backend for a local, read-only browser bridge.

The Render service never logs in to Quotex and never receives browser cookies,
SSID values, raw WebSocket frames, or credentials. A local trusted agent may
submit only validated OHLC candle records using MARKET_BRIDGE_TOKEN.
"""
from __future__ import annotations

import hmac
import math
import os
import threading
import time
from typing import Any

_lock = threading.Lock()
_candles: dict[tuple[str, int], list[dict[str, Any]]] = {}
_last_received: dict[str, int] = {}


class BridgeError(ValueError):
    """Raised when bridge credentials or submitted market data are invalid."""


def _normalize_symbol(value: str) -> str:
    symbol = value.strip()
    if not symbol or len(symbol) > 40 or any(ch.isspace() for ch in symbol):
        raise BridgeError("Invalid symbol.")
    return symbol


def _validate_candle(row: dict[str, Any], symbol: str, timeframe: int) -> dict[str, Any]:
    try:
        timestamp = int(row["time"])
        values = {key: float(row[key]) for key in ("open", "high", "low", "close")}
    except (KeyError, TypeError, ValueError, OverflowError):
        raise BridgeError("Candle requires integer time and numeric OHLC fields.") from None
    if timestamp <= 0 or timestamp > int(time.time()) + 60:
        raise BridgeError("Candle timestamp is invalid or too far in the future.")
    if timestamp < int(time.time()) - 7 * 86400:
        raise BridgeError("Candle is older than the accepted seven-day window.")
    if any(not math.isfinite(value) for value in values.values()):
        raise BridgeError("Candle OHLC values must be finite.")
    o, h, low, close = values["open"], values["high"], values["low"], values["close"]
    if h < max(o, low, close) or low > min(o, h, close):
        raise BridgeError("Candle has inconsistent OHLC values.")
    if timestamp % timeframe != 0:
        raise BridgeError("Candle timestamp is not aligned to its timeframe.")
    return {
        "time": timestamp, **values, "symbol": symbol,
        "timeframe_seconds": timeframe,
        "venue": "quotex_browser_demo",
        "market_type": "Quotex Demo (browser-observed)",
        "source": "local_read_only_browser_bridge",
    }


def ingest(payload: dict[str, Any], supplied_token: str | None) -> dict[str, Any]:
    expected = os.getenv("MARKET_BRIDGE_TOKEN", "").strip()
    if not expected:
        raise BridgeError("MARKET_BRIDGE_TOKEN is not configured on the server.")
    if not supplied_token or not hmac.compare_digest(supplied_token, expected):
        raise PermissionError("Invalid or missing bridge token.")

    symbol = _normalize_symbol(str(payload.get("symbol", "")))
    timeframe = payload.get("timeframe_seconds", 60)
    if isinstance(timeframe, bool) or timeframe not in (60, 300):
        raise BridgeError("Only 60-second and 300-second candles are accepted.")
    rows = payload.get("candles")
    if not isinstance(rows, list) or not rows or len(rows) > 200:
        raise BridgeError("Submit between 1 and 200 validated candles.")
    validated = [_validate_candle(row, symbol, timeframe) for row in rows]
    validated.sort(key=lambda item: item["time"])
    if len({row["time"] for row in validated}) != len(validated):
        raise BridgeError("Duplicate candle timestamps are not accepted.")
    now = int(time.time())
    with _lock:
        key = (symbol, timeframe)
        existing = {row["time"]: row for row in _candles.get(key, [])}
        existing.update({row["time"]: row for row in validated})
        _candles[key] = [existing[k] for k in sorted(existing)][-200:]
        _last_received[symbol] = now
    return {
        "accepted": len(validated),
        "symbol": symbol,
        "timeframe_seconds": timeframe,
        "latest_candle_time": validated[-1]["time"],
        "received_at": now,
        "read_only": True,
    }


def get_candles(symbol: str, timeframe_seconds: int, limit: int = 100) -> list[dict[str, Any]]:
    with _lock:
        rows = list(_candles.get((symbol, timeframe_seconds), []))
    return rows[-max(1, min(int(limit), 200)):]


def status() -> dict[str, Any]:
    with _lock:
        received = dict(_last_received)
        counts = {f"{symbol}:{tf}": len(rows) for (symbol, tf), rows in _candles.items()}
    now = int(time.time())
    fresh = any(now - timestamp <= 30 for timestamp in received.values())
    candle_fresh = any(
        rows and now - int(rows[-1]["time"]) <= 120
        for rows in _candles.values()
    )
    return {
        "connected": fresh,
        "live_data": fresh and candle_fresh and bool(counts),
        "credentials_configured": bool(os.getenv("MARKET_BRIDGE_TOKEN", "").strip()),
        "source": "Local read-only Quotex Demo browser bridge",
        "market_type": "Quotex Demo (browser-observed)",
        "bridge_last_received": received,
        "candle_counts": counts,
        "message": (
            "Authenticated local browser bridge is receiving recent validated candles."
            if fresh else
            "Waiting for a local read-only browser bridge. Render does not connect to Quotex directly."
        ),
        "read_only": True,
    }
