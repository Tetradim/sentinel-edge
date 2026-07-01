import type { ChartWorkspaceIndicatorId } from '@/types';
import type {
  ChartWorkspaceBarLimit,
  ChartWorkspaceIndicatorPresetOption,
  ChartWorkspaceLayoutMode,
  ChartWorkspaceOrbOverlaySession,
  ChartWorkspaceOrbReplaySession,
  ChartWorkspacePanelId,
  ChartWorkspacePanelVisibility,
  ChartWorkspacePreferencesState,
  MarketMapLayoutPreset,
  ChartWorkspaceLayoutState,
} from './chartWorkspaceTypes';

export const INDICATOR_OPTIONS: { id: ChartWorkspaceIndicatorId; label: string }[] = [
  { id: 'ema_9', label: 'EMA 9' },
  { id: 'ema_20', label: 'EMA 20' },
  { id: 'sma_20', label: 'SMA 20' },
  { id: 'rsi_14', label: 'RSI 14' },
  { id: 'macd', label: 'MACD' },
];

export const DEFAULT_INDICATORS: ChartWorkspaceIndicatorId[] = ['ema_9', 'ema_20', 'sma_20', 'rsi_14', 'macd'];

export const MARKET_MAP_LAYOUT_STORAGE_KEY = 'sentinel-edge.market-map.layout.v1';
export const MARKET_MAP_PREFERENCES_STORAGE_KEY = 'sentinel-edge.market-map.preferences.v1';
export const CHART_WORKSPACE_LAYOUT_STORAGE_KEY = 'sentinel-edge.chart-workspace.layout.v1';
export const CHART_WORKSPACE_PREFERENCES_STORAGE_KEY = 'sentinel-edge.chart-workspace.preferences.v1';
export const CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY = 'sentinel-edge.chart-workspace.lab-result.v1';
export const DEFAULT_ORB_OVERLAY_SESSIONS: ChartWorkspaceOrbOverlaySession[] = ['market_open', 'premarket_30m'];
export const LOCAL_PREVIEW_FEED_MESSAGE = 'Local preview feed active: chart workspace API unavailable.';
export const FALLBACK_PRICE_ANCHORS: Record<string, number> = {
  SPY: 603.47,
  QQQ: 492.18,
  TSLA: 228.45,
  NVDA: 159.32,
  AAPL: 214.82,
  MSFT: 498.3,
  ESU6: 6023.25,
  NQU6: 22114.5,
  'BTC-USD': 106782,
  'ETH-USD': 3892,
};

export const DEFAULT_PANEL_VISIBILITY: ChartWorkspacePanelVisibility = {
  snapshot: true,
  strategy: true,
  lab: true,
  oscillators: true,
};

export const DEFAULT_LAYOUT_STATE: ChartWorkspaceLayoutState = {
  marketMapPreset: 'morning_plan',
  layoutMode: 'analysis',
  panelVisibility: DEFAULT_PANEL_VISIBILITY,
};

export const MARKET_MAP_LAYOUT_PRESETS: {
  id: MarketMapLayoutPreset;
  label: string;
  detail: string;
  layoutMode: ChartWorkspaceLayoutMode;
  panelVisibility: ChartWorkspacePanelVisibility;
}[] = [
  {
    id: 'morning_plan',
    label: 'Morning Plan',
    detail: 'Levels, VWAP, trend, and watched tickers before the session.',
    layoutMode: 'analysis',
    panelVisibility: { snapshot: true, strategy: true, lab: false, oscillators: true },
  },
  {
    id: 'intraday_alerts',
    label: 'Intraday Alerts',
    detail: 'Live alert context, Edge confidence, and options quality.',
    layoutMode: 'execution',
    panelVisibility: { snapshot: true, strategy: true, lab: false, oscillators: true },
  },
  {
    id: 'replay_proof',
    label: 'Replay Proof',
    detail: 'Alert-chain proof, chart markers, and reconciliation evidence.',
    layoutMode: 'research',
    panelVisibility: { snapshot: true, strategy: true, lab: true, oscillators: true },
  },
];

export const DEFAULT_PREFERENCES_STATE: ChartWorkspacePreferencesState = {
  activeSymbol: 'SPY',
  chartType: 'candlestick',
  indicatorPreset: 'core',
  selectedIndicators: DEFAULT_INDICATORS,
  barLimit: 240,
  showOrbOverlays: true,
  showVolume: true,
  orbOverlaySessions: DEFAULT_ORB_OVERLAY_SESSIONS,
};

export const LAYOUT_OPTIONS: { id: ChartWorkspaceLayoutMode; label: string }[] = [
  { id: 'analysis', label: 'Analysis' },
  { id: 'execution', label: 'Execution' },
  { id: 'research', label: 'Research' },
];

export const PANEL_OPTIONS: { id: ChartWorkspacePanelId; label: string }[] = [
  { id: 'snapshot', label: 'Snapshot' },
  { id: 'strategy', label: 'Strategy' },
  { id: 'lab', label: 'Lab' },
  { id: 'oscillators', label: 'Oscillators' },
];

export const BAR_LIMIT_OPTIONS: { value: ChartWorkspaceBarLimit; label: string }[] = [
  { value: 120, label: '120 bars' },
  { value: 240, label: '240 bars' },
  { value: 390, label: '390 bars' },
];

export const INDICATOR_PRESET_OPTIONS: ChartWorkspaceIndicatorPresetOption[] = [
  { id: 'core', label: 'Core', indicators: DEFAULT_INDICATORS },
  { id: 'trend', label: 'Trend', indicators: ['ema_9', 'ema_20', 'sma_20'] },
  { id: 'momentum', label: 'Momentum', indicators: ['rsi_14', 'macd'] },
  { id: 'clean', label: 'Clean', indicators: [] },
];

export const ORB_REPLAY_SESSION_OPTIONS: {
  id: ChartWorkspaceOrbReplaySession;
  label: string;
  timeframeMinutes: 30;
}[] = [
  { id: 'market_open', label: 'Market open', timeframeMinutes: 30 },
  { id: 'premarket_30m', label: 'Premarket 30m', timeframeMinutes: 30 },
];

export const ORB_OVERLAY_SESSION_OPTIONS: { id: ChartWorkspaceOrbOverlaySession; label: string }[] = [
  { id: 'market_open', label: 'Market open ORB' },
  { id: 'premarket_30m', label: 'Premarket ORB' },
];

export const panelClass = 'rounded-lg border border-slate-800 bg-slate-950/80 p-3';
export const activeToolClass =
  'inline-flex h-9 items-center gap-2 rounded-lg border border-cyan-300/60 bg-cyan-400/15 px-3 text-sm font-semibold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-60';
export const inactiveToolClass =
  'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm font-semibold text-slate-300 hover:border-cyan-400/40 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-60';
export const activeRadioClass = `${activeToolClass} cursor-pointer`;
export const inactiveRadioClass = `${inactiveToolClass} cursor-pointer`;
