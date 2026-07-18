from types import SimpleNamespace

from edge_profitability import EdgeProfitabilityCoordinator


def analysis(
    *,
    symbol="AAPL",
    price=100.0,
    signal=4.0,
    confidence=0.80,
    support=99.6,
    resistance=103.0,
    structure="pullback",
    atr=1.0,
):
    return SimpleNamespace(
        symbol=symbol,
        signal_strength=signal,
        price=price,
        trend=SimpleNamespace(name="BULLISH"),
        confidence=SimpleNamespace(overall=confidence),
        metadata={
            "enhanced_authoritative": True,
            "multi_timeframe_alignment": 0.70,
            "market_structure": {
                "state": structure,
                "support": support,
                "resistance": resistance,
            },
            "indicators": {"atr_current": atr, "ema_20": support + 0.1},
        },
    )


def thesis(*, symbol="AAPL", entry=100.0, stop=98.0, target=104.0, strategy="multi_timeframe_trend"):
    return {
        "symbol": symbol,
        "strategy": strategy,
        "entry": entry,
        "entry_trigger": entry,
        "stop": stop,
        "targets": [target],
        "expiration": "2099-01-01T00:00:00+00:00",
        "invalidation": f"close below {stop}",
        "rationale": ["test"],
        "patterns": [],
    }


def coordinator(tmp_path):
    return EdgeProfitabilityCoordinator(tmp_path / "profitability.json")


def permissive_experiment(monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "-100")
    monkeypatch.setenv("EDGE_ENTRY_MIN_CONFIDENCE", "0")
    monkeypatch.setenv("EDGE_MIN_NET_EXPECTED_VALUE_PCT", "0")
    monkeypatch.setenv("EDGE_EXPERIMENT_MIN_REWARD_RISK", "1")
    monkeypatch.setenv("EDGE_MAX_CYCLE_ENTRIES", "1")
    monkeypatch.setenv("EDGE_ENTRY_SETUP_PROXIMITY_ATR", "0.55")
    monkeypatch.setenv("EDGE_ENTRY_TRIGGER_RECLAIM_ATR", "0.12")
    monkeypatch.setenv("EDGE_ENTRY_TRIGGER_SIGNAL_IMPROVEMENT", "0.25")


def test_extended_trend_is_forecast_not_an_immediate_buy(tmp_path, monkeypatch):
    permissive_experiment(monkeypatch)
    engine = coordinator(tmp_path)
    cycle = engine.begin_evaluation_cycle(["AAPL"])
    _regime, opportunity = engine.stage_cycle_candidate(
        cycle,
        analysis(price=103.0, support=99.5),
        thesis(entry=103.0, stop=99.0, target=111.0),
        base_decision="buy",
    )
    finalized = engine.finalize_evaluation_cycle(cycle)

    assert finalized["summary"]["selected_symbols"] == []
    assert "entry_forecast_only" in opportunity.reasons
    assert engine.latest_decisions["AAPL"]["entry_timing"]["state"] == "forecast"


def test_pullback_requires_setup_then_reclaim_trigger(tmp_path, monkeypatch):
    permissive_experiment(monkeypatch)
    engine = coordinator(tmp_path)

    first = engine.begin_evaluation_cycle(["AAPL"])
    _regime, first_opportunity = engine.stage_cycle_candidate(
        first,
        analysis(price=100.0, signal=4.0, support=99.6),
        thesis(entry=100.0, stop=98.0, target=104.0),
        base_decision="buy",
    )
    assert engine.finalize_evaluation_cycle(first)["summary"]["selected_symbols"] == []
    assert "entry_setup_waiting_for_trigger" in first_opportunity.reasons
    setup = engine.latest_decisions["AAPL"]["entry_timing"]
    assert setup["state"] == "setup"

    second = engine.begin_evaluation_cycle(["AAPL"])
    _regime, second_opportunity = engine.stage_cycle_candidate(
        second,
        analysis(price=100.25, signal=4.5, support=99.6),
        thesis(entry=100.25, stop=98.0, target=104.75),
        base_decision="buy",
    )
    finalized = engine.finalize_evaluation_cycle(second)

    assert second_opportunity.eligible is True
    assert finalized["summary"]["selected_symbols"] == ["AAPL"]
    card = finalized["selected"][0]["card"]
    assert card.metadata["entry_trigger_state"] == "triggered"
    assert card.metadata["entry_timing"]["reason"] == "pullback_reclaim_confirmed"
    assert card.maximum_entry_price > 100.25
    assert card.entry_trigger > setup["setup_price"]


def test_confirmed_breakout_can_trigger_in_one_cycle(tmp_path, monkeypatch):
    permissive_experiment(monkeypatch)
    engine = coordinator(tmp_path)
    cycle = engine.begin_evaluation_cycle(["NVDA"])
    _regime, opportunity = engine.stage_cycle_candidate(
        cycle,
        analysis(
            symbol="NVDA",
            price=200.0,
            signal=6.0,
            support=196.0,
            resistance=200.0,
            structure="resistance_breakout",
            atr=2.0,
        ),
        thesis(symbol="NVDA", entry=200.0, stop=196.0, target=208.0, strategy="breakout"),
        base_decision="buy",
    )
    finalized = engine.finalize_evaluation_cycle(cycle)

    assert opportunity.eligible is True
    assert finalized["summary"]["selected_symbols"] == ["NVDA"]
    timing = engine.latest_decisions["NVDA"]["entry_timing"]
    assert timing["state"] == "triggered"
    assert timing["reason"] == "confirmed_resistance_breakout"


def test_entry_timing_settings_are_exposed(tmp_path, monkeypatch):
    permissive_experiment(monkeypatch)
    status = coordinator(tmp_path).portfolio_status(include_cards=False)
    experiment = status["profitability_experiment"]
    assert experiment["forecast_setup_trigger_required"] is True
    assert experiment["entry_timing_contract"] == "edge.entry_timing.v1"
