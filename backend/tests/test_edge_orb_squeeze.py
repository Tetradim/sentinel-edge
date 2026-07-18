from datetime import datetime
from types import SimpleNamespace

from edge_orb_squeeze import ShortSqueezeStore, calculate_squeeze_pressure, fuse_orb_and_squeeze
from edge_execution_thesis import build_trade_thesis
from signals_enhanced import AnalysisResult, ConfidenceScore, TrendDirection


def _analysis(*, price=101.0, volume=200.0, signal=4.0):
    return AnalysisResult(
        symbol="GME",
        timestamp=datetime.utcnow(),
        signal_strength=signal,
        trend=TrendDirection.BULLISH,
        confidence=ConfidenceScore(overall=0.80),
        patterns=[],
        price=price,
        volume=volume,
        metadata={
            "enhanced_authoritative": True,
            "multi_timeframe_alignment": 0.65,
            "indicators": {"atr_current": 2.0},
            "market_structure": {
                "state": "resistance_breakout",
                "support": 96.0,
                "resistance": 100.0,
            },
        },
    )


def _scheduler(*, high=100.0, low=95.0, average_volume=100.0):
    level = SimpleNamespace(locked=True, is_valid=True, high=high, low=low)
    orb = SimpleNamespace(get_session_levels=lambda symbol: {"market_open": {15: level}})
    signals = SimpleNamespace(avg_volume={"GME": average_volume})
    return SimpleNamespace(orb=orb, signals=signals)


def _record(store):
    return store.record(
        {
            "contract_version": "edge.squeeze.snapshot.v1",
            "snapshot_id": "squeeze:GME:1",
            "symbol": "GME",
            "source": "test",
            "observed_at": "2026-07-18T12:00:00+00:00",
            "expires_at": "2099-07-19T12:00:00+00:00",
            "short_float_pct": 28.0,
            "days_to_cover": 8.0,
            "borrow_rate_pct": 80.0,
            "utilization_pct": 95.0,
            "availability_change_pct": -30.0,
            "gamma_squeeze_score": 70.0,
            "catalyst_score": 60.0,
        }
    )


def test_squeeze_pressure_is_explainable_and_bounded():
    result = calculate_squeeze_pressure(
        {
            "short_float_pct": 35,
            "days_to_cover": 10,
            "borrow_rate_pct": 100,
            "utilization_pct": 98,
            "gamma_squeeze_score": 80,
            "catalyst_score": 60,
            "availability_change_pct": -40,
        }
    )
    assert 0 <= result["pressure_score"] <= 100
    assert result["pressure_state"] in {"armed", "extreme"}
    assert set(result["components"]) >= {"short_float", "days_to_cover", "borrow_rate"}


def test_pressure_alone_does_not_trigger_entry(tmp_path, monkeypatch):
    store = ShortSqueezeStore(tmp_path / "squeeze.json")
    _record(store)
    monkeypatch.setattr("edge_orb_squeeze.short_squeeze_store", store)

    fused = fuse_orb_and_squeeze(
        _analysis(price=99.0, volume=100.0),
        _scheduler(high=100.0, low=95.0, average_volume=100.0),
    )

    assert fused.metadata["short_squeeze"]["state"] == "armed"
    assert fused.metadata["short_squeeze"]["trigger_confirmed"] is False
    assert fused.metadata["market_event_fusion"]["squeeze_adjustment"] == 0.0


def test_orb_volume_and_squeeze_pressure_create_one_fused_trigger(tmp_path, monkeypatch):
    store = ShortSqueezeStore(tmp_path / "squeeze.json")
    _record(store)
    monkeypatch.setattr("edge_orb_squeeze.short_squeeze_store", store)

    original = _analysis()
    fused = fuse_orb_and_squeeze(original, _scheduler())

    squeeze = fused.metadata["short_squeeze"]
    orb = fused.metadata["orb_evidence"]
    assert squeeze["state"] == "triggering"
    assert squeeze["trigger_confirmed"] is True
    assert orb["direction"] == "bullish"
    assert orb["strongest"]["timeframe_minutes"] == 15
    assert fused.signal_strength > original.signal_strength
    assert fused.signal_strength <= 10.0

    thesis = build_trade_thesis("GME", fused, "buy")
    assert thesis["strategy"] == "short_squeeze_breakout"
    assert thesis["execution_style_preference"] == "breakout_stop_limit"
    assert thesis["execution_style_policy"]["stop_trigger_price"] == 100.0
    assert thesis["short_squeeze"]["trigger_confirmed"] is True
