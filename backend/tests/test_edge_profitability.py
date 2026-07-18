from types import SimpleNamespace

import pytest

from edge_profitability import EdgeProfitabilityCoordinator, MarketRegime, TradeCardState


def analysis(
    *,
    symbol="AAPL",
    signal=5.0,
    confidence=0.80,
    trend="BULLISH",
    alignment=0.65,
    structure="resistance_breakout",
    price=100.0,
    atr=1.0,
):
    return SimpleNamespace(
        symbol=symbol,
        signal_strength=signal,
        price=price,
        trend=SimpleNamespace(name=trend),
        confidence=SimpleNamespace(overall=confidence),
        metadata={
            "enhanced_authoritative": True,
            "multi_timeframe_alignment": alignment,
            "market_structure": {
                "state": structure,
                "support": price - 2.0,
                "resistance": price,
            },
            "indicators": {"atr_current": atr},
        },
    )


def thesis(symbol="AAPL", entry=100.0, stop=98.0, target=104.0):
    return {
        "symbol": symbol,
        "strategy": "breakout",
        "entry": entry,
        "entry_trigger": entry,
        "stop": stop,
        "targets": [target, target + 2.0],
        "expiration": "2099-01-01T00:00:00+00:00",
        "invalidation": f"close below {stop}",
        "rationale": ["test"],
        "patterns": ["RESISTANCE_BREAKOUT"],
    }


def coordinator(tmp_path):
    return EdgeProfitabilityCoordinator(tmp_path / "profitability.json")


def test_range_regime_is_explicit_no_trade(tmp_path):
    engine = coordinator(tmp_path)
    item = analysis(signal=1.0, confidence=0.75, trend="NEUTRAL", alignment=0.05, structure="range")
    allowed, regime, opportunity, card = engine.evaluate_entry(item, thesis())

    assert not allowed
    assert regime.regime == MarketRegime.RANGE
    assert "range_no_trade" in opportunity.reasons
    assert card is None
    assert engine.symbol_status("AAPL")["no_trade"] is True


def test_breakout_creates_position_scoped_trade_card(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    allowed, regime, opportunity, card = engine.evaluate_entry(analysis(), thesis())

    assert allowed
    assert regime.regime == MarketRegime.BREAKOUT_UP
    assert opportunity.expected_value_pct > 0
    assert card is not None
    assert card.state == TradeCardState.ARMED
    assert card.position_id.startswith("edge-position:")
    assert card.metadata["stop_owner"]["position_id"] == card.position_id
    assert card.metadata["stop_owner"]["inherit_on_reentry"] is False


def test_position_close_expires_stop_and_records_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    allowed, _regime, _opportunity, card = engine.evaluate_entry(analysis(), thesis())
    assert allowed and card is not None

    engine.record_feedback(card, action="buy", feedback={"sent": True, "status": "accepted"}, metadata={"price": 100})
    engine.observe_position("AAPL", {"qty": 10, "avg_entry": 100, "current_pnl_dollar": 0}, current_price=100)
    assert card.state == TradeCardState.ACTIVE

    engine.record_feedback(card, action="sell", feedback={"sent": True, "status": "accepted", "reason": "target"}, metadata={"price": 104})
    engine.observe_position("AAPL", {"qty": 0, "current_pnl_dollar": 40, "current_pnl_pct": 4}, current_price=104)

    assert card.state == TradeCardState.COMPLETED
    assert card.current_stop is None
    assert card.metadata["stop_owner"]["expired_at"]
    assert engine.outcomes[-1]["realized_pnl"] == 40


def test_losses_calibrate_confidence_downward(tmp_path):
    engine = coordinator(tmp_path)
    engine.outcomes = [
        {
            "target_bot": "sentinel-pulse",
            "strategy": "breakout",
            "regime": "breakout_up",
            "realized_pnl": -10,
        }
        for _ in range(20)
    ]
    calibrated = engine.calibrate_confidence(0.80, "sentinel-pulse", "breakout", "breakout_up")
    assert calibrated < 0.60


def test_correlation_penalty_reduces_second_equity_score(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    allowed, _regime, first, card = engine.evaluate_entry(analysis(symbol="AAPL"), thesis(symbol="AAPL"))
    assert allowed and card is not None
    engine.record_feedback(card, action="buy", feedback={"sent": True, "status": "accepted"}, metadata={"price": 100})

    second_analysis = analysis(symbol="NVDA", price=200)
    second_thesis = thesis(symbol="NVDA", entry=200, stop=196, target=208)
    _allowed, _regime, second, _card = engine.evaluate_entry(second_analysis, second_thesis)

    assert second.correlation_penalty > 0
    assert second.score < first.score


def test_external_specialist_proposal_gets_authorization_and_card(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    result = engine.evaluate_external_proposal(
        {
            "proposal_id": "iron-1",
            "source_bot": "sentinel-iron",
            "target_bot": "sentinel-iron",
            "symbol": "ES=F",
            "strategy": "opening_breakout",
            "regime": "trending_up",
            "confidence": 0.80,
            "expected_reward_pct": 2.0,
            "expected_risk_pct": 1.0,
            "entry_price": 5000,
            "stop_price": 4950,
            "targets": [5100],
        }
    )

    assert result["authorized"] is True
    assert result["trade_card"]["target_bot"] == "sentinel-iron"
    assert result["trade_card"]["position_id"].startswith("edge-position:")


def test_execution_feedback_tracks_slippage(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    allowed, _regime, _opportunity, card = engine.evaluate_entry(analysis(), thesis())
    assert allowed and card is not None

    engine.record_feedback(
        card,
        action="buy",
        feedback={"sent": True, "status": "accepted", "filled_price": 100.10, "quantity": 10},
        metadata={"price": 100.0},
    )
    assert engine.execution_feedback[-1]["slippage_bps"] == pytest.approx(10.0)


def test_external_long_is_rejected_in_bearish_regime(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    result = engine.evaluate_external_proposal(
        {
            "source_bot": "sentinel-iron",
            "symbol": "ES=F",
            "direction": "long",
            "strategy": "trend",
            "regime": "trending_down",
            "confidence": 0.90,
            "expected_reward_pct": 3.0,
            "expected_risk_pct": 1.0,
        }
    )
    assert result["authorized"] is False
    assert "direction_regime_conflict" in result["reasons"]


def test_transport_sent_but_rejected_does_not_advance_card(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    allowed, _regime, _opportunity, card = engine.evaluate_entry(analysis(), thesis())
    assert allowed and card is not None
    engine.record_feedback(
        card,
        action="buy",
        feedback={"sent": True, "accepted": False, "status": "rejected", "reason": "risk"},
        metadata={"price": 100},
    )
    assert card.state == TradeCardState.ARMED
    assert engine.execution_feedback[-1]["accepted"] is False


def test_broker_realized_pnl_is_used_for_outcome(tmp_path, monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "5")
    engine = coordinator(tmp_path)
    allowed, _regime, _opportunity, card = engine.evaluate_entry(analysis(), thesis())
    assert allowed and card is not None
    engine.record_feedback(card, action="buy", feedback={"accepted": True, "status": "accepted"}, metadata={"price": 100})
    engine.observe_position("AAPL", {"qty": 10, "avg_entry": 100, "current_pnl_dollar": 0}, current_price=100)
    engine.record_feedback(
        card,
        action="sell",
        feedback={"accepted": True, "status": "accepted", "realized_pnl": 37.5, "realized_return_pct": 3.75},
        metadata={"price": 104},
    )
    engine.observe_position("AAPL", {"qty": 0}, current_price=104)
    assert engine.outcomes[-1]["realized_pnl"] == 37.5
    assert engine.outcomes[-1]["realized_return_pct"] == 3.75
