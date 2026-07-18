"""Trade-thesis enrichment for ORB, squeeze and Pulse execution style."""
from __future__ import annotations

import os
from typing import Any, Dict

import edge_brain_analysis
import edge_brain_runtime as brain_runtime
from edge_profitability_entry_timing import ProfitabilityEntryTimingMixin
from edge_profitability_models import finite, iso_now


_ORIGINAL_BUILD_TRADE_THESIS = edge_brain_analysis.build_trade_thesis
_ORIGINAL_ASSESS_ENTRY_TIMING = ProfitabilityEntryTimingMixin.assess_entry_timing
_INSTALLED = False


def _execution_style(strategy: str, squeeze: Dict[str, Any], orb: Dict[str, Any]) -> str:
    if strategy == "short_squeeze_breakout":
        return "breakout_stop_limit"
    if strategy == "breakout" and orb.get("direction") == "bullish":
        return "breakout_stop_limit"
    if strategy in {"continuation", "reversal"}:
        return "passive_limit"
    return "timed_limit"


def build_trade_thesis(symbol: str, analysis: Any, action: str) -> Dict[str, Any]:
    thesis = dict(_ORIGINAL_BUILD_TRADE_THESIS(symbol, analysis, action))
    metadata = dict(getattr(analysis, "metadata", None) or {})
    squeeze = metadata.get("short_squeeze") if isinstance(metadata.get("short_squeeze"), dict) else {}
    orb = metadata.get("orb_evidence") if isinstance(metadata.get("orb_evidence"), dict) else {}
    strongest_orb = orb.get("strongest") if isinstance(orb.get("strongest"), dict) else {}

    if squeeze.get("trigger_confirmed"):
        thesis["strategy"] = "short_squeeze_breakout"
        thesis["rationale"] = list(thesis.get("rationale") or []) + [
            "short-squeeze pressure and price/volume trigger confirmed",
            f"squeeze pressure={finite(squeeze.get('pressure_score')):.1f}/100",
        ]
        orb_trigger = finite(strongest_orb.get("orb_high"))
        if orb.get("direction") == "bullish" and orb_trigger > 0:
            thesis["entry_trigger"] = orb_trigger
        entry = finite(thesis.get("entry"))
        stop = finite(thesis.get("stop"))
        risk = max(entry - stop, entry * 0.01) if entry > 0 and 0 < stop < entry else max(entry * 0.015, 0.01)
        if entry > 0:
            thesis["targets"] = [round(entry + risk * 2.5, 4), round(entry + risk * 4.0, 4)]
        thesis["invalidation"] = (
            f"close back below ORB trigger {orb_trigger:.4f} or squeeze volume fails"
            if orb_trigger > 0 else
            "squeeze trigger loses volume confirmation or bullish structure"
        )

    strategy = str(thesis.get("strategy") or "multi_timeframe_trend")
    preferred = _execution_style(strategy, squeeze, orb)
    trigger_price = finite(thesis.get("entry_trigger")) or None
    thesis["execution_style_preference"] = preferred
    thesis["execution_style_policy"] = {
        "contract_version": "edge.execution_style.v1",
        "preferred_style": preferred,
        "allowed_styles": ["passive_limit", "timed_limit", "breakout_stop_limit"],
        "timeout_seconds": max(1, int(finite(os.getenv("EDGE_TIMED_LIMIT_TIMEOUT_SECONDS"), 8.0))),
        "passive_offset_bps": max(0.0, finite(os.getenv("EDGE_PASSIVE_LIMIT_OFFSET_BPS"), 2.0)),
        "aggressive_limit_buffer_bps": max(0.0, finite(os.getenv("EDGE_TIMED_LIMIT_BUFFER_BPS"), 4.0)),
        "stop_trigger_price": trigger_price,
        "post_fill_horizons_seconds": [30, 60, 300],
        "strategy": strategy,
        "orb_confirmation": orb,
        "squeeze_state": squeeze.get("state"),
    }
    thesis["orb_evidence"] = orb
    thesis["short_squeeze"] = squeeze
    return thesis


def assess_entry_timing(
    self: ProfitabilityEntryTimingMixin,
    analysis: Any,
    thesis: Dict[str, Any],
    *,
    previous: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    metadata = dict(getattr(analysis, "metadata", None) or {})
    squeeze = metadata.get("short_squeeze") if isinstance(metadata.get("short_squeeze"), dict) else {}
    if str(thesis.get("strategy") or "") != "short_squeeze_breakout" or not squeeze.get("trigger_confirmed"):
        return _ORIGINAL_ASSESS_ENTRY_TIMING(self, analysis, thesis, previous=previous)

    price = finite(getattr(analysis, "price", thesis.get("entry")))
    trigger = finite(thesis.get("entry_trigger"), price)
    stop = finite(thesis.get("stop"))
    analysis_metadata = metadata.get("indicators") if isinstance(metadata.get("indicators"), dict) else {}
    atr = finite(analysis_metadata.get("atr_current")) or max(price * 0.005, 0.01)
    risk = max(price - stop, atr) if 0 < stop < price else atr
    maximum = price + risk * max(0.0, finite(os.getenv("EDGE_MAX_ENTRY_SLIPPAGE_R"), 0.15))
    return {
        "contract_version": "edge.entry_timing.v1",
        "symbol": str(getattr(analysis, "symbol", thesis.get("symbol", ""))).upper(),
        "strategy": "short_squeeze_breakout",
        "state": "triggered",
        "ready": True,
        "reason": "short_squeeze_orb_trigger_confirmed",
        "observed_at": iso_now(),
        "triggered_at": iso_now(),
        "observed_price": round(price, 6),
        "ideal_entry_price": round(trigger or price, 6),
        "entry_trigger_price": round(trigger or price, 6),
        "maximum_entry_price": round(maximum, 6),
        "setup_price": round(trigger or price, 6),
        "setup_signal_strength": round(finite(getattr(analysis, "signal_strength", 0.0)), 4),
        "confidence": round(finite(getattr(getattr(analysis, "confidence", None), "overall", 0.0)), 4),
        "atr": round(atr, 6),
        "short_squeeze": squeeze,
        "orb_evidence": metadata.get("orb_evidence"),
    }


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    edge_brain_analysis.build_trade_thesis = build_trade_thesis
    brain_runtime.build_trade_thesis = build_trade_thesis
    ProfitabilityEntryTimingMixin.assess_entry_timing = assess_entry_timing
    _INSTALLED = True
