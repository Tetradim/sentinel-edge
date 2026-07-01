import type { ChartWorkspaceIndicatorId } from '@/types';

export type ChartWorkspaceIndicatorPresetId = 'core' | 'trend' | 'momentum' | 'clean' | 'custom';

export type ChartWorkspaceIndicatorPresetOption = {
  id: Exclude<ChartWorkspaceIndicatorPresetId, 'custom'>;
  label: string;
  indicators: ChartWorkspaceIndicatorId[];
};

export type ChartWorkspaceLayoutMode = 'analysis' | 'execution' | 'research';
export type ChartWorkspacePanelId = 'snapshot' | 'strategy' | 'lab' | 'oscillators';
export type ChartWorkspaceChartType = 'candlestick' | 'line';
export type ChartWorkspaceBarLimit = 120 | 240 | 390;
export type ChartWorkspaceOrbReplaySession = 'market_open' | 'premarket_30m';
export type ChartWorkspaceOrbOverlaySession = 'market_open' | 'premarket_30m';
export type MarketMapLayoutPreset = 'morning_plan' | 'intraday_alerts' | 'replay_proof';

export type ChartWorkspacePanelVisibility = {
  snapshot: boolean;
  strategy: boolean;
  lab: boolean;
  oscillators: boolean;
};

export type ChartWorkspaceLayoutState = {
  marketMapPreset: MarketMapLayoutPreset;
  layoutMode: ChartWorkspaceLayoutMode;
  panelVisibility: ChartWorkspacePanelVisibility;
};

export type ChartWorkspacePreferencesState = {
  activeSymbol: string;
  chartType: ChartWorkspaceChartType;
  indicatorPreset: ChartWorkspaceIndicatorPresetId;
  selectedIndicators: ChartWorkspaceIndicatorId[];
  barLimit: ChartWorkspaceBarLimit;
  showOrbOverlays: boolean;
  showVolume: boolean;
  orbOverlaySessions: ChartWorkspaceOrbOverlaySession[];
};

export type ChartWorkspaceSimulationLabExperiment = {
  id?: string;
  label?: string;
  runnable?: boolean;
  http_method?: string;
  endpoint_path?: string;
  result_schema_version?: string;
  result_metadata_fields?: string[];
};

export type ChartWorkspaceSimulationLabStatus = {
  enabled?: boolean;
  default_hidden?: boolean;
  disabled_reason?: string | null;
  experiments?: ChartWorkspaceSimulationLabExperiment[];
};

export type ChartWorkspaceSimulationLabResult = {
  kind: 'orb_backtest' | 'buying_power_allocation' | 'stop_trailing_dca';
  label: string;
  symbol?: string;
  created_at?: string;
  result: Record<string, unknown> & {
    schema_version?: string;
    run_id?: string;
    input_fingerprint?: string;
    input_fingerprint_algorithm?: string;
    summary?: Record<string, unknown>;
  };
};

export type ChartWorkspaceIndicatorSnapshotMetric = {
  label: string;
  value: string;
  timestamp?: string;
};
