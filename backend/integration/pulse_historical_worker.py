#!/usr/bin/env python3
"""Persistent Pulse-side worker for historical Edge communication replays.

The worker imports the real Pulse handoff schema, execution-intent consumer,
route implementation, and durable idempotency helpers. Lightweight in-memory
dependencies replace MongoDB and brokers so replayed orders remain paper-only.
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def _install_pulse_path() -> Path:
    if len(sys.argv) != 2:
        raise SystemExit("usage: pulse_historical_worker.py <pulse-backend-path>")
    backend = Path(sys.argv[1]).resolve()
    if not backend.exists():
        raise SystemExit(f"Pulse backend not found: {backend}")
    sys.path.insert(0, str(backend))
    return backend


PULSE_BACKEND = _install_pulse_path()

from routes import edge as edge_routes  # noqa: E402
from routes.edge_contracts import PulseHandoffRequest  # noqa: E402
from trading.edge_handoff_contract_patch import _apply_execution_intent  # noqa: E402
from trading.edge_handoff_idempotency_patch import (  # noqa: E402
    _claim_or_replay,
    _store_response,
)


class _WriteResult:
    def __init__(self, *, matched: int = 1, modified: int = 1):
        self.matched_count = matched
        self.modified_count = modified


class _TickerCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def find_one(self, query=None, projection=None, **kwargs):
        query = query or {}
        symbol = query.get("symbol")
        if symbol:
            doc = self.docs.get(str(symbol).upper())
            return deepcopy(doc) if doc else None
        docs = sorted(self.docs.values(), key=lambda item: item.get("sort_order", 0), reverse=True)
        return deepcopy(docs[0]) if docs else None

    async def insert_one(self, document):
        doc = deepcopy(document)
        self.docs[str(doc["symbol"]).upper()] = doc
        return SimpleNamespace(inserted_id=doc["symbol"])

    async def update_one(self, query, update):
        symbol = str((query or {}).get("symbol") or "").upper()
        doc = self.docs.setdefault(symbol, _default_ticker(symbol))
        for key, value in (update.get("$set") or {}).items():
            doc[key] = deepcopy(value)
        for key, value in (update.get("$inc") or {}).items():
            doc[key] = float(doc.get(key, 0) or 0) + float(value)
        for key in (update.get("$unset") or {}):
            doc.pop(key, None)
        self.docs[symbol] = doc
        return _WriteResult()

    async def update_many(self, query, update):
        for symbol in list(self.docs):
            await self.update_one({"symbol": symbol}, update)
        return _WriteResult()


class _LedgerCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def create_index(self, *_args, **_kwargs):
        return "idempotency_key_1"

    async def find_one(self, query, projection=None):
        key = str((query or {}).get("idempotency_key") or "")
        doc = self.docs.get(key)
        return deepcopy(doc) if doc else None

    async def insert_one(self, document):
        key = str(document["idempotency_key"])
        if key in self.docs:
            raise RuntimeError("duplicate idempotency key")
        self.docs[key] = deepcopy(document)
        return SimpleNamespace(inserted_id=key)

    async def update_one(self, query, update):
        key = str((query or {}).get("idempotency_key") or "")
        doc = self.docs.get(key)
        if not doc:
            return _WriteResult(matched=0, modified=0)
        if "owner" in query and doc.get("owner") != query["owner"]:
            return _WriteResult(matched=0, modified=0)
        if "lease_expires_at" in query and doc.get("lease_expires_at") != query["lease_expires_at"]:
            return _WriteResult(matched=0, modified=0)
        response_filter = query.get("response")
        if isinstance(response_filter, dict) and response_filter.get("$exists") is False and "response" in doc:
            return _WriteResult(matched=0, modified=0)
        for key_name, value in (update.get("$set") or {}).items():
            doc[key_name] = deepcopy(value)
        for key_name in (update.get("$unset") or {}):
            doc.pop(key_name, None)
        self.docs[key] = doc
        return _WriteResult()


class _SettingsCollection:
    async def find_one(self, query, projection=None):
        return None


class _ReplayDatabase:
    def __init__(self) -> None:
        self.tickers = _TickerCollection()
        self.edge_handoffs = _LedgerCollection()
        self.settings = _SettingsCollection()


class _ReplayPriceService:
    def __init__(self) -> None:
        self.prices: dict[str, float] = {}

    async def get_price(self, symbol: str) -> float:
        return float(self.prices.get(symbol.upper(), 0.0))


class _ReplayEngine:
    def __init__(self, price_service: _ReplayPriceService) -> None:
        self._positions: dict[str, dict[str, float]] = {}
        self._prices: dict[str, float] = {}
        self._pending_sells: dict[str, Any] = {}
        self.price_service = price_service
        self.simulate_24_7 = True
        self.live_during_market_hours = False
        self.paused = False
        self.running = True

    def get_trading_mode(self) -> str:
        return "paper"

    def is_market_open(self) -> bool:
        return True

    async def execute_buy(self, symbol: str, price: float) -> dict:
        symbol = symbol.upper()
        if float((self._positions.get(symbol) or {}).get("qty", 0) or 0) > 0:
            raise ValueError(f"Open position already exists for {symbol}")
        quantity = round(1000.0 / float(price), 8)
        self._prices[symbol] = float(price)
        self._positions[symbol] = {
            "qty": quantity,
            "avg_entry": float(price),
            "high": float(price),
        }
        return {
            "status": "executed",
            "symbol": symbol,
            "price": float(price),
            "quantity": quantity,
            "total_value": round(quantity * float(price), 2),
            "trading_mode": "paper",
        }

    async def execute_sell(self, symbol: str, price: float | None = None) -> dict:
        symbol = symbol.upper()
        position = self._positions.get(symbol) or {}
        quantity = float(position.get("qty", 0) or 0)
        if quantity <= 0:
            raise ValueError(f"No open position for {symbol}")
        execution_price = float(
            price
            or self._prices.get(symbol)
            or self.price_service.prices.get(symbol)
            or 0.0
        )
        if execution_price <= 0:
            raise ValueError(f"Invalid sell price for {symbol}")
        entry = float(position.get("avg_entry", 0) or 0)
        self._positions[symbol] = {"qty": 0.0, "avg_entry": 0.0, "high": 0.0}
        self._prices[symbol] = execution_price
        return {
            "status": "executed",
            "symbol": symbol,
            "price": execution_price,
            "quantity": quantity,
            "remaining_quantity": 0.0,
            "pnl": round((execution_price - entry) * quantity, 2),
            "trading_mode": "paper",
        }

    async def execute_reduce_position(
        self,
        symbol: str,
        quantity: float,
        price: float | None = None,
        reason: str = "Edge supervisory position reduction",
    ) -> dict:
        symbol = symbol.upper()
        position = self._positions.get(symbol) or {}
        held = float(position.get("qty", 0) or 0)
        requested = float(quantity)
        if held <= 0:
            raise ValueError(f"No open position for {symbol}")
        if not math.isfinite(requested) or requested <= 0 or requested >= held:
            raise ValueError(f"Invalid reduction quantity for {symbol}: {requested}")
        execution_price = float(
            price
            or self._prices.get(symbol)
            or self.price_service.prices.get(symbol)
            or 0.0
        )
        if execution_price <= 0:
            raise ValueError(f"Invalid reduction price for {symbol}")
        remaining = round(held - requested, 8)
        self._positions[symbol] = {
            "qty": remaining,
            "avg_entry": float(position.get("avg_entry", execution_price) or execution_price),
            "high": float(position.get("high", execution_price) or execution_price),
        }
        self._prices[symbol] = execution_price
        return {
            "status": "executed",
            "symbol": symbol,
            "price": execution_price,
            "quantity": round(requested, 8),
            "remaining_quantity": remaining,
            "reason": reason,
            "trading_mode": "paper",
        }


def _default_ticker(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol.upper(),
        "enabled": True,
        "base_power": 1000.0,
        "compound_profits": False,
        "stop_offset": -6.0,
        "stop_percent": True,
        "trailing_enabled": False,
        "broker_ids": [],
        "broker_allocations": {},
        "sort_order": 0,
    }


class _ReplayRuntime:
    def __init__(self) -> None:
        self.db = _ReplayDatabase()
        self.price_service = _ReplayPriceService()
        self.engine = _ReplayEngine(self.price_service)
        self.sequence = 0
        edge_routes.deps.db = self.db
        edge_routes.deps.engine = self.engine
        edge_routes.deps.price_service = self.price_service

    def reset(self) -> None:
        self.__init__()

    def _snapshot(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        return {
            "position": deepcopy(self.engine._positions.get(symbol) or {}),
            "ticker": deepcopy(self.db.tickers.docs.get(symbol) or {}),
            "ledger_entries": len(self.db.edge_handoffs.docs),
        }

    async def process(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        body = PulseHandoffRequest(**payload)
        symbol = body.symbol
        metadata = body.metadata if isinstance(body.metadata, dict) else {}
        price = float(
            metadata.get("price")
            or metadata.get("current_price")
            or metadata.get("last_price")
            or 0.0
        )
        if price > 0:
            self.price_service.prices[symbol] = price
            self.engine._prices[symbol] = price
        self.db.tickers.docs.setdefault(symbol, _default_ticker(symbol))

        owner = f"historical-worker-{self.sequence}"
        state, replay = await _claim_or_replay(edge_routes, body, owner)
        if replay is not None:
            return {
                "ok": True,
                "claim_state": state,
                "response": replay,
                **self._snapshot(symbol),
            }

        response = await _apply_execution_intent(edge_routes, body)
        if response is None:
            response = await edge_routes.post_handoff(body)
        await _store_response(edge_routes, body, owner, response)
        return {
            "ok": True,
            "claim_state": state,
            "response": response,
            **self._snapshot(symbol),
        }


async def _handle(runtime: _ReplayRuntime, message: dict[str, Any]) -> dict[str, Any]:
    operation = str(message.get("op") or "process")
    if operation == "reset":
        runtime.reset()
        return {"ok": True, "reset": True}
    if operation == "stop":
        return {"ok": True, "stop": True}
    if operation != "process":
        return {"ok": False, "error": f"unknown operation: {operation}"}
    payload = message.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "error": "payload must be an object"}
    try:
        return await runtime.process(payload)
    except Exception as exc:
        return {
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "payload": payload,
        }


def main() -> int:
    runtime = _ReplayRuntime()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
            result = asyncio.run(_handle(runtime, message))
        except Exception as exc:
            result = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
        sys.stdout.write(json.dumps(result, sort_keys=True, default=str) + "\n")
        sys.stdout.flush()
        if result.get("stop"):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
