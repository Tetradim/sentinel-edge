"""Regime classification, confidence calibration, ranking, and capital allocation."""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Iterable, Optional

from edge_profitability_models import (
    MarketRegime,
    OpportunityScore,
    RegimeAssessment,
    TradeCard,
    TradeCardState,
    analysis_metadata,
    clamp,
    confidence,
    env_float,
    env_int,
    finite,
    infer_target_bot,
    iso_now,
    symbol_bucket,
    trend_name,
)


class ProfitabilityScoringMixin:
    def classify_regime(self, analysis: Any) -> RegimeAssessment:
        metadata = analysis_metadata(analysis)
        indicators = metadata.get("indicators") if isinstance(metadata.get("indicators"), dict) else {}
        structure = metadata.get("market_structure") if isinstance(metadata.get("market_structure"), dict) else {}
        signal = finite(getattr(analysis, "signal_strength", 0.0))
        price = finite(getattr(analysis, "price", 0.0))
        atr = finite(indicators.get("atr_current"))
        volatility = (atr / price) * 100.0 if price > 0 and atr > 0 else finite(metadata.get("volatility_pct"))
        alignment = finite(metadata.get("multi_timeframe_alignment"))
        trend = trend_name(analysis)
        structure_state = str(structure.get("state") or "").lower()
        raw_confidence = confidence(analysis)

        if signal <= -7.0 and volatility >= 2.0:
            regime, allowed, reason = MarketRegime.PANIC, False, "panic_regime"
        elif structure_state == "resistance_breakout" and trend == "bullish":
            regime, allowed, reason = MarketRegime.BREAKOUT_UP, True, "confirmed_resistance_breakout"
        elif structure_state == "support_breakdown" or (trend == "bearish" and alignment <= -0.35):
            regime = MarketRegime.BREAKOUT_DOWN if structure_state == "support_breakdown" else MarketRegime.TRENDING_DOWN
            allowed, reason = False, "bearish_regime"
        elif volatility >= env_float("EDGE_HIGH_VOLATILITY_PCT", 3.0, minimum=0.1):
            regime = MarketRegime.HIGH_VOLATILITY
            allowed = raw_confidence >= env_float("EDGE_HIGH_VOL_MIN_CONFIDENCE", 0.82, minimum=0.0) and signal >= 4.5
            reason = "high_volatility_exception" if allowed else "high_volatility_no_trade"
        elif trend == "bullish" and alignment >= 0.35 and signal >= 2.5:
            regime, allowed, reason = MarketRegime.TRENDING_UP, True, "bullish_multi_timeframe_trend"
        elif abs(alignment) < 0.20 and abs(signal) < 3.0:
            regime = MarketRegime.RANGE
            allowed = os.getenv("EDGE_ALLOW_RANGE_ENTRIES", "false").lower() in {"1", "true", "yes", "on"}
            reason = "range_strategy_enabled" if allowed else "range_no_trade"
        else:
            regime = MarketRegime.UNKNOWN
            allowed = raw_confidence >= env_float("EDGE_UNKNOWN_REGIME_MIN_CONFIDENCE", 0.78, minimum=0.0) and signal >= 4.0
            reason = "strong_unknown_regime_exception" if allowed else "unclassified_no_trade"

        return RegimeAssessment(
            regime=regime,
            trade_allowed=allowed,
            reason=reason,
            strength=clamp(max(abs(alignment), abs(signal) / 10.0), 0.0, 1.0),
            volatility_pct=round(volatility, 4),
            mtf_alignment=round(alignment, 4),
            signal_strength=round(signal, 4),
            metadata={"trend": trend, "structure_state": structure_state},
        )

    def _matching_outcomes(self, target_bot: str, strategy: str, regime: str) -> Iterable[Dict[str, Any]]:
        exact = [
            item for item in self.outcomes
            if str(item.get("target_bot")) == target_bot
            and str(item.get("strategy")) == strategy
            and str(item.get("regime")) == regime
        ]
        if len(exact) >= 5:
            return exact
        broader = [
            item for item in self.outcomes
            if str(item.get("target_bot")) == target_bot
            and str(item.get("strategy")) == strategy
        ]
        return broader if broader else exact

    def calibrate_confidence(self, raw: float, target_bot: str, strategy: str, regime: str) -> float:
        samples = list(self._matching_outcomes(target_bot, strategy, regime))
        wins = sum(1 for item in samples if finite(item.get("realized_pnl")) > 0)
        posterior = (wins + 2.0) / (len(samples) + 4.0)
        weight = len(samples) / (len(samples) + 12.0)
        return round(clamp(raw * (1.0 - weight) + posterior * weight, 0.05, 0.95), 4)

    def _correlation_penalty(self, symbol: str, target_bot: str) -> float:
        bucket = symbol_bucket(symbol, target_bot)
        related = sum(
            1 for card in self._active_cards()
            if symbol_bucket(card.symbol, card.target_bot) == bucket and card.symbol != symbol.upper()
        )
        return round(min(0.65, related * env_float("EDGE_CORRELATED_POSITION_PENALTY", 0.18, minimum=0.0)), 4)

    def _rank_candidate(self, symbol: str, score: float, target_bot: str, payload: Dict[str, Any]) -> int:
        now = time.time()
        ttl = env_int("EDGE_CANDIDATE_TTL_SECONDS", 180, minimum=10)
        self.candidates = {
            key: value for key, value in self.candidates.items()
            if now - finite(value.get("updated_at"), now) <= ttl
        }
        self.candidates[symbol.upper()] = {
            "symbol": symbol.upper(),
            "target_bot": target_bot,
            "score": round(score, 4),
            "updated_at": now,
            **payload,
        }
        ordered = sorted(self.candidates.values(), key=lambda item: finite(item.get("score")), reverse=True)
        for index, item in enumerate(ordered, start=1):
            if str(item.get("symbol")) == symbol.upper():
                return index
        return len(ordered)

    def score_opportunity(
        self,
        analysis: Any,
        thesis: Dict[str, Any],
        target_bot: Optional[str] = None,
    ) -> tuple[RegimeAssessment, OpportunityScore]:
        symbol = str(getattr(analysis, "symbol", None) or thesis.get("symbol") or "").upper()
        target_bot = target_bot or infer_target_bot(symbol, analysis_metadata(analysis))
        strategy = str(thesis.get("strategy") or "unknown")
        assessment = self.classify_regime(analysis)
        raw_confidence = confidence(analysis)
        calibrated = self.calibrate_confidence(raw_confidence, target_bot, strategy, assessment.regime.value)
        entry = finite(thesis.get("entry") or getattr(analysis, "price", 0.0))
        stop = finite(thesis.get("stop"))
        targets = thesis.get("targets") if isinstance(thesis.get("targets"), list) else []
        target = finite(targets[0]) if targets else 0.0
        risk_pct = ((entry - stop) / entry) * 100.0 if entry > 0 and 0 < stop < entry else 0.0
        reward_pct = ((target - entry) / entry) * 100.0 if entry > 0 and target > entry else 0.0
        reward_risk = reward_pct / risk_pct if risk_pct > 0 else 0.0
        cost_pct = env_float("EDGE_ESTIMATED_ROUND_TRIP_COST_BPS", 10.0, minimum=0.0) / 100.0
        expected_value = calibrated * reward_pct - (1.0 - calibrated) * risk_pct - cost_pct
        regime_multiplier = {
            MarketRegime.BREAKOUT_UP: 1.15,
            MarketRegime.TRENDING_UP: 1.0,
            MarketRegime.HIGH_VOLATILITY: 0.65,
            MarketRegime.RANGE: 0.45,
            MarketRegime.UNKNOWN: 0.60,
            MarketRegime.TRENDING_DOWN: 0.0,
            MarketRegime.BREAKOUT_DOWN: 0.0,
            MarketRegime.PANIC: 0.0,
        }[assessment.regime]
        correlation_penalty = self._correlation_penalty(symbol, target_bot)
        expectancy_ratio = expected_value / max(risk_pct, 0.25)
        score = clamp(expectancy_ratio * 50.0 * regime_multiplier * (1.0 - correlation_penalty), -100.0, 100.0)
        remaining = max(0.0, self.total_risk_budget_pct - self._risk_used())
        proposed_risk = self.per_trade_max_risk_pct * (0.45 + calibrated * 0.55) * max(regime_multiplier, 0.25)
        risk_budget = min(self.per_trade_max_risk_pct, remaining, max(0.0, proposed_risk))
        base_notional = env_float("EDGE_BASE_TARGET_NOTIONAL", 1000.0, minimum=1.0)
        target_notional = base_notional * clamp((score + 20.0) / 70.0, 0.25, 1.25)
        rank = self._rank_candidate(
            symbol,
            score,
            target_bot,
            {"strategy": strategy, "regime": assessment.regime.value, "expected_value_pct": round(expected_value, 4)},
        )
        reasons: list[str] = []
        if not assessment.trade_allowed:
            reasons.append(assessment.reason)
        if raw_confidence < env_float("EDGE_ENTRY_MIN_CONFIDENCE", 0.64, minimum=0.0):
            reasons.append("confidence_below_profitability_threshold")
        if reward_risk < env_float("EDGE_MIN_REWARD_RISK", 1.5, minimum=0.1):
            reasons.append("reward_risk_below_threshold")
        if expected_value <= 0:
            reasons.append("non_positive_expected_value")
        if score < env_float("EDGE_MIN_OPPORTUNITY_SCORE", 20.0):
            reasons.append("opportunity_score_below_threshold")
        if risk_budget <= 0:
            reasons.append("portfolio_risk_budget_exhausted")
        if rank > env_int("EDGE_MAX_RANKED_ENTRY_SLOTS", 3, minimum=1):
            reasons.append("outside_ranked_entry_slots")

        opportunity = OpportunityScore(
            symbol=symbol,
            target_bot=target_bot,
            strategy=strategy,
            regime=assessment.regime.value,
            raw_confidence=round(raw_confidence, 4),
            calibrated_confidence=calibrated,
            reward_risk=round(reward_risk, 4),
            expected_value_pct=round(expected_value, 4),
            estimated_cost_pct=round(cost_pct, 4),
            regime_multiplier=round(regime_multiplier, 4),
            correlation_penalty=correlation_penalty,
            score=round(score, 4),
            risk_budget_pct=round(risk_budget, 4),
            target_notional=round(target_notional, 2),
            rank=rank,
            eligible=not reasons,
            reasons=reasons,
        )
        self.latest_decisions[symbol] = {
            "updated_at": iso_now(),
            "regime": assessment.public_dict(),
            "opportunity": opportunity.public_dict(),
            "no_trade": not opportunity.eligible,
            "no_trade_reason": reasons[0] if reasons else None,
        }
        self._save()
        return assessment, opportunity

    def _new_identity(self, symbol: str, strategy: str) -> tuple[str, str, str, str]:
        seed = f"{symbol.upper()}:{strategy}:{time.time_ns()}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        card_id = f"edge-card:{digest[:24]}"
        return card_id, f"edge-strategy:{digest[24:40]}", f"edge-thesis:{digest[40:56]}", f"edge-position:{digest[8:32]}"

    def create_trade_card(self, analysis: Any, thesis: Dict[str, Any], opportunity: OpportunityScore) -> TradeCard:
        existing = self.active_card(opportunity.symbol)
        if existing is not None:
            return existing
        card_id, strategy_id, thesis_id, position_id = self._new_identity(opportunity.symbol, opportunity.strategy)
        entry = finite(thesis.get("entry")) or None
        trigger = finite(thesis.get("entry_trigger")) or None
        stop = finite(thesis.get("stop")) or None
        risk_distance = (entry - stop) if entry and stop and stop < entry else 0.0
        max_entry = entry + risk_distance * env_float("EDGE_MAX_ENTRY_SLIPPAGE_R", 0.15, minimum=0.0) if entry else None
        card = TradeCard(
            card_id=card_id,
            strategy_id=strategy_id,
            thesis_id=thesis_id,
            position_id=position_id,
            symbol=opportunity.symbol,
            target_bot=opportunity.target_bot,
            direction="long",
            strategy=opportunity.strategy,
            state=TradeCardState.ARMED,
            regime=opportunity.regime,
            created_at=iso_now(),
            updated_at=iso_now(),
            expires_at=str(thesis.get("expiration")) if thesis.get("expiration") else None,
            entry_trigger=trigger,
            entry_price=entry,
            maximum_entry_price=round(max_entry, 4) if max_entry else None,
            target_notional=opportunity.target_notional,
            risk_budget_pct=opportunity.risk_budget_pct,
            initial_stop=stop,
            current_stop=stop,
            targets=[finite(value) for value in (thesis.get("targets") or []) if finite(value) > 0],
            invalidation=str(thesis.get("invalidation") or "strategy thesis invalidated"),
            predicted_probability=opportunity.calibrated_confidence,
            expected_value_pct=opportunity.expected_value_pct,
            opportunity_score=opportunity.score,
            metadata={
                "trade_card_schema": "edge.trade_card.v1",
                "source": "edge_profitability_coordinator",
                "rationale": list(thesis.get("rationale") or []),
                "patterns": list(thesis.get("patterns") or []),
                "stop_owner": {"position_id": position_id, "expires_on_position_close": True, "inherit_on_reentry": False},
            },
        )
        self.cards[card.card_id] = card
        self.latest_decisions.setdefault(card.symbol, {})["trade_card"] = card.public_dict()
        self._save()
        return card

    def evaluate_entry(
        self,
        analysis: Any,
        thesis: Dict[str, Any],
        target_bot: Optional[str] = None,
    ) -> tuple[bool, RegimeAssessment, OpportunityScore, Optional[TradeCard]]:
        active = self.active_card(str(getattr(analysis, "symbol", None) or thesis.get("symbol") or ""))
        assessment, opportunity = self.score_opportunity(analysis, thesis, target_bot)
        if active is not None:
            opportunity.eligible = False
            opportunity.reasons.append("active_trade_card_exists")
            self.latest_decisions.setdefault(opportunity.symbol, {}).update(
                {"no_trade": True, "no_trade_reason": "active_trade_card_exists", "trade_card": active.public_dict()}
            )
            self._save()
            return False, assessment, opportunity, active
        if not opportunity.eligible:
            return False, assessment, opportunity, None
        return True, assessment, opportunity, self.create_trade_card(analysis, thesis, opportunity)

    def evaluate_external_proposal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        symbol = str(payload.get("symbol") or "").strip().upper()
        target_bot = str(payload.get("target_bot") or payload.get("source_bot") or infer_target_bot(symbol)).strip()
        strategy = str(payload.get("strategy") or "external_specialist")
        direction = str(payload.get("direction") or "long").strip().lower()
        if direction not in {"long", "short"}:
            direction = "long"
        raw_confidence = clamp(finite(payload.get("confidence"), 0.0), 0.0, 1.0)
        reward_pct = max(0.0, finite(payload.get("expected_reward_pct")))
        risk_pct = max(0.0, finite(payload.get("expected_risk_pct")))
        costs = max(0.0, finite(payload.get("estimated_cost_pct"), env_float("EDGE_ESTIMATED_ROUND_TRIP_COST_BPS", 10.0) / 100.0))
        regime = str(payload.get("regime") or MarketRegime.UNKNOWN.value)
        calibrated = self.calibrate_confidence(raw_confidence, target_bot, strategy, regime)
        reward_risk = reward_pct / risk_pct if risk_pct > 0 else 0.0
        expected_value = calibrated * reward_pct - (1.0 - calibrated) * risk_pct - costs
        penalty = self._correlation_penalty(symbol, target_bot)
        score = clamp((expected_value / max(risk_pct, 0.25)) * 50.0 * (1.0 - penalty), -100.0, 100.0)
        remaining = max(0.0, self.total_risk_budget_pct - self._risk_used())
        risk_budget = min(self.per_trade_max_risk_pct, remaining, self.per_trade_max_risk_pct * calibrated)
        rank = self._rank_candidate(symbol, score, target_bot, {"strategy": strategy, "regime": regime, "external": True})
        reasons: list[str] = []
        normalized_regime = regime.strip().lower()
        if not symbol:
            reasons.append("missing_symbol")
        if not target_bot:
            reasons.append("missing_target_bot")
        if normalized_regime == MarketRegime.PANIC.value:
            reasons.append("panic_regime")
        if normalized_regime == MarketRegime.RANGE.value and os.getenv("EDGE_ALLOW_RANGE_ENTRIES", "false").lower() not in {"1", "true", "yes", "on"}:
            reasons.append("range_no_trade")
        if direction == "long" and normalized_regime in {MarketRegime.TRENDING_DOWN.value, MarketRegime.BREAKOUT_DOWN.value}:
            reasons.append("direction_regime_conflict")
        if direction == "short" and normalized_regime in {MarketRegime.TRENDING_UP.value, MarketRegime.BREAKOUT_UP.value}:
            reasons.append("direction_regime_conflict")
        if normalized_regime == MarketRegime.HIGH_VOLATILITY.value and raw_confidence < env_float("EDGE_HIGH_VOL_MIN_CONFIDENCE", 0.82, minimum=0.0):
            reasons.append("high_volatility_no_trade")
        if normalized_regime == MarketRegime.UNKNOWN.value and raw_confidence < env_float("EDGE_UNKNOWN_REGIME_MIN_CONFIDENCE", 0.78, minimum=0.0):
            reasons.append("unclassified_no_trade")
        if raw_confidence < env_float("EDGE_ENTRY_MIN_CONFIDENCE", 0.64, minimum=0.0):
            reasons.append("confidence_below_profitability_threshold")
        if reward_risk < env_float("EDGE_MIN_REWARD_RISK", 1.5, minimum=0.1):
            reasons.append("reward_risk_below_threshold")
        if expected_value <= 0:
            reasons.append("non_positive_expected_value")
        if score < env_float("EDGE_MIN_OPPORTUNITY_SCORE", 20.0):
            reasons.append("opportunity_score_below_threshold")
        if risk_budget <= 0:
            reasons.append("portfolio_risk_budget_exhausted")
        if rank > env_int("EDGE_MAX_RANKED_ENTRY_SLOTS", 3, minimum=1):
            reasons.append("outside_ranked_entry_slots")
        if self.active_card(symbol) is not None:
            reasons.append("active_trade_card_exists")
        evaluated_at = iso_now()
        result = {
            "contract_version": "edge.strategy.authorization.v1",
            "authorized": not reasons,
            "symbol": symbol,
            "target_bot": target_bot,
            "strategy": strategy,
            "regime": regime,
            "rank": rank,
            "score": round(score, 4),
            "raw_confidence": round(raw_confidence, 4),
            "calibrated_confidence": calibrated,
            "reward_risk": round(reward_risk, 4),
            "expected_value_pct": round(expected_value, 4),
            "risk_budget_pct": round(risk_budget, 4),
            "target_notional": round(env_float("EDGE_BASE_TARGET_NOTIONAL", 1000.0) * clamp((score + 20) / 70, 0.25, 1.25), 2),
            "reasons": reasons,
            "evaluated_at": evaluated_at,
        }
        if result["authorized"]:
            card_id, strategy_id, thesis_id, position_id = self._new_identity(symbol, strategy)
            entry_price = finite(payload.get("entry_price")) or None
            stop_price = finite(payload.get("stop_price")) or None
            card = TradeCard(
                card_id=card_id,
                strategy_id=strategy_id,
                thesis_id=thesis_id,
                position_id=position_id,
                symbol=symbol,
                target_bot=target_bot,
                direction=direction,
                strategy=strategy,
                state=TradeCardState.ARMED,
                regime=regime,
                created_at=evaluated_at,
                updated_at=evaluated_at,
                expires_at=str(payload.get("expires_at")) if payload.get("expires_at") else None,
                entry_trigger=finite(payload.get("entry_trigger")) or None,
                entry_price=entry_price,
                maximum_entry_price=finite(payload.get("maximum_entry_price")) or None,
                target_notional=result["target_notional"],
                risk_budget_pct=result["risk_budget_pct"],
                initial_stop=stop_price,
                current_stop=stop_price,
                targets=[finite(value) for value in (payload.get("targets") or []) if finite(value) > 0],
                invalidation=str(payload.get("invalidation") or "specialist thesis invalidated"),
                predicted_probability=calibrated,
                expected_value_pct=result["expected_value_pct"],
                opportunity_score=result["score"],
                metadata={
                    "trade_card_schema": "edge.trade_card.v1",
                    "source": "external_specialist_proposal",
                    "source_bot": payload.get("source_bot"),
                    "proposal": dict(payload),
                    "stop_owner": {"position_id": position_id, "expires_on_position_close": True, "inherit_on_reentry": False},
                },
            )
            self.cards[card.card_id] = card
            result["trade_card"] = card.public_dict()
        self.latest_decisions[symbol] = {
            "updated_at": evaluated_at,
            "regime": {"regime": regime},
            "opportunity": result,
            "no_trade": bool(reasons),
            "no_trade_reason": reasons[0] if reasons else None,
            "trade_card": result.get("trade_card"),
        }
        self._save()
        return result
