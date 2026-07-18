"""Two-phase portfolio evaluation cycles for profitability experiments."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Iterable, Optional

from edge_profitability_models import (
    OpportunityScore,
    TradeCard,
    TradeCardState,
    env_float,
    env_int,
    finite,
    infer_target_bot,
    iso_now,
)


_DEFAULT_CORRELATION_GROUPS: Dict[str, set[str]] = {
    "us_growth_beta": {
        "SPY", "QQQ", "AAPL", "NVDA", "MSFT", "AMZN", "META", "GOOG", "GOOGL", "TSLA", "AVGO", "AMD"
    },
    "semiconductors": {"NVDA", "AMD", "AVGO", "INTC", "MU", "SNDK", "QCOM", "ARM"},
}
_TRANSIENT_RANK_REASONS = {"outside_ranked_entry_slots"}


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


class ProfitabilityCycleMixin:
    """Collect all candidates before selecting the portfolio winner."""

    def _init_cycle_state(self) -> None:
        self._evaluation_cycles: Dict[str, Dict[str, Any]] = {}

    @property
    def minimum_net_expected_value_pct(self) -> float:
        return env_float("EDGE_MIN_NET_EXPECTED_VALUE_PCT", 0.15, minimum=0.0)

    @property
    def experiment_minimum_reward_risk(self) -> float:
        return env_float("EDGE_EXPERIMENT_MIN_REWARD_RISK", 2.0, minimum=0.1)

    @property
    def maximum_cycle_entries(self) -> int:
        return env_int("EDGE_MAX_CYCLE_ENTRIES", 1, minimum=1)

    def experiment_settings(self) -> Dict[str, Any]:
        return {
            "experiment": "top_ranked_net_positive_candidate",
            "score_all_candidates": True,
            "maximum_cycle_entries": self.maximum_cycle_entries,
            "minimum_net_expected_value_pct": self.minimum_net_expected_value_pct,
            "minimum_reward_risk": self.experiment_minimum_reward_risk,
            "hard_correlated_substitute_rejection": True,
        }

    def _configured_correlation_groups(self) -> Dict[str, set[str]]:
        groups = {name: set(symbols) for name, symbols in _DEFAULT_CORRELATION_GROUPS.items()}
        raw = os.getenv("EDGE_CORRELATED_SUBSTITUTE_GROUPS_JSON", "").strip()
        if not raw:
            return groups
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return groups
        if not isinstance(payload, dict):
            return groups
        for name, symbols in payload.items():
            if isinstance(symbols, list):
                groups[str(name)] = {str(symbol).upper() for symbol in symbols if str(symbol).strip()}
        return groups

    def correlation_groups(self, symbol: str, target_bot: str = "") -> set[str]:
        normalized = str(symbol or "").upper()
        groups = {
            name for name, symbols in self._configured_correlation_groups().items()
            if normalized in symbols
        }
        bot = str(target_bot or "").lower()
        if "chain" in bot or normalized.endswith(("-USD", "/USD", "USDT")):
            groups.add("crypto_beta")
        elif "iron" in bot or normalized.endswith("=F"):
            groups.add("futures_beta")
        return groups

    def begin_evaluation_cycle(
        self,
        symbols: Iterable[str],
        *,
        cycle_id: Optional[str] = None,
    ) -> str:
        if not hasattr(self, "_evaluation_cycles"):
            self._init_cycle_state()
        normalized = sorted({str(symbol).upper() for symbol in symbols if str(symbol).strip()})
        cycle_id = cycle_id or f"edge-cycle:{int(time.time() * 1000)}"
        self._evaluation_cycles[cycle_id] = {
            "cycle_id": cycle_id,
            "started_at": iso_now(),
            "expected_symbols": normalized,
            "candidates": {},
        }
        return cycle_id

    def stage_cycle_candidate(
        self,
        cycle_id: str,
        analysis: Any,
        thesis: Dict[str, Any],
        *,
        base_decision: str,
        target_bot: Optional[str] = None,
    ) -> tuple[Any, OpportunityScore]:
        if not hasattr(self, "_evaluation_cycles"):
            self._init_cycle_state()
        cycle = self._evaluation_cycles.setdefault(
            cycle_id,
            {"cycle_id": cycle_id, "started_at": iso_now(), "expected_symbols": [], "candidates": {}},
        )
        symbol = str(getattr(analysis, "symbol", None) or thesis.get("symbol") or "").upper()
        target_bot = target_bot or infer_target_bot(symbol, getattr(analysis, "metadata", None))
        assessment, opportunity = self.score_opportunity(analysis, thesis, target_bot)
        reasons = [reason for reason in opportunity.reasons if reason not in _TRANSIENT_RANK_REASONS]
        if opportunity.expected_value_pct < self.minimum_net_expected_value_pct:
            reasons.append("expected_value_below_net_threshold")
        if opportunity.reward_risk < self.experiment_minimum_reward_risk:
            reasons.append("experiment_reward_risk_below_2r")
        if str(base_decision).lower() != "buy":
            reasons.append("base_decision_not_buy")
        if self.active_card(symbol) is not None:
            reasons.append("active_trade_card_exists")
        opportunity.reasons = _unique(reasons)
        opportunity.eligible = not opportunity.reasons

        cycle["candidates"][symbol] = {
            "symbol": symbol,
            "target_bot": target_bot,
            "base_decision": str(base_decision).lower(),
            "analysis": analysis,
            "thesis": dict(thesis),
            "assessment": assessment,
            "opportunity": opportunity,
            "staged_at": iso_now(),
        }
        self.latest_decisions[symbol] = {
            "updated_at": iso_now(),
            "regime": assessment.public_dict(),
            "opportunity": opportunity.public_dict(),
            "portfolio_cycle_id": cycle_id,
            "selection_status": "staged",
            "no_trade": not opportunity.eligible,
            "no_trade_reason": opportunity.reasons[0] if opportunity.reasons else None,
        }
        self._save()
        return assessment, opportunity

    def _active_correlation_conflicts(self, symbol: str, target_bot: str) -> list[str]:
        groups = self.correlation_groups(symbol, target_bot)
        if not groups:
            return []
        conflicts: list[str] = []
        for card in self._active_cards():
            if card.symbol == symbol.upper():
                continue
            if groups.intersection(self.correlation_groups(card.symbol, card.target_bot)):
                conflicts.append(card.symbol)
        return sorted(set(conflicts))

    def finalize_evaluation_cycle(self, cycle_id: str) -> Dict[str, Any]:
        if not hasattr(self, "_evaluation_cycles"):
            self._init_cycle_state()
        cycle = self._evaluation_cycles.pop(cycle_id, None) or {
            "cycle_id": cycle_id,
            "started_at": iso_now(),
            "expected_symbols": [],
            "candidates": {},
        }
        ordered = sorted(
            cycle["candidates"].values(),
            key=lambda item: finite(item["opportunity"].score),
            reverse=True,
        )
        selected: list[Dict[str, Any]] = []
        selection_groups: set[str] = set()
        eligible_before_selection = 0

        for rank, candidate in enumerate(ordered, start=1):
            opportunity: OpportunityScore = candidate["opportunity"]
            opportunity.rank = rank
            reasons = [reason for reason in opportunity.reasons if reason not in _TRANSIENT_RANK_REASONS]
            conflicts = self._active_correlation_conflicts(candidate["symbol"], candidate["target_bot"])
            if conflicts:
                reasons.append("correlated_active_exposure:" + ",".join(conflicts))
            reasons = _unique(reasons)
            candidate_groups = self.correlation_groups(candidate["symbol"], candidate["target_bot"])
            initially_eligible = not reasons
            if initially_eligible:
                eligible_before_selection += 1

            if initially_eligible and len(selected) < self.maximum_cycle_entries and not selection_groups.intersection(candidate_groups):
                opportunity.eligible = True
                opportunity.reasons = []
                card = self.create_trade_card(candidate["analysis"], candidate["thesis"], opportunity)
                candidate["card"] = card
                candidate["selection_status"] = "selected"
                selected.append(candidate)
                selection_groups.update(candidate_groups)
            else:
                if initially_eligible:
                    if selection_groups.intersection(candidate_groups):
                        winner = selected[0]["symbol"] if selected else "active_portfolio"
                        reasons.append(f"correlated_substitute_of:{winner}")
                    else:
                        reasons.append("not_top_ranked_opportunity")
                opportunity.eligible = False
                opportunity.reasons = _unique(reasons)
                candidate["selection_status"] = "rejected"

            self.latest_decisions[candidate["symbol"]] = {
                "updated_at": iso_now(),
                "regime": candidate["assessment"].public_dict(),
                "opportunity": opportunity.public_dict(),
                "portfolio_cycle_id": cycle_id,
                "selection_status": candidate["selection_status"],
                "no_trade": not opportunity.eligible,
                "no_trade_reason": opportunity.reasons[0] if opportunity.reasons else None,
                "trade_card": candidate.get("card").public_dict() if candidate.get("card") else None,
            }

        summary = {
            "contract_version": "edge.evaluation_cycle.v1",
            "cycle_id": cycle_id,
            "started_at": cycle.get("started_at"),
            "finalized_at": iso_now(),
            "expected_symbols": cycle.get("expected_symbols", []),
            "scored_symbols": [candidate["symbol"] for candidate in ordered],
            "candidate_count": len(ordered),
            "eligible_before_selection": eligible_before_selection,
            "selected_symbols": [candidate["symbol"] for candidate in selected],
            "settings": self.experiment_settings(),
            "candidates": [
                {
                    "symbol": candidate["symbol"],
                    "target_bot": candidate["target_bot"],
                    "base_decision": candidate["base_decision"],
                    "selection_status": candidate["selection_status"],
                    "opportunity": candidate["opportunity"].public_dict(),
                }
                for candidate in ordered
            ],
        }
        previous = dict(self.latest_decisions.get("__PORTFOLIO_CYCLE__") or {})
        history = list(previous.get("history") or [])[-99:]
        history.append({key: value for key, value in summary.items() if key != "candidates"})
        summary["history"] = history
        self.latest_decisions["__PORTFOLIO_CYCLE__"] = summary
        self._save()
        return {"summary": summary, "selected": selected}

    def entry_preflight(self, card: TradeCard, current_price: float) -> tuple[bool, Optional[str]]:
        price = finite(current_price)
        if price <= 0:
            return False, "entry_price_unavailable"
        maximum = finite(card.maximum_entry_price)
        if maximum > 0 and price > maximum:
            card.state = TradeCardState.INVALIDATED
            card.current_stop = None
            card.close_reason = "maximum_entry_price_exceeded"
            card.updated_at = iso_now()
            card.metadata["entry_preflight"] = {
                "accepted": False,
                "reason": card.close_reason,
                "observed_price": price,
                "maximum_entry_price": maximum,
                "checked_at": card.updated_at,
            }
            self.cards[card.card_id] = card
            self._save()
            return False, card.close_reason
        return True, None

    def release_unfilled_card(self, card: TradeCard, reason: str) -> None:
        if card.position_quantity > 0:
            return
        if card.state in {TradeCardState.ARMED, TradeCardState.ENTERING, TradeCardState.PAUSED}:
            card.state = TradeCardState.INVALIDATED
            card.current_stop = None
            card.close_reason = str(reason or "entry_not_accepted")
            card.updated_at = iso_now()
            self.cards[card.card_id] = card
            self._save()

    def record_cycle_handoff(self, cycle_id: str, symbol: str, feedback: Dict[str, Any]) -> None:
        summary = dict(self.latest_decisions.get("__PORTFOLIO_CYCLE__") or {})
        if summary.get("cycle_id") != cycle_id:
            return
        summary["handoff"] = {
            "symbol": symbol.upper(),
            "recorded_at": iso_now(),
            "sent": bool(feedback.get("sent") or feedback.get("accepted")),
            "status": feedback.get("status"),
            "reason": feedback.get("reason") or feedback.get("rejection_reason"),
        }
        self.latest_decisions["__PORTFOLIO_CYCLE__"] = summary
        self._save()

    def portfolio_status(self, *, include_cards: bool = True) -> Dict[str, Any]:
        payload = super().portfolio_status(include_cards=include_cards)
        payload["profitability_experiment"] = self.experiment_settings()
        payload["latest_evaluation_cycle"] = dict(self.latest_decisions.get("__PORTFOLIO_CYCLE__") or {})
        return payload
