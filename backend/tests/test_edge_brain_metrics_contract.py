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
