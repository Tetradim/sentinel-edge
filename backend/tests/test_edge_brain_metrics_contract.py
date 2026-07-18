import numpy as np

import metrics as edge_metrics


REQUIRED_ENHANCED_METRICS = {
    "edge_pattern_detected",
    "edge_pattern_confidence",
    "edge_pattern_active",
    "edge_multi_timeframe_alignment",
    "edge_rsi_oversold_total",
    "edge_rsi_overbought_total",
    "edge_macd_crossover_total",
    "edge_support_level",
    "edge_resistance_level",
    "edge_sentinel_echo_detected",
    "edge_volatility_surge",
    "edge_confidence_score",
    "edge_signal_quality",
}


def test_enhanced_analysis_metrics_are_importable():
    missing = sorted(name for name in REQUIRED_ENHANCED_METRICS if not hasattr(edge_metrics, name))
    assert missing == []


def test_production_hook_installs_edge_brain_runtime():
    import edge_brain_patch  # noqa: F401
    from scheduler import EvaluationScheduler
    from signals_enhanced import TechnicalIndicators

    assert EvaluationScheduler._edge_brain_patch_installed is True
    assert TechnicalIndicators.compute_atr.__name__ == "safe_compute_atr"
    assert TechnicalIndicators.compute_rsi.__name__ == "safe_compute_rsi"


def test_rsi_fallback_preserves_input_length():
    from edge_brain_indicators import safe_compute_rsi

    prices = np.linspace(100.0, 112.0, 32)
    rsi = safe_compute_rsi(prices, period=14)

    assert len(rsi) == len(prices)
    assert np.isfinite(rsi[-1])
    assert 0.0 <= rsi[-1] <= 100.0
