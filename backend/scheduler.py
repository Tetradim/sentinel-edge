"""Async Evaluation Scheduler — the heartbeat of Sentinel Edge.

EvaluationScheduler runs an asyncio loop that evaluates every active ticker
concurrently every EVAL_INTERVAL seconds.

For each ticker it:
  1. Fetches price + volume (yfinance, 30 s shared cache)
  2. Updates ORB tracker (5m / 15m / 30m ranges, ET-anchored)
  3. Updates ATR calculator (14-period true range)
  4. Scores the signal (5-layer ±10 with volume Z-score)
  5. Reads live position state from PositionTracker (change stream or self-sovereign)
  6. Updates self-sovereign PnL from live price (SELF_SOVEREIGN mode only)
  7. Passes ALL risk parameters to DecisionEngine.decide()
  8. Sends the decision to Pulse — silently suppressed in standalone mode
  9. Notifies PositionTracker of the decision (entry/exit bookkeeping)
 10. Updates enriched ticker_state for the REST API
 11. Records the decision in the 50-entry decision feed
 12. Runs BaseSignal plugins
 13. Persists ORB levels to MongoDB
"""
import logging
import asyncio
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from atr import ATRCalculator
from automation import AutomationAction, AutomationController, HandoffCommand
from correlation import CorrelationEngine
from engine import DecisionEngine, Decision
from market_hours import MarketHours
from metrics import (
    analyst_plugin_signals_total,
    edge_engine_paused,
    edge_engine_running,
    edge_eval_duration,
    ticker_active_count,
    ticker_evaluation_total,
)
from orb import MARKET_OPEN_SESSION_ID, ORBTracker, ORBLevel
from position_tracker import PositionTracker
from price_fetcher import PriceFetcher
from providers.ws_manager import WebSocketManager
from pulse_client import PulseClient
from signals import SignalEngine, TrendDirection

logger = logging.getLogger(__name__)


class EvaluationScheduler:
    """Continuously evaluate tickers and make decisions."""

    DEFAULT_TICKERS = ["SPY", "QQQ", "NVDA", "AAPL"]
    EVAL_INTERVAL   = 1   # seconds between full evaluation sweeps

    def __init__(
        self,
        pulse_client:    PulseClient,
        price_fetcher:   PriceFetcher,
        orb_tracker:     ORBTracker,
        atr_calculator:  ATRCalculator,
        signal_engine:   SignalEngine,
        decision_engine: DecisionEngine,
        market_hours:    MarketHours,
        db=None,
    ):
        self.pulse    = pulse_client
        self.prices   = price_fetcher
        self.orb      = orb_tracker
        self.atr      = atr_calculator
        self.signals  = signal_engine
        self.decisions = decision_engine
        self.market_hours = market_hours
        self.db       = db

        self.active_tickers: List[str] = self.DEFAULT_TICKERS.copy()
        self.running = False
        self.paused  = False

        self.prev_prices:    Dict[str, float] = {}
        self.ticker_configs: Dict[str, Dict]  = {}
        self.ticker_state:   Dict[str, Dict]  = {}
        self.recent_decisions: list           = []
        self.signal_plugins:   list           = []
        self.automation = AutomationController()

        # Dual-mode position tracker (change stream primary, self-sovereign fallback)
        self.position_tracker = PositionTracker(
            db=db,
            decision_engine=decision_engine,
        )

        # Daily PnL tracking
        self._daily_pnl_cache = None
        self._daily_pnl_timestamp = None

        self.correlation = CorrelationEngine(
            db=self.db,
            pulse_base_url=os.getenv("PULSE_API_URL", "http://pulse:8001"),
            pulse_overrides_enabled=os.getenv("DEMO_MODE", "false").lower() not in ("true", "1", "yes"),
            window_sec=120,
            min_symbols=3,
            cooldown_sec=300,
        )

        # Phase 3: WebSocket integration
        self.ws_manager = WebSocketManager(
            self.prices,
            self._on_ws_price_update,
            get_active_symbols=lambda: set(self.active_tickers)
        )
        self.prices.set_ws_manager(self.ws_manager)
        logger.info("WebSocketManager wired into scheduler")

        logger.info("Scheduler initialised with %d tickers", len(self.active_tickers))


    async def _get_daily_pnl(self) -> float:
        """Calculate daily realized PnL percentage from Pulse or local state."""
        now = time.time()
        if self._daily_pnl_cache is not None and self._daily_pnl_timestamp:
            if now - self._daily_pnl_timestamp < 60:
                return self._daily_pnl_cache

        daily_pnl = 0.0

        if getattr(self.pulse, "pulse_available", False):
            try:
                account = await self.pulse.get_account_status()
                extracted = self._extract_daily_pnl_pct(account)
                if extracted is not None:
                    daily_pnl = extracted
            except Exception as exc:
                logger.debug("Could not read daily PnL from Pulse account status: %s", exc)

        if daily_pnl == 0.0:
            extracted = self._extract_daily_pnl_pct(
                getattr(self.decisions, "account_state", None)
            )
            if extracted is not None:
                daily_pnl = extracted

        if daily_pnl == 0.0 and hasattr(self.decisions, "get_daily_pnl_pct"):
            try:
                daily_pnl = float(self.decisions.get_daily_pnl_pct())
            except Exception as exc:
                logger.debug("Could not read daily PnL from DecisionEngine: %s", exc)

        self._daily_pnl_cache = daily_pnl
        self._daily_pnl_timestamp = now
        return self._daily_pnl_cache

    def _extract_daily_pnl_pct(self, account: Optional[Dict[str, Any]]) -> Optional[float]:
        """Extract daily PnL percentage from account-style payloads."""
        if not isinstance(account, dict):
            return None

        for key in ("daily_pnl_pct", "daily_pnl_percent", "day_pnl_pct", "pnl_pct"):
            value = self._float_or_none(account.get(key))
            if value is not None:
                return value

        pnl = self._float_or_none(
            account.get("daily_pnl")
            or account.get("day_pnl")
            or account.get("realized_pnl_today")
            or account.get("todays_pnl")
        )
        if pnl is None:
            return None

        base = self._float_or_none(
            account.get("start_of_day_equity")
            or account.get("starting_equity")
            or account.get("previous_close_equity")
            or account.get("initial_equity")
            or account.get("equity")
            or account.get("total_equity")
        )
        if base is None or base <= 0:
            return None

        return (pnl / base) * 100.0

    @staticmethod
    def _float_or_none(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    # ─────────────────────────────────────────────────────────────────────────
    # Evaluation
    # ─────────────────────────────────────────────────────────────────────────

    async def evaluate_ticker(
        self,
        symbol: str,
        is_ws_update: bool = False,
        current_price: Optional[float] = None,
        current_volume: Optional[float] = None,
    ):
        """Full evaluation pipeline for a single ticker (see module docstring).

        Args:
            symbol: Ticker symbol to evaluate
            is_ws_update: If True, this is a real-time WS update (skip normal price fetch)
            current_price: Optional pre-fetched price (for WS updates)
            current_volume: Optional pre-fetched volume (for WS updates)
        """
        start_time = time.time()

        # ── 0. Production Safeguards ─────────────────────────────────────────
        import os
        if os.getenv("GLOBAL_KILL_SWITCH", "false").lower() == "true":
            logger.warning("🚨 GLOBAL KILL SWITCH ACTIVATED - No decisions allowed")
            return

        # Max daily loss protection (check every evaluation)
        daily_loss = await self._get_daily_pnl()
        if daily_loss < -5.0:  # -5% daily loss limit
            logger.critical(f"🚨 DAILY LOSS LIMIT BREACHED (-{daily_loss}%) - Pausing trading")
            return

        try:
            # ── 1. Price + volume ────────────────────────────────────────────
            # Use pre-fetched price from WS update if available
            ticker_cfg = self.ticker_configs.get(symbol, {})
            provider_order = ticker_cfg.get("price_providers")

            if is_ws_update and current_price is not None:
                price = current_price
                volume = current_volume or 0
            else:
                result = await self.prices.get_price_with_volume(
                    symbol,
                    provider_order=provider_order,
                )
                if not result:
                    logger.warning("Could not fetch data for %s", symbol)
                    return
                price, volume = result
            now = datetime.now()

            # ── 2. ORB update + breakout detection ───────────────────────────
            orb_levels = self.orb.update(symbol, price, now)
            for bo in self.orb.check_breakout(symbol, price):
                logger.warning(
                    "🚨 BREAKOUT: %s %s on %dm",
                    symbol, bo["direction"].upper(), bo["timeframe"],
                )

            # ── 3. ATR ───────────────────────────────────────────────────────
            ohlcv_data = await self.prices.get_ohlcv(
                symbol,
                provider_order=provider_order,
            )
            atr = 0.0
            if ohlcv_data is not None and not ohlcv_data.empty:
                latest = ohlcv_data.iloc[-1]
                atr = self.atr.update(
                    symbol,
                    float(latest["High"]),
                    float(latest["Low"]),
                    float(latest["Close"]),
                )

            # ── 4. Price momentum ────────────────────────────────────────────
            price_change_pct = 0.0
            if symbol in self.prev_prices and self.prev_prices[symbol] > 0:
                price_change_pct = (
                    (price - self.prev_prices[symbol]) / self.prev_prices[symbol]
                ) * 100
            self.prev_prices[symbol] = price

            # ── 5. Volume & signal scoring ───────────────────────────────────
            self.signals.update_avg_volume(symbol, volume)
            volume_ratio  = self.signals.get_volume_ratio(symbol, volume)
            volume_zscore = self.signals.compute_volume_zscore(symbol, volume)

            orb_high: Optional[float] = None
            orb_low:  Optional[float] = None
            if 15 in orb_levels and orb_levels[15].is_valid:
                orb_high = orb_levels[15].high
                orb_low  = orb_levels[15].low
            orb_decision_context = self.orb.get_decision_context(symbol, now=now)
            orb_metadata = {
                "orb_decision_context": orb_decision_context,
            }

            trend, signal_strength = self.signals.evaluate_signal(
                symbol=symbol,
                price=price,
                orb_high=orb_high,
                orb_low=orb_low,
                volume_ratio=volume_ratio,
                atr=atr,
                price_change_pct=price_change_pct,
                volume_zscore=volume_zscore,
            )

            # ── 5b. Pattern detection via SignalEngineEnhanced ─────────────────
            pattern_impact = 0.0
            pattern_confidence = 1.0  # Default: full confidence if no analysis
            try:
                # Get price data for pattern analysis
                if ohlcv_data is not None and not ohlcv_data.empty:
                    from signals_enhanced import get_signal_engine
                    
                    # Get or create enhanced signal engine
                    pattern_engine = get_signal_engine(
                        enable_talib=True,
                        multi_timeframe=False
                    )
                    
                    # Analyze for patterns
                    analysis = await pattern_engine.analyze(
                        symbol, ohlcv_data, timeframe="15m"
                    )
                    
                    # Extract confidence for decision gate
                    pattern_confidence = analysis.confidence.overall
                    
                    # Convert detected patterns to observations and add to DecisionEngine
                    if analysis.patterns:
                        from shared.observations import create_pattern_observation
                        
                        for pattern in analysis.patterns:
                            if pattern.detected and pattern.confidence > 0.5:
                                obs = create_pattern_observation(
                                    symbol=symbol,
                                    pattern_results=[pattern],
                                    source="EDGE_PATTERNS"
                                )
                                self.decisions.add_observation(obs)
                                
                                # Accumulate pattern impact
                                if pattern.direction.name == "BULLISH":
                                    pattern_impact += pattern.confidence * pattern.strength / 100
                                elif pattern.direction.name == "BEARISH":
                                    pattern_impact -= pattern.confidence * pattern.strength / 100
                                
                                logger.debug(
                                    f"🔍 {symbol}: Pattern {pattern.pattern_type.value} "
                                    f"detected ({pattern.confidence:.2f} conf, {pattern.direction.name})"
                                )
                        
                        # Apply pattern impact to signal strength
                        if pattern_impact != 0.0:
                            signal_strength = signal_strength + (pattern_impact * 1.0)
                            logger.info(
                                f"📊 {symbol}: Pattern impact {pattern_impact:+.2f} applied "
                                f"to signal ({signal_strength - pattern_impact:.2f} -> {signal_strength:.2f})"
                            )
                            
            except Exception as e:
                logger.debug(f"Pattern detection failed for {symbol}: {e}")

            # ── 6. Position state (DecisionEngine: synced from Pulse via Change Stream)
            # Get real position state from DecisionEngine which receives updates
            # from Pulse via MongoDB Change Stream (ORDER_FILLED, POSITION_UPDATE)
            position = self.decisions.get_position(symbol)
            has_position = position is not None
            pnl_pct = position.get("current_pnl_pct", 0.0) if position else 0.0
            pnl_dollar = position.get("current_pnl_dollar", 0.0) if position else 0.0
            
            # Also update local position tracker for other components
            self.position_tracker.update_price(symbol, price)
            pos = self.position_tracker.get(symbol)

            # ── 7. Decision — all risk parameters populated ──────────────────
            risk_cfg = ticker_cfg.get("risk", {})
            
            # Use real position data from DecisionEngine (synced from Pulse)
            base_signal = signal_strength
            
            # Apply observation-based adjustments (from Pulse feedback, patterns, etc.)
            if hasattr(self.decisions, 'apply_observation_adjustment'):
                signal_strength = self.decisions.apply_observation_adjustment(
                    signal_strength, symbol
                )
            
            decision = self.decisions.decide(
                symbol=symbol,
                trend=trend,
                signal_strength=signal_strength,
                confidence=pattern_confidence,
                pnl=pnl_dollar,
                pnl_pct=pnl_pct,  # Real PnL from Pulse
                current_drawdown=pos["drawdown_pct"],
                has_position=has_position,  # Real position state from Pulse
                trailing_enabled=pos["trailing_enabled"],
                max_consecutive_losses=risk_cfg.get("max_consecutive_losses"),
                max_drawdown_pct=risk_cfg.get("max_drawdown_pct"),
                trailing_stop_profit_threshold=risk_cfg.get("trailing_stop_profit_threshold"),
            )
            
            # Log if observation adjustment was applied
            if base_signal != signal_strength:
                logger.info(f"📊 {symbol}: Observation adjustment applied ({base_signal:.2f} -> {signal_strength:.2f})")

            # ── 8. Send decision to Pulse when autonomous handoff allows it ───
            confidence = min(abs(signal_strength) / 10.0, 1.0)
            handoff_sent = False
            if decision == Decision.BUY:
                handoff_sent = await self._handoff_to_pulse(
                    symbol=symbol,
                    action=AutomationAction.BUY,
                    confidence=confidence,
                    reason="Bullish ORB/signal confluence",
                    orb_session=orb_decision_context["signal_session"],
                    metadata={**orb_metadata, "signal_strength": signal_strength, "trend": trend.name.lower()},
                )

            elif decision == Decision.STOP_BUYING:
                handoff_sent = await self._handoff_to_pulse(
                    symbol=symbol,
                    action=AutomationAction.STOP_BUYING,
                    confidence=confidence,
                    reason="Bearish ORB/signal risk",
                    orb_session=orb_decision_context["signal_session"],
                    metadata={**orb_metadata, "signal_strength": signal_strength, "trend": trend.name.lower()},
                )

            elif decision == Decision.ENABLE_TRAILING_STOP:
                trailing_pct = (
                    min(2.0, max(0.5, (atr / price) * 100 * 2))
                    if price > 0 else 1.5
                )
                handoff_sent = await self._handoff_to_pulse(
                    symbol=symbol,
                    action=AutomationAction.TRAILING_STOP,
                    confidence=confidence,
                    reason="Position in profit; enable trailing stop",
                    orb_session=orb_decision_context["signal_session"],
                    stop_type="trailing",
                    trailing_percent=trailing_pct,
                    metadata={**orb_metadata, "atr": atr, "price": price, "pnl_pct": pnl_pct},
                )

            elif decision == Decision.TIGHTEN_TRAILING_STOP:
                handoff_sent = await self._handoff_to_pulse(
                    symbol=symbol,
                    action=AutomationAction.TIGHTEN_TRAILING_STOP,
                    confidence=confidence,
                    reason="Strong move while trailing; tighten trailing stop",
                    orb_session=orb_decision_context["signal_session"],
                    stop_type="trailing",
                    trailing_percent=0.5,
                    metadata={**orb_metadata, "signal_strength": signal_strength, "pnl_pct": pnl_pct},
                )

            elif decision == Decision.TIGHTEN_STOP:
                handoff_sent = await self._handoff_to_pulse(
                    symbol=symbol,
                    action=AutomationAction.TIGHTEN_STOP,
                    confidence=confidence,
                    reason="Bearish reversal detected; tighten stop",
                    orb_session=orb_decision_context["signal_session"],
                    stop_type="regular",
                    metadata={**orb_metadata, "signal_strength": signal_strength, "trend": trend.name.lower()},
                )

            elif decision == Decision.EMERGENCY_EXIT:
                handoff_sent = await self._handoff_to_pulse(
                    symbol=symbol,
                    action=AutomationAction.EMERGENCY_EXIT,
                    confidence=max(confidence, 0.95),
                    reason="Emergency risk threshold reached",
                    orb_session=orb_decision_context["signal_session"],
                    metadata={**orb_metadata, "drawdown_pct": pos["drawdown_pct"], "pnl_pct": pnl_pct},
                )

            # ── 9a. Notify PositionTracker of decision taken ─────────────────
            # Only mutate local position state after Pulse accepts the handoff.
            if handoff_sent:
                self.position_tracker.on_decision(symbol, decision, entry_price=price)

            # ── 9. Correlation tracking ──────────────────────────────────────
            if decision == Decision.BUY:
                await self.correlation.record_signal(symbol, "BUY", confidence)
            elif decision in (Decision.STOP_BUYING, Decision.EMERGENCY_EXIT):
                await self.correlation.record_signal(symbol, "SELL", confidence)

            # ── 10. Decision feed (skip HOLD) ─────────────────────────────────
            if decision != Decision.HOLD:
                self.recent_decisions.insert(0, {
                    "symbol":          symbol,
                    "decision":        decision.value,
                    "signal_strength": round(signal_strength, 2),
                    "trend":           trend.name.lower(),
                    "confidence":      round(confidence, 3),
                    "price":           round(price, 4),
                    "pnl_pct":         round(pos["pnl_pct"], 3),
                    "has_position":    pos["has_position"],
                    "orb_decision_context": orb_decision_context,
                    "timestamp":       now.isoformat(),
                })
                self.recent_decisions = self.recent_decisions[:50]

            # ── 11. Enriched ticker state (GET /api/tickers) ──────────────────
            orb_data: Dict[str, Dict] = {}
            for tf, level in orb_levels.items():
                safe_low = level.low if level.low != float("inf") else 0.0
                orb_data[f"{tf}m"] = {
                    "high":        round(level.high, 4),
                    "low":         round(safe_low, 4),
                    "locked":      level.locked,
                    "range_width": round(level.range_width, 4),
                    "is_valid":    level.is_valid,
                }
            orb_session_status = self.orb.get_session_status(symbol, now=now)

            self.ticker_state[symbol] = {
                "symbol":           symbol,
                "enabled":          True,
                "current_price":    round(price, 4),
                "orb_levels":       orb_data,
                "orb_session_status": orb_session_status,
                "orb_decision_context": orb_decision_context,
                "signal_strength":  round(signal_strength, 2),
                "trend":            trend.name.lower(),
                "atr":              round(atr, 4),
                "volume_ratio":     round(volume_ratio, 4),
                "volume_zscore":    round(volume_zscore, 3),
                "last_decision":    decision.value,
                "confidence":       round(confidence, 3),
                # Position context visible in the dashboard
                "has_position":     pos["has_position"],
                "pnl":              round(pos["pnl"], 2),
                "pnl_pct":          round(pos["pnl_pct"], 3),
                "trailing_enabled": pos["trailing_enabled"],
                "drawdown_pct":     round(pos["drawdown_pct"], 3),
                "last_updated":     now.isoformat(),
            }

            # ── 12. BaseSignal plugins ─────────────────────────────────────────
            if self.signal_plugins and ohlcv_data is not None and not ohlcv_data.empty:
                market_data = {
                    "ohlcv":           ohlcv_data,
                    "price":           price,
                    "volume":          volume,
                    "atr":             atr,
                    "volume_ratio":    volume_ratio,
                    "volume_zscore":   volume_zscore,
                    "signal_strength": signal_strength,
                    "trend":           trend.name.lower(),
                    "orb_high":        orb_high,
                    "orb_low":         orb_low,
                }
                for plugin in self.signal_plugins:
                    try:
                        plugin_signal = await plugin.generate(symbol, market_data)
                        if plugin_signal and plugin_signal.action in ("BUY", "SELL"):
                            await self.correlation.record_signal(
                                symbol,
                                plugin_signal.action,
                                plugin_signal.confidence,
                            )
                            analyst_plugin_signals_total.labels(
                                plugin=plugin.name,
                                symbol=symbol,
                                action=plugin_signal.action,
                            ).inc()
                            if plugin_signal.metadata.get("plugin") == "puzzle_key_strategy":
                                plugin_action = (
                                    AutomationAction.BUY
                                    if plugin_signal.action == "BUY"
                                    else AutomationAction.STOP_BUYING
                                )
                                plugin_handoff_sent = await self._handoff_to_pulse(
                                    symbol=symbol,
                                    action=plugin_action,
                                    confidence=plugin_signal.confidence,
                                    reason="Puzzle Key Strategy plugin signal",
                                    orb_session="puzzle_key",
                                    metadata={
                                        **plugin_signal.metadata,
                                        "price": plugin_signal.price,
                                        "atr": plugin_signal.atr,
                                        "reason": plugin_signal.reason,
                                    },
                                )
                                if plugin_handoff_sent:
                                    logger.info(
                                        "Puzzle Key Strategy handoff sent for %s action=%s conf=%.2f",
                                        symbol,
                                        plugin_action.value,
                                        plugin_signal.confidence,
                                    )
                            logger.info(
                                "🔌 Plugin [%s] → %s %s conf=%.2f: %s",
                                plugin.name, plugin_signal.action, symbol,
                                plugin_signal.confidence, plugin_signal.reason,
                            )
                    except Exception as pe:
                        logger.debug("Plugin %s error for %s: %s", plugin.name, symbol, pe)

            # ── 13. MongoDB ORB persistence ────────────────────────────────────
            await self._persist_orb(symbol, orb_levels, now)

            ticker_evaluation_total.labels(symbol=symbol).inc()

        except Exception as e:
            logger.error("Error evaluating %s: %s", symbol, e, exc_info=True)

        finally:
            edge_eval_duration.labels(symbol=symbol).observe(time.time() - start_time)

    async def _on_ws_price_update(self, symbol: str, price: float, volume: float = 0):
        """Called by WebSocket when live price arrives - trigger immediate evaluation"""
        logger.info(f"📡 WS Live Update → {symbol} @ ${price:.2f} (vol={volume})")

        # Skip if symbol's market is closed
        if not self.market_hours.is_symbol_tradeable(symbol):
            market = self.market_hours.get_market_for_symbol(symbol)
            logger.debug(f"WS update ignored for {symbol} - market ({market}) closed")
            return

        # Trigger fresh evaluation with real data
        await self.evaluate_ticker(
            symbol=symbol,
            is_ws_update=True,
            current_price=price,
            current_volume=volume
        )

    async def _handoff_to_pulse(
        self,
        symbol: str,
        action: AutomationAction,
        confidence: float,
        reason: str,
        orb_session: str = "market_open",
        stop_type: Optional[str] = None,
        trailing_percent: Optional[float] = None,
        dca: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """Gate and send an autonomous Edge -> Pulse handoff command."""
        command = HandoffCommand(
            symbol=symbol,
            action=action,
            confidence=confidence,
            reason=reason,
            mode=self.automation.settings.mode,
            orb_session=orb_session,
            stop_type=stop_type,
            trailing_percent=trailing_percent,
            dca=dca,
            metadata=metadata or {},
        )
        market = self.market_hours.get_market_for_symbol(command.symbol)
        market_status = self.market_hours.market_status(market)
        if not market_status.get("open", False):
            market_reason = market_status.get("reason", "closed")
            gate_reason = f"market_closed:{market_reason}"
            command.metadata.update({"market_status": market_status})
            self.automation.record_suppressed(command, gate_reason)
            logger.debug(
                "Pulse handoff suppressed for %s %s: %s",
                symbol,
                action.value,
                gate_reason,
            )
            return False

        allowed, gate_reason = self.automation.plan(command)
        if not allowed:
            logger.debug(
                "Pulse handoff suppressed for %s %s: %s",
                symbol,
                action.value,
                gate_reason,
            )
            return False

        sent = await self.pulse.send_handoff_command(command.payload())
        self.automation.record_sent(command, sent)
        if sent:
            logger.info("Pulse handoff sent: %s %s conf=%.2f", symbol, action.value, confidence)
        return sent

    async def evaluate_all(self):
        """Evaluate all active tickers concurrently."""
        if self.paused:
            return
        self.market_hours.update_metrics()
        ticker_active_count.set(len(self.active_tickers))
        
        # Skip tickers that have active WebSocket subscriptions
        # (WS will trigger evaluation instead of polling)
        skipped = getattr(self.ws_manager, 'subscribed_symbols', set())
        
        tasks = []
        for symbol in self.active_tickers:
            if skipped and symbol in skipped:
                continue  # WS will trigger evaluation instead
            tasks.append(self.evaluate_ticker(symbol))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def run(self):
        """Main evaluation loop — runs until stop() is called."""
        self.running = True
        edge_engine_running.set(1)
        logger.info(
            "🚀 Sentinel Edge scheduler started (interval: %ds, position tracking: %s)",
            self.EVAL_INTERVAL, self.position_tracker.mode_name,
        )

        # Start position tracker background task (change stream probe + auto-upgrade)
        self.position_tracker.start()

        # Start WebSocket for live price streaming
        await self.ws_manager.start()

        await self._load_orb_from_db()

        try:
            while self.running:
                await self.evaluate_all()
                await asyncio.sleep(self.EVAL_INTERVAL)
        except Exception as e:
            logger.error("Scheduler fatal error: %s", e, exc_info=True)
        finally:
            self.running = False
            edge_engine_running.set(0)
            logger.info("⏸️ Sentinel Edge scheduler stopped")

    # ─────────────────────────────────────────────────────────────────────────
    # MongoDB helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def _persist_orb(self, symbol: str, orb_levels: Dict, now: datetime):
        """Upsert ORB levels to MongoDB (one document per symbol per trading day)."""
        if self.db is None:
            return
        try:
            orb_decision_context = self.orb.get_decision_context(symbol, now=now)
            levels_doc: Dict[str, Dict] = {}
            for tf, level in orb_levels.items():
                if level.is_valid:
                    safe_low = level.low if level.low != float("inf") else 0.0
                    levels_doc[str(tf)] = {
                        "high":   level.high,
                        "low":    safe_low,
                        "locked": level.locked,
                        "is_valid": True,
                        "session_id": MARKET_OPEN_SESSION_ID,
                        "start_time": level.start_time,
                        "lock_time": level.lock_time,
                    }
            sessions_doc: Dict[str, Dict] = {}
            for session_id, session_levels in self.orb.get_session_levels(symbol).items():
                session_doc: Dict[str, Dict] = {}
                for tf, level in session_levels.items():
                    if level.is_valid:
                        safe_low = level.low if level.low != float("inf") else 0.0
                        session_doc[str(tf)] = {
                            "high": level.high,
                            "low": safe_low,
                            "locked": level.locked,
                            "is_valid": True,
                            "session_id": session_id,
                            "start_time": level.start_time,
                            "lock_time": level.lock_time,
                        }
                if session_doc:
                    sessions_doc[session_id] = session_doc

            if levels_doc or sessions_doc:
                await self.db.orb_levels.update_one(
                    {"symbol": symbol, "date": now.strftime("%Y-%m-%d")},
                    {"$set": {
                        "symbol":     symbol,
                        "date":       now.strftime("%Y-%m-%d"),
                        "levels":     levels_doc,
                        "sessions": sessions_doc,
                        "decision_context": orb_decision_context,
                        "updated_at": now,
                    }},
                    upsert=True,
                )
        except Exception as e:
            logger.error("Failed to persist ORB for %s: %s", symbol, e)

    async def _load_orb_from_db(self):
        """Restore today's ORB levels from MongoDB on startup."""
        if self.db is None:
            return
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            count = 0
            async for doc in self.db.orb_levels.find({"date": today}, {"_id": 0}):
                symbol = doc["symbol"]
                if symbol not in self.orb.orb_sessions:
                    self.orb._init_symbol(symbol, datetime.now().date())

                sessions = doc.get("sessions") or {}
                for session_id, session_levels in sessions.items():
                    session_bucket = self.orb.orb_sessions[symbol].setdefault(session_id, {})
                    for tf_str, level_data in session_levels.items():
                        tf = int(tf_str)
                        if level_data.get("is_valid"):
                            session_bucket[tf] = ORBLevel(
                                high=level_data["high"],
                                low=level_data["low"],
                                locked=level_data["locked"],
                                start_time=level_data.get("start_time") or datetime.now(),
                                lock_time=level_data.get("lock_time"),
                                date=doc.get("date", today),
                                session_id=level_data.get("session_id", session_id),
                            )
                            count += 1

                for tf_str, level_data in doc.get("levels", {}).items():
                    tf = int(tf_str)
                    if tf in [5, 15, 30] and level_data.get("is_valid"):
                        market_open_levels = self.orb.orb_sessions[symbol].setdefault(
                            MARKET_OPEN_SESSION_ID,
                            {},
                        )
                        market_open_levels[tf] = ORBLevel(
                            high=level_data["high"],
                            low=level_data["low"],
                            locked=level_data["locked"],
                            start_time=level_data.get("start_time") or datetime.now(),
                            lock_time=level_data.get("lock_time"),
                            date=doc.get("date", today),
                            session_id=level_data.get("session_id", MARKET_OPEN_SESSION_ID),
                        )
                        count += 1
                self.orb.orb_levels[symbol] = self.orb.orb_sessions[symbol].get(
                    MARKET_OPEN_SESSION_ID,
                    {},
                )
            if count:
                logger.info("✅ Restored %d ORB levels from MongoDB", count)
        except Exception as e:
            logger.error("Failed to load ORB from DB: %s", e)

    # ─────────────────────────────────────────────────────────────────────────
    # Runtime control
    # ─────────────────────────────────────────────────────────────────────────

    def pause(self):
        self.paused = True
        edge_engine_paused.set(1)
        logger.info("⏸️ Scheduler paused")

    def resume(self):
        self.paused = False
        edge_engine_paused.set(0)
        logger.info("▶️ Scheduler resumed")

    def stop(self):
        self.running = False
        self.position_tracker.stop()
        # Stop WebSocket connection
        if hasattr(self, 'ws_manager'):
            self.ws_manager._running = False
            logger.info("WebSocket disabled")
        logger.info("⏹️ Stopping scheduler...")

    def add_ticker(self, symbol: str):
        if symbol not in self.active_tickers:
            self.active_tickers.append(symbol)
            # Subscribe to new symbol via WebSocket if connected
            if hasattr(self, 'ws_manager') and self.ws_manager.subscribed_symbols is not None:
                asyncio.create_task(
                    self.ws_manager.add_symbols({symbol})
                )
            logger.info("➕ Added %s to watch list", symbol)

    def remove_ticker(self, symbol: str):
        if symbol in self.active_tickers:
            self.active_tickers.remove(symbol)
            self.ticker_state.pop(symbol, None)
            self.position_tracker.remove(symbol)
            logger.info("➖ Removed %s from watch list", symbol)
