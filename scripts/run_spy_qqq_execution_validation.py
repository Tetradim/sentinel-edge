#!/usr/bin/env python3
"""Paper-only SPY/QQQ scalp validation.

Attempts authenticated Alpaca historical quote/trade data (SIP, then IEX) for an
exact bid/ask replay. Independently downloads one-minute bars and emits
stop-first/target-first bounds. Exact conclusions are never claimed when the
quote/trade feed is unavailable.
"""
from __future__ import annotations

import argparse
import json
import os
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

SYMBOLS = ("SPY", "QQQ")
HALF_WIDTHS = (0.25, 0.50, 0.75, 1.00)


def cents(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-06-19")
    parser.add_argument("--end", default="2026-07-18", help="exclusive")
    parser.add_argument("--exact-days", default="2026-07-15,2026-07-16,2026-07-17")
    parser.add_argument("--output", type=Path, default=Path("artifacts/edge-scalp-follow-tick-validation"))
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def self_test() -> None:
    assert cents(750.005) == 750.01
    assert cents(750.006) == 750.01
    observation = 750.0
    assert observation > cents(observation - 0.50)
    print("SPY/QQQ execution validation self-test passed")


def download_minute_bars(symbol: str, start: str, end: str) -> pd.DataFrame:
    import yfinance as yf
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    current = start_ts
    parts: list[pd.DataFrame] = []
    while current < end_ts:
        nxt = min(current + pd.Timedelta(days=6), end_ts)
        frame = yf.download(
            symbol,
            start=current.date().isoformat(),
            end=nxt.date().isoformat(),
            interval="1m",
            auto_adjust=False,
            prepost=False,
            progress=False,
            threads=False,
        )
        if not frame.empty:
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = [str(item[0]).lower() for item in frame.columns]
            else:
                frame.columns = [str(item).lower() for item in frame.columns]
            frame = frame.reset_index()
            time_col = "Datetime" if "Datetime" in frame.columns else "datetime"
            frame = frame.rename(columns={time_col: "timestamp"})
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
            frame["symbol"] = symbol
            parts.append(frame[["timestamp", "symbol", "open", "high", "low", "close", "volume"]])
        next_current = nxt - pd.Timedelta(days=1)
        current = nxt if next_current <= current else next_current
    if not parts:
        return pd.DataFrame()
    frame = pd.concat(parts, ignore_index=True).drop_duplicates(["timestamp", "symbol"])
    frame = frame.sort_values("timestamp")
    minute = frame.timestamp.dt.hour * 60 + frame.timestamp.dt.minute
    frame = frame[(minute >= 13 * 60 + 30) & (minute <= 20 * 60)].copy()
    frame["day"] = frame.timestamp.dt.date
    prior_close = frame.close.shift(1)
    true_range = pd.concat(
        [frame.high - frame.low, (frame.high - prior_close).abs(), (frame.low - prior_close).abs()], axis=1
    ).max(axis=1)
    frame["atr"] = true_range.rolling(14, min_periods=3).mean().fillna(true_range.expanding().mean())
    return frame


def minute_sequence_test(frame: pd.DataFrame, half_width: float, sequence: str) -> dict[str, Any]:
    pnl: list[float] = []
    recenters = 0
    for _, day in frame.groupby("day"):
        day = day.sort_values("timestamp")
        center = cents(day.iloc[0].close)
        position: dict[str, float] | None = None
        closes: deque[float] = deque(maxlen=7)
        last_recenter: pd.Timestamp | None = None
        up_count = down_count = 0
        for row in day.itertuples(index=False):
            price = cents(row.close)
            closes.append(price)
            trigger = max(4 * half_width, float(row.atr))
            if position:
                stop_hit = row.low <= position["stop"]
                target_hit = row.high >= position["target"]
                exit_price = None
                if stop_hit and target_hit:
                    exit_price = position["stop"] if sequence == "stop_first" else position["target"]
                elif stop_hit:
                    exit_price = position["stop"]
                elif target_hit:
                    exit_price = position["target"]
                elif row.timestamp.hour * 60 + row.timestamp.minute >= 19 * 60 + 55:
                    exit_price = price
                if exit_price is not None:
                    pnl.append((exit_price - position["entry"]) * (500 / position["entry"]))
                    position = None
            if position is None:
                distance = price - center
                up_count = up_count + 1 if distance >= trigger else 0
                down_count = down_count + 1 if distance <= -trigger else 0
                ready = last_recenter is None or (row.timestamp - last_recenter).total_seconds() >= 600
                if ready and len(closes) >= 5 and (up_count >= 3 or down_count >= 5):
                    recent = list(closes)[-5:]
                    stable = True
                    if down_count >= 5:
                        last_three = recent[-3:]
                        stable = int(np.argmin(last_three)) == 0 and last_three[-1] >= last_three[-2]
                    if stable:
                        new_center = cents(round(float(np.median(recent)) / 0.25) * 0.25)
                        if abs(new_center - center) >= half_width:
                            center = new_center
                            recenters += 1
                            last_recenter = row.timestamp
                        up_count = down_count = 0
                buy = cents(center - half_width)
                target = cents(center + half_width)
                if row.low <= buy and row.timestamp.hour * 60 + row.timestamp.minute <= 19 * 60 + 15:
                    position = {"entry": buy, "target": target, "stop": cents(buy - (target - buy))}
        if position:
            pnl.append((cents(day.iloc[-1].close) - position["entry"]) * (500 / position["entry"]))
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    return {
        "trades": len(pnl),
        "pnl": sum(pnl),
        "win_rate": 100 * len(wins) / len(pnl) if pnl else 0,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else 0,
        "recenters": recenters,
    }


def alpaca_headers() -> dict[str, str]:
    key = os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID") or ""
    secret = os.getenv("ALPACA_API_SECRET") or os.getenv("APCA_API_SECRET_KEY") or ""
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def fetch_alpaca(symbol: str, kind: str, day: str, feed: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    token = None
    url = f"https://data.alpaca.markets/v2/stocks/{symbol}/{kind}"
    while True:
        params = {
            "start": f"{day}T13:30:00Z",
            "end": f"{day}T20:00:00Z",
            "limit": 10000,
            "feed": feed,
            "sort": "asc",
        }
        if token:
            params["page_token"] = token
        response = requests.get(url, params=params, headers=alpaca_headers(), timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"{feed} {kind} {symbol}: {response.status_code} {response.text[:180]}")
        payload = response.json()
        rows.extend(payload.get(kind, []))
        token = payload.get("next_page_token")
        if not token:
            return rows


def exact_quote_test(events: list[dict[str, Any]], half_width: float, follow: bool) -> dict[str, Any]:
    if not events:
        return {"trades": 0, "pnl": 0, "win_rate": 0, "recenters": 0}
    bid = ask = center = None
    position = None
    pnl: list[float] = []
    recent: deque[float] = deque(maxlen=7)
    last_recenter = None
    up_count = down_count = recenters = 0
    for event in events:
        timestamp = event["timestamp"]
        observed = None
        if event["kind"] == "quote":
            bid, ask = event["bid"], event["ask"]
            if bid > 0 and ask >= bid:
                observed = (bid + ask) / 2
        else:
            observed = event["price"]
        if observed is None:
            continue
        if center is None:
            center = cents(observed)
        recent.append(observed)
        if position and bid is not None:
            exit_price = None
            if bid <= position["stop"]:
                exit_price = bid
            elif bid >= position["target"]:
                exit_price = bid
            elif timestamp.hour * 60 + timestamp.minute >= 19 * 60 + 55:
                exit_price = bid
            if exit_price is not None:
                pnl.append((exit_price - position["entry"]) * (500 / position["entry"]))
                position = None
        if position is None:
            if follow:
                distance = observed - center
                trigger = 4 * half_width
                up_count = up_count + 1 if distance >= trigger else 0
                down_count = down_count + 1 if distance <= -trigger else 0
                ready = last_recenter is None or (timestamp - last_recenter).total_seconds() >= 600
                if ready and len(recent) >= 5 and (up_count >= 3 or down_count >= 5):
                    sample = list(recent)[-5:]
                    stable = True
                    if down_count >= 5:
                        last_three = sample[-3:]
                        stable = int(np.argmin(last_three)) == 0 and last_three[-1] >= last_three[-2]
                    if stable:
                        new_center = cents(round(float(np.median(sample)) / 0.25) * 0.25)
                        if abs(new_center - center) >= half_width:
                            center = new_center
                            recenters += 1
                            last_recenter = timestamp
                        up_count = down_count = 0
            else:
                center = cents(observed)
            buy = cents(center - half_width)
            target = cents(center + half_width)
            if ask is not None and ask <= buy and timestamp.hour * 60 + timestamp.minute <= 19 * 60 + 15:
                if target > ask:
                    position = {"entry": ask, "target": target, "stop": cents(ask - (target - ask))}
    if position and bid is not None:
        pnl.append((bid - position["entry"]) * (500 / position["entry"]))
    return {
        "trades": len(pnl),
        "pnl": sum(pnl),
        "win_rate": 100 * sum(value > 0 for value in pnl) / len(pnl) if pnl else 0,
        "recenters": recenters,
    }


def main() -> None:
    args = parse_args()
    if args.self_test:
        self_test()
        return
    args.output.mkdir(parents=True, exist_ok=True)
    minute_frames = [download_minute_bars(symbol, args.start, args.end) for symbol in SYMBOLS]
    nonempty = [frame for frame in minute_frames if not frame.empty]
    bars = pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame()
    coverage = [
        {
            "symbol": symbol,
            "bars": int((bars.symbol == symbol).sum()) if not bars.empty else 0,
            "sessions": int(bars.loc[bars.symbol == symbol, "day"].nunique()) if not bars.empty else 0,
        }
        for symbol in SYMBOLS
    ]
    minute_rows = []
    for symbol in SYMBOLS:
        symbol_bars = bars[bars.symbol == symbol] if not bars.empty else pd.DataFrame()
        for half_width in HALF_WIDTHS:
            for sequence in ("stop_first", "target_first"):
                result = minute_sequence_test(symbol_bars, half_width, sequence) if not symbol_bars.empty else {}
                minute_rows.append({"symbol": symbol, "half_width": half_width, "sequence": sequence, **result})

    key_present = bool(alpaca_headers()["APCA-API-KEY-ID"] and alpaca_headers()["APCA-API-SECRET-KEY"])
    exact_provider = "unavailable"
    exact_error = "credentials missing" if not key_present else ""
    exact_rows: list[dict[str, Any]] = []
    exact_coverage: list[dict[str, Any]] = []
    days = [item.strip() for item in args.exact_days.split(",") if item.strip()]
    if key_present:
        for feed in ("sip", "iex"):
            try:
                candidate_rows = []
                candidate_coverage = []
                for symbol in SYMBOLS:
                    for day in days:
                        quotes = fetch_alpaca(symbol, "quotes", day, feed)
                        trades = fetch_alpaca(symbol, "trades", day, feed)
                        events = [
                            {
                                "timestamp": pd.Timestamp(item["t"]),
                                "kind": "quote",
                                "bid": float(item.get("bp") or 0),
                                "ask": float(item.get("ap") or 0),
                            }
                            for item in quotes
                        ]
                        events.extend(
                            {
                                "timestamp": pd.Timestamp(item["t"]),
                                "kind": "trade",
                                "price": float(item.get("p") or 0),
                            }
                            for item in trades
                        )
                        events.sort(key=lambda item: (item["timestamp"], item["kind"]))
                        spreads = [
                            item["ask"] - item["bid"]
                            for item in events
                            if item["kind"] == "quote" and item["bid"] > 0 and item["ask"] >= item["bid"]
                        ]
                        candidate_coverage.append(
                            {
                                "symbol": symbol,
                                "day": day,
                                "feed": feed,
                                "quotes": len(quotes),
                                "trades": len(trades),
                                "median_spread": float(np.median(spreads)) if spreads else None,
                            }
                        )
                        for half_width in HALF_WIDTHS:
                            candidate_rows.append(
                                {
                                    "symbol": symbol,
                                    "day": day,
                                    "feed": feed,
                                    "half_width": half_width,
                                    "profile": "step_follow",
                                    **exact_quote_test(events, half_width, True),
                                }
                            )
                            candidate_rows.append(
                                {
                                    "symbol": symbol,
                                    "day": day,
                                    "feed": feed,
                                    "half_width": half_width,
                                    "profile": "continuous_chase",
                                    **exact_quote_test(events, half_width, False),
                                }
                            )
                exact_provider = f"alpaca_{feed}"
                exact_error = ""
                exact_rows = candidate_rows
                exact_coverage = candidate_coverage
                break
            except Exception as exc:
                exact_error = str(exc)

    report = {
        "period": {"start": args.start, "end_exclusive": args.end},
        "minute_coverage": coverage,
        "exact_provider": exact_provider,
        "exact_error": exact_error,
        "exact_coverage": exact_coverage,
        "minute_sequence_bounds": minute_rows,
        "exact_results": exact_rows,
        "limitation": None
        if exact_rows
        else "No authenticated historical quote/trade feed was available; exact tick conclusions are not claimed.",
    }
    (args.output / "latest.json").write_text(json.dumps(report, indent=2))
    pd.DataFrame(minute_rows).to_csv(args.output / "minute-sequence-bounds.csv", index=False)
    pd.DataFrame(exact_rows).to_csv(args.output / "exact-results.csv", index=False)
    pd.DataFrame(exact_coverage).to_csv(args.output / "exact-coverage.csv", index=False)
    print(json.dumps({"exact_provider": exact_provider, "exact_error": exact_error, "coverage": coverage}, indent=2))


if __name__ == "__main__":
    main()
