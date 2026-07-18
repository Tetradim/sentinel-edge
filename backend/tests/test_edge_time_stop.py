from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import edge_brain_runtime as brain_runtime
import edge_time_stop_runtime as runtime
from edge_profitability import EdgeProfitabilityCoordinator
from engine import Decision, DecisionEngine


def analysis(symbol="AAPL", price=100.0):
    return SimpleNamespace(
        symbol=symbol,
        signal_strength=1.0,
        price=price,
        trend=SimpleNamespace(name="BULLISH"),
        confidence=SimpleNamespace(overall=0.80),
        metadata={
            "enhanced_authoritative": True,
            "multi_timeframe_alignment": 0.70,
            "market_structure": {
                "state": "resistance_breakout",
                "support": price - 2.0,
                "resistance": price,
            },
            "indicators": {"atr_current": 1.0},
        },
    )


def thesis(symbol="AAPL", entry=100.0, stop=98.0, target=104.0):
    return {
        "symbol": symbol,
        "strategy": "breakout",
        "entry": entry,
        "entry_trigger": entry,
        "stop": stop,
        "targets": [target],
        "expiration": "2099-01-01T00:00:00+00:00",
        "invalidation": f"close below {stop}",
        "rationale": ["test"],
        "patterns": ["RESISTANCE_BREAKOUT"],
    }


def active_card(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "-100")
    monkeypatch.setenv("EDGE_ENTRY_MIN_CONFIDENCE", "0")
    monkeypatch.setenv("EDGE_MIN_NET_EXPECTED_VALUE_PCT", "0")
    monkeypatch.setenv("EDGE_EXPERIMENT_MIN_REWARD_RISK", "1")
    engine = EdgeProfitabilityCoordinator(tmp_path / "profitability.json")
    cycle = engine.begin_evaluation_cycle(["AAPL"])
    engine.stage_cycle_candidate(cycle, analysis(), thesis(), base_decision="buy")
    card = engine.finalize_evaluation_cycle(cycle)["selected"][0]["card"]
    engine.record_feedback(card, action="buy", feedback={"accepted": True, "status": "accepted"}, metadata={"price": 100})
    engine.observe_position("AAPL", {"qty": 10, "avg_entry": 100}, current_price=100)
    return engine, card


def age_measurement(card, *, observations=4, minutes=31):
    metrics = dict(card.metadata["time_stop"])
    metrics["opened_at_confirmed"] = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    metrics["observations"] = observations
    card.metadata["time_stop"] = metrics


def test_stagnant_breakout_generates_shadow_reduction(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_TIME_STOP_MODE", "shadow")
    monkeypatch.setenv("EDGE_TIME_STOP_BREAKOUT_MINUTES", "30")
    monkeypatch.setenv("EDGE_TIME_STOP_MIN_OBSERVATIONS", "5")
    engine, card = active_card(tmp_path, monkeypatch)
    age_measurement(card)

    engine.observe_position("AAPL", {"qty": 10, "avg_entry": 100}, current_price=100.10)
    recommendation = engine.time_stop_recommendation("AAPL")

    assert recommendation["recommendation_active"] is True
    assert recommendation["recommended_action"] == "reduce_position"
    assert recommendation["current_r"] == 0.05
    assert recommendation["max_favorable_r"] < 0.50
    assert engine.portfolio_status(include_cards=False)["time_stop"]["recommendation_count"] == 1


def test_reaching_half_r_disables_time_stop(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_TIME_STOP_MODE", "shadow")
    monkeypatch.setenv("EDGE_TIME_STOP_BREAKOUT_MINUTES", "1")
    monkeypatch.setenv("EDGE_TIME_STOP_MIN_OBSERVATIONS", "2")
    engine, card = active_card(tmp_path, monkeypatch)
    age_measurement(card, observations=1, minutes=5)

    engine.observe_position("AAPL", {"qty": 10, "avg_entry": 100}, current_price=101.0)
    metrics = card.metadata["time_stop"]

    assert metrics["max_favorable_r"] == 0.5
    assert metrics["reached_progress_target_at"]
    assert metrics["recommendation_active"] is False
    assert engine.time_stop_recommendation("AAPL") == {}


def test_time_stop_metrics_are_attributed_to_terminal_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_TIME_STOP_MODE", "shadow")
    engine, card = active_card(tmp_path, monkeypatch)
    engine.observe_position("AAPL", {"qty": 10, "avg_entry": 100}, current_price=100.5)
    engine.record_feedback(
        card,
        action="sell",
        feedback={"accepted": True, "status": "accepted", "realized_pnl": 5, "realized_return_pct": 0.5},
        metadata={"price": 100.5},
    )
    engine.observe_position("AAPL", {"qty": 0}, current_price=100.5)

    attributed = engine.outcomes[-1]["metadata"]["time_stop"]
    assert attributed["max_favorable_r"] == 0.25
    assert attributed["observations"] >= 2


def test_reduce_mode_reuses_supervisory_directive_without_overriding_emergency(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_TIME_STOP_MODE", "reduce")
    engine, card = active_card(tmp_path, monkeypatch)
    metrics = dict(card.metadata["time_stop"])
    metrics.update(
        {
            "recommendation_active": True,
            "recommended_action": "reduce_position",
            "recommendation_reason": "stagnant test position",
        }
    )
    card.metadata["time_stop"] = metrics
    engine.cards[card.card_id] = card
    monkeypatch.setattr(runtime, "coordinator", engine)
    monkeypatch.setattr(runtime, "_ORIGINAL_DECIDE", lambda self, *args, **kwargs: Decision.HOLD)

    decision_engine = DecisionEngine()
    decision_engine.positions["AAPL"] = {"size": 10}
    context = {"analysis": analysis(), "supervisory_action": None}
    token = brain_runtime._BRAIN_CONTEXT.set(context)
    try:
        decision = runtime._decide_with_time_stop(
            decision_engine,
            symbol="AAPL",
            has_position=True,
            current_drawdown=0,
        )
    finally:
        brain_runtime._BRAIN_CONTEXT.reset(token)

    assert decision == Decision.HOLD
    assert context["supervisory_directive"] == "reduce_position"
    assert context["reduce_percent"] == 35.0
    assert context["time_stop_enforced"] is True

    monkeypatch.setattr(runtime, "_ORIGINAL_DECIDE", lambda self, *args, **kwargs: Decision.EMERGENCY_EXIT)
    emergency_context = {"analysis": analysis(), "supervisory_action": None}
    token = brain_runtime._BRAIN_CONTEXT.set(emergency_context)
    try:
        emergency = runtime._decide_with_time_stop(
            decision_engine,
            symbol="AAPL",
            has_position=True,
            current_drawdown=10,
        )
    finally:
        brain_runtime._BRAIN_CONTEXT.reset(token)
    assert emergency == Decision.EMERGENCY_EXIT
    assert emergency_context.get("time_stop_enforced") is None
