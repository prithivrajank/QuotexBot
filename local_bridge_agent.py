"""Forward already-parsed, completed OHLC candles from local capture to Render.

This agent does not log in, read cookies, extract SSIDs, inspect raw frames, or
place trades. It only forwards JSONL records containing explicit OHLC fields.
"""
from __future__ import annotations

import glob
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

RENDER_BASE_URL = os.getenv("RENDER_BASE_URL", "").strip().rstrip("/")
MARKET_BRIDGE_TOKEN = os.getenv("MARKET_BRIDGE_TOKEN", "").strip()
CANDLE_FILE = os.getenv("BROWSER_CANDLE_FILE", "").strip()
TIMEFRAME_SECONDS = int(os.getenv("BROWSER_TIMEFRAME_SECONDS", "60"))
POLL_SECONDS = max(2, int(os.getenv("BRIDGE_POLL_SECONDS", "5")))
SENT: set[tuple[str, int, int]] = set()


def find_files() -> list[Path]:
    if CANDLE_FILE:
        return [Path(CANDLE_FILE)]
    # Existing capture output convention. Only parsed candle JSONL is read.
    return [Path(name) for name in sorted(glob.glob("browser_candles_*.jsonl"))]


def read_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    if not path.exists():
        return rows
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if not {"time", "open", "high", "low", "close"}.issubset(row):
                    continue
                rows.append(row)
    except OSError as exc:
        print(f"[bridge] Cannot read {path.name}: {type(exc).__name__}")
    return rows


def normalize_row(row: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    symbol = str(row.get("symbol") or row.get("asset") or "").strip()
    if not symbol or len(symbol) > 40 or any(ch.isspace() for ch in symbol):
        return None
    try:
        timestamp = int(row["time"])
        values = {key: float(row[key]) for key in ("open", "high", "low", "close")}
    except (TypeError, ValueError, KeyError, OverflowError):
        return None
    import math
    if timestamp <= 0 or any(not math.isfinite(v) for v in values.values()):
        return None
    o,h,low,c = values["open"],values["high"],values["low"],values["close"]
    if h < max(o,low,c) or low > min(o,h,c):
        return None
    return symbol, {"time":timestamp,**values}


def send_batch(symbol: str, rows: list[dict[str, Any]]) -> bool:
    payload = {
        "symbol": symbol,
        "timeframe_seconds": TIMEFRAME_SECONDS,
        "candles": rows,
    }
    try:
        response = requests.post(
            f"{RENDER_BASE_URL}/api/bridge/candles",
            json=payload,
            headers={"X-Market-Bridge-Token": MARKET_BRIDGE_TOKEN},
            timeout=15,
        )
    except requests.RequestException as exc:
        print(f"[bridge] Render delivery failed: {type(exc).__name__}")
        return False
    if response.status_code != 200:
        print(f"[bridge] Render rejected candle batch: HTTP {response.status_code}")
        return False
    try:
        result = response.json()
    except ValueError:
        print("[bridge] Render returned non-JSON response.")
        return False
    print(f"[bridge] Accepted {result.get('accepted', 0)} candles for {symbol}.")
    return True


def main() -> None:
    if not RENDER_BASE_URL.startswith("https://"):
        raise SystemExit("Set RENDER_BASE_URL to your HTTPS Render service URL.")
    if not MARKET_BRIDGE_TOKEN:
        raise SystemExit("Set MARKET_BRIDGE_TOKEN locally; it must match Render Environment.")
    if TIMEFRAME_SECONDS not in (60, 300):
        raise SystemExit("BROWSER_TIMEFRAME_SECONDS must be 60 or 300.")
    print("[bridge] Read-only candle forwarder started. Ctrl+C stops it.")
    print("[bridge] It reads parsed OHLC JSONL only; no cookies, SSID, or raw WebSocket frames.")
    while True:
        grouped: dict[str, dict[int, dict[str, Any]]] = {}
        for path in find_files():
            for raw in read_rows(path):
                normalized = normalize_row(raw)
                if not normalized:
                    continue
                symbol, candle = normalized
                key = (str(path.resolve()), symbol, candle["time"])
                if key in SENT:
                    continue
                grouped.setdefault(symbol, {})[candle["time"]] = candle
        for symbol, by_time in grouped.items():
            rows = [by_time[t] for t in sorted(by_time)][-200:]
            if send_batch(symbol, rows):
                for row in rows:
                    # Deduplicate by symbol/time across capture files.
                    SENT.add(("*", symbol, row["time"]))
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[bridge] Stopped.")
