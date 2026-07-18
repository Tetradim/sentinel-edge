"""Trade-card lifecycle, execution feedback, and outcome learning."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
from typing import Any, Dict, Optional

from edge_profitability_models import OutcomeRecord, TradeCard, TradeCardState, finite, iso_now


class ProfitabilityLifecycleMixin:
    def lifecycle_metadata(self, card: TradeCard, *, action: str) -> Dict[str, Any]:
        return {
            "contract_version": "edge.strategy.lifecycle.v1",
            "card_id": card.card_id,
            "strategy_id": card.strategy_id,
            "thesis_id": card.thesis_id,
            "position_id": card.position_id,
            "state": card.state.value,
            "action": action,
            "assigned_bot": card.target_bot,
            "risk_budget_pct": card.risk_budget_pct,
            "target_notional": card.target_notional,
            "entry_trigger": card.entry_trigger,
            "maximum_entry_price": card.maximum_entry_price,
            "initial_stop": card.initial_stop,
            "current_stop": card.current_stop,
            "targets": card.targets,
            "expires_at": card.expires_at,
            "invalidation": card.invalidation,
            "stop_owner": {"position_id": card.position_id, "expires_on_position_close": True, "inherit_on_reentry": False},
        }

    def attach_to_metadata(self, metadata: Dict[str, Any], card: TradeCard, *, action: str) -> Dict[str, Any]:
        merged = dict(metadata)
        merged.update(
            {
                "trade_card": card.public_dict(),
                "strategy_lifecycle": self.lifecycle_metadata(card, action=action),
                "card_id": card.card_id,
                "strategy_id": card.strategy_id,
                "thesis_id": card.thesis_id,
                "position_id": card.position_id,
                "target_bot": card.target_bot,
                "risk_budget_pct": card.risk_budget_pct,
                "opportunity_score": card.opportunity_score,
                "expected_value_pct": card.expected_value_pct,
                "calibrated_confidence": card.predicted_probability,
            }
        )
        if action == "buy":
            merged.setdefault("target_notional", card.target_notional)
            merged.setdefault("max_notional", card.target_notional)
        if action in {"sell", "emergency_exit"}:
            merged["invalidate_position_scoped_stop"] = True
            merged["closed_position_id"] = card.position_id
        if action == "tighten_stop" or str(merged.get("supervisory_directive")) == "set_stop":
            merged["position_scoped_stop"] = {
                "position_id": card.position_id,
                "expires_on_position_close": True,
                "inherit_on_reentry": False,
            }
        return merged

    def record_feedback(
        self,
        card: Optional[TradeCard],
        *,
        action: str,
        feedback: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if card is None:
            return
        payload = dict(feedback) if isinstance(feedback, dict) else {"sent": bool(feedback)}
        status = str(payload.get("status") or "").lower()
        negative_status = status in {"rejected", "failed", "cancelled", "canceled", "expired"}
        accepted = bool(payload.get("accepted") or (payload.get("sent") and not negative_status))
        if not status:
            status = "accepted" if accepted else "failed"
        now = iso_now()
        record = {
            "recorded_at": now,
            "card_id": card.card_id,
            "position_id": card.position_id,
            "symbol": card.symbol,
            "target_bot": card.target_bot,
            "action": action,
            "accepted": accepted,
            "status": status,
            "reason": payload.get("reason") or payload.get("rejection_reason"),
            "requested_price": finite((metadata or {}).get("price")),
            "filled_price": finite(payload.get("filled_price") or payload.get("price")),
            "filled_quantity": finite(payload.get("filled_quantity") or payload.get("quantity")),
            "fees": finite(payload.get("fees") or payload.get("commission")),
            "latency_ms": finite(payload.get("latency_ms")),
            "feedback": payload,
        }
        requested_price, filled_price = record["requested_price"], record["filled_price"]
        if requested_price > 0 and filled_price > 0:
            direction = 1.0 if action == "buy" else -1.0
            record["slippage_bps"] = round(((filled_price - requested_price) / requested_price) * 10000.0 * direction, 4)
        self.execution_feedback.append(record)
        card.last_feedback = payload
        card.updated_at = now
        if accepted:
            if action == "buy":
                card.state = TradeCardState.ENTERING
            elif action in {"sell", "emergency_exit"}:
                card.state = TradeCardState.EXITING
            elif str((metadata or {}).get("supervisory_directive")) == "reduce_position":
                card.state = TradeCardState.REDUCING
            elif action == "tighten_stop" or str((metadata or {}).get("supervisory_directive")) == "set_stop":
                stop_price = finite((metadata or {}).get("stop_price"))
                if stop_price > 0:
                    card.current_stop = stop_price
        elif status in {"rejected", "failed"} and action == "buy":
            card.state = TradeCardState.ARMED
        self.cards[card.card_id] = card
        self._save()

    def observe_position(self, symbol: str, position: Optional[Dict[str, Any]], current_price: float = 0.0) -> None:
        symbol = symbol.upper()
        position = dict(position or {})
        quantity = finite(position.get("quantity", position.get("qty", position.get("size", 0.0))))
        entry = finite(position.get("entry_price", position.get("avg_entry", 0.0)))
        pnl = finite(position.get("current_pnl_dollar", position.get("pnl", 0.0)))
        pnl_pct = finite(position.get("current_pnl_pct", position.get("pnl_pct", 0.0)))
        previous = dict(self.position_snapshots.get(symbol) or {})
        previous_qty = finite(previous.get("quantity"))
        card = self.active_card(symbol)
        now = iso_now()

        if card is not None and quantity > 0:
            card.position_quantity = quantity
            if entry > 0:
                card.entry_price = entry
            if card.state in {TradeCardState.ARMED, TradeCardState.ENTERING, TradeCardState.REDUCING}:
                card.state = TradeCardState.ACTIVE
            card.updated_at = now
            self.cards[card.card_id] = card

        if card is not None and quantity <= 0 and previous_qty > 0:
            feedback_pnl = card.last_feedback.get("realized_pnl", card.last_feedback.get("pnl"))
            feedback_return = card.last_feedback.get("realized_return_pct", card.last_feedback.get("pnl_pct"))
            realized = finite(feedback_pnl) if feedback_pnl is not None else (pnl if pnl != 0.0 else finite(previous.get("pnl")))
            realized_pct = finite(feedback_return) if feedback_return is not None else (pnl_pct if pnl_pct != 0.0 else finite(previous.get("pnl_pct")))
            card.state = TradeCardState.COMPLETED
            card.position_quantity = 0.0
            card.realized_pnl = realized
            card.close_reason = str(card.last_feedback.get("reason") or "position_closed")
            card.current_stop = None
            card.updated_at = now
            card.metadata["stop_owner"] = {
                "position_id": card.position_id,
                "expired_at": now,
                "expires_on_position_close": True,
                "inherit_on_reentry": False,
            }
            outcome_seed = f"{card.card_id}:{now}"
            outcome = OutcomeRecord(
                outcome_id=f"edge-outcome:{hashlib.sha256(outcome_seed.encode()).hexdigest()[:24]}",
                card_id=card.card_id,
                strategy_id=card.strategy_id,
                thesis_id=card.thesis_id,
                position_id=card.position_id,
                symbol=card.symbol,
                target_bot=card.target_bot,
                strategy=card.strategy,
                regime=card.regime,
                opened_at=card.created_at,
                closed_at=now,
                predicted_probability=card.predicted_probability,
                expected_value_pct=card.expected_value_pct,
                realized_pnl=realized,
                realized_return_pct=realized_pct,
                exit_reason=card.close_reason or "position_closed",
                execution_cost=sum(
                    finite(item.get("fees")) for item in self.execution_feedback if item.get("card_id") == card.card_id
                ),
                metadata={"last_price": current_price},
            )
            self.outcomes.append(asdict(outcome))
            self.cards[card.card_id] = card

        self.position_snapshots[symbol] = {
            "quantity": quantity,
            "entry_price": entry,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "current_price": current_price,
            "updated_at": now,
        }
        self._save()
