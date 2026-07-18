"""Runtime wiring for Edge's portfolio strategy coordinator."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from automation import AutomationAction
from edge_brain_analysis import build_trade_thesis
import edge_brain_runtime as brain_runtime
from edge_profitability import coordinator
from engine import Decision, DecisionEngine
from scheduler import EvaluationScheduler


logger = logging.getLogger(__name__)
_ORIGINAL_DECIDE = DecisionEngine.decide
_ORIGINAL_HANDOFF = EvaluationScheduler._handoff_to_pulse_with_feedback
_ORIGINAL_EVALUATE = EvaluationScheduler.evaluate_ticker
_INSTALLED = False


def _action_value(action: Any) -> str:
    return str(getattr(action, "value", action) or "").lower()


def _feedback_sent(feedback: Any) -> bool:
    if not isinstance(feedback, dict):
        return bool(feedback)
    status = str(feedback.get("status") or "").lower()
    return bool(
        feedback.get("sent")
        or feedback.get("accepted")
        or feedback.get("ambiguous_delivery")
        or feedback.get("reconciliation_required")
        or status in {"accepted", "processing", "pending", "broker_reconciliation_pending"}
    )


def _current_context() -> Dict[str, Any]:
    value = brain_runtime._BRAIN_CONTEXT.get()
    return value if isinstance(value, dict) else {}


def _profitability_decide(self: DecisionEngine, *args, **kwargs) -> Decision:
    decision = _ORIGINAL_DECIDE(self, *args, **kwargs)
    context = _current_context()
    analysis = context.get("analysis")
    if args or analysis is None or not (getattr(analysis, "metadata", {}) or {}).get("enhanced_authoritative"):
        return decision

    symbol = str(kwargs.get("symbol") or getattr(analysis, "symbol", "")).upper()
    has_position = bool(kwargs.get("has_position"))

    if decision != Decision.BUY or has_position:
        try:
            assessment = coordinator.classify_regime(analysis)
            latest = coordinator.latest_decisions.setdefault(symbol, {})
            latest.update(
                {
                    "updated_at": str(getattr(analysis, "timestamp", None) or ""),
                    "regime": assessment.public_dict(),
                }
            )
            if not has_position and decision == Decision.HOLD and not assessment.trade_allowed:
                latest.update({"no_trade": True, "no_trade_reason": assessment.reason})
        except Exception:
            logger.debug("Could not update portfolio regime for %s", symbol, exc_info=True)
        return decision

    try:
        thesis = build_trade_thesis(symbol, analysis, AutomationAction.BUY.value)
        target_bot = str((getattr(analysis, "metadata", {}) or {}).get("target_bot") or "") or None
        allowed, assessment, opportunity, card = coordinator.evaluate_entry(analysis, thesis, target_bot)
        context["profitability_gate"] = {
            "allowed": allowed,
            "regime": assessment.public_dict(),
            "opportunity": opportunity.public_dict(),
            "trade_card": card.public_dict() if card else None,
        }
        context["trade_card"] = card
        context["opportunity"] = opportunity
        if not allowed:
            context["no_trade"] = True
            context["no_trade_reason"] = opportunity.reasons[0] if opportunity.reasons else assessment.reason
            logger.info(
                "Edge NO_TRADE %s: %s score=%.2f rank=%s",
                symbol,
                context["no_trade_reason"],
                opportunity.score,
                opportunity.rank,
            )
            return Decision.HOLD
        logger.info(
            "Edge authorized %s for %s: score=%.2f rank=%s risk=%.2f%% card=%s",
            symbol,
            opportunity.target_bot,
            opportunity.score,
            opportunity.rank,
            opportunity.risk_budget_pct,
            card.card_id if card else "none",
        )
    except Exception:
        logger.exception("Portfolio entry gate failed for %s; forcing NO_TRADE", symbol)
        context["no_trade"] = True
        context["no_trade_reason"] = "profitability_gate_error"
        return Decision.HOLD
    return decision


async def _profitability_handoff(
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
    action_value = _action_value(action)
    symbol = symbol.upper()
    context = _current_context()
    analysis = context.get("analysis")
    merged = dict(metadata or {})
    card = context.get("trade_card") or coordinator.active_card(symbol)

    if action_value == AutomationAction.BUY.value and card is None and analysis is not None:
        try:
            thesis = build_trade_thesis(symbol, analysis, action_value)
            allowed, assessment, opportunity, card = coordinator.evaluate_entry(analysis, thesis)
            context["profitability_gate"] = {
                "allowed": allowed,
                "regime": assessment.public_dict(),
                "opportunity": opportunity.public_dict(),
                "trade_card": card.public_dict() if card else None,
            }
            context["trade_card"] = card
            if not allowed:
                gate_reason = opportunity.reasons[0] if opportunity.reasons else assessment.reason
                context["no_trade"] = True
                context["no_trade_reason"] = gate_reason
                return {
                    "sent": False,
                    "accepted": False,
                    "status": "suppressed",
                    "reason": f"profitability_no_trade:{gate_reason}",
                    "symbol": symbol,
                    "action": action_value,
                    "profitability_gate": context["profitability_gate"],
                }
        except Exception:
            logger.exception("Portfolio handoff gate failed for %s", symbol)
            return {
                "sent": False,
                "accepted": False,
                "status": "suppressed",
                "reason": "profitability_gate_error",
                "symbol": symbol,
                "action": action_value,
            }

    if card is not None:
        merged = coordinator.attach_to_metadata(merged, card, action=action_value)
        if action_value in {AutomationAction.SELL.value, AutomationAction.EMERGENCY_EXIT.value}:
            merged["invalidate_position_scoped_stop"] = True
        if action_value == AutomationAction.TIGHTEN_STOP.value:
            merged.setdefault("supervisory_directive", "set_stop")
            merged.setdefault("expected_position_quantity", card.position_quantity or None)

    feedback = await _ORIGINAL_HANDOFF(
        self,
        symbol=symbol,
        action=action,
        confidence=confidence,
        reason=reason,
        orb_session=orb_session,
        stop_type=stop_type,
        trailing_percent=trailing_percent,
        dca=dca,
        metadata=merged,
    )
    coordinator.record_feedback(card, action=action_value, feedback=feedback, metadata=merged)
    if card is not None and _feedback_sent(feedback):
        context["trade_card"] = card
    return feedback


async def _profitability_evaluate(self: EvaluationScheduler, symbol: str, *args, **kwargs):
    result = await _ORIGINAL_EVALUATE(self, symbol, *args, **kwargs)
    symbol = symbol.upper()
    try:
        position = self.decisions.get_position(symbol) if hasattr(self.decisions, "get_position") else None
        ticker_state = self.ticker_state.get(symbol) or {}
        price = float(ticker_state.get("current_price") or 0.0)
        coordinator.observe_position(symbol, position, current_price=price)
        status = coordinator.symbol_status(symbol)
        ticker_state.update(
            {
                "market_regime": (status.get("regime") or {}).get("regime"),
                "regime_assessment": status.get("regime"),
                "no_trade": bool(status.get("no_trade", False)),
                "no_trade_reason": status.get("no_trade_reason"),
                "opportunity": status.get("opportunity"),
                "trade_card": status.get("trade_card"),
                "portfolio_strategy": status.get("portfolio"),
            }
        )
        self.ticker_state[symbol] = ticker_state
        for item in self.recent_decisions:
            if str(item.get("symbol") or "").upper() == symbol:
                item.update(
                    {
                        "market_regime": (status.get("regime") or {}).get("regime"),
                        "no_trade": bool(status.get("no_trade", False)),
                        "no_trade_reason": status.get("no_trade_reason"),
                        "opportunity": status.get("opportunity"),
                        "trade_card": status.get("trade_card"),
                    }
                )
                break
    except Exception:
        logger.debug("Could not publish portfolio strategy state for %s", symbol, exc_info=True)
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    DecisionEngine.decide = _profitability_decide
    EvaluationScheduler._handoff_to_pulse_with_feedback = _profitability_handoff
    EvaluationScheduler.evaluate_ticker = _profitability_evaluate
    EvaluationScheduler._edge_profitability_patch_installed = True
    _INSTALLED = True
    logger.info(
        "Edge portfolio coordinator installed: regime gate, NO_TRADE, ranked risk, trade cards, feedback learning"
    )
