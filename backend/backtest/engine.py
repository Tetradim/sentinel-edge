"""Comprehensive Backtesting & Sentinel Archive - Phase 8

This module provides:
- BacktestEngine: Historical backtesting with realistic execution
- MonteCarloEngine: Probabilistic simulation
- Strategy interface: Custom strategies can be plugged in
- Performance metrics: Sharpe, Sortino, drawdown, etc.

This is the single source of truth for backtesting functionality.
Previously this was split between engine.py and monte_carlo.py.
"""
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Optional dependencies
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed. Install with: pip install yfinance")


# ============================================================================
# Configuration
# ============================================================================

class DataSource(str, Enum):
    YFINANCE = "yfinance"
    POLYGON = "polygon"
    CUSTOM = "custom"


@dataclass
class BacktestConfig:
    """Backtest configuration - all settings in one place"""
    # Symbols and timeframe
    symbols: List[str] = field(default_factory=lambda: ["AAPL"])
    start_date: str = "2023-01-01"
    end_date: str = "2024-01-01"
    timeframe: str = "1d"  # 1m, 5m, 15m, 1h, 1d, 1wk
    
    # Capital settings
    initial_capital: float = 100000
    position_size_pct: float = 0.10  # 10% per trade
    max_positions: int = 5
    
    # Risk settings
    stop_loss_pct: float = 0.05  # 5% stop loss
    take_profit_pct: float = 0.15  # 15% take profit
    trailing_stop: bool = True
    trailing_pct: float = 0.03
    
    # Execution costs
    commission_pct: float = 0.001  # 0.1% commission
    slippage_pct: float = 0.0005  # 0.05% slippage
    
    # Data source
    data_source: DataSource = DataSource.YFINANCE
    
    # Advanced
    allow_short: bool = False
    hedge_mode: bool = False


@dataclass
class Trade:
    """Individual trade record"""
    entry_date: Optional[datetime] = None
    exit_date: Optional[datetime] = None
    symbol: str = ""
    side: str = "LONG"  # LONG, SHORT
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    holding_period: int = 0  # bars
    signal: str = ""  # What triggered the trade
    patterns: List[str] = field(default_factory=list)


@dataclass
class Position:
    """Current position state"""
    symbol: str = ""
    side: str = "LONG"
    quantity: float = 0.0
    entry_price: float = 0.0
    entry_date: Optional[datetime] = None
    stop_loss: float = 0.0
    take_profit: float = 0.0
    trailing_stop: float = 0.0


# ============================================================================
# Performance Metrics (DataFrame-friendly)
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Complete performance metrics"""
    # Returns
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    
    # Risk
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_holding_period: float = 0.0
    
    # Position stats
    avg_position_size: float = 0.0
    max_position_size: float = 0.0
    
    # Time stats
    time_in_market: float = 0.0
    
    # Equity
    equity_curve: List[float] = field(default_factory=list)
    equity_dates: List[str] = field(default_factory=list)
    
    # Trade log
    trades: List[Trade] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON/API responses"""
        return {
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "annualized_return": self.annualized_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_holding_period": self.avg_holding_period,
        }


# ============================================================================
# Strategy Interface
# ============================================================================

class Strategy(Callable):
    """Base strategy class for backtesting - implement generate_signals()"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
    
    async def generate_signals(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        """Generate trading signals from price data.
        
        Should return DataFrame with columns:
        - signal: 1 (buy), -1 (sell), 0 (hold)
        - confidence: 0-1
        - reason: str
        
        The DataFrame index should be preserved.
        """
        raise NotImplementedError("Subclass must implement generate_signals()")
    
    async def analyze(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> Dict[str, Any]:
        """Full analysis - can be overridden for richer output"""
        signals = await self.generate_signals(symbol, data)
        return {"signals": signals}


# ============================================================================
# Built-in Strategies
# ============================================================================

class SimpleMovingAverageStrategy(Strategy):
    """SMA crossover strategy"""
    
    def __init__(self, config: BacktestConfig, fast: int = 10, slow: int = 30):
        super().__init__(config)
        self.fast = fast
        self.slow = slow
    
    async def generate_signals(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        df = data.copy()
        
        # Handle MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Standardize column names
        df.columns = [c.lower() for c in df.columns]
        
        # Ensure we have required columns
        if 'close' not in df.columns:
            raise ValueError(f"Missing 'close' column in data for {symbol}")
        
        df['sma_fast'] = df['close'].rolling(self.fast).mean()
        df['sma_slow'] = df['close'].rolling(self.slow).mean()
        
        # Signal: crossover detection
        df['signal'] = 0
        above = df['sma_fast'] > df['sma_slow']
        df['above_prev'] = above.shift(1)
        df.loc[(above) & (~df['above_prev']), 'signal'] = 1
        df.loc[(~above) & (df['above_prev']), 'signal'] = -1
        
        df['confidence'] = 0.7
        df['reason'] = f"SMA {self.fast}/{self.slow} crossover"
        
        # Clean up helper columns
        df = df.drop(columns=['above_prev'], errors='ignore')
        
        return df[['open', 'high', 'low', 'close', 'volume', 'signal', 'confidence', 'reason']]


class RSIStrategy(Strategy):
    """RSI-based strategy"""
    
    def __init__(self, config: BacktestConfig, period: int = 14, oversold: int = 30, overbought: int = 70):
        super().__init__(config)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    async def generate_signals(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        df = data.copy()
        
        # Handle columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if 'close' not in df.columns:
            raise ValueError(f"Missing 'close' column in data for {symbol}")
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(self.period).mean()
        avg_loss = loss.rolling(self.period).mean()
        
        rs = avg_gain / (avg_loss + 1e-10)
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Signals
        df['signal'] = 0
        df.loc[df['rsi'] < self.oversold, 'signal'] = 1
        df.loc[df['rsi'] > self.overbought, 'signal'] = -1
        
        # Confidence based on distance from extremes
        df['confidence'] = np.where(
            df['rsi'] < self.oversold,
            (self.oversold - df['rsi']) / self.oversold,
            np.where(df['rsi'] > self.overbought, 
                    (df['rsi'] - self.overbought) / (100 - self.overbought), 0)
        )
        df['reason'] = f"RSI (oversold<{self.oversold}, overbought>{self.overbought})"
        
        return df[['open', 'high', 'low', 'close', 'volume', 'signal', 'confidence', 'reason']]


class BreakoutStrategy(Strategy):
    """Channel breakout strategy"""
    
    def __init__(self, config: BacktestConfig, lookback: int = 20):
        super().__init__(config)
        self.lookback = lookback
    
    async def generate_signals(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> pd.DataFrame:
        df = data.copy()
        
        # Handle columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if 'close' not in df.columns or 'high' not in df.columns or 'low' not in df.columns:
            raise ValueError(f"Missing required columns in data for {symbol}")
        
        # Channel breakout
        df['highest'] = df['high'].rolling(self.lookback).max()
        df['lowest'] = df['low'].rolling(self.lookback).min()
        
        # Signals
        df['signal'] = 0
        df.loc[df['close'] > df['highest'].shift(1), 'signal'] = 1
        df.loc[df['close'] < df['lowest'].shift(1), 'signal'] = -1
        
        # Confidence based on volume
        df['vol_ma'] = df['volume'].rolling(20).mean()
        df['confidence'] = np.where(
            df['signal'] != 0,
            np.clip(df['volume'] / df['vol_ma'], 0.5, 1.0),
            0
        )
        df['reason'] = f"Breakout (lookback={self.lookback})"
        
        return df[['open', 'high', 'low', 'close', 'volume', 'signal', 'confidence', 'reason']]


# ============================================================================
# Data Fetching
# ============================================================================

class DataFetcher:
    """Fetch historical data for backtesting"""
    
    @staticmethod
    async def fetch_yahoo(
        symbol: str,
        start: str,
        end: str,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Fetch data from Yahoo Finance"""
        if not YFINANCE_AVAILABLE:
            raise RuntimeError("yfinance not available")
        
        # Map interval to yfinance format
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h",
            "1d": "1d", "1wk": "1wk"
        }
        yf_interval = interval_map.get(interval, "1d")
        
        # Run in thread to avoid blocking
        loop = asyncio.get_event_loop()
        with asyncio.timeout(30):  # 30 second timeout
            ticker = await loop.run_in_executor(
                None,
                lambda: yf.download(symbol, start=start, end=end, interval=yf_interval, progress=False)
            )
        
        if ticker.empty:
            raise ValueError(f"No data returned for {symbol}")
        
        # Flatten multi-index columns if present
        if isinstance(ticker.columns, pd.MultiIndex):
            ticker.columns = ticker.columns.get_level_values(0)
        
        # Standardize column names
        ticker.columns = [c.lower() for c in ticker.columns]
        
        # Ensure OHLCV
        required = ['open', 'high', 'low', 'close', 'volume']
        for col in required:
            if col not in ticker.columns:
                raise ValueError(f"Missing column {col} in data for {symbol}")
        
        return ticker
    
    @staticmethod
    async def fetch_multi(
        symbols: List[str],
        config: BacktestConfig
    ) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols"""
        data = {}
        
        for symbol in symbols:
            try:
                df = await DataFetcher.fetch_yahoo(
                    symbol,
                    config.start_date,
                    config.end_date,
                    config.timeframe
                )
                data[symbol] = df
                logger.info(f"Fetched {len(df)} bars for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to fetch {symbol}: {e}")
        
        return data


# ============================================================================
# Main Backtest Engine
# ============================================================================

class BacktestEngine:
    """Comprehensive backtesting engine with full position management.
    
    This is the single source of truth - replaces the old engine.py
    
    Usage:
        config = BacktestConfig(symbols=["NVDA"], start_date="2023-01-01", end_date="2024-01-01")
        strategy = SimpleMovingAverageStrategy(config)
        engine = BacktestEngine(config, strategy)
        results = await engine.run()
    """
    
    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        strategy: Optional[Strategy] = None,
        price_fetcher: Optional[Callable] = None,
        decision_engine: Optional[Any] = None
    ):
        """
        Initialize backtest engine.
        
        Args:
            config: BacktestConfig with all settings
            strategy: Strategy instance for signal generation
            price_fetcher: Legacy price fetcher (optional, for backward compat)
            decision_engine: Legacy decision engine (optional, for backward compat)
        """
        # Support legacy parameter passing
        if config is None:
            config = BacktestConfig()
        
        self.config = config
        self.strategy = strategy
        self.price_fetcher = price_fetcher
        self.decision_engine = decision_engine
        
        # State
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [config.initial_capital]
        self.equity_dates: List[datetime] = []
        
        # Metrics
        self.metrics: Optional[PerformanceMetrics] = None
        
        # Cache
        self.data_cache: Dict[str, pd.DataFrame] = {}
        
        logger.info(f"BacktestEngine initialized: {config.symbols}, ${config.initial_capital}")
    
    async def run(self) -> PerformanceMetrics:
        """Run the backtest - main entry point"""
        logger.info("Fetching data...")
        data = await DataFetcher.fetch_multi(self.config.symbols, self.config)
        
        if not data:
            raise RuntimeError("No data fetched")
        
        self.data_cache = data
        
        # Get common date range
        common_dates = None
        for df in data.values():
            if common_dates is None:
                common_dates = df.index
            else:
                common_dates = common_dates.intersection(df.index)
        
        if common_dates is None or len(common_dates) == 0:
            raise RuntimeError("No overlapping dates in data")
        
        logger.info(f"Running backtest from {common_dates[0]} to {common_dates[-1]}")
        
        # Run simulation
        for date in common_dates:
            # Update equity
            self.equity_dates.append(date)
            current_capital = self._calculate_portfolio_value(data, date)
            self.equity_curve.append(current_capital)
            
            # Process each symbol
            for symbol, df in data.items():
                if date not in df.index:
                    continue
                
                await self._process_bar(symbol, df, date, current_capital)
        
        # Close any open positions at end
        await self._close_all_positions(data, common_dates[-1])
        
        # Calculate metrics
        self.metrics = self._calculate_metrics()
        
        return self.metrics
    
    def _calculate_portfolio_value(
        self,
        data: Dict[str, pd.DataFrame],
        date: datetime
    ) -> float:
        """Calculate total portfolio value at a date"""
        cash = self.equity_curve[-1] if self.equity_curve else self.config.initial_capital
        position_value = 0.0
        
        for symbol, pos in self.positions.items():
            if symbol in data and date in data[symbol].index:
                current_price = data[symbol].loc[date, 'close']
                position_value += pos.quantity * current_price
        
        return cash + position_value
    
    async def _process_bar(
        self,
        symbol: str,
        data: pd.DataFrame,
        date: datetime,
        current_capital: float
    ):
        """Process a single bar"""
        row = data.loc[date]
        price = row['close']
        
        # Generate signals
        signal = 0
        confidence = 0.5
        reason = "no strategy"
        
        if self.strategy:
            try:
                signals = await self.strategy.generate_signals(symbol, data[:date + timedelta(days=1)])
                # Find the signal for this date
                if date in signals.index:
                    signal_row = signals.loc[date]
                    signal = int(signal_row.get('signal', 0))
                    confidence = float(signal_row.get('confidence', 0.5))
                    reason = str(signal_row.get('reason', 'strategy'))
            except Exception as e:
                logger.debug(f"Signal generation error for {symbol}: {e}")
        
        # Get current position
        position = self.positions.get(symbol)
        
        # Check exits first
        if position:
            # Stop loss
            if position.side == "LONG" and price <= position.stop_loss:
                await self._close_position(symbol, price, date, "stop_loss")
                return
            elif position.side == "SHORT" and price >= position.stop_loss:
                await self._close_position(symbol, price, date, "stop_loss")
                return
            
            # Take profit
            if position.side == "LONG" and price >= position.take_profit:
                await self._close_position(symbol, price, date, "take_profit")
                return
            elif position.side == "SHORT" and price <= position.take_profit:
                await self._close_position(symbol, price, date, "take_profit")
                return
            
            # Trailing stop
            if self.config.trailing_stop and position.trailing_stop > 0:
                if position.side == "LONG" and price <= position.trailing_stop:
                    await self._close_position(symbol, price, date, "trailing_stop")
                    return
                elif position.side == "SHORT" and price >= position.trailing_stop:
                    await self._close_position(symbol, price, date, "trailing_stop")
                    return
            
            # Update trailing stop
            if self.config.trailing_stop and position.side == "LONG":
                new_trailing = price * (1 - self.config.trailing_pct)
                if new_trailing > position.trailing_stop:
                    position.trailing_stop = new_trailing
            elif self.config.trailing_stop and position.side == "SHORT":
                new_trailing = price * (1 + self.config.trailing_pct)
                if new_trailing < position.trailing_stop or position.trailing_stop == 0:
                    position.trailing_stop = new_trailing
        
        # Check entries
        if signal == 1 and not position and len(self.positions) < self.config.max_positions:
            # Apply slippage to entry
            entry_price = price * (1 + self.config.slippage_pct)
            
            position_value = current_capital * self.config.position_size_pct
            quantity = position_value / entry_price
            
            stop_loss = entry_price * (1 - self.config.stop_loss_pct)
            take_profit = entry_price * (1 + self.config.take_profit_pct)
            
            self.positions[symbol] = Position(
                symbol=symbol,
                side="LONG",
                quantity=quantity,
                entry_price=entry_price,
                entry_date=date,
                stop_loss=stop_loss,
                take_profit=take_profit,
                trailing_stop=0
            )
            
            logger.debug(f"{date}: BUY {symbol} @ ${entry_price:.2f}")
        
        elif signal == -1 and position:
            # Apply slippage to exit
            exit_price = price * (1 - self.config.slippage_pct)
            await self._close_position(symbol, exit_price, date, reason)
    
    async def _close_position(
        self,
        symbol: str,
        price: float,
        date: datetime,
        reason: str
    ):
        """Close a position"""
        position = self.positions.pop(symbol)
        
        # Calculate PnL
        if position.side == "LONG":
            pnl = (price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - price) * position.quantity
        
        pnl_pct = (price - position.entry_price) / position.entry_price * 100 if position.entry_price > 0 else 0
        
        # Commission
        value = price * position.quantity
        commission = value * self.config.commission_pct
        pnl -= commission
        
        # Holding period
        holding_period = 1
        if position.entry_date:
            if isinstance(position.entry_date, datetime) and isinstance(date, datetime):
                holding_period = max(1, (date - position.entry_date).days)
        
        # Record trade
        trade = Trade(
            entry_date=position.entry_date,
            exit_date=date,
            symbol=symbol,
            side=position.side,
            entry_price=position.entry_price,
            exit_price=price,
            quantity=position.quantity,
            pnl=pnl,
            pnl_pct=pnl_pct,
            commission=commission,
            holding_period=holding_period,
            signal=reason
        )
        self.trades.append(trade)
        
        logger.debug(f"{date}: SELL {symbol} @ ${price:.2f} | PnL: ${pnl:.2f} ({pnl_pct:+.2f}%)")
    
    async def _close_all_positions(self, data: pd.DataFrame, date: datetime):
        """Close all open positions at end of backtest"""
        for symbol, position in list(self.positions.items()):
            if symbol in data:
                final_price = data[symbol].iloc[-1]['close']
                await self._close_position(symbol, final_price, date, "end_of_backtest")
    
    def _calculate_metrics(self) -> PerformanceMetrics:
        """Calculate performance metrics"""
        if not self.trades:
            return PerformanceMetrics()
        
        # Basic stats
        pnls = [t.pnl for t in self.trades]
        winning_pnls = [p for p in pnls if p > 0]
        losing_pnls = [p for p in pnls if p <= 0]
        
        total_pnl = sum(pnls)
        total_return_pct = (total_pnl / self.config.initial_capital) * 100
        
        # Annualized return
        if len(self.equity_dates) > 1:
            days = (self.equity_dates[-1] - self.equity_dates[0]).days
            years = days / 365
            annualized = ((1 + total_return_pct / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
        else:
            annualized = 0
        
        # Volatility (annualized)
        if len(self.equity_curve) > 1:
            returns = np.diff(self.equity_curve) / np.array(self.equity_curve[:-1])
            returns = returns[np.isfinite(returns)]  # Remove inf/nan
            volatility = np.std(returns) * np.sqrt(252) * 100 if len(returns) > 0 else 0
        else:
            volatility = 0
        
        # Sharpe ratio
        sharpe = (annualized - 0) / volatility if volatility > 0 else 0
        
        # Sortino (downside deviation)
        if len(self.equity_curve) > 1:
            downside_returns = returns[returns < 0]
            downside_std = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
            sortino = (annualized - 0) / downside_std if downside_std > 0 else 0
        else:
            sortino = 0
        
        # Drawdown
        equity_arr = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity_arr)
        drawdowns = (equity_arr - running_max) / running_max * 100
        max_drawdown = abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0
        
        # Trade stats
        total_trades = len(self.trades)
        winning_trades = len(winning_pnls)
        losing_trades = len(losing_pnls)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = np.mean(winning_pnls) if winning_pnls else 0
        avg_loss = np.mean(losing_pnls) if losing_pnls else 0
        
        # Holding period
        holding_periods = [t.holding_period for t in self.trades]
        avg_holding = np.mean(holding_periods) if holding_periods else 0
        
        return PerformanceMetrics(
            total_return=total_pnl,
            total_return_pct=total_return_pct,
            annualized_return=annualized,
            volatility=volatility,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_holding_period=avg_holding,
            equity_curve=self.equity_curve,
            equity_dates=[d.strftime('%Y-%m-%d') for d in self.equity_dates],
            trades=self.trades
        )
    
    # ============================================================================
    # Legacy API Compatibility (for backward compat with old code)
    # ============================================================================
    
    async def run_backtest(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 10000.0,
        slippage_pct: float = 0.05,
        commission_pct: float = 0.1,
        num_simulations: int = 1000,
        volatility_multiplier: float = 1.0
    ) -> Dict:
        """
        Legacy API - wraps the new run() method for backward compatibility.
        
        Old code calling run_backtest() will still work.
        """
        # Update config for legacy call
        self.config.symbols = [symbol]
        self.config.start_date = start_date
        self.config.end_date = end_date
        self.config.initial_capital = initial_capital
        self.config.slippage_pct = slippage_pct / 100  # Convert %
        self.config.commission_pct = commission_pct / 100
        
        try:
            metrics = await self.run()
            
            return {
                "symbol": symbol,
                "trades": [
                    {
                        "entry_time": t.entry_date.isoformat() if t.entry_date else None,
                        "exit_time": t.exit_date.isoformat() if t.exit_date else None,
                        "pnl": t.pnl,
                        "pnl_pct": t.pnl_pct
                    } for t in metrics.trades
                ],
                "final_capital": self.equity_curve[-1] if self.equity_curve else initial_capital,
                "win_rate": metrics.win_rate,
                "total_return_pct": metrics.total_return_pct,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "equity_curve": self.equity_curve,
                "trade_points": []
            }
        except Exception as e:
            return {"error": str(e)}
    
    def print_summary(self):
        """Print backtest summary"""
        if not self.metrics:
            print("No results to display")
            return
        
        m = self.metrics
        
        print("\n" + "=" * 60)
        print("BACKTEST RESULTS")
        print("=" * 60)
        print(f"Period: {self.equity_dates[0] if self.equity_dates else 'N/A'} to {self.equity_dates[-1] if self.equity_dates else 'N/A'}")
        print(f"Initial Capital: ${self.config.initial_capital:,.2f}")
        print(f"Final Equity: ${self.equity_curve[-1]:,.2f}")
        print()
        print("RETURN:")
        print(f"  Total Return: ${m.total_return:+,.2f} ({m.total_return_pct:+.2f}%)")
        print(f"  Annualized: {m.annualized_return:+.2f}%")
        print()
        print("RISK:")
        print(f"  Volatility: {m.volatility:.2f}%")
        print(f"  Sharpe: {m.sharpe_ratio:.2f}")
        print(f"  Sortino: {m.sortino_ratio:.2f}")
        print(f"  Max Drawdown: {m.max_drawdown_pct:.2f}%")
        print()
        print("TRADES:")
        print(f"  Total: {m.total_trades}")
        print(f"  Winners: {m.winning_trades}")
        print(f"  Losers: {m.losing_trades}")
        print(f"  Win Rate: {m.win_rate*100:.1f}%")
        print(f"  Avg Win: ${m.avg_win:+,.2f}")
        print(f"  Avg Loss: ${m.avg_loss:+,.2f}")
        print(f"  Avg Holding: {m.avg_holding_period:.1f} days")
        print("=" * 60)
    
    def generate_report(self, filename: str = "backtest_report.html"):
        """Generate HTML report"""
        if not self.metrics:
            print("No results to report")
            return
        
        m = self.metrics
        
        trades_html = "".join(
            f"<tr><td>{t.entry_date.strftime('%Y-%m-%d') if t.entry_date else '-'}</td>"
            f"<td>{t.symbol}</td><td>{t.side}</td>"
            f"<td>${t.entry_price:.2f}</td><td>${t.exit_price:.2f}</td>"
            f"<td class='{'positive' if t.pnl >= 0 else 'negative'}>${t.pnl:+,.2f}</td>"
            f"<td class='{'positive' if t.pnl_pct >= 0 else 'negative'}>${t.pnl_pct:+.2f}%</td></tr>"
            for t in self.trades[:50]
        )
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sentinel Edge Backtest Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; background: #1a1a1a; color: #e0e0e0; }}
        h1, h2 {{ color: #4ade80; }}
        .card {{ background: #2a2a2a; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #fff; }}
        .metric-label {{ font-size: 12px; color: #888; }}
        .positive {{ color: #4ade80; }}
        .negative {{ color: #f87171; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ color: #888; }}
    </style>
</head>
<body>
    <h1>📊 Sentinel Edge Backtest Report</h1>
    
    <div class="card">
        <h2>Overview</h2>
        <div class="metric"><div class="metric-label">Period</div><div class="metric-value">{self.equity_dates[0] if self.equity_dates else '-'} to {self.equity_dates[-1] if self.equity_dates else '-'}</div></div>
        <div class="metric"><div class="metric-label">Initial Capital</div><div class="metric-value">${self.config.initial_capital:,.0f}</div></div>
        <div class="metric"><div class="metric-label">Final Equity</div><div class="metric-value">${self.equity_curve[-1]:,.0f}</div></div>
    </div>
    
    <div class="card">
        <h2>Returns</h2>
        <div class="metric"><div class="metric-label">Total Return</div><div class="metric-value {'positive' if m.total_return >= 0 else 'negative'}">${m.total_return:+,.2f} ({m.total_return_pct:+.2f}%)</div></div>
        <div class="metric"><div class="metric-label">Annualized</div><div class="metric-value {'positive' if m.annualized_return >= 0 else 'negative'}">{m.annualized_return:+.2f}%</div></div>
    </div>
    
    <div class="card">
        <h2>Risk Metrics</h2>
        <div class="metric"><div class="metric-label">Volatility</div><div class="metric-value">{m.volatility:.2f}%</div></div>
        <div class="metric"><div class="metric-label">Sharpe</div><div class="metric-value">{m.sharpe_ratio:.2f}</div></div>
        <div class="metric"><div class="metric-label">Sortino</div><div class="metric-value">{m.sortino_ratio:.2f}</div></div>
        <div class="metric"><div class="metric-label">Max Drawdown</div><div class="metric-value negative">{m.max_drawdown_pct:.2f}%</div></div>
    </div>
    
    <div class="card">
        <h2>Trade Statistics</h2>
        <table>
            <tr><th>Total Trades</th><td>{m.total_trades}</td></tr>
            <tr><th>Winners</th><td class="positive">{m.winning_trades}</td></tr>
            <tr><th>Losers</th><td class="negative">{m.losing_trades}</td></tr>
            <tr><th>Win Rate</th><td>{m.win_rate*100:.1f}%</td></tr>
            <tr><th>Avg Win</th><td class="positive">${m.avg_win:+,.2f}</td></tr>
            <tr><th>Avg Loss</th><td class="negative">${m.avg_loss:+,.2f}</td></tr>
            <tr><th>Avg Holding</th><td>{m.avg_holding_period:.1f} days</td></tr>
        </table>
    </div>
    
    <div class="card">
        <h2>Trade Log (last 50)</h2>
        <table>
            <tr><th>Entry</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL</th><th>PnL%</th></tr>
            {trades_html}
        </table>
    </div>
</body>
</html>
"""
        
        with open(filename, 'w') as f:
            f.write(html)
        
        logger.info(f"Report saved to {filename}")


# ============================================================================
# Monte Carlo Engine (enhanced from monte_carlo.py)
# ============================================================================

class MonteCarloEngine:
    """Monte Carlo Sentinel Archive - replaces old monte_carlo.py
    
    Usage:
        mc = MonteCarloEngine()
        results = mc.run_simulation(backtest_engine)
    """
    
    def __init__(self):
        logger.info("MonteCarloEngine initialized")
    
    async def run_simulation(
        self,
        backtest_engine: BacktestEngine,
        num_simulations: int = 1000,
        volatility_multiplier: float = 1.0
    ) -> Dict:
        """
        Run Monte Carlo simulation on backtest results.
        
        Args:
            backtest_engine: BacktestEngine with completed run()
            num_simulations: Number of Monte Carlo iterations
            volatility_multiplier: Multiply observed volatility
            
        Returns:
            Dict with simulation results
        """
        trades = backtest_engine.trades
        
        if not trades:
            return {"error": "No trades in base backtest"}
        
        # Extract returns
        returns = np.array([t.pnl_pct / 100 for t in trades])
        initial_capital = backtest_engine.config.initial_capital
        
        mean_return = np.mean(returns)
        std_return = np.std(returns) * volatility_multiplier
        
        simulated_final_equities = []
        win_rates = []
        max_drawdowns = []
        
        for _ in range(num_simulations):
            # Randomly sample returns
            sim_returns = np.random.normal(mean_return, std_return, len(trades))
            
            # Calculate equity path
            equity = initial_capital
            equity_curve = [equity]
            peak = equity
            
            for r in sim_returns:
                equity *= (1 + r)
                equity_curve.append(equity)
                peak = max(peak, equity)
            
            final_equity = equity_curve[-1]
            simulated_final_equities.append(final_equity)
            
            # Stats
            wins = sum(1 for r in sim_returns if r > 0)
            win_rates.append(wins / len(sim_returns) * 100)
            
            # Drawdown
            running_max = np.maximum.accumulate(equity_curve)
            drawdowns = (equity_curve - running_max) / running_max * 100
            dd = abs(min(drawdowns)) if len(drawdowns) > 0 else 0
            max_drawdowns.append(dd)
        
        return {
            "simulations": num_simulations,
            "base_return_pct": backtest_engine.metrics.total_return_pct if backtest_engine.metrics else 0,
            "mean_final_equity": round(float(np.mean(simulated_final_equities)), 2),
            "median_final_equity": round(float(np.median(simulated_final_equities)), 2),
            "worst_case_equity": round(float(np.percentile(simulated_final_equities, 5)), 2),
            "best_case_equity": round(float(np.percentile(simulated_final_equities, 95)), 2),
            "mean_win_rate": round(float(np.mean(win_rates)), 1),
            "mean_max_drawdown": round(float(np.mean(max_drawdowns)), 2),
            "probability_of_profit": round(
                sum(1 for e in simulated_final_equities if e > initial_capital) / num_simulations * 100,
                1
            )
        }
    
    # Legacy API
    async def run_simulation_old(
        self,
        base_results: dict,
        num_simulations: int = 1000,
        volatility_multiplier: float = 1.0
    ) -> Dict:
        """Legacy API for backward compatibility"""
        if not base_results.get("trades"):
            return {"error": "No trades in base backtest"}
        
        trades = base_results["trades"]
        returns = [t.get("pnl_pct", 0) / 100 for t in trades]
        
        initial_capital = base_results.get("initial_capital", 10000.0)
        mean_return = np.mean(returns)
        std_return = np.std(returns) * volatility_multiplier
        
        simulated_final_equities = []
        win_rates = []
        max_drawdowns = []
        
        for _ in range(num_simulations):
            sim_returns = np.random.normal(mean_return, std_return, len(trades))
            equity = initial_capital
            equity_curve = [equity]
            peak = equity
            
            for r in sim_returns:
                equity *= (1 + r)
                equity_curve.append(equity)
                peak = max(peak, equity)
            
            simulated_final_equities.append(equity_curve[-1])
            win_rates.append(sum(1 for r in sim_returns if r > 0) / len(sim_returns) * 100)
            
            running_max = np.maximum.accumulate(equity_curve)
            drawdowns = (equity_curve - running_max) / running_max * 100
            max_drawdowns.append(max(0, abs(min(drawdowns)) if drawdowns else 0))
        
        return {
            "simulations": num_simulations,
            "base_return_pct": base_results.get("total_return_pct", 0),
            "mean_final_equity": round(float(np.mean(simulated_final_equities)), 2),
            "median_final_equity": round(float(np.median(simulated_final_equities)), 2),
            "worst_case_equity": round(float(np.percentile(simulated_final_equities, 5)), 2),
            "best_case_equity": round(float(np.percentile(simulated_final_equities, 95)), 2),
            "mean_win_rate": round(float(np.mean(win_rates)), 1),
            "mean_max_drawdown": round(float(np.mean(max_drawdowns)), 2),
            "probability_of_profit": round(
                sum(1 for e in simulated_final_equities if e > initial_capital) / num_simulations * 100,
                1
            )
        }


# ============================================================================
# Convenience Functions
# ============================================================================

async def run_simple_backtest(
    symbols: List[str],
    start: str,
    end: str,
    strategy_type: str = "sma",
    initial_capital: float = 100000,
    **kwargs
) -> PerformanceMetrics:
    """Quick backtest with built-in strategy"""
    
    config = BacktestConfig(
        symbols=symbols,
        start_date=start,
        end_date=end,
        initial_capital=initial_capital,
        **kwargs
    )
    
    # Create strategy
    if strategy_type == "sma":
        strategy = SimpleMovingAverageStrategy(config)
    elif strategy_type == "rsi":
        strategy = RSIStrategy(config)
    elif strategy_type == "breakout":
        strategy = BreakoutStrategy(config)
    else:
        strategy = None
    
    engine = BacktestEngine(config, strategy)
    results = await engine.run()
