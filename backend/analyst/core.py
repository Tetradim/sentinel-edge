"""Sentinel Edge — Main orchestrator (analyst/core.py)

SentinelEdge wraps the existing EvaluationScheduler and adds:
  - OpenTelemetry distributed tracing
  - Bidirectional WebSocket connection to Pulse (optional — Pulse may not be running)
  - MongoDB Change Streams for cross-service commands
  - Pluggable PrometheusExporter
  - Graceful degradation when Pulse or MongoDB are unavailable

Pulse independence
──────────────────
The WebSocket connection is fully optional. When Pulse is not reachable:
  - _connect_pulse_ws() backs off exponentially (up to WS_MAX_BACKOFF seconds)
    and does not spam reconnect attempts once pulse_available is False.
  - WS events that update PositionTracker or DecisionEngine are processed only
    when a connection is live; no queuing or replay is attempted.
  - All signal analysis, ORB detection, risk management, and metric export
    continue normally in standalone mode.
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

import httpx

from analyst.correlation.engine import CorrelationEngine
from analyst.exporters.prometheus import PrometheusExporter
from analyst.observability.otel import setup_otel, get_tracer
from engine import DecisionEngine
from pulse_client import resolve_pulse_api_key

logger = logging.getLogger(__name__)

# Module-level singleton — set by server.py lifespan so alert_handler.py
# can access the live instance without a circular import.
analyst_instance: Optional["SentinelEdge"] = None

# WebSocket reconnect back-off parameters
WS_INITIAL_BACKOFF = 5    # seconds
WS_MAX_BACKOFF     = 120  # seconds — cap at 2 minutes between attempts
WS_BACKOFF_FACTOR  = 2    # double each attempt


class SentinelEdge:
    """Top-level orchestrator for Sentinel Edge.

    Usage in server.py lifespan
    ────────────────────────────
        edge = SentinelEdge(db=db, pulse_url=os.getenv("PULSE_API_URL", "..."))
        edge.set_scheduler(scheduler)
        await edge.start_background_tasks()
        yield
        edge.stop()
    """

    def __init__(
        self,
        db=None,
        pulse_url:    str = "http://pulse:8001",
        window_sec:   int = 120,
        min_symbols:  int = 3,
        cooldown_sec: int = 300,
    ):
        self.db        = db
        self.pulse_url = pulse_url

        setup_otel("sentinel-edge")
        self.tracer = get_tracer("sentinel.edge")

        start_server = os.getenv("ANALYST_START_METRICS_SERVER", "false").lower() == "true"
        self.prom_exporter = PrometheusExporter(start_server=start_server, port=8002)

        # Decision engine with full Pulse feedback loop
        self.decision_engine = DecisionEngine()

        self.correlation = CorrelationEngine(
            db=db,
            pulse_base_url=pulse_url,
            window_sec=window_sec,
            min_symbols=min_symbols,
            cooldown_sec=cooldown_sec,
        )

        self._running    = False
        self._scheduler: Optional[Any] = None
        self._bg_tasks:  list = []

        logger.info("SentinelEdge initialized with full Pulse integration")

    # ── Wiring ───────────────────────────────────────────────────────────────

    def set_scheduler(self, scheduler: Any) -> None:
        """Wire the EvaluationScheduler — share correlation engine, load plugins."""
        self._scheduler = scheduler
        scheduler.correlation = self.correlation
        
        # Wire decision engine for Pulse feedback loop
        scheduler.decisions = self.decision_engine

        try:
            from analyst.signals import discover_plugins
            scheduler.signal_plugins = discover_plugins()
        except Exception as exc:
            logger.warning("Plugin discovery failed: %s", exc)
            scheduler.signal_plugins = []

        logger.info(
            "SentinelEdge wired to EvaluationScheduler (decision_engine + %d plugin(s) loaded)",
            len(scheduler.signal_plugins),
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start_background_tasks(self) -> None:
        """Launch ancillary tasks. Never blocks startup — all failures are logged."""
        self._running = True
        self._bg_tasks = [
            asyncio.create_task(self._connect_pulse_ws(),    name="edge-pulse-ws"),
            asyncio.create_task(self._watch_mongo_commands(), name="edge-mongo-cmd"),
            asyncio.create_task(self._watch_pulse_commands(), name="edge-pulse-cmd"),
        ]
        logger.info("SentinelEdge background tasks started")

    def stop(self) -> None:
        self._running = False
        for task in self._bg_tasks:
            task.cancel()
        self._bg_tasks.clear()
        logger.info("SentinelEdge stopped")

    # ── Pulse WebSocket ───────────────────────────────────────────────────────

    async def _connect_pulse_ws(self) -> None:
        """Connect to Pulse WebSocket with exponential backoff.

        Backoff rules
        ─────────────
        - First attempt fires immediately.
        - Each failure doubles the wait (WS_INITIAL_BACKOFF … WS_MAX_BACKOFF).
        - When pulse_available is False (startup probe failed), the initial
          backoff starts at WS_MAX_BACKOFF so we don't flood logs or the
          network with rapid retry attempts against a known-down service.
        - On successful connection the backoff resets to WS_INITIAL_BACKOFF.
        """
        ws_url = (
            self.pulse_url
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        ) + "/ws/analyst"

        # If Pulse was already known-down at startup, start at the max backoff
        pulse_known_down = (
            self._scheduler is not None
            and hasattr(self._scheduler, "pulse")
            and not self._scheduler.pulse.pulse_available
        )
        backoff = WS_MAX_BACKOFF if pulse_known_down else 0

        try:
            import websockets
        except ImportError:
            logger.warning("websockets not installed — Pulse WS disabled")
            return

        while self._running:
            if backoff > 0:
                logger.debug("Pulse WS: waiting %ds before connect attempt", backoff)
                await asyncio.sleep(backoff)
                if not self._running:
                    return

            try:
                async with websockets.connect(
                    ws_url,
                    open_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    logger.info("✅ Pulse WebSocket connected @ %s", ws_url)
                    backoff = WS_INITIAL_BACKOFF  # reset on success

                    while self._running:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                            await self._handle_pulse_message(json.loads(raw))
                        except asyncio.TimeoutError:
                            continue  # normal — no message in 30 s

            except Exception as exc:
                backoff = min(backoff * WS_BACKOFF_FACTOR if backoff else WS_INITIAL_BACKOFF,
                              WS_MAX_BACKOFF)
                logger.debug(
                    "Pulse WS unavailable (%s) — retry in %ds", exc, backoff
                )

    async def _handle_pulse_message(self, data: dict) -> None:
        """Dispatch an incoming Pulse WebSocket message.

        Supported message types
        ───────────────────────
        ORDER_FILLED      : trade executed — update PositionTracker + correlation
        POSITION_CLOSED   : position closed by Pulse — record trade result
        POSITION_UPDATE   : live PnL update from Pulse — push to PositionTracker
        SIGNAL_UPDATE     : explicit signal from Pulse — feed correlation engine
        OVERRIDE_ACK      : Pulse acknowledged a control command
        """
        msg_type = data.get("type", "")
        symbol   = data.get("symbol", "").upper()

        with self.tracer.start_as_current_span("edge.handle_pulse_message") as span:
            span.set_attribute("msg_type", msg_type)
            span.set_attribute("symbol",   symbol)

            pt = (
                self._scheduler.position_tracker
                if self._scheduler and hasattr(self._scheduler, "position_tracker")
                else None
            )

            # ── Order filled (entry or exit) ──────────────────────────────────
            if msg_type == "ORDER_FILLED" and symbol:
                side = data.get("side", "")
                action = "BUY" if side == "buy" else "SELL"

                if action == "BUY" and pt:
                    from engine import Decision
                    pt.on_decision(
                        symbol,
                        Decision.BUY,
                        entry_price=data.get("fill_price") or data.get("price"),
                    )

                elif action == "SELL" and pt:
                    pnl = float(data.get("realized_pnl", data.get("pnl", 0.0)))
                    if self._scheduler and self._scheduler.decisions:
                        await self._scheduler.decisions.record_trade_result(symbol, pnl)
                        logger.info(
                            "record_trade_result(%s, %.2f) via WS ORDER_FILLED (SELL)",
                            symbol, pnl,
                        )

                await self.correlation.record_signal(symbol, action, confidence=0.8)

            # ── Position closed by Pulse (stop-loss, TP, manual close) ────────
            elif msg_type == "POSITION_CLOSED" and symbol:
                pnl = float(data.get("realized_pnl", data.get("pnl", 0.0)))

                if self._scheduler and self._scheduler.decisions:
                    await self._scheduler.decisions.record_trade_result(symbol, pnl)
                    logger.info(
                        "record_trade_result(%s, %.2f) via WS POSITION_CLOSED",
                        symbol, pnl,
                    )

                if pt:
                    pt.remove(symbol)   # clear stale state

                # Bearish close — feed correlation
                await self.correlation.record_signal(symbol, "SELL", confidence=0.9)

            # ── Live position update (PnL, trailing state) ────────────────────
            elif msg_type == "POSITION_UPDATE" and symbol and pt:
                # Push real-time state into PositionTracker so SELF_SOVEREIGN
                # mode has accurate numbers even without the change stream.
                state = pt.get(symbol)
                pnl     = float(data.get("pnl",     state.get("pnl",     0.0)))
                pnl_pct = float(data.get("pnl_pct", state.get("pnl_pct", 0.0)))
                peak    = max(state.get("peak_pnl_pct", 0.0), pnl_pct)

                updated = dict(state)
                updated.update({
                    "pnl":              pnl,
                    "pnl_pct":          pnl_pct,
                    "peak_pnl_pct":     peak,
                    "drawdown_pct":     max(0.0, peak - pnl_pct),
                    "trailing_enabled": data.get("trailing_enabled", state.get("trailing_enabled")),
                    "trailing_percent": data.get("trailing_percent", state.get("trailing_percent")),
                    "source":           "ws_position_update",
                })
                pt._state[symbol] = updated

            # ── Signal or correlation event ───────────────────────────────────
            elif msg_type == "SIGNAL_UPDATE" and symbol:
                action     = data.get("action", "BUY")
                confidence = float(data.get("confidence", 1.0))
                await self.correlation.record_signal(symbol, action, confidence)

            # ── Override acknowledgement ──────────────────────────────────────
            elif msg_type == "OVERRIDE_ACK":
                logger.info("Pulse acknowledged override: %s", data)

    # ── MongoDB Change Stream (command bus) ───────────────────────────────────

    async def _watch_mongo_commands(self) -> None:
        """Watch `analyst_commands` for cross-service commands.

        This is separate from the `positions` change stream in PositionTracker.
        It handles operational commands (pause, resume, add_ticker, override).
        """
        if self.db is None:
            return

        backoff = 0
        while self._running:
            if backoff > 0:
                await asyncio.sleep(backoff)
            try:
                pipeline = [{"$match": {"operationType": "insert"}}]
                async with self.db.analyst_commands.watch(pipeline) as stream:
                    logger.info("MongoDB change stream watching 'analyst_commands'")
                    backoff = 15  # reset after successful connect
                    async for change in stream:
                        if not self._running:
                            break
                        doc = change.get("fullDocument", {})
                        await self._handle_db_command(doc)
            except Exception as exc:
                backoff = min((backoff or 15) * 2, 120)
                logger.debug(
                    "analyst_commands stream error (%s) — retry in %ds", exc, backoff
                )

    # ── Pulse Commands (Change Stream from shared commands collection) ─────────

    async def _watch_pulse_commands(self) -> None:
        """Watch `commands` collection for Pulse → Edge commands.

        This closes the feedback loop: Pulse reports ORDER_FILLED, POSITION_UPDATE,
        and ACCOUNT_UPDATE via MongoDB Change Streams.
        """
        if self.db is None:
            return

        backoff = 0
        while self._running:
            if backoff > 0:
                await asyncio.sleep(backoff)
            try:
                pipeline = [{"$match": {"operationType": {"$in": ["insert", "update"]}}}]
                async with self.db.commands.watch(pipeline) as stream:
                    logger.info("MongoDB change stream watching 'commands' (Pulse → Edge)")
                    backoff = 15
                    async for change in stream:
                        if not self._running:
                            break

                        doc = change.get("fullDocument") or change.get("updateDescription", {}).get("updatedFields", {})
                        if not doc:
                            continue

                        cmd_type = doc.get("command_type")
                        symbol = (
                            doc.get("symbol")
                            or ("ACCOUNT" if cmd_type == "ACCOUNT_UPDATE" else None)
                            or ("PULSE" if cmd_type == "PULSE_STATUS" else None)
                            or ("BROKER" if cmd_type == "BROKER_STATUS" else None)
                        )

                        if not cmd_type:
                            continue

                        await self._handle_pulse_command(cmd_type, symbol, doc)

            except Exception as exc:
                backoff = min((backoff or 15) * 2, 120)
                logger.debug(
                    "commands stream error (%s) — retry in %ds", exc, backoff
                )

    async def _handle_pulse_command(self, cmd_type: str, symbol: str, doc: dict) -> None:
        """Handle incoming commands from Pulse via MongoDB Change Stream."""
        try:
            from shared.commands import command_from_dict

            # Parse and validate command using shared schema
            cmd = command_from_dict(doc)
            logger.debug(f"Parsed command: {cmd}")

            if cmd_type == "ORDER_FILLED":
                # Get decision engine from scheduler
                if self._scheduler and hasattr(self._scheduler, "decisions"):
                    await self._scheduler.decisions.record_trade_result(
                        symbol=symbol,
                        fill_price=cmd.fill_price,
                        quantity=cmd.quantity,
                        side=cmd.side,
                        realized_pnl=cmd.pnl_realized
                    )
                # Also update position tracker
                pt = (
                    self._scheduler.position_tracker
                    if self._scheduler and hasattr(self._scheduler, "position_tracker")
                    else None
                )
                if pt and cmd.side == "SELL":
                    from engine import Decision
                    pt.on_decision(
                        symbol,
                        Decision.SELL,
                        exit_price=cmd.fill_price,
                    )
                logger.info(f"✅ Edge received ORDER_FILLED from Pulse → {symbol} | fill={cmd.fill_price} qty={cmd.quantity}")

            elif cmd_type == "POSITION_UPDATE":
                # Update position state in position tracker
                pt = (
                    self._scheduler.position_tracker
                    if self._scheduler and hasattr(self._scheduler, "position_tracker")
                    else None
                )
                if pt:
                    state = pt.get(symbol) or {}
                    state.update({
                        "position_size": cmd.position_size,
                        "entry_price": cmd.entry_price,
                        "pnl_pct": cmd.current_pnl_pct,
                        "pnl_dollar": cmd.current_pnl_dollar,
                        "market_value": cmd.market_value,
                        "source": "pulse_position_update",
                    })
                    pt._state[symbol] = state
                logger.info(f"📍 Position sync from Pulse → {symbol} | size={cmd.position_size} pnl%={cmd.current_pnl_pct:.2f}")

            elif cmd_type == "ACCOUNT_UPDATE":
                # Future: update global risk metrics, buying power, etc.
                logger.info(f"📊 Account update from Pulse → equity={cmd.total_equity} buying_power={cmd.buying_power}")

        except Exception as e:
            logger.error(f"Error processing command {cmd_type} for {symbol}: {e}")

    async def _handle_db_command(self, doc: dict) -> None:
        cmd = doc.get("command", "")
        logger.info("DB command received: %s", cmd)

        if not self._scheduler:
            return

        if cmd == "pause":
            self._scheduler.pause()
        elif cmd == "resume":
            self._scheduler.resume()
        elif cmd == "add_ticker":
            symbol = doc.get("symbol", "").upper()
            if symbol:
                self._scheduler.add_ticker(symbol)
        elif cmd == "remove_ticker":
            symbol = doc.get("symbol", "").upper()
            if symbol:
                self._scheduler.remove_ticker(symbol)
        elif cmd == "override":
            await self.send_override(doc.get("action", ""), doc)

    # ── Pulse REST override ───────────────────────────────────────────────────

    @staticmethod
    def _override_trailing_percent(payload: dict) -> float:
        metadata = payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
        for value in (
            payload.get("trailing_percent"),
            payload.get("trail_percent"),
            metadata.get("trailing_percent"),
            os.getenv("ALERT_TRAILING_PERCENT"),
        ):
            if value is None:
                continue
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
        return 1.0

    @staticmethod
    def _override_idempotency_key(symbol: str, handoff_action: str, payload: dict) -> str:
        minute_bucket = int(time.time() // 60)
        fingerprint = (
            payload.get("fingerprint")
            or payload.get("cluster_id")
            or payload.get("alertname")
            or f"{symbol}:{handoff_action}"
        )
        nonce = hashlib.sha1(str(fingerprint).encode("utf-8")).hexdigest()[:10]
        return f"edge:{symbol}:{handoff_action}:market_open:{minute_bucket}:{nonce}"

    def _override_handoff_payload(self, action: str, payload: dict) -> Optional[dict]:
        action_key = str(action or "").strip().lower()
        symbol = str(payload.get("symbol") or "GLOBAL").strip().upper()
        metadata = {"source": "sentinel_edge_override", **payload}
        base = {
            "contract_version": "edge.pulse.handoff.v1",
            "symbol": symbol,
            "confidence": float(payload.get("confidence", 1.0) or 1.0),
            "reason": str(payload.get("reason") or payload.get("summary") or action_key),
            "mode": os.getenv("PULSE_HANDOFF_MODE", "paper"),
            "orb_session": "market_open",
            "source": "sentinel_edge",
            "created_at": time.time(),
            "metadata": metadata,
        }

        if action_key in {"tighten_trailing_global", "tighten_trailing_stops"}:
            handoff_action = "tighten_trailing_stop"
            return {
                **base,
                "symbol": "GLOBAL",
                "action": handoff_action,
                "stop_type": "tighten_trailing",
                "trailing_percent": self._override_trailing_percent(payload),
                "idempotency_key": self._override_idempotency_key("GLOBAL", handoff_action, payload),
            }

        if action_key in {"pause_new_entries", "stop_all", "global_stop"}:
            handoff_action = "stop_all"
            return {
                **base,
                "symbol": "GLOBAL",
                "action": handoff_action,
                "idempotency_key": self._override_idempotency_key("GLOBAL", handoff_action, payload),
            }

        if action_key in {"emergency_exit_all", "emergency_exit"}:
            handoff_action = "emergency_exit"
            return {
                **base,
                "symbol": "GLOBAL",
                "action": handoff_action,
                "idempotency_key": self._override_idempotency_key("GLOBAL", handoff_action, payload),
            }

        if action_key in {"stop_buying", "pause_symbol"} and symbol != "GLOBAL":
            handoff_action = "stop_buying"
            return {
                **base,
                "action": handoff_action,
                "idempotency_key": self._override_idempotency_key(symbol, handoff_action, payload),
            }

        return None

    async def send_override(self, action: str, payload: dict) -> None:
        """Send an override to Pulse through the structured handoff contract."""
        handoff_payload = self._override_handoff_payload(action, payload)
        if not handoff_payload:
            logger.warning("Pulse override action has no handoff mapping: %s", action)
            return

        sched = self._scheduler
        if sched and hasattr(sched, "pulse") and not sched.pulse.pulse_available:
            logger.debug("STANDALONE: override suppressed (%s)", action)
            return

        with self.tracer.start_as_current_span("edge.send_override"):
            try:
                if sched and hasattr(sched, "pulse") and hasattr(sched.pulse, "send_handoff_command"):
                    result = await sched.pulse.send_handoff_command(handoff_payload)
                    if not bool(result.get("sent", False)):
                        logger.warning("Pulse override handoff not accepted: %s", result)
                    return

                edge_api_key = resolve_pulse_api_key()
                if not edge_api_key:
                    logger.warning("Pulse override handoff suppressed: missing Pulse API key")
                    return
                headers = {"X-API-Key": edge_api_key}

                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        f"{self.pulse_url}/api/edge/handoff",
                        json=handoff_payload,
                        headers=headers,
                    )
                    if response.status_code >= 400:
                        logger.error(
                            "Pulse override handoff failed: HTTP %s %s",
                            response.status_code,
                            response.text,
                        )
            except Exception as exc:
                logger.error("Pulse override handoff failed: %s", exc)
