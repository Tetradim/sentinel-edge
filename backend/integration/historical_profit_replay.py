#!/usr/bin/env python3
"""Brain-only and protocol-path profitability replay for Edge -> Pulse.

The replay uses real hourly Yahoo Finance OHLCV for the same historical windows
as the communication audit. Edge receives no future bars. Pulse's real handoff
schema, execution-intent consumer, route logic, and idempotency layer execute
all orders in the existing paper worker.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from automation import AutomationAction
from edge_brain_runtime import _BRAIN_CONTEXT
from engine import Decision, DecisionEngine
from signals import TrendDirection as DecisionTrend
from signals_enhanced import SignalEngineEnhanced
from integration.historical_communication_replay import (
    DEFAULT_SYMBOLS,
    WINDOWS,
    PulseWorker,
    _aggregate,
    _command,
    _float,
    _sync_edge_position,
    download_history,
)

STARTING_CAPITAL = 1000.0
COST_BPS = 5.0
EVALUATION_EVERY_BARS = 8
ACTION_COOLDOWN_BARS = 24


@dataclass
class Ledger:
    cash: float = STARTING_CAPITAL
    costs: float = 0.0
    cycle_pnl: float = 0.0
    trade_pnls: list[float] = field(default_factory=list)
    fills: list[dict[str, Any]] = field(default_factory=list)
    peak: float = STARTING_CAPITAL
    max_drawdown_pct: float = 0.0
    last_equity: float = STARTING_CAPITAL

    def fill(self, timestamp, symbol, source, price, old_position, new_position):
        old_qty = _float(old_position.get("size"))
        new_qty = _float(new_position.get("size"))
        old_entry = _float(old_position.get("entry_price"))
        delta = new_qty - old_qty
        if abs(delta) < 1e-10:
            return
        self.costs += abs(delta) * price * COST_BPS / 10000.0
        realized = 0.0
        if delta > 0:
            self.cash -= delta * price
            side = "buy"
        else:
            sold = -delta
            self.cash += sold * price
            realized = (price - old_entry) * sold
            self.cycle_pnl += realized
            side = "sell"
            if new_qty <= 1e-10:
                self.trade_pnls.append(self.cycle_pnl)
                self.cycle_pnl = 0.0
        self.fills.append({
            "timestamp": timestamp.isoformat(),
            "symbol": symbol,
            "source": source,
            "side": side,
            "price": round(price, 6),
            "quantity": round(abs(delta), 8),
            "gross_realized_pnl": round(realized, 6),
            "remaining_quantity": round(new_qty, 8),
        })

    def mark(self, close_price, position):
        equity = self.cash + _float(position.get("size")) * close_price
        self.last_equity = equity
        self.peak = max(self.peak, equity)
        if self.peak > 0:
            self.max_drawdown_pct = max(
                self.max_drawdown_pct,
                (self.peak - equity) / self.peak * 100.0,
            )

    def summary(self):
        gross = self.last_equity - STARTING_CAPITAL
        wins = sum(pnl > 0 for pnl in self.trade_pnls)
        losses = sum(pnl < 0 for pnl in self.trade_pnls)
        trades = len(self.trade_pnls)
        return {
            "starting_capital": STARTING_CAPITAL,
            "ending_equity_gross": round(self.last_equity, 4),
            "gross_pnl": round(gross, 4),
            "estimated_costs_5bps_per_side": round(self.costs, 4),
            "net_pnl_after_estimated_costs": round(gross - self.costs, 4),
            "gross_return_pct": round(gross / STARTING_CAPITAL * 100.0, 4),
            "net_return_pct_after_estimated_costs": round(
                (gross - self.costs) / STARTING_CAPITAL * 100.0, 4
            ),
            "max_drawdown_pct": round(self.max_drawdown_pct, 4),
            "closed_trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wins / trades * 100.0, 2) if trades else None,
            "fills": self.fills,
        }


def position(engine, symbol):
    return dict(engine.positions.get(symbol) or {})


def accepted(result):
    response = result.get("response") or {}
    return bool(result.get("ok") and (response.get("accepted") or response.get("sent")))


def send(worker, engine, ledger, command, timestamp, price, source):
    before = position(engine, command.symbol)
    result = worker.send(command.payload())
    _sync_edge_position(engine, command.symbol, result)
    after = position(engine, command.symbol)
    if accepted(result):
        ledger.fill(timestamp, command.symbol, source, price, before, after)
    return result


async def analyze(signal_engine, decision_engine, symbol, history_to_bar):
    hourly = history_to_bar.tail(240)
    frames = {
        "1h": hourly,
        "4h": _aggregate(history_to_bar, "4h"),
        "1d": _aggregate(history_to_bar, "1D"),
    }
    context = {"multi_frames": frames}
    token = _BRAIN_CONTEXT.set(context)
    try:
        result = await signal_engine.analyze(
            symbol, hourly, timeframe="1h", higher_tf_data=frames["1d"]
        )
        context["analysis"] = result
        current = position(decision_engine, symbol)
        qty = _float(current.get("size"))
        entry = _float(current.get("entry_price"))
        pnl_pct = ((float(result.price) - entry) / entry * 100.0) if qty and entry else 0.0
        decision = decision_engine.decide(
            symbol=symbol,
            trend=DecisionTrend.NEUTRAL,
            signal_strength=0.0,
            confidence=0.0,
            pnl=0.0,
            pnl_pct=pnl_pct,
            current_drawdown=max(0.0, -pnl_pct),
            has_position=qty > 0,
            trailing_enabled=False,
        )
        return result, decision, dict(context)
    finally:
        _BRAIN_CONTEXT.reset(token)


def build_command(window, symbol, timestamp, price, analysis, decision, context, qty):
    directive = str(context.get("supervisory_directive") or "")
    common = {
        "signal_strength": float(analysis.signal_strength),
        "trend": analysis.trend.name.lower(),
    }
    if directive == "set_stop" and qty > 0:
        stop = _float(context.get("stop_price"))
        if 0 < stop < float(analysis.price):
            return _command(
                symbol=symbol,
                action=AutomationAction.TIGHTEN_STOP,
                price=price,
                reason=str(context.get("supervisory_reason") or "Brain protective stop"),
                replay_id=f"profit:{window}:{symbol}:stop:{timestamp.isoformat()}",
                historical_timestamp=timestamp,
                confidence=float(analysis.confidence.overall),
                stop_type="tighten",
                metadata={
                    "supervisory_directive": "set_stop",
                    "expected_position_quantity": qty,
                    "max_quantity_drift_percent": 0.5,
                    "stop_price": stop,
                    "tighten_only": True,
                    **common,
                },
            ), "edge_set_stop"
    if directive == "reduce_position" and qty > 0:
        return _command(
            symbol=symbol,
            action=AutomationAction.SELL,
            price=price,
            reason=str(context.get("supervisory_reason") or "Brain exposure reduction"),
            replay_id=f"profit:{window}:{symbol}:reduce:{timestamp.isoformat()}",
            historical_timestamp=timestamp,
            confidence=float(analysis.confidence.overall),
            metadata={
                "supervisory_directive": "reduce_position",
                "expected_position_quantity": qty,
                "max_quantity_drift_percent": 0.5,
                "reduce_percent": _float(context.get("reduce_percent"), 25.0),
                **common,
            },
        ), "edge_reduce_position"
    if directive == "sell" and qty > 0:
        return _command(
            symbol=symbol,
            action=AutomationAction.SELL,
            price=price,
            reason=str(context.get("supervisory_reason") or "Brain thesis invalidation"),
            replay_id=f"profit:{window}:{symbol}:sell:{timestamp.isoformat()}",
            historical_timestamp=timestamp,
            confidence=float(analysis.confidence.overall),
            metadata={"supervisory_override": True, **common},
        ), "edge_sell"
    if decision == Decision.BUY and qty <= 0:
        return _command(
            symbol=symbol,
            action=AutomationAction.BUY,
            price=price,
            reason="Historical authoritative Edge brain entry",
            replay_id=f"profit:{window}:{symbol}:buy:{timestamp.isoformat()}",
            historical_timestamp=timestamp,
            confidence=float(analysis.confidence.overall),
            metadata={"target_notional": 1000.0, "max_notional": 1000.0, **common},
        ), "edge_buy"
    return None


async def replay_symbol(worker, history, symbol, window, start, end):
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    frame = history.loc[(history.index >= start_ts) & (history.index < end_ts)]
    signal_engine = SignalEngineEnhanced(enable_talib=False, multi_timeframe=True)
    decision_engine = DecisionEngine()
    ledger = Ledger()
    active_stop = None
    pending = None
    last_action = -1000
    evaluations = authoritative = accepted_count = rejected_count = 0
    reasons = {}

    for index, (timestamp, bar) in enumerate(frame.iterrows()):
        open_price = float(bar["open"])
        close_price = float(bar["close"])

        if pending is not None:
            command, source = pending
            command.metadata["price"] = round(open_price, 8)
            result = send(
                worker, decision_engine, ledger, command, timestamp, open_price, source
            )
            response = result.get("response") or {}
            reason = str(response.get("reason") or result.get("error") or "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
            if accepted(result):
                accepted_count += 1
                last_action = index
                ticker = result.get("ticker") or {}
                if ticker.get("stop_percent") is False:
                    candidate = _float(ticker.get("stop_offset"))
                    if candidate > 0:
                        active_stop = candidate
                if _float((result.get("position") or {}).get("qty")) <= 0:
                    active_stop = None
            else:
                rejected_count += 1
            pending = None

        current = position(decision_engine, symbol)
        if _float(current.get("size")) > 0 and active_stop is not None:
            trigger = None
            if open_price <= active_stop:
                trigger = open_price
            elif float(bar["low"]) <= active_stop:
                trigger = active_stop
            if trigger is not None:
                command = _command(
                    symbol=symbol,
                    action=AutomationAction.SELL,
                    price=trigger,
                    reason="Pulse historical absolute stop trigger",
                    replay_id=f"profit:{window}:{symbol}:pulse_stop:{timestamp.isoformat()}",
                    historical_timestamp=timestamp,
                    confidence=1.0,
                    metadata={"pulse_stop_trigger": True},
                )
                result = send(
                    worker, decision_engine, ledger, command, timestamp, trigger, "pulse_stop"
                )
                if accepted(result):
                    accepted_count += 1
                    active_stop = None
                    last_action = index
                else:
                    rejected_count += 1

        ledger.mark(close_price, position(decision_engine, symbol))
        if index % EVALUATION_EVERY_BARS or index + 1 >= len(frame):
            continue
        history_to_bar = history.loc[:timestamp]
        if len(history_to_bar) < 80:
            continue
        analysis_result, decision, context = await analyze(
            signal_engine, decision_engine, symbol, history_to_bar
        )
        evaluations += 1
        authoritative += int(bool((analysis_result.metadata or {}).get("enhanced_authoritative")))
        if index - last_action < ACTION_COOLDOWN_BARS:
            continue
        qty = _float(position(decision_engine, symbol).get("size"))
        next_timestamp = frame.index[index + 1]
        next_open = float(frame.iloc[index + 1]["open"])
        pending = build_command(
            window,
            symbol,
            next_timestamp,
            next_open,
            analysis_result,
            decision,
            context,
            qty,
        )

    final = position(decision_engine, symbol)
    if _float(final.get("size")) > 0:
        timestamp = frame.index[-1]
        price = float(frame["close"].iloc[-1])
        command = _command(
            symbol=symbol,
            action=AutomationAction.SELL,
            price=price,
            reason="Historical profit replay window liquidation",
            replay_id=f"profit:{window}:{symbol}:window_close",
            historical_timestamp=timestamp,
            confidence=1.0,
            metadata={"historical_window_close": True},
        )
        result = send(
            worker, decision_engine, ledger, command, timestamp, price, "window_liquidation"
        )
        accepted_count += int(accepted(result))
        rejected_count += int(not accepted(result))
        ledger.mark(price, position(decision_engine, symbol))

    summary = ledger.summary()
    summary.update({
        "bars": len(frame),
        "brain_evaluations": evaluations,
        "authoritative_analyses": authoritative,
        "accepted_commands": accepted_count,
        "rejected_commands": rejected_count,
        "reasons": reasons,
        "first_close": round(float(frame["close"].iloc[0]), 4),
        "last_close": round(float(frame["close"].iloc[-1]), 4),
        "buy_and_hold_return_pct": round(
            (float(frame["close"].iloc[-1]) / float(frame["close"].iloc[0]) - 1.0) * 100.0,
            4,
        ),
    })
    return summary


def protocol_profit(history, start, end):
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")
    frame = history.loc[(history.index >= start_ts) & (history.index < end_ts)]
    first = float(frame["close"].iloc[0])
    last = float(frame["close"].iloc[-1])
    gross = 0.75 * STARTING_CAPITAL * (last / first - 1.0)
    turnover = STARTING_CAPITAL + 0.25 * STARTING_CAPITAL + 0.75 * STARTING_CAPITAL * last / first
    costs = turnover * COST_BPS / 10000.0
    return {
        "gross_pnl": round(gross, 4),
        "net_pnl_after_estimated_costs": round(gross - costs, 4),
        "gross_return_pct": round(gross / STARTING_CAPITAL * 100.0, 4),
    }


async def run(args):
    symbols = tuple(item.strip().upper() for item in args.symbols if item.strip())
    histories = {symbol: download_history(symbol) for symbol in symbols}
    worker = PulseWorker(
        Path(__file__).with_name("pulse_historical_worker.py"),
        Path(args.pulse_backend).resolve(),
    )
    windows = {}
    try:
        for window, (start, end) in WINDOWS.items():
            brain_symbols = {}
            protocol_symbols = {}
            for symbol in symbols:
                worker.reset()
                brain_symbols[symbol] = await replay_symbol(
                    worker, histories[symbol], symbol, window, start, end
                )
                protocol_symbols[symbol] = protocol_profit(histories[symbol], start, end)
            capital = STARTING_CAPITAL * len(symbols)
            brain_gross = sum(item["gross_pnl"] for item in brain_symbols.values())
            brain_net = sum(item["net_pnl_after_estimated_costs"] for item in brain_symbols.values())
            protocol_gross = sum(item["gross_pnl"] for item in protocol_symbols.values())
            protocol_net = sum(item["net_pnl_after_estimated_costs"] for item in protocol_symbols.values())
            windows[window] = {
                "start": start,
                "end_exclusive": end,
                "brain_only": {
                    "symbols": brain_symbols,
                    "starting_capital": capital,
                    "gross_pnl": round(brain_gross, 4),
                    "net_pnl_after_estimated_costs": round(brain_net, 4),
                    "gross_return_pct": round(brain_gross / capital * 100.0, 4),
                    "net_return_pct_after_estimated_costs": round(brain_net / capital * 100.0, 4),
                    "closed_trades": sum(item["closed_trades"] for item in brain_symbols.values()),
                    "wins": sum(item["wins"] for item in brain_symbols.values()),
                    "losses": sum(item["losses"] for item in brain_symbols.values()),
                },
                "protocol_probe": {
                    "symbols": protocol_symbols,
                    "starting_capital": capital,
                    "gross_pnl": round(protocol_gross, 4),
                    "net_pnl_after_estimated_costs": round(protocol_net, 4),
                    "gross_return_pct": round(protocol_gross / capital * 100.0, 4),
                    "net_return_pct_after_estimated_costs": round(protocol_net / capital * 100.0, 4),
                },
            }
    finally:
        worker.close()
    return {
        "schema_version": "edge-pulse-historical-profit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assumptions": {
            "data": "Yahoo Finance hourly OHLCV, no future bars in Edge analysis",
            "signal_execution": "market actions execute at the next hourly bar open",
            "stop_execution": "gap below stop fills at bar open; intrabar touch fills at stop",
            "paper_engine": "Pulse real handoff consumer with in-memory paper broker",
            "starting_capital_per_symbol": STARTING_CAPITAL,
            "estimated_cost_bps_per_side": COST_BPS,
            "evaluation_every_bars": EVALUATION_EVERY_BARS,
            "action_cooldown_bars": ACTION_COOLDOWN_BARS,
        },
        "symbols": list(symbols),
        "windows": windows,
    }


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pulse-backend", required=True)
    parser.add_argument("--output", default="historical-profit-report.json")
    parser.add_argument("--symbols", nargs="+", default=list(DEFAULT_SYMBOLS))
    return parser.parse_args()


def main():
    args = parse_args()
    report = asyncio.run(run(args))
    output = Path(args.output)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str) + "\n")
    for name, window in report["windows"].items():
        brain = window["brain_only"]
        protocol = window["protocol_probe"]
        print(
            f"{name}: brain_net={brain['net_pnl_after_estimated_costs']:.2f} "
            f"brain_trades={brain['closed_trades']} protocol_net={protocol['net_pnl_after_estimated_costs']:.2f}"
        )
    print(f"report={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
