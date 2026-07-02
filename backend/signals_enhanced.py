"""
Enhanced Signal Analysis Engine - Multi-Timeframe + Advanced Patterns

Features:
- Sophisticated confidence scoring (volume, EMA, RSI, trend context)
- Multi-timeframe support (confirm with higher TF)
- TA-Lib with NumPy fallback
- Advanced candlestick patterns (Island, Abandoned Baby, Kicker, etc.)
- Testing hooks with synthetic data generator
- Prometheus metrics exposed
- Vectorized operations for performance

Usage:
    from signals_enhanced import SignalEngineEnhanced, PatternType
    
    engine = SignalEngineEnhanced(
        enable_talib=True,        # Use TA-Lib if available
        multi_timeframe=True,     # Enable HTF confirmation
        patterns=["ORB", "KICKER", "ISLAND"]
    )
    
    result = await engine.analyze(
        symbol="NVDA",
        price_data=ohlcv_df,      # pandas DataFrame
        timeframe="1m",
        higher_tf_data=None       # Optional HTF data for confirmation
    )
"""
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable

import numpy as np
import pandas as pd

# Optional: TA-Lib
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

# Optional: scipy for peak detection (complex patterns)
try:
    from scipy.signal import find_peaks
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

from metrics import (
    edge_signal_strength,
    edge_trend_direction,
    edge_volume_ratio,
    edge_volume_zscore,
    edge_pattern_detected,
    edge_pattern_confidence,
    edge_pattern_active,
    edge_multi_timeframe_alignment,
    edge_rsi_oversold_total,
    edge_rsi_overbought_total,
    edge_macd_crossover_total,
    edge_support_level,
    edge_resistance_level,
    edge_sentinel_echo_detected,
    edge_volatility_surge,
    edge_confidence_score,
    edge_signal_quality,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

class ConfidenceWeights:
    """Configurable weights for confidence scoring"""
    def __init__(
        self,
        volume_weight: float = 0.20,
        trend_weight: float = 0.25,
        momentum_weight: float = 0.20,
        pattern_weight: float = 0.25,
        rsi_filter_weight: float = 0.10,
        # Multi-timeframe
        htf_confirm_bonus: float = 0.15,
        htf_conflict_penalty: float = 0.25,
    ):
        self.volume_weight = volume_weight
        self.trend_weight = trend_weight
        self.momentum_weight = momentum_weight
        self.pattern_weight = pattern_weight
        self.rsi_filter_weight = rsi_filter_weight
        self.htf_confirm_bonus = htf_confirm_bonus
        self.htf_conflict_penalty = htf_conflict_penalty


# Default weights
DEFAULT_WEIGHTS = ConfidenceWeights()


# ============================================================================
# Enums & Dataclasses
# ============================================================================

class PatternType(str, Enum):
    """Supported candlestick patterns"""
    # Basic
    ORB_BREAKOUT = "ORB_BREAKOUT"
    ORB_FAIL = "ORB_FAIL"
    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    
    # Advanced candlestick (TA-Lib patterns)
    HAMMER = "HAMMER"
    INVERTED_HAMMER = "INVERTED_HAMMER"
    SHOOTING_STAR = "SHOOTING_STAR"
    DOJI = "DOJI"
    DRAGONFLY_DOJI = "DRAGONFLY_DOJI"
    GRAVESTONE_DOJI = "GRAVESTONE_DOJI"
    
    # Multi-candle patterns
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"
    PIERCING = "PIERCING"
    DARK_CLOUD_COVER = "DARK_CLOUD_COVER"
    
    # Rare patterns
    ISLAND_TOP = "ISLAND_TOP"        # Bearish reversal
    ISLAND_BOTTOM = "ISLAND_BOTTOM"  # Bullish reversal
    ABANDONED_BABY = "ABANDONED_BABY"  # Bullish/Bearish reversal
    KICKER_BULLISH = "KICKER_BULLISH"  # Strong bullish reversal
    KICKER_BEARISH = "KICKER_BEARISH"  # Strong bearish reversal
    THREE_WHITE_SOLDIERS = "THREE_WHITE_SOLDIERS"
    THREE_BLACK_CROWS = "THREE_BLACK_CROWS"
    
    # Complex patterns (scipy-based)
    DOUBLE_BOTTOM = "DOUBLE_BOTTOM"  # Bullish reversal (W shape)
    DOUBLE_TOP = "DOUBLE_TOP"        # Bearish reversal (M shape)
    HEAD_SHOULDERS = "HEAD_SHOULDERS"  # Bearish reversal
    INVERSE_HEAD_SHOULDERS = "INVERSE_HEAD_SHOULDERS"  # Bullish reversal
    
    # Indicator-based patterns
    RSI_OVERBOUGHT = "RSI_OVERBOUGHT"
    RSI_OVERSOLD = "RSI_OVERSOLD"
    MACD_CROSS = "MACD_CROSS"


class TrendDirection(Enum):
    BULLISH = 1
    NEUTRAL = 0
    BEARISH = -1


@dataclass
class PatternResult:
    """Result of pattern detection"""
    pattern_type: PatternType
    detected: bool
    confidence: float = 0.0  # 0.0 to 1.0
    strength: float = 0.0    # How strong the pattern is
    direction: TrendDirection = TrendDirection.NEUTRAL
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConfidenceScore:
    """Detailed confidence breakdown"""
    overall: float  # 0.0 to 1.0
    
    # Components
    volume_score: float = 0.0
    trend_score: float = 0.0
    momentum_score: float = 0.0
    pattern_score: float = 0.0
    rsi_filter_score: float = 0.0
    
    # Multi-timeframe
    htf_confirmed: bool = False
    htf_direction: Optional[TrendDirection] = None
    
    # Details
    rsi_value: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    volume_ratio: float = 1.0


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    symbol: str
    timestamp: datetime
    
    # Signal components
    signal_strength: float  # -10 to +10
    trend: TrendDirection
    confidence: ConfidenceScore
    
    # Pattern results
    patterns: List[PatternResult]
    
    # Raw data for debugging
    price: float
    volume: float
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Technical Indicators (TA-Lib with NumPy Fallback)
# ============================================================================

class TechnicalIndicators:
    """Technical indicators with TA-Lib primary, NumPy fallback"""
    
    @staticmethod
    def compute_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Compute RSI indicator"""
        if TALIB_AVAILABLE:
            return talib.RSI(prices, timeperiod=period)
        
        # NumPy fallback
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.convolve(gains, np.ones(period)/period, mode='valid')
        avg_loss = np.convolve(losses, np.ones(period)/period, mode='valid')
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        # Pad to match input length
        return np.concatenate([np.full(period - 1, np.nan), rsi])
    
    @staticmethod
    def compute_ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Compute EMA"""
        if TALIB_AVAILABLE:
            return talib.EMA(prices, timeperiod=period)
        
        # NumPy fallback (simple EMA)
        ema = np.zeros_like(prices)
        ema[0] = prices[0]
        alpha = 2 / (period + 1)
        
        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    @staticmethod
    def compute_sma(prices: np.ndarray, period: int) -> np.ndarray:
        """Compute SMA"""
        if TALIB_AVAILABLE:
            return talib.SMA(prices, timeperiod=period)
        
        # NumPy fallback
        sma = np.full_like(prices, np.nan)
        for i in range(period - 1, len(prices)):
            sma[i] = np.mean(prices[i - period + 1:i + 1])
        return sma
    
    @staticmethod
    def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Compute ATR (Average True Range)"""
        if TALIB_AVAILABLE:
            return talib.ATR(high, low, close, timeperiod=period)
        
        # NumPy fallback
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        atr = np.full_like(high, np.nan)
        atr[1:period] = np.convolve(tr, np.ones(period)/period, mode='valid')
        return atr
    
    @staticmethod
    def compute_macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute MACD (returns macd, signal, hist)"""
        if TALIB_AVAILABLE:
            macd, signal_line, hist = talib.MACD(prices, fastperiod=fast, slowperiod=slow, signalperiod=signal)
            return macd, signal_line, hist
        
        # NumPy fallback
        ema_fast = TechnicalIndicators.compute_ema(prices, fast)
        ema_slow = TechnicalIndicators.compute_ema(prices, slow)
        macd = ema_fast - ema_slow
        signal_line = TechnicalIndicators.compute_ema(macd, signal)
        hist = macd - signal_line
        return macd, signal_line, hist
    
    @staticmethod
    def compute_candlestick_patterns(
        open_prices: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> Dict[PatternType, np.ndarray]:
        """Detect candlestick patterns using TA-Lib"""
        patterns = {}
        
        if not TALIB_AVAILABLE:
            logger.debug("TA-Lib not available, skipping candlestick patterns")
            return patterns
        
        # Single candle patterns
        patterns[PatternType.HAMMER] = talib.CDLHAMMER(open_prices, high, low, close)
        patterns[PatternType.INVERTED_HAMMER] = talib.CDLINVERTEDHAMMER(open_prices, high, low, close)
        patterns[PatternType.SHOOTING_STAR] = talib.CDLSHOOTINGSTAR(open_prices, high, low, close)
        patterns[PatternType.DOJI] = talib.CDLDOJI(open_prices, high, low, close)
        patterns[PatternType.DRAGONFLY_DOJI] = talib.CDLDRAGONFLYDOJI(open_prices, high, low, close)
        patterns[PatternType.GRAVESTONE_DOJI] = talib.CDLGRAVESTONEDOJI(open_prices, high, low, close)
        
        # Multi-candle patterns
        patterns[PatternType.MORNING_STAR] = talib.CDLMORNINGSTAR(open_prices, high, low, close)
        patterns[PatternType.EVENING_STAR] = talib.CDLEVENINGSTAR(open_prices, high, low, close)
        patterns[PatternType.PIERCING] = talib.CDLPIERCING(open_prices, high, low, close)
        patterns[PatternType.DARK_CLOUD_COVER] = talib.CDLDARKCLOUDCOVER(open_prices, high, low, close)
        
        # Rare patterns
        patterns[PatternType.ISLAND_TOP] = talib.CDLISLANDTOP(open_prices, high, low, close)
        patterns[PatternType.ISLAND_BOTTOM] = talib.CDLISLANDBOTTOM(open_prices, high, low, close)
        patterns[PatternType.ABANDONED_BABY] = talib.CDLABANDONEDBABY(open_prices, high, low, close)
        patterns[PatternType.KICKER_BULLISH] = talib.CDLKICKER(open_prices, high, low, close)  # Bullish
        patterns[PatternType.KICKER_BEARISH] = talib.CDLKICKER(open_prices, high, low, close)  # Bearish (negative)
        
        return patterns


# ============================================================================
# Signal Engine Enhanced
# ============================================================================

class SignalEngineEnhanced:
    """Enhanced signal engine with multi-timeframe and advanced patterns"""
    
    def __init__(
        self,
        enable_talib: bool = True,
        multi_timeframe: bool = True,
        enabled_patterns: Optional[List[str]] = None,
        weights: Optional[ConfidenceWeights] = None,
        # Performance
        cache_size: int = 100,
        # Testing
        synthetic_mode: bool = False,
    ):
        self.enable_talib = enable_talib and TALIB_AVAILABLE
        self.multi_timeframe = multi_timeframe
        self.weights = weights or DEFAULT_WEIGHTS
        
        # Enabled patterns (default: all basic + common advanced)
        self.enabled_patterns = enabled_patterns or [
            "ORB_BREAKOUT", "GAP_UP", "GAP_DOWN", "VOLUME_SPIKE",
            "HAMMER", "DOJI", "MORNING_STAR", "EVENING_STAR",
            "RSI_OVERBOUGHT", "RSI_OVERSOLD", "MACD_CROSS"
        ]
        
        # Cache for indicators (per-symbol)
        self._cache: Dict[str, dict] = {}
        self._cache_size = cache_size
        
        # Testing hooks
        self.synthetic_mode = synthetic_mode
        
        # Metrics
        self._init_metrics()
        
        logger.info(
            f"SignalEngineEnhanced initialized | TA-Lib: {self.enable_talib} | "
            f"Multi-TF: {multi_timeframe} | Patterns: {len(self.enabled_patterns)}"
        )
    
    def _init_metrics(self):
        """Initialize Prometheus metrics"""
        # Pattern detection counters
        self.pattern_counters = {}
    
    def _get_cached(self, symbol: str, key: str) -> Optional[Any]:
        """Get cached indicator value"""
        return self._cache.get(symbol, {}).get(key)
    
    def _set_cached(self, symbol: str, key: str, value: Any):
        """Set cached indicator value"""
        if symbol not in self._cache:
            # Evict oldest if at capacity
            if len(self._cache) >= self._cache_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[symbol] = {}
        self._cache[symbol][key] = value
    
    async def analyze(
        self,
        symbol: str,
        price_data: pd.DataFrame,
        timeframe: str = "1m",
        higher_tf_data: Optional[pd.DataFrame] = None,
    ) -> AnalysisResult:
        """Perform complete signal analysis"""
        symbol = symbol.upper()
        
        # Ensure DataFrame has required columns
        required = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in price_data.columns for col in required):
            raise ValueError(f"DataFrame missing required columns: {required}")
        
        # Extract arrays for faster processing
        close = price_data['close'].values.astype(np.float64)
        open_prices = price_data['open'].values.astype(np.float64)
        high = price_data['high'].values.astype(np.float64)
        low = price_data['low'].values.astype(np.float64)
        volume = price_data['volume'].values.astype(np.float64)
        
        current_price = close[-1]
        current_volume = volume[-1]
        
        # 1. Compute technical indicators
        indicators = self._compute_indicators(symbol, close, high, low, volume)
        
        # 2. Detect patterns
        patterns = self._detect_patterns(
            symbol, open_prices, high, low, close, volume, indicators
        )
        
        # 3. Compute confidence score
        confidence = self._compute_confidence(
            symbol, close, volume, indicators, patterns,
            higher_tf_data, timeframe
        )
        
        # 4. Compute final signal strength
        signal_strength = self._compute_signal_strength(
            confidence, patterns, indicators
        )
        
        # 5. Determine trend
        trend = self._determine_trend(indicators)
        
        # Update metrics
        self._update_metrics(symbol, patterns, confidence, trend, indicators)
        
        return AnalysisResult(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            signal_strength=signal_strength,
            trend=trend,
            confidence=confidence,
            patterns=patterns,
            price=current_price,
            volume=current_volume,
            metadata={
                "timeframe": timeframe,
                "ta_lib_used": self.enable_talib,
                "indicators": indicators,
            }
        )
    
    def _compute_indicators(
        self,
        symbol: str,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray
    ) -> dict:
        """Compute all technical indicators"""
        indicators = {}
        
        # RSI (14-period)
        rsi = TechnicalIndicators.compute_rsi(close, 14)
        indicators['rsi'] = rsi
        indicators['rsi_current'] = rsi[-1] if not np.isnan(rsi[-1]) else 50.0
        
        # EMAs
        ema_9 = TechnicalIndicators.compute_ema(close, 9)
        ema_21 = TechnicalIndicators.compute_ema(close, 21)
        ema_50 = TechnicalIndicators.compute_ema(close, 50) if len(close) >= 50 else ema_21
        
        indicators['ema_9'] = ema_9
        indicators['ema_21'] = ema_21
        indicators['ema_50'] = ema_50
        indicators['ema_9_current'] = ema_9[-1]
        indicators['ema_21_current'] = ema_21[-1]
        
        # MACD
        macd, signal, hist = TechnicalIndicators.compute_macd(close)
        indicators['macd'] = macd
        indicators['macd_signal'] = signal
        indicators['macd_hist'] = hist
        indicators['macd_current'] = macd[-1] if not np.isnan(macd[-1]) else 0.0
        
        # ATR
        atr = TechnicalIndicators.compute_atr(high, low, close, 14)
        indicators['atr'] = atr
        indicators['atr_current'] = atr[-1] if not np.isnan(atr[-1]) else 0.0
        
        # Volume metrics
        avg_volume = np.mean(volume[-20:])  # 20-period average
        volume_ratio = volume[-1] / avg_volume if avg_volume > 0 else 1.0
        indicators['volume_ratio'] = volume_ratio
        indicators['volume_ratio_raw'] = volume_ratio
        
        # Trend strength (EMA alignment)
        if ema_9[-1] > ema_21[-1] > ema_50[-1]:
            indicators['trend_strength'] = 1.0  # Strong uptrend
        elif ema_9[-1] < ema_21[-1] < ema_50[-1]:
            indicators['trend_strength'] = -1.0  # Strong downtrend
        else:
            indicators['trend_strength'] = 0.0  # No clear trend
        
        return indicators
    
    def _detect_patterns(
        self,
        symbol: str,
        open_prices: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
        indicators: dict
    ) -> List[PatternResult]:
        """Detect enabled patterns"""
        patterns = []
        
        # ORB Breakout
        if "ORB_BREAKOUT" in self.enabled_patterns:
            patterns.append(self._detect_orb_breakout(close, volume, indicators))
        
        # Gap patterns
        if "GAP_UP" in self.enabled_patterns:
            patterns.append(self._detect_gap(open_prices, close, "UP"))
        if "GAP_DOWN" in self.enabled_patterns:
            patterns.append(self._detect_gap(open_prices, close, "DOWN"))
        
        # Volume spike
        if "VOLUME_SPIKE" in self.enabled_patterns:
            patterns.append(self._detect_volume_spike(volume, indicators))
        
        # RSI patterns
        if "RSI_OVERBOUGHT" in self.enabled_patterns:
            patterns.append(self._detect_rsi_extreme(indicators, "OVERBOUGHT"))
        if "RSI_OVERSOLD" in self.enabled_patterns:
            patterns.append(self._detect_rsi_extreme(indicators, "OVERSOLD"))
        
        # MACD cross
        if "MACD_CROSS" in self.enabled_patterns:
            patterns.append(self._detect_macd_cross(indicators))
        
        # Complex patterns (scipy-based)
        if any(p in self.enabled_patterns for p in ["DOUBLE_BOTTOM", "DOUBLE_TOP", "HEAD_SHOULDERS", "INVERSE_HEAD_SHOULDERS"]):
            patterns.extend(self._detect_complex_patterns(close, high, low, volume, indicators))
        
        # TA-Lib candlestick patterns
        if self.enable_talib and any(p in self.enabled_patterns for p in [
            "HAMMER", "DOJI", "MORNING_STAR", "EVENING_STAR"
        ]):
            patterns.extend(self._detect_talib_patterns(
                open_prices, high, low, close
            ))
        
        return [p for p in patterns if p.detected]
    
    def _detect_orb_breakout(
        self,
        close: np.ndarray,
        volume: np.ndarray,
        indicators: dict
    ) -> PatternResult:
        """Opening Range Breakout detection"""
        if len(close) < 30:
            return PatternResult(PatternType.ORB_BREAKOUT, False)
        
        # First 15 minutes (or 15 bars) as ORB
        orb_high = np.max(close[:15])
        orb_low = np.min(close[:15])
        current_price = close[-1]
        
        # Breakout above ORB high with volume
        if current_price > orb_high and indicators['volume_ratio'] > 1.5:
            return PatternResult(
                PatternType.ORB_BREAKOUT,
                True,
                confidence=min(1.0, indicators['volume_ratio'] / 3),
                strength=(current_price - orb_high) / orb_high * 100,
                direction=TrendDirection.BULLISH
            )
        
        # Breakdown below ORB low
        if current_price < orb_low and indicators['volume_ratio'] > 1.5:
            return PatternResult(
                PatternType.ORB_BREAKOUT,
                True,
                confidence=min(1.0, indicators['volume_ratio'] / 3),
                strength=(orb_low - current_price) / orb_low * 100,
                direction=TrendDirection.BEARISH
            )
        
        return PatternResult(PatternType.ORB_BREAKOUT, False)
    
    def _detect_gap(
        self,
        open_prices: np.ndarray,
        close: np.ndarray,
        direction: str
    ) -> PatternResult:
        """Gap detection"""
        if len(close) < 2:
            return PatternResult(PatternType.GAP_UP if direction == "UP" else PatternType.GAP_DOWN, False)
        
        prev_close = close[-2]
        current_open = open_prices[-1]
        gap_pct = (current_open - prev_close) / prev_close * 100
        
        if direction == "UP" and gap_pct > 1.0:
            return PatternResult(
                PatternType.GAP_UP, True,
                confidence=min(1.0, gap_pct / 5),
                strength=gap_pct,
                direction=TrendDirection.BULLISH
            )
        elif direction == "DOWN" and gap_pct < -1.0:
            return PatternResult(
                PatternType.GAP_DOWN, True,
                confidence=min(1.0, abs(gap_pct) / 5),
                strength=abs(gap_pct),
                direction=TrendDirection.BEARISH
            )
        
        return PatternResult(
            PatternType.GAP_UP if direction == "UP" else PatternType.GAP_DOWN, False
        )
    
    def _detect_volume_spike(
        self,
        volume: np.ndarray,
        indicators: dict
    ) -> PatternResult:
        """Volume spike detection"""
        vol_ratio = indicators['volume_ratio']
        
        if vol_ratio > 2.0:  # 2x average
            return PatternResult(
                PatternType.VOLUME_SPIKE, True,
                confidence=min(1.0, (vol_ratio - 2) / 3),  # 2x = 0 conf, 5x = 1 conf
                strength=vol_ratio,
                direction=TrendDirection.NEUTRAL
            )
        
        return PatternResult(PatternType.VOLUME_SPIKE, False)
    
    def _detect_rsi_extreme(
        self,
        indicators: dict,
        extreme_type: str
    ) -> PatternResult:
        """RSI overbought/oversold detection"""
        rsi = indicators['rsi_current']
        
        if extreme_type == "OVERBOUGHT" and rsi > 70:
            return PatternResult(
                PatternType.RSI_OVERBOUGHT, True,
                confidence=(rsi - 70) / 30,  # 70 = 0, 100 = 1
                strength=rsi,
                direction=TrendDirection.BEARISH  # Overbought = potential reversal down
            )
        elif extreme_type == "OVERSOLD" and rsi < 30:
            return PatternResult(
                PatternType.RSI_OVERSOLD, True,
                confidence=(30 - rsi) / 30,  # 30 = 0, 0 = 1
                strength=30 - rsi,
                direction=TrendDirection.BULLISH  # Oversold = potential reversal up
            )
        
        return PatternResult(
            PatternType.RSI_OVERBOUGHT if extreme_type == "OVERBOUGHT" else PatternType.RSI_OVERSOLD,
            False
        )
    
    def _detect_macd_cross(
        self,
        indicators: dict
    ) -> PatternResult:
        """MACD zero-line cross detection"""
        macd = indicators['macd_current']
        
        if macd > 0 and indicators['macd'][-2] <= 0:
            return PatternResult(
                PatternType.MACD_CROSS, True,
                confidence=0.7,
                strength=macd,
                direction=TrendDirection.BULLISH
            )
        elif macd < 0 and indicators['macd'][-2] >= 0:
            return PatternResult(
                PatternType.MACD_CROSS, True,
                confidence=0.7,
                strength=abs(macd),
                direction=TrendDirection.BEARISH
            )
        
        return PatternResult(PatternType.MACD_CROSS, False)
    
    def _detect_talib_patterns(
        self,
        open_prices: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray
    ) -> List[PatternResult]:
        """TA-Lib candlestick pattern detection"""
        patterns = []
        
        results = TechnicalIndicators.compute_candlestick_patterns(
            open_prices, high, low, close
        )
        
        # Last value indicates pattern (100 = bullish, -100 = bearish, 0 = none)
        for pattern_type, values in results.items():
            if pattern_type.value not in self.enabled_patterns:
                continue
            
            last_val = values[-1] if len(values) > 0 else 0
            
            if abs(last_val) >= 100:  # Pattern detected
                direction = TrendDirection.BULLISH if last_val > 0 else TrendDirection.BEARISH
                patterns.append(PatternResult(
                    pattern_type, True,
                    confidence=1.0,  # TA-Lib patterns are definitive
                    strength=abs(last_val) / 100,
                    direction=direction
                ))
        
        return patterns
    
    def _detect_complex_patterns(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
        indicators: dict
    ) -> List[PatternResult]:
        """Complex chart patterns using scipy peak detection"""
        patterns = []
        
        # Double Bottom (Bullish reversal)
        db = self._detect_double_bottom(low, volume, indicators)
        if db:
            patterns.append(db)
        
        # Double Top (Bearish reversal)
        dt = self._detect_double_top(high, volume, indicators)
        if dt:
            patterns.append(dt)
        
        # Head and Shoulders
        hs = self._detect_head_shoulders(high, low, indicators)
        if hs:
            patterns.append(hs)
        
        # Inverse Head and Shoulders
        ihs = self._detect_inverse_head_shoulders(high, low, indicators)
        if ihs:
            patterns.append(ihs)
        
        return patterns
    
    def _detect_double_bottom(
        self,
        lows: np.ndarray,
        volume: np.ndarray,
        indicators: dict
    ) -> Optional[PatternResult]:
        """Double Bottom pattern detection (bullish)"""
        if not SCIPY_AVAILABLE or len(lows) < 30:
            return None
        
        # Find troughs (inverse peaks)
        try:
            troughs, _ = find_peaks(-lows, distance=8, prominence=np.std(lows) * 0.3)
        except:
            return None
        
        for i in range(len(troughs) - 1):
            idx1, idx2 = troughs[i], troughs[i + 1]
            
            # Must be within reasonable distance (5-30 bars apart)
            if idx2 - idx1 < 5 or idx2 - idx1 > 30:
                continue
            
            p1, p2 = lows[idx1], lows[idx2]
            avg_price = (p1 + p2) / 2
            
            # bottoms should be within 2% of each other
            if abs(p1 - p2) / avg_price > 0.02:
                continue
            
            # Volume should increase on second bottom
            vol1 = np.mean(volume[max(0, idx1-3):idx1+1])
            vol2 = np.mean(volume[max(0, idx2-3):idx2+1])
            vol_ratio = vol2 / vol1 if vol1 > 0 else 1.0
            
            # RSI should be oversold or improving
            rsi = indicators.get('rsi_current', 50)
            rsi_bonus = 0.1 if rsi < 45 else 0.0
            
            # Calculate confidence
            confidence = 0.65 + min(0.25, (vol_ratio - 1) * 0.15) + rsi_bonus
            confidence = min(0.95, confidence)
            
            # Calculate strength (distance from avg to last price)
            last_price = lows[-1]
            strength = (last_price - avg_price) / avg_price * 100 if last_price > avg_price else 0
            
            return PatternResult(
                PatternType.DOUBLE_BOTTOM, True,
                confidence=confidence,
                strength=strength,
                direction=TrendDirection.BULLISH,
                metadata={"trough1": float(p1), "trough2": float(p2), "vol_ratio": float(vol_ratio)}
            )
        
        return None
    
    def _detect_double_top(
        self,
        highs: np.ndarray,
        volume: np.ndarray,
        indicators: dict
    ) -> Optional[PatternResult]:
        """Double Top pattern detection (bearish)"""
        if not SCIPY_AVAILABLE or len(highs) < 30:
            return None
        
        try:
            peaks, _ = find_peaks(highs, distance=8, prominence=np.std(highs) * 0.3)
        except:
            return None
        
        for i in range(len(peaks) - 1):
            idx1, idx2 = peaks[i], peaks[i + 1]
            
            if idx2 - idx1 < 5 or idx2 - idx1 > 30:
                continue
            
            p1, p2 = highs[idx1], highs[idx2]
            avg_price = (p1 + p2) / 2
            
            if abs(p1 - p2) / avg_price > 0.02:
                continue
            
            # Volume should decrease on second top
            vol1 = np.mean(volume[max(0, idx1-3):idx1+1])
            vol2 = np.mean(volume[max(0, idx2-3):idx2+1])
            vol_ratio = vol2 / vol1 if vol1 > 0 else 1.0
            
            # RSI should be overbought
            rsi = indicators.get('rsi_current', 50)
            rsi_bonus = 0.1 if rsi > 55 else 0.0
            
            confidence = 0.65 + min(0.25, (1 - vol_ratio) * 0.15) + rsi_bonus
            confidence = min(0.95, confidence)
            
            last_price = highs[-1]
            strength = (avg_price - last_price) / avg_price * 100 if last_price < avg_price else 0
            
            return PatternResult(
                PatternType.DOUBLE_TOP, True,
                confidence=confidence,
                strength=strength,
                direction=TrendDirection.BEARISH,
                metadata={"peak1": float(p1), "peak2": float(p2), "vol_ratio": float(vol_ratio)}
            )
        
        return None
    
    def _detect_head_shoulders(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        indicators: dict
    ) -> Optional[PatternResult]:
        """Head and Shoulders pattern detection (bearish reversal)"""
        if not SCIPY_AVAILABLE or len(highs) < 40:
            return None
        
        try:
            peaks, _ = find_peaks(highs, distance=5, prominence=np.std(highs) * 0.4)
        except:
            return None
        
        # Need at least 3 peaks for H&S
        if len(peaks) < 3:
            return None
        
        # Check last 3 peaks for H&S pattern
        for i in range(len(peaks) - 2):
            left_shoulder = highs[peaks[i]]
            head = highs[peaks[i+1]]
            right_shoulder = highs[peaks[i+2]]
            
            # Head should be highest
            if head <= left_shoulder or head <= right_shoulder:
                continue
            
            # Shoulders should be roughly equal (within 3%)
            shoulder_diff = abs(left_shoulder - right_shoulder) / head
            if shoulder_diff > 0.03:
                continue
            
            # Neckline (support from lows between peaks)
            left_neck = np.min(lows[peaks[i]:peaks[i+1]])
            right_neck = np.min(lows[peaks[i+1]:peaks[i+2]])
            neckline = (left_neck + right_neck) / 2
            
            # Price should be breaking below neckline
            if highs[-1] < neckline:
                confidence = 0.7 + (head - left_shoulder) / head * 0.2
                return PatternResult(
                    PatternType.HEAD_SHOULDERS, True,
                    confidence=min(0.95, confidence),
                    strength=(head - neckline) / neckline * 100,
                    direction=TrendDirection.BEARISH,
                    metadata={"head": float(head), "neckline": float(neckline)}
                )
        
        return None
    
    def _detect_inverse_head_shoulders(
        self,
        highs: np.ndarray,
        lows: np.ndarray,
        indicators: dict
    ) -> Optional[PatternResult]:
        """Inverse Head and Shoulders pattern detection (bullish reversal)"""
        if not SCIPY_AVAILABLE or len(lows) < 40:
            return None
        
        try:
            troughs, _ = find_peaks(-lows, distance=5, prominence=np.std(lows) * 0.4)
        except:
            return None
        
        if len(troughs) < 3:
            return None
        
        for i in range(len(troughs) - 2):
            left_shoulder = lows[troughs[i]]
            head = lows[troughs[i+1]]
            right_shoulder = lows[troughs[i+2]]
            
            # Head should be lowest
            if head >= left_shoulder or head >= right_shoulder:
                continue
            
            shoulder_diff = abs(left_shoulder - right_shoulder) / head
            if shoulder_diff > 0.03:
                continue
            
            # Neckline (resistance from highs between troughs)
            left_neck = np.max(highs[troughs[i]:troughs[i+1]])
            right_neck = np.max(highs[troughs[i+1]:troughs[i+2]])
            neckline = (left_neck + right_neck) / 2
            
            # Price should be breaking above neckline
            if lows[-1] > neckline:
                confidence = 0.7 + (left_shoulder - head) / head * 0.2
                return PatternResult(
                    PatternType.INVERSE_HEAD_SHOULDERS, True,
                    confidence=min(0.95, confidence),
                    strength=(neckline - head) / head * 100,
                    direction=TrendDirection.BULLISH,
                    metadata={"head": float(head), "neckline": float(neckline)}
                )
        
        return None
    
    def _detect_island_reversal(
        self,
        open_prices: np.ndarray,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray
    ) -> Optional[PatternResult]:
        """Island Reversal pattern detection"""
        if len(close) < 10:
            return None
        
        # Look for gap down then gap up (Island Bottom)
        # Or gap up then gap down (Island Top)
        
        for i in range(2, len(close) - 2):
            # Island Bottom: gap down, then gap up
            gap_down_1 = close[i-1] - low[i] > (high[i-1] - low[i-1]) * 0.5  # Gap down
            gap_up_1 = high[i+2] - close[i+1] > (high[i+1] - low[i+1]) * 0.5  # Gap up
            
            if gap_down_1 and gap_up_1:
                # Calculate isolation (gap size)
                isolation = (high[i+2] - low[i]) / low[i] * 100
                return PatternResult(
                    PatternType.ISLAND_BOTTOM, True,
                    confidence=min(0.9, 0.5 + isolation / 100),
                    strength=isolation,
                    direction=TrendDirection.BULLISH
                )
            
            # Island Top: gap up, then gap down
            gap_up_2 = high[i] - close[i-1] > (high[i-1] - low[i-1]) * 0.5
            gap_down_2 = close[i+1] - low[i+2] > (high[i+1] - low[i+1]) * 0.5
            
            if gap_up_2 and gap_down_2:
                isolation = (high[i] - low[i+2]) / high[i] * 100
                return PatternResult(
                    PatternType.ISLAND_TOP, True,
                    confidence=min(0.9, 0.5 + isolation / 100),
                    strength=isolation,
                    direction=TrendDirection.BEARISH
                )
        
        return None
    
    def _compute_confidence(
        self,
        symbol: str,
        close: np.ndarray,
        volume: np.ndarray,
        indicators: dict,
        patterns: List[PatternResult],
        higher_tf_data: Optional[pd.DataFrame],
        timeframe: str
    ) -> ConfidenceScore:
        """Compute weighted confidence score"""
        w = self.weights
        
        # 1. Volume score
        vol_ratio = indicators.get('volume_ratio', 1.0)
        volume_score = min(1.0, vol_ratio / 3) if vol_ratio >= 1 else vol_ratio / 3
        
        # 2. Trend score (EMA alignment)
        trend_strength = indicators.get('trend_strength', 0)
        trend_score = abs(trend_strength)
        
        # 3. Momentum score (MACD)
        macd_hist = indicators.get('macd_hist', np.array([0]))[-1]
        momentum_score = min(1.0, abs(macd_hist) / (indicators.get('atr_current', 1) * 2))
        
        # 4. Pattern score
        if patterns:
            pattern_score = max(p.confidence for p in patterns)
        else:
            pattern_score = 0.0
        
        # 5. RSI filter
        rsi = indicators.get('rsi_current', 50)
        if 30 <= rsi <= 70:
            rsi_filter_score = 1.0  # Neutral zone - no filter applied
        elif rsi < 30 or rsi > 70:
            rsi_filter_score = 0.5  # Extreme - might be reversal
        
        # Combine
        overall = (
            volume_score * w.volume_weight +
            trend_score * w.trend_weight +
            momentum_score * w.momentum_weight +
            pattern_score * w.pattern_weight +
            rsi_filter_score * w.rsi_filter_weight
        )
        
        # Multi-timeframe confirmation
        htf_confirmed = False
        htf_direction = None
        
        if self.multi_timeframe and higher_tf_data is not None:
            htf_confirmed, htf_direction = self._check_htf_confirmation(
                higher_tf_data, patterns
            )
            if htf_confirmed:
                overall = min(1.0, overall + w.htf_confirm_bonus)
            elif htf_direction is not None:
                overall = max(0, overall - w.htf_conflict_penalty)
        
        return ConfidenceScore(
            overall=overall,
            volume_score=volume_score,
            trend_score=trend_score,
            momentum_score=momentum_score,
            pattern_score=pattern_score,
            rsi_filter_score=rsi_filter_score,
            rsi_value=rsi,
            ema_9=indicators.get('ema_9_current'),
            ema_21=indicators.get('ema_21_current'),
            volume_ratio=vol_ratio,
            htf_confirmed=htf_confirmed,
            htf_direction=htf_direction
        )
    
    def _check_htf_confirmation(
        self,
        htf_data: pd.DataFrame,
        patterns: List[PatternResult]
    ) -> Tuple[bool, Optional[TrendDirection]]:
        """Check higher timeframe confirmation"""
        if htf_data is None or len(htf_data) < 20:
            return False, None
        
        # Get HTF trend from EMAs
        htf_close = htf_data['close'].values
        htf_ema_9 = TechnicalIndicators.compute_ema(htf_close, 9)
        htf_ema_21 = TechnicalIndicators.compute_ema(htf_close, 21)
        
        htf_bullish = htf_ema_9[-1] > htf_ema_21[-1]
        htf_direction = TrendDirection.BULLISH if htf_bullish else TrendDirection.BEARISH
        
        # Check if current patterns align with HTF direction
        for p in patterns:
            if p.direction == htf_direction:
                return True, htf_direction
        
        # No alignment found
        return False, htf_direction
    
    def _compute_signal_strength(
        self,
        confidence: ConfidenceScore,
        patterns: List[PatternResult],
        indicators: dict
    ) -> float:
        """Compute final signal strength (-10 to +10)"""
        # Base from confidence
        strength = (confidence.overall - 0.5) * 20  # Map 0-1 to -10 to +10
        
        # Pattern adjustments
        for p in patterns:
            if p.detected and p.direction == TrendDirection.BULLISH:
                strength += p.confidence * 2
            elif p.detected and p.direction == TrendDirection.BEARISH:
                strength -= p.confidence * 2
        
        # Trend alignment
        trend_strength = indicators.get('trend_strength', 0)
        if trend_strength > 0:
            strength += 1
        elif trend_strength < 0:
            strength -= 1
        
        # RSI filter - if overbought, reduce bullish signal
        if confidence.rsi_value and confidence.rsi_value > 75:
            strength = min(strength, 2)  # Cap bullish
        
        # Clamp
        return max(-10, min(10, strength))
    
    def _determine_trend(self, indicators: dict) -> TrendDirection:
        """Determine trend direction"""
        trend_strength = indicators.get('trend_strength', 0)
        
        if trend_strength > 0.5:
            return TrendDirection.BULLISH
        elif trend_strength < -0.5:
            return TrendDirection.BEARISH
        return TrendDirection.NEUTRAL
    
    def _update_metrics(
        self,
        symbol: str,
        patterns: List[PatternResult],
        confidence: ConfidenceScore,
        trend: TrendDirection,
        indicators: Optional[dict] = None
    ):
        """Update Prometheus metrics"""
        # Core metrics
        edge_signal_strength.labels(symbol=symbol).set(confidence.overall * 10 - 5)
        edge_trend_direction.labels(symbol=symbol).set(trend.value)
        edge_volume_ratio.labels(symbol=symbol).set(confidence.volume_ratio)
        edge_confidence_score.labels(symbol=symbol).set(confidence.overall)
        edge_signal_quality.labels(symbol=symbol).set(
            confidence.overall * confidence.volume_ratio * confidence.trend_score * 10
        )
        
        # Pattern detection metrics
        active_patterns = []
        for p in patterns:
            if p.detected:
                # Total detections
                edge_pattern_detected.labels(
                    symbol=symbol,
                    pattern=p.pattern_type.value,
                    direction=p.direction.value,
                    timeframe=self.default_timeframe
                ).inc()
                
                # Pattern confidence
                edge_pattern_confidence.labels(
                    symbol=symbol,
                    pattern=p.pattern_type.value,
                    timeframe=self.default_timeframe
                ).set(p.confidence)
                
                # Pattern active
                edge_pattern_active.labels(
                    symbol=symbol,
                    pattern=p.pattern_type.value,
                    timeframe=self.default_timeframe
                ).set(1)
                
                active_patterns.append(p.pattern_type.value)
        
        # Set inactive for patterns not detected
        all_patterns = [p.value for p in PatternType] if hasattr(PatternType, '__members__') else []
        for pat in all_patterns:
            if pat not in active_patterns:
                edge_pattern_active.labels(
                    symbol=symbol,
                    pattern=pat,
                    timeframe=self.default_timeframe
                ).set(0)
        
        # RSI metrics
        if indicators:
            rsi = indicators.get('rsi_current', 50)
            if rsi < 30:
                edge_rsi_oversold_total.labels(symbol=symbol).inc()
            elif rsi > 70:
                edge_rsi_overbought_total.labels(symbol=symbol).inc()
            
            # MACD crossover
            macd_hist = indicators.get('macd_hist', np.array([0]))
            if len(macd_hist) > 1:
                prev_hist = macd_hist[-2]
                curr_hist = macd_hist[-1]
                if prev_hist < 0 and curr_hist > 0:
                    edge_macd_crossover_total.labels(
                        symbol=symbol, direction="bullish"
                    ).inc()
                elif prev_hist > 0 and curr_hist < 0:
                    edge_macd_crossover_total.labels(
                        symbol=symbol, direction="bearish"
                    ).inc()
            
            # Support/Resistance
            support = indicators.get('support_level')
            resistance = indicators.get('resistance_level')
            if support:
                edge_support_level.labels(
                    symbol=symbol, timeframe=self.default_timeframe
                ).set(support)
            if resistance:
                edge_resistance_level.labels(
                    symbol=symbol, timeframe=self.default_timeframe
                ).set(resistance)
            
            # Sentinel Echo
            sentinel_echo = indicators.get('sentinel-echo', False)
            edge_sentinel_echo_detected.labels(
                symbol=symbol, timeframe=self.default_timeframe
            ).set(1 if sentinel_echo else 0)
            
            # Volatility surge
            volatility_pct = indicators.get('volatility_percentile', 0)
            if volatility_pct > 80:
                edge_volatility_surge.labels(symbol=symbol).inc()
        
        # Multi-timeframe alignment (placeholder - would be computed with HTF data)
        edge_multi_timeframe_alignment.labels(symbol=symbol).set(0)


# ============================================================================
# Testing Hooks - Synthetic Data Generator
# ============================================================================

class SyntheticDataGenerator:
    """Generate synthetic OHLCV data for testing"""
    
    @staticmethod
    def generate_ohlcv(
        n_bars: int = 100,
        start_price: float = 100.0,
        volatility: float = 0.02,
        trend: float = 0.0,
        volume_base: float = 1_000_000
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data
        
        Args:
            n_bars: Number of bars to generate
            start_price: Starting price
            volatility: Daily volatility (0.02 = 2%)
            trend: Trend bias (positive = up, negative = down)
            volume_base: Base volume
        """
        np.random.seed(42)  # Reproducible
        
        # Generate returns with trend and volatility
        returns = np.random.normal(trend / n_bars, volatility, n_bars)
        
        # Calculate prices
        prices = start_price * np.cumprod(1 + returns)
        
        # Generate OHLC (realistic spread)
        spread = prices * volatility * 0.5
        open_prices = prices + np.random.uniform(-spread * 0.5, spread * 0.5, n_bars)
        high = np.maximum(prices, open_prices) + np.random.uniform(0, spread, n_bars)
        low = np.minimum(prices, open_prices) - np.random.uniform(0, spread, n_bars)
        close = prices
        
        # Generate volume (with occasional spikes)
        base_vol = volume_base
        volume = np.random.lognormal(0, 0.5, n_bars) * base_vol
        
        # Occasional volume spikes (5% chance)
        spike_mask = np.random.random(n_bars) < 0.05
        volume[spike_mask] *= np.random.uniform(3, 10, spike_mask.sum())
        
        df = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=n_bars, freq='1min'),
            'open': open_prices,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume.astype(int)
        })
        
        return df
    
    @staticmethod
    def generate_pattern(
        pattern_type: str,
        base_price: float = 100.0
    ) -> pd.DataFrame:
        """Generate synthetic data with specific pattern"""
        
        if pattern_type == "ORB_BREAKOUT":
            # First 15 bars flat, then breakout
            prices = np.concatenate([
                np.linspace(base_price, base_price, 15),
                np.linspace(base_price, base_price * 1.03, 10),
                np.linspace(base_price * 1.03, base_price * 1.05, 5)
            ])
            volume = np.concatenate([
                np.full(15, 100000),
                np.full(10, 200000),
                np.full(5, 500000)
            ])
        
        elif pattern_type == "HAMMER":
            # Hammer pattern at bottom
            prices = np.array([
                base_price * 0.98,
                base_price * 0.97,
                base_price * 0.95,  # Low
                base_price * 0.97,
                base_price * 0.99   # Close
            ])
            volume = np.array([100000, 100000, 300000, 100000, 100000])
        
        elif pattern_type == "GAP_UP":
            # Gap up pattern
            prices = np.array([
                base_price,
                base_price * 1.02  # Gap
            ] * 10)[:20]
            volume = np.array([100000, 300000] * 10)
        
        else:
            # Default random
            return SyntheticDataGenerator.generate_ohlcv(50, base_price)
        
        # Create DataFrame
        n = len(prices)
        return pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01', periods=n, freq='1min'),
            'open': prices,
            'high': prices * 1.005,
            'low': prices * 0.995,
            'close': prices,
            'volume': volume
        })


# ============================================================================
# Module-level helpers
# ============================================================================

# Singleton instance
_signal_engine: Optional[SignalEngineEnhanced] = None


def get_signal_engine(
    enable_talib: bool = True,
    multi_timeframe: bool = True,
    **kwargs
) -> SignalEngineEnhanced:
    """Get or create signal engine singleton"""
    global _signal_engine
    
    if _signal_engine is None:
        _signal_engine = SignalEngineEnhanced(
            enable_talib=enable_talib,
            multi_timeframe=multi_timeframe,
            **kwargs
        )
    
    return _signal_engine
