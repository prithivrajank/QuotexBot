import os
import time

import pytest

import market_bridge


def test_bridge_requires_server_token(monkeypatch):
    monkeypatch.delenv("MARKET_BRIDGE_TOKEN", raising=False)
    with pytest.raises(market_bridge.BridgeError, match="not configured"):
        market_bridge.ingest({"symbol": "EURUSD_otc", "candles": []}, "x")


def test_bridge_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("MARKET_BRIDGE_TOKEN", "expected")
    with pytest.raises(PermissionError):
        market_bridge.ingest({"symbol": "EURUSD_otc", "candles": []}, "wrong")


def test_bridge_accepts_valid_aligned_candle(monkeypatch):
    monkeypatch.setenv("MARKET_BRIDGE_TOKEN", "expected")
    timestamp = int(time.time()) // 60 * 60
    result = market_bridge.ingest({
        "symbol": "EURUSD_otc",
        "timeframe_seconds": 60,
        "candles": [{
            "time": timestamp, "open": 1.1, "high": 1.3,
            "low": 1.0, "close": 1.2,
        }],
    }, "expected")
    assert result["accepted"] == 1
    rows = market_bridge.get_candles("EURUSD_otc", 60, 10)
    assert rows[-1]["close"] == 1.2
    assert rows[-1]["market_type"] == "Quotex Demo (browser-observed)"


def test_bridge_rejects_inconsistent_ohlc(monkeypatch):
    monkeypatch.setenv("MARKET_BRIDGE_TOKEN", "expected")
    timestamp = int(time.time()) // 60 * 60
    with pytest.raises(market_bridge.BridgeError, match="inconsistent"):
        market_bridge.ingest({
            "symbol": "EURUSD_otc",
            "timeframe_seconds": 60,
            "candles": [{
                "time": timestamp, "open": 1.2, "high": 1.1,
                "low": 1.0, "close": 1.15,
            }],
        }, "expected")


def test_bridge_rejects_unsupported_timeframe(monkeypatch):
    monkeypatch.setenv("MARKET_BRIDGE_TOKEN", "expected")
    with pytest.raises(market_bridge.BridgeError, match="Only 60-second"):
        market_bridge.ingest({"symbol": "EURUSD_otc", "timeframe_seconds": 30, "candles": []}, "expected")
