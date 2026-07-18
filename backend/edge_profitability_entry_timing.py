"""Forecast -> setup -> trigger discipline for new Edge entries."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from edge_profitability_models import TradeCard, env_float, finite, iso_now


_TIMING_REASONS = {
    "entry_forecast_only",
    "entry_setup_waiting_for_trigger",
    "entry_setup_expired",
    "entry_setup_invalidated",
}


def _metadata(analysis: Any) -> Dict[str, Any]:
    value = getattr(analysis, "metadata", None)
    return dict(value) if isinstance(value, dict) else {}


def _parse_time(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first_below(price: float, *values: Any) -> float:
    candidates = [finite(value) for value in values]
    candidates = [value for value in candidates if 0 < value <= price]
    return max(candidates) if candidates else 0.0


class ProfitabilityEntryTimingMixin:
    """Require setup location and trigger confirmation before ranking can enter."""

    @property
    def setup_proximity_atr(self) -> float:
        return env_float("EDGE_ENTRY_SETUP_PROXIMITY_ATR", 0.55, minimum=0.05)

    @property
    def trigger_reclaim_atr(self) -> float:
        return env_float("EDGE_ENTRY_TRIGGER_RECLAIM_ATR", 0.12, minimum=0.01)

    @property
    def trigger_signal_improvement(self) -> float:
        return env_float("EDGE_ENTRY_TRIGGER_SIGNAL_IMPROVEMENT", 0.25, minimum=0.0)

    @property
    def setup_expiry_minutes(self) -> float:
        return env_float("EDGE_ENTRY_SETUP_EXPIRY_MINUTES", 45.0, minimum=1.0)

    def experiment_settings(self) -> Dict[str, Any]:
        payload = super().experiment_settings()
        payload.update(
            {
                "entry_timing_contract": "edge.entry_timing.v1",
                "forecast_setup_trigger_required": True,
                "confirmed_breakout_immediate_trigger": True,
                "setup_proximity_atr": self.setup_proximity_atr,
                "trigger_reclaim_atr": self.trigger_reclaim_atr,
                "trigger_signal_improvement": self.trigger_signal_improvement,
                "setup_expiry_minutes": self.setup_expiry_minutes,
            }
        )
        return payload

    def assess_entry_timing(
        self,
        analysis: Any,
        thesis: Dict[str, Any],
        *,
        previous: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        previous = dict(previous or {})
        metadata = _metadata(analysis)
        indicators = metadata.get("indicators") if isinstance(metadata.get("indicators"), dict) else {}
        structure = metadata.get("market_structure") if isinstance(metadata.get("market_structure"), dict) else {}
        strategy = str(thesis.get("strategy") or "unknown")
        price = finite(getattr(analysis, "price", thesis.get("entry")))
        signal = finite(getattr(analysis, "signal_strength", 0.0))
        confidence = finite(getattr(getattr(analysis, "confidence", None), "overall", 0.0))
        atr = finite(indicators.get("atr_current"))
        if atr <= 0 and price > 0:
            atr = max(price * 0.005, 0.01)
        support = finite(structure.get("support"))
        resistance = finite(structure.get("resistance"))
        stop = finite(thesis.get("stop"))
        structure_state = str(structure.get("state") or "").lower()
        now = datetime.now(timezone.utc)

        base = {
            "contract_version": "edge.entry_timing.v1",
            "symbol": str(getattr(analysis, "symbol", thesis.get("symbol", ""))).upper(),
            "strategy": strategy,
            "observed_at": iso_now(),
            "observed_price": round(price, 6),
            "signal_strength": round(signal, 4),
            "confidence": round(confidence, 4),
            "atr": round(atr, 6),
            "support": support or None,
            "resistance": resistance or None,
        }
        if price <= 0 or atr <= 0:
            return {**base, "state": "forecast", "ready": False, "reason": "entry_price_unavailable"}

        # A structure-confirmed breakout is already the setup and trigger. It is
        # allowed immediately, but still remains bounded by maximum entry price.
        if strategy == "breakout" and structure_state == "resistance_breakout":
            trigger = resistance if resistance > 0 else price
            risk = max(price - stop, atr) if 0 < stop < price else atr
            maximum = trigger + risk * env_float("EDGE_MAX_ENTRY_SLIPPAGE_R", 0.15, minimum=0.0)
            return {
                **base,
                "state": "triggered",
                "ready": True,
                "reason": "confirmed_resistance_breakout",
                "ideal_entry_price": round(trigger, 6),
                "entry_trigger_price": round(trigger, 6),
                "maximum_entry_price": round(maximum, 6),
                "setup_price": round(trigger, 6),
                "setup_signal_strength": round(signal, 4),
                "triggered_at": iso_now(),
            }

        ema = _first_below(
            price,
            indicators.get("ema_9"),
            indicators.get("ema9"),
            indicators.get("ema_20"),
            indicators.get("ema20"),
            indicators.get("ema_short"),
        )
        setup_level = _first_below(price, support, ema)
        if setup_level <= 0:
            setup_level = max(0.01, price - atr)
        distance_atr = abs(price - setup_level) / atr
        previous_state = str(previous.get("state") or "")
        previous_time = _parse_time(previous.get("setup_observed_at") or previous.get("observed_at"))
        age_minutes = ((now - previous_time).total_seconds() / 60.0) if previous_time else 0.0

        if previous_state == "setup":
            setup_price = finite(previous.get("setup_price"), setup_level)
            setup_signal = finite(previous.get("setup_signal_strength"), signal)
            if stop > 0 and price <= stop:
                return {
                    **base,
                    "state": "invalidated",
                    "ready": False,
                    "reason": "entry_setup_invalidated",
                    "setup_price": setup_price,
                    "setup_observed_at": previous.get("setup_observed_at"),
                }
            if age_minutes > self.setup_expiry_minutes:
                return {
                    **base,
                    "state": "expired",
                    "ready": False,
                    "reason": "entry_setup_expired",
                    "setup_price": setup_price,
                    "setup_observed_at": previous.get("setup_observed_at"),
                    "age_minutes": round(age_minutes, 3),
                }
            trigger_price = setup_price + atr * self.trigger_reclaim_atr
            reclaimed = price >= trigger_price
            signal_confirmed = signal >= max(2.5, setup_signal + self.trigger_signal_improvement)
            confidence_confirmed = confidence >= env_float("EDGE_ENTRY_MIN_CONFIDENCE", 0.64, minimum=0.0)
            if reclaimed and signal_confirmed and confidence_confirmed:
                risk = max(price - stop, atr) if 0 < stop < price else atr
                maximum = price + risk * env_float("EDGE_MAX_ENTRY_SLIPPAGE_R", 0.15, minimum=0.0)
                return {
                    **base,
                    "state": "triggered",
                    "ready": True,
                    "reason": "pullback_reclaim_confirmed",
                    "ideal_entry_price": round(setup_price, 6),
                    "entry_trigger_price": round(trigger_price, 6),
                    "maximum_entry_price": round(maximum, 6),
                    "setup_price": round(setup_price, 6),
                    "setup_signal_strength": round(setup_signal, 4),
                    "setup_observed_at": previous.get("setup_observed_at"),
                    "triggered_at": iso_now(),
                    "age_minutes": round(age_minutes, 3),
                }
            if distance_atr <= self.setup_proximity_atr * 1.75:
                return {
                    **base,
                    "state": "setup",
                    "ready": False,
                    "reason": "entry_setup_waiting_for_trigger",
                    "ideal_entry_price": round(setup_price, 6),
                    "entry_trigger_price": round(trigger_price, 6),
                    "setup_price": round(setup_price, 6),
                    "setup_signal_strength": round(setup_signal, 4),
                    "setup_observed_at": previous.get("setup_observed_at"),
                    "age_minutes": round(age_minutes, 3),
                    "distance_to_setup_atr": round(distance_atr, 4),
                }

        if distance_atr <= self.setup_proximity_atr:
            trigger_price = price + atr * self.trigger_reclaim_atr
            return {
                **base,
                "state": "setup",
                "ready": False,
                "reason": "entry_setup_waiting_for_trigger",
                "ideal_entry_price": round(setup_level, 6),
                "entry_trigger_price": round(trigger_price, 6),
                "setup_price": round(price, 6),
                "setup_signal_strength": round(signal, 4),
                "setup_observed_at": iso_now(),
                "distance_to_setup_atr": round(distance_atr, 4),
            }

        return {
            **base,
            "state": "forecast",
            "ready": False,
            "reason": "entry_forecast_only",
            "ideal_entry_price": round(setup_level, 6),
            "distance_to_setup_atr": round(distance_atr, 4),
        }

    def stage_cycle_candidate(
        self,
        cycle_id: str,
        analysis: Any,
        thesis: Dict[str, Any],
        *,
        base_decision: str,
        target_bot: Optional[str] = None,
    ):
        symbol = str(getattr(analysis, "symbol", None) or thesis.get("symbol") or "").upper()
        previous = dict((self.latest_decisions.get(symbol) or {}).get("entry_timing") or {})
        assessment, opportunity = super().stage_cycle_candidate(
            cycle_id,
            analysis,
            thesis,
            base_decision=base_decision,
            target_bot=target_bot,
        )
        timing = self.assess_entry_timing(analysis, thesis, previous=previous)
        reasons = [reason for reason in opportunity.reasons if reason not in _TIMING_REASONS]
        if not timing.get("ready"):
            reasons.append(str(timing.get("reason") or "entry_trigger_not_confirmed"))
        opportunity.reasons = list(dict.fromkeys(reasons))
        opportunity.eligible = not opportunity.reasons

        timed_thesis = dict(thesis)
        timed_thesis["ideal_entry_price"] = timing.get("ideal_entry_price")
        timed_thesis["entry_trigger"] = timing.get("entry_trigger_price") or timed_thesis.get("entry_trigger")
        timed_thesis["maximum_entry_price"] = timing.get("maximum_entry_price")
        timed_thesis["entry_trigger_state"] = timing.get("state")
        cycle = self._evaluation_cycles.get(cycle_id) or {}
        candidate = (cycle.get("candidates") or {}).get(symbol)
        if isinstance(candidate, dict):
            candidate["thesis"] = timed_thesis
            candidate["entry_timing"] = timing
        latest = self.latest_decisions.setdefault(symbol, {})
        latest.update(
            {
                "entry_timing": timing,
                "opportunity": opportunity.public_dict(),
                "no_trade": not opportunity.eligible,
                "no_trade_reason": opportunity.reasons[0] if opportunity.reasons else None,
            }
        )
        self._save()
        return assessment, opportunity

    def create_trade_card(self, analysis: Any, thesis: Dict[str, Any], opportunity: Any) -> TradeCard:
        card = super().create_trade_card(analysis, thesis, opportunity)
        timing = dict((self.latest_decisions.get(card.symbol) or {}).get("entry_timing") or {})
        if timing:
            card.entry_trigger = finite(timing.get("entry_trigger_price")) or card.entry_trigger
            maximum = finite(timing.get("maximum_entry_price"))
            if maximum > 0:
                card.maximum_entry_price = round(maximum, 6)
            card.metadata["entry_trigger_state"] = str(timing.get("state") or "")
            card.metadata["entry_timing"] = timing
            card.metadata["ideal_entry_price"] = timing.get("ideal_entry_price")
            card.updated_at = iso_now()
            self.cards[card.card_id] = card
            self._save()
        return card
