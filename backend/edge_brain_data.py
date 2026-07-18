"""OHLCV, timeframe, indicator, pattern, and market-structure primitives."""
from __future__ import annotations

import asyncio
from enum import Enum
import logging
import os
import time
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from signals_enhanced import (
    PatternResult,
    SignalEngineEnhanced,
    TrendDirection as EnhancedTrend,
)

logger = logging.getLogger(__name__)


class EdgePatternType(str, Enum):
    BULL_FLAG = "BULL_FLAG"
    BEAR_FLAG = "BEAR_FLAG"
    RESISTANCE_BREAKOUT = "RESISTANCE_BREAKOUT"
    SUPPORT_BREAKDOWN = "SUPPORT_BREAKDOWN"


_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume")
_COMPLEX_PATTERNS = {
    "HEAD_SHOULDERS",
    "INVERSE_HEAD_SHOULDERS",
    "DOUBLE_BOTTOM",
    "DOUBLE_TOP",
}
_MTF_CACHE: Dict[tuple[str, str], tuple[pd.DataFrame, float]] = {}
_MTF_LOCKS: Dict[tuple[str, str], asyncio.Lock] = {}
_MTF_SEMAPHORE = asyncio.Semaphore(
    max(1, int(os.getenv("EDGE_BRAIN_MTF_CONCURRENCY", "4")))
)


def env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def env_float(name: str, default: float, *, minimum: Optional[float] = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value) if minimum is not None else value


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def normalize_ohlcv(frame: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    """Convert provider OHLCV columns to the analyzer's lower-case contract."""
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return None
    aliases = {
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adj close": "close",
        "adj_close": "close",
        "volume": "volume",
    }
    selected: Dict[str, pd.Series] = {}
    for column in frame.columns:
        canonical = aliases.get(str(column).strip().lower())
        if canonical and canonical not in selected:
            selected[canonical] = frame[column]
    if not all(column in selected for column in _REQUIRED_COLUMNS):
        return None
    clean = pd.DataFrame(selected, index=frame.index).copy()
    for column in _REQUIRED_COLUMNS:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    clean = clean.dropna(subset=list(_REQUIRED_COLUMNS))
    clean = clean[~clean.index.duplicated(keep="last")]
    return clean.sort_index() if not clean.empty else None


def resample_ohlcv(frame: Optional[pd.DataFrame], rule: str) -> Optional[pd.DataFrame]:
    frame = normalize_ohlcv(frame)
    if frame is None or not isinstance(frame.index, pd.DatetimeIndex):
        return None
    try:
        result = frame.resample(rule).agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
    except (TypeError, ValueError):
        return None
    result = result.dropna(subset=list(_REQUIRED_COLUMNS))
    return result if len(result) >= 20 else None


def safe_compute_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """ATR fallback that always returns one value per input bar."""
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    if len(close) == 0:
        return np.array([], dtype=float)
    true_range = np.empty(len(close), dtype=float)
    true_range[0] = high[0] - low[0]
    if len(close) > 1:
        true_range[1:] = np.maximum.reduce(
            [
                high[1:] - low[1:],
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1]),
            ]
        )
    return pd.Series(true_range).rolling(period, min_periods=1).mean().to_numpy(dtype=float)


def configure_engine(engine: SignalEngineEnhanced) -> None:
    engine.multi_timeframe = True
    engine.default_timeframe = os.getenv("EDGE_BRAIN_DEFAULT_TIMEFRAME", "15m")
    for pattern in _COMPLEX_PATTERNS:
        if pattern not in engine.enabled_patterns:
            engine.enabled_patterns.append(pattern)


def _yf_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    return yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)


async def _fetch_mtf_frame(
    symbol: str,
    timeframe: str,
    period: str,
    interval: str,
) -> Optional[pd.DataFrame]:
    key = (symbol.upper(), timeframe)
    ttl = env_float("EDGE_BRAIN_MTF_CACHE_SECONDS", 900.0, minimum=60.0)
    cached = _MTF_CACHE.get(key)
    if cached and time.monotonic() - cached[1] < ttl:
        return cached[0]
    lock = _MTF_LOCKS.setdefault(key, asyncio.Lock())
    async with lock:
        cached = _MTF_CACHE.get(key)
        if cached and time.monotonic() - cached[1] < ttl:
            return cached[0]
        try:
            async with _MTF_SEMAPHORE:
                loop = asyncio.get_running_loop()
                raw = await loop.run_in_executor(None, _yf_history, symbol, period, interval)
            frame = normalize_ohlcv(raw)
            if frame is not None:
                _MTF_CACHE[key] = (frame, time.monotonic())
            return frame
        except Exception as exc:  # pragma: no cover - provider-specific
            logger.debug("MTF fetch failed for %s %s: %s", symbol, timeframe, exc)
            return cached[0] if cached else None


async def load_longer_timeframes(symbol: str) -> Dict[str, pd.DataFrame]:
    if not env_flag("EDGE_BRAIN_MTF_ENABLED", "true"):
        return {}
    one_hour, one_day = await asyncio.gather(
        _fetch_mtf_frame(symbol, "1h", "3mo", "60m"),
        _fetch_mtf_frame(symbol, "1d", "1y", "1d"),
    )
    frames: Dict[str, pd.DataFrame] = {}
    if one_hour is not None:
        frames["1h"] = one_hour
        four_hour = resample_ohlcv(one_hour, "4h")
        if four_hour is not None:
            frames["4h"] = four_hour
    if one_day is not None:
        frames["1d"] = one_day
    return frames


def frame_trend(frame: Optional[pd.DataFrame]) -> tuple[float, Dict[str, float]]:
    frame = normalize_ohlcv(frame)
    if frame is None or len(frame) < 30:
        return 0.0, {}
    close = frame["close"].astype(float)
    ema9 = close.ewm(span=9, adjust=False).mean().iloc[-1]
    ema21 = close.ewm(span=21, adjust=False).mean().iloc[-1]
    ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    histogram = float((macd - macd.ewm(span=9, adjust=False).mean()).iloc[-1])
    scale = max(abs(float(close.iloc[-1])) * 0.002, 1e-9)
    ema_score = clamp(((ema9 - ema21) + (ema21 - ema50)) / (2 * scale), -1.0, 1.0)
    macd_score = clamp(histogram / scale, -1.0, 1.0)
    return clamp(ema_score * 0.7 + macd_score * 0.3, -1.0, 1.0), {
        "ema_9": float(ema9),
        "ema_21": float(ema21),
        "ema_50": float(ema50),
        "macd_hist": histogram,
    }


def detect_flag(frame: Optional[pd.DataFrame], timeframe: str) -> Optional[PatternResult]:
    frame = normalize_ohlcv(frame)
    if frame is None or len(frame) < 28:
        return None
    window = frame.tail(min(48, len(frame)))
    close = window["close"].to_numpy(dtype=float)
    volume = window["volume"].to_numpy(dtype=float)
    impulse_bars = max(8, len(close) // 3)
    start = close[0]
    end = close[impulse_bars - 1]
    if start <= 0 or end == 0:
        return None
    impulse = (end - start) / start
    consolidation = close[impulse_bars - 1 :]
    if len(consolidation) < 12:
        return None
    slope = float(np.polyfit(np.arange(len(consolidation)), consolidation / end, 1)[0])
    impulse_volume = float(np.mean(volume[:impulse_bars]))
    later_volume = float(np.mean(volume[impulse_bars:]))
    volume_bonus = 0.12 if later_volume <= impulse_volume * 0.95 else 0.0

    pattern_type: Optional[EdgePatternType] = None
    direction = EnhancedTrend.NEUTRAL
    retracement = 0.0
    valid = False
    if impulse >= 0.025:
        peak = float(np.max(close[:impulse_bars]))
        retracement = (peak - close[-1]) / max(peak - start, 1e-9)
        valid = -0.004 <= slope <= 0.0015 and -0.05 <= retracement <= 0.6
        pattern_type, direction = EdgePatternType.BULL_FLAG, EnhancedTrend.BULLISH
    elif impulse <= -0.025:
        trough = float(np.min(close[:impulse_bars]))
        retracement = (close[-1] - trough) / max(start - trough, 1e-9)
        valid = -0.0015 <= slope <= 0.004 and -0.05 <= retracement <= 0.6
        pattern_type, direction = EdgePatternType.BEAR_FLAG, EnhancedTrend.BEARISH
    if not valid or pattern_type is None:
        return None
    confidence = clamp(0.48 + min(abs(impulse), 0.12) * 2.5 + volume_bonus, 0.0, 0.92)
    return PatternResult(
        pattern_type=pattern_type,
        detected=True,
        confidence=confidence,
        strength=abs(impulse) * 100,
        direction=direction,
        metadata={"timeframe": timeframe, "impulse_pct": impulse * 100, "retracement": retracement},
    )


def market_structure(frame: Optional[pd.DataFrame], timeframe: str) -> Dict[str, Any]:
    frame = normalize_ohlcv(frame)
    if frame is None or len(frame) < 22:
        return {"timeframe": timeframe, "state": "insufficient_data", "confidence": 0.0}
    recent = frame.tail(61)
    prior = recent.iloc[:-1].tail(40)
    latest = recent.iloc[-1]
    resistance = float(prior["high"].max())
    support = float(prior["low"].min())
    price = float(latest["close"])
    average_volume = float(prior["volume"].tail(20).mean())
    volume_ratio = float(latest["volume"] / average_volume) if average_volume > 0 else 1.0
    buffer = env_float("EDGE_BRAIN_BREAKOUT_BUFFER", 0.001, minimum=0.0)
    state, direction = "range", 0
    if price > resistance * (1 + buffer):
        state, direction = "resistance_breakout", 1
    elif price < support * (1 - buffer):
        state, direction = "support_breakdown", -1
    proximity = min(abs(price - resistance), abs(price - support)) / max(price, 1e-9)
    confidence = (
        clamp(0.5 + max(0.0, volume_ratio - 1.0) * 0.2, 0.0, 0.95)
        if direction
        else 0.35 if proximity <= 0.005 else 0.0
    )
    return {
        "timeframe": timeframe,
        "state": state,
        "direction": direction,
        "support": support,
        "resistance": resistance,
        "price": price,
        "volume_ratio": volume_ratio,
        "confidence": confidence,
    }
