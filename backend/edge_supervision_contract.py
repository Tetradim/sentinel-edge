"""Typed supervisory directives inside the compatible Pulse handoff envelope."""
from __future__ import annotations

import math
from typing import Any, Dict

from automation import HandoffCommand


_ORIGINAL_EXECUTION_INTENT = HandoffCommand.execution_intent
_INSTALLED = False


def _positive(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _nonnegative(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) and number >= 0 else default


def _execution_intent_v3(self: HandoffCommand) -> Dict[str, Any]:
    base = _ORIGINAL_EXECUTION_INTENT(self)
    directive = str(self.metadata.get("supervisory_directive") or "").strip().lower()
    if directive not in {"set_stop", "reduce_position"}:
        return base

    intent = dict(base)
    intent["contract_version"] = "edge.execution_intent.v3"
    intent["directive"] = directive

    expected_quantity = _positive(self.metadata.get("expected_position_quantity"))
    if expected_quantity is not None:
        intent["position_guard"] = {
            "expected_quantity": expected_quantity,
            "max_quantity_drift_percent": _nonnegative(
                self.metadata.get("max_quantity_drift_percent"), 2.0
            ),
        }

    if directive == "set_stop":
        stop_price = _positive(self.metadata.get("stop_price"))
        intent["stop_policy"] = {
            "type": "absolute",
            "stop_price": stop_price,
            "tighten_only": bool(self.metadata.get("tighten_only", True)),
        }
        intent["quantity_policy"] = {"type": "preserve_position"}
    else:
        reduce_quantity = _positive(self.metadata.get("reduce_quantity"))
        reduce_percent = _positive(self.metadata.get("reduce_percent"))
        if reduce_quantity is not None:
            intent["quantity_policy"] = {
                "type": "reduce_quantity",
                "reduce_quantity": reduce_quantity,
            }
        else:
            intent["quantity_policy"] = {
                "type": "reduce_percent",
                "reduce_percent": reduce_percent,
            }
        intent["stop_policy"] = None

    intent["supervision"] = {
        "brain_version": self.metadata.get("brain_version", "edge-brain-v1"),
        "signal_strength": self.metadata.get("signal_strength"),
        "trend": self.metadata.get("trend"),
        "confidence": self.confidence,
        "thesis": self.metadata.get("trade_thesis"),
    }
    return intent


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    HandoffCommand.execution_intent = _execution_intent_v3
    _INSTALLED = True


install()
