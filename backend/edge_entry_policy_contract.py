"""Attach price and execution-cost profitability limits to Pulse BUY intents."""
from __future__ import annotations

import math
import os
from typing import Any, Dict

from automation import AutomationAction, HandoffCommand


_ORIGINAL_EXECUTION_INTENT = HandoffCommand.execution_intent
_PATCH_MARKER = "_edge_entry_policy_contract_v1"


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _positive(value: Any) -> float | None:
    number = _finite(value)
    return number if number > 0 else None


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    return max(minimum, _finite(os.getenv(name), default))


def build_entry_policy(metadata: Dict[str, Any]) -> Dict[str, Any]:
    metadata = metadata if isinstance(metadata, dict) else {}
    card = metadata.get("trade_card") if isinstance(metadata.get("trade_card"), dict) else {}
    card_meta = card.get("metadata") if isinstance(card.get("metadata"), dict) else {}
    lifecycle = metadata.get("strategy_lifecycle") if isinstance(metadata.get("strategy_lifecycle"), dict) else {}

    reference_price = (
        _positive(metadata.get("ideal_entry_price"))
        or _positive(card.get("entry_price"))
        or _positive(metadata.get("entry_price"))
        or _positive(metadata.get("price"))
    )
    maximum_entry_price = (
        _positive(metadata.get("maximum_entry_price"))
        or _positive(card.get("maximum_entry_price"))
        or _positive(lifecycle.get("maximum_entry_price"))
    )
    expected_value_pct = _finite(
        metadata.get("expected_value_pct"),
        _finite(card.get("expected_value_pct")),
    )
    baseline_cost_pct = max(
        0.0,
        _finite(
            metadata.get("estimated_cost_pct"),
            _finite(
                card_meta.get("estimated_cost_pct"),
                _env_float("EDGE_ESTIMATED_ROUND_TRIP_COST_BPS", 10.0) / 100.0,
            ),
        ),
    )
    minimum_remaining = _env_float(
        "EDGE_MIN_REMAINING_NET_EV_PCT",
        _env_float("EDGE_MIN_NET_EXPECTED_VALUE_PCT", 0.15),
    )
    # Allow only the cost degradation that leaves the experiment's required net
    # expectancy intact. A trade at the threshold receives no extra cost budget.
    maximum_execution_cost = baseline_cost_pct + max(0.0, expected_value_pct - minimum_remaining)
    configured_cost = _positive(metadata.get("maximum_execution_cost_pct"))
    if configured_cost is not None:
        maximum_execution_cost = min(maximum_execution_cost, configured_cost)
    maximum_spread = _env_float(
        "EDGE_MAX_ENTRY_SPREAD_PCT",
        min(0.20, maximum_execution_cost) if maximum_execution_cost > 0 else 0.20,
        minimum=0.01,
    )

    return {
        "contract_version": "edge.entry_policy.v1",
        "direction": "long",
        "reference_price": reference_price,
        "ideal_entry_price": reference_price,
        "maximum_entry_price": maximum_entry_price,
        "expected_value_pct": round(expected_value_pct, 6),
        "estimated_cost_pct": round(baseline_cost_pct, 6),
        "maximum_execution_cost_pct": round(maximum_execution_cost, 6),
        "minimum_remaining_expected_value_pct": round(minimum_remaining, 6),
        "maximum_spread_pct": round(maximum_spread, 6),
        "card_id": str(card.get("card_id") or metadata.get("card_id") or ""),
        "position_id": str(card.get("position_id") or metadata.get("position_id") or ""),
        "trigger_state": str(
            metadata.get("entry_trigger_state")
            or card_meta.get("entry_trigger_state")
            or "triggered"
        ),
    }


def _execution_intent_with_entry_policy(self: HandoffCommand) -> Dict[str, Any]:
    intent = _ORIGINAL_EXECUTION_INTENT(self)
    if self.action == AutomationAction.BUY:
        intent["entry_policy"] = build_entry_policy(self.metadata)
    return intent


if not getattr(HandoffCommand.execution_intent, _PATCH_MARKER, False):
    setattr(_execution_intent_with_entry_policy, _PATCH_MARKER, True)
    HandoffCommand.execution_intent = _execution_intent_with_entry_policy
