"""Simulation Lab feature gate and experiment discovery contract."""
from collections import defaultdict
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List

from orb import ET, MARKET_CLOSE, ORB_SESSIONS, _is_trading_day, _session_dt, _to_et


SIMULATION_LAB_ENV_FLAG = "EDGE_SIMULATION_LAB_ENABLED"
SIMULATION_LAB_STATUS_VERSION = "edge.simulation_lab.status.v1"
SIMULATION_LAB_ORB_BACKTEST_VERSION = "edge.simulation_lab.orb_backtest.v1"
SIMULATION_LAB_BUYING_POWER_VERSION = "edge.simulation_lab.buying_power_allocation.v1"
_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_BREAKOUT_SIDES = {"both", "long", "short"}
_ALLOCATION_MODES = {"confidence_weighted", "equal_weight", "priority_fill"}


class SimulationLabDisabledError(RuntimeError):
    """Raised when a gated Simulation Lab operation is requested while disabled."""


@dataclass(frozen=True)
class SimulationLabExperiment:
    """Roadmap experiment metadata surfaced before runnable lab endpoints exist."""

    id: str
    label: str
    capability: str
    status: str = "planned"
    runnable_when_enabled: bool = False

    def to_status(self, lab_enabled: bool) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "capability": self.capability,
            "status": self.status,
            "state": "visible" if lab_enabled else "hidden",
            "runnable": lab_enabled and self.runnable_when_enabled,
        }


_EXPERIMENTS = (
    SimulationLabExperiment(
        id="orb_backtest",
        label="ORB backtesting",
        capability="Replay ORB session decisions independently from live automation.",
        status="available",
        runnable_when_enabled=True,
    ),
    SimulationLabExperiment(
        id="buying_power_allocation",
        label="Buying-power allocation experiments",
        capability="Compare capital-allocation assumptions before promotion to automation settings.",
        status="available",
        runnable_when_enabled=True,
    ),
    SimulationLabExperiment(
        id="stop_trailing_dca",
        label="Stop vs trailing-stop vs DCA comparisons",
        capability="Compare exit and averaging tactics against the same historical trade stream.",
    ),
)


def _simulation_lab_enabled() -> bool:
    value = os.getenv(SIMULATION_LAB_ENV_FLAG, "")
    return value.strip().lower() in _TRUTHY_VALUES


def require_simulation_lab_enabled() -> None:
    """Raise when a runnable Simulation Lab workflow is requested while disabled."""
    if not _simulation_lab_enabled():
        raise SimulationLabDisabledError(
            f"Simulation Lab is disabled. Set {SIMULATION_LAB_ENV_FLAG}=true to run lab experiments."
        )


def simulation_lab_status() -> Dict[str, Any]:
    """Return the default-off Simulation Lab discovery payload."""
    enabled = _simulation_lab_enabled()
    return {
        "schema_version": SIMULATION_LAB_STATUS_VERSION,
        "enabled": enabled,
        "default_hidden": not enabled,
        "env_flag": SIMULATION_LAB_ENV_FLAG,
        "experiments": [experiment.to_status(enabled) for experiment in _EXPERIMENTS],
    }


def run_buying_power_allocation_experiment(
    *,
    buying_power: float,
    candidates: Iterable[Dict[str, Any]],
    mode: str = "confidence_weighted",
    cash_reserve_pct: float = 0.0,
    max_position_pct: float = 1.0,
) -> Dict[str, Any]:
    """Allocate buying power across candidate trades without touching live state."""
    buying_power = _positive_float(buying_power, "buying_power")
    cash_reserve_pct = _bounded_ratio(cash_reserve_pct, "cash_reserve_pct")
    max_position_pct = _bounded_ratio(max_position_pct, "max_position_pct", allow_zero=False)
    if mode not in _ALLOCATION_MODES:
        raise ValueError("mode must be one of: confidence_weighted, equal_weight, priority_fill")

    normalised = [_normalise_allocation_candidate(candidate, index) for index, candidate in enumerate(candidates)]
    if not normalised:
        raise ValueError("At least one allocation candidate is required")

    reserve_notional = buying_power * cash_reserve_pct
    allocatable_notional = buying_power - reserve_notional
    max_position_notional = buying_power * max_position_pct
    eligible: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    for candidate in normalised:
        remaining_position_capacity = max(0.0, max_position_notional - candidate["current_exposure"])
        candidate_cap = min(candidate["requested_notional"], remaining_position_capacity)
        if candidate_cap <= 0:
            skipped.append(_skipped_allocation(candidate, "position_limit"))
            continue
        eligible.append({**candidate, "candidate_cap": candidate_cap})

    allocations = _allocate_buying_power(
        eligible=eligible,
        allocatable_notional=allocatable_notional,
        buying_power=buying_power,
        mode=mode,
    )
    allocated_notional = round(sum(item["allocated_notional"] for item in allocations), 2)
    unallocated_notional = round(max(0.0, allocatable_notional - allocated_notional), 2)

    return {
        "schema_version": SIMULATION_LAB_BUYING_POWER_VERSION,
        "mode": mode,
        "buying_power": round(buying_power, 2),
        "cash_reserve_pct": round(cash_reserve_pct, 4),
        "max_position_pct": round(max_position_pct, 4),
        "cash_reserve_notional": round(reserve_notional, 2),
        "allocatable_notional": round(allocatable_notional, 2),
        "max_position_notional": round(max_position_notional, 2),
        "summary": {
            "candidate_count": len(normalised),
            "allocated_count": len(allocations),
            "skipped_count": len(skipped),
            "allocated_notional": allocated_notional,
            "unallocated_notional": unallocated_notional,
        },
        "allocations": allocations,
        "skipped": skipped,
    }


def _allocate_buying_power(
    *,
    eligible: List[Dict[str, Any]],
    allocatable_notional: float,
    buying_power: float,
    mode: str,
) -> List[Dict[str, Any]]:
    if not eligible or allocatable_notional <= 0:
        return []

    if mode == "priority_fill":
        ordered = sorted(eligible, key=lambda item: (-item["confidence"], item["index"]))
        remaining = allocatable_notional
        allocations = []
        for candidate in ordered:
            allocated = min(candidate["candidate_cap"], remaining)
            if allocated <= 0:
                break
            allocations.append(_allocation_payload(candidate, allocated, buying_power))
            remaining -= allocated
        return allocations

    if mode == "equal_weight":
        targets = {candidate["index"]: allocatable_notional / len(eligible) for candidate in eligible}
    else:
        confidence_total = sum(candidate["confidence"] for candidate in eligible)
        if confidence_total <= 0:
            targets = {candidate["index"]: allocatable_notional / len(eligible) for candidate in eligible}
        else:
            targets = {
                candidate["index"]: allocatable_notional * (candidate["confidence"] / confidence_total)
                for candidate in eligible
            }

    allocations = []
    for candidate in eligible:
        allocated = min(candidate["candidate_cap"], targets[candidate["index"]])
        if allocated > 0:
            allocations.append(_allocation_payload(candidate, allocated, buying_power))
    return allocations


def _normalise_allocation_candidate(candidate: Dict[str, Any], index: int) -> Dict[str, Any]:
    symbol = str(candidate.get("symbol", "")).strip().upper()
    if not symbol:
        raise ValueError("Allocation candidate symbol is required")
    return {
        "index": index,
        "symbol": symbol,
        "confidence": _bounded_ratio(candidate.get("confidence"), "confidence"),
        "requested_notional": _positive_float(candidate.get("requested_notional"), "requested_notional"),
        "current_exposure": _non_negative_float(candidate.get("current_exposure", 0.0), "current_exposure"),
    }


def _allocation_payload(candidate: Dict[str, Any], allocated: float, buying_power: float) -> Dict[str, Any]:
    allocated = round(allocated, 2)
    requested = candidate["requested_notional"]
    return {
        "symbol": candidate["symbol"],
        "confidence": round(candidate["confidence"], 4),
        "requested_notional": round(requested, 2),
        "current_exposure": round(candidate["current_exposure"], 2),
        "allocated_notional": allocated,
        "allocation_pct_of_buying_power": round(allocated / buying_power, 4),
        "fill_ratio": round(allocated / requested, 4) if requested > 0 else 0.0,
    }


def _skipped_allocation(candidate: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "symbol": candidate["symbol"],
        "confidence": round(candidate["confidence"], 4),
        "requested_notional": round(candidate["requested_notional"], 2),
        "current_exposure": round(candidate["current_exposure"], 2),
        "reason": reason,
    }


def _positive_float(value: Any, field: str) -> float:
    numeric = _coerce_float(value, field)
    if numeric <= 0:
        raise ValueError(f"{field} must be greater than 0")
    return numeric


def _non_negative_float(value: Any, field: str) -> float:
    numeric = _coerce_float(value, field)
    if numeric < 0:
        raise ValueError(f"{field} must be greater than or equal to 0")
    return numeric


def _bounded_ratio(value: Any, field: str, allow_zero: bool = True) -> float:
    numeric = _coerce_float(value, field)
    lower_ok = numeric >= 0 if allow_zero else numeric > 0
    if not lower_ok or numeric > 1:
        bound = "between 0 and 1" if allow_zero else "greater than 0 and at most 1"
        raise ValueError(f"{field} must be {bound}")
    return numeric


def _coerce_float(value: Any, field: str) -> float:
    if value is None:
        raise ValueError(f"{field} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc


def run_orb_backtest_replay(
    *,
    symbol: str,
    bars: Iterable[Dict[str, Any]],
    session_id: str = "market_open",
    timeframe_minutes: int = 30,
    breakout_side: str = "both",
) -> Dict[str, Any]:
    """Replay explicit OHLC bars through a deterministic ORB breakout scan."""
    session = ORB_SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"Unknown ORB session: {session_id}")
    if timeframe_minutes not in session.timeframes:
        raise ValueError(f"Timeframe {timeframe_minutes}m is not valid for ORB session {session_id}")
    if breakout_side not in _BREAKOUT_SIDES:
        raise ValueError("breakout_side must be one of: both, long, short")

    normalised_bars = sorted((_normalise_orb_bar(bar) for bar in bars), key=lambda bar: bar["timestamp"])
    if not normalised_bars:
        raise ValueError("At least one OHLC bar is required for ORB replay")

    grouped: Dict[date, List[Dict[str, Any]]] = defaultdict(list)
    for bar in normalised_bars:
        grouped[bar["timestamp"].date()].append(bar)

    days = [
        _run_orb_backtest_day(
            et_date=et_date,
            bars=day_bars,
            session_id=session_id,
            timeframe_minutes=timeframe_minutes,
            breakout_side=breakout_side,
        )
        for et_date, day_bars in sorted(grouped.items(), key=lambda item: item[0])
    ]

    completed_days = [day for day in days if day["status"] == "completed"]
    breakouts = [day["breakout"] for day in completed_days if day["breakout"] is not None]
    return {
        "schema_version": SIMULATION_LAB_ORB_BACKTEST_VERSION,
        "symbol": symbol.strip().upper(),
        "session_id": session_id,
        "timeframe_minutes": timeframe_minutes,
        "breakout_side": breakout_side,
        "summary": {
            "sessions": len(days),
            "completed_sessions": len(completed_days),
            "breakouts": len(breakouts),
            "bullish_breakouts": sum(1 for breakout in breakouts if breakout["direction"] == "bullish"),
            "bearish_breakouts": sum(1 for breakout in breakouts if breakout["direction"] == "bearish"),
            "no_breakout_sessions": sum(1 for day in completed_days if day["breakout"] is None),
        },
        "days": days,
    }


def _run_orb_backtest_day(
    *,
    et_date: date,
    bars: List[Dict[str, Any]],
    session_id: str,
    timeframe_minutes: int,
    breakout_side: str,
) -> Dict[str, Any]:
    if not _is_trading_day(et_date):
        return {
            "date": et_date.isoformat(),
            "status": "skipped_non_trading_day",
            "orb_high": None,
            "orb_low": None,
            "range_width": 0.0,
            "breakout": None,
        }

    session = ORB_SESSIONS[session_id]
    session_start = _session_dt(et_date, session.start)
    lock_time = session_start + timedelta(minutes=timeframe_minutes)
    market_close = _session_dt(et_date, MARKET_CLOSE)
    range_bars = [bar for bar in bars if session_start <= bar["timestamp"] < lock_time]
    if not range_bars:
        return {
            "date": et_date.isoformat(),
            "status": "missing_orb_range",
            "session_start": session_start.isoformat(),
            "lock_time": lock_time.isoformat(),
            "orb_high": None,
            "orb_low": None,
            "range_width": 0.0,
            "breakout": None,
        }

    orb_high = max(bar["high"] for bar in range_bars)
    orb_low = min(bar["low"] for bar in range_bars)
    replay_bars = [bar for bar in bars if lock_time <= bar["timestamp"] <= market_close]
    breakout = _first_orb_breakout(replay_bars, orb_high, orb_low, breakout_side)
    return {
        "date": et_date.isoformat(),
        "status": "completed",
        "session_start": session_start.isoformat(),
        "lock_time": lock_time.isoformat(),
        "orb_high": round(orb_high, 4),
        "orb_low": round(orb_low, 4),
        "range_width": round(orb_high - orb_low, 4),
        "bars_in_range": len(range_bars),
        "bars_scanned": len(replay_bars),
        "breakout": breakout,
    }


def _first_orb_breakout(
    bars: Iterable[Dict[str, Any]],
    orb_high: float,
    orb_low: float,
    breakout_side: str,
) -> Dict[str, Any] | None:
    for bar in bars:
        if breakout_side in {"both", "long"} and bar["high"] > orb_high:
            return _breakout_payload("bullish", bar, bar["high"], orb_high, orb_low)
        if breakout_side in {"both", "short"} and bar["low"] < orb_low:
            return _breakout_payload("bearish", bar, bar["low"], orb_high, orb_low)
    return None


def _breakout_payload(
    direction: str,
    bar: Dict[str, Any],
    price: float,
    orb_high: float,
    orb_low: float,
) -> Dict[str, Any]:
    return {
        "direction": direction,
        "timestamp": bar["timestamp"].isoformat(),
        "price": round(price, 4),
        "close": round(bar["close"], 4),
        "orb_high": round(orb_high, 4),
        "orb_low": round(orb_low, 4),
    }


def _normalise_orb_bar(bar: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = _parse_bar_timestamp(bar.get("timestamp"))
    high = _required_float(bar, "high")
    low = _required_float(bar, "low")
    close = _required_float(bar, "close")
    if high < low:
        raise ValueError("ORB replay bar high cannot be below low")
    return {
        "timestamp": timestamp,
        "high": high,
        "low": low,
        "close": close,
    }


def _parse_bar_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _to_et(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ORB replay bar timestamp is required")
    raw_value = value.strip()
    parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    return _to_et(parsed).astimezone(ET)


def _required_float(bar: Dict[str, Any], field: str) -> float:
    value = bar.get(field)
    if value is None:
        raise ValueError(f"ORB replay bar {field} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"ORB replay bar {field} must be numeric") from exc
