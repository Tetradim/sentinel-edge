#!/usr/bin/env python3
"""June/July 2026 minute-candle Edge -> Pulse interaction experiment.

This is an experiment runner, not a live trading entry point. It uses real one-minute
OHLCV bars and the production Edge analysis/ranking modules when available, then
simulates Pulse's documented handoff-created ticker, execution-style, bracket and
flat-only re-bracket behavior across a parameter grid.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import json
import math
import os
import statistics
import tempfile
import time
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
PULSE_DEFAULTS = {"SPY", "QQQ", "AAPL", "NVDA"}
CORE_SYMBOLS = [
    "AMD", "MU", "AMAT", "KLAC", "AVGO", "TSLA", "META", "MSFT", "GOOGL",
    "AMZN", "PLTR", "SOFI", "HOOD", "COIN", "RIVN",
]
PENNY_CANDIDATES = [
    "SLND", "CJMB", "GRML", "BNRG", "BIYA", "JSPR", "GORO", "BATL", "EOSE",
    "PLUG", "IOVA", "LAES", "IAUX", "KOS", "FFAI", "BSIN", "ANY", "HIVE",
    "ABTS", "OTLK",
]
CORRELATED_GROUPS = [
    {"AMD", "MU", "AMAT", "KLAC", "AVGO"},
    {"TSLA", "META", "MSFT", "GOOGL", "AMZN", "PLTR"},
    {"SOFI", "HOOD", "COIN"},
]


@dataclass(frozen=True)
class SweepConfig:
    band_pct: float
    rebracket_threshold_pct: float
    rebracket_spread_pct: float
    rebracket_buffer_pct: float
    rebracket_lookback: int = 10
    rebracket_cooldown_minutes: int = 5
    entry_window_minutes: int = 45
    stop_multiplier: float = 1.5


@dataclass
class SignalRecord:
    timestamp: str
    symbol: str
    score: float
    confidence: float
    signal_strength: float
    strategy: str
    regime: str
    entry_price: float
    maximum_entry_price: float
    initial_stop: float
    target_1: float
    target_2: float
    execution_style: str
    entry_trigger: float
    squeeze_triggered: bool
    squeeze_pressure_score: float
    orb_direction: str
    selected_rank: int
    expected_value_pct: float
    reward_risk: float


@dataclass
class TradeRecord:
    symbol: str
    signal_timestamp: str
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    net_pnl: float
    return_pct: float
    exit_reason: str
    execution_style: str
    fill_source: str
    fill_delay_minutes: int
    rebracket_count: int
    squeeze_triggered: bool
    max_favorable_pct: float
    max_adverse_pct: float


def finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def iso(ts: Any) -> str:
    value = pd.Timestamp(ts)
    if value.tzinfo is None:
        value = value.tz_localize("UTC")
    return value.tz_convert("UTC").isoformat()


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    out = frame.copy()
    out.columns = [str(c).lower().replace(" ", "_") for c in out.columns]
    required = ["open", "high", "low", "close", "volume"]
    if not all(col in out.columns for col in required):
        return pd.DataFrame(columns=required)
    out = out[required].apply(pd.to_numeric, errors="coerce")
    out = out.dropna(subset=["open", "high", "low", "close"])
    out = out[(out[["open", "high", "low", "close"]] > 0).all(axis=1)]
    index = pd.DatetimeIndex(out.index)
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    out.index = index
    out = out[~out.index.duplicated(keep="last")].sort_index()
    out["volume"] = out["volume"].fillna(0.0).clip(lower=0.0)
    return out


def _extract_yfinance_symbol(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    if not isinstance(frame.columns, pd.MultiIndex):
        return _normalize_frame(frame)
    levels0 = set(map(str, frame.columns.get_level_values(0)))
    levels1 = set(map(str, frame.columns.get_level_values(1)))
    try:
        if symbol in levels0:
            return _normalize_frame(frame[symbol])
        if symbol in levels1:
            return _normalize_frame(frame.xs(symbol, axis=1, level=1))
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _date_chunks(start: date, end: date, days: int = 6) -> Iterable[tuple[date, date]]:
    cursor = start
    while cursor < end:
        next_cursor = min(end, cursor + timedelta(days=days))
        yield cursor, next_cursor
        cursor = next_cursor


def download_yfinance(symbols: list[str], start: date, end: date) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    import yfinance as yf

    pieces: dict[str, list[pd.DataFrame]] = {symbol: [] for symbol in symbols}
    failures: list[dict[str, str]] = []
    for chunk_start, chunk_end in _date_chunks(start, end):
        try:
            raw = yf.download(
                tickers=" ".join(symbols),
                start=chunk_start.isoformat(),
                end=chunk_end.isoformat(),
                interval="1m",
                group_by="ticker",
                auto_adjust=False,
                prepost=True,
                progress=False,
                threads=True,
                timeout=30,
            )
        except Exception as exc:
            failures.append({"chunk": f"{chunk_start}:{chunk_end}", "error": str(exc)})
            raw = pd.DataFrame()
        for symbol in symbols:
            part = _extract_yfinance_symbol(raw, symbol)
            if not part.empty:
                pieces[symbol].append(part)
        time.sleep(0.25)

    missing = [symbol for symbol, frames in pieces.items() if not frames]
    for symbol in missing:
        for chunk_start, chunk_end in _date_chunks(start, end):
            try:
                raw = yf.download(
                    tickers=symbol,
                    start=chunk_start.isoformat(),
                    end=chunk_end.isoformat(),
                    interval="1m",
                    auto_adjust=False,
                    prepost=True,
                    progress=False,
                    threads=False,
                    timeout=30,
                )
                part = _extract_yfinance_symbol(raw, symbol)
                if not part.empty:
                    pieces[symbol].append(part)
            except Exception as exc:
                failures.append({"symbol": symbol, "chunk": f"{chunk_start}:{chunk_end}", "error": str(exc)})
            time.sleep(0.4)

    data: dict[str, pd.DataFrame] = {}
    for symbol, frames in pieces.items():
        if frames:
            data[symbol] = _normalize_frame(pd.concat(frames).sort_index())
    return data, {"provider": "yfinance", "failures": failures}


def download_alpaca(symbols: list[str], start: date, end: date, feed: str = "iex") -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    import requests

    key = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
    secret = os.getenv("ALPACA_API_SECRET") or os.getenv("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("Alpaca credentials are unavailable")
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    params = {
        "symbols": ",".join(symbols),
        "timeframe": "1Min",
        "start": datetime.combine(start, datetime.min.time(), tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "end": datetime.combine(end, datetime.min.time(), tzinfo=UTC).isoformat().replace("+00:00", "Z"),
        "limit": 10000,
        "adjustment": "raw",
        "feed": feed,
        "sort": "asc",
    }
    rows: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in symbols}
    page_token: Optional[str] = None
    pages = 0
    while True:
        query = dict(params)
        if page_token:
            query["page_token"] = page_token
        response = requests.get(
            "https://data.alpaca.markets/v2/stocks/bars",
            params=query,
            headers=headers,
            timeout=60,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Alpaca HTTP {response.status_code}: {response.text[:500]}")
        payload = response.json()
        for symbol, bars in (payload.get("bars") or {}).items():
            rows.setdefault(symbol, []).extend(bars or [])
        pages += 1
        page_token = payload.get("next_page_token")
        if not page_token:
            break
    data: dict[str, pd.DataFrame] = {}
    for symbol, bars in rows.items():
        if not bars:
            continue
        frame = pd.DataFrame(
            {
                "open": [bar.get("o") for bar in bars],
                "high": [bar.get("h") for bar in bars],
                "low": [bar.get("l") for bar in bars],
                "close": [bar.get("c") for bar in bars],
                "volume": [bar.get("v", 0) for bar in bars],
            },
            index=pd.to_datetime([bar.get("t") for bar in bars], utc=True),
        )
        data[symbol] = _normalize_frame(frame)
    return data, {"provider": "alpaca", "feed": feed, "pages": pages}


def download_data(symbols: list[str], start: date, end: date, provider: str) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    if provider in {"auto", "alpaca"}:
        try:
            return download_alpaca(symbols, start, end)
        except Exception as exc:
            if provider == "alpaca":
                raise
            fallback_error = str(exc)
    else:
        fallback_error = "not_requested"
    data, meta = download_yfinance(symbols, start, end)
    meta["alpaca_fallback_reason"] = fallback_error
    return data, meta


def regular_session(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    local = frame.tz_convert(ET)
    mask = (
        (local.index.time >= datetime.strptime("09:30", "%H:%M").time())
        & (local.index.time <= datetime.strptime("16:00", "%H:%M").time())
    )
    return local.loc[mask].tz_convert("UTC")


def daily_breakout_table(data: dict[str, pd.DataFrame], candidates: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in candidates:
        frame = regular_session(data.get(symbol, pd.DataFrame()))
        if frame.empty:
            continue
        local = frame.tz_convert(ET).copy()
        local["session_date"] = local.index.date
        daily = local.groupby("session_date").agg(
            open=("open", "first"), high=("high", "max"), low=("low", "min"),
            close=("close", "last"), volume=("volume", "sum"),
        )
        daily["prior_close"] = daily["close"].shift(1)
        daily["volume_baseline"] = daily["volume"].shift(1).rolling(10, min_periods=3).median()
        daily["close_return_pct"] = (daily["close"] / daily["prior_close"] - 1.0) * 100.0
        daily["high_return_pct"] = (daily["high"] / daily["prior_close"] - 1.0) * 100.0
        daily["volume_ratio"] = daily["volume"] / daily["volume_baseline"].replace(0, np.nan)
        for session_date, row in daily.dropna(subset=["prior_close"]).iterrows():
            if finite(row["prior_close"]) >= 5.0 and finite(row["low"]) >= 5.0:
                continue
            breakout_return = max(finite(row["close_return_pct"]), finite(row["high_return_pct"]))
            volume_ratio = max(0.0, finite(row["volume_ratio"], 1.0))
            score = breakout_return + min(25.0, max(0.0, volume_ratio - 1.0) * 5.0)
            rows.append(
                {
                    "symbol": symbol,
                    "date": str(session_date),
                    "prior_close": round(finite(row["prior_close"]), 4),
                    "high": round(finite(row["high"]), 4),
                    "close": round(finite(row["close"]), 4),
                    "close_return_pct": round(finite(row["close_return_pct"]), 4),
                    "high_return_pct": round(finite(row["high_return_pct"]), 4),
                    "volume_ratio": round(volume_ratio, 4),
                    "breakout_score": round(score, 4),
                    "qualifies": breakout_return >= 10.0 and volume_ratio >= 1.5,
                }
            )
    return pd.DataFrame(rows)


def choose_penny_breakouts(table: pd.DataFrame, count: int = 5) -> list[str]:
    if table.empty:
        return []
    ordered = table.sort_values(["qualifies", "breakout_score"], ascending=[False, False])
    selected: list[str] = []
    for symbol in ordered["symbol"]:
        if symbol not in selected:
            selected.append(symbol)
        if len(selected) >= count:
            break
    return selected


def synthetic_squeeze_snapshot(symbol: str, breakout_rows: pd.DataFrame) -> dict[str, Any]:
    row = breakout_rows.sort_values("breakout_score", ascending=False).iloc[0]
    move = max(0.0, finite(row.get("high_return_pct")))
    volume_ratio = max(1.0, finite(row.get("volume_ratio"), 1.0))
    payload = {
        "short_float_pct": min(45.0, 18.0 + move * 0.35),
        "days_to_cover": min(12.0, 4.0 + volume_ratio * 0.7),
        "borrow_rate_pct": min(180.0, 35.0 + move * 1.4),
        "utilization_pct": min(99.0, 75.0 + volume_ratio * 3.0),
        "availability_change_pct": -min(80.0, move * 1.2),
        "gamma_squeeze_score": min(100.0, 45.0 + move),
        "catalyst_score": min(100.0, 35.0 + move * 0.8),
    }
    try:
        from edge_orb_squeeze import calculate_squeeze_pressure
        pressure = calculate_squeeze_pressure(payload)
    except Exception:
        components = [payload["short_float_pct"], payload["days_to_cover"] * 2.5, payload["borrow_rate_pct"] * 0.15]
        pressure = {"pressure_score": min(100.0, sum(components)), "pressure_probability": 0.75, "pressure_state": "armed"}
    return {
        "contract_version": "edge.squeeze.evidence.v1",
        "symbol": symbol,
        "source": "synthetic-pressure-real-minute-price-volume",
        **payload,
        **pressure,
    }


class ReplaySqueezeStore:
    def __init__(self, snapshots: dict[str, dict[str, Any]]):
        self.snapshots = snapshots

    def active(self, symbol: str) -> Optional[dict[str, Any]]:
        value = self.snapshots.get(str(symbol).upper())
        return dict(value) if value else None


class OrbLevel:
    def __init__(self, high: float, low: float, locked: bool):
        self.high = high
        self.low = low
        self.locked = locked
        self.is_valid = locked and high > 0 and low > 0 and high >= low


class ReplayOrb:
    def __init__(self):
        self.levels: dict[str, dict[str, dict[int, OrbLevel]]] = {}

    def set_levels(self, symbol: str, levels: dict[str, dict[int, OrbLevel]]) -> None:
        self.levels[symbol.upper()] = levels

    def get_session_levels(self, symbol: str) -> dict[str, dict[int, OrbLevel]]:
        return self.levels.get(symbol.upper(), {})


class NoSaveCoordinatorMixin:
    def _save(self) -> None:
        return None


def _resample(frame: pd.DataFrame, rule: str) -> Optional[pd.DataFrame]:
    if frame.empty:
        return None
    sampled = frame.resample(rule).agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["open", "high", "low", "close"])
    return sampled if len(sampled) >= 10 else None


def _session_orb_levels(day_frame: pd.DataFrame, current_ts: pd.Timestamp) -> dict[str, dict[int, OrbLevel]]:
    local = day_frame.tz_convert(ET)
    now_local = current_ts.tz_convert(ET)
    market = local.between_time("09:30", "16:00")
    premarket = local.between_time("04:00", "09:29")
    result: dict[str, dict[int, OrbLevel]] = {"market_open": {}, "premarket": {}}
    for minutes in (5, 15, 30):
        segment = market.iloc[:minutes]
        locked = len(segment) >= minutes and now_local.time() >= (datetime.combine(date.today(), datetime.strptime("09:30", "%H:%M").time()) + timedelta(minutes=minutes)).time()
        result["market_open"][minutes] = OrbLevel(
            finite(segment["high"].max()) if not segment.empty else 0.0,
            finite(segment["low"].min()) if not segment.empty else 0.0,
            locked,
        )
    if not premarket.empty:
        result["premarket"][30] = OrbLevel(finite(premarket["high"].max()), finite(premarket["low"].min()), now_local.time() >= datetime.strptime("09:30", "%H:%M").time())
    return result


async def build_edge_signal_stream(
    data: dict[str, pd.DataFrame],
    universe: list[str],
    penny_symbols: list[str],
    breakout_table: pd.DataFrame,
    eval_minutes: int,
) -> tuple[list[SignalRecord], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    from signals_enhanced import SignalEngineEnhanced, TechnicalIndicators, TrendDirection as EnhancedTrend
    from signals import TrendDirection as LegacyTrend
    from engine import DecisionEngine
    from edge_brain_analysis import augment_analysis
    from edge_brain_data import safe_compute_atr
    from edge_brain_indicators import safe_compute_rsi
    import edge_orb_squeeze as squeeze_module
    from edge_orb_squeeze import fuse_orb_and_squeeze
    import edge_execution_thesis as execution_thesis
    from edge_profitability import EdgeProfitabilityCoordinator

    class ReplayCoordinator(NoSaveCoordinatorMixin, EdgeProfitabilityCoordinator):
        pass

    TechnicalIndicators.compute_atr = staticmethod(safe_compute_atr)
    TechnicalIndicators.compute_rsi = staticmethod(safe_compute_rsi)
    execution_thesis.install()
    build_trade_thesis = execution_thesis.build_trade_thesis

    snapshots = {
        symbol: synthetic_squeeze_snapshot(symbol, breakout_table[breakout_table["symbol"] == symbol])
        for symbol in penny_symbols
        if not breakout_table[breakout_table["symbol"] == symbol].empty
    }
    squeeze_module.short_squeeze_store = ReplaySqueezeStore(snapshots)

    engine = SignalEngineEnhanced(enable_talib=False, multi_timeframe=True)
    decision_engine = DecisionEngine()
    coordinator = ReplayCoordinator(Path(tempfile.gettempdir()) / "edge-minute-sweep-state.json")
    coordinator.cards = {}
    coordinator.outcomes = []
    coordinator.latest_decisions = {}
    coordinator.candidates = {}
    orb = ReplayOrb()
    scheduler_stub = SimpleNamespace(orb=orb, signals=SimpleNamespace(avg_volume={}))

    event_times: set[pd.Timestamp] = set()
    regular_frames: dict[str, pd.DataFrame] = {}
    for symbol in universe:
        frame = regular_session(data.get(symbol, pd.DataFrame()))
        regular_frames[symbol] = frame
        if frame.empty:
            continue
        local = frame.tz_convert(ET)
        mask = (local.index.minute % eval_minutes == 0) & (local.index.time >= datetime.strptime("10:00", "%H:%M").time()) & (local.index.time <= datetime.strptime("15:45", "%H:%M").time())
        event_times.update(frame.index[mask])

    signals: list[SignalRecord] = []
    sell_events: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in universe}
    analysis_count = 0
    cycles = 0
    for current_ts in sorted(event_times):
        cycle_analyses: list[tuple[str, Any, dict[str, Any], str]] = []
        for symbol in universe:
            full = data.get(symbol)
            if full is None or full.empty or current_ts not in regular_frames[symbol].index:
                continue
            position = full.index.searchsorted(current_ts, side="right")
            if position < 60:
                continue
            window = full.iloc[max(0, position - 390):position]
            if len(window) < 60:
                continue
            base = await engine.analyze(symbol, window, timeframe="1m", higher_tf_data=None)
            frames = {"1m": window}
            for label, rule in (("5m", "5min"), ("15m", "15min"), ("1h", "1h"), ("1d", "1D")):
                sampled = _resample(window, rule)
                if sampled is not None:
                    frames[label] = sampled
            analysis = augment_analysis(base, frames)
            analysis = replace(analysis, timestamp=current_ts.to_pydatetime())
            local_date = current_ts.tz_convert(ET).date()
            day_mask = full.tz_convert(ET).index.date == local_date
            day_frame = full.loc[day_mask & (full.index <= current_ts)]
            orb.set_levels(symbol, _session_orb_levels(day_frame, current_ts))
            scheduler_stub.signals.avg_volume[symbol] = finite(window["volume"].iloc[-20:].mean())
            analysis = fuse_orb_and_squeeze(analysis, scheduler_stub)
            trend = LegacyTrend[analysis.trend.name]
            decision = decision_engine.decide(
                symbol=symbol,
                trend=trend,
                signal_strength=finite(analysis.signal_strength),
                confidence=finite(analysis.confidence.overall),
                has_position=False,
            )
            base_decision = decision.value
            thesis = build_trade_thesis(symbol, analysis, "buy")
            cycle_analyses.append((symbol, analysis, thesis, base_decision))
            if analysis.trend == EnhancedTrend.BEARISH and analysis.signal_strength <= -3.5 and analysis.confidence.overall >= 0.65:
                sell_events[symbol].append(
                    {
                        "timestamp": iso(current_ts),
                        "price": round(finite(analysis.price), 8),
                        "signal_strength": round(finite(analysis.signal_strength), 4),
                        "confidence": round(finite(analysis.confidence.overall), 4),
                        "reason": "edge_bearish_supervisory_sell",
                    }
                )
            analysis_count += 1

        if not cycle_analyses:
            continue
        cycle_id = coordinator.begin_evaluation_cycle([item[0] for item in cycle_analyses], cycle_id=f"replay:{iso(current_ts)}")
        for symbol, analysis, thesis, base_decision in cycle_analyses:
            coordinator.stage_cycle_candidate(
                cycle_id,
                analysis,
                thesis,
                base_decision=base_decision,
                target_bot="sentinel-pulse",
            )
        result = coordinator.finalize_evaluation_cycle(cycle_id)
        cycles += 1
        selected = result.get("selected") or []
        if selected:
            candidate = selected[0]
            card = candidate["card"]
            opportunity = candidate["opportunity"]
            metadata = card.metadata or {}
            squeeze = metadata.get("short_squeeze") if isinstance(metadata.get("short_squeeze"), dict) else {}
            orb_evidence = metadata.get("orb_evidence") if isinstance(metadata.get("orb_evidence"), dict) else {}
            targets = list(card.targets or [])
            signals.append(
                SignalRecord(
                    timestamp=iso(current_ts),
                    symbol=card.symbol,
                    score=round(finite(opportunity.score), 4),
                    confidence=round(finite(opportunity.calibrated_confidence), 4),
                    signal_strength=round(finite(candidate["analysis"].signal_strength), 4),
                    strategy=card.strategy,
                    regime=card.regime,
                    entry_price=round(finite(card.entry_price), 8),
                    maximum_entry_price=round(finite(card.maximum_entry_price), 8),
                    initial_stop=round(finite(card.initial_stop), 8),
                    target_1=round(finite(targets[0]) if targets else 0.0, 8),
                    target_2=round(finite(targets[1]) if len(targets) > 1 else 0.0, 8),
                    execution_style=str(metadata.get("execution_style_preference") or "timed_limit"),
                    entry_trigger=round(finite(card.entry_trigger), 8),
                    squeeze_triggered=bool(squeeze.get("trigger_confirmed")),
                    squeeze_pressure_score=round(finite(squeeze.get("pressure_score")), 4),
                    orb_direction=str(orb_evidence.get("direction") or "neutral"),
                    selected_rank=1,
                    expected_value_pct=round(finite(opportunity.expected_value_pct), 4),
                    reward_risk=round(finite(opportunity.reward_risk), 4),
                )
            )
        coordinator.cards.clear()

    return signals, sell_events, {
        "analysis_count": analysis_count,
        "evaluation_cycles": cycles,
        "selected_signal_count": len(signals),
        "squeeze_snapshot_mode": "synthetic pressure inputs over real historical price and volume",
        "squeeze_snapshots": snapshots,
    }


def _bars_between(frame: pd.DataFrame, start: pd.Timestamp, end: Optional[pd.Timestamp] = None) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.loc[frame.index >= start]
    if end is not None:
        result = result.loc[result.index <= end]
    return result


def _approx_arrival_prices(bar: pd.Series) -> tuple[float, float]:
    close = finite(bar["close"])
    spread_proxy = max(close * 0.0002, finite(bar["high"] - bar["low"]) * 0.08)
    bid = max(0.0001, close - spread_proxy / 2.0)
    ask = close + spread_proxy / 2.0
    return bid, ask


def _find_edge_sell(sell_events: list[dict[str, Any]], after: pd.Timestamp, before: pd.Timestamp) -> Optional[dict[str, Any]]:
    for event in sell_events:
        ts = pd.Timestamp(event["timestamp"])
        if after < ts <= before:
            return event
    return None


def simulate_entry(signal: SignalRecord, frame: pd.DataFrame, config: SweepConfig) -> Optional[dict[str, Any]]:
    signal_ts = pd.Timestamp(signal.timestamp)
    session_end_local = signal_ts.tz_convert(ET).replace(hour=16, minute=0, second=0, microsecond=0)
    window_end = min(signal_ts + timedelta(minutes=config.entry_window_minutes), session_end_local.tz_convert(UTC))
    bars = _bars_between(frame, signal_ts, window_end)
    if bars.empty:
        return None
    first_bar = bars.iloc[0]
    bid, ask = _approx_arrival_prices(first_bar)
    maximum = signal.maximum_entry_price or signal.entry_price * 1.01
    style = signal.execution_style
    buffer = 0.0004
    if style == "breakout_stop_limit":
        stop_price = signal.entry_trigger or signal.entry_price
        handoff_limit = min(maximum, max(ask, stop_price * (1.0 + buffer)))
        handoff_minutes = 8
    elif style == "passive_limit":
        stop_price = 0.0
        handoff_limit = min(signal.entry_price, bid * 1.0002)
        handoff_minutes = config.entry_window_minutes
    else:
        stop_price = 0.0
        handoff_limit = min(maximum, ask * (1.0 + buffer))
        handoff_minutes = 8

    recent: list[float] = []
    anchor = signal.entry_price
    buy_target = min(maximum, anchor * (1.0 - config.band_pct / 100.0))
    spread_abs = anchor * config.rebracket_spread_pct / 100.0
    sell_target = buy_target + spread_abs
    threshold_abs = anchor * config.rebracket_threshold_pct / 100.0
    buffer_abs = anchor * config.rebracket_buffer_pct / 100.0
    min_drift_abs = max(anchor * 0.0005, buffer_abs)
    last_rebracket: Optional[pd.Timestamp] = None
    rebrackets = 0

    for ts, bar in bars.iterrows():
        low, high, close = finite(bar["low"]), finite(bar["high"]), finite(bar["close"])
        recent.append(close)
        recent = recent[-config.rebracket_lookback :]
        elapsed = int((ts - signal_ts).total_seconds() // 60)
        if elapsed <= handoff_minutes:
            if style == "breakout_stop_limit":
                if high >= stop_price and low <= handoff_limit:
                    fill = min(handoff_limit, max(stop_price, finite(bar["open"], stop_price)))
                    return {"timestamp": ts, "price": fill, "source": "edge_handoff", "delay": elapsed, "rebrackets": rebrackets}
            elif low <= handoff_limit:
                fill = min(handoff_limit, finite(bar["open"], handoff_limit)) if finite(bar["open"]) <= handoff_limit else handoff_limit
                return {"timestamp": ts, "price": fill, "source": "edge_handoff", "delay": elapsed, "rebrackets": rebrackets}

        cooldown_ok = last_rebracket is None or (ts - last_rebracket).total_seconds() >= config.rebracket_cooldown_minutes * 60
        if cooldown_ok and recent:
            buy_drift = close - buy_target
            sell_drift = sell_target - close
            if buy_drift > threshold_abs and buy_drift > min_drift_abs:
                buy_target = min(maximum, min(recent) - buffer_abs)
                sell_target = buy_target + spread_abs
                last_rebracket = ts
                rebrackets += 1
                recent = []
            elif sell_drift > threshold_abs and sell_drift > min_drift_abs:
                buy_target = min(maximum, max(recent) - buffer_abs)
                sell_target = buy_target + spread_abs
                last_rebracket = ts
                rebrackets += 1
                recent = []

        if low <= buy_target <= high:
            return {"timestamp": ts, "price": buy_target, "source": "pulse_rebracket", "delay": elapsed, "rebrackets": rebrackets}
    return None


def simulate_exit(signal: SignalRecord, frame: pd.DataFrame, fill: dict[str, Any], config: SweepConfig, sell_events: list[dict[str, Any]]) -> dict[str, Any]:
    entry_ts = pd.Timestamp(fill["timestamp"])
    entry = finite(fill["price"])
    session_end = entry_ts.tz_convert(ET).replace(hour=16, minute=0, second=0, microsecond=0).tz_convert(UTC)
    bars = _bars_between(frame, entry_ts, session_end)
    target = entry * (1.0 + config.band_pct / 100.0)
    configured_stop = entry * (1.0 - max(0.50, config.band_pct * config.stop_multiplier) / 100.0)
    edge_stop = signal.initial_stop if 0 < signal.initial_stop < entry else 0.0
    stop = max(configured_stop, edge_stop)
    mfe = 0.0
    mae = 0.0
    for ts, bar in bars.iterrows():
        high, low = finite(bar["high"]), finite(bar["low"])
        mfe = max(mfe, (high / entry - 1.0) * 100.0)
        mae = min(mae, (low / entry - 1.0) * 100.0)
        edge_sell = _find_edge_sell(sell_events, entry_ts, ts)
        if edge_sell is not None:
            return {"timestamp": ts, "price": finite(bar["open"], finite(bar["close"])), "reason": "edge_supervisory_sell", "mfe": mfe, "mae": mae}
        if low <= stop:
            return {"timestamp": ts, "price": stop, "reason": "pulse_stop", "mfe": mfe, "mae": mae}
        if high >= target:
            return {"timestamp": ts, "price": target, "reason": "pulse_sell_target", "mfe": mfe, "mae": mae}
    if bars.empty:
        return {"timestamp": entry_ts, "price": entry, "reason": "no_exit_bars", "mfe": 0.0, "mae": 0.0}
    final_ts = bars.index[-1]
    return {"timestamp": final_ts, "price": finite(bars.iloc[-1]["close"]), "reason": "session_close", "mfe": mfe, "mae": mae}


def simulate_config(config: SweepConfig, signals: list[SignalRecord], data: dict[str, pd.DataFrame], sell_events: dict[str, list[dict[str, Any]]], starting_capital: float = 10000.0) -> tuple[dict[str, Any], list[TradeRecord], list[dict[str, Any]]]:
    capital = starting_capital
    peak = capital
    max_drawdown = 0.0
    trades: list[TradeRecord] = []
    communications: list[dict[str, Any]] = []
    busy_until = pd.Timestamp("1970-01-01", tz="UTC")
    pulse_symbols = set(PULSE_DEFAULTS)
    missed = 0
    for signal in sorted(signals, key=lambda item: item.timestamp):
        signal_ts = pd.Timestamp(signal.timestamp)
        if signal_ts < busy_until:
            continue
        created = signal.symbol not in pulse_symbols
        if created:
            pulse_symbols.add(signal.symbol)
        communication = {
            "timestamp": signal.timestamp,
            "symbol": signal.symbol,
            "contract_version": "edge.pulse.handoff.v1",
            "action": "buy",
            "pulse_ticker_created": created,
            "execution_style": signal.execution_style,
            "squeeze_triggered": signal.squeeze_triggered,
            "edge_score": signal.score,
            "edge_expected_value_pct": signal.expected_value_pct,
            "status": "attempted",
        }
        frame = data.get(signal.symbol, pd.DataFrame())
        fill = simulate_entry(signal, frame, config)
        if fill is None:
            missed += 1
            communication.update({"status": "missed_fill", "accepted": False})
            communications.append(communication)
            continue
        communication.update({
            "status": "filled", "accepted": True, "fill_source": fill["source"],
            "fill_delay_minutes": fill["delay"], "rebracket_count": fill["rebrackets"],
            "fill_price": round(fill["price"], 8),
        })
        communications.append(communication)
        exit_info = simulate_exit(signal, frame, fill, config, sell_events.get(signal.symbol, []))
        entry = finite(fill["price"])
        exit_price = finite(exit_info["price"])
        position_notional = min(capital, 1000.0)
        quantity = position_notional / entry if entry > 0 else 0.0
        gross = (exit_price - entry) * quantity
        round_trip_cost = position_notional * 0.0010
        net = gross - round_trip_cost
        capital += net
        peak = max(peak, capital)
        drawdown = ((peak - capital) / peak) * 100.0 if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        trade = TradeRecord(
            symbol=signal.symbol, signal_timestamp=signal.timestamp, entry_timestamp=iso(fill["timestamp"]),
            exit_timestamp=iso(exit_info["timestamp"]), entry_price=round(entry, 8), exit_price=round(exit_price, 8),
            quantity=round(quantity, 8), gross_pnl=round(gross, 4), net_pnl=round(net, 4),
            return_pct=round((net / position_notional) * 100.0 if position_notional > 0 else 0.0, 4),
            exit_reason=str(exit_info["reason"]), execution_style=signal.execution_style,
            fill_source=fill["source"], fill_delay_minutes=int(fill["delay"]),
            rebracket_count=int(fill["rebrackets"]), squeeze_triggered=signal.squeeze_triggered,
            max_favorable_pct=round(finite(exit_info["mfe"]), 4), max_adverse_pct=round(finite(exit_info["mae"]), 4),
        )
        trades.append(trade)
        busy_until = pd.Timestamp(trade.exit_timestamp) + timedelta(minutes=5)

    wins = [trade for trade in trades if trade.net_pnl > 0]
    returns = [trade.return_pct for trade in trades]
    gross_profit = sum(max(0.0, trade.net_pnl) for trade in trades)
    gross_loss = abs(sum(min(0.0, trade.net_pnl) for trade in trades))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    result = {
        **asdict(config), "starting_capital": starting_capital, "ending_capital": round(capital, 4),
        "net_profit": round(capital - starting_capital, 4), "net_return_pct": round((capital / starting_capital - 1.0) * 100.0, 4),
        "trade_count": len(trades), "win_rate_pct": round((len(wins) / len(trades)) * 100.0, 4) if trades else 0.0,
        "average_trade_pct": round(statistics.mean(returns), 4) if returns else 0.0,
        "median_trade_pct": round(statistics.median(returns), 4) if returns else 0.0,
        "profit_factor": round(profit_factor, 4), "max_drawdown_pct": round(max_drawdown, 4),
        "missed_fill_count": missed, "fill_rate_pct": round((len(trades) / max(1, len(trades) + missed)) * 100.0, 4),
        "ticker_creations": sum(1 for item in communications if item["pulse_ticker_created"]),
        "edge_handoff_fills": sum(1 for trade in trades if trade.fill_source == "edge_handoff"),
        "pulse_rebracket_fills": sum(1 for trade in trades if trade.fill_source == "pulse_rebracket"),
        "squeeze_trade_count": sum(1 for trade in trades if trade.squeeze_triggered),
    }
    result["objective"] = round(result["net_return_pct"] - 0.35 * result["max_drawdown_pct"], 6)
    return result, trades, communications


def coarse_configs() -> list[SweepConfig]:
    return [
        SweepConfig(band, threshold, spread, buffer)
        for band in (0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00)
        for threshold in (0.25, 0.50, 1.00, 2.00)
        for spread in (0.50, 0.80, 1.20, 2.00)
        for buffer in (0.05, 0.10, 0.20)
    ]


def fine_configs(top: list[dict[str, Any]]) -> list[SweepConfig]:
    configs: dict[tuple[Any, ...], SweepConfig] = {}
    for row in top[:12]:
        for lookback in (5, 10, 20):
            for cooldown in (0, 5, 15):
                config = SweepConfig(
                    band_pct=finite(row["band_pct"]), rebracket_threshold_pct=finite(row["rebracket_threshold_pct"]),
                    rebracket_spread_pct=finite(row["rebracket_spread_pct"]), rebracket_buffer_pct=finite(row["rebracket_buffer_pct"]),
                    rebracket_lookback=lookback, rebracket_cooldown_minutes=cooldown,
                )
                configs[tuple(asdict(config).values())] = config
    return list(configs.values())


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def save_minute_bars(path: Path, data: dict[str, pd.DataFrame], universe: list[str]) -> None:
    with gzip.open(path, "wt", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "timestamp", "open", "high", "low", "close", "volume"])
        for symbol in universe:
            for ts, row in data.get(symbol, pd.DataFrame()).iterrows():
                writer.writerow([symbol, iso(ts), row["open"], row["high"], row["low"], row["close"], row["volume"]])


def coverage_rows(data: dict[str, pd.DataFrame], symbols: list[str]) -> list[dict[str, Any]]:
    rows = []
    for symbol in symbols:
        frame = data.get(symbol, pd.DataFrame())
        regular = regular_session(frame)
        rows.append({
            "symbol": symbol, "available": not frame.empty, "bar_count_all_sessions": len(frame),
            "bar_count_regular_session": len(regular), "first_timestamp": iso(frame.index[0]) if not frame.empty else None,
            "last_timestamp": iso(frame.index[-1]) if not frame.empty else None,
            "median_price": round(finite(regular["close"].median()), 4) if not regular.empty else None,
        })
    return rows


def self_test() -> None:
    index = pd.date_range("2026-07-01 13:30:00+00:00", periods=120, freq="1min")
    prices = np.linspace(10.0, 10.6, len(index))
    frame = pd.DataFrame({
        "open": prices, "high": prices + 0.03, "low": prices - 0.03, "close": prices,
        "volume": np.full(len(index), 1000.0),
    }, index=index)
    signal = SignalRecord(
        timestamp=iso(index[10]), symbol="TEST", score=40, confidence=0.8, signal_strength=5,
        strategy="multi_timeframe_trend", regime="trending_up", entry_price=float(prices[10]),
        maximum_entry_price=float(prices[10] * 1.01), initial_stop=float(prices[10] * 0.98),
        target_1=float(prices[10] * 1.02), target_2=float(prices[10] * 1.03),
        execution_style="timed_limit", entry_trigger=0.0, squeeze_triggered=False,
        squeeze_pressure_score=0.0, orb_direction="neutral", selected_rank=1,
        expected_value_pct=0.5, reward_risk=2.0,
    )
    result, trades, communications = simulate_config(SweepConfig(0.5, 0.5, 0.8, 0.1), [signal], {"TEST": frame}, {"TEST": []})
    assert communications and communications[0]["pulse_ticker_created"]
    assert result["ticker_creations"] == 1
    assert result["trade_count"] in {0, 1}
    print("self-test passed")


async def main_async(args: argparse.Namespace) -> int:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    all_candidates = list(dict.fromkeys(CORE_SYMBOLS + PENNY_CANDIDATES))
    data, provider_meta = download_data(all_candidates, start, end, args.provider)
    breakout_table = daily_breakout_table(data, PENNY_CANDIDATES)
    penny_symbols = choose_penny_breakouts(breakout_table, 5)
    universe = [symbol for symbol in CORE_SYMBOLS if symbol in data] + penny_symbols
    universe = list(dict.fromkeys(universe))
    if len(universe) < 20:
        for symbol in PENNY_CANDIDATES:
            if symbol in data and symbol not in universe:
                universe.append(symbol)
            if len(universe) >= 20:
                break
    if len(universe) < 20:
        raise RuntimeError(f"Only {len(universe)} symbols had usable minute data; 20 are required")
    universe = universe[:20]
    penny_symbols = [symbol for symbol in penny_symbols if symbol in universe][:5]
    if len(penny_symbols) < 5:
        raise RuntimeError(f"Only {len(penny_symbols)} penny breakout symbols qualified with data")

    signals, sell_events, edge_meta = await build_edge_signal_stream(data, universe, penny_symbols, breakout_table, args.eval_minutes)
    if not signals:
        raise RuntimeError("Edge produced no selected BUY handoffs over the replay period")

    grid_rows: list[dict[str, Any]] = []
    best_trades: list[TradeRecord] = []
    best_communications: list[dict[str, Any]] = []
    best_result: Optional[dict[str, Any]] = None
    for config in coarse_configs():
        result, trades, communications = simulate_config(config, signals, data, sell_events)
        grid_rows.append(result)
        if best_result is None or result["objective"] > best_result["objective"]:
            best_result, best_trades, best_communications = result, trades, communications
    coarse_sorted = sorted(grid_rows, key=lambda row: row["objective"], reverse=True)
    for config in fine_configs(coarse_sorted):
        result, trades, communications = simulate_config(config, signals, data, sell_events)
        grid_rows.append(result)
        if best_result is None or result["objective"] > best_result["objective"]:
            best_result, best_trades, best_communications = result, trades, communications
    grid_rows.sort(key=lambda row: row["objective"], reverse=True)

    baseline_config = SweepConfig(3.0, 2.0, 0.8, 0.1, 10, 0)
    baseline, baseline_trades, baseline_comms = simulate_config(baseline_config, signals, data, sell_events)

    coverage = coverage_rows(data, all_candidates)
    write_csv(output / "data-coverage.csv", coverage)
    write_csv(output / "penny-breakout-ranking.csv", breakout_table.to_dict("records") if not breakout_table.empty else [])
    write_csv(output / "edge-selected-signals.csv", [asdict(item) for item in signals])
    write_csv(output / "parameter-grid.csv", grid_rows)
    write_csv(output / "best-trades.csv", [asdict(item) for item in best_trades])
    write_csv(output / "best-communications.csv", best_communications)
    write_csv(output / "baseline-trades.csv", [asdict(item) for item in baseline_trades])
    write_csv(output / "baseline-communications.csv", baseline_comms)
    save_minute_bars(output / "minute-bars.csv.gz", data, universe)

    style_summary: dict[str, dict[str, Any]] = {}
    for style in ("passive_limit", "timed_limit", "breakout_stop_limit"):
        trades = [trade for trade in best_trades if trade.execution_style == style]
        comms = [item for item in best_communications if item["execution_style"] == style]
        style_summary[style] = {
            "attempts": len(comms), "fills": len(trades),
            "missed_fills": sum(1 for item in comms if item["status"] == "missed_fill"),
            "fill_rate_pct": round(len(trades) / max(1, len(comms)) * 100.0, 4),
            "net_pnl": round(sum(trade.net_pnl for trade in trades), 4),
            "average_return_pct": round(statistics.mean([trade.return_pct for trade in trades]), 4) if trades else 0.0,
            "average_fill_delay_minutes": round(statistics.mean([trade.fill_delay_minutes for trade in trades]), 4) if trades else 0.0,
            "average_post_fill_mfe_pct": round(statistics.mean([trade.max_favorable_pct for trade in trades]), 4) if trades else 0.0,
            "average_post_fill_mae_pct": round(statistics.mean([trade.max_adverse_pct for trade in trades]), 4) if trades else 0.0,
        }

    report = {
        "contract_version": "edge.pulse.minute_sweep.v1", "generated_at": datetime.now(UTC).isoformat(),
        "period": {"start": start.isoformat(), "end_exclusive": end.isoformat(), "interval": "1m"},
        "provider": provider_meta, "pulse_starting_symbols": sorted(PULSE_DEFAULTS),
        "edge_test_universe": universe, "penny_breakout_symbols": penny_symbols,
        "penny_breakout_data": breakout_table[breakout_table["symbol"].isin(penny_symbols)].to_dict("records") if not breakout_table.empty else [],
        "edge_generation": edge_meta, "signal_count": len(signals), "baseline": baseline, "best": best_result,
        "improvement_vs_baseline": {
            "net_profit": round(finite(best_result["net_profit"]) - finite(baseline["net_profit"]), 4),
            "net_return_pct": round(finite(best_result["net_return_pct"]) - finite(baseline["net_return_pct"]), 4),
            "max_drawdown_pct": round(finite(best_result["max_drawdown_pct"]) - finite(baseline["max_drawdown_pct"]), 4),
        },
        "execution_style_attribution": style_summary,
        "grid": {"coarse_config_count": len(coarse_configs()), "total_result_count": len(grid_rows), "top_10": grid_rows[:10]},
        "limitations": [
            "Minute OHLCV is real provider data, but historical bid/ask is approximated from each minute range.",
            "Historical short-interest snapshots are unavailable from the selected providers; squeeze pressure inputs are synthetic stress overlays while price, volume and ORB confirmation remain historical.",
            "The replay starts Pulse with repository canonical defaults, not a live user MongoDB watchlist.",
            "Results are research output and do not establish live profitability.",
        ],
    }
    (output / "experiment-report.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown = f"""# Edge ↔ Pulse minute-candle sweep\n\n- Period: `{start}` through `{end - timedelta(days=1)}`\n- Provider: `{provider_meta.get('provider')}`\n- Minute bars: `{sum(len(data.get(symbol, [])) for symbol in universe):,}`\n- Edge-only symbols: `{', '.join(universe)}`\n- Penny breakout stress symbols: `{', '.join(penny_symbols)}`\n- Edge selected BUY handoffs: `{len(signals)}`\n\n## Best configuration\n\n```json\n{json.dumps(best_result, indent=2, sort_keys=True)}\n```\n\n## Canonical baseline\n\n```json\n{json.dumps(baseline, indent=2, sort_keys=True)}\n```\n\n## Important limitation\n\nHistorical squeeze pressure is a synthetic stress overlay because the minute-bar providers do not supply historical borrow/utilization snapshots. Price, volume, ORB, entries and exits use historical minute bars.\n"""
    (output / "README.md").write_text(markdown, encoding="utf-8")
    print(json.dumps({"best": best_result, "baseline": baseline, "universe": universe, "penny_symbols": penny_symbols, "signals": len(signals)}, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-06-19")
    parser.add_argument("--end", default="2026-07-18", help="Exclusive end date")
    parser.add_argument("--provider", choices=("auto", "alpaca", "yfinance"), default="auto")
    parser.add_argument("--eval-minutes", type=int, default=5)
    parser.add_argument("--output", default="artifacts/edge-pulse-minute-sweep")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        self_test()
        return 0
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
