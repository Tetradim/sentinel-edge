"""Prometheus Metrics Definitions for Sentinel Edge"""
from prometheus_client import Counter, Gauge, Histogram, Info, Enum

# ═══════════════════════════════════════════════════════════
# Core health metrics (required for alerts)
# ═══════════════════════════════════════════════════════════

# Bot up/down status (standard prometheus up metric)
# Will be set by the health check endpoint

# Last tick timestamp for staleness detection
sentinel_last_tick = Gauge(
    "sentinel_last_tick",
    "Unix timestamp of last tick for staleness detection",
    ["symbol"]
)

# Portfolio-level drawdown (not per-ticker)
sentinel_drawdown_pct = Gauge(
    "sentinel_drawdown_pct",
    "Current portfolio drawdown as percentage (negative = loss from peak)",
)

# ═══════════════════════════════════════════════════════════
# ORB METRICS
# ═══════════════════════════════════════════════════════════════════

edge_orb_breakouts_total = Counter(
    "edge_orb_breakouts_total",
    "Total ORB breakouts detected",
    ["symbol", "direction", "timeframe"]
)

edge_orb_high = Gauge(
    "edge_orb_high",
    "ORB high level for symbol",
    ["symbol", "timeframe"]
)

edge_orb_low = Gauge(
    "edge_orb_low",
    "ORB low level for symbol",
    ["symbol", "timeframe"]
)

edge_orb_range_width = Gauge(
    "edge_orb_range_width",
    "ORB range width (high - low)",
    ["symbol", "timeframe"]
)

# ═══════════════════════════════════════════════════════════
# SIGNAL METRICS
# ═══════════════════════════════════════════════════════════

edge_signal_strength = Gauge(
    "edge_signal_strength",
    "Bullish/Bearish strength score (-10 to +10)",
    ["symbol"]
)

edge_trend_direction = Gauge(
    "edge_trend_direction",
    "Trend direction: 1=bullish, -1=bearish, 0=neutral",
    ["symbol"]
)

edge_volume_ratio = Gauge(
    "edge_volume_ratio",
    "Current volume vs average volume ratio",
    ["symbol"]
)

edge_atr_value = Gauge(
    "edge_atr_value",
    "Average True Range (ATR) value",
    ["symbol", "period"]
)

edge_volatility_percentile = Gauge(
    "edge_volatility_percentile",
    "Volatility percentile (0-100)",
    ["symbol"]
)

# ═══════════════════════════════════════════════════════════
# DECISION METRICS
# ═══════════════════════════════════════════════════════════

edge_decision_total = Counter(
    "edge_decision_total",
    "Total decisions made by type",
    ["symbol", "decision"]
)

edge_automation_handoffs_total = Counter(
    "edge_automation_handoffs_total",
    "Autonomous Edge to Pulse handoff outcomes by bounded action, mode, result, and reason",
    ["action", "mode", "result", "reason"],
)

edge_active_positions = Gauge(
    "edge_active_positions",
    "Number of active positions",
    ["symbol"]
)

edge_consecutive_losses = Gauge(
    "edge_consecutive_losses",
    "Consecutive loss streak per ticker",
    ["symbol"]
)

edge_win_rate = Gauge(
    "edge_win_rate",
    "Win rate percentage per ticker",
    ["symbol"]
)

# ═══════════════════════════════════════════════════════════
# PULSE API METRICS
# ═══════════════════════════════════════════════════════════

edge_api_calls_total = Counter(
    "edge_api_calls_total",
    "Total API calls to Pulse",
    ["endpoint", "status"]
)

edge_api_latency = Histogram(
    "edge_api_latency_seconds",
    "API call latency to Pulse",
    ["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

broker_circuit_state = Gauge(
    "broker_circuit_state",
    "Circuit breaker state: 0=CLOSED, 1=HALF_OPEN, 2=OPEN",
    ["broker_id"]
)

broker_failure_rate = Gauge(
    "broker_failure_rate",
    "API failure rate percentage",
    ["broker_id"]
)

# ═══════════════════════════════════════════════════════════
# P&L METRICS
# ═══════════════════════════════════════════════════════════

ticker_realized_pnl_total = Gauge(
    "ticker_realized_pnl_total",
    "Realized P&L per ticker",
    ["symbol"]
)

ticker_unrealized_pnl = Gauge(
    "ticker_unrealized_pnl",
    "Unrealized P&L per ticker",
    ["symbol"]
)

ticker_drawdown_percent = Gauge(
    "ticker_drawdown_percent",
    "Current drawdown percentage from peak",
    ["symbol"]
)

ticker_max_drawdown_percent = Gauge(
    "ticker_max_drawdown_percent",
    "Maximum drawdown percentage",
    ["symbol"]
)

total_portfolio_value = Gauge(
    "total_portfolio_value",
    "Total portfolio value"
)

# ═══════════════════════════════════════════════════════════
# ENGINE METRICS
# ═══════════════════════════════════════════════════════════

edge_eval_duration = Histogram(
    "edge_eval_duration_seconds",
    "Evaluation duration per ticker",
    ["symbol"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

edge_engine_running = Gauge(
    "edge_engine_running",
    "Engine running status: 0=stopped, 1=running"
)

edge_engine_paused = Gauge(
    "edge_engine_paused",
    "Engine paused status: 0=active, 1=paused"
)

edge_readiness_status = Gauge(
    "edge_readiness_status",
    "Sentinel Edge readiness status: 0=not ready, 1=ready",
)

edge_readiness_check_status = Gauge(
    "edge_readiness_check_status",
    "Sentinel Edge readiness check status: 0=failed, 1=passed",
    ["check"],
)

edge_rate_limit_rejections_total = Counter(
    "edge_rate_limit_rejections_total",
    "API requests rejected by the Edge in-memory rate limiter",
    ["scope"],
)

edge_rate_limit_tracked_clients = Gauge(
    "edge_rate_limit_tracked_clients",
    "Current number of client buckets tracked by the Edge in-memory rate limiter",
)

edge_rate_limit_pruned_clients_total = Counter(
    "edge_rate_limit_pruned_clients_total",
    "Total stale client buckets pruned from the Edge in-memory rate limiter",
)

ticker_evaluation_total = Counter(
    "ticker_evaluation_total",
    "Total ticker evaluations",
    ["symbol"]
)

ticker_active_count = Gauge(
    "ticker_active_count",
    "Number of active tickers being tracked"
)

# ═══════════════════════════════════════════════════════════
# PRICE FEED METRICS
# ═══════════════════════════════════════════════════════════

price_fetch_latency = Histogram(
    "price_fetch_latency_seconds",
    "Price data fetch latency",
    ["source"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

price_fetch_failures_total = Counter(
    "price_fetch_failures_total",
    "Total price fetch failures",
    ["symbol", "source"]
)

current_price = Gauge(
    "current_price",
    "Current price per ticker",
    ["symbol"]
)

# ═══════════════════════════════════════════════════════════
# MARKET COVERAGE METRICS
# ═══════════════════════════════════════════════════════════

market_open_status = Gauge(
    "market_open_status",
    "Market open status: 0=closed, 1=open",
    ["market"]
)

market_lunch_break = Gauge(
    "market_lunch_break",
    "Market in lunch break: 0=no, 1=yes",
    ["market"]
)

market_minutes_to_close = Gauge(
    "market_minutes_to_close",
    "Minutes remaining until market close",
    ["market"]
)

# ═══════════════════════════════════════════════════════════
# CORRELATION METRICS
# ═══════════════════════════════════════════════════════════

correlation_clusters_total = Counter(
    "analyst_correlation_clusters_total",
    "Detected correlation clusters",
    ["direction", "strength"]
)

# ── Volume anomaly metrics ──────────────────────────────────────────────────

edge_volume_zscore = Gauge(
    "edge_volume_zscore",
    "Volume Z-score — standard deviations above/below rolling mean",
    ["symbol"],
)

analyst_plugin_signals_total = Counter(
    "analyst_plugin_signals_total",
    "Signals generated by analyst BaseSignal plugins",
    ["plugin", "symbol", "action"],
)

# Frontend real-user monitoring metrics.
edge_frontend_rum_samples_total = Counter(
    "edge_frontend_rum_samples_total",
    "Frontend real-user monitoring snapshots received by the Edge API",
    ["route"],
)

edge_frontend_rum_last_received_timestamp_seconds = Gauge(
    "edge_frontend_rum_last_received_timestamp_seconds",
    "Unix timestamp of the latest frontend RUM snapshot accepted by the Edge API",
)

edge_frontend_rum_active_routes = Gauge(
    "edge_frontend_rum_active_routes",
    "Number of normalized frontend routes tracked in the Edge RUM status registry",
)

edge_frontend_rum_dropped_metrics_total = Counter(
    "edge_frontend_rum_dropped_metrics_total",
    "Frontend RUM metric samples dropped before Prometheus export",
    ["reason"],
)

edge_frontend_web_vital_value = Gauge(
    "edge_frontend_web_vital_value",
    "Latest frontend Web Vital value reported by the Edge UI",
    ["route", "metric", "rating"],
)

edge_frontend_slow_interaction_duration_ms = Histogram(
    "edge_frontend_slow_interaction_duration_ms",
    "Slow frontend interaction duration reported by the Edge UI",
    ["route", "type"],
    buckets=[50, 100, 200, 500, 1000, 2500, 5000],
)

edge_frontend_long_task_duration_ms = Histogram(
    "edge_frontend_long_task_duration_ms",
    "Frontend long task duration reported by the Edge UI",
    ["route"],
    buckets=[50, 100, 200, 500, 1000, 2500, 5000],
)

# ═══════════════════════════════════════════════════════════
# SYSTEM INFO
# ═══════════════════════════════════════════════════════════

edge_info = Info(
    "edge_info",
    "Sentinel Edge system information"
)

# Initialize system info
edge_info.info({
    'version': '1.0.0',
    'name': 'Sentinel Edge',
    'description': 'Trading analyst sidecar for Sentinel Pulse'
})

# ═══════════════════════════════════════════════════════════
# PRODUCTION SAFEGUARDS METRICS
# ═══════════════════════════════════════════════════════════

global_kill_switch = Gauge(
    "edge_kill_switch_active",
    "Global kill switch status: 0=OFF, 1=ON",
)

daily_loss_limit_triggered = Gauge(
    "edge_daily_loss_limit_triggered",
    "Daily loss limit triggered: 0=OK, 1=TRIGGERED",
)

circuit_breaker_state = Gauge(
    "edge_circuit_breaker_state",
    "Circuit breaker per provider: 0=CLOSED, 1=HALF_OPEN, 2=OPEN",
    ["provider"]
)

circuit_breaker_failures = Counter(
    "edge_circuit_breaker_failures_total",
    "Total circuit breaker failures",
    ["provider"]
)

# ═══════════════════════════════════════════════════════════
# PROVIDER HEALTH METRICS
# ═══════════════════════════════════════════════════════════

provider_health_status = Gauge(
    "edge_provider_health_status",
    "Provider health status: 0=UNKNOWN, 1=HEALTHY, 2=DEGRADED, 3=FAILED",
    ["provider"]
)

provider_latency_ms = Gauge(
    "edge_provider_latency_ms",
    "Provider latency in milliseconds",
    ["provider"]
)

provider_requests_total = Counter(
    "edge_provider_requests_total",
    "Total requests to provider",
    ["provider", "status"]
)

# ═══════════════════════════════════════════════════════════
# RETRY QUEUE METRICS
# ═══════════════════════════════════════════════════════════

retry_queue_depth = Gauge(
    "edge_retry_queue_depth",
    "Current depth of retry queue",
    ["priority"]
)

retry_queue_processed = Counter(
    "edge_retry_queue_processed_total",
    "Total items processed from retry queue",
    ["priority", "result"]
)

retry_queue_age_seconds = Gauge(
    "edge_retry_queue_age_seconds",
    "Age of oldest item in retry queue",
    ["priority"]
)

# ═══════════════════════════════════════════════════════════
# BACKTEST METRICS
# ═══════════════════════════════════════════════════════════

backtest_runs_total = Counter(
    "edge_backtest_runs_total",
    "Total backtest runs",
    ["symbol"]
)

backtest_duration_seconds = Histogram(
    "edge_backtest_duration_seconds",
    "Backtest execution duration",
    ["symbol"],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

backtest_return_pct = Gauge(
    "edge_backtest_return_pct",
    "Backtest return percentage",
    ["symbol"]
)

monte_carlo_probability_profit = Gauge(
    "edge_monte_carlo_probability_profit",
    "Monte Carlo probability of profit",
    ["symbol"]
)

monte_carlo_profit_prob = Gauge(
    "edge_monte_carlo_profit_prob",
    "Monte Carlo probability of profit as a ratio",
    ["symbol"]
)

monte_carlo_var_5pct = Gauge(
    "edge_monte_carlo_var_5pct",
    "Monte Carlo value at risk at the configured lower tail, as a loss ratio",
    ["symbol"]
)

monte_carlo_expected_shortfall = Gauge(
    "edge_monte_carlo_expected_shortfall",
    "Monte Carlo expected shortfall at the configured lower tail, as a loss ratio",
    ["symbol"]
)

monte_carlo_median_equity = Gauge(
    "edge_monte_carlo_median_equity",
    "Monte Carlo median final equity",
    ["symbol"]
)

monte_carlo_mean_drawdown = Gauge(
    "edge_monte_carlo_mean_drawdown",
    "Monte Carlo mean max drawdown as a ratio",
    ["symbol"]
)

monte_carlo_ruin_prob = Gauge(
    "edge_monte_carlo_ruin_prob",
    "Monte Carlo probability of reaching the configured ruin threshold as a ratio",
    ["symbol"]
)

# ═══════════════════════════════════════════════════════════
# STRATEGY OPTIMIZATION METRICS
# ═══════════════════════════════════════════════════════════

optimization_runs_total = Counter(
    "edge_optimization_runs_total",
    "Total optimization runs",
    ["symbol"]
)

optimization_best_score = Gauge(
    "edge_optimization_best_score",
    "Best optimization score",
    ["symbol"]
)

strategy_versions_total = Gauge(
    "edge_strategy_versions_total",
    "Total strategy versions stored",
    ["strategy"]
)

# ═════════════════════════════════════════════════════════════════════
# PATTERN RECOGNITION METRICS
# ═════════════════════════════════════════════════════════════════════

edge_pattern_detected = Counter(
    "edge_pattern_detected_total",
    "Total pattern detections by type",
    ["symbol", "pattern", "direction", "timeframe"]
)

edge_pattern_confidence = Gauge(
    "edge_pattern_confidence",
    "Confidence score for detected pattern (0-1)",
    ["symbol", "pattern", "timeframe"]
)

edge_pattern_active = Gauge(
    "edge_pattern_active",
    "Currently active pattern for symbol (1=active)",
    ["symbol", "pattern", "timeframe"]
)

edge_multi_timeframe_alignment = Gauge(
    "edge_multi_timeframe_alignment",
    "Multi-timeframe alignment score (-1 to 1)",
    ["symbol"]
)

edge_chart_pattern_count = Gauge(
    "edge_chart_pattern_count",
    "Number of active complex chart patterns",
    ["symbol", "pattern_type"]
)

edge_rsi_oversold_count = Counter(
    "edge_rsi_oversold_total",
    "Total RSI oversold (<30) detections",
    ["symbol"]
)

edge_rsi_overbought_count = Counter(
    "edge_rsi_overbought_total",
    "Total RSI overbought (>70) detections",
    ["symbol"]
)

edge_macd_crossover_count = Counter(
    "edge_macd_crossover_total",
    "Total MACD crossovers detected",
    ["symbol", "direction"]
)

edge_support_level = Gauge(
    "edge_support_level",
    "Detected support price level",
    ["symbol", "timeframe"]
)

edge_resistance_level = Gauge(
    "edge_resistance_level",
    "Detected resistance price level",
    ["symbol", "timeframe"]
)

edge_sentinel_echo_detected = Gauge(
    "edge_sentinel_echo_detected",
    "Sentinel Echo detected (1=yes, 0=no)",
    ["symbol", "timeframe"]
)

edge_volatility_surge = Counter(
    "edge_volatility_surge_total",
    "Total volatility surge events",
    ["symbol"]
)

# ═════════════════════════════════════════════════════════════════════
# SIGNAL QUALITY METRICS
# ═════════════════════════════════════════════════════════════════════

edge_confidence_score = Gauge(
    "edge_confidence_score",
    "Weighted confidence score (0-1)",
    ["symbol"]
)

edge_signal_quality = Gauge(
    "edge_signal_quality",
    "Signal quality score based on multiple factors",
    ["symbol"]
)

edge_observation_impact = Gauge(
    "edge_observation_impact",
    "Impact of observation on signal adjustment",
    ["symbol", "observation_type"]
)

edge_desync_warnings = Counter(
    "edge_desync_warnings_total",
    "Total observation desync warnings",
    ["severity"]
)
