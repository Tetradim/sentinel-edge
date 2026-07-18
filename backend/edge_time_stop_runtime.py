"""Optional enforcement for Edge time-stop capital recycling recommendations."""
from __future__ import annotations

import logging
from typing import Any, Dict

from engine import Decision, DecisionEngine
import edge_brain_runtime as brain_runtime
from edge_brain_data import env_float
from edge_profitability import coordinator
import edge_supervision_runtime as supervision


logger = logging.getLogger(__name__)
_ORIGINAL_DECIDE = DecisionEngine.decide
_INSTALLED = False


def _decide_with_time_stop(self: DecisionEngine, *args, **kwargs) -> Decision:
    decision = _ORIGINAL_DECIDE(self, *args, **kwargs)
    context: Dict[str, Any] = brain_runtime._BRAIN_CONTEXT.get() or {}
    analysis = context.get("analysis")
    if (
        args
        or analysis is None
        or not (getattr(analysis, "metadata", {}) or {}).get("enhanced_authoritative")
        or not bool(kwargs.get("has_position"))
        or decision == Decision.EMERGENCY_EXIT
        or context.get("supervisory_action") == "sell"
    ):
        return decision

    symbol = str(kwargs.get("symbol") or getattr(analysis, "symbol", "")).upper()
    recommendation = coordinator.time_stop_recommendation(symbol)
    if not recommendation:
        return decision
    context["time_stop"] = recommendation
    mode = coordinator.time_stop_mode
    if mode in {"off", "shadow"}:
        logger.info(
            "Edge time-stop shadow recommendation for %s: %s",
            symbol,
            recommendation.get("recommendation_reason"),
        )
        return decision

    directive = "sell" if mode == "exit" else str(recommendation.get("recommended_action") or "reduce_position")
    if directive not in {"sell", "reduce_position"}:
        directive = "reduce_position"
    context["supervisory_action"] = "sell"
    context["supervisory_directive"] = directive
    context["supervisory_reason"] = str(recommendation.get("recommendation_reason") or "Time-stop capital recycling")
    context["expected_position_quantity"] = supervision._expected_position_quantity(self, symbol)
    context["time_stop_enforced"] = True
    if directive == "reduce_position":
        context["reduce_percent"] = env_float("EDGE_TIME_STOP_REDUCE_PERCENT", 35.0, minimum=1.0)
    logger.warning(
        "Edge enforcing time-stop %s for %s: %s",
        directive,
        symbol,
        context["supervisory_reason"],
    )
    return Decision.HOLD


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    DecisionEngine.decide = _decide_with_time_stop
    _INSTALLED = True
    logger.info("Edge time-stop runtime installed in %s mode", coordinator.time_stop_mode)
