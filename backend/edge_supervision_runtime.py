"""Supervisory ladder for concrete stops, partial reductions, and full exits."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from automation import AutomationAction
from engine import Decision, DecisionEngine
from metrics import edge_decision_total
from signals_enhanced import AnalysisResult, TrendDirection as EnhancedTrend

import edge_brain_runtime as brain_runtime
import live_scheduler_patch
from edge_brain_data import clamp, env_float


logger = logging.getLogger(__name__)
_ORIGINAL_DECIDE = DecisionEngine.decide
_ORIGINAL_EMIT = brain_runtime._emit_supervisory_sell
_INSTALLED = False


def _optional_limit(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _expected_position_quantity(engine: DecisionEngine, symbol: str) -> Optional[float]:
    position = engine.get_position(symbol) if hasattr(engine, "get_position") else None
    if not position:
        position = getattr(engine, "positions", {}).get(symbol.upper())
    if not isinstance(position, dict):
        return None
    for key in ("size", "qty", "quantity", "position_size"):
        try:
            value = float(position.get(key) or 0.0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _supervisory_stop_price(analysis: AnalysisResult) -> Optional[float]:
    price = float(analysis.price or 0.0)
    if price <= 0:
        return None
    metadata = analysis.metadata or {}
    indicators = metadata.get("indicators") or {}
    structure = metadata.get("market_structure") or {}
    try:
        atr = float(indicators.get("atr_current") or 0.0)
    except (TypeError, ValueError):
        atr = 0.0
    distance = max(atr * 0.75, price * 0.005, 0.01)
    candidate = price - distance
    try:
        support = float(structure.get("support") or 0.0)
    except (TypeError, ValueError):
        support = 0.0
    if 0 < support < price:
        candidate = max(candidate, support)
    candidate = min(candidate, price * 0.999)
    return round(candidate, 4) if candidate > 0 else None


def _emergency_active(engine: DecisionEngine, symbol: str, kwargs: Dict[str, Any]) -> bool:
    max_losses = int(
        _optional_limit(
            kwargs.get("max_consecutive_losses"),
            float(engine.MAX_CONSECUTIVE_LOSSES),
        )
    )
    max_drawdown = _optional_limit(
        kwargs.get("max_drawdown_pct"),
        float(engine.MAX_DRAWDOWN_PCT),
    )
    return bool(
        engine.global_kill_switch
        or engine.consecutive_losses.get(symbol, 0) >= max_losses
        or float(kwargs.get("current_drawdown") or 0.0) > max_drawdown
    )


def _set_supervisory_context(
    context: Dict[str, Any],
    *,
    directive: str,
    reason: str,
    expected_quantity: Optional[float],
    stop_price: Optional[float] = None,
    reduce_percent: Optional[float] = None,
) -> None:
    # edge_brain_runtime currently invokes its post-evaluation emitter when this
    # legacy trigger is "sell". The typed directive below selects the real action.
    context["supervisory_action"] = "sell"
    context["supervisory_directive"] = directive
    context["supervisory_reason"] = reason
    context["expected_position_quantity"] = expected_quantity
    context["stop_price"] = stop_price
    context["reduce_percent"] = reduce_percent


def _decide_with_supervision(self: DecisionEngine, *args, **kwargs) -> Decision:
    context = brain_runtime._BRAIN_CONTEXT.get()
    analysis: Optional[AnalysisResult] = context.get("analysis") if context else None
    if args or analysis is None or not (analysis.metadata or {}).get("enhanced_authoritative"):
        return _ORIGINAL_DECIDE(self, *args, **kwargs)

    symbol = str(kwargs.get("symbol") or analysis.symbol).upper()
    if not bool(kwargs.get("has_position")) or _emergency_active(self, symbol, kwargs):
        return _ORIGINAL_DECIDE(self, **kwargs)
    if analysis.trend != EnhancedTrend.BEARISH:
        return _ORIGINAL_DECIDE(self, **kwargs)

    signal = float(analysis.signal_strength)
    confidence = float(analysis.confidence.overall)
    expected_quantity = _expected_position_quantity(self, symbol)

    sell_threshold = abs(env_float("EDGE_BRAIN_FULL_EXIT_SIGNAL", 5.5, minimum=0.5))
    sell_confidence = env_float("EDGE_BRAIN_FULL_EXIT_CONFIDENCE", 0.75, minimum=0.0)
    reduce_threshold = abs(env_float("EDGE_BRAIN_REDUCE_SIGNAL", 3.5, minimum=0.5))
    reduce_confidence = env_float("EDGE_BRAIN_REDUCE_CONFIDENCE", 0.65, minimum=0.0)
    stop_threshold = abs(env_float("EDGE_BRAIN_SET_STOP_SIGNAL", 2.0, minimum=0.5))
    stop_confidence = env_float("EDGE_BRAIN_SET_STOP_CONFIDENCE", 0.60, minimum=0.0)

    if signal <= -sell_threshold and confidence >= sell_confidence:
        _set_supervisory_context(
            context,
            directive="sell",
            reason=(
                "Severe enhanced bearish thesis invalidated the position "
                f"(signal={signal:.2f}, confidence={confidence:.2f})"
            ),
            expected_quantity=expected_quantity,
        )
        edge_decision_total.labels(symbol=symbol, decision="sell").inc()
        return Decision.HOLD

    if signal <= -reduce_threshold and confidence >= reduce_confidence:
        severity = clamp(
            (abs(signal) - reduce_threshold) / max(sell_threshold - reduce_threshold, 0.5),
            0.0,
            1.0,
        )
        minimum = env_float("EDGE_BRAIN_REDUCE_MIN_PERCENT", 25.0, minimum=1.0)
        maximum = env_float("EDGE_BRAIN_REDUCE_MAX_PERCENT", 50.0, minimum=minimum)
        reduce_percent = round(minimum + (maximum - minimum) * severity, 2)
        _set_supervisory_context(
            context,
            directive="reduce_position",
            reason=(
                "Confirmed bearish deterioration requires exposure reduction "
                f"(signal={signal:.2f}, confidence={confidence:.2f})"
            ),
            expected_quantity=expected_quantity,
            reduce_percent=reduce_percent,
        )
        edge_decision_total.labels(symbol=symbol, decision="reduce_position").inc()
        return Decision.HOLD

    if signal <= -stop_threshold and confidence >= stop_confidence:
        stop_price = _supervisory_stop_price(analysis)
        if stop_price is not None:
            _set_supervisory_context(
                context,
                directive="set_stop",
                reason=(
                    "Early bearish deterioration requires a concrete protective stop "
                    f"(signal={signal:.2f}, confidence={confidence:.2f})"
                ),
                expected_quantity=expected_quantity,
                stop_price=stop_price,
            )
            edge_decision_total.labels(symbol=symbol, decision="set_stop").inc()
            return Decision.HOLD

    return _ORIGINAL_DECIDE(self, **kwargs)


def _feedback_sent(feedback: Any) -> bool:
    if not isinstance(feedback, dict):
        return False
    status = str(feedback.get("status") or "").lower()
    return bool(
        feedback.get("sent")
        or feedback.get("accepted")
        or feedback.get("ambiguous_delivery")
        or feedback.get("reconciliation_required")
        or status in {"accepted", "processing", "pending", "broker_reconciliation_pending"}
    )


def _record_supervisory_feedback(
    scheduler: Any,
    symbol: str,
    analysis: AnalysisResult,
    directive: str,
    feedback: Any,
) -> None:
    confidence = clamp(float(analysis.confidence.overall), 0.0, 1.0)
    sent = _feedback_sent(feedback)
    item = {
        "symbol": symbol.upper(),
        "decision": directive,
        "signal_strength": round(float(analysis.signal_strength), 2),
        "trend": analysis.trend.name.lower(),
        "confidence": round(confidence, 3),
        "price": round(float(analysis.price or 0.0), 4),
        "has_position": True,
        "handoff_sent": sent,
        "handoff_status": feedback.get("status") if isinstance(feedback, dict) else None,
        "handoff_reason": feedback.get("reason") if isinstance(feedback, dict) else None,
        "pulse_feedback": feedback,
        "supervisory_override": True,
        "timestamp": time.time(),
    }
    scheduler.recent_decisions.insert(0, item)
    scheduler.recent_decisions = scheduler.recent_decisions[:50]
    ticker_state = scheduler.ticker_state.get(symbol.upper())
    if ticker_state is not None:
        ticker_state.update(
            {
                "last_decision": directive,
                "supervisory_override": True,
                "pulse_feedback": feedback,
            }
        )


async def _emit_supervisory_directive(
    scheduler: Any,
    symbol: str,
    analysis: AnalysisResult,
    reason: str,
) -> None:
    context = brain_runtime._BRAIN_CONTEXT.get() or {}
    directive = str(context.get("supervisory_directive") or "sell")
    if directive == "sell":
        await _ORIGINAL_EMIT(scheduler, symbol, analysis, reason)
        return

    value = context.get("stop_price") if directive == "set_stop" else context.get("reduce_percent")
    decision_id = (
        f"edge-supervision:{symbol.upper()}:{directive}:"
        f"{round(float(value or 0.0), 4)}:{int(time.time() // 30)}"
    )
    metadata = {
        "price": analysis.price,
        "signal_strength": analysis.signal_strength,
        "trend": analysis.trend.name.lower(),
        "supervisory_override": True,
        "supervisory_directive": directive,
        "expected_position_quantity": context.get("expected_position_quantity"),
        "max_quantity_drift_percent": env_float(
            "EDGE_BRAIN_POSITION_GUARD_DRIFT_PERCENT", 2.0, minimum=0.0
        ),
        "decision_id": decision_id,
        "brain_version": (analysis.metadata or {}).get("brain_version", "edge-brain-v1"),
    }

    if directive == "set_stop":
        metadata.update(
            {
                "stop_price": context.get("stop_price"),
                "tighten_only": True,
            }
        )
        feedback = await scheduler._handoff_to_pulse_with_feedback(
            symbol=symbol,
            action=AutomationAction.TIGHTEN_STOP,
            confidence=clamp(float(analysis.confidence.overall), 0.0, 1.0),
            reason=reason,
            orb_session="market_open",
            stop_type="tighten",
            metadata=metadata,
        )
    else:
        metadata["reduce_percent"] = context.get("reduce_percent")
        feedback = await scheduler._handoff_to_pulse_with_feedback(
            symbol=symbol,
            action=AutomationAction.SELL,
            confidence=clamp(float(analysis.confidence.overall), 0.0, 1.0),
            reason=reason,
            orb_session="market_open",
            metadata=metadata,
        )

    _record_supervisory_feedback(scheduler, symbol, analysis, directive, feedback)


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    # Concrete stops depend on a current market reference just like buys/sells.
    live_scheduler_patch._PRICE_SENSITIVE_ACTIONS.add("tighten_stop")
    DecisionEngine.decide = _decide_with_supervision
    brain_runtime._emit_supervisory_sell = _emit_supervisory_directive
    _INSTALLED = True
    logger.info("Edge supervisory ladder installed: SET_STOP -> REDUCE_POSITION -> SELL")
