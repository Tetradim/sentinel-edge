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
  sessions: Record<string, OrbSessionSummary>;
}

export interface OrbSessionSummary {
  id: string;
  label: string;
  description?: string;
  status: string;
  start_time?: string;
  timeframes: string[];
  levels?: Record<string, OrbLevel>;
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

export interface DecisionEntry {
  symbol: string;
  decision: string;
  signal_strength: number;
  trend: string;
  confidence: number;
  price: number;
  timestamp: string;
}

export interface CorrelationCluster {
  direction: 'BULLISH' | 'BEARISH';
  count: number;
  symbols: string[];
  strength: number;
  score?: number;
  timestamp: string;
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
