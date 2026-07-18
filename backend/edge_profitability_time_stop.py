"""Position progress, MFE/MAE, and time-stop capital recycling policy."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional

from edge_profitability_models import TradeCard, env_float, env_int, finite, iso_now


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _quantity(position: Dict[str, Any]) -> float:
    return finite(position.get("quantity", position.get("qty", position.get("size", 0.0))))


def _entry(position: Dict[str, Any], card: TradeCard) -> float:
    return finite(
        position.get("entry_price", position.get("avg_entry", position.get("average_price", card.entry_price or 0.0)))
    )


def _price(position: Dict[str, Any], current_price: float, entry: float) -> float:
    return finite(
        current_price,
        finite(position.get("current_price", position.get("market_price", position.get("price", entry))), entry),
    )


class ProfitabilityTimeStopMixin:
    """Measure whether a position validates quickly enough to keep its risk budget."""

    @property
    def time_stop_mode(self) -> str:
        mode = os.getenv("EDGE_TIME_STOP_MODE", "shadow").strip().lower()
        return mode if mode in {"off", "shadow", "reduce", "exit"} else "shadow"

    @property
    def time_stop_target_r(self) -> float:
        return env_float("EDGE_TIME_STOP_PROGRESS_TARGET_R", 0.50, minimum=0.05)

    @property
    def time_stop_min_observations(self) -> int:
        return env_int("EDGE_TIME_STOP_MIN_OBSERVATIONS", 5, minimum=1)

    def _time_limit_minutes(self, strategy: str) -> float:
        normalized = str(strategy or "").lower()
        if normalized == "breakout":
            return env_float("EDGE_TIME_STOP_BREAKOUT_MINUTES", 30.0, minimum=1.0)
        if normalized in {"continuation", "reversal"}:
            return env_float("EDGE_TIME_STOP_PATTERN_MINUTES", 45.0, minimum=1.0)
        return env_float("EDGE_TIME_STOP_TREND_MINUTES", 60.0, minimum=1.0)

    def experiment_settings(self) -> Dict[str, Any]:
        payload = super().experiment_settings()
        payload.update(
            {
                "time_stop_contract": "edge.time_stop.v1",
                "time_stop_mode": self.time_stop_mode,
                "time_stop_progress_target_r": self.time_stop_target_r,
                "time_stop_min_observations": self.time_stop_min_observations,
                "time_stop_breakout_minutes": self._time_limit_minutes("breakout"),
                "time_stop_pattern_minutes": self._time_limit_minutes("continuation"),
                "time_stop_trend_minutes": self._time_limit_minutes("multi_timeframe_trend"),
            }
        )
        return payload

    def _update_time_stop_metrics(
        self,
        card: TradeCard,
        position: Dict[str, Any],
        *,
        current_price: float,
    ) -> Dict[str, Any]:
        quantity = _quantity(position)
        if quantity <= 0:
            return dict(card.metadata.get("time_stop") or {})
        entry = _entry(position, card)
        observed_price = _price(position, current_price, entry)
        if entry <= 0 or observed_price <= 0:
            return dict(card.metadata.get("time_stop") or {})

        risk_per_share = entry - finite(card.initial_stop)
        if risk_per_share <= 0:
            risk_per_share = max(entry * env_float("EDGE_TIME_STOP_FALLBACK_RISK_PCT", 1.5, minimum=0.1) / 100.0, 0.01)
        now = datetime.now(timezone.utc)
        prior = dict(card.metadata.get("time_stop") or {})
        opened_at = _parse_time(prior.get("opened_at_confirmed")) or now
        observations = int(prior.get("observations") or 0) + 1
        current_r = (observed_price - entry) / risk_per_share
        max_favorable_r = max(finite(prior.get("max_favorable_r"), current_r), current_r)
        max_adverse_r = min(finite(prior.get("max_adverse_r"), current_r), current_r)
        elapsed_minutes = max(0.0, (now - opened_at).total_seconds() / 60.0)
        target_r = self.time_stop_target_r
        reached_at = prior.get("reached_progress_target_at")
        observations_to_target = prior.get("observations_to_progress_target")
        if reached_at is None and max_favorable_r >= target_r:
            reached_at = iso_now()
            observations_to_target = observations

        limit_minutes = self._time_limit_minutes(card.strategy)
        maximum_current_r = env_float("EDGE_TIME_STOP_MAX_CURRENT_R", 0.15)
        recommendation = bool(
            reached_at is None
            and observations >= self.time_stop_min_observations
            and elapsed_minutes >= limit_minutes
            and max_favorable_r < target_r
            and current_r <= maximum_current_r
        )
        severe_stagnation_r = env_float("EDGE_TIME_STOP_EXIT_BELOW_R", -0.35)
        action = "sell" if current_r <= severe_stagnation_r else "reduce_position"
        reason = None
        if recommendation:
            reason = (
                f"Position failed to reach +{target_r:.2f}R within {limit_minutes:.0f} minutes "
                f"({observations} observations, MFE={max_favorable_r:.2f}R, current={current_r:.2f}R)"
            )

        metrics = {
            "contract_version": "edge.time_stop.v1",
            "mode": self.time_stop_mode,
            "opened_at_confirmed": opened_at.isoformat(),
            "updated_at": iso_now(),
            "strategy": card.strategy,
            "entry_price": round(entry, 8),
            "observed_price": round(observed_price, 8),
            "risk_per_share": round(risk_per_share, 8),
            "current_r": round(current_r, 6),
            "max_favorable_r": round(max_favorable_r, 6),
            "max_adverse_r": round(max_adverse_r, 6),
            "observations": observations,
            "elapsed_minutes": round(elapsed_minutes, 4),
            "progress_target_r": target_r,
            "reached_progress_target_at": reached_at,
            "observations_to_progress_target": observations_to_target,
            "limit_minutes": limit_minutes,
            "recommendation_active": recommendation,
            "recommended_action": action if recommendation else None,
            "recommendation_reason": reason,
        }
        card.metadata["time_stop"] = metrics
        card.updated_at = metrics["updated_at"]
        self.cards[card.card_id] = card
        latest = self.latest_decisions.setdefault(card.symbol, {})
        latest["time_stop"] = metrics
        return metrics

    def observe_position(self, symbol: str, position: Optional[Dict[str, Any]], current_price: float = 0.0) -> None:
        symbol = symbol.upper()
        position_payload = dict(position or {})
        card = self.active_card(symbol)
        metrics: Dict[str, Any] = {}
        if card is not None and _quantity(position_payload) > 0:
            metrics = self._update_time_stop_metrics(card, position_payload, current_price=current_price)
        super().observe_position(symbol, position_payload, current_price=current_price)

        # A close may have produced the terminal outcome inside the lifecycle
        # implementation. Preserve progress attribution on that exact outcome.
        if card is not None and _quantity(position_payload) <= 0 and metrics:
            for outcome in reversed(self.outcomes):
                if outcome.get("card_id") == card.card_id:
                    outcome.setdefault("metadata", {})["time_stop"] = metrics
                    break
            self._save()

    def time_stop_recommendation(self, symbol: str) -> Dict[str, Any]:
        card = self.active_card(symbol.upper())
        metrics = dict((card.metadata.get("time_stop") if card else {}) or {})
        return metrics if metrics.get("recommendation_active") else {}

    def portfolio_status(self, *, include_cards: bool = True) -> Dict[str, Any]:
        payload = super().portfolio_status(include_cards=include_cards)
        active = [
            {"symbol": card.symbol, **dict(card.metadata.get("time_stop") or {})}
            for card in self._active_cards()
            if isinstance(card.metadata.get("time_stop"), dict)
        ]
        payload["time_stop"] = {
            "contract_version": "edge.time_stop.status.v1",
            "mode": self.time_stop_mode,
            "active_measurements": active,
            "recommendation_count": sum(1 for item in active if item.get("recommendation_active")),
        }
        return payload
