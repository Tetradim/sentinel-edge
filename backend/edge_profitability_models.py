"""Data contracts and helpers for Edge's portfolio profitability coordinator."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import math
import os
from typing import Any, Dict, Optional

TERMINAL_STATES = {"completed", "invalidated", "expired"}
ACTIVE_STATES = {"armed", "entering", "active", "reducing", "exiting", "paused"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def env_float(name: str, default: float, *, minimum: Optional[float] = None) -> float:
    value = finite(os.getenv(name), default)
    return max(minimum, value) if minimum is not None else value


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value)


def trend_name(analysis: Any) -> str:
    trend = getattr(analysis, "trend", None)
    return str(getattr(trend, "name", trend) or "neutral").strip().lower()


def analysis_metadata(analysis: Any) -> Dict[str, Any]:
    value = getattr(analysis, "metadata", None)
    return dict(value) if isinstance(value, dict) else {}


def confidence(analysis: Any) -> float:
    value = getattr(getattr(analysis, "confidence", None), "overall", 0.0)
    return clamp(finite(value), 0.0, 1.0)


def symbol_bucket(symbol: str, target_bot: str) -> str:
    normalized, bot = symbol.upper(), target_bot.lower()
    if "chain" in bot or normalized.endswith(("-USD", "/USD", "USDT")):
        return "crypto"
    if "iron" in bot or normalized.endswith("=F"):
        return "futures"
    if "pulse" in bot:
        return "equity_beta"
    return bot or "unknown"


def infer_target_bot(symbol: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    metadata = metadata or {}
    explicit = str(metadata.get("target_bot") or metadata.get("assigned_bot") or "").strip()
    if explicit:
        return explicit
    normalized = symbol.upper()
    if normalized.endswith(("-USD", "/USD", "USDT")):
        return "sentinel-chain"
    if normalized.endswith("=F"):
        return "sentinel-iron"
    return "sentinel-pulse"


class MarketRegime(str, Enum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE = "range"
    BREAKOUT_UP = "breakout_up"
    BREAKOUT_DOWN = "breakout_down"
    HIGH_VOLATILITY = "high_volatility"
    PANIC = "panic"
    UNKNOWN = "unknown"


class TradeCardState(str, Enum):
    PROPOSED = "proposed"
    ARMED = "armed"
    ENTERING = "entering"
    ACTIVE = "active"
    REDUCING = "reducing"
    EXITING = "exiting"
    COMPLETED = "completed"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    PAUSED = "paused"


@dataclass
class RegimeAssessment:
    regime: MarketRegime
    trade_allowed: bool
    reason: str
    strength: float
    volatility_pct: float
    mtf_alignment: float
    signal_strength: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["regime"] = self.regime.value
        return data


@dataclass
class OpportunityScore:
    symbol: str
    target_bot: str
    strategy: str
    regime: str
    raw_confidence: float
    calibrated_confidence: float
    reward_risk: float
    expected_value_pct: float
    estimated_cost_pct: float
    regime_multiplier: float
    correlation_penalty: float
    score: float
    risk_budget_pct: float
    target_notional: float
    rank: int = 0
    eligible: bool = False
    reasons: list[str] = field(default_factory=list)

    def public_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TradeCard:
    card_id: str
    strategy_id: str
    thesis_id: str
    position_id: str
    symbol: str
    target_bot: str
    direction: str
    strategy: str
    state: TradeCardState
    regime: str
    created_at: str
    updated_at: str
    expires_at: Optional[str]
    entry_trigger: Optional[float]
    entry_price: Optional[float]
    maximum_entry_price: Optional[float]
    target_notional: float
    risk_budget_pct: float
    initial_stop: Optional[float]
    current_stop: Optional[float]
    targets: list[float]
    invalidation: str
    predicted_probability: float
    expected_value_pct: float
    opportunity_score: float
    position_quantity: float = 0.0
    realized_pnl: Optional[float] = None
    close_reason: Optional[str] = None
    last_feedback: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "TradeCard":
        data = dict(value)
        try:
            data["state"] = TradeCardState(str(data.get("state") or "proposed"))
        except ValueError:
            data["state"] = TradeCardState.PROPOSED
        data.setdefault("last_feedback", {})
        data.setdefault("metadata", {})
        data.setdefault("targets", [])
        return cls(**data)


@dataclass
class OutcomeRecord:
    outcome_id: str
    card_id: str
    strategy_id: str
    thesis_id: str
    position_id: str
    symbol: str
    target_bot: str
    strategy: str
    regime: str
    opened_at: str
    closed_at: str
    predicted_probability: float
    expected_value_pct: float
    realized_pnl: float
    realized_return_pct: float
    exit_reason: str
    execution_cost: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
