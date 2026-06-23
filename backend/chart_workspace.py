"""Chart Workspace snapshot assembly and indicator calculations."""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Dict, Iterable, List, Sequence

from orb import ET, _to_et


CHART_WORKSPACE_SCHEMA_VERSION = "edge.chart_workspace.snapshot.v1"
DEFAULT_INDICATORS = ("ema_9", "ema_20", "sma_20", "rsi_14", "macd")


def build_chart_workspace_payload(
    *,
    symbol: str,
    bars: Iterable[Dict[str, Any]],
    indicators: Sequence[str] | None = None,
    limit: int = 240,
    orb_status: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build chart-ready OHLCV, indicator, and ORB overlay data."""
    normalised_bars = sorted((_normalise_bar(bar) for bar in bars), key=lambda bar: bar["timestamp"])
    if not normalised_bars:
        raise ValueError("At least one chart bar is required")

    limit = _bounded_limit(limit)
    requested_indicators = _normalise_indicators(indicators)
    closes = [bar["close"] for bar in normalised_bars]
    timestamps = [bar["timestamp"] for bar in normalised_bars]
    start_index = max(0, len(normalised_bars) - limit)
    visible_bars = normalised_bars[start_index:]

    orb_overlays = _orb_overlays(orb_status)
    return {
        "schema_version": CHART_WORKSPACE_SCHEMA_VERSION,
        "symbol": symbol.strip().upper(),
        "timeframe": "1m",
        "source": "edge_ohlcv_cache",
        "summary": {
            "bar_count": len(visible_bars),
            "available_bar_count": len(normalised_bars),
            "indicator_count": len(requested_indicators),
            "orb_overlay_count": len(orb_overlays),
        },
        "bars": [_bar_payload(bar) for bar in visible_bars],
        "indicators": _indicator_payloads(
            indicator_ids=requested_indicators,
            bars=normalised_bars,
            closes=closes,
            timestamps=timestamps,
            start_index=start_index,
        ),
        "levels": _market_map_levels(normalised_bars),
        "orb_overlays": orb_overlays,
        "orb_session_status": orb_status,
    }


def _indicator_payloads(
    *,
    indicator_ids: Sequence[str],
    bars: Sequence[Dict[str, Any]],
    closes: Sequence[float],
    timestamps: Sequence[datetime],
    start_index: int,
) -> Dict[str, Dict[str, Any]]:
    payloads: Dict[str, Dict[str, Any]] = {}
    for indicator_id in indicator_ids:
        if indicator_id.startswith("ema_"):
            period = _indicator_period(indicator_id, "ema")
            payloads[indicator_id] = _single_value_indicator(
                label=f"EMA {period}",
                kind="overlay",
                timestamps=timestamps[start_index:],
                values=_ema_series(closes, period)[start_index:],
            )
        elif indicator_id.startswith("sma_"):
            period = _indicator_period(indicator_id, "sma")
            payloads[indicator_id] = _single_value_indicator(
                label=f"SMA {period}",
                kind="overlay",
                timestamps=timestamps[start_index:],
                values=_sma_series(closes, period)[start_index:],
            )
        elif indicator_id.startswith("rsi_"):
            period = _indicator_period(indicator_id, "rsi")
            payloads[indicator_id] = _single_value_indicator(
                label=f"RSI {period}",
                kind="oscillator",
                timestamps=timestamps[start_index:],
                values=_rsi_series(closes, period)[start_index:],
            )
        elif indicator_id == "macd":
            payloads[indicator_id] = {
                "label": "MACD 12/26/9",
                "kind": "oscillator",
                "points": _macd_points(closes=closes, timestamps=timestamps)[start_index:],
            }
        elif indicator_id == "vwap":
            payloads[indicator_id] = _single_value_indicator(
                label="VWAP",
                kind="overlay",
                timestamps=timestamps[start_index:],
                values=_vwap_series(bars)[start_index:],
            )
        elif indicator_id.startswith("atr_"):
            period = _indicator_period(indicator_id, "atr")
            payloads[indicator_id] = _single_value_indicator(
                label=f"ATR {period}",
                kind="oscillator",
                timestamps=timestamps[start_index:],
                values=_atr_series(bars, period)[start_index:],
            )
    return payloads


def _single_value_indicator(
    *,
    label: str,
    kind: str,
    timestamps: Sequence[datetime],
    values: Sequence[float | None],
) -> Dict[str, Any]:
    return {
        "label": label,
        "kind": kind,
        "points": [
            {
                "timestamp": timestamp.isoformat(),
                "value": _round_optional(value),
            }
            for timestamp, value in zip(timestamps, values)
        ],
    }


def _ema_series(values: Sequence[float], period: int) -> List[float | None]:
    alpha = 2 / (period + 1)
    ema_values: List[float | None] = []
    current: float | None = None
    for value in values:
        current = value if current is None else (value * alpha) + (current * (1 - alpha))
        ema_values.append(round(current, 4))
    return ema_values


def _sma_series(values: Sequence[float], period: int) -> List[float | None]:
    series: List[float | None] = []
    for index, _ in enumerate(values):
        if index + 1 < period:
            series.append(None)
            continue
        window = values[index + 1 - period : index + 1]
        series.append(round(sum(window) / period, 4))
    return series


def _rsi_series(values: Sequence[float], period: int) -> List[float | None]:
    series: List[float | None] = []
    for index, _ in enumerate(values):
        if index < period:
            series.append(None)
            continue
        deltas = [values[pos] - values[pos - 1] for pos in range(index + 1 - period, index + 1)]
        gains = [delta for delta in deltas if delta > 0]
        losses = [-delta for delta in deltas if delta < 0]
        average_gain = sum(gains) / period
        average_loss = sum(losses) / period
        if average_loss == 0:
            series.append(100.0 if average_gain > 0 else 50.0)
            continue
        relative_strength = average_gain / average_loss
        series.append(round(100 - (100 / (1 + relative_strength)), 4))
    return series


def _macd_points(*, closes: Sequence[float], timestamps: Sequence[datetime]) -> List[Dict[str, Any]]:
    fast = _ema_series(closes, 12)
    slow = _ema_series(closes, 26)
    macd_values = [
        None if fast_value is None or slow_value is None else round(fast_value - slow_value, 4)
        for fast_value, slow_value in zip(fast, slow)
    ]
    signal_values = _ema_series([value or 0.0 for value in macd_values], 9)
    points = []
    for timestamp, macd_value, signal_value in zip(timestamps, macd_values, signal_values):
        histogram = None
        if macd_value is not None and signal_value is not None:
            histogram = round(macd_value - signal_value, 4)
        points.append(
            {
                "timestamp": timestamp.isoformat(),
                "macd": _round_optional(macd_value),
                "signal": _round_optional(signal_value),
                "histogram": _round_optional(histogram),
            }
        )
    return points


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


def _market_map_levels(bars: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    latest = bars[-1]
    latest_date = latest["timestamp"].date()
    current_day_bars = [bar for bar in bars if bar["timestamp"].date() == latest_date] or list(bars)
    prior_day_bars = [bar for bar in bars if bar["timestamp"].date() < latest_date]
    session_bars = [bar for bar in current_day_bars if _is_regular_session_bar(bar["timestamp"])] or current_day_bars
    premarket_bars = [bar for bar in current_day_bars if _is_premarket_bar(bar["timestamp"])]
    opening_range_bars = [bar for bar in session_bars if _is_opening_range_bar(bar["timestamp"])]
    vwap_values = _vwap_series(current_day_bars)
    atr_values = _atr_series(current_day_bars, min(14, max(2, len(current_day_bars))))
    latest_vwap = _latest_value(vwap_values)
    latest_atr = _latest_value(atr_values)
    timestamp = latest["timestamp"]
    items = [
        _level_item("session_high", "Session high", "session_high", max(bar["high"] for bar in session_bars), "ohlcv", "regular", timestamp, 0.9, False),
        _level_item("session_low", "Session low", "session_low", min(bar["low"] for bar in session_bars), "ohlcv", "regular", timestamp, 0.9, False),
    ]
    if prior_day_bars:
        items.extend(
            [
                _level_item("prior_day_high", "Prior day high", "prior_day_high", max(bar["high"] for bar in prior_day_bars), "ohlcv", "prior_day", timestamp, 0.85, True),
                _level_item("prior_day_low", "Prior day low", "prior_day_low", min(bar["low"] for bar in prior_day_bars), "ohlcv", "prior_day", timestamp, 0.85, True),
            ]
        )
    if premarket_bars:
        items.extend(
            [
                _level_item("premarket_high", "Premarket high", "premarket_high", max(bar["high"] for bar in premarket_bars), "ohlcv", "premarket", timestamp, 0.8, True),
                _level_item("premarket_low", "Premarket low", "premarket_low", min(bar["low"] for bar in premarket_bars), "ohlcv", "premarket", timestamp, 0.8, True),
            ]
        )
    if opening_range_bars:
        items.extend(
            [
                _level_item("opening_range_high", "Opening range high", "opening_range_high", max(bar["high"] for bar in opening_range_bars), "ohlcv", "regular", timestamp, 0.8, False),
                _level_item("opening_range_low", "Opening range low", "opening_range_low", min(bar["low"] for bar in opening_range_bars), "ohlcv", "regular", timestamp, 0.8, False),
            ]
        )
    if latest_vwap is not None:
        items.append(_level_item("vwap", "VWAP", "vwap", latest_vwap, "computed", "session", timestamp, 0.85, False))
    if latest_atr is not None:
        items.append(_level_item("atr_upper", "ATR upper", "atr_upper", latest["close"] + latest_atr, "computed", "session", timestamp, 0.7, False))
        items.append(_level_item("atr_lower", "ATR lower", "atr_lower", latest["close"] - latest_atr, "computed", "session", timestamp, 0.7, False))
    return {"schema_version": "edge.market_map.levels.v1", "items": items}


def _level_item(
    level_id: str,
    label: str,
    kind: str,
    price: float,
    source: str,
    session: str,
    timestamp: datetime,
    confidence: float,
    locked: bool,
) -> Dict[str, Any]:
    return {
        "id": level_id,
        "label": label,
        "kind": kind,
        "price": round(float(price), 4),
        "source": source,
        "session": session,
        "confidence": round(float(confidence), 4),
        "timestamp": timestamp.isoformat(),
        "locked": bool(locked),
    }


def _is_regular_session_bar(timestamp: datetime) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return (9 * 60 + 30) <= minute < (16 * 60)


def _is_premarket_bar(timestamp: datetime) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return (4 * 60) <= minute < (9 * 60 + 30)


def _is_opening_range_bar(timestamp: datetime) -> bool:
    minute = timestamp.hour * 60 + timestamp.minute
    return (9 * 60 + 30) <= minute < (10 * 60)


def _latest_value(values: Sequence[float | None]) -> float | None:
    for value in reversed(values):
        if value is not None:
            return value
    return None


def _normalise_indicators(indicators: Sequence[str] | None) -> List[str]:
    raw_indicators = indicators or DEFAULT_INDICATORS
    normalised: List[str] = []
    for indicator in raw_indicators:
        indicator_id = str(indicator).strip().lower()
        if not indicator_id:
            continue
        if indicator_id == "vwap":
            if indicator_id not in normalised:
                normalised.append(indicator_id)
            continue
        if indicator_id.startswith("atr_"):
            _indicator_period(indicator_id, "atr")
            if indicator_id not in normalised:
                normalised.append(indicator_id)
            continue
        if indicator_id == "macd" or indicator_id.startswith(("ema_", "sma_", "rsi_")):
            if indicator_id != "macd":
                prefix = indicator_id.split("_", 1)[0]
                _indicator_period(indicator_id, prefix)
            if indicator_id not in normalised:
                normalised.append(indicator_id)
            continue
        raise ValueError(f"Unknown chart workspace indicator: {indicator_id}")
    return normalised or list(DEFAULT_INDICATORS)


def _indicator_period(indicator_id: str, prefix: str) -> int:
    raw_period = indicator_id.removeprefix(f"{prefix}_")
    try:
        period = int(raw_period)
    except ValueError as exc:
        raise ValueError(f"{indicator_id} indicator period must be an integer") from exc
    if period < 2 or period > 200:
        raise ValueError(f"{indicator_id} indicator period must be between 2 and 200")
    return period


def _orb_overlays(orb_status: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    overlays = []
    if not orb_status:
        return overlays
    for session_id, session in (orb_status.get("sessions") or {}).items():
        for timeframe, level in (session.get("levels") or {}).items():
            high = level.get("high")
            low = level.get("low")
            if high is None or low is None or not level.get("is_valid"):
                continue
            overlays.append(
                {
                    "session_id": str(session_id),
                    "label": session.get("label") or str(session_id),
                    "timeframe": str(timeframe),
                    "high": round(float(high), 4),
                    "low": round(float(low), 4),
                    "range_width": round(float(level.get("range_width", float(high) - float(low))), 4),
                    "locked": bool(level.get("locked")),
                    "is_valid": bool(level.get("is_valid")),
                    "date": level.get("date"),
                }
            )
    return overlays


def _normalise_bar(bar: Dict[str, Any]) -> Dict[str, Any]:
    timestamp = _parse_timestamp(bar.get("timestamp"))
    open_price = _required_price(bar, "open")
    high = _required_price(bar, "high")
    low = _required_price(bar, "low")
    close = _required_price(bar, "close")
    if high < low:
        raise ValueError("Chart workspace bar high cannot be below low")
    return {
        "timestamp": timestamp,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": _optional_float(bar.get("volume", 0.0)),
    }


def _bar_payload(bar: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "timestamp": bar["timestamp"].isoformat(),
        "open": round(bar["open"], 4),
        "high": round(bar["high"], 4),
        "low": round(bar["low"], 4),
        "close": round(bar["close"], 4),
        "volume": round(bar["volume"], 4),
    }


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _to_et(value).astimezone(ET)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Chart workspace bar timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Chart workspace bar timestamp must be ISO-8601") from exc
    return _to_et(parsed).astimezone(ET)


def _required_price(bar: Dict[str, Any], field: str) -> float:
    value = _optional_float(bar.get(field))
    if value is None:
        raise ValueError(f"Chart workspace bar {field} is required")
    return value


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


def _round_optional(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _bounded_limit(value: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer") from exc
    if numeric < 1 or numeric > 2000:
        raise ValueError("limit must be between 1 and 2000")
    return numeric
