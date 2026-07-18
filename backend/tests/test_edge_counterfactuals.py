from types import SimpleNamespace

import pytest

from edge_profitability import EdgeProfitabilityCoordinator


def analysis(symbol: str, *, price: float, confidence: float = 0.80):
    return SimpleNamespace(
        symbol=symbol,
        signal_strength=5.0,
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


def thesis(symbol: str, *, entry: float, target: float):
    return {
        "symbol": symbol,
        "strategy": "breakout",
        "entry": entry,
        "entry_trigger": entry,
        "stop": entry - 2.0,
        "targets": [target],
        "expiration": "2099-01-01T00:00:00+00:00",
        "invalidation": f"close below {entry - 2.0}",
    }


def configure(monkeypatch):
    monkeypatch.setenv("EDGE_MIN_OPPORTUNITY_SCORE", "-100")
    monkeypatch.setenv("EDGE_ENTRY_MIN_CONFIDENCE", "0")
    monkeypatch.setenv("EDGE_MIN_NET_EXPECTED_VALUE_PCT", "0")
    monkeypatch.setenv("EDGE_EXPERIMENT_MIN_REWARD_RISK", "1.5")
    monkeypatch.setenv("EDGE_MAX_CYCLE_ENTRIES", "1")
    monkeypatch.setenv("EDGE_COUNTERFACTUAL_HORIZON_CYCLES", "2")


def test_selected_and_rejected_candidates_are_marked_counterfactually(tmp_path, monkeypatch):
    configure(monkeypatch)
    state_path = tmp_path / "profitability.json"
    coordinator = EdgeProfitabilityCoordinator(state_path)
    cycle = coordinator.begin_evaluation_cycle(["AAPL", "XOM"])
    coordinator.stage_cycle_candidate(
        cycle,
        analysis("AAPL", price=100.0, confidence=0.90),
        thesis("AAPL", entry=100.0, target=108.0),
        base_decision="buy",
    )
    coordinator.stage_cycle_candidate(
        cycle,
        analysis("XOM", price=100.0, confidence=0.75),
        thesis("XOM", entry=100.0, target=104.0),
        base_decision="buy",
    )
    finalized = coordinator.finalize_evaluation_cycle(cycle)

    assert finalized["summary"]["selected_symbols"] == ["AAPL"]
    initial = coordinator.counterfactual_status(include_records=True)
    assert initial["record_count"] == 2
    assert {record["selected"] for record in initial["records"]} == {True, False}

    coordinator._mark_counterfactuals("AAPL", 104.0)
    coordinator._mark_counterfactuals("XOM", 101.0)
    coordinator._mark_counterfactuals("AAPL", 105.0)
    coordinator._mark_counterfactuals("XOM", 102.0)

    status = coordinator.counterfactual_status(include_records=True)
    assert status["closed_count"] == 2
    assert status["selected_average_return_pct"] == pytest.approx(5.0)
    assert status["rejected_average_return_pct"] == pytest.approx(2.0)
    assert status["selection_edge_pct"] == pytest.approx(3.0)

    restored = EdgeProfitabilityCoordinator(state_path)
    restored_status = restored.counterfactual_status(include_records=True)
    assert restored_status["record_count"] == 2
    assert restored_status["selection_edge_pct"] == pytest.approx(3.0)


def test_counterfactual_summary_is_exposed_in_portfolio_status(tmp_path, monkeypatch):
    configure(monkeypatch)
    coordinator = EdgeProfitabilityCoordinator(tmp_path / "profitability.json")
    status = coordinator.portfolio_status(include_cards=False)

    assert status["counterfactuals"]["contract_version"] == "edge.counterfactual.summary.v1"
    assert status["counterfactuals"]["horizon_cycles"] == 2
