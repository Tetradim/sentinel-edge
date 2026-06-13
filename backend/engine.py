"""DecisionEngine - Core risk & decision logic with full Pulse feedback"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from collections import defaultdict, deque
from enum import Enum

from signals import TrendDirection
from metrics import (
    edge_decision_total, 
    edge_consecutive_losses, 
    edge_win_rate,
    edge_confidence_score,
    edge_signal_quality
)

from shared.commands import (
    OrderFilledCommand,
    PositionUpdateCommand,
    SignalUpdateCommand
)
from shared.observations import (
    BaseObservation,
    PatternObservation,
    ExecutionObservation,
    ObservationScorer,
    observation_scorer,
    desync_monitor
)


logger = logging.getLogger(__name__)


class Decision(Enum):
    BUY = "buy"
    SELL = "sell"
    STOP_BUYING = "stop_buying"
    ENABLE_TRAILING_STOP = "enable_trailing_stop"
    TIGHTEN_TRAILING_STOP = "tighten_trailing_stop"   # auto-tighten on strong move
    TIGHTEN_STOP = "tighten_stop"
    HOLD = "hold"
    EMERGENCY_EXIT = "emergency_exit"


class DecisionEngine:
    """Make trading decisions based on signals and risk management.
    
    Enhanced with full Pulse feedback loop:
    - record_trade_result() - called when Pulse reports ORDER_FILLED
    - update_position_state() - called when Pulse reports POSITION_UPDATE
    - update_account_state() - called when Pulse reports ACCOUNT_UPDATE
    
    Observation Integration:
    - add_observation() - Store observations from Pulse/Edge/external
    - get_observation_impact() - Calculate how observations affect scoring
    - check_timeframe_desync() - Detect and handle desync between systems
    """

    # Risk thresholds
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_DRAWDOWN_PCT = 10.0
    TRAILING_STOP_PROFIT_THRESHOLD = 2.0  # Enable trailing after 2% profit
    
    # Observation settings
    MAX_OBSERVATIONS_PER_SYMBOL = 50
    OBSERVATION_DECAY_MINUTES = 5
    
    def __init__(self):
        # Per-symbol state (original)
        self.position_pnl: Dict[str, float] = {}
        self.consecutive_losses: Dict[str, int] = {}
        self.total_trades: Dict[str, int] = {}
        self.winning_trades: Dict[str, int] = {}
        self.peak_equity: Dict[str, float] = {}
        
        # Enhanced: Full position tracking
        self.positions: Dict[str, dict] = {}           # symbol -> position info
        self.trade_history: Dict[str, List[dict]] = defaultdict(list)
        self.win_rate: Dict[str, float] = defaultdict(float)
        self.daily_pnl: Dict[str, float] = defaultdict(float)
        self.account_state: Dict[str, Any] = {}
        
        # Global kill switch
        self.global_kill_switch = False
        
        # Observation tracking for scoring
        self.observations: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.MAX_OBSERVATIONS_PER_SYMBOL)
        )
        self.observation_scorer = observation_scorer
        self.desync_monitor = desync_monitor
        self.max_daily_loss_pct = -5.0
        
        logger.info("DecisionEngine initialized with Pulse feedback support")


    # ====================== INCOMING FROM PULSE ======================


    async def record_trade_result(
        self,
        symbol: str,
        fill_price: float,
        quantity: float = 0.0,
        side: str = "SELL",
        realized_pnl: Optional[float] = None,
        order_id: Optional[str] = None,
    ):
        """Called when Pulse reports an order was filled.
        
        This is the async version that accepts individual parameters,
        matching how it's called from the change stream handler.
        """
        symbol = symbol.upper()
        if realized_pnl is None and quantity == 0.0 and side == "SELL":
            self.record_trade_result_legacy(symbol, profit=fill_price)
            return
        
        self.trade_history[symbol].append({
            "timestamp": datetime.utcnow(),
            "order_id": order_id or "",
            "side": side,
            "price": fill_price,
            "quantity": quantity,
            "pnl_realized": realized_pnl or 0.0,
            "fees": 0.0
        })

        # Update position
        if side == "BUY":
            self.positions[symbol] = {
                "size": quantity,
                "entry_price": fill_price,
                "entry_time": datetime.utcnow()
            }
        else:  # SELL
            if symbol in self.positions:
                del self.positions[symbol]

        # Track consecutive losses (also update original tracking)
        if realized_pnl is not None:
            self.daily_pnl[symbol] += realized_pnl
            if realized_pnl < 0:
                self.consecutive_losses[symbol] += 1
            else:
                self.consecutive_losses[symbol] = 0

        logger.info(f"Trade recorded: {side} {quantity} {symbol} @ {fill_price} | PnL: {realized_pnl}")


    async def update_position_state_simple(
        self,
        symbol: str,
        position_size: float,
        pnl_pct: float = 0.0,
        pnl_dollar: float = 0.0
    ):
        """Real-time position & PnL sync from Pulse.
        
        Async version accepting individual parameters.
        """
        symbol = symbol.upper()
        
        if position_size == 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = {
                "size": position_size,
                "entry_price": None,
                "current_pnl_pct": pnl_pct,
                "current_pnl_dollar": pnl_dollar,
                "last_updated": datetime.utcnow()
            }
        
        # Also update original position_pnl
        self.position_pnl[symbol] = pnl_dollar

        logger.debug(f"Position updated from Pulse: {symbol} | size={position_size} | PnL={pnl_pct:.2f}%")


    # ====================== OUTGOING TO PULSE ======================


    def create_signal_command(self, symbol: str, signal_score: float, action: str, reason: str = "") -> SignalUpdateCommand:
        """Create a SignalUpdateCommand to send to Pulse."""
        return SignalUpdateCommand(
            symbol=symbol,
            signal_score=signal_score,
            action=action,
            confidence=min(1.0, abs(signal_score) / 10),
            reason=reason
        )


    # ====================== CORE DECISION LOGIC ======================


    def decide(
        self,
        symbol: str,
        trend: TrendDirection,
        signal_strength: float,
        confidence: float = 1.0,  # 0.0 to 1.0 - signal quality gate
        pnl: float = 0.0,
        pnl_pct: float = 0.0,
        current_drawdown: float = 0.0,
        has_position: bool = False,
        trailing_enabled: bool = False,
        max_consecutive_losses: Optional[int] = None,
        max_drawdown_pct: Optional[float] = None,
        trailing_stop_profit_threshold: Optional[float] = None,
    ) -> Decision:
        """Main decision method - now fully aware of real position state via Pulse feedback."""
        
        # ── Confidence gate: Skip low-quality signals ───────────────────────────
        MIN_CONFIDENCE = 0.6
        if confidence < MIN_CONFIDENCE:
            logger.info(
                f"🛡️ {symbol}: LOW CONFIDENCE ({confidence:.2f} < {MIN_CONFIDENCE}) → HOLD"
            )
            edge_decision_total.labels(symbol=symbol, decision=Decision.HOLD.value).inc()
            return Decision.HOLD
        
        # Scale signal strength based on confidence (0.6-1.0 maps to ~0.7-1.0 factor)
        confidence_factor = 0.7 + (confidence - MIN_CONFIDENCE) * 0.75  # 0.6→0.7, 1.0→1.0
        effective_signal = signal_strength * confidence_factor
        
        # Track confidence metrics
        edge_confidence_score.labels(symbol=symbol).set(confidence)
        edge_signal_quality.labels(symbol=symbol).set(confidence_factor)
        
        max_losses = (
            int(max_consecutive_losses)
            if max_consecutive_losses is not None
            else self.MAX_CONSECUTIVE_LOSSES
        )
        max_drawdown = (
            float(max_drawdown_pct)
            if max_drawdown_pct is not None
            else self.MAX_DRAWDOWN_PCT
        )
        trailing_profit_threshold = (
            float(trailing_stop_profit_threshold)
            if trailing_stop_profit_threshold is not None
            else self.TRAILING_STOP_PROFIT_THRESHOLD
        )

        # Initialize tracking
        if symbol not in self.consecutive_losses:
            self.consecutive_losses[symbol] = 0
            self.total_trades[symbol] = 0
            self.winning_trades[symbol] = 0
            self.peak_equity[symbol] = 0.0
        
        # Update metrics
        edge_consecutive_losses.labels(symbol=symbol).set(self.consecutive_losses[symbol])
        if self.total_trades[symbol] > 0:
            win_rate = (self.winning_trades[symbol] / self.total_trades[symbol]) * 100
            edge_win_rate.labels(symbol=symbol).set(win_rate)
        
        # ═══════════════════════════════════════════════════════════
        # EMERGENCY CONDITIONS
        # ═══════════════════════════════════════════════════════════
        
        # Global kill switch
        if self.global_kill_switch:
            logger.warning(f"🚨 {symbol}: GLOBAL KILL SWITCH ACTIVATED")
            decision = Decision.EMERGENCY_EXIT
            edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
            return decision
        
        # Too many consecutive losses
        if self.consecutive_losses[symbol] >= max_losses:
            logger.warning(
                f"⛔ {symbol}: Max consecutive losses reached ({self.consecutive_losses[symbol]})"
            )
            decision = Decision.EMERGENCY_EXIT
            edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
            return decision
        
        # Excessive drawdown
        if current_drawdown > max_drawdown:
            logger.warning(
                f"⛔ {symbol}: Excessive drawdown ({current_drawdown:.2f}%)"
            )
            decision = Decision.EMERGENCY_EXIT
            edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
            return decision
        
        # ═══════════════════════════════════════════════════════════
        # POSITION MANAGEMENT
        # ═══════════════════════════════════════════════════════════
        
        if has_position:
            # Strong move while already trailing — auto-tighten to 0.5 %
            if (
                trailing_enabled
                and effective_signal >= 7.0
                and pnl_pct > 5.0
            ):
                logger.info(
                    f"🎯 {symbol}: Strong move + profit >{pnl_pct:.1f}% → tightening trailing stop"
                )
                decision = Decision.TIGHTEN_TRAILING_STOP
                edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
                return decision

            # Already in profit - enable trailing stop
            if pnl_pct > trailing_profit_threshold and not trailing_enabled:
                logger.info(
                    f"✅ {symbol}: Profit threshold reached ({pnl_pct:.2f}%), enabling trailing stop"
                )
                decision = Decision.ENABLE_TRAILING_STOP
                edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
                return decision
            
            # Trend reversing - tighten stops
            if trend == TrendDirection.BEARISH and effective_signal < -3.0:
                logger.warning(
                    f"⚠️ {symbol}: Bearish reversal detected (strength: {effective_signal:.2f})"
                )
                decision = Decision.TIGHTEN_STOP
                edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
                return decision
        
        # ═══════════════════════════════════════════════════════════
        # ENTRY/EXIT LOGIC
        # ═══════════════════════════════════════════════════════════
        
        if trend == TrendDirection.BULLISH:
            if effective_signal >= 5.0:
                # Strong bullish signal - buy
                logger.info(
                    f"🚀 {symbol}: Strong bullish signal (strength: {effective_signal:.2f}) - BUY"
                )
                decision = Decision.BUY
            elif effective_signal >= 3.0:
                # Moderate bullish - buy if not too risky
                if self.consecutive_losses[symbol] < 2:
                    decision = Decision.BUY
                else:
                    decision = Decision.HOLD
            else:
                decision = Decision.HOLD
        
        elif trend == TrendDirection.BEARISH:
            if effective_signal <= -5.0:
                # Strong bearish - stop buying
                logger.warning(
                    f"🔻 {symbol}: Strong bearish signal (strength: {effective_signal:.2f}) - STOP BUYING"
                )
                decision = Decision.STOP_BUYING
            elif effective_signal <= -3.0:
                # Moderate bearish
                decision = Decision.STOP_BUYING if has_position else Decision.HOLD
            else:
                decision = Decision.HOLD
        
        else:
            # Neutral trend
            decision = Decision.HOLD
        
        # Record decision
        edge_decision_total.labels(symbol=symbol, decision=decision.value).inc()
        
        return decision
    
    # ====================== LEGACY COMPATIBILITY METHODS ======================
    
    def record_trade_result_legacy(
        self,
        symbol: str,
        profit: float,
        fill_price: Optional[float] = None,
        quantity: Optional[float] = None,
        side: Optional[str] = None,
        realized_pnl: Optional[float] = None,
        order_id: Optional[str] = None,
    ):
        """Legacy version for backward compatibility.
        
        Called when Pulse reports ORDER_FILLED via Command Bus.
        This closes the feedback loop and enables advanced risk logic.
        """
        # Use realized PnL if provided, otherwise use profit
        final_pnl = realized_pnl if realized_pnl is not None else profit
        
        logger.info(
            "📊 Trade recorded: %s %s @ %.2f qty=%.4f pnl=%.2f order_id=%s",
            symbol, side or "UNKNOWN", 
            fill_price or 0, quantity or 0,
            final_pnl, order_id or "N/A"
        )
        
        if symbol not in self.total_trades:
            self.total_trades[symbol] = 0
            self.winning_trades[symbol] = 0
            self.consecutive_losses[symbol] = 0
            self.position_pnl[symbol] = 0.0
        
        self.total_trades[symbol] += 1
        
        if final_pnl > 0:
            self.winning_trades[symbol] += 1
            self.consecutive_losses[symbol] = 0
            logger.info(f"✅ {symbol}: Winning trade (+${final_pnl:.2f})")
        else:
            self.consecutive_losses[symbol] += 1
            logger.warning(
                f"❌ {symbol}: Losing trade (-${abs(final_pnl):.2f}) "
                f"[Streak: {self.consecutive_losses[symbol]}]"
            )
        
        # Update position PnL
        self.position_pnl[symbol] = final_pnl
        self.daily_pnl[symbol] += final_pnl
        
        # Update metrics
        edge_consecutive_losses.labels(symbol=symbol).set(self.consecutive_losses[symbol])
        win_rate = (self.winning_trades[symbol] / self.total_trades[symbol]) * 100
        edge_win_rate.labels(symbol=symbol).set(win_rate)

    def update_position_state(
        self,
        symbol: str,
        position_size: float,
        entry_price: Optional[float] = None,
        pnl_pct: float = 0.0,
        pnl_dollar: float = 0.0,
    ):
        """Update position state from Pulse (sync version).
        
        Called when Pulse reports POSITION_UPDATE via Command Bus.
        This keeps DecisionEngine in sync with real position state.
        """
        self.position_pnl[symbol] = pnl_dollar
        
        logger.debug(
            "📍 Position update: %s size=%.4f entry=%.2f pnl=%.2f%% ($.2f)",
            symbol, position_size, entry_price or 0, pnl_pct, pnl_dollar
        )

    def update_account_state(
        self,
        total_equity: float,
        available_balance: float,
        margin_used: float = 0.0,
        unrealized_pnl: float = 0.0,
    ):
        """Update account-level state from Pulse.
        
        Called when Pulse reports ACCOUNT_UPDATE via Command Bus.
        This enables account-level risk checks.
        """
        # Update peak equity for drawdown tracking
        if not hasattr(self, 'peak_equity_total'):
            self.peak_equity_total = total_equity
            
        if total_equity > self.peak_equity_total:
            self.peak_equity_total = total_equity
        
        # Calculate current drawdown
        if self.peak_equity_total > 0:
            drawdown_pct = ((self.peak_equity_total - total_equity) / self.peak_equity_total) * 100
            logger.debug(
                "💰 Account update: equity=%.2f unrealized_pnl=%.2f drawdown=%.2f%%",
                total_equity, unrealized_pnl, drawdown_pct
            )

        if self.peak_equity_total <= 0:
            drawdown_pct = 0.0

        self.account_state = {
            "total_equity": total_equity,
            "equity": total_equity,
            "available_balance": available_balance,
            "margin_used": margin_used,
            "unrealized_pnl": unrealized_pnl,
            "drawdown_pct": drawdown_pct,
            "updated_at": datetime.utcnow().isoformat(),
        }

    def record_order_rejected(
        self,
        symbol: str,
        order_id: str,
        reason: str,
    ):
        """Record order rejection for tracking.
        
        Called when Pulse reports ORDER_REJECTED via Command Bus.
        """
        if not hasattr(self, 'rejected_orders'):
            self.rejected_orders = {}
        
        if symbol not in self.rejected_orders:
            self.rejected_orders[symbol] = 0
        self.rejected_orders[symbol] += 1
        
        logger.warning(
            "❌ Order rejected: %s order_id=%s reason=%s (total rejected: %d)",
            symbol, order_id, reason, self.rejected_orders[symbol]
        )

    # ====================== UTILITY ======================

    def get_position(self, symbol: str) -> Optional[dict]:
        """Get position info for a symbol."""
        return self.positions.get(symbol.upper())

    def get_all_positions(self) -> Dict[str, dict]:
        """Get all positions."""
        return self.positions

    def get_daily_pnl_pct(self) -> float:
        """Return today's realized PnL as a percentage of known account equity."""
        total_pnl = sum(float(value) for value in self.daily_pnl.values())
        equity = float(
            self.account_state.get("start_of_day_equity")
            or self.account_state.get("starting_equity")
            or self.account_state.get("previous_close_equity")
            or self.account_state.get("total_equity")
            or self.account_state.get("equity")
            or 0.0
        )
        if equity <= 0:
            return 0.0
        return (total_pnl / equity) * 100.0

    def reset_daily(self):
        """Call this at market open"""
        self.daily_pnl.clear()
        self.consecutive_losses.clear()
        logger.info("DecisionEngine daily reset completed")


    # ====================== OBSERVATION INTEGRATION ======================


    def add_observation(self, observation: BaseObservation) -> None:
        """Add an observation to the symbol's observation history.
        
        Observations come from:
        - Pulse: Execution results (fills, rejections)
        - Edge: Pattern detections (ORB, momentum)
        - External: News, sentiment, etc.
        
        Args:
            observation: Validated observation object
        """
        symbol = observation.symbol.upper()
        self.observations[symbol].append(observation)
        
        logger.debug(
            f"📊 Observation added: {observation.source.value} -> {symbol} | "
            f"type={getattr(observation, 'pattern_type', getattr(observation, 'observation_type', 'unknown'))}"
        )


    def get_observation_impact(self, symbol: str) -> float:
        """Calculate total impact from recent observations on scoring.
        
        Returns:
            Impact value from -1.0 to +1.0 that should modify signal score
        """
        symbol = symbol.upper()
        observations = self.observations.get(symbol, [])
        
        if not observations:
            return 0.0
        
        now = datetime.utcnow()
        total_impact = 0.0
        
        for obs in observations:
            # Check for desync
            desync_msg = self.desync_monitor.check_desync(
                symbol, obs.timestamp, now
            )
            if desync_msg:
                logger.warning(f"⚠️ {desync_msg}")
                continue
            
            # Calculate impact
            impact = self.observation_scorer.calculate_impact(obs, now)
            total_impact += impact
        
        # Average out multiple observations
        return max(-1.0, min(1.0, total_impact / len(observations)))


    def apply_observation_adjustment(
        self,
        signal_strength: float,
        symbol: str
    ) -> float:
        """Apply observation-based adjustments to signal strength.
        
        This is called during decision making to weight observations.
        
        Args:
            signal_strength: Base signal strength from SignalEngine
            symbol: Symbol being evaluated
            
        Returns:
            Adjusted signal strength incorporating observations
        """
        impact = self.get_observation_impact(symbol)
        
        if impact != 0.0:
            # Convert impact to adjustment (max ±1.5 points)
            adjustment = impact * 1.5
            adjusted = signal_strength + adjustment
            logger.info(
                f"📊 {symbol}: Signal adjusted by {adjustment:+.2f} "
                f"({signal_strength:.2f} -> {adjusted:.2f}) from observations"
            )
            return adjusted
        
        return signal_strength


    def check_timeframe_desync(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Check for timeframe desync between Edge and Pulse.
        
        Args:
            symbol: Symbol to check
            
        Returns:
            Dict with desync info if detected, None otherwise
        """
        symbol = symbol.upper()
        observations = self.observations.get(symbol, [])
        
        if not observations:
            return None
        
        now = datetime.utcnow()
        latest_obs_time = max(obs.timestamp for obs in observations)
        
        drift_seconds = (now - latest_obs_time).total_seconds()
        
        if drift_seconds > 60:  # More than 60s is concerning
            return {
                "symbol": symbol,
                "drift_seconds": drift_seconds,
                "latest_observation": latest_obs_time.isoformat(),
                "observation_count": len(observations),
                "severity": "HIGH" if drift_seconds > 120 else "MEDIUM"
            }
        
        return None


    def get_observation_status(self) -> Dict[str, Any]:
        """Get overall observation system status."""
        return {
            "symbols_with_observations": len(self.observations),
            "desync_status": self.desync_monitor.get_status(),
            "scorer_config": {
                "max_age_seconds": self.observation_scorer.weights.observation_max_age_seconds,
                "max_drift_seconds": self.observation_scorer.weights.max_timeframe_diff_seconds
            }
        }


    def clear_old_observations(self, max_age_minutes: int = 5) -> int:
        """Remove observations older than max_age_minutes.
        
        Should be called periodically to prevent memory buildup.
        
        Args:
            max_age_minutes: Maximum age in minutes
            
        Returns:
            Number of observations cleared
        """
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        cleared = 0
        
        for symbol in list(self.observations.keys()):
            obs_list = list(self.observations[symbol])
            filtered = [obs for obs in obs_list if obs.timestamp > cutoff]
            
            if len(filtered) != len(obs_list):
                self.observations[symbol] = deque(filtered)
                cleared += len(obs_list) - len(filtered)
        
        if cleared > 0:
            logger.info(f"🧹 Cleared {cleared} old observations")
        
        return cleared
