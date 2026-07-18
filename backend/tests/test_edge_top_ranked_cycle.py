from types import SimpleNamespace

from edge_profitability import EdgeProfitabilityCoordinator, TradeCardState


def analysis(
    symbol: str,
    *,
    confidence: float = 0.80,
    signal: float = 5.0,
    price: float = 100.0,
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
                "state": "resistance_breakout",
                "support": price - 2.0,
                "resistance": price,
            },
            "indicators": {"atr_current": 1.0},
        },
    )


def thesis(symbol: str, *, entry: float = 100.0, stop: float = 98.0, target: float = 104.0):
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


def engine(tmp_path):
    return EdgeProfitabilityCoordinator(tmp_path / "profitability.json")


def experiment_env(monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "-100")
    monkeypatch.setenv("EDGE_ENTRY_MIN_CONFIDENCE", "0")
    monkeypatch.setenv("EDGE_MIN_NET_EXPECTED_VALUE_PCT", "0.15")
    monkeypatch.setenv("EDGE_EXPERIMENT_MIN_REWARD_RISK", "2.0")
    monkeypatch.setenv("EDGE_MAX_CYCLE_ENTRIES", "1")


def test_cycle_scores_every_symbol_and_selects_only_best(tmp_path, monkeypatch):
    experiment_env(monkeypatch)
    coordinator = engine(tmp_path)
    cycle = coordinator.begin_evaluation_cycle(["SPY", "QQQ", "AAPL", "NVDA"])
    coordinator.stage_cycle_candidate(cycle, analysis("SPY"), thesis("SPY"), base_decision="buy")
    coordinator.stage_cycle_candidate(cycle, analysis("QQQ"), thesis("QQQ"), base_decision="buy")
    coordinator.stage_cycle_candidate(cycle, analysis("AAPL"), thesis("AAPL"), base_decision="buy")
    coordinator.stage_cycle_candidate(
        cycle,
        analysis("NVDA", confidence=0.90, price=200.0),
        thesis("NVDA", entry=200.0, stop=196.0, target=216.0),
        base_decision="buy",
    )

    finalized = coordinator.finalize_evaluation_cycle(cycle)

    assert finalized["summary"]["candidate_count"] == 4
    assert finalized["summary"]["scored_symbols"] == ["NVDA", "SPY", "QQQ", "AAPL"]
    assert finalized["summary"]["selected_symbols"] == ["NVDA"]
    assert len(finalized["selected"]) == 1
    assert len(coordinator._active_cards()) == 1
    for symbol in ("SPY", "QQQ", "AAPL"):
        reasons = coordinator.latest_decisions[symbol]["opportunity"]["reasons"]
        assert any(reason.startswith("correlated_substitute_of:NVDA") for reason in reasons)


def test_net_expected_value_threshold_is_after_costs(tmp_path, monkeypatch):
    experiment_env(monkeypatch)
    coordinator = engine(tmp_path)
    cycle = coordinator.begin_evaluation_cycle(["AAPL"])
    _regime, opportunity = coordinator.stage_cycle_candidate(
        cycle,
        analysis("AAPL", confidence=0.60),
        thesis("AAPL", entry=100.0, stop=99.75, target=100.50),
        base_decision="buy",
    )
    finalized = coordinator.finalize_evaluation_cycle(cycle)

    assert opportunity.reward_risk == 2.0
    assert opportunity.expected_value_pct < 0.15
    assert "expected_value_below_net_threshold" in opportunity.reasons
    assert finalized["summary"]["selected_symbols"] == []


def test_non_buy_decisions_are_still_scored_but_not_selected(tmp_path, monkeypatch):
    experiment_env(monkeypatch)
    coordinator = engine(tmp_path)
    cycle = coordinator.begin_evaluation_cycle(["SPY"])
    coordinator.stage_cycle_candidate(cycle, analysis("SPY"), thesis("SPY"), base_decision="hold")
    finalized = coordinator.finalize_evaluation_cycle(cycle)

    assert finalized["summary"]["scored_symbols"] == ["SPY"]
    assert finalized["summary"]["selected_symbols"] == []
    assert "base_decision_not_buy" in coordinator.latest_decisions["SPY"]["opportunity"]["reasons"]


def test_active_growth_exposure_rejects_correlated_substitute(tmp_path, monkeypatch):
    experiment_env(monkeypatch)
    coordinator = engine(tmp_path)
    first = coordinator.begin_evaluation_cycle(["AAPL"])
    coordinator.stage_cycle_candidate(first, analysis("AAPL"), thesis("AAPL"), base_decision="buy")
    assert coordinator.finalize_evaluation_cycle(first)["summary"]["selected_symbols"] == ["AAPL"]

    second = coordinator.begin_evaluation_cycle(["NVDA", "XOM"])
    coordinator.stage_cycle_candidate(
        second,
        analysis("NVDA", confidence=0.95, price=200.0),
        thesis("NVDA", entry=200.0, stop=196.0, target=216.0),
        base_decision="buy",
    )
    coordinator.stage_cycle_candidate(second, analysis("XOM"), thesis("XOM"), base_decision="buy")
    finalized = coordinator.finalize_evaluation_cycle(second)

    assert finalized["summary"]["selected_symbols"] == ["XOM"]
    nvda_reasons = coordinator.latest_decisions["NVDA"]["opportunity"]["reasons"]
    assert any(reason.startswith("correlated_active_exposure:AAPL") for reason in nvda_reasons)


def test_maximum_entry_price_preflight_invalidates_chased_entry(tmp_path, monkeypatch):
    experiment_env(monkeypatch)
    coordinator = engine(tmp_path)
    cycle = coordinator.begin_evaluation_cycle(["AAPL"])
    coordinator.stage_cycle_candidate(cycle, analysis("AAPL"), thesis("AAPL"), base_decision="buy")
    card = coordinator.finalize_evaluation_cycle(cycle)["selected"][0]["card"]

    allowed, reason = coordinator.entry_preflight(card, card.maximum_entry_price + 0.01)

    assert allowed is False
    assert reason == "maximum_entry_price_exceeded"
    assert card.state == TradeCardState.INVALIDATED
    assert card.current_stop is None


def test_cycle_configuration_is_exposed_in_portfolio_status(tmp_path, monkeypatch):
    experiment_env(monkeypatch)
    coordinator = engine(tmp_path)
    status = coordinator.portfolio_status(include_cards=False)

    assert status["profitability_experiment"]["maximum_cycle_entries"] == 1
    assert status["profitability_experiment"]["minimum_net_expected_value_pct"] == 0.15
    assert status["profitability_experiment"]["minimum_reward_risk"] == 2.0
