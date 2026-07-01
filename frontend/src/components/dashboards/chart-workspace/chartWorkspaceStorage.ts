import type { ChartWorkspaceIndicatorId } from '@/types';
import {
  CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY,
  CHART_WORKSPACE_LAYOUT_STORAGE_KEY,
  CHART_WORKSPACE_PREFERENCES_STORAGE_KEY,
  DEFAULT_INDICATORS,
  DEFAULT_LAYOUT_STATE,
  DEFAULT_ORB_OVERLAY_SESSIONS,
  DEFAULT_PANEL_VISIBILITY,
  DEFAULT_PREFERENCES_STATE,
  INDICATOR_OPTIONS,
  INDICATOR_PRESET_OPTIONS,
  MARKET_MAP_LAYOUT_PRESETS,
  MARKET_MAP_LAYOUT_STORAGE_KEY,
  MARKET_MAP_PREFERENCES_STORAGE_KEY,
  ORB_OVERLAY_SESSION_OPTIONS,
} from './chartWorkspaceConstants';
import type {
  ChartWorkspaceBarLimit,
  ChartWorkspaceChartType,
  ChartWorkspaceIndicatorPresetId,
  ChartWorkspaceLayoutMode,
  ChartWorkspaceLayoutState,
  ChartWorkspaceOrbOverlaySession,
  ChartWorkspacePanelVisibility,
  ChartWorkspacePreferencesState,
  ChartWorkspaceSimulationLabResult,
  MarketMapLayoutPreset,
} from './chartWorkspaceTypes';
import { normalizeChartWorkspaceSymbol } from './chartWorkspaceSymbols';

export function readChartWorkspaceLayout(): ChartWorkspaceLayoutState {
  if (typeof window === 'undefined') return cloneDefaultLayoutState();
  try {
    const storedLayout =
      window.localStorage.getItem(MARKET_MAP_LAYOUT_STORAGE_KEY) ||
      window.localStorage.getItem(CHART_WORKSPACE_LAYOUT_STORAGE_KEY);
    if (!storedLayout) return cloneDefaultLayoutState();
    return normalizeChartWorkspaceLayout(JSON.parse(storedLayout));
  } catch {
    return cloneDefaultLayoutState();
  }
}

export function persistChartWorkspaceLayout(layout: ChartWorkspaceLayoutState) {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(MARKET_MAP_LAYOUT_STORAGE_KEY, JSON.stringify(layout));
    return true;
  } catch {
    return false;
  }
}

export function clearChartWorkspaceLayout() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(MARKET_MAP_LAYOUT_STORAGE_KEY);
    window.localStorage.removeItem(CHART_WORKSPACE_LAYOUT_STORAGE_KEY);
  } catch {
    return;
  }
}

export function readChartWorkspacePreferences(): ChartWorkspacePreferencesState {
  if (typeof window === 'undefined') return cloneDefaultPreferencesState();
  try {
    const storedPreferences =
      window.localStorage.getItem(MARKET_MAP_PREFERENCES_STORAGE_KEY) ||
      window.localStorage.getItem(CHART_WORKSPACE_PREFERENCES_STORAGE_KEY);
    if (!storedPreferences) return cloneDefaultPreferencesState();
    return normalizeChartWorkspacePreferences(JSON.parse(storedPreferences));
  } catch {
    return cloneDefaultPreferencesState();
  }
}

export function persistChartWorkspacePreferences(preferences: ChartWorkspacePreferencesState) {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(MARKET_MAP_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
    return true;
  } catch {
    return false;
  }
}

export function clearChartWorkspacePreferences() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(MARKET_MAP_PREFERENCES_STORAGE_KEY);
    window.localStorage.removeItem(CHART_WORKSPACE_PREFERENCES_STORAGE_KEY);
  } catch {
    return;
  }
}

export function readChartWorkspaceLabResult(): ChartWorkspaceSimulationLabResult | null {
  if (typeof window === 'undefined') return null;
  try {
    const storedResult = window.localStorage.getItem(CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY);
    if (!storedResult) return null;
    return normalizeChartWorkspaceLabResult(JSON.parse(storedResult));
  } catch {
    return null;
  }
}

export function persistChartWorkspaceLabResult(result: ChartWorkspaceSimulationLabResult) {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY, JSON.stringify(result));
    return true;
  } catch {
    return false;
  }
}

export function clearChartWorkspaceLabResult() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY);
  } catch {
    return;
  }
}

function normalizeChartWorkspaceLayout(value: unknown): ChartWorkspaceLayoutState {
  if (!isRecord(value)) return cloneDefaultLayoutState();
  const storedPanels = isRecord(value.panelVisibility) ? value.panelVisibility : {};
  const panelVisibility = {
    snapshot: typeof storedPanels.snapshot === 'boolean' ? storedPanels.snapshot : DEFAULT_PANEL_VISIBILITY.snapshot,
    strategy:
      typeof storedPanels.strategy === 'boolean' ? storedPanels.strategy : DEFAULT_PANEL_VISIBILITY.strategy,
    lab: typeof storedPanels.lab === 'boolean' ? storedPanels.lab : DEFAULT_PANEL_VISIBILITY.lab,
    oscillators:
      typeof storedPanels.oscillators === 'boolean' ? storedPanels.oscillators : DEFAULT_PANEL_VISIBILITY.oscillators,
  };
  const layoutMode = isChartWorkspaceLayoutMode(value.layoutMode) ? value.layoutMode : DEFAULT_LAYOUT_STATE.layoutMode;
  return {
    marketMapPreset: isMarketMapLayoutPreset(value.marketMapPreset)
      ? value.marketMapPreset
      : inferMarketMapPreset(layoutMode, panelVisibility),
    layoutMode,
    panelVisibility,
  };
}

function normalizeChartWorkspacePreferences(value: unknown): ChartWorkspacePreferencesState {
  if (!isRecord(value)) return cloneDefaultPreferencesState();
  const selectedIndicators = normalizeChartWorkspaceIndicators(value.selectedIndicators);
  return {
    activeSymbol: normalizeChartWorkspaceSymbol(value.activeSymbol),
    chartType: isChartWorkspaceChartType(value.chartType) ? value.chartType : DEFAULT_PREFERENCES_STATE.chartType,
    indicatorPreset: isChartWorkspaceIndicatorPresetId(value.indicatorPreset)
      ? value.indicatorPreset
      : inferIndicatorPreset(selectedIndicators),
    selectedIndicators,
    barLimit: isChartWorkspaceBarLimit(value.barLimit) ? value.barLimit : DEFAULT_PREFERENCES_STATE.barLimit,
    showOrbOverlays:
      typeof value.showOrbOverlays === 'boolean'
        ? value.showOrbOverlays
        : DEFAULT_PREFERENCES_STATE.showOrbOverlays,
    showVolume:
      typeof value.showVolume === 'boolean'
        ? value.showVolume
        : DEFAULT_PREFERENCES_STATE.showVolume,
    orbOverlaySessions: normalizeOrbOverlaySessions(value.orbOverlaySessions),
  };
}

function normalizeChartWorkspaceLabResult(value: unknown): ChartWorkspaceSimulationLabResult | null {
  if (!isRecord(value)) return null;
  const kind = value.kind;
  const label = typeof value.label === 'string' ? value.label.trim() : '';
  const storedResult = isRecord(value.result) ? value.result : null;
  if (!isChartWorkspaceSimulationLabResultKind(kind) || !label || !storedResult) return null;

  const summary = isRecord(storedResult.summary) ? storedResult.summary : undefined;
  const symbol = normalizeChartWorkspaceLabResultSymbol(value.symbol);
  const createdAt = normalizeChartWorkspaceLabResultTimestamp(value.created_at);
  return {
    kind,
    label,
    symbol,
    created_at: createdAt,
    result: {
      ...storedResult,
      schema_version: typeof storedResult.schema_version === 'string' ? storedResult.schema_version : undefined,
      summary,
    },
  };
}

function normalizeChartWorkspaceLabResultSymbol(value: unknown) {
  if (typeof value !== 'string') return undefined;
  const symbol = value.trim().toUpperCase();
  return /^[A-Z0-9.-]{1,10}$/.test(symbol) ? symbol : undefined;
}

function normalizeChartWorkspaceLabResultTimestamp(value: unknown) {
  if (typeof value !== 'string') return undefined;
  const timestamp = value.trim();
  return timestamp && !Number.isNaN(Date.parse(timestamp)) ? timestamp : undefined;
}

export function cloneDefaultLayoutState(): ChartWorkspaceLayoutState {
  return {
    marketMapPreset: DEFAULT_LAYOUT_STATE.marketMapPreset,
    layoutMode: DEFAULT_LAYOUT_STATE.layoutMode,
    panelVisibility: { ...DEFAULT_PANEL_VISIBILITY },
  };
}

export function cloneDefaultPreferencesState(): ChartWorkspacePreferencesState {
  return {
    ...DEFAULT_PREFERENCES_STATE,
    selectedIndicators: [...DEFAULT_INDICATORS],
    orbOverlaySessions: [...DEFAULT_ORB_OVERLAY_SESSIONS],
  };
}

function isChartWorkspaceLayoutMode(value: unknown): value is ChartWorkspaceLayoutMode {
  return value === 'analysis' || value === 'execution' || value === 'research';
}

function isMarketMapLayoutPreset(value: unknown): value is MarketMapLayoutPreset {
  return MARKET_MAP_LAYOUT_PRESETS.some((option) => option.id === value);
}

export function inferMarketMapPreset(
  layoutMode: ChartWorkspaceLayoutMode,
  panelVisibility: ChartWorkspacePanelVisibility,
): MarketMapLayoutPreset {
  const matchingPreset = MARKET_MAP_LAYOUT_PRESETS.find(
    (preset) =>
      preset.layoutMode === layoutMode &&
      preset.panelVisibility.snapshot === panelVisibility.snapshot &&
      preset.panelVisibility.strategy === panelVisibility.strategy &&
      preset.panelVisibility.lab === panelVisibility.lab &&
      preset.panelVisibility.oscillators === panelVisibility.oscillators,
  );
  return matchingPreset?.id ?? DEFAULT_LAYOUT_STATE.marketMapPreset;
}

function isChartWorkspaceChartType(value: unknown): value is ChartWorkspaceChartType {
  return value === 'candlestick' || value === 'line';
}

function isChartWorkspaceBarLimit(value: unknown): value is ChartWorkspaceBarLimit {
  return value === 120 || value === 240 || value === 390;
}

function isChartWorkspaceIndicatorId(value: unknown): value is ChartWorkspaceIndicatorId {
  return INDICATOR_OPTIONS.some((option) => option.id === value);
}

function isChartWorkspaceIndicatorPresetId(value: unknown): value is ChartWorkspaceIndicatorPresetId {
  return value === 'custom' || INDICATOR_PRESET_OPTIONS.some((option) => option.id === value);
}

function isChartWorkspaceSimulationLabResultKind(value: unknown): value is ChartWorkspaceSimulationLabResult['kind'] {
  return value === 'orb_backtest' || value === 'buying_power_allocation' || value === 'stop_trailing_dca';
}

export function normalizeChartWorkspaceIndicators(value: unknown) {
  if (!Array.isArray(value)) return [...DEFAULT_INDICATORS];
  return Array.from(new Set(value.filter(isChartWorkspaceIndicatorId)));
}

export function inferIndicatorPreset(indicators: ChartWorkspaceIndicatorId[]): ChartWorkspaceIndicatorPresetId {
  const normalizedIndicators = normalizeIndicatorPresetSignature(indicators);
  const matchingPreset = INDICATOR_PRESET_OPTIONS.find(
    (option) => normalizeIndicatorPresetSignature(option.indicators) === normalizedIndicators,
  );
  return matchingPreset?.id ?? 'custom';
}

function normalizeIndicatorPresetSignature(indicators: ChartWorkspaceIndicatorId[]) {
  return [...indicators].sort().join(',');
}

function normalizeOrbOverlaySessions(value: unknown) {
  if (!Array.isArray(value)) return [...DEFAULT_ORB_OVERLAY_SESSIONS];
  const sessions = Array.from(new Set(value.filter(isChartWorkspaceOrbOverlaySession)));
  return sessions.length ? sessions : [];
}

function isChartWorkspaceOrbOverlaySession(value: unknown): value is ChartWorkspaceOrbOverlaySession {
  return ORB_OVERLAY_SESSION_OPTIONS.some((option) => option.id === value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}
