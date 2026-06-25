"""Support/resistance level ranking and option-position directive evaluation."""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import isfinite
import re
from typing import Any, Dict, Iterable, List, Sequence


LEVELS_SCHEMA_VERSION = "edge.support_resistance.levels.v1"
DIRECTIVE_SCHEMA_VERSION = "edge.sr.directive.v1"
BREAK_CONFIRMATION_MODES = {"tick_break", "candle_close_break"}

DEFAULT_SETTINGS: Dict[str, Any] = {
    "opening_range_minutes": 30,
    "swing_window": 2,
    "break_confirmation": "tick_break",
    "break_buffer_pct": 0.0,
    "confirming_closes": 1,
    "scale_in_fraction": 0.25,
    "scale_in_sizing_mode": "buying_power_fraction",
    "minimum_scale_in_contracts": 1,
    "max_scale_ins_per_position": 1,
    "scale_in_cooldown_seconds": 300,
    "one_scale_in_per_level": True,
    "strict_0dte_exits_enabled": True,
    "stop_trading_after_time_enabled": False,
    "pre_close_trailing_rescue_enabled": False,
    "session_id": "",
    "now": None,
}


class SupportResistanceDirectiveState:
    """In-memory guardrail for repeated S/R scale-in directives."""

    def __init__(self) -> None:
        self._scale_ins: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        self._scale_ins.clear()

    def allow_and_record(self, directive: Dict[str, Any], settings: Dict[str, Any]) -> bool:
        if directive.get("action") != "request_scale_in":
            return True

        metadata = directive.get("metadata") if isinstance(directive.get("metadata"), dict) else {}
        position = directive.get("position") if isinstance(directive.get("position"), dict) else {}
        level = directive.get("level") if isinstance(directive.get("level"), dict) else {}
        session_id = _safe_identifier(metadata.get("session_id") or settings.get("session_id") or "default")
        position_id = _position_identity(position)
        level_id = _safe_identifier(level.get("id") or level.get("kind") or "level")
        key = f"{session_id}:{position_id}"
        level_key = f"{key}:{level_id}"
        now = _settings_now(settings)

        record = self._scale_ins.setdefault(
            key,
            {"count": 0, "levels": set(), "last_at": None},
        )

        if bool(settings["one_scale_in_per_level"]) and level_key in record["levels"]:
            return False

        cooldown_seconds = int(settings["scale_in_cooldown_seconds"])
        last_at = record.get("last_at")
        if cooldown_seconds > 0 and isinstance(last_at, datetime):
            if (now - last_at).total_seconds() < cooldown_seconds:
                return False

        if int(record["count"]) >= int(settings["max_scale_ins_per_position"]):
            return False

        record["count"] = int(record["count"]) + 1
        record["levels"].add(level_key)
        record["last_at"] = now
        return True


support_resistance_directive_state = SupportResistanceDirectiveState()


def build_support_resistance_levels(
    *,
    symbol: str,
    bars: Iterable[Dict[str, Any]],
    current_price: float | None = None,
    settings: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build ranked support/resistance levels from supplied OHLCV bars."""
    resolved_settings = _settings(settings)
    normalised_bars = sorted((_normalise_bar(bar) for bar in bars), key=lambda item: item["timestamp"])
    if not normalised_bars:
        raise ValueError("At least one support/resistance bar is required")

    latest = normalised_bars[-1]
    numeric_current_price = _optional_float(current_price)
    if numeric_current_price is None:
        numeric_current_price = latest["close"]

    latest_date = latest["timestamp"].date()
    current_day_bars = [bar for bar in normalised_bars if bar["timestamp"].date() == latest_date] or normalised_bars
    prior_day_bars = [bar for bar in normalised_bars if bar["timestamp"].date() < latest_date]
    session_bars = [bar for bar in current_day_bars if _is_regular_session_bar(bar["timestamp"])] or current_day_bars
    premarket_bars = [bar for bar in current_day_bars if _is_premarket_bar(bar["timestamp"])]
    opening_range_bars = [
        bar
        for bar in session_bars
        if _is_opening_range_bar(bar["timestamp"], int(resolved_settings["opening_range_minutes"]))
    ]

    levels: List[Dict[str, Any]] = []
    timestamp = latest["timestamp"]
    _append_high_low_levels(
        levels,
        prefix="session",
        label_prefix="Session",
        bars=session_bars,
        source="ohlcv",
        session="regular",
        timestamp=timestamp,
        confidence=0.9,
        locked=False,
        priority=95,
    )
    if prior_day_bars:
        _append_high_low_levels(
            levels,
            prefix="prior_day",
            label_prefix="Prior day",
            bars=prior_day_bars,
            source="ohlcv",
            session="prior_day",
            timestamp=timestamp,
            confidence=0.85,
            locked=True,
            priority=85,
        )
    if premarket_bars:
        _append_high_low_levels(
            levels,
            prefix="premarket",
            label_prefix="Premarket",
            bars=premarket_bars,
            source="ohlcv",
            session="premarket",
            timestamp=timestamp,
            confidence=0.8,
            locked=True,
            priority=80,
        )
    if opening_range_bars:
        _append_high_low_levels(
            levels,
            prefix="opening_range",
            label_prefix="Opening range",
            bars=opening_range_bars,
            source="ohlcv",
            session="regular",
            timestamp=timestamp,
            confidence=0.8,
            locked=False,
            priority=88,
        )

    latest_vwap = _latest_value(_vwap_series(current_day_bars))
    if latest_vwap is not None:
        levels.append(
            _level_item(
                "vwap",
                "VWAP",
                "vwap",
                _role_for_neutral_price(latest_vwap, numeric_current_price),
                latest_vwap,
                "computed",
                "session",
                timestamp,
                0.85,
                False,
                76,
            )
        )

    latest_atr = _latest_value(_atr_series(current_day_bars, min(14, max(2, len(current_day_bars)))))
    if latest_atr is not None:
        levels.append(
            _level_item(
                "atr_upper",
                "ATR upper",
                "atr_upper",
                "resistance",
                latest["close"] + latest_atr,
                "computed",
                "session",
                timestamp,
                0.7,
                False,
                62,
            )
        )
        levels.append(
            _level_item(
                "atr_lower",
                "ATR lower",
                "atr_lower",
                "support",
                latest["close"] - latest_atr,
                "computed",
                "session",
                timestamp,
                0.7,
                False,
                62,
            )
        )

    levels.extend(
        _swing_levels(
            current_day_bars,
            window=int(resolved_settings["swing_window"]),
            timestamp=timestamp,
        )
    )

    ranked = _rank_levels(levels, numeric_current_price)
    return {
        "schema_version": LEVELS_SCHEMA_VERSION,
        "symbol": _symbol(symbol),
        "current_price": round(numeric_current_price, 4),
        "settings": {
            "opening_range_minutes": int(resolved_settings["opening_range_minutes"]),
            "swing_window": int(resolved_settings["swing_window"]),
        },
        "items": ranked,
    }


def evaluate_support_resistance_position(
    *,
    position: Dict[str, Any],
    levels: Sequence[Dict[str, Any]],
    current_price: float,
    settings: Dict[str, Any] | None = None,
    bars: Sequence[Dict[str, Any]] | None = None,
    state: SupportResistanceDirectiveState | None = None,
) -> Dict[str, Any] | None:
    """Evaluate one option position against S/R levels and return a directive."""
    resolved_settings = _settings(settings)
    numeric_current_price = _required_float(current_price, "current_price")
    option_side = _option_side(position.get("option_side") or position.get("side") or position.get("direction"))
    confirmation_bars = _confirmation_bars(bars, resolved_settings)
    support_break = _nearest_broken_level(
        levels,
        role="support",
        current_price=numeric_current_price,
        break_buffer_pct=float(resolved_settings["break_buffer_pct"]),
        settings=resolved_settings,
        bars=confirmation_bars,
    )
    resistance_break = _nearest_broken_level(
        levels,
        role="resistance",
        current_price=numeric_current_price,
        break_buffer_pct=float(resolved_settings["break_buffer_pct"]),
        settings=resolved_settings,
        bars=confirmation_bars,
    )

    directive = None
    if option_side == "call" and support_break:
        directive = _directive(
            action="close_position",
            reason_code="call_support_break",
            position=position,
            level=support_break,
            current_price=numeric_current_price,
            settings=resolved_settings,
        )
    elif option_side == "put" and resistance_break:
        directive = _directive(
            action="close_position",
            reason_code="put_resistance_break",
            position=position,
            level=resistance_break,
            current_price=numeric_current_price,
            settings=resolved_settings,
        )
    elif option_side == "call" and resistance_break:
        directive = _directive(
            action="request_scale_in",
            reason_code="call_resistance_break",
            position=position,
            level=resistance_break,
            current_price=numeric_current_price,
            settings=resolved_settings,
        )
    elif option_side == "put" and support_break:
        directive = _directive(
            action="request_scale_in",
            reason_code="put_support_break",
            position=position,
            level=support_break,
            current_price=numeric_current_price,
            settings=resolved_settings,
        )

    if directive is None:
        return None
    if state is not None and not state.allow_and_record(directive, resolved_settings):
        return None
    return directive


def _settings(settings: Dict[str, Any] | None) -> Dict[str, Any]:
    resolved = dict(DEFAULT_SETTINGS)
    if isinstance(settings, dict):
        for key, value in settings.items():
            if key in resolved and value is not None:
                resolved[key] = value
    resolved["opening_range_minutes"] = _clamp_int(resolved["opening_range_minutes"], 1, 120)
    resolved["swing_window"] = _clamp_int(resolved["swing_window"], 1, 20)
    resolved["break_confirmation"] = _break_confirmation_mode(resolved["break_confirmation"])
    resolved["break_buffer_pct"] = _clamp_float(resolved["break_buffer_pct"], 0.0, 0.05)
    resolved["confirming_closes"] = _strict_int(resolved["confirming_closes"], "confirming_closes", 1, 20)
    resolved["scale_in_fraction"] = _clamp_float(resolved["scale_in_fraction"], 0.01, 1.0)
    resolved["minimum_scale_in_contracts"] = _clamp_int(resolved["minimum_scale_in_contracts"], 1, 1000)
    resolved["max_scale_ins_per_position"] = _strict_int(
        resolved["max_scale_ins_per_position"],
        "max_scale_ins_per_position",
        0,
        1000,
    )
    resolved["scale_in_cooldown_seconds"] = _strict_int(
        resolved["scale_in_cooldown_seconds"],
        "scale_in_cooldown_seconds",
        0,
        86400,
    )
    resolved["one_scale_in_per_level"] = _bool_value(resolved["one_scale_in_per_level"])
    return resolved


def _append_high_low_levels(
    levels: List[Dict[str, Any]],
    *,
    prefix: str,
    label_prefix: str,
    bars: Sequence[Dict[str, Any]],
    source: str,
    session: str,
    timestamp: datetime,
    confidence: float,
    locked: bool,
    priority: int,
) -> None:
    levels.append(
        _level_item(
            f"{prefix}_high",
            f"{label_prefix} high",
            f"{prefix}_high",
            "resistance",
            max(bar["high"] for bar in bars),
            source,
            session,
            timestamp,
            confidence,
            locked,
            priority,
        )
    )
    levels.append(
        _level_item(
            f"{prefix}_low",
            f"{label_prefix} low",
            f"{prefix}_low",
            "support",
            min(bar["low"] for bar in bars),
            source,
            session,
            timestamp,
            confidence,
            locked,
            priority,
        )
    )


def _swing_levels(
    bars: Sequence[Dict[str, Any]],
    *,
    window: int,
    timestamp: datetime,
) -> List[Dict[str, Any]]:
    if len(bars) < (window * 2) + 1:
        return []

    levels: List[Dict[str, Any]] = []
    for index in range(window, len(bars) - window):
        bar = bars[index]
        left = bars[index - window : index]
        right = bars[index + 1 : index + 1 + window]
        if all(bar["high"] > neighbor["high"] for neighbor in [*left, *right]):
            levels.append(
                _level_item(
                    f"swing_high_{index}",
                    "Swing high",
                    "swing_high",
                    "resistance",
                    bar["high"],
                    "computed",
                    "intraday",
                    timestamp,
                    0.72,
                    False,
                    70,
                )
            )
        if all(bar["low"] < neighbor["low"] for neighbor in [*left, *right]):
            levels.append(
                _level_item(
                    f"swing_low_{index}",
                    "Swing low",
                    "swing_low",
                    "support",
                    bar["low"],
                    "computed",
                    "intraday",
                    timestamp,
                    0.72,
                    False,
                    70,
                )
            )
    return levels


def _level_item(
    level_id: str,
    label: str,
    kind: str,
    role: str,
    price: float,
    source: str,
    session: str,
    timestamp: datetime,
    confidence: float,
    locked: bool,
    priority: int,
) -> Dict[str, Any]:
    return {
        "id": level_id,
        "label": label,
        "kind": kind,
        "role": role,
        "price": round(float(price), 4),
        "source": source,
        "session": session,
        "confidence": round(float(confidence), 4),
        "timestamp": timestamp.isoformat(),
        "locked": bool(locked),
        "priority": int(priority),
    }


def _rank_levels(levels: Sequence[Dict[str, Any]], current_price: float) -> List[Dict[str, Any]]:
    ranked: List[Dict[str, Any]] = []
    for level in levels:
        price = _optional_float(level.get("price"))
        if price is None:
            continue
        item = dict(level)
        item["distance_pct"] = round(abs(price - current_price) / max(abs(current_price), 0.01), 6)
        ranked.append(item)
    ranked.sort(key=lambda item: (item["distance_pct"], -int(item.get("priority", 0)), item["id"]))
    for index, item in enumerate(ranked, start=1):
        item["rank"] = index
    return ranked


def _nearest_broken_level(
    levels: Sequence[Dict[str, Any]],
    *,
    role: str,
    current_price: float,
    break_buffer_pct: float,
    settings: Dict[str, Any],
    bars: Sequence[Dict[str, Any]] | None,
) -> Dict[str, Any] | None:
    candidates: List[Dict[str, Any]] = []
    for level in levels:
        if _level_role(level) != role:
            continue
        price = _optional_float(level.get("price"))
        if price is None:
            continue
        threshold = price * (1 - break_buffer_pct) if role == "support" else price * (1 + break_buffer_pct)
        if _level_is_broken(
            role=role,
            current_price=current_price,
            threshold=threshold,
            settings=settings,
            bars=bars,
        ):
            item = dict(level)
            item["price"] = round(price, 4)
            item["break_distance_pct"] = round(abs(current_price - price) / max(abs(current_price), 0.01), 6)
            candidates.append(item)
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item["break_distance_pct"], -int(item.get("priority", 0))))


def _level_role(level: Dict[str, Any]) -> str:
    raw_role = str(level.get("role") or "").strip().lower()
    if raw_role in {"support", "resistance"}:
        return raw_role
    kind = str(level.get("kind") or level.get("id") or "").lower()
    if any(part in kind for part in ("low", "lower", "support")):
        return "support"
    if any(part in kind for part in ("high", "upper", "resistance")):
        return "resistance"
    return ""


def _directive(
    *,
    action: str,
    reason_code: str,
    position: Dict[str, Any],
    level: Dict[str, Any],
    current_price: float,
    settings: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_position = _position_payload(position)
    directive_id = str(position.get("directive_id") or _deterministic_directive_id(
        position=normalized_position,
        action=action,
        level=level,
        settings=settings,
    ))
    directive = {
        "schema_version": DIRECTIVE_SCHEMA_VERSION,
        "directive_id": directive_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "reason_code": reason_code,
        "position": normalized_position,
        "underlying": normalized_position.get("underlying"),
        "level": {
            "id": level.get("id"),
            "kind": level.get("kind"),
            "role": _level_role(level),
            "price": level.get("price"),
            "break_distance_pct": level.get("break_distance_pct"),
        },
        "underlying_price": round(current_price, 4),
        "execution_hint": {
            "immediate": action == "close_position",
            "order_preference": "marketable_limit" if action == "close_position" else "risk_capped_limit",
        },
        "metadata": {
            "strict_0dte_exits_enabled": bool(settings["strict_0dte_exits_enabled"]),
            "is_0dte": _is_0dte(normalized_position.get("expiry"), settings),
            "break_confirmation": settings["break_confirmation"],
            "confirming_closes": int(settings["confirming_closes"]),
            "session_id": _session_id(level, settings),
            "max_scale_ins_per_position": int(settings["max_scale_ins_per_position"]),
            "scale_in_cooldown_seconds": int(settings["scale_in_cooldown_seconds"]),
            "one_scale_in_per_level": bool(settings["one_scale_in_per_level"]),
            "stop_trading_after_time_enabled": bool(settings["stop_trading_after_time_enabled"]),
            "pre_close_trailing_rescue_enabled": bool(settings["pre_close_trailing_rescue_enabled"]),
        },
    }
    if action == "request_scale_in":
        directive["sizing_hint"] = {
            "mode": settings["scale_in_sizing_mode"],
            "fraction": round(float(settings["scale_in_fraction"]), 4),
            "minimum_contracts": int(settings["minimum_scale_in_contracts"]),
        }
    else:
        directive["sizing_hint"] = {"mode": "close_existing_position", "fraction": 1.0}
    return directive


def _position_payload(position: Dict[str, Any]) -> Dict[str, Any]:
    option_side = _option_side(position.get("option_side") or position.get("side") or position.get("direction"))
    quantity = _required_float(position.get("quantity"), "position.quantity")
    strike = _optional_float(position.get("strike"))
    entry_price = _optional_float(position.get("entry_price"))
    return {
        "position_id": str(position.get("position_id") or position.get("id") or "").strip(),
        "underlying": _symbol(str(position.get("underlying") or position.get("symbol") or "")),
        "option_side": option_side,
        "quantity": quantity,
        "expiry": str(position.get("expiry") or "").strip(),
        "strike": strike,
        "entry_price": entry_price,
    }


def _confirmation_bars(
    bars: Sequence[Dict[str, Any]] | None,
    settings: Dict[str, Any],
) -> Sequence[Dict[str, Any]] | None:
    if settings["break_confirmation"] != "candle_close_break":
        return None
    if not bars:
        raise ValueError("bars are required when break_confirmation is candle_close_break")
    return sorted((_normalise_bar(dict(bar)) for bar in bars), key=lambda item: item["timestamp"])


def _level_is_broken(
    *,
    role: str,
    current_price: float,
    threshold: float,
    settings: Dict[str, Any],
    bars: Sequence[Dict[str, Any]] | None,
) -> bool:
    if settings["break_confirmation"] == "tick_break":
        return (role == "support" and current_price <= threshold) or (
            role == "resistance" and current_price >= threshold
        )

    if settings["break_confirmation"] == "candle_close_break":
        confirming_closes = int(settings["confirming_closes"])
        if not bars or len(bars) < confirming_closes:
            return False
        closes = [float(bar["close"]) for bar in bars[-confirming_closes:]]
        if role == "support":
            return all(close <= threshold for close in closes)
        return all(close >= threshold for close in closes)

    raise ValueError(f"Unsupported break_confirmation: {settings['break_confirmation']}")


def _deterministic_directive_id(
    *,
    position: Dict[str, Any],
    action: str,
    level: Dict[str, Any],
    settings: Dict[str, Any],
) -> str:
    return ":".join(
        [
            "edge-sr",
            _safe_identifier(_session_id(level, settings)),
            _position_identity(position),
            _safe_identifier(action),
            _safe_identifier(level.get("id") or level.get("kind") or "level"),
        ]
    )


def _session_id(level: Dict[str, Any], settings: Dict[str, Any]) -> str:
    configured = str(settings.get("session_id") or "").strip()
    if configured:
        return configured
    for key in ("session_id", "session"):
        value = str(level.get(key) or "").strip()
        if value:
            return value
    timestamp = str(level.get("timestamp") or "").strip()
    if len(timestamp) >= 10:
        return timestamp[:10]
    return "default"


def _position_identity(position: Dict[str, Any]) -> str:
    position_id = str(position.get("position_id") or "").strip()
    if position_id:
        return _safe_identifier(position_id)
    parts = [
        position.get("underlying"),
        position.get("option_side"),
        position.get("expiry"),
        position.get("strike"),
    ]
    return _safe_identifier("-".join(str(part or "") for part in parts) or "unknown-position")


def _safe_identifier(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", text).strip("-") or "unknown"


def _normalise_bar(bar: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = _parse_timestamp(bar.get("timestamp"))
    open_price = _required_float(bar.get("open"), "bar.open")
    high = _required_float(bar.get("high"), "bar.high")
    low = _required_float(bar.get("low"), "bar.low")
    close = _required_float(bar.get("close"), "bar.close")
    if high < low:
        raise ValueError("Support/resistance bar high cannot be below low")
    return {
        "timestamp": timestamp,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": _optional_float(bar.get("volume")) or 0.0,
    }


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Support/resistance bar timestamp is required")
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Support/resistance bar timestamp must be ISO-8601") from exc


def _vwap_series(bars: Sequence[Dict[str, Any]]) -> List[float | None]:
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    values: List[float | None] = []
    for bar in bars:
        volume = max(float(bar.get("volume") or 0.0), 0.0)
        typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
        cumulative_price_volume += typical_price * volume
        cumulative_volume += volume
        values.append(round(cumulative_price_volume / cumulative_volume, 4) if cumulative_volume > 0 else None)
    return values


def _true_range_series(bars: Sequence[Dict[str, Any]]) -> List[float]:
    ranges: List[float] = []
    previous_close: float | None = None
    for bar in bars:
        high = bar["high"]
        low = bar["low"]
        if previous_close is None:
            ranges.append(high - low)
        else:
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = bar["close"]
    return [round(value, 4) for value in ranges]


def _atr_series(bars: Sequence[Dict[str, Any]], period: int) -> List[float | None]:
    true_ranges = _true_range_series(bars)
    series: List[float | None] = []
    for index, _ in enumerate(true_ranges):
        if index + 1 < period:
            series.append(None)
            continue
        window = true_ranges[index + 1 - period : index + 1]
        series.append(round(sum(window) / period, 4))
    return series


def _latest_value(values: Sequence[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def _is_regular_session_bar(timestamp: datetime) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return (9 * 60 + 30) <= minute < (16 * 60)


def _is_premarket_bar(timestamp: datetime) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return (4 * 60) <= minute < (9 * 60 + 30)


def _is_opening_range_bar(timestamp: datetime, opening_range_minutes: int) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    start = 9 * 60 + 30
    return start <= minute < start + opening_range_minutes


def _role_for_neutral_price(price: float, current_price: float) -> str:
    return "support" if price <= current_price else "resistance"


def _option_side(value: Any) -> str:
    side = str(value or "").strip().lower()
    side = side.replace("long_", "")
    if side in {"c", "call", "calls"}:
        return "call"
    if side in {"p", "put", "puts"}:
        return "put"
    raise ValueError("Position option_side must be call or put")


def _is_0dte(expiry: Any, settings: Dict[str, Any]) -> bool:
    if not expiry:
        return False
    raw_as_of = settings.get("as_of_date")
    if raw_as_of:
        try:
            as_of = date.fromisoformat(str(raw_as_of))
        except ValueError:
            as_of = date.today()
    else:
        as_of = date.today()
    try:
        return date.fromisoformat(str(expiry)) == as_of
    except ValueError:
        return False


def _symbol(raw: str) -> str:
    symbol = str(raw or "").strip().upper()
    if not symbol:
        raise ValueError("symbol is required")
    return symbol


def _required_float(value: Any, field: str) -> float:
    numeric = _optional_float(value)
    if numeric is None:
        raise ValueError(f"{field} must be a finite number")
    return numeric


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(numeric):
        return None
    return numeric


def _break_confirmation_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode not in BREAK_CONFIRMATION_MODES:
        raise ValueError(
            f"break_confirmation must be one of {sorted(BREAK_CONFIRMATION_MODES)}"
        )
    return mode


def _settings_now(settings: Dict[str, Any]) -> datetime:
    raw = settings.get("now")
    if isinstance(raw, datetime):
        parsed = raw
    elif raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            parsed = datetime.now(timezone.utc)
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _strict_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if numeric < minimum or numeric > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return numeric


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clamp_float(value: Any, minimum: float, maximum: float) -> float:
    numeric = _optional_float(value)
    if numeric is None:
        return minimum
    return max(minimum, min(float(numeric), maximum))


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(numeric, maximum))
