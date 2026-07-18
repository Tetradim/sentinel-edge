"""Expose every Prometheus collector required by the enhanced analyzer."""
from __future__ import annotations

from typing import Callable

from prometheus_client import Counter, Gauge, REGISTRY

import metrics as edge_metrics


def _registered_collector(metric_name: str):
    """Return a collector already registered under *metric_name*, if any."""
    registry_map = getattr(REGISTRY, "_names_to_collectors", {})
    collector = registry_map.get(metric_name)
    if collector is not None:
        return collector
    if metric_name.endswith("_total"):
        return registry_map.get(metric_name[:-6])
    return None


def _install(name: str, metric_name: str, factory: Callable[[], object]) -> None:
    """Attach an existing collector or create it only when truly absent."""
    if hasattr(edge_metrics, name):
        return
    collector = _registered_collector(metric_name)
    if collector is None:
        collector = factory()
    setattr(edge_metrics, name, collector)


_install(
    "edge_pattern_detected",
    "edge_pattern_detected_total",
    lambda: Counter(
        "edge_pattern_detected_total",
        "Total enhanced chart patterns detected",
        ["symbol", "pattern", "direction", "timeframe"],
    ),
)
_install(
    "edge_pattern_confidence",
    "edge_pattern_confidence",
    lambda: Gauge(
        "edge_pattern_confidence",
        "Confidence of the latest enhanced chart pattern",
        ["symbol", "pattern", "timeframe"],
    ),
)
_install(
    "edge_pattern_active",
    "edge_pattern_active",
    lambda: Gauge(
        "edge_pattern_active",
        "Whether an enhanced chart pattern is currently active",
        ["symbol", "pattern", "timeframe"],
    ),
)
_install(
    "edge_multi_timeframe_alignment",
    "edge_multi_timeframe_alignment",
    lambda: Gauge(
        "edge_multi_timeframe_alignment",
        "Directional alignment across analyzed timeframes from -1 to 1",
        ["symbol"],
    ),
)
_install(
    "edge_rsi_oversold_total",
    "edge_rsi_oversold_total",
    lambda: Counter("edge_rsi_oversold_total", "Total RSI oversold observations", ["symbol"]),
)
_install(
    "edge_rsi_overbought_total",
    "edge_rsi_overbought_total",
    lambda: Counter("edge_rsi_overbought_total", "Total RSI overbought observations", ["symbol"]),
)
_install(
    "edge_macd_crossover_total",
    "edge_macd_crossover_total",
    lambda: Counter(
        "edge_macd_crossover_total",
        "Total MACD histogram crossovers",
        ["symbol", "direction"],
    ),
)
_install(
    "edge_support_level",
    "edge_support_level",
    lambda: Gauge(
        "edge_support_level",
        "Latest calculated support level",
        ["symbol", "timeframe"],
    ),
)
_install(
    "edge_resistance_level",
    "edge_resistance_level",
    lambda: Gauge(
        "edge_resistance_level",
        "Latest calculated resistance level",
        ["symbol", "timeframe"],
    ),
)
_install(
    "edge_sentinel_echo_detected",
    "edge_sentinel_echo_detected",
    lambda: Gauge(
        "edge_sentinel_echo_detected",
        "Whether Sentinel Echo divergence is currently detected",
        ["symbol", "timeframe"],
    ),
)
_install(
    "edge_volatility_surge",
    "edge_volatility_surge_total",
    lambda: Counter(
        "edge_volatility_surge_total",
        "Total volatility surge detections",
        ["symbol"],
    ),
)
_install(
    "edge_confidence_score",
    "edge_confidence_score",
    lambda: Gauge(
        "edge_confidence_score",
        "Latest enhanced Edge confidence score",
        ["symbol"],
    ),
)
_install(
    "edge_signal_quality",
    "edge_signal_quality",
    lambda: Gauge(
        "edge_signal_quality",
        "Latest enhanced Edge signal quality score",
        ["symbol"],
    ),
)
