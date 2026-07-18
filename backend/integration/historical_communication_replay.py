#!/usr/bin/env python3
"""Historical Edge -> Pulse communication replay.

This is a communication and state-synchronization test, not a profitability
backtest. It uses real hourly OHLCV bars for the requested windows, runs Edge's
authoritative enhanced brain without future data, serializes real handoff
commands, and sends them to a persistent worker that imports Pulse's real
schema, v2/v3 intent consumer, route logic, and durable idempotency helpers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

import edge_brain_patch  # noqa: F401 - install authoritative brain + supervision
from automation import AutomationAction, AutomationMode, HandoffCommand
from edge_brain_runtime import _BRAIN_CONTEXT
from engine import Decision, DecisionEngine
from signals import TrendDirection as DecisionTrend
from signals_enhanced import SignalEngineEnhanced


WINDOWS = {
    "oct_nov_2025": ("2025-10-01", "2025-12-01"),
    "jan_feb_2026": ("2026-01-01", "2026-03-01"),
}
DEFAULT_SYMBOLS = ("SPY", "QQQ", "AAPL", "NVDA", "TSLA")
DOWNLOAD_START = "2025-07-01"
DOWNLOAD_END = "2026-03-02"
SAFE_REJECTIONS = {
    "stop_widening_blocked",
    "stop_above_market",
    "no_position",
    "already_have_position",
}


class PulseWorker:
    def __init__(self, worker_path: Path, pulse_backend: Path) -> None:
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        self.process = subprocess.Popen(
            [sys.executable, str(worker_path), str(pulse_backend)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
        )

    def request(self, message: dict[str, Any]) -> dict[str, Any]:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("Pulse replay worker pipes are unavailable")
        self.process.stdin.write(json.dumps(message, sort_keys=True, default=str) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            stderr = self.process.stderr.read() if self.process.stderr else ""
            raise RuntimeError(f"Pulse replay worker exited unexpectedly: {stderr[-4000:]}")
        return json.loads(line)

    def reset(self) -> None:
        result = self.request({"op": "reset"})
        if not result.get("ok"):
            raise RuntimeError(f"Pulse worker reset failed: {result}")

    def send(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request({"op": "process", "payload": payload})

    def close(self) -> None:
        try:
            self.request({"op": "stop"})
        except Exception:
            pass
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def _normalise_download(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        raise RuntimeError(f"No hourly history returned for {symbol}")
    result = frame.copy()
    if isinstance(result.columns, pd.MultiIndex):
        result.columns = [str(column[0]).strip().lower().replace(" ", "_") for column in result.columns]
    else:
        result.columns = [str(column).strip().lower().replace(" ", "_") for column in result.columns]
    required = ["open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in result.columns]
    if missing:
        raise RuntimeError(f"{symbol} hourly history is missing columns: {missing}")
    result = result[required].apply(pd.to_numeric, errors="coerce").dropna()
    result = result[~result.index.duplicated(keep="last")].sort_index()
    index = pd.DatetimeIndex(result.index)
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    result.index = index
    if len(result) < 250:
        raise RuntimeError(f"Insufficient hourly history for {symbol}: {len(result)} rows")
    return result


def download_history(symbol: str, attempts: int = 3) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            frame = yf.download(
                symbol,
                start=DOWNLOAD_START,
                end=DOWNLOAD_END,
                interval="1h",
                auto_adjust=False,
                progress=False,
                prepost=False,
                threads=False,
            )
            return _normalise_download(frame, symbol)
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    raise RuntimeError(f"Could not download {symbol} hourly history: {last_error}")


def _aggregate(frame: pd.DataFrame, rule: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    aggregated = frame.resample(rule).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return aggregated.dropna().tail(240)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _current_position(result: dict[str, Any]) -> dict[str, float]:
    position = result.get("position")
    return position if isinstance(position, dict) else {}


def _sync_edge_position(
    decision_engine: DecisionEngine,
    symbol: str,
    pulse_result: dict[str, Any],
) -> None:
    position = _current_position(pulse_result)
    quantity = _float(position.get("qty"))
    if quantity <= 0:
        decision_engine.positions.pop(symbol, None)
        return
    decision_engine.positions[symbol] = {
        "size": quantity,
        "entry_price": _float(position.get("avg_entry")),
        "last_updated": datetime.now(timezone.utc),
    }


def _record_result(
    report: dict[str, Any],
    payload: dict[str, Any],
    result: dict[str, Any],
    *,
    source: str,
) -> None:
    report["commands"] += 1
    action = str(payload.get("action") or "unknown")
    intent = ((payload.get("metadata") or {}).get("execution_intent") or {})
    directive = str(intent.get("directive") or action)
    report["actions"][action] += 1
    report["directives"][directive] += 1
    report["sources"][source] += 1

    if not result.get("ok"):
        report["errors"].append(result)
        return
    response = result.get("response") or {}
    status = str(response.get("status") or "unknown")
    reason = str(response.get("reason") or "unknown")
    report["statuses"][status] += 1
    report["reasons"][reason] += 1
    if response.get("duplicate") or result.get("claim_state") == "replay":
        report["duplicates"] += 1
    if bool(response.get("accepted") or response.get("sent")):
        report["accepted"] += 1
    else:
        report["rejected"] += 1
        if reason in SAFE_REJECTIONS:
            report["safe_rejections"] += 1
        else:
            report["unexpected_rejections"].append(
                {
                    "symbol": payload.get("symbol"),
                    "action": action,
                    "directive": directive,
                    "reason": reason,
                    "message": response.get("message"),
                    "source": source,
                }
            )


def _command(
    *,
    symbol: str,
    action: AutomationAction,
    price: float,
    reason: str,
    replay_id: str,
    historical_timestamp: pd.Timestamp,
    confidence: float = 0.90,
    stop_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> HandoffCommand:
    merged = {
        "price": round(float(price), 8),
        "decision_id": replay_id,
        "historical_timestamp": historical_timestamp.isoformat(),
        "historical_replay": True,
        "strategy": "historical_communication_replay",
        "command_ttl_seconds": 600,
        **(metadata or {}),
    }
    return HandoffCommand(
        symbol=symbol,
        action=action,
        confidence=max(0.0, min(1.0, float(confidence))),
        reason=reason,
        mode=AutomationMode.PAPER,
        orb_session="market_open",
        stop_type=stop_type,
        created_at=time.time(),
        metadata=merged,
    )


def _send_command(
    worker: PulseWorker,
    decision_engine: DecisionEngine,
    report: dict[str, Any],
    command: HandoffCommand,
    *,
    source: str,
    duplicate: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = command.payload()
    result = worker.send(payload)
    _record_result(report, payload, result, source=source)
    _sync_edge_position(decision_engine, command.symbol, result)
    if duplicate:
        replay = worker.send(payload)
        _record_result(report, payload, replay, source=f"{source}_duplicate")
        _sync_edge_position(decision_engine, command.symbol, replay)
        return result, replay
    return result, {}


async def _analyze_bar(
    signal_engine: SignalEngineEnhanced,
    decision_engine: DecisionEngine,
    symbol: str,
    history_to_bar: pd.DataFrame,
) -> tuple[Any, Decision, dict[str, Any]]:
    hourly = history_to_bar.tail(240)
    frames = {
        "1h": hourly,
        "4h": _aggregate(history_to_bar, "4h"),
        "1d": _aggregate(history_to_bar, "1D"),
    }
    context: dict[str, Any] = {"multi_frames": frames}
    token = _BRAIN_CONTEXT.set(context)
    try:
        analysis = await signal_engine.analyze(
            symbol,
            hourly,
            timeframe="1h",
            higher_tf_data=frames["1d"],
        )
        context["analysis"] = analysis
        position = decision_engine.positions.get(symbol) or {}
        quantity = _float(position.get("size"))
        entry = _float(position.get("entry_price"))
        pnl_pct = (
            ((float(analysis.price) - entry) / entry) * 100.0
            if quantity > 0 and entry > 0
            else 0.0
        )
        decision = decision_engine.decide(
            symbol=symbol,
            trend=DecisionTrend.NEUTRAL,
            signal_strength=0.0,
            confidence=0.0,
            pnl=0.0,
            pnl_pct=pnl_pct,
            current_drawdown=max(0.0, -pnl_pct),
            has_position=quantity > 0,
            trailing_enabled=False,
        )
        return analysis, decision, dict(context)
    finally:
        _BRAIN_CONTEXT.reset(token)


def _new_window_report(start: str, end: str) -> dict[str, Any]:
    return {
        "start": start,
        "end_exclusive": end,
        "symbols": {},
        "bars": 0,
        "brain_evaluations": 0,
        "authoritative_analyses": 0,
        "commands": 0,
        "accepted": 0,
        "rejected": 0,
        "safe_rejections": 0,
        "duplicates": 0,
        "actions": Counter(),
        "directives": Counter(),
        "sources": Counter(),
        "statuses": Counter(),
        "reasons": Counter(),
        "errors": [],
        "unexpected_rejections": [],
        "protocol_assertions": [],
    }


async def replay_window(
    worker: PulseWorker,
    histories: dict[str, pd.DataFrame],
    window_name: str,
    start: str,
    end: str,
) -> dict[str, Any]:
    worker.reset()
    report = _new_window_report(start, end)
    signal_engine = SignalEngineEnhanced(enable_talib=False, multi_timeframe=True)
    decision_engine = DecisionEngine()

    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")

    for symbol, history in histories.items():
        in_window = history.loc[(history.index >= start_ts) & (history.index < end_ts)]
        if len(in_window) < 80:
            report["errors"].append(
                {"symbol": symbol, "error": f"only {len(in_window)} hourly bars in requested window"}
            )
            continue

        report["bars"] += len(in_window)
        symbol_report = {
            "bars": len(in_window),
            "first_bar": in_window.index[0].isoformat(),
            "last_bar": in_window.index[-1].isoformat(),
            "first_close": round(float(in_window["close"].iloc[0]), 4),
            "last_close": round(float(in_window["close"].iloc[-1]), 4),
            "brain_actions": Counter(),
        }
        report["symbols"][symbol] = symbol_report

        first_timestamp = in_window.index[0]
        first_price = float(in_window["close"].iloc[0])

        buy = _command(
            symbol=symbol,
            action=AutomationAction.BUY,
            price=first_price,
            reason=f"{window_name} protocol probe: establish paper position",
            replay_id=f"{window_name}:{symbol}:protocol:buy",
            historical_timestamp=first_timestamp,
            metadata={"target_notional": 1000.0, "max_notional": 1000.0},
        )
        buy_result, _ = _send_command(
            worker, decision_engine, report, buy, source="protocol_buy"
        )
        buy_accepted = bool((buy_result.get("response") or {}).get("accepted"))

        position = _current_position(buy_result)
        quantity = _float(position.get("qty"))
        stop_price = round(first_price * 0.98, 4)
        stop = _command(
            symbol=symbol,
            action=AutomationAction.TIGHTEN_STOP,
            price=first_price,
            reason=f"{window_name} protocol probe: install absolute protective stop",
            replay_id=f"{window_name}:{symbol}:protocol:set_stop",
            historical_timestamp=first_timestamp,
            stop_type="tighten",
            metadata={
                "supervisory_directive": "set_stop",
                "expected_position_quantity": quantity,
                "max_quantity_drift_percent": 0.1,
                "stop_price": stop_price,
                "tighten_only": True,
                "signal_strength": -2.5,
                "trend": "bearish",
            },
        )
        stop_result, _ = _send_command(
            worker, decision_engine, report, stop, source="protocol_set_stop"
        )
        stop_accepted = bool((stop_result.get("response") or {}).get("accepted"))

        reduce = _command(
            symbol=symbol,
            action=AutomationAction.SELL,
            price=first_price,
            reason=f"{window_name} protocol probe: reduce paper exposure by 25 percent",
            replay_id=f"{window_name}:{symbol}:protocol:reduce",
            historical_timestamp=first_timestamp,
            metadata={
                "supervisory_directive": "reduce_position",
                "expected_position_quantity": quantity,
                "max_quantity_drift_percent": 0.1,
                "reduce_percent": 25.0,
                "signal_strength": -4.0,
                "trend": "bearish",
            },
        )
        reduce_result, duplicate_result = _send_command(
            worker,
            decision_engine,
            report,
            reduce,
            source="protocol_reduce",
            duplicate=True,
        )
        reduce_accepted = bool((reduce_result.get("response") or {}).get("accepted"))
        duplicate_replayed = bool(
            (duplicate_result.get("response") or {}).get("duplicate")
            or duplicate_result.get("claim_state") == "replay"
        )

        report["protocol_assertions"].append(
            {
                "symbol": symbol,
                "buy_accepted": buy_accepted,
                "set_stop_accepted": stop_accepted,
                "reduce_accepted": reduce_accepted,
                "duplicate_replayed": duplicate_replayed,
            }
        )

        last_brain_action_index = -1000
        reductions_sent = 0
        for bar_index, timestamp in enumerate(in_window.index):
            if bar_index % 8 != 0:
                continue
            history_to_bar = history.loc[:timestamp]
            if len(history_to_bar) < 80:
                continue
            analysis, decision, context = await _analyze_bar(
                signal_engine,
                decision_engine,
                symbol,
                history_to_bar,
            )
            report["brain_evaluations"] += 1
            if bool((analysis.metadata or {}).get("enhanced_authoritative")):
                report["authoritative_analyses"] += 1

            if bar_index - last_brain_action_index < 24:
                continue

            current_position = decision_engine.positions.get(symbol) or {}
            current_quantity = _float(current_position.get("size"))
            directive = str(context.get("supervisory_directive") or "")
            command: HandoffCommand | None = None

            if directive == "set_stop" and current_quantity > 0:
                requested_stop = _float(context.get("stop_price"))
                if 0 < requested_stop < float(analysis.price):
                    command = _command(
                        symbol=symbol,
                        action=AutomationAction.TIGHTEN_STOP,
                        price=float(analysis.price),
                        reason=str(context.get("supervisory_reason") or "historical brain protective stop"),
                        replay_id=f"{window_name}:{symbol}:brain:set_stop:{timestamp.isoformat()}",
                        historical_timestamp=timestamp,
                        confidence=float(analysis.confidence.overall),
                        stop_type="tighten",
                        metadata={
                            "supervisory_directive": "set_stop",
                            "expected_position_quantity": current_quantity,
                            "max_quantity_drift_percent": 0.5,
                            "stop_price": requested_stop,
                            "tighten_only": True,
                            "signal_strength": float(analysis.signal_strength),
                            "trend": analysis.trend.name.lower(),
                        },
                    )
            elif directive == "reduce_position" and current_quantity > 0 and reductions_sent < 2:
                command = _command(
                    symbol=symbol,
                    action=AutomationAction.SELL,
                    price=float(analysis.price),
                    reason=str(context.get("supervisory_reason") or "historical brain exposure reduction"),
                    replay_id=f"{window_name}:{symbol}:brain:reduce:{timestamp.isoformat()}",
                    historical_timestamp=timestamp,
                    confidence=float(analysis.confidence.overall),
                    metadata={
                        "supervisory_directive": "reduce_position",
                        "expected_position_quantity": current_quantity,
                        "max_quantity_drift_percent": 0.5,
                        "reduce_percent": _float(context.get("reduce_percent"), 25.0),
                        "signal_strength": float(analysis.signal_strength),
                        "trend": analysis.trend.name.lower(),
                    },
                )
                reductions_sent += 1
            elif directive == "sell" and current_quantity > 0:
                command = _command(
                    symbol=symbol,
                    action=AutomationAction.SELL,
                    price=float(analysis.price),
                    reason=str(context.get("supervisory_reason") or "historical brain thesis invalidation"),
                    replay_id=f"{window_name}:{symbol}:brain:sell:{timestamp.isoformat()}",
                    historical_timestamp=timestamp,
                    confidence=float(analysis.confidence.overall),
                    metadata={
                        "signal_strength": float(analysis.signal_strength),
                        "trend": analysis.trend.name.lower(),
                        "supervisory_override": True,
                    },
                )
            elif decision == Decision.BUY and current_quantity <= 0:
                command = _command(
                    symbol=symbol,
                    action=AutomationAction.BUY,
                    price=float(analysis.price),
                    reason="Historical authoritative Edge brain entry",
                    replay_id=f"{window_name}:{symbol}:brain:buy:{timestamp.isoformat()}",
                    historical_timestamp=timestamp,
                    confidence=float(analysis.confidence.overall),
                    metadata={
                        "target_notional": 1000.0,
                        "max_notional": 1000.0,
                        "signal_strength": float(analysis.signal_strength),
                        "trend": analysis.trend.name.lower(),
                    },
                )

            if command is not None:
                result, _ = _send_command(
                    worker,
                    decision_engine,
                    report,
                    command,
                    source="brain",
                )
                response = result.get("response") or {}
                symbol_report["brain_actions"][
                    str(((command.payload().get("metadata") or {}).get("execution_intent") or {}).get("directive") or command.action.value)
                ] += 1
                if response.get("accepted"):
                    last_brain_action_index = bar_index

        final_position = decision_engine.positions.get(symbol) or {}
        final_quantity = _float(final_position.get("size"))
        if final_quantity > 0:
            last_timestamp = in_window.index[-1]
            last_price = float(in_window["close"].iloc[-1])
            close = _command(
                symbol=symbol,
                action=AutomationAction.SELL,
                price=last_price,
                reason=f"{window_name} protocol probe: close remaining paper position",
                replay_id=f"{window_name}:{symbol}:protocol:sell",
                historical_timestamp=last_timestamp,
                metadata={"historical_window_close": True},
            )
            close_result, _ = _send_command(
                worker, decision_engine, report, close, source="protocol_sell"
            )
            symbol_report["final_sell_accepted"] = bool(
                (close_result.get("response") or {}).get("accepted")
            )
        else:
            symbol_report["final_sell_accepted"] = True
            symbol_report["already_flat_at_end"] = True

        symbol_report["brain_actions"] = dict(symbol_report["brain_actions"])

    report["actions"] = dict(report["actions"])
    report["directives"] = dict(report["directives"])
    report["sources"] = dict(report["sources"])
    report["statuses"] = dict(report["statuses"])
    report["reasons"] = dict(report["reasons"])

    protocol_ok = all(
        item["buy_accepted"]
        and item["set_stop_accepted"]
        and item["reduce_accepted"]
        and item["duplicate_replayed"]
        for item in report["protocol_assertions"]
    )
    report["passed"] = bool(
        protocol_ok
        and not report["errors"]
        and not report["unexpected_rejections"]
        and report["brain_evaluations"] > 0
        and report["authoritative_analyses"] == report["brain_evaluations"]
    )
    return report


def _summary(report: dict[str, Any]) -> str:
    lines = []
    for name, window in report["windows"].items():
        lines.append(
            f"{name}: passed={window['passed']} bars={window['bars']} "
            f"brain_evaluations={window['brain_evaluations']} "
            f"commands={window['commands']} accepted={window['accepted']} "
            f"rejected={window['rejected']} duplicates={window['duplicates']} "
            f"directives={window['directives']}"
        )
    return "\n".join(lines)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    symbols = tuple(symbol.strip().upper() for symbol in args.symbols if symbol.strip())
    histories = {symbol: download_history(symbol) for symbol in symbols}
    worker_path = Path(__file__).with_name("pulse_historical_worker.py")
    worker = PulseWorker(worker_path, Path(args.pulse_backend).resolve())
    try:
        windows = {}
        for window_name, (start, end) in WINDOWS.items():
            windows[window_name] = await replay_window(
                worker,
                histories,
                window_name,
                start,
                end,
            )
    finally:
        worker.close()

    report = {
        "schema_version": "edge-pulse-historical-communication.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_source": {
            "provider": "Yahoo Finance via yfinance",
            "interval": "1h",
            "download_start": DOWNLOAD_START,
            "download_end_exclusive": DOWNLOAD_END,
            "symbols": list(symbols),
            "future_data_policy": "Each brain evaluation receives only bars at or before its replay timestamp.",
        },
        "pulse_backend": str(Path(args.pulse_backend).resolve()),
        "windows": windows,
    }
    report["passed"] = all(window["passed"] for window in windows.values())
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pulse-backend", required=True)
    parser.add_argument("--output", default="historical-communication-report.json")
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(run(args))
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(_summary(report))
    print(f"report={output.resolve()}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
