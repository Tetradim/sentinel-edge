"""Numerically stable indicator fallbacks used by the Edge strategist brain."""
from __future__ import annotations

import numpy as np


def safe_compute_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Return Wilder RSI with exactly one output for every input candle."""
    prices = np.asarray(prices, dtype=float)
    result = np.full(len(prices), np.nan, dtype=float)
    if len(prices) <= period or period <= 0:
        return result

    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    average_gain = float(np.mean(gains[:period]))
    average_loss = float(np.mean(losses[:period]))

    def _rsi(gain: float, loss: float) -> float:
        if loss <= 1e-12:
            return 100.0 if gain > 0 else 50.0
        relative_strength = gain / loss
        return 100.0 - (100.0 / (1.0 + relative_strength))

    result[period] = _rsi(average_gain, average_loss)
    for index in range(period + 1, len(prices)):
        average_gain = ((average_gain * (period - 1)) + gains[index - 1]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index - 1]) / period
        result[index] = _rsi(average_gain, average_loss)

    return result
