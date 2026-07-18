"""Persistence and portfolio-state primitives for Edge profitability."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional

from edge_profitability_models import (
    ACTIVE_STATES,
    TERMINAL_STATES,
    TradeCard,
    TradeCardState,
    env_float,
    finite,
    iso_now,
    utcnow,
)


class ProfitabilityStateMixin:
    def _init_state(self, state_path: Optional[Path] = None) -> None:
        self.state_path = state_path or Path(
            os.getenv("EDGE_PROFITABILITY_STATE_FILE", "data/edge_profitability_state.json")
        )
        self._lock = RLock()
        self.cards: Dict[str, TradeCard] = {}
        self.outcomes: list[Dict[str, Any]] = []
        self.execution_feedback: list[Dict[str, Any]] = []
        self.candidates: Dict[str, Dict[str, Any]] = {}
        self.position_snapshots: Dict[str, Dict[str, Any]] = {}
        self.latest_decisions: Dict[str, Dict[str, Any]] = {}
        self._load()

    @property
    def total_risk_budget_pct(self) -> float:
        return env_float("EDGE_PORTFOLIO_MAX_RISK_PCT", 2.0, minimum=0.1)

    @property
    def per_trade_max_risk_pct(self) -> float:
        return env_float("EDGE_MAX_TRADE_RISK_PCT", 0.60, minimum=0.05)

    def _load(self) -> None:
        try:
            if not self.state_path.exists():
                return
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            for card_id, raw in (payload.get("cards") or {}).items():
                if isinstance(raw, dict):
                    self.cards[str(card_id)] = TradeCard.from_dict(raw)
            self.outcomes = list(payload.get("outcomes") or [])[-5000:]
            self.execution_feedback = list(payload.get("execution_feedback") or [])[-5000:]
            self.candidates = dict(payload.get("candidates") or {})
            self.position_snapshots = dict(payload.get("position_snapshots") or {})
            self.latest_decisions = dict(payload.get("latest_decisions") or {})
        except Exception:
            self.cards, self.outcomes, self.execution_feedback = {}, [], []
            self.candidates, self.position_snapshots, self.latest_decisions = {}, {}, {}

    def _save(self) -> None:
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": "edge-profitability-state.v1",
                "updated_at": iso_now(),
                "cards": {key: value.public_dict() for key, value in self.cards.items()},
                "outcomes": self.outcomes[-5000:],
                "execution_feedback": self.execution_feedback[-5000:],
                "candidates": self.candidates,
                "position_snapshots": self.position_snapshots,
                "latest_decisions": self.latest_decisions,
            }
            temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
            temp.replace(self.state_path)

    def expire_cards(self, *, save: bool = True) -> None:
        now, changed = utcnow(), False
        for card in self.cards.values():
            if card.state.value in TERMINAL_STATES or not card.expires_at:
                continue
            try:
                expiration = datetime.fromisoformat(card.expires_at.replace("Z", "+00:00"))
                if expiration.tzinfo is None:
                    expiration = expiration.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
            if expiration <= now and card.position_quantity <= 0:
                card.state = TradeCardState.EXPIRED
                card.current_stop = None
                card.updated_at = iso_now()
                changed = True
        if changed and save:
            self._save()

    def _active_cards(self) -> list[TradeCard]:
        self.expire_cards(save=False)
        return [card for card in self.cards.values() if card.state.value in ACTIVE_STATES]

    def active_card(self, symbol: str) -> Optional[TradeCard]:
        matches = [card for card in self._active_cards() if card.symbol == symbol.upper()]
        return max(matches, key=lambda item: item.updated_at) if matches else None

    def _risk_used(self) -> float:
        return sum(max(0.0, card.risk_budget_pct) for card in self._active_cards())

    def symbol_status(self, symbol: str) -> Dict[str, Any]:
        symbol = symbol.upper()
        card = self.active_card(symbol)
        latest = dict(self.latest_decisions.get(symbol) or {})
        latest["trade_card"] = card.public_dict() if card else latest.get("trade_card")
        latest["portfolio"] = self.portfolio_status(include_cards=False)
        return latest

    def portfolio_status(self, *, include_cards: bool = True) -> Dict[str, Any]:
        active = self._active_cards()
        payload = {
            "contract_version": "edge.portfolio.strategy.v1",
            "generated_at": iso_now(),
            "total_risk_budget_pct": self.total_risk_budget_pct,
            "risk_used_pct": round(self._risk_used(), 4),
            "risk_available_pct": round(max(0.0, self.total_risk_budget_pct - self._risk_used()), 4),
            "active_trade_cards": len(active),
            "candidate_count": len(self.candidates),
            "outcome_count": len(self.outcomes),
            "execution_feedback_count": len(self.execution_feedback),
        }
        if include_cards:
            payload["cards"] = [card.public_dict() for card in active]
            payload["candidates"] = sorted(
                self.candidates.values(), key=lambda item: finite(item.get("score")), reverse=True
            )
        return payload

    def recent_outcomes(self, limit: int = 100) -> list[Dict[str, Any]]:
        return list(self.outcomes[-max(1, min(int(limit), 1000)):])[::-1]
