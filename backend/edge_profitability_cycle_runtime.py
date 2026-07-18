"""Runtime enforcement for two-phase, top-ranked portfolio entry cycles."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

from automation import AutomationAction
from edge_brain_analysis import build_trade_thesis
import edge_brain_runtime as brain_runtime
from edge_profitability import coordinator
import edge_profitability_runtime as profitability_runtime
from engine import Decision, DecisionEngine
from scheduler import EvaluationScheduler


logger = logging.getLogger(__name__)
_BASE_DECIDE = DecisionEngine.decide
_PRE_PROFITABILITY_DECIDE = profitability_runtime._ORIGINAL_DECIDE
_BASE_EVALUATE_ALL = EvaluationScheduler.evaluate_all
_INSTALLED = False


def _current_context() -> Dict[str, Any]:
    value = brain_runtime._BRAIN_CONTEXT.get()
    return value if isinstance(value, dict) else {}


def _cycle_decide(self: DecisionEngine, *args, **kwargs) -> Decision:
    context = _current_context()
    scheduler = context.get("scheduler")
    cycle_id = getattr(scheduler, "_edge_profitability_cycle_id", None) if scheduler is not None else None
    if not cycle_id:
        return _BASE_DECIDE(self, *args, **kwargs)

    decision = _PRE_PROFITABILITY_DECIDE(self, *args, **kwargs)
    analysis = context.get("analysis")
    if (
        args
        or analysis is None
        or bool(kwargs.get("has_position"))
        or not (getattr(analysis, "metadata", {}) or {}).get("enhanced_authoritative")
    ):
        return decision

    symbol = str(kwargs.get("symbol") or getattr(analysis, "symbol", "")).upper()
    try:
        thesis = build_trade_thesis(symbol, analysis, AutomationAction.BUY.value)
        target_bot = str((getattr(analysis, "metadata", {}) or {}).get("target_bot") or "") or None
        assessment, opportunity = coordinator.stage_cycle_candidate(
            cycle_id,
            analysis,
            thesis,
            base_decision=decision.value,
            target_bot=target_bot,
        )
        context["profitability_gate"] = {
            "allowed": False,
            "pending_portfolio_selection": decision == Decision.BUY,
            "cycle_id": cycle_id,
            "regime": assessment.public_dict(),
            "opportunity": opportunity.public_dict(),
            "trade_card": None,
        }
        context["opportunity"] = opportunity
        if decision == Decision.BUY:
            context["entry_deferred_for_portfolio_selection"] = True
            context["no_trade"] = False
            context["no_trade_reason"] = None
            logger.info(
                "Edge staged %s for portfolio cycle %s: score=%.2f ev=%.3f%% rr=%.2f",
                symbol,
                cycle_id,
                opportunity.score,
                opportunity.expected_value_pct,
                opportunity.reward_risk,
            )
            return Decision.HOLD
    except Exception:
        logger.exception("Could not stage %s in portfolio cycle %s", symbol, cycle_id)
        if decision == Decision.BUY:
            context["no_trade"] = True
            context["no_trade_reason"] = "portfolio_cycle_staging_error"
            return Decision.HOLD
    return decision


def _force_full_candidate_sweep(scheduler: EvaluationScheduler) -> tuple[Any, bool]:
    manager = getattr(scheduler, "ws_manager", None)
    if manager is None or os.getenv("EDGE_TOP_RANKED_FORCE_FULL_SWEEP", "true").lower() not in {"1", "true", "yes", "on"}:
        return None, False
    original = getattr(manager, "subscribed_symbols", None)
    manager.subscribed_symbols = set()
    return original, True


def _restore_subscriptions(scheduler: EvaluationScheduler, value: Any, changed: bool) -> None:
    if changed and getattr(scheduler, "ws_manager", None) is not None:
        scheduler.ws_manager.subscribed_symbols = value


async def _cycle_evaluate_all(self: EvaluationScheduler):
    if getattr(self, "paused", False):
        return await _BASE_EVALUATE_ALL(self)

    symbols = list(getattr(self, "active_tickers", []) or [])
    cycle_id = coordinator.begin_evaluation_cycle(symbols)
    self._edge_profitability_cycle_id = cycle_id
    previous_subscriptions, subscriptions_changed = _force_full_candidate_sweep(self)
    try:
        result = await _BASE_EVALUATE_ALL(self)
    finally:
        _restore_subscriptions(self, previous_subscriptions, subscriptions_changed)
        self._edge_profitability_cycle_id = None

    finalized = coordinator.finalize_evaluation_cycle(cycle_id)
    summary = finalized["summary"]
    self._edge_profitability_last_cycle = summary

    for symbol in summary.get("scored_symbols", []):
        latest = coordinator.latest_decisions.get(symbol) or {}
        ticker_state = self.ticker_state.get(symbol) or {}
        ticker_state.update(
            {
                "portfolio_cycle_id": cycle_id,
                "portfolio_selection_status": latest.get("selection_status"),
                "opportunity": latest.get("opportunity"),
                "no_trade": bool(latest.get("no_trade", False)),
                "no_trade_reason": latest.get("no_trade_reason"),
            }
        )
        self.ticker_state[symbol] = ticker_state

    if not finalized["selected"]:
        logger.info(
            "Edge portfolio cycle %s selected no entry from %d scored candidates",
            cycle_id,
            summary.get("candidate_count", 0),
        )
        return result

    winner = finalized["selected"][0]
    symbol = winner["symbol"]
    analysis = winner["analysis"]
    thesis = winner["thesis"]
    opportunity = winner["opportunity"]
    card = winner["card"]
    ticker_state = self.ticker_state.get(symbol) or {}
    current_price = float(ticker_state.get("current_price") or getattr(analysis, "price", 0.0) or 0.0)
    preflight_allowed, preflight_reason = coordinator.entry_preflight(card, current_price)
    if not preflight_allowed:
        latest = coordinator.latest_decisions.setdefault(symbol, {})
        latest.update(
            {
                "selection_status": "preflight_rejected",
                "no_trade": True,
                "no_trade_reason": preflight_reason,
                "trade_card": card.public_dict(),
            }
        )
        coordinator.record_cycle_handoff(
            cycle_id,
            symbol,
            {"sent": False, "status": "suppressed", "reason": preflight_reason},
        )
        logger.info("Edge rejected selected %s at entry preflight: %s", symbol, preflight_reason)
        return result

    compact_cycle = {
        "contract_version": summary.get("contract_version"),
        "cycle_id": cycle_id,
        "candidate_count": summary.get("candidate_count"),
        "eligible_before_selection": summary.get("eligible_before_selection"),
        "selected_symbols": summary.get("selected_symbols"),
        "settings": summary.get("settings"),
    }
    metadata = {
        "decision_id": f"{cycle_id}:{symbol}:buy",
        "portfolio_cycle": compact_cycle,
        "portfolio_rank": opportunity.rank,
        "portfolio_candidate_count": summary.get("candidate_count", 0),
        "selection_policy": "top_ranked_net_positive_non_correlated",
        "trade_thesis": thesis,
        "strategy": thesis.get("strategy"),
        "price": current_price,
        "signal_strength": getattr(analysis, "signal_strength", None),
        "trend": str(getattr(getattr(analysis, "trend", None), "name", "neutral")).lower(),
        "estimated_cost_pct": opportunity.estimated_cost_pct,
        "minimum_net_expected_value_pct": coordinator.minimum_net_expected_value_pct,
        "minimum_reward_risk": coordinator.experiment_minimum_reward_risk,
    }
    feedback = await self._handoff_to_pulse_with_feedback(
        symbol=symbol,
        action=AutomationAction.BUY,
        confidence=opportunity.calibrated_confidence,
        reason=(
            f"Top-ranked Edge opportunity ({opportunity.score:.2f}) after costs; "
            f"net EV={opportunity.expected_value_pct:.3f}% R:R={opportunity.reward_risk:.2f}"
        ),
        orb_session="portfolio_ranked",
        metadata=metadata,
    )
    feedback = feedback if isinstance(feedback, dict) else {
        "sent": bool(feedback),
        "status": "accepted" if feedback else "failed",
    }
    coordinator.record_cycle_handoff(cycle_id, symbol, feedback)
    accepted = profitability_runtime._feedback_sent(feedback)
    if not accepted:
        coordinator.release_unfilled_card(card, str(feedback.get("reason") or feedback.get("status") or "entry_not_accepted"))

    ticker_state.update(
        {
            "last_decision": Decision.BUY.value if accepted else Decision.HOLD.value,
            "portfolio_cycle_id": cycle_id,
            "portfolio_selection_status": "handoff_accepted" if accepted else "handoff_rejected",
            "handoff_sent": accepted,
            "handoff_status": feedback.get("status"),
            "handoff_reason": feedback.get("reason"),
            "trade_card": card.public_dict(),
        }
    )
    self.ticker_state[symbol] = ticker_state
    self.recent_decisions.insert(
        0,
        {
            "symbol": symbol,
            "decision": Decision.BUY.value if accepted else Decision.HOLD.value,
            "price": round(current_price, 4),
            "confidence": round(opportunity.calibrated_confidence, 4),
            "opportunity": opportunity.public_dict(),
            "trade_card": card.public_dict(),
            "portfolio_cycle_id": cycle_id,
            "portfolio_selection_status": "handoff_accepted" if accepted else "handoff_rejected",
            "handoff_sent": accepted,
            "handoff_status": feedback.get("status"),
            "handoff_reason": feedback.get("reason"),
            "pulse_feedback": feedback,
            "timestamp": summary.get("finalized_at"),
        },
    )
    self.recent_decisions = self.recent_decisions[:50]

    if accepted:
        try:
            self.position_tracker.on_decision(symbol, Decision.BUY, entry_price=current_price)
        except Exception:
            logger.debug("Could not record selected command for %s", symbol, exc_info=True)
        try:
            await self.correlation.record_signal(symbol, "BUY", opportunity.calibrated_confidence)
        except Exception:
            logger.debug("Could not record selected correlation signal for %s", symbol, exc_info=True)
        logger.info(
            "Edge portfolio cycle %s authorized only %s from %d candidates",
            cycle_id,
            symbol,
            summary.get("candidate_count", 0),
        )
    return result


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    DecisionEngine.decide = _cycle_decide
    # Preserve the public production-entrypoint identity used by existing wiring tests.
    profitability_runtime._profitability_decide = _cycle_decide
    EvaluationScheduler.evaluate_all = _cycle_evaluate_all
    EvaluationScheduler._edge_profitability_cycle_patch_installed = True
    _INSTALLED = True
    logger.info(
        "Edge top-ranked experiment installed: score-all sweep, one net-positive entry, hard correlation rejection"
    )
