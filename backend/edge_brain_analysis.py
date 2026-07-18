"""Authoritative analysis composition, observations, and trade theses."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Optional

import pandas as pd

from automation import AutomationAction
from shared.observations import (
    ObservationSource,
    PatternObservation,
    PatternType as ObservationPatternType,
)
from signals_enhanced import (
    AnalysisResult,
    ConfidenceScore,
    PatternResult,
    SignalEngineEnhanced,
    TrendDirection as EnhancedTrend,
)

from edge_brain_data import (
    EdgePatternType,
    clamp,
    detect_flag,
    frame_trend,
    market_structure,
    normalize_ohlcv,
    resample_ohlcv,
)

logger = logging.getLogger(__name__)


def augment_analysis(result: AnalysisResult, frames: Dict[str, pd.DataFrame]) -> AnalysisResult:
    weights = {"5m": 0.10, "15m": 0.20, "1h": 0.25, "4h": 0.20, "1d": 0.25}
    details: Dict[str, Any] = {}
    weighted_score = used_weight = 0.0
    for timeframe, weight in weights.items():
        score, indicators = frame_trend(frames.get(timeframe))
        if indicators:
            details[timeframe] = {"score": score, **indicators}
            weighted_score += score * weight
            used_weight += weight
    alignment = weighted_score / used_weight if used_weight else 0.0

    patterns = list(result.patterns)
    flags: list[PatternResult] = []
    for timeframe in ("15m", "1h", "4h", "1d"):
        detected = detect_flag(frames.get(timeframe), timeframe)
        if detected is not None:
            flags.append(detected)
    patterns.extend(flags)

    structure_frame = frames.get("15m")
    structure_timeframe = "15m"
    if structure_frame is None:
        structure_frame, structure_timeframe = frames.get("5m"), "5m"
    structure = market_structure(structure_frame, structure_timeframe)
    structure_direction = int(structure.get("direction") or 0)
    structure_confidence = float(structure.get("confidence") or 0.0)
    if structure_direction:
        patterns.append(
            PatternResult(
                pattern_type=(
                    EdgePatternType.RESISTANCE_BREAKOUT
                    if structure_direction > 0
                    else EdgePatternType.SUPPORT_BREAKDOWN
                ),
                detected=True,
                confidence=structure_confidence,
                strength=abs(float(structure.get("volume_ratio", 1.0))) * 10,
                direction=EnhancedTrend.BULLISH if structure_direction > 0 else EnhancedTrend.BEARISH,
                metadata=structure,
            )
        )

    flag_adjustment = sum(
        pattern.confidence * (2.0 if pattern.direction == EnhancedTrend.BULLISH else -2.0)
        for pattern in flags
    )
    signal = clamp(
        result.signal_strength
        + alignment * 2.5
        + structure_direction * structure_confidence * 2.0
        + flag_adjustment,
        -10.0,
        10.0,
    )
    confidence = replace(result.confidence)
    evidence = max(
        [structure_confidence, abs(alignment)]
        + [pattern.confidence for pattern in patterns]
        + [0.0]
    )
    confidence.overall = clamp(result.confidence.overall * 0.80 + evidence * 0.20, 0.0, 1.0)
    confidence.htf_confirmed = abs(alignment) >= 0.45
    confidence.htf_direction = (
        EnhancedTrend.BULLISH if alignment > 0.15 else
        EnhancedTrend.BEARISH if alignment < -0.15 else None
    )
    trend = result.trend
    if signal >= 2.0:
        trend = EnhancedTrend.BULLISH
    elif signal <= -2.0:
        trend = EnhancedTrend.BEARISH
    elif abs(alignment) < 0.15:
        trend = EnhancedTrend.NEUTRAL
    metadata = dict(result.metadata or {})
    metadata.update(
        {
            "brain_version": "edge-brain-v1",
            "enhanced_authoritative": True,
            "multi_timeframe_alignment": alignment,
            "multi_timeframe": details,
            "market_structure": structure,
        }
    )
    return replace(
        result,
        signal_strength=signal,
        trend=trend,
        confidence=confidence,
        patterns=patterns,
        metadata=metadata,
    )


def neutral_analysis(
    symbol: str,
    frame: Optional[pd.DataFrame],
    timeframe: str,
    error: Exception,
) -> AnalysisResult:
    frame = normalize_ohlcv(frame)
    price = float(frame["close"].iloc[-1]) if frame is not None else 0.0
    volume = float(frame["volume"].iloc[-1]) if frame is not None else 0.0
    return AnalysisResult(
        symbol=symbol.upper(),
        timestamp=datetime.utcnow(),
        signal_strength=0.0,
        trend=EnhancedTrend.NEUTRAL,
        confidence=ConfidenceScore(overall=0.0),
        patterns=[],
        price=price,
        volume=volume,
        metadata={
            "timeframe": timeframe,
            "brain_version": "edge-brain-v1",
            "enhanced_authoritative": False,
            "analysis_error": str(error),
            "fallback": "neutral_hold",
        },
    )


async def run_analysis(
    original_analyze,
    engine: SignalEngineEnhanced,
    symbol: str,
    price_data: pd.DataFrame,
    timeframe: str,
    higher_tf_data: Optional[pd.DataFrame],
    context: Optional[Dict[str, Any]],
) -> AnalysisResult:
    frame = normalize_ohlcv(price_data)
    frames: Dict[str, pd.DataFrame] = {}
    if frame is not None:
        frames["1m"] = frame
        for label, rule in (("5m", "5min"), ("15m", "15min"), ("1h", "1h")):
            resampled = resample_ohlcv(frame, rule)
            if resampled is not None:
                frames[label] = resampled
    if context:
        frames.update(context.get("multi_frames") or {})
    normalized_higher = normalize_ohlcv(higher_tf_data)
    if normalized_higher is None:
        for candidate in ("1d", "4h", "1h"):
            normalized_higher = frames.get(candidate)
            if normalized_higher is not None:
                break
    try:
        if frame is None:
            raise ValueError("OHLCV is missing open/high/low/close/volume")
        analysis_frame = frames.get(timeframe)
        if analysis_frame is None:
            analysis_frame = frame
        result = await original_analyze(
            engine,
            symbol,
            analysis_frame,
            timeframe=timeframe,
            higher_tf_data=normalized_higher,
        )
        return augment_analysis(result, frames)
    except Exception as exc:
        logger.warning("Enhanced analysis failed for %s; forcing neutral hold: %s", symbol, exc)
        return neutral_analysis(symbol, frame, timeframe, exc)


def pattern_value(pattern: PatternResult) -> str:
    return str(getattr(pattern.pattern_type, "value", pattern.pattern_type))


def create_pattern_observation(
    symbol: str,
    pattern_results: list[PatternResult],
    source: str = "EDGE_PATTERNS",
) -> PatternObservation:
    """Bridge chart patterns into the legacy validated observation contract."""
    if not pattern_results:
        raise ValueError("No patterns to convert")
    strongest = max(pattern_results, key=lambda pattern: float(pattern.confidence))
    raw_pattern = pattern_value(strongest)
    try:
        observation_pattern = ObservationPatternType(raw_pattern)
    except ValueError:
        observation_pattern = ObservationPatternType.MA_CROSS
    raw_strength = abs(float(strongest.strength or 0.0))
    strength = raw_strength if raw_strength <= 1.0 else raw_strength / 100.0
    direction = getattr(strongest.direction, "name", "NEUTRAL")
    impact = float(strongest.confidence) * clamp(strength, 0.0, 1.0)
    if direction == "BEARISH":
        impact *= -1.0
    elif direction != "BULLISH":
        impact = 0.0
    return PatternObservation(
        symbol=symbol,
        source=ObservationSource.EDGE,
        pattern_type=observation_pattern,
        confidence=clamp(float(strongest.confidence), 0.0, 1.0),
        strength=clamp(strength, 0.0, 1.0),
        score_impact=clamp(impact, -1.0, 1.0),
        observation_period=str((strongest.metadata or {}).get("timeframe") or "15m"),
        metadata={
            **dict(strongest.metadata or {}),
            "edge_pattern_type": raw_pattern,
            "reported_source": source,
        },
    )


def build_trade_thesis(symbol: str, analysis: AnalysisResult, action: str) -> Dict[str, Any]:
    metadata = analysis.metadata or {}
    indicators = metadata.get("indicators") or {}
    structure = metadata.get("market_structure") or {}
    patterns = [pattern_value(pattern) for pattern in analysis.patterns if pattern.detected]
    flag = next((name for name in patterns if name in {"BULL_FLAG", "BEAR_FLAG"}), None)
    if structure.get("state") == "resistance_breakout":
        strategy = "breakout"
    elif structure.get("state") == "support_breakdown":
        strategy = "breakdown"
    elif flag:
        strategy = "continuation"
    elif any("HEAD_SHOULDERS" in name for name in patterns):
        strategy = "reversal"
    else:
        strategy = "multi_timeframe_trend"
    price = float(analysis.price or 0.0)
    atr = float(indicators.get("atr_current") or 0.0)
    support, resistance = structure.get("support"), structure.get("resistance")
    risk_unit = atr if atr > 0 else max(price * 0.015, 0.01)
    bullish = analysis.trend == EnhancedTrend.BULLISH
    stop = None
    targets: list[float] = []
    if action == AutomationAction.BUY.value and price > 0:
        stop = float(support) if support and float(support) < price else price - 1.5 * risk_unit
        stop = round(max(0.01, stop), 4)
        risk = max(price - stop, risk_unit)
        targets = [round(price + risk * 2, 4), round(price + risk * 3, 4)]
    dominant_timeframe = "multi_timeframe"
    for pattern in analysis.patterns:
        if (pattern.metadata or {}).get("timeframe"):
            dominant_timeframe = str(pattern.metadata["timeframe"])
            break
    expiry = datetime.now(timezone.utc) + (
        timedelta(days=1) if dominant_timeframe == "1d" else timedelta(minutes=45)
    )
    rationale = [
        f"enhanced trend={analysis.trend.name.lower()}",
        f"signal={analysis.signal_strength:.2f}",
        f"MTF alignment={float(metadata.get('multi_timeframe_alignment') or 0.0):.2f}",
    ]
    if patterns:
        rationale.append("patterns=" + ",".join(patterns[:5]))
    if structure.get("state"):
        rationale.append("structure=" + str(structure["state"]))
    return {
        "strategy": strategy,
        "timeframe": dominant_timeframe,
        "entry": round(price, 4) if price > 0 else None,
        "entry_trigger": (
            round(float(resistance), 4) if bullish and resistance else
            round(float(support), 4) if support else None
        ),
        "stop": stop,
        "targets": targets,
        "confidence": round(float(analysis.confidence.overall), 4),
        "expiration": expiry.isoformat(),
        "invalidation": (
            f"close below {float(support):.4f}" if bullish and support else
            f"close above {float(resistance):.4f}" if resistance else
            "enhanced trend or market structure reverses"
        ),
        "patterns": patterns,
        "rationale": rationale,
        "source": "edge_brain_v1",
        "symbol": symbol.upper(),
    }
