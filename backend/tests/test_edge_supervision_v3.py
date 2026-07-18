"""Regression tests for Edge's concrete supervisory action ladder."""
from datetime import datetime

import pytest

import edge_brain_runtime as brain_runtime
import edge_supervision_contract  # noqa: F401 - installs HandoffCommand v3 adapter
import edge_supervision_runtime as supervision
from automation import AutomationAction, AutomationMode, HandoffCommand
from engine import Decision, DecisionEngine
from signals import TrendDirection as DecisionTrend
from signals_enhanced import AnalysisResult, ConfidenceScore, TrendDirection as EnhancedTrend


def _analysis(signal: float, confidence: float, *, price: float = 100.0) -> AnalysisResult:
    return AnalysisResult(
        symbol="SPY",
        timestamp=datetime.utcnow(),
        signal_strength=signal,
        trend=EnhancedTrend.BEARISH,
        confidence=ConfidenceScore(overall=confidence),
        patterns=[],
        price=price,
        volume=1_000_000,
        metadata={
            "enhanced_authoritative": True,
            "brain_version": "edge-brain-v1",
            "indicators": {"atr_current": 2.0},
            "market_structure": {"support": 98.0, "resistance": 104.0},
        },
    )


def _decision_kwargs(**overrides):
    values = {
        "symbol": "SPY",
        "trend": DecisionTrend.NEUTRAL,
        "signal_strength": 0.0,
        "confidence": 1.0,
        "pnl": -100.0,
        "pnl_pct": -1.0,
        "current_drawdown": 1.0,
        "has_position": True,
        "trailing_enabled": False,
    }
    values.update(overrides)
    return values


def _run_decision(analysis: AnalysisResult):
    engine = DecisionEngine()
    engine.positions["SPY"] = {"size": 10.0, "current_pnl_pct": -1.0}
    context = {"analysis": analysis, "supervisory_action": None}
    token = brain_runtime._BRAIN_CONTEXT.set(context)
    try:
        decision = supervision._decide_with_supervision(engine, **_decision_kwargs())
    finally:
        brain_runtime._BRAIN_CONTEXT.reset(token)
    return decision, context


def test_early_bearish_deterioration_sets_absolute_stop():
    decision, context = _run_decision(_analysis(-2.5, 0.65))
    assert decision == Decision.HOLD
    assert context["supervisory_directive"] == "set_stop"
    assert 0 < context["stop_price"] < 100.0
    assert context["expected_position_quantity"] == 10.0


def test_confirmed_bearish_deterioration_reduces_position():
    decision, context = _run_decision(_analysis(-4.5, 0.70))
    assert decision == Decision.HOLD
    assert context["supervisory_directive"] == "reduce_position"
    assert 25.0 <= context["reduce_percent"] <= 50.0
    assert context["expected_position_quantity"] == 10.0


def test_severe_bearish_invalidation_keeps_full_sell():
    decision, context = _run_decision(_analysis(-6.5, 0.85))
    assert decision == Decision.HOLD
    assert context["supervisory_directive"] == "sell"
    assert "invalidated" in context["supervisory_reason"]


def test_reduce_position_serializes_execution_intent_v3_inside_v1_envelope():
    command = HandoffCommand(
        symbol="SPY",
        action=AutomationAction.SELL,
        confidence=0.72,
        reason="reduce risk",
        mode=AutomationMode.PAPER,
        metadata={
            "supervisory_directive": "reduce_position",
            "reduce_percent": 40.0,
            "expected_position_quantity": 10.0,
            "max_quantity_drift_percent": 2.0,
            "signal_strength": -4.5,
            "trend": "bearish",
            "position_id": "edge-position:test",
        },
    )
    payload = command.payload()
    intent = payload["metadata"]["execution_intent"]
    assert payload["contract_version"] == "edge.pulse.handoff.v1"
    assert payload["action"] == "sell"
    assert intent["contract_version"] == "edge.execution_intent.v3"
    assert intent["directive"] == "reduce_position"
    assert intent["quantity_policy"] == {"type": "reduce_percent", "reduce_percent": 40.0}
    assert intent["position_guard"]["expected_quantity"] == 10.0
    assert intent["position_guard"]["expected_position_id"] == "edge-position:test"


def test_set_stop_serializes_position_scoped_tighten_only_policy():
    command = HandoffCommand(
        symbol="SPY",
        action=AutomationAction.TIGHTEN_STOP,
        confidence=0.65,
        reason="protect thesis",
        mode=AutomationMode.PAPER,
        stop_type="tighten",
        metadata={
            "supervisory_directive": "set_stop",
            "stop_price": 98.25,
            "tighten_only": True,
            "position_id": "edge-position:test",
        },
    )
    intent = command.payload()["metadata"]["execution_intent"]
    assert intent["directive"] == "set_stop"
    assert intent["stop_policy"]["type"] == "absolute"
    assert intent["stop_policy"]["stop_price"] == 98.25
    assert intent["stop_policy"]["tighten_only"] is True
    assert intent["stop_policy"]["position_id"] == "edge-position:test"
    assert intent["stop_policy"]["inherit_on_reentry"] is False


@pytest.mark.asyncio
async def test_emitter_sends_reduce_as_sell_envelope_with_typed_directive():
    analysis = _analysis(-4.5, 0.70)
    calls = []

    class _Scheduler:
        def __init__(self):
            self.recent_decisions = []
            self.ticker_state = {"SPY": {}}

        async def _handoff_to_pulse_with_feedback(self, **kwargs):
            calls.append(kwargs)
            return {"sent": True, "accepted": True, "status": "accepted", "reason": "accepted"}

    scheduler = _Scheduler()
    context = {
        "analysis": analysis,
        "supervisory_directive": "reduce_position",
        "reduce_percent": 40.0,
        "expected_position_quantity": 10.0,
    }
    token = brain_runtime._BRAIN_CONTEXT.set(context)
    try:
        await supervision._emit_supervisory_directive(scheduler, "SPY", analysis, "confirmed deterioration")
    finally:
        brain_runtime._BRAIN_CONTEXT.reset(token)

    assert calls[0]["action"] == AutomationAction.SELL
    assert calls[0]["metadata"]["supervisory_directive"] == "reduce_position"
    assert calls[0]["metadata"]["reduce_percent"] == 40.0
    assert scheduler.recent_decisions[0]["decision"] == "reduce_position"
    assert scheduler.ticker_state["SPY"]["last_decision"] == "reduce_position"


def test_production_install_order_is_profitability_then_supervision_then_brain():
    import edge_brain_patch  # noqa: F401
    import edge_profitability_runtime as profitability

    assert DecisionEngine.decide is profitability._profitability_decide
    assert profitability._ORIGINAL_DECIDE is supervision._decide_with_supervision
    assert supervision._ORIGINAL_DECIDE is brain_runtime._decide
    assert "tighten_stop" in __import__("live_scheduler_patch")._PRICE_SENSITIVE_ACTIONS
