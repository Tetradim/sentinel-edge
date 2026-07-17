"""Runtime wiring that makes enhanced Edge analysis authoritative."""
from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime
import logging
from typing import Any, Dict, Optional

from automation import AutomationAction
from engine import Decision, DecisionEngine
from metrics import edge_decision_total
from scheduler import EvaluationScheduler
from signals import TrendDirection as DecisionTrend
import signals_enhanced as enhanced_module
import shared.observations as observation_module
from signals_enhanced import AnalysisResult, SignalEngineEnhanced, TechnicalIndicators, TrendDirection as EnhancedTrend

from edge_brain_analysis import (
    build_trade_thesis,
    create_pattern_observation,
    run_analysis,
)
from edge_brain_data import (
    clamp,
    configure_engine,
    env_float,
    load_longer_timeframes,
    safe_compute_atr,
)

logger = logging.getLogger(__name__)
_BRAIN_CONTEXT: ContextVar[Optional[Dict[str, Any]]] = ContextVar("edge_brain_context", default=None)

_ORIGINAL_ENGINE_INIT = SignalEngineEnhanced.__init__
_ORIGINAL_ANALYZE = SignalEngineEnhanced.analyze
_ORIGINAL_DECIDE = DecisionEngine.decide
_ORIGINAL_EVALUATE = EvaluationScheduler.evaluate_ticker
_ORIGINAL_HANDOFF = EvaluationScheduler._handoff_to_pulse_with_feedback


def _engine_init(self: SignalEngineEnhanced, *args, **kwargs) -> None:
    args = list(args)
    if len(args) >= 2:
        args[1] = True
    else:
        kwargs["multi_timeframe"] = True
    _ORIGINAL_ENGINE_INIT(self, *args, **kwargs)
    configure_engine(self)


async def _analyze(
    self: SignalEngineEnhanced,
    symbol: str,
    price_data,
    timeframe: str = "1m",
    higher_tf_data=None,
) -> AnalysisResult:
    context = _BRAIN_CONTEXT.get()
    result = await run_analysis(
        _ORIGINAL_ANALYZE,
        self,
        symbol,
        price_data,
        timeframe,
        higher_tf_data,
        context,
    )
    if context is not None:
        context["analysis"] = result
        scheduler = context.get("scheduler")
        if scheduler is not None:
            state = getattr(scheduler, "_edge_brain_state", None)
            if state is None:
                state = {}
                scheduler._edge_brain_state = state
            state[symbol.upper()] = result
    return result


def _decision_trend(trend: EnhancedTrend) -> DecisionTrend:
    return DecisionTrend[trend.name]


def _decide(self: DecisionEngine, *args, **kwargs) -> Decision:
    context = _BRAIN_CONTEXT.get()
    analysis: Optional[AnalysisResult] = context.get("analysis") if context else None
    if args or analysis is None or not analysis.metadata.get("enhanced_authoritative"):
        return _ORIGINAL_DECIDE(self, *args, **kwargs)
    kwargs = dict(kwargs)
    kwargs["trend"] = _decision_trend(analysis.trend)
    kwargs["signal_strength"] = float(analysis.signal_strength)
    kwargs["confidence"] = float(analysis.confidence.overall)
    symbol = str(kwargs.get("symbol") or analysis.symbol).upper()
    max_losses = int(kwargs.get("max_consecutive_losses") or self.MAX_CONSECUTIVE_LOSSES)
    max_drawdown = float(kwargs.get("max_drawdown_pct") or self.MAX_DRAWDOWN_PCT)
    emergency = (
        self.global_kill_switch
        or self.consecutive_losses.get(symbol, 0) >= max_losses
        or float(kwargs.get("current_drawdown") or 0.0) > max_drawdown
    )
    confirmed_bearish = (
        bool(kwargs.get("has_position"))
        and analysis.trend == EnhancedTrend.BEARISH
        and analysis.signal_strength <= -abs(env_float("EDGE_BRAIN_SELL_SIGNAL_THRESHOLD", 3.5, minimum=0.5))
        and analysis.confidence.overall >= env_float("EDGE_BRAIN_SELL_MIN_CONFIDENCE", 0.65, minimum=0.0)
    )
    if confirmed_bearish and not emergency:
        context["supervisory_action"] = "sell"
        context["supervisory_reason"] = (
            "Enhanced bearish thesis invalidated the position "
            f"(signal={analysis.signal_strength:.2f}, confidence={analysis.confidence.overall:.2f})"
        )
        edge_decision_total.labels(symbol=symbol, decision=Decision.SELL.value).inc()
        return Decision.HOLD
    return _ORIGINAL_DECIDE(self, **kwargs)


async def _handoff(
    self: EvaluationScheduler,
    symbol: str,
    action,
    confidence: float,
    reason: str,
    orb_session: str = "market_open",
    stop_type: Optional[str] = None,
    trailing_percent: Optional[float] = None,
    dca: Optional[Dict] = None,
    metadata: Optional[Dict] = None,
) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    analysis = getattr(self, "_edge_brain_state", {}).get(symbol.upper())
    if analysis is not None:
        action_value = str(getattr(action, "value", action)).lower()
        thesis = build_trade_thesis(symbol, analysis, action_value)
        confidence = float(analysis.confidence.overall)
        if action_value in {AutomationAction.BUY.value, AutomationAction.SELL.value}:
            reason = f"Edge {thesis['strategy']} thesis: " + "; ".join(thesis["rationale"][:3])
        metadata.update(
            {
                "trade_thesis": thesis,
                "strategy": thesis["strategy"],
                "enhanced_signal_strength": analysis.signal_strength,
                "enhanced_trend": analysis.trend.name.lower(),
                "enhanced_confidence": analysis.confidence.overall,
                "market_structure": analysis.metadata.get("market_structure"),
                "multi_timeframe_alignment": analysis.metadata.get("multi_timeframe_alignment"),
            }
        )
    return await _ORIGINAL_HANDOFF(
        self,
        symbol=symbol,
        action=action,
        confidence=confidence,
        reason=reason,
        orb_session=orb_session,
        stop_type=stop_type,
        trailing_percent=trailing_percent,
        dca=dca,
        metadata=metadata,
    )


def _publish_analysis_state(scheduler: EvaluationScheduler, symbol: str, analysis: AnalysisResult) -> None:
    ticker_state = scheduler.ticker_state.get(symbol.upper())
    update = {
        "signal_strength": round(analysis.signal_strength, 2),
        "trend": analysis.trend.name.lower(),
        "confidence": round(float(analysis.confidence.overall), 3),
        "market_structure": analysis.metadata.get("market_structure"),
        "multi_timeframe_alignment": analysis.metadata.get("multi_timeframe_alignment"),
        "enhanced_authoritative": True,
    }
    if ticker_state is not None:
        ticker_state.update(update)
    for item in scheduler.recent_decisions:
        if item.get("symbol") == symbol.upper():
            item.update(update)
            break


async def _emit_supervisory_sell(
    scheduler: EvaluationScheduler,
    symbol: str,
    analysis: AnalysisResult,
    reason: str,
) -> None:
    confidence = clamp(float(analysis.confidence.overall), 0.0, 1.0)
    feedback = await scheduler._handoff_to_pulse_with_feedback(
        symbol=symbol,
        action=AutomationAction.SELL,
        confidence=confidence,
        reason=reason,
        orb_session="market_open",
        metadata={
            "price": analysis.price,
            "signal_strength": analysis.signal_strength,
            "trend": analysis.trend.name.lower(),
            "supervisory_override": True,
            "directive": "sell_immediately",
        },
    )
    sent = bool(feedback.get("sent") or feedback.get("accepted")) if isinstance(feedback, dict) else False
    if sent:
        scheduler.position_tracker.on_decision(symbol, Decision.SELL, entry_price=analysis.price)
    if hasattr(scheduler, "correlation"):
        try:
            await scheduler.correlation.record_signal(symbol, "SELL", confidence)
        except Exception:
            logger.debug("Correlation recording failed for supervisory SELL", exc_info=True)
    scheduler.recent_decisions.insert(
        0,
        {
            "symbol": symbol.upper(),
            "decision": Decision.SELL.value,
            "signal_strength": round(analysis.signal_strength, 2),
            "trend": analysis.trend.name.lower(),
            "confidence": round(confidence, 3),
            "price": round(float(analysis.price or 0.0), 4),
            "has_position": True,
            "handoff_sent": sent,
            "handoff_status": feedback.get("status") if isinstance(feedback, dict) else None,
            "handoff_reason": feedback.get("reason") if isinstance(feedback, dict) else None,
            "pulse_feedback": feedback,
            "supervisory_override": True,
            "timestamp": datetime.now().isoformat(),
        },
    )
    scheduler.recent_decisions = scheduler.recent_decisions[:50]
    ticker_state = scheduler.ticker_state.get(symbol.upper())
    if ticker_state is not None:
        ticker_state.update(
            {
                "last_decision": Decision.SELL.value,
                "supervisory_override": True,
                "pulse_feedback": feedback,
            }
        )


async def _evaluate(self: EvaluationScheduler, symbol: str, *args, **kwargs):
    context: Dict[str, Any] = {
        "scheduler": self,
        "symbol": symbol.upper(),
        "analysis": None,
        "multi_frames": {},
        "supervisory_action": None,
    }
    token = _BRAIN_CONTEXT.set(context)
    try:
        context["multi_frames"] = await load_longer_timeframes(symbol)
        result = await _ORIGINAL_EVALUATE(self, symbol, *args, **kwargs)
        analysis: Optional[AnalysisResult] = context.get("analysis")
        if analysis is not None and analysis.metadata.get("enhanced_authoritative"):
            _publish_analysis_state(self, symbol, analysis)
        if context.get("supervisory_action") == "sell" and analysis is not None:
            await _emit_supervisory_sell(
                self,
                symbol,
                analysis,
                str(context.get("supervisory_reason") or "Enhanced bearish thesis invalidated position"),
            )
        return result
    finally:
        _BRAIN_CONTEXT.reset(token)


def install() -> None:
    """Install after live_scheduler_patch so its safety wrappers remain inner-most."""
    if getattr(EvaluationScheduler, "_edge_brain_patch_installed", False):
        return
    TechnicalIndicators.compute_atr = staticmethod(safe_compute_atr)
    observation_module.create_pattern_observation = create_pattern_observation
    SignalEngineEnhanced.__init__ = _engine_init
    SignalEngineEnhanced.analyze = _analyze
    DecisionEngine.decide = _decide
    EvaluationScheduler._handoff_to_pulse_with_feedback = _handoff
    EvaluationScheduler.evaluate_ticker = _evaluate
    EvaluationScheduler._edge_brain_patch_installed = True
    existing = getattr(enhanced_module, "_signal_engine", None)
    if existing is not None:
        configure_engine(existing)
    logger.info("Edge strategist brain installed: MTF, structure, flags, theses, SELL override")
