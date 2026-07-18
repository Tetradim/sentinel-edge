import asyncio
from datetime import datetime

import numpy as np
import pandas as pd

import live_scheduler_patch  # noqa: F401 - installs safety wrapper first
import edge_brain_analysis as analysis_patch
import edge_brain_data as data_patch
import edge_brain_runtime as runtime_patch
from automation import AutomationAction
from engine import Decision, DecisionEngine
from scheduler import EvaluationScheduler
from signals import TrendDirection as DecisionTrend
from shared.observations import ExecutionObservation, ObservationSource
from signals_enhanced import (
    AnalysisResult,
    ConfidenceScore,
    PatternResult,
    SCIPY_AVAILABLE,
    SignalEngineEnhanced,
    TrendDirection as EnhancedTrend,
)


def _uppercase_frame(rows: int = 480, trend: float = 0.02) -> pd.DataFrame:
    index = pd.date_range("2026-01-02 09:30", periods=rows, freq="1min")
    base = 80 + np.linspace(0, trend * rows, rows) + np.sin(np.arange(rows) / 7) * 0.15
    return pd.DataFrame(
        {
            "Open": base - 0.03,
            "High": base + 0.12,
            "Low": base - 0.15,
            "Close": base,
            "Volume": np.linspace(100_000, 180_000, rows),
        },
        index=index,
    )


def _analysis(
    *,
    signal: float = -6.0,
    confidence: float = 0.85,
    trend: EnhancedTrend = EnhancedTrend.BEARISH,
) -> AnalysisResult:
    return AnalysisResult(
        symbol="SPY",
        timestamp=datetime.utcnow(),
        signal_strength=signal,
        trend=trend,
        confidence=ConfidenceScore(overall=confidence),
        patterns=[],
        price=620.0,
        volume=1_000_000,
        metadata={
            "enhanced_authoritative": True,
            "brain_version": "edge-brain-v1",
            "multi_timeframe_alignment": -0.75,
            "market_structure": {
                "state": "support_breakdown",
                "support": 621.0,
                "resistance": 628.0,
                "confidence": 0.8,
            },
            "indicators": {"atr_current": 3.0},
        },
    )


def test_uppercase_provider_data_runs_full_enhanced_engine():
    engine = SignalEngineEnhanced(enable_talib=False, multi_timeframe=False)
    data_patch.configure_engine(engine)
    result = asyncio.run(
        runtime_patch._analyze(engine, "ASTS", _uppercase_frame(), timeframe="15m")
    )

    assert SCIPY_AVAILABLE is True
    assert engine.multi_timeframe is True
    assert engine.default_timeframe == "15m"
    assert "HEAD_SHOULDERS" in engine.enabled_patterns
    assert "INVERSE_HEAD_SHOULDERS" in engine.enabled_patterns
    assert result.metadata["enhanced_authoritative"] is True
    assert result.metadata["brain_version"] == "edge-brain-v1"
    assert -10.0 <= result.signal_strength <= 10.0


def test_atr_fallback_preserves_input_length():
    high = np.array([10, 11, 12, 13, 14], dtype=float)
    low = np.array([9, 9.5, 10.5, 11.5, 12.0], dtype=float)
    close = np.array([9.5, 10.5, 11.0, 12.5, 13.0], dtype=float)

    atr = data_patch.safe_compute_atr(high, low, close, period=3)

    assert len(atr) == len(close)
    assert np.isfinite(atr).all()
    assert (atr > 0).all()


def test_enhanced_failure_is_neutral_not_full_confidence(monkeypatch):
    async def explode(*_args, **_kwargs):
        raise RuntimeError("indicator failure")

    monkeypatch.setattr(runtime_patch, "_ORIGINAL_ANALYZE", explode)
    engine = SignalEngineEnhanced(enable_talib=False)
    result = asyncio.run(
        runtime_patch._analyze(engine, "ASTS", _uppercase_frame(), timeframe="15m")
    )

    assert result.signal_strength == 0.0
    assert result.trend == EnhancedTrend.NEUTRAL
    assert result.confidence.overall == 0.0
    assert result.metadata["fallback"] == "neutral_hold"


def test_confirmed_bearish_position_requests_explicit_sell():
    engine = DecisionEngine()
    context = {"analysis": _analysis(), "supervisory_action": None}
    token = runtime_patch._BRAIN_CONTEXT.set(context)
    try:
        decision = runtime_patch._decide(
            engine,
            symbol="SPY",
            trend=DecisionTrend.NEUTRAL,
            signal_strength=0.0,
            confidence=1.0,
            pnl=-100.0,
            pnl_pct=-1.0,
            current_drawdown=1.0,
            has_position=True,
            trailing_enabled=False,
        )
    finally:
        runtime_patch._BRAIN_CONTEXT.reset(token)

    assert decision == Decision.HOLD
    assert context["supervisory_action"] == "sell"
    assert "invalidated" in context["supervisory_reason"]


def test_handoff_contains_explainable_trade_thesis(monkeypatch):
    scheduler = EvaluationScheduler.__new__(EvaluationScheduler)
    scheduler._edge_brain_state = {"SPY": _analysis()}
    captured = {}

    async def original(_self, **kwargs):
        captured.update(kwargs)
        return {"sent": True, "status": "accepted"}

    monkeypatch.setattr(runtime_patch, "_ORIGINAL_HANDOFF", original)
    result = asyncio.run(
        runtime_patch._handoff(
            scheduler,
            symbol="SPY",
            action=AutomationAction.SELL,
            confidence=0.1,
            reason="legacy reason",
            metadata={"price": 620.0},
        )
    )

    thesis = captured["metadata"]["trade_thesis"]
    assert result["sent"] is True
    assert captured["confidence"] == 0.85
    assert captured["metadata"]["enhanced_signal_strength"] == -6.0
    assert thesis["strategy"] == "breakdown"
    assert thesis["entry"] == 620.0
    assert thesis["confidence"] == 0.85
    assert thesis["expiration"]


def test_extended_patterns_bridge_into_observation_contract():
    pattern = PatternResult(
        pattern_type=data_patch.EdgePatternType.BEAR_FLAG,
        detected=True,
        confidence=0.8,
        strength=4.0,
        direction=EnhancedTrend.BEARISH,
        metadata={"timeframe": "1h"},
    )

    observation = analysis_patch.create_pattern_observation("SPY", [pattern])

    assert observation.metadata["edge_pattern_type"] == "BEAR_FLAG"
    assert observation.observation_period == "1h"
    assert observation.score_impact < 0
    assert 0.0 <= observation.strength <= 1.0


def test_non_edge_observations_remain_part_of_authoritative_signal():
    engine = DecisionEngine()
    engine.observations["SPY"].append(
        ExecutionObservation(
            symbol="SPY",
            source=ObservationSource.PULSE,
            observation_type="ORDER_REJECTED",
        )
    )

    assert runtime_patch._non_edge_observation_adjustment(engine, "SPY") < 0


def test_emergency_override_bypasses_low_signal_confidence():
    engine = DecisionEngine()
    engine.global_kill_switch = True
    context = {"analysis": _analysis(confidence=0.1), "supervisory_action": None}
    token = runtime_patch._BRAIN_CONTEXT.set(context)
    try:
        decision = runtime_patch._decide(
            engine,
            symbol="SPY",
            trend=DecisionTrend.NEUTRAL,
            signal_strength=0.0,
            confidence=0.1,
            current_drawdown=0.0,
            has_position=True,
            trailing_enabled=False,
        )
    finally:
        runtime_patch._BRAIN_CONTEXT.reset(token)

    assert decision == Decision.EMERGENCY_EXIT
