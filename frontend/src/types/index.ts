// API Types
export interface TickerData {
  symbol: string;
  enabled: boolean;
  current_price?: number;
  orb_levels?: {
    '5m'?: OrbLevel;
    '15m'?: OrbLevel;
    '30m'?: OrbLevel;
  };
  orb_session_status?: OrbSessionStatus;
  orb_decision_context?: OrbDecisionContext;
  signal_strength?: number;
  trend?: string;
  atr?: number;
  volume_ratio?: number;
  last_decision?: string;
  confidence?: number;
  last_updated?: string;
  volume_zscore?: number;
}

export interface OrbLevel {
  high: number;
  low: number;
  locked: boolean;
  range_width: number;
  is_valid: boolean;
  date?: string;
  session_id?: string;
  start_time?: string | null;
  lock_time?: string | null;
}

export interface OrbSessionStatus {
  active_session: string;
  active_label: string;
  active_status: string;
  active_ready: boolean;
  active_readiness: string;
  active_ready_timeframes: string[];
  active_missing_timeframes: string[];
  sessions: Record<string, OrbSessionSummary>;
}

export interface OrbSessionSummary {
  id: string;
  label: string;
  description?: string;
  status: string;
  ready: boolean;
  readiness: string;
  ready_timeframes: string[];
  collecting_timeframes: string[];
  missing_timeframes: string[];
  start_time?: string;
  timeframes: string[];
  levels?: Record<string, OrbLevel>;
}

export interface OrbDecisionContext {
  source: string;
  active_session: string;
  active_label: string;
  active_status: string;
  active_ready: boolean;
  active_readiness: string;
  signal_session: string;
  signal_timeframe: string;
  signal_ready: boolean;
  signal_readiness: string;
  signal_level?: OrbLevel | null;
  reference_sessions?: Record<string, Record<string, OrbLevel>>;
  generated_at?: string;
}

export interface MarketStatus {
  open: boolean;
  lunch_break: boolean;
  minutes_to_close: number;
}

export interface SystemStats {
  active_tickers: string[];
  running: boolean;
  paused: boolean;
  orb_levels_count: number;
  pulse_circuit_state: string;
  pulse_failures: number;
}

export interface MetricCard {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'neutral';
  icon?: string;
}

export interface ChartDataPoint {
  timestamp: string;
  value: number;
  label?: string;
}

export type ChartWorkspaceIndicatorId =
  | 'ema_9'
  | 'ema_20'
  | 'sma_20'
  | 'sma_50'
  | 'sma_200'
  | 'rsi_14'
  | 'macd'
  | 'vwap'
  | 'atr_14';

export interface ChartWorkspaceBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartWorkspaceIndicatorPoint {
  timestamp: string;
  value?: number | null;
  macd?: number | null;
  signal?: number | null;
  histogram?: number | null;
}

export interface ChartWorkspaceIndicator {
  label: string;
  kind: 'overlay' | 'oscillator';
  points: ChartWorkspaceIndicatorPoint[];
}

export interface ChartWorkspaceOrbOverlay {
  session_id: string;
  label: string;
  timeframe: string;
  high: number;
  low: number;
  range_width: number;
  locked: boolean;
  is_valid: boolean;
  date?: string;
}

export interface MarketMapLevel {
  id: string;
  label: string;
  kind: string;
  price: number;
  source: string;
  session: string;
  confidence: number;
  timestamp: string;
  locked: boolean;
}

export interface MarketMapLevelsPayload {
  schema_version: string;
  items: MarketMapLevel[];
}

export interface MarketMapProofMarker {
  id: string;
  symbol: string;
  timestamp: string;
  kind: string;
  label: string;
  status: string;
  parser_confidence?: number | null;
  raw_text?: string | null;
  proof?: Record<string, unknown>;
}

export interface MarketMapProofMarkersPayload {
  schema_version: string;
  symbol: string;
  items: MarketMapProofMarker[];
}

export interface MarketMapContext {
  schema_version: string;
  symbol: string;
  status: 'pass' | 'review' | 'block' | string;
  score: number;
  directional_bias: string;
  trend_state: string;
  momentum_state: string;
  volatility_state: string;
  level_proximity?: {
    id?: string;
    label?: string;
    price?: number;
    distance_pct?: number;
  } | null;
  reasons: string[];
  warnings: string[];
}

export interface ChartWorkspaceSnapshot {
  schema_version: string;
  symbol: string;
  timeframe: string;
  source: string;
  summary: {
    bar_count: number;
    available_bar_count: number;
    indicator_count: number;
    orb_overlay_count: number;
  };
  bars: ChartWorkspaceBar[];
  indicators: Record<string, ChartWorkspaceIndicator>;
  levels?: MarketMapLevelsPayload;
  orb_overlays: ChartWorkspaceOrbOverlay[];
  orb_session_status?: OrbSessionStatus | null;
}

export interface ScannerWorkbenchCatalog {
  schema_version: string;
  source_policy: string;
  source_urls: string[];
  counts: {
    scanners: number;
    recommended_tickers: number;
    strategies: number;
    indicators: number;
    collection_packs: number;
  };
  scanners: ScannerWorkbenchScanner[];
  recommended_tickers: ScannerWorkbenchTicker[];
  strategies: ScannerWorkbenchStrategy[];
  indicators: ScannerWorkbenchIndicator[];
  collection_packs: ScannerWorkbenchCollectionPack[];
}

export interface ScannerWorkbenchWatchIntent {
  scanners: string[];
  tickers: string[];
  strategies: string[];
  indicators: string[];
}

export interface ScannerWorkbenchWatchIntentValidation {
  schema_version: string;
  catalog_schema_version: string;
  valid: boolean;
  selected_count: number;
  invalid_count: number;
  ignored_fields: string[];
  resolved_counts: {
    scanners: number;
    tickers: number;
    strategies: number;
    indicators: number;
  };
  expanded_counts: {
    scanners: number;
    tickers: number;
    strategies: number;
    indicators: number;
  };
  sanitized_intent: ScannerWorkbenchWatchIntent;
  expanded_intent: ScannerWorkbenchWatchIntent;
  invalid_selections: ScannerWorkbenchWatchIntent;
}

export interface ScannerWorkbenchScanner {
  id: string;
  name: string;
  category: string;
  description: string;
  watch_signals: string[];
  timeframes: string[];
  source_inspiration: string;
  source_urls: string[];
  requires: string[];
  automation_default: string;
}

export interface ScannerWorkbenchTicker {
  symbol: string;
  name: string;
  asset_class: string;
  liquidity_profile: string;
  recommended_for: string[];
  notes: string;
}

export interface ScannerWorkbenchStrategy {
  id: string;
  name: string;
  description: string;
  scanner_ids: string[];
  indicator_ids: string[];
  risk_notes: string;
  default_mode: string;
}

export interface ScannerWorkbenchIndicator {
  id: string;
  name: string;
  description: string;
  parameters: string[];
  used_by: string[];
}

export interface ScannerWorkbenchCollectionPack {
  id: string;
  name: string;
  description: string;
  scanner_ids: string[];
}

export interface PulseFeedback {
  sent?: boolean;
  status?: string;
  reason?: string;
  handoff_id?: string;
  message?: string;
  endpoint?: string;
  status_code?: number;
  legacy_fallback?: boolean;
  response?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface DecisionEntry {
  symbol: string;
  decision: string;
  signal_strength: number;
  trend: string;
  confidence: number;
  price: number;
  orb_decision_context?: OrbDecisionContext;
  handoff_sent?: boolean;
  handoff_status?: string;
  handoff_reason?: string;
  pulse_feedback?: PulseFeedback;
  timestamp: string;
}

export interface CorrelationRiskRecommendation {
  action: 'tighten_trailing_global' | 'review_trailing_stops' | 'observe_momentum' | string;
  priority: 'high' | 'medium' | 'low' | string;
  scope: 'global' | 'cluster_symbols' | 'watchlist' | string;
  trailing_stop_action: 'tighten' | 'review' | 'maintain' | string;
  operator_summary: string;
}

export interface CorrelationCluster {
  direction: 'BULLISH' | 'BEARISH';
  count: number;
  symbols: string[];
  strength: number;
  score?: number;
  timestamp: string;
  risk_recommendation?: CorrelationRiskRecommendation;
}

export interface MonteCarloResult {
  status?: string;
  method?: string;
  confidence_level?: number;
  simulations: number;
  median_final_equity: number;
  worst_case_equity: number;
  best_case_equity?: number;
  probability_of_profit: number;
  probability_of_ruin?: number;
  mean_max_drawdown: number;
  value_at_risk?: number;
  value_at_risk_pct?: number;
  conditional_value_at_risk?: number;
  conditional_value_at_risk_pct?: number;
  max_drawdown_percentiles?: {
    p50: number;
    p95: number;
    p99: number;
  };
  saved_chart_set?: {
    run_id: string;
    chart_count: number;
    manifest_path: string;
    charts: {
      name: string;
      path: string;
      api_path?: string;
    }[];
  };
}

export interface BacktestResult {
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  avg_trade_return_pct: number;
  avg_holding_period_minutes: number;
  consecutive_wins: number;
  consecutive_losses: number;
  monte_carlo?: MonteCarloResult;
}
