"""Telegram alerts for filtered CALL/PUT signals, and for SSID/auth problems.

Separate from telegram_market_data.py (which only sends raw candle updates).
This module sends actionable CALL/PUT alerts, but:
  - WAIT is never sent.
  - Signals below TELEGRAM_SIGNAL_MIN_STRENGTH are filtered out.
  - The same (symbol, candle_time, signal) is never sent twice.
  - Every message carries the same heuristic/non-advice disclaimer as the UI.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

import requests

_lock = threading.Lock()
_last_alert_signal: dict[str, tuple[int, str]] = {}
_last_ssid_alert_at = 0.0
_SSID_ALERT_COOLDOWN_SECONDS = 600
_STRENGTH_RANK = {"LOW": 0, "MODERATE": 1}


def _credentials() -> tuple[str, str]:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip(), os.getenv("TELEGRAM_CHAT_ID", "").strip()


def signal_alerts_enabled() -> bool:
    return os.getenv("TELEGRAM_SIGNAL_ALERTS_ENABLED", "true").strip().lower() not in {"0", "false", "no"}


def _min_strength() -> str:
    value = os.getenv("TELEGRAM_SIGNAL_MIN_STRENGTH", "MODERATE").strip().upper()
    return value if value in _STRENGTH_RANK else "MODERATE"


def _send(token: str, chat_id: str, text: str) -> dict[str, Any]:
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            error_code = payload.get("error_code") if isinstance(payload, dict) else None
            return {"sent": False, "reason": "telegram_rejected_message", "error_code": error_code}
        return {"sent": True}
    except (requests.RequestException, ValueError):
        return {"sent": False, "reason": "telegram_delivery_failed"}


def notify_signal(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Send one alert for an actionable, sufficiently-strong, not-yet-seen signal."""
    if not signal_alerts_enabled():
        return {"sent": False, "reason": "signal_alerts_disabled"}
    token, chat_id = _credentials()
    if not token or not chat_id:
        return {"sent": False, "reason": "telegram_not_configured"}

    analysis = snapshot.get("analysis") or {}
    signal = str(analysis.get("signal") or "WAIT")
    if signal not in {"CALL", "PUT"}:
        return {"sent": False, "reason": "no_actionable_signal"}

    strength = str(analysis.get("signal_strength") or "LOW").upper()
    if _STRENGTH_RANK.get(strength, 0) < _STRENGTH_RANK.get(_min_strength(), 1):
        return {"sent": False, "reason": "below_min_strength"}

    symbol = str(snapshot.get("symbol") or "").strip()
    candle = snapshot.get("latest_candle") or {}
    try:
        candle_time = int(candle.get("time") or 0)
    except (TypeError, ValueError):
        candle_time = 0
    if not symbol or candle_time <= 0:
        return {"sent": False, "reason": "missing_symbol_or_candle_timestamp"}

    with _lock:
        if _last_alert_signal.get(symbol) == (candle_time, signal):
            return {"sent": False, "reason": "duplicate_signal"}

        expiry = analysis.get("expiry_recommendation_minutes")
        candle_time_text = datetime.fromtimestamp(candle_time, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        message = (
            f"{'CALL' if signal == 'CALL' else 'PUT'} signal ({strength})\n"
            f"Symbol: {symbol}\n"
            f"Candle time: {candle_time_text}\n"
            f"Reason: {analysis.get('reason', '-')}\n"
            f"RSI(14): {analysis.get('rsi_14', '-')} | MACD hist: {analysis.get('macd_histogram', '-')}\n"
            f"Expiry hint: {expiry if expiry else '-'} minute(s) - {analysis.get('expiry_reason', '')}\n"
            "Heuristic signal only, filtered by strategies.py. Not financial advice, "
            "not a validated system, and not a guaranteed outcome."
        )
        result = _send(token, chat_id, message)
        if result.get("sent"):
            _last_alert_signal[symbol] = (candle_time, signal)
        return result


def notify_ssid_issue(detail: str) -> dict[str, Any]:
    """Alert at most once per cooldown window when a refresh looks like an auth/SSID failure."""
    global _last_ssid_alert_at
    token, chat_id = _credentials()
    if not token or not chat_id:
        return {"sent": False, "reason": "telegram_not_configured"}
    with _lock:
        now = time.monotonic()
        if now - _last_ssid_alert_at < _SSID_ALERT_COOLDOWN_SECONDS:
            return {"sent": False, "reason": "cooldown"}
        message = (
            "Quotex SSID looks expired or invalid.\n"
            f"Detail: {detail[:300]}\n\n"
            "Get a fresh SSID from your browser session (DevTools > Network > WS > auth message) "
            "and update it with:\n"
            "POST /api/admin/ssid  header X-Admin-Token: <your ADMIN_TOKEN>  "
            'body {"ssid": "<new value>"}\n'
            "No redeploy needed; the bot reconnects automatically after this."
        )
        result = _send(token, chat_id, message)
        if result.get("sent"):
            _last_ssid_alert_at = now
        return result


_AUTH_ERROR_HINTS = ("ssid", "session", "login", "auth", "unauthorized", "401", "credential")


def looks_like_auth_error(message: str) -> bool:
    lowered = message.lower()
    return any(hint in lowered for hint in _AUTH_ERROR_HINTS)
