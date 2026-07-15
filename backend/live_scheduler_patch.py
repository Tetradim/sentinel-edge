"""Live-money data freshness and one-action arbitration for Edge."""
from __future__ import annotations

import asyncio
import os
import time
import weakref
from typing import Any, Dict, Optional

from automation import AutomationMode, HandoffCommand
from price_fetcher import PriceFetcher
from scheduler import EvaluationScheduler


_original_handoff = EvaluationScheduler._handoff_to_pulse_with_feedback
_TASK_ACTIONS: "weakref.WeakKeyDictionary[asyncio.Task, dict[str, str]]" = weakref.WeakKeyDictionary()
_PRICE_SENSITIVE_ACTIONS = {"buy", "sell", "dca"}


def _positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def execution_data_status(self: PriceFetcher, symbol: str) -> Dict[str, Any]:
    """Describe whether current data is fresh enough to authorize live execution."""
    symbol = str(symbol or "").upper()
    max_age = _positive_float("EDGE_LIVE_MAX_QUOTE_AGE_SECONDS", 5.0)
    live = getattr(self, "_live_prices", {}).get(symbol)
    if live:
        price, volume, timestamp = live
        age = max(0.0, time.time() - float(timestamp))
        return {
            "source": "websocket",
            "price": float(price),
            "volume": float(volume or 0),
            "age_seconds": age,
            "max_age_seconds": max_age,
            "executable": age <= max_age and float(price) > 0,
        }

    cached = getattr(self, "_cache", {}).get(symbol)
    if cached:
        frame, fetched_at = cached
        age = max(0.0, time.monotonic() - float(fetched_at))
        price = 0.0
        volume = 0.0
        try:
            if frame is not None and not frame.empty:
                price = float(frame.iloc[-1]["Close"])
                volume = float(frame.iloc[-1]["Volume"])
        except Exception:
            pass
        allowed = _flag("EDGE_ALLOW_CACHED_LIVE_EXECUTION", "false")
        return {
            "source": "cached_ohlcv",
            "price": price,
            "volume": volume,
            "age_seconds": age,
            "max_age_seconds": max_age,
            "executable": allowed and age <= max_age and price > 0,
            "cached_live_execution_enabled": allowed,
        }

    return {
        "source": "unavailable",
        "price": 0.0,
        "volume": 0.0,
        "age_seconds": None,
        "max_age_seconds": max_age,
        "executable": False,
    }


def _suppressed_command(
    scheduler: EvaluationScheduler,
    *,
    symbol: str,
    action,
    confidence: float,
    reason: str,
    orb_session: str,
    stop_type: Optional[str],
    trailing_percent: Optional[float],
    dca: Optional[Dict],
    metadata: Dict,
    suppression_reason: str,
    extra: Dict[str, Any],
) -> Dict[str, Any]:
    command = HandoffCommand(
        symbol=symbol,
        action=action,
        confidence=confidence,
        reason=reason,
        mode=scheduler.automation.settings.mode,
        orb_session=orb_session,
        stop_type=stop_type,
        trailing_percent=trailing_percent,
        dca=dca,
        metadata=metadata,
    )
    scheduler.automation.record_suppressed(command, suppression_reason)
    return {
        "sent": False,
        "status": "suppressed",
        "reason": suppression_reason,
        "symbol": command.symbol,
        "action": command.action.value,
        "mode": command.mode.value,
        "idempotency_key": command.idempotency_key,
        **extra,
    }


async def _handoff_with_fresh_data_and_single_action(
    self: EvaluationScheduler,
    symbol: str,
    action,
    confidence: float,
    reason: str,
    orb_session: str = "market_open",
    stop_type: Optional[str] = None,
    trailing_percent: Optional[float] = None,
    dca: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    action_value = getattr(action, "value", str(action)).lower()
    mode = getattr(self.automation.settings.mode, "value", self.automation.settings.mode)

    if str(mode).lower() == AutomationMode.LIVE.value and action_value in _PRICE_SENSITIVE_ACTIONS:
        data_status = self.prices.execution_data_status(symbol)
        metadata["execution_data"] = data_status
        if not data_status.get("executable"):
            return _suppressed_command(
                self,
                symbol=symbol,
                action=action,
                confidence=confidence,
                reason=reason,
                orb_session=orb_session,
                stop_type=stop_type,
                trailing_percent=trailing_percent,
                dca=dca,
                metadata=metadata,
                suppression_reason="live_execution_data_stale",
                extra={"execution_data": data_status},
            )

    task = asyncio.current_task()
    if task is not None:
        task_actions = _TASK_ACTIONS.setdefault(task, {})
        prior = task_actions.get(str(symbol).upper())
        if prior is not None:
            return _suppressed_command(
                self,
                symbol=symbol,
                action=action,
                confidence=confidence,
                reason=reason,
                orb_session=orb_session,
                stop_type=stop_type,
                trailing_percent=trailing_percent,
                dca=dca,
                metadata=metadata,
                suppression_reason="evaluation_action_already_selected",
                extra={"selected_action": prior},
            )
        task_actions[str(symbol).upper()] = action_value

    return await _original_handoff(
        self,
        symbol=symbol,
        action=action,
        confidence=confidence,
        reason=reason,
        orb_session=orb_session,
        stop_type=stop_type,
        trailing_percent=trailing_percent,
        dca=dca,
        metadata=metadata,
    )


PriceFetcher.execution_data_status = execution_data_status
EvaluationScheduler._handoff_to_pulse_with_feedback = _handoff_with_fresh_data_and_single_action
