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
SIMULATION_LAB_STOP_TRAILING_DCA_VERSION = "edge.simulation_lab.stop_trailing_dca.v1"
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
    endpoint_path: str
    result_schema_version: str
    http_method: str = "POST"
    status: str = "planned"
    runnable_when_enabled: bool = False

    def to_status(self, lab_enabled: bool) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "capability": self.capability,
            "http_method": self.http_method,
            "endpoint_path": self.endpoint_path,
            "result_schema_version": self.result_schema_version,
            "status": self.status,
            "state": "visible" if lab_enabled else "hidden",
            "runnable": lab_enabled and self.runnable_when_enabled,
        }


_EXPERIMENTS = (
    SimulationLabExperiment(
        id="orb_backtest",
        label="ORB backtesting",
        capability="Replay ORB session decisions independently from live automation.",
        endpoint_path="/api/simulation-lab/orb/backtest",
        result_schema_version=SIMULATION_LAB_ORB_BACKTEST_VERSION,
        status="available",
        runnable_when_enabled=True,
    ),
    SimulationLabExperiment(
        id="buying_power_allocation",
        label="Buying-power allocation experiments",
        capability="Compare capital-allocation assumptions before promotion to automation settings.",
        endpoint_path="/api/simulation-lab/buying-power/allocation",
        result_schema_version=SIMULATION_LAB_BUYING_POWER_VERSION,
        status="available",
        runnable_when_enabled=True,
    ),
    SimulationLabExperiment(
        id="stop_trailing_dca",
        label="Stop vs trailing-stop vs DCA comparisons",
        capability="Compare exit and averaging tactics against the same historical trade stream.",
        endpoint_path="/api/simulation-lab/stop-trailing-dca/compare",
        result_schema_version=SIMULATION_LAB_STOP_TRAILING_DCA_VERSION,
        status="available",
        runnable_when_enabled=True,
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


def run_stop_trailing_dca_comparison(
    *,
    entry_price: float,
    price_path: Iterable[Dict[str, Any]],
    quantity: float = 1.0,
    stop_loss_pct: float = 0.05,
    trailing_pct: float = 0.03,
    dca_steps: int = 1,
    dca_drop_pct: float = 0.03,
    dca_allocation_multiplier: float = 1.0,
) -> Dict[str, Any]:
    """Compare fixed-stop, trailing-stop, and DCA outcomes against one long price path."""
    entry_price = _positive_float(entry_price, "entry_price")
    quantity = _positive_float(quantity, "quantity")
    stop_loss_pct = _bounded_ratio(stop_loss_pct, "stop_loss_pct", allow_zero=False)
    trailing_pct = _bounded_ratio(trailing_pct, "trailing_pct", allow_zero=False)
    dca_steps = _bounded_int(dca_steps, "dca_steps", minimum=0, maximum=50)
    dca_drop_pct = _bounded_ratio(dca_drop_pct, "dca_drop_pct", allow_zero=False)
    dca_allocation_multiplier = _positive_float(dca_allocation_multiplier, "dca_allocation_multiplier")

    bars = sorted(
        (_normalise_comparison_bar(bar) for bar in price_path),
        key=lambda bar: bar["timestamp"],
    )
    if not bars:
        raise ValueError("At least one price_path bar is required")

    plans = [
        _simulate_regular_stop_plan(
            entry_price=entry_price,
            quantity=quantity,
            stop_loss_pct=stop_loss_pct,
            bars=bars,
        ),
        _simulate_trailing_stop_plan(
            entry_price=entry_price,
            quantity=quantity,
            trailing_pct=trailing_pct,
            bars=bars,
        ),
        _simulate_dca_plan(
            entry_price=entry_price,
            quantity=quantity,
            dca_steps=dca_steps,
            dca_drop_pct=dca_drop_pct,
            dca_allocation_multiplier=dca_allocation_multiplier,
            bars=bars,
        ),
    ]
    best_plan = max(plans, key=lambda plan: plan["pnl"])
    worst_plan = min(plans, key=lambda plan: plan["pnl"])

    return {
        "schema_version": SIMULATION_LAB_STOP_TRAILING_DCA_VERSION,
        "side": "long",
        "entry_price": round(entry_price, 4),
        "quantity": round(quantity, 4),
        "price_points": len(bars),
        "parameters": {
            "stop_loss_pct": round(stop_loss_pct, 4),
            "trailing_pct": round(trailing_pct, 4),
            "dca_steps": dca_steps,
            "dca_drop_pct": round(dca_drop_pct, 4),
            "dca_allocation_multiplier": round(dca_allocation_multiplier, 4),
        },
        "summary": {
            "plan_count": len(plans),
            "best_plan": best_plan["plan"],
            "best_pnl": best_plan["pnl"],
            "worst_plan": worst_plan["plan"],
            "worst_pnl": worst_plan["pnl"],
        },
        "plans": plans,
    }


def _simulate_regular_stop_plan(
    *,
    entry_price: float,
    quantity: float,
    stop_loss_pct: float,
    bars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    stop_price = entry_price * (1 - stop_loss_pct)
    for bar in bars:
        if bar["low"] <= stop_price:
            return _comparison_plan_payload(
                plan="regular_stop",
                entry_price=entry_price,
                average_entry_price=entry_price,
                quantity=quantity,
                exit_price=stop_price,
                exit_timestamp=bar["timestamp"],
                exit_reason="stop_loss",
                extra={"stop_price": round(stop_price, 4)},
            )
    final_bar = bars[-1]
    return _comparison_plan_payload(
        plan="regular_stop",
        entry_price=entry_price,
        average_entry_price=entry_price,
        quantity=quantity,
        exit_price=final_bar["close"],
        exit_timestamp=final_bar["timestamp"],
        exit_reason="final_close",
        extra={"stop_price": round(stop_price, 4)},
    )


def _simulate_trailing_stop_plan(
    *,
    entry_price: float,
    quantity: float,
    trailing_pct: float,
    bars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    highest_high = entry_price
    trailing_stop = entry_price * (1 - trailing_pct)
    for bar in bars:
        highest_high = max(highest_high, bar["high"])
        trailing_stop = max(trailing_stop, highest_high * (1 - trailing_pct))
        if bar["low"] <= trailing_stop:
            return _comparison_plan_payload(
                plan="trailing_stop",
                entry_price=entry_price,
                average_entry_price=entry_price,
                quantity=quantity,
                exit_price=trailing_stop,
                exit_timestamp=bar["timestamp"],
                exit_reason="trailing_stop",
                extra={
                    "highest_high": round(highest_high, 4),
                    "trailing_stop": round(trailing_stop, 4),
                },
            )
    final_bar = bars[-1]
    return _comparison_plan_payload(
        plan="trailing_stop",
        entry_price=entry_price,
        average_entry_price=entry_price,
        quantity=quantity,
        exit_price=final_bar["close"],
        exit_timestamp=final_bar["timestamp"],
        exit_reason="final_close",
        extra={
            "highest_high": round(highest_high, 4),
            "trailing_stop": round(trailing_stop, 4),
        },
    )


def _simulate_dca_plan(
    *,
    entry_price: float,
    quantity: float,
    dca_steps: int,
    dca_drop_pct: float,
    dca_allocation_multiplier: float,
    bars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    total_quantity = quantity
    total_cost = entry_price * quantity
    fill_quantity = quantity * dca_allocation_multiplier
    fills: List[Dict[str, Any]] = []

    for bar in bars:
        while len(fills) < dca_steps:
            step = len(fills) + 1
            trigger_price = entry_price * (1 - dca_drop_pct * step)
            if trigger_price <= 0 or bar["low"] > trigger_price:
                break
            total_quantity += fill_quantity
            total_cost += trigger_price * fill_quantity
            fills.append(
                {
                    "step": step,
                    "timestamp": bar["timestamp"].isoformat(),
                    "price": round(trigger_price, 4),
                    "quantity": round(fill_quantity, 4),
                }
            )

    final_bar = bars[-1]
    average_entry_price = total_cost / total_quantity
    return _comparison_plan_payload(
        plan="dca",
        entry_price=entry_price,
        average_entry_price=average_entry_price,
        quantity=total_quantity,
        exit_price=final_bar["close"],
        exit_timestamp=final_bar["timestamp"],
        exit_reason="final_close",
        extra={
            "dca_fills": len(fills),
            "fills": fills,
        },
    )


def _comparison_plan_payload(
    *,
    plan: str,
    entry_price: float,
    average_entry_price: float,
    quantity: float,
    exit_price: float,
    exit_timestamp: datetime,
    exit_reason: str,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    invested_notional = average_entry_price * quantity
    pnl = (exit_price - average_entry_price) * quantity
    payload = {
        "plan": plan,
        "side": "long",
        "entry_price": round(entry_price, 4),
        "average_entry_price": round(average_entry_price, 4),
        "quantity": round(quantity, 4),
        "exit_price": round(exit_price, 4),
        "exit_timestamp": exit_timestamp.isoformat(),
        "exit_reason": exit_reason,
        "invested_notional": round(invested_notional, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round((pnl / invested_notional) * 100, 4) if invested_notional > 0 else 0.0,
    }
    if extra:
        payload.update(extra)
    return payload


def _normalise_comparison_bar(bar: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = _parse_lab_timestamp(bar.get("timestamp"), "price_path bar")
    close = _required_price_path_float(bar, "close")
    high = close if bar.get("high") is None else _required_price_path_float(bar, "high")
    low = close if bar.get("low") is None else _required_price_path_float(bar, "low")
    if high < low:
        raise ValueError("price_path bar high cannot be below low")
    return {
        "timestamp": timestamp,
        "high": high,
        "low": low,
        "close": close,
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


def _bounded_int(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if numeric < minimum or numeric > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
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
    target_r_multiple: float = 2.0,
) -> Dict[str, Any]:
    """Replay explicit OHLC bars through a deterministic ORB breakout scan."""
    session = ORB_SESSIONS.get(session_id)
    if session is None:
        raise ValueError(f"Unknown ORB session: {session_id}")
    if timeframe_minutes not in session.timeframes:
        raise ValueError(f"Timeframe {timeframe_minutes}m is not valid for ORB session {session_id}")
    if breakout_side not in _BREAKOUT_SIDES:
        raise ValueError("breakout_side must be one of: both, long, short")
    target_r_multiple = _positive_float(target_r_multiple, "target_r_multiple")

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
            target_r_multiple=target_r_multiple,
        )
        for et_date, day_bars in sorted(grouped.items(), key=lambda item: item[0])
    ]

    completed_days = [day for day in days if day["status"] == "completed"]
    breakouts = [day["breakout"] for day in completed_days if day["breakout"] is not None]
    risk_reward_scores = [
        breakout["risk_reward"]
        for breakout in breakouts
        if breakout.get("risk_reward") is not None
    ]
    outcome_scores = [
        breakout["outcome"]
        for breakout in breakouts
        if breakout.get("outcome") is not None
    ]
    return {
        "schema_version": SIMULATION_LAB_ORB_BACKTEST_VERSION,
        "symbol": symbol.strip().upper(),
        "session_id": session_id,
        "timeframe_minutes": timeframe_minutes,
        "breakout_side": breakout_side,
        "parameters": {
            "target_r_multiple": round(target_r_multiple, 4),
            "stop_model": "opposite_orb_boundary",
        },
        "summary": {
            "sessions": len(days),
            "completed_sessions": len(completed_days),
            "breakouts": len(breakouts),
            "bullish_breakouts": sum(1 for breakout in breakouts if breakout["direction"] == "bullish"),
            "bearish_breakouts": sum(1 for breakout in breakouts if breakout["direction"] == "bearish"),
            "no_breakout_sessions": sum(1 for day in completed_days if day["breakout"] is None),
            "scored_breakouts": len(risk_reward_scores),
            "avg_reward_r_multiple": _average_metric(risk_reward_scores, "reward_r_multiple"),
            "max_risk_per_share": _max_metric(risk_reward_scores, "risk_per_share"),
            "max_reward_per_share": _max_metric(risk_reward_scores, "reward_per_share"),
            "outcome_scored_breakouts": len(outcome_scores),
            "target_hits": _count_outcome_status(outcome_scores, "target_hit"),
            "stop_hits": _count_outcome_status(outcome_scores, "stop_hit"),
            "open_after_replay": _count_outcome_status(outcome_scores, "open_after_replay"),
            "avg_realized_r_multiple": _average_metric(outcome_scores, "realized_r_multiple"),
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
    target_r_multiple: float,
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
    breakout, breakout_index = _first_orb_breakout(replay_bars, orb_high, orb_low, breakout_side, target_r_multiple)
    if breakout is not None and breakout_index is not None:
        breakout["outcome"] = _orb_outcome_payload(
            direction=breakout["direction"],
            risk_reward=breakout["risk_reward"],
            bars_after_breakout=replay_bars[breakout_index + 1:],
        )
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
    target_r_multiple: float,
) -> tuple[Dict[str, Any] | None, int | None]:
    for index, bar in enumerate(bars):
        if breakout_side in {"both", "long"} and bar["high"] > orb_high:
            return _breakout_payload("bullish", bar, bar["high"], orb_high, orb_low, target_r_multiple), index
        if breakout_side in {"both", "short"} and bar["low"] < orb_low:
            return _breakout_payload("bearish", bar, bar["low"], orb_high, orb_low, target_r_multiple), index
    return None, None


def _breakout_payload(
    direction: str,
    bar: Dict[str, Any],
    price: float,
    orb_high: float,
    orb_low: float,
    target_r_multiple: float,
) -> Dict[str, Any]:
    return {
        "direction": direction,
        "timestamp": bar["timestamp"].isoformat(),
        "price": round(price, 4),
        "close": round(bar["close"], 4),
        "orb_high": round(orb_high, 4),
        "orb_low": round(orb_low, 4),
        "risk_reward": _orb_risk_reward_payload(direction, price, orb_high, orb_low, target_r_multiple),
    }


def _orb_risk_reward_payload(
    direction: str,
    entry_price: float,
    orb_high: float,
    orb_low: float,
    target_r_multiple: float,
) -> Dict[str, Any]:
    if direction == "bullish":
        stop_price = orb_low
        stop_source = "orb_low"
        risk_per_share = entry_price - stop_price
        target_price = entry_price + (risk_per_share * target_r_multiple)
    else:
        stop_price = orb_high
        stop_source = "orb_high"
        risk_per_share = stop_price - entry_price
        target_price = entry_price - (risk_per_share * target_r_multiple)

    reward_per_share = abs(target_price - entry_price)
    return {
        "entry_price": round(entry_price, 4),
        "stop_price": round(stop_price, 4),
        "stop_source": stop_source,
        "target_price": round(target_price, 4),
        "risk_per_share": round(risk_per_share, 4),
        "reward_per_share": round(reward_per_share, 4),
        "reward_r_multiple": round(reward_per_share / risk_per_share, 4) if risk_per_share > 0 else 0.0,
    }


def _orb_outcome_payload(
    *,
    direction: str,
    risk_reward: Dict[str, Any],
    bars_after_breakout: List[Dict[str, Any]],
) -> Dict[str, Any]:
    entry_price = float(risk_reward["entry_price"])
    stop_price = float(risk_reward["stop_price"])
    target_price = float(risk_reward["target_price"])
    risk_per_share = float(risk_reward["risk_per_share"])

    for bars_to_outcome, bar in enumerate(bars_after_breakout, start=1):
        target_hit = _orb_target_hit(direction, bar, target_price)
        stop_hit = _orb_stop_hit(direction, bar, stop_price)
        if stop_hit:
            return _orb_exit_payload(
                status="stop_hit",
                exit_source="stop",
                exit_price=stop_price,
                timestamp=bar["timestamp"],
                bars_to_outcome=bars_to_outcome,
                realized_r_multiple=-1.0,
            )
        if target_hit:
            return _orb_exit_payload(
                status="target_hit",
                exit_source="target",
                exit_price=target_price,
                timestamp=bar["timestamp"],
                bars_to_outcome=bars_to_outcome,
                realized_r_multiple=risk_reward["reward_r_multiple"],
            )

    if bars_after_breakout:
        last_bar = bars_after_breakout[-1]
        exit_price = last_bar["close"]
        realized_r_multiple = _realized_r_multiple(direction, entry_price, exit_price, risk_per_share)
        return _orb_exit_payload(
            status="open_after_replay",
            exit_source="last_close",
            exit_price=exit_price,
            timestamp=last_bar["timestamp"],
            bars_to_outcome=len(bars_after_breakout),
            realized_r_multiple=realized_r_multiple,
        )

    return {
        "status": "open_after_replay",
        "exit_source": "no_post_breakout_bar",
        "timestamp": None,
        "exit_price": None,
        "bars_to_outcome": 0,
        "realized_r_multiple": 0.0,
    }


def _orb_target_hit(direction: str, bar: Dict[str, Any], target_price: float) -> bool:
    if direction == "bullish":
        return bar["high"] >= target_price
    return bar["low"] <= target_price


def _orb_stop_hit(direction: str, bar: Dict[str, Any], stop_price: float) -> bool:
    if direction == "bullish":
        return bar["low"] <= stop_price
    return bar["high"] >= stop_price


def _realized_r_multiple(direction: str, entry_price: float, exit_price: float, risk_per_share: float) -> float:
    if risk_per_share <= 0:
        return 0.0
    if direction == "bullish":
        return round((exit_price - entry_price) / risk_per_share, 4)
    return round((entry_price - exit_price) / risk_per_share, 4)


def _orb_exit_payload(
    *,
    status: str,
    exit_source: str,
    exit_price: float,
    timestamp: datetime,
    bars_to_outcome: int,
    realized_r_multiple: float,
) -> Dict[str, Any]:
    return {
        "status": status,
        "exit_source": exit_source,
        "timestamp": timestamp.isoformat(),
        "exit_price": round(exit_price, 4),
        "bars_to_outcome": bars_to_outcome,
        "realized_r_multiple": round(float(realized_r_multiple), 4),
    }


def _count_outcome_status(items: List[Dict[str, Any]], status: str) -> int:
    return sum(1 for item in items if item.get("status") == status)


def _average_metric(items: List[Dict[str, Any]], field: str) -> float:
    if not items:
        return 0.0
    return round(sum(float(item[field]) for item in items) / len(items), 4)


def _max_metric(items: List[Dict[str, Any]], field: str) -> float:
    if not items:
        return 0.0
    return round(max(float(item[field]) for item in items), 4)


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


def _parse_lab_timestamp(value: Any, label: str) -> datetime:
    if isinstance(value, datetime):
        return _to_et(value)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} timestamp is required")
    raw_value = value.strip()
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} timestamp must be ISO-8601") from exc
    return _to_et(parsed).astimezone(ET)


def _required_float(bar: Dict[str, Any], field: str) -> float:
    value = bar.get(field)
    if value is None:
        raise ValueError(f"ORB replay bar {field} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"ORB replay bar {field} must be numeric") from exc


def _required_price_path_float(bar: Dict[str, Any], field: str) -> float:
    value = bar.get(field)
    if value is None:
        raise ValueError(f"price_path bar {field} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"price_path bar {field} must be numeric") from exc
