import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  CandlestickChart,
  FlaskConical,
  LineChart,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { api } from '@/lib/api';
import type {
  ChartWorkspaceIndicatorId,
  ChartWorkspaceIndicatorPoint,
  ChartWorkspaceSnapshot,
  OrbSessionSummary,
} from '@/types';
import { PlotlyChart } from '../ui/PlotlyCharts';

const INDICATOR_OPTIONS: { id: ChartWorkspaceIndicatorId; label: string }[] = [
  { id: 'ema_9', label: 'EMA 9' },
  { id: 'ema_20', label: 'EMA 20' },
  { id: 'sma_20', label: 'SMA 20' },
  { id: 'rsi_14', label: 'RSI 14' },
  { id: 'macd', label: 'MACD' },
];

type ChartWorkspaceIndicatorPresetId = 'core' | 'trend' | 'momentum' | 'clean' | 'custom';
interface ChartWorkspaceIndicatorPresetOption {
  id: Exclude<ChartWorkspaceIndicatorPresetId, 'custom'>;
  label: string;
  indicators: ChartWorkspaceIndicatorId[];
}

const DEFAULT_INDICATORS: ChartWorkspaceIndicatorId[] = ['ema_9', 'ema_20', 'sma_20', 'rsi_14', 'macd'];

type ChartWorkspaceLayoutMode = 'analysis' | 'execution' | 'research';
type ChartWorkspacePanelId = 'snapshot' | 'strategy' | 'lab' | 'oscillators';
type ChartWorkspaceChartType = 'candlestick' | 'line';
type ChartWorkspaceBarLimit = 120 | 240 | 390;
type ChartWorkspaceOrbReplaySession = 'market_open' | 'premarket_30m';
type ChartWorkspaceOrbOverlaySession = 'market_open' | 'premarket_30m';

interface ChartWorkspacePanelVisibility {
  snapshot: boolean;
  strategy: boolean;
  lab: boolean;
  oscillators: boolean;
}

interface ChartWorkspaceLayoutState {
  layoutMode: ChartWorkspaceLayoutMode;
  panelVisibility: ChartWorkspacePanelVisibility;
}

interface ChartWorkspacePreferencesState {
  activeSymbol: string;
  chartType: ChartWorkspaceChartType;
  indicatorPreset: ChartWorkspaceIndicatorPresetId;
  selectedIndicators: ChartWorkspaceIndicatorId[];
  barLimit: ChartWorkspaceBarLimit;
  showOrbOverlays: boolean;
  showVolume: boolean;
  orbOverlaySessions: ChartWorkspaceOrbOverlaySession[];
}

interface ChartWorkspaceSimulationLabExperiment {
  id?: string;
  label?: string;
  runnable?: boolean;
  http_method?: string;
  endpoint_path?: string;
  result_schema_version?: string;
  result_metadata_fields?: string[];
}

interface ChartWorkspaceSimulationLabStatus {
  enabled?: boolean;
  default_hidden?: boolean;
  experiments?: ChartWorkspaceSimulationLabExperiment[];
}

interface ChartWorkspaceSimulationLabResult {
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
}

interface ChartWorkspaceIndicatorSnapshotMetric {
  label: string;
  value: string;
  timestamp?: string;
}

const CHART_WORKSPACE_LAYOUT_STORAGE_KEY = 'sentinel-edge.chart-workspace.layout.v1';
const CHART_WORKSPACE_PREFERENCES_STORAGE_KEY = 'sentinel-edge.chart-workspace.preferences.v1';
const CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY = 'sentinel-edge.chart-workspace.lab-result.v1';
const DEFAULT_ORB_OVERLAY_SESSIONS: ChartWorkspaceOrbOverlaySession[] = ['market_open', 'premarket_30m'];

const DEFAULT_PANEL_VISIBILITY: ChartWorkspacePanelVisibility = {
  snapshot: true,
  strategy: true,
  lab: true,
  oscillators: true,
};

const DEFAULT_LAYOUT_STATE: ChartWorkspaceLayoutState = {
  layoutMode: 'analysis',
  panelVisibility: DEFAULT_PANEL_VISIBILITY,
};

const DEFAULT_PREFERENCES_STATE: ChartWorkspacePreferencesState = {
  activeSymbol: 'SPY',
  chartType: 'candlestick',
  indicatorPreset: 'core',
  selectedIndicators: DEFAULT_INDICATORS,
  barLimit: 240,
  showOrbOverlays: true,
  showVolume: true,
  orbOverlaySessions: DEFAULT_ORB_OVERLAY_SESSIONS,
};

const LAYOUT_OPTIONS: { id: ChartWorkspaceLayoutMode; label: string }[] = [
  { id: 'analysis', label: 'Analysis' },
  { id: 'execution', label: 'Execution' },
  { id: 'research', label: 'Research' },
];

const PANEL_OPTIONS: { id: ChartWorkspacePanelId; label: string }[] = [
  { id: 'snapshot', label: 'Snapshot' },
  { id: 'strategy', label: 'Strategy' },
  { id: 'lab', label: 'Lab' },
  { id: 'oscillators', label: 'Oscillators' },
];

const BAR_LIMIT_OPTIONS: { value: ChartWorkspaceBarLimit; label: string }[] = [
  { value: 120, label: '120 bars' },
  { value: 240, label: '240 bars' },
  { value: 390, label: '390 bars' },
];

const INDICATOR_PRESET_OPTIONS: ChartWorkspaceIndicatorPresetOption[] = [
  { id: 'core', label: 'Core', indicators: DEFAULT_INDICATORS },
  { id: 'trend', label: 'Trend', indicators: ['ema_9', 'ema_20', 'sma_20'] },
  { id: 'momentum', label: 'Momentum', indicators: ['rsi_14', 'macd'] },
  { id: 'clean', label: 'Clean', indicators: [] },
];

const ORB_REPLAY_SESSION_OPTIONS: {
  id: ChartWorkspaceOrbReplaySession;
  label: string;
  timeframeMinutes: 30;
}[] = [
  { id: 'market_open', label: 'Market open', timeframeMinutes: 30 },
  { id: 'premarket_30m', label: 'Premarket 30m', timeframeMinutes: 30 },
];

const ORB_OVERLAY_SESSION_OPTIONS: { id: ChartWorkspaceOrbOverlaySession; label: string }[] = [
  { id: 'market_open', label: 'Market open ORB' },
  { id: 'premarket_30m', label: 'Premarket ORB' },
];

const chartCrosshairAxis = {
  showspikes: true,
  spikemode: 'across',
  spikesnap: 'cursor',
  spikethickness: 1,
  spikecolor: '#38bdf8',
};

export const ChartWorkspace: React.FC = () => {
  const [workspacePreferences, setWorkspacePreferences] =
    useState<ChartWorkspacePreferencesState>(readChartWorkspacePreferences);
  const workspacePreferencesRef = useRef(workspacePreferences);
  const [symbolInput, setSymbolInput] = useState(workspacePreferences.activeSymbol);
  const [workspaceLayout, setWorkspaceLayout] = useState<ChartWorkspaceLayoutState>(readChartWorkspaceLayout);
  const [snapshot, setSnapshot] = useState<ChartWorkspaceSnapshot | null>(null);
  const [simulationLabStatus, setSimulationLabStatus] = useState<ChartWorkspaceSimulationLabStatus | null>(null);
  const [simulationLabResult, setSimulationLabResult] = useState<ChartWorkspaceSimulationLabResult | null>(readChartWorkspaceLabResult);
  const [orbReplaySession, setOrbReplaySession] = useState<ChartWorkspaceOrbReplaySession>('market_open');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [labMessage, setLabMessage] = useState('');
  const [labRunInProgress, setLabRunInProgress] = useState(false);
  const labRunInProgressRef = useRef(false);
  const [layoutMessage, setLayoutMessage] = useState('');
  const [viewMessage, setViewMessage] = useState('');
  const {
    activeSymbol,
    chartType,
    indicatorPreset,
    selectedIndicators,
    barLimit,
    showOrbOverlays,
    showVolume,
    orbOverlaySessions,
  } =
    workspacePreferences;

  useEffect(() => {
    let cancelled = false;
    const loadSnapshot = async () => {
      setLoading(true);
      setError('');
      try {
        const nextSnapshot = await api.getChartWorkspace(activeSymbol, {
          indicators: selectedIndicators,
          limit: barLimit,
        });
        if (!cancelled) setSnapshot(nextSnapshot);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load chart workspace');
          setSnapshot(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    loadSnapshot();
    return () => {
      cancelled = true;
    };
  }, [activeSymbol, selectedIndicators, barLimit]);

  useEffect(() => {
    let cancelled = false;
    api.getSimulationLabStatus()
      .then((status) => {
        if (!cancelled) setSimulationLabStatus(status);
      })
      .catch(() => {
        if (!cancelled) {
          setSimulationLabStatus({
            enabled: false,
            default_hidden: true,
            experiments: [],
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const priceData = useMemo(
    () => buildPriceTraces(snapshot, chartType, showOrbOverlays, showVolume, orbOverlaySessions),
    [snapshot, chartType, showOrbOverlays, showVolume, orbOverlaySessions],
  );
  const oscillatorData = useMemo(() => buildOscillatorTraces(snapshot), [snapshot]);
  const indicatorSnapshotMetrics = useMemo(
    () => buildIndicatorSnapshotMetrics(snapshot, selectedIndicators),
    [snapshot, selectedIndicators],
  );
  const latestBar = snapshot?.bars[snapshot.bars.length - 1];
  const { layoutMode, panelVisibility } = workspaceLayout;
  const simulationLabEnabled = Boolean(
    simulationLabStatus?.enabled && simulationLabStatus.experiments?.some((experiment) => experiment.runnable),
  );
  const simulationLabExperiments = simulationLabStatus?.experiments?.filter((experiment) => experiment.runnable) ?? [];
  const visiblePanelOptions = useMemo(
    () => PANEL_OPTIONS.filter((option) => option.id !== 'lab' || simulationLabEnabled),
    [simulationLabEnabled],
  );
  const hasSidePanels =
    panelVisibility.snapshot || panelVisibility.strategy || (panelVisibility.lab && simulationLabEnabled);
  const workspaceGridClass = getWorkspaceGridClass(layoutMode);
  const sidePanelClass = getSidePanelClass(layoutMode);
  const pricePanelClass = `${panelClass} ${layoutMode === 'execution' ? '2xl:order-last' : ''}`;
  const selectedOrbReplaySession =
    ORB_REPLAY_SESSION_OPTIONS.find((option) => option.id === orbReplaySession) || ORB_REPLAY_SESSION_OPTIONS[0];
  const orbSessionStatus = snapshot?.orb_session_status;
  const orbSessionEntries = useMemo(() => Object.values(orbSessionStatus?.sessions ?? {}), [orbSessionStatus]);
  const oscillatorHeight = layoutMode === 'research' ? 260 : 220;
  const priceChartHeight = layoutMode === 'research' ? 500 : 430;
  const labActionsReady = Boolean(snapshot?.bars.length && latestBar);
  const labActionDisabled = labRunInProgress || !labActionsReady;
  const labUnavailableMessage = 'Load chart data to run Simulation Lab.';
  const activeChartSymbol = snapshot?.symbol || activeSymbol;
  const simulationLabResultSymbolMismatch = Boolean(
    simulationLabResult?.symbol && simulationLabResult.symbol !== activeChartSymbol,
  );

  const submitSymbol = (event: React.FormEvent) => {
    event.preventDefault();
    const symbol = symbolInput.trim().toUpperCase();
    if (!symbol || !/^[A-Z0-9.-]{1,10}$/.test(symbol)) {
      setError('Enter a valid symbol');
      return;
    }
    setSymbolInput(symbol);
    updateWorkspacePreferences((current) => ({
      ...current,
      activeSymbol: symbol,
    }));
  };

  const toggleIndicator = (indicator: ChartWorkspaceIndicatorId, checked: boolean) => {
    updateWorkspacePreferences((current) => {
      const nextIndicators = checked
        ? current.selectedIndicators.includes(indicator)
          ? current.selectedIndicators
          : [...current.selectedIndicators, indicator]
        : current.selectedIndicators.filter((item) => item !== indicator);
      return {
        ...current,
        indicatorPreset: 'custom',
        selectedIndicators: nextIndicators,
      };
    });
  };

  const applyIndicatorPreset = (preset: ChartWorkspaceIndicatorPresetOption) => {
    updateWorkspacePreferences((current) => ({
      ...current,
      indicatorPreset: preset.id,
      selectedIndicators: [...preset.indicators],
    }));
  };

  const selectChartType = (nextChartType: ChartWorkspaceChartType) => {
    updateWorkspacePreferences((current) => ({
      ...current,
      chartType: nextChartType,
    }));
  };

  const setBarLimit = (nextBarLimit: ChartWorkspaceBarLimit) => {
    updateWorkspacePreferences((current) => ({
      ...current,
      barLimit: nextBarLimit,
    }));
  };

  const toggleOrbOverlays = (checked: boolean) => {
    updateWorkspacePreferences((current) => ({
      ...current,
      showOrbOverlays: checked,
    }));
  };

  const toggleVolume = (checked: boolean) => {
    updateWorkspacePreferences((current) => ({
      ...current,
      showVolume: checked,
    }));
  };

  const toggleOrbOverlaySession = (session: ChartWorkspaceOrbOverlaySession, checked: boolean) => {
    updateWorkspacePreferences((current) => {
      const nextSessions = checked
        ? Array.from(new Set([...current.orbOverlaySessions, session]))
        : current.orbOverlaySessions.filter((item) => item !== session);
      return {
        ...current,
        orbOverlaySessions: nextSessions,
      };
    });
  };

  const resetWorkspacePreferences = () => {
    const nextPreferences = cloneDefaultPreferencesState();
    workspacePreferencesRef.current = nextPreferences;
    setWorkspacePreferences(nextPreferences);
    setSymbolInput(nextPreferences.activeSymbol);
    clearChartWorkspacePreferences();
    setViewMessage('View reset');
  };

  const updateWorkspacePreferences = (
    resolveNextPreferences: (current: ChartWorkspacePreferencesState) => ChartWorkspacePreferencesState,
  ) => {
    const nextPreferences = resolveNextPreferences(workspacePreferencesRef.current);
    workspacePreferencesRef.current = nextPreferences;
    setWorkspacePreferences(nextPreferences);
    setViewMessage(
      persistChartWorkspacePreferences(nextPreferences) ? 'View saved' : 'View changes are local only',
    );
  };

  const updateWorkspaceLayout = (nextLayout: ChartWorkspaceLayoutState) => {
    setWorkspaceLayout(nextLayout);
    setLayoutMessage(persistChartWorkspaceLayout(nextLayout) ? 'Layout saved' : 'Layout changes are local only');
  };

  const rememberSimulationLabResult = (nextResult: ChartWorkspaceSimulationLabResult) => {
    const enrichedResult: ChartWorkspaceSimulationLabResult = {
      ...nextResult,
      symbol: snapshot?.symbol || activeSymbol,
      created_at: new Date().toISOString(),
    };
    setSimulationLabResult(enrichedResult);
    return persistChartWorkspaceLabResult(enrichedResult);
  };

  const forgetSimulationLabResult = () => {
    setSimulationLabResult(null);
    clearChartWorkspaceLabResult();
    setLabMessage('Lab result cleared');
  };

  const runSimulationLabWorkflow = async (workflow: () => Promise<void>) => {
    if (labRunInProgress) return;
    if (labRunInProgressRef.current) return;
    labRunInProgressRef.current = true;
    setLabRunInProgress(true);
    try {
      await workflow();
    } finally {
      labRunInProgressRef.current = false;
      setLabRunInProgress(false);
    }
  };

  const selectLayoutMode = (nextLayoutMode: ChartWorkspaceLayoutMode) => {
    updateWorkspaceLayout({
      ...workspaceLayout,
      layoutMode: nextLayoutMode,
    });
  };

  const toggleWorkspacePanel = (panel: ChartWorkspacePanelId, checked: boolean) => {
    updateWorkspaceLayout({
      ...workspaceLayout,
      panelVisibility: {
        ...workspaceLayout.panelVisibility,
        [panel]: checked,
      },
    });
  };

  const resetWorkspaceLayout = () => {
    setWorkspaceLayout(DEFAULT_LAYOUT_STATE);
    clearChartWorkspaceLayout();
    setLayoutMessage('Layout reset');
  };

  const runOrbReplay = () => runSimulationLabWorkflow(async () => {
    if (!labActionsReady) {
      setLabMessage(labUnavailableMessage);
      return;
    }
    if (!snapshot?.bars.length) return;
    setLabMessage(`Running ${selectedOrbReplaySession.label} ORB replay`);
    try {
      const result = await api.runSimulationLabOrbBacktest({
        symbol: snapshot.symbol,
        session_id: orbReplaySession,
        timeframe_minutes: selectedOrbReplaySession.timeframeMinutes,
        breakout_side: 'both',
        target_r_multiple: 2,
        bars: snapshot.bars,
      });
      rememberSimulationLabResult({
        kind: 'orb_backtest',
        label: `${selectedOrbReplaySession.label} ORB replay`,
        result,
      });
      setLabMessage(`${selectedOrbReplaySession.label} ORB replay: ${result.summary?.breakouts ?? 0} breakouts`);
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'ORB replay unavailable');
    }
  });

  const runAllocationExperiment = () => runSimulationLabWorkflow(async () => {
    if (!labActionsReady) {
      setLabMessage(labUnavailableMessage);
      return;
    }
    if (!snapshot?.bars.length || !latestBar) return;
    setLabMessage('Running buying-power allocation');
    try {
      const result = await api.runSimulationLabBuyingPowerAllocation({
        buying_power: 10000,
        cash_reserve_pct: 0.1,
        max_position_pct: 0.4,
        mode: 'confidence_weighted',
        candidates: buildAllocationCandidates(snapshot.symbol, latestBar.close),
      });
      rememberSimulationLabResult({
        kind: 'buying_power_allocation',
        label: 'Buying-power allocation',
        result,
      });
      setLabMessage(
        `Allocation: $${Number(result.summary?.allocated_notional ?? 0).toLocaleString()} across ${
          result.summary?.allocated_count ?? 0
        } candidates`,
      );
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'Allocation experiment unavailable');
    }
  });

  const runExitComparison = () => runSimulationLabWorkflow(async () => {
    if (!labActionsReady) {
      setLabMessage(labUnavailableMessage);
      return;
    }
    if (!snapshot?.bars.length) return;
    setLabMessage('Running exit comparison');
    try {
      const result = await api.runSimulationLabStopTrailingDcaComparison({
        entry_price: snapshot.bars[0].close,
        quantity: 1,
        stop_loss_pct: 0.05,
        trailing_pct: 0.03,
        dca_steps: 1,
        dca_drop_pct: 0.03,
        price_path: snapshot.bars,
      });
      rememberSimulationLabResult({
        kind: 'stop_trailing_dca',
        label: 'Stop vs trailing-stop vs DCA',
        result,
      });
      setLabMessage(`Exit comparison: ${result.summary?.best_plan ?? 'n/a'} best`);
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'Exit comparison unavailable');
    }
  });

  const sidePanels = hasSidePanels ? (
    <aside className={sidePanelClass}>
      {panelVisibility.snapshot && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Activity className="h-4 w-4 text-cyan-300" />
            Snapshot
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Metric label="Last" value={latestBar ? `$${latestBar.close.toFixed(2)}` : '--'} />
            <Metric label="Bars" value={snapshot?.summary.bar_count ?? '--'} />
            <Metric label="Indicators" value={snapshot?.summary.indicator_count ?? '--'} />
            <Metric label="ORB" value={snapshot?.summary.orb_overlay_count ?? '--'} />
            <Metric label="ORB session" value={orbSessionStatus?.active_label ?? '--'} />
            <Metric label="ORB status" value={formatOrbSessionStatus(orbSessionStatus?.active_status)} />
            <Metric label="ORB readiness" value={formatOrbReadiness(orbSessionStatus?.active_readiness)} />
          </div>
          {orbSessionEntries.length > 0 && (
            <div className="mt-3 space-y-1 text-[11px] text-slate-400">
              <div className="font-semibold uppercase text-slate-500">ORB sessions</div>
              {orbSessionEntries.map((session) => (
                <div key={session.id} className="border-t border-slate-800/80 pt-1 first:border-t-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-slate-300">{session.label}</span>
                    <span className="shrink-0 text-slate-500">{formatOrbSessionStatus(session.status)}</span>
                  </div>
                  <div className="truncate text-slate-500">{formatOrbSessionLevelSummary(session)}</div>
                  <div className="truncate text-slate-500">
                    {formatOrbSessionReadinessDetail(session)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {panelVisibility.strategy && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <BarChart3 className="h-4 w-4 text-emerald-300" />
            Strategy Context
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Metric label="Preset" value={formatIndicatorPresetLabel(indicatorPreset)} />
            <Metric label="Indicators" value={formatSelectedIndicators(selectedIndicators)} />
            <Metric label="Range" value={`${barLimit} bars`} />
            <Metric label="Chart" value={formatChartType(chartType)} />
            <Metric label="ORB overlays" value={formatOrbOverlaySessionSummary(showOrbOverlays, orbOverlaySessions)} />
            <Metric label="Volume" value={formatVolumeOverlay(showVolume)} />
            <Metric label="Lab gate" value={formatSimulationLabGate(simulationLabStatus, simulationLabEnabled)} />
          </div>
          <div className="mt-3 space-y-1 border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
            <div className="font-semibold uppercase text-slate-500">Workspace posture</div>
            <div>Layout: {formatLayoutMode(layoutMode)}</div>
            <div>Replay session: {selectedOrbReplaySession.label}</div>
            <div>Symbol: {activeSymbol}</div>
          </div>
          {indicatorSnapshotMetrics.length > 0 && (
            <div className="mt-3 space-y-1 border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
              <div className="font-semibold uppercase text-slate-500">Indicator Snapshot</div>
              {indicatorSnapshotMetrics.map((metric) => (
                <div key={metric.label} className="flex items-center justify-between gap-2">
                  <span className="truncate text-slate-300">{metric.label}</span>
                  <span className="shrink-0 font-mono text-slate-500" title={metric.timestamp}>
                    {metric.value}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {panelVisibility.lab && simulationLabEnabled && (
        <section className={panelClass} aria-busy={labRunInProgress}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <FlaskConical className="h-4 w-4 text-amber-300" />
            Simulation Lab
          </div>
          {labRunInProgress && <div className="mb-2 text-xs text-amber-200">Running...</div>}
          {!labActionsReady && <div className="mb-2 text-xs text-slate-400">{labUnavailableMessage}</div>}
          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2" role="group" aria-label="ORB replay session">
              {ORB_REPLAY_SESSION_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setOrbReplaySession(option.id)}
                  disabled={labRunInProgress}
                  className={orbReplaySession === option.id ? activeToolClass : inactiveToolClass}
                  aria-pressed={orbReplaySession === option.id}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button type="button" onClick={runOrbReplay} disabled={labActionDisabled} className={inactiveToolClass}>
              <BarChart3 className="h-4 w-4" />
              ORB Replay
            </button>
            <button type="button" onClick={runAllocationExperiment} disabled={labActionDisabled} className={inactiveToolClass}>
              <Activity className="h-4 w-4" />
              Buying Power
            </button>
            <button type="button" onClick={runExitComparison} disabled={labActionDisabled} className={inactiveToolClass}>
              <Activity className="h-4 w-4" />
              Stop/DCA
            </button>
          </div>
          {simulationLabExperiments.length > 0 && (
            <div className="mt-3 space-y-1 text-[11px] text-slate-400">
              <div className="font-semibold uppercase text-slate-500">Lab catalog</div>
              {simulationLabExperiments.map((experiment, index) => {
                const endpointLabel = formatSimulationLabEndpoint(experiment);
                return (
                  <div
                    key={`${experiment.id || experiment.endpoint_path || experiment.label || 'experiment'}-${index}`}
                    className="border-t border-slate-800/80 pt-1 first:border-t-0"
                  >
                    <div className="truncate text-slate-300">
                      {experiment.label || formatSimulationLabExperimentId(experiment.id)}
                    </div>
                    <div className="truncate font-mono text-[10px] text-slate-500" title={endpointLabel}>
                      {endpointLabel}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {simulationLabResult && (
            <div className="mt-3 rounded-lg border border-slate-800 bg-slate-900/60 p-2">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="text-[11px] font-semibold uppercase text-slate-500">Last lab result</div>
                  <span className={formatSimulationLabResultScopeClass(simulationLabResultSymbolMismatch)}>
                    {formatSimulationLabResultScopeLabel(simulationLabResultSymbolMismatch)}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={forgetSimulationLabResult}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-slate-700 text-slate-400 hover:border-cyan-400/40 hover:text-cyan-100"
                  aria-label="Clear lab result"
                  title="Clear lab result"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="mt-1 truncate text-xs font-semibold text-slate-200">
                {formatSimulationLabResultTitle(simulationLabResult)}
              </div>
              <div className="mt-1 truncate text-[11px] text-slate-500">
                {formatSimulationLabResultMeta(simulationLabResult)}
              </div>
              {simulationLabResultSymbolMismatch && (
                <div className="mt-1 rounded-md border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-[11px] text-amber-200">
                  {formatSimulationLabResultMismatch(simulationLabResult, activeChartSymbol)}
                </div>
              )}
              <div className="mt-2 grid grid-cols-2 gap-2">
                {buildSimulationLabResultMetrics(simulationLabResult).map((metric) => (
                  <Metric key={metric.label} label={metric.label} value={metric.value} />
                ))}
              </div>
            </div>
          )}
          {labMessage && <p className="mt-3 text-xs text-slate-300">{labMessage}</p>}
        </section>
      )}
    </aside>
  ) : null;

  return (
    <div className="space-y-4" data-testid="chart-workspace">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">Chart Workspace</p>
          <h2 className="text-2xl font-bold text-white">{snapshot?.symbol || activeSymbol}</h2>
        </div>
        <form onSubmit={submitSymbol} className="flex items-center gap-2">
          <input
            value={symbolInput}
            onChange={(event) => setSymbolInput(event.target.value.toUpperCase())}
            maxLength={10}
            className="h-10 w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400"
            aria-label="Chart symbol"
          />
          <button
            type="submit"
            className="inline-flex h-10 items-center gap-2 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 text-sm font-semibold text-cyan-100 hover:bg-cyan-400/20"
          >
            <RefreshCw className="h-4 w-4" />
            Load
          </button>
        </form>
      </div>

      <section className={panelClass}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <BarChart3 className="h-4 w-4 text-cyan-300" />
            Layout
          </div>
          <button type="button" onClick={resetWorkspaceLayout} className={inactiveToolClass}>
            <RefreshCw className="h-4 w-4" />
            Reset
          </button>
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3 2xl:grid-cols-[minmax(0,1fr)_minmax(260px,auto)]">
          <div className="flex flex-wrap items-center gap-2">
            {LAYOUT_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                onClick={() => selectLayoutMode(option.id)}
                className={layoutMode === option.id ? activeToolClass : inactiveToolClass}
                aria-pressed={layoutMode === option.id}
              >
                {option.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {visiblePanelOptions.map((option) => (
              <label key={option.id} className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={panelVisibility[option.id]}
                  onChange={(event) => toggleWorkspacePanel(option.id, event.target.checked)}
                  className="h-3.5 w-3.5 accent-cyan-400"
                />
                {option.label}
              </label>
            ))}
          </div>
        </div>
        {layoutMessage && <p className="mt-3 text-xs text-slate-400">{layoutMessage}</p>}
      </section>

      <div className={workspaceGridClass}>
        {layoutMode === 'execution' && sidePanels}

        <section className={pricePanelClass}>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <label className={chartType === 'candlestick' ? activeRadioClass : inactiveRadioClass}>
                <input
                  type="radio"
                  name="chart-type"
                  checked={chartType === 'candlestick'}
                  onChange={() => selectChartType('candlestick')}
                  className="sr-only"
                />
                <CandlestickChart className="h-4 w-4" />
                Candle
              </label>
              <label className={chartType === 'line' ? activeRadioClass : inactiveRadioClass}>
                <input
                  type="radio"
                  name="chart-type"
                  checked={chartType === 'line'}
                  onChange={() => selectChartType('line')}
                  className="sr-only"
                />
                <LineChart className="h-4 w-4" />
                Line
              </label>
              <button type="button" onClick={resetWorkspacePreferences} className={inactiveToolClass}>
                <RefreshCw className="h-4 w-4" />
                Reset View
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Preset</span>
              {INDICATOR_PRESET_OPTIONS.map((preset) => (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyIndicatorPreset(preset)}
                  className={indicatorPreset === preset.id ? activeToolClass : inactiveToolClass}
                  aria-pressed={indicatorPreset === preset.id}
                >
                  {preset.label}
                </button>
              ))}
              {indicatorPreset === 'custom' && (
                <span className="text-xs font-semibold text-slate-500">Custom</span>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold uppercase text-slate-500">Range</span>
              {BAR_LIMIT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setBarLimit(option.value)}
                  className={barLimit === option.value ? activeToolClass : inactiveToolClass}
                  aria-pressed={barLimit === option.value}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showOrbOverlays}
                  onChange={(event) => toggleOrbOverlays(event.target.checked)}
                  className="h-3.5 w-3.5 accent-cyan-400"
                />
                ORB overlays
              </label>
              <label className="flex items-center gap-1.5 text-xs font-semibold text-slate-300">
                <input
                  type="checkbox"
                  checked={showVolume}
                  onChange={(event) => toggleVolume(event.target.checked)}
                  className="h-3.5 w-3.5 accent-cyan-400"
                />
                Volume
              </label>
              {ORB_OVERLAY_SESSION_OPTIONS.map((option) => (
                <label
                  key={option.id}
                  className={`flex items-center gap-1.5 text-xs ${
                    showOrbOverlays ? 'text-slate-300' : 'text-slate-600'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={orbOverlaySessions.includes(option.id)}
                    disabled={!showOrbOverlays}
                    onChange={(event) => toggleOrbOverlaySession(option.id, event.target.checked)}
                    className="h-3.5 w-3.5 accent-cyan-400 disabled:opacity-40"
                  />
                  {option.label}
                </label>
              ))}
              {INDICATOR_OPTIONS.map((option) => (
                <label key={option.id} className="flex items-center gap-1.5 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={selectedIndicators.includes(option.id)}
                    onChange={(event) => toggleIndicator(option.id, event.target.checked)}
                    className="h-3.5 w-3.5 accent-cyan-400"
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </div>
          {viewMessage && <p className="mb-3 text-xs text-slate-400">{viewMessage}</p>}

          {error && (
            <p role="alert" className="mb-3 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">
              {error}
            </p>
          )}

          {loading && !snapshot ? (
            <div className="grid h-[420px] place-items-center text-sm text-slate-400">Loading chart data</div>
          ) : (
            <PlotlyChart
              data={priceData}
              height={priceChartHeight}
              layout={{
                showlegend: true,
                legend: { orientation: 'h', y: 1.08, x: 0 },
                hovermode: 'x unified',
                xaxis: { rangeslider: { visible: false }, ...chartCrosshairAxis },
                yaxis: { title: 'Price', ...chartCrosshairAxis },
                yaxis2: showVolume
                  ? { title: 'Volume', overlaying: 'y', side: 'right', showgrid: false, rangemode: 'tozero' }
                  : undefined,
              }}
            />
          )}
        </section>

        {layoutMode !== 'execution' && sidePanels}
      </div>

      {panelVisibility.oscillators && (
        <section className={panelClass}>
          <PlotlyChart
            data={oscillatorData}
            height={oscillatorHeight}
            layout={{
              showlegend: true,
              legend: { orientation: 'h', y: 1.15, x: 0 },
              hovermode: 'x unified',
              xaxis: { ...chartCrosshairAxis },
              yaxis: { title: 'Oscillators', ...chartCrosshairAxis },
            }}
          />
        </section>
      )}
    </div>
  );
};

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-2">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function buildAllocationCandidates(symbol: string, lastClose: number) {
  const fallbackSymbols = ['QQQ', 'AAPL'];
  const symbols = Array.from(new Set([symbol.toUpperCase(), ...fallbackSymbols])).slice(0, 3);
  const baseNotional = Math.max(1000, Math.round(lastClose * 5));
  return symbols.map((candidateSymbol, index) => ({
    symbol: candidateSymbol,
    confidence: Math.max(0.35, 0.8 - index * 0.15),
    requested_notional: baseNotional,
    current_exposure: 0,
  }));
}

function buildPriceTraces(
  snapshot: ChartWorkspaceSnapshot | null,
  chartType: 'candlestick' | 'line',
  includeOrbOverlays = true,
  includeVolume = true,
  includeOrbOverlaySession: ChartWorkspaceOrbOverlaySession[] = DEFAULT_ORB_OVERLAY_SESSIONS,
) {
  if (!snapshot) return [];
  const x = snapshot.bars.map((bar) => bar.timestamp);
  const baseTrace = chartType === 'candlestick'
    ? {
        x,
        open: snapshot.bars.map((bar) => bar.open),
        high: snapshot.bars.map((bar) => bar.high),
        low: snapshot.bars.map((bar) => bar.low),
        close: snapshot.bars.map((bar) => bar.close),
        type: 'candlestick',
        name: snapshot.symbol,
        increasing: { line: { color: '#22c55e' } },
        decreasing: { line: { color: '#ef4444' } },
      }
    : {
        x,
        y: snapshot.bars.map((bar) => bar.close),
        type: 'scatter',
        mode: 'lines',
        name: snapshot.symbol,
        line: { color: '#22d3ee', width: 2 },
      };
  const volumeTrace = includeVolume
    ? {
        x,
        y: snapshot.bars.map((bar) => bar.volume),
        type: 'bar',
        name: 'Volume',
        yaxis: 'y2',
        marker: { color: 'rgba(148, 163, 184, 0.28)' },
        opacity: 0.35,
        hovertemplate: 'Volume %{y:,}<extra></extra>',
      }
    : null;
  const indicatorTraces = Object.entries(snapshot.indicators)
    .filter(([, indicator]) => indicator.kind === 'overlay')
    .map(([id, indicator]) => ({
      x: indicator.points.map((point) => point.timestamp),
      y: indicator.points.map((point) => point.value),
      type: 'scatter',
      mode: 'lines',
      name: indicator.label || id,
      line: { width: 1.5 },
    }));
  const enabledOrbOverlaySessions = new Set(includeOrbOverlaySession);
  const orbTraces = includeOrbOverlays
    ? snapshot.orb_overlays
        .filter((overlay) => enabledOrbOverlaySessions.has(overlay.session_id as ChartWorkspaceOrbOverlaySession))
        .flatMap((overlay) => [
          orbLineTrace(x, overlay.high, `${overlay.label} ${overlay.timeframe} high`, '#f59e0b'),
          orbLineTrace(x, overlay.low, `${overlay.label} ${overlay.timeframe} low`, '#38bdf8'),
        ])
    : [];
  return [baseTrace, ...(volumeTrace ? [volumeTrace] : []), ...indicatorTraces, ...orbTraces];
}

function buildOscillatorTraces(snapshot: ChartWorkspaceSnapshot | null) {
  if (!snapshot) return [];
  const traces: any[] = [];
  Object.entries(snapshot.indicators).forEach(([id, indicator]) => {
    if (indicator.kind !== 'oscillator') return;
    if (id.startsWith('rsi_')) {
      traces.push({
        x: indicator.points.map((point) => point.timestamp),
        y: indicator.points.map((point) => point.value),
        type: 'scatter',
        mode: 'lines',
        name: indicator.label,
        line: { color: '#a78bfa', width: 2 },
      });
    }
    if (id === 'macd') {
      traces.push(
        {
          x: indicator.points.map((point) => point.timestamp),
          y: indicator.points.map((point) => point.macd),
          type: 'scatter',
          mode: 'lines',
          name: 'MACD',
          line: { color: '#22d3ee', width: 1.5 },
        },
        {
          x: indicator.points.map((point) => point.timestamp),
          y: indicator.points.map((point) => point.signal),
          type: 'scatter',
          mode: 'lines',
          name: 'Signal',
          line: { color: '#f59e0b', width: 1.5 },
        },
        {
          x: indicator.points.map((point) => point.timestamp),
          y: indicator.points.map((point) => point.histogram),
          type: 'bar',
          name: 'Histogram',
          marker: { color: '#64748b' },
        },
      );
    }
  });
  return traces;
}

function buildIndicatorSnapshotMetrics(
  snapshot: ChartWorkspaceSnapshot | null,
  selectedIndicators: ChartWorkspaceIndicatorId[],
): ChartWorkspaceIndicatorSnapshotMetric[] {
  if (!snapshot) return [];
  const metrics: ChartWorkspaceIndicatorSnapshotMetric[] = [];

  selectedIndicators.forEach((id) => {
    const indicator = snapshot.indicators[id];
    if (!indicator) return;
    const latestPoint = findLatestIndicatorPoint(indicator.points);
    metrics.push({
      label: indicator.label || formatIndicatorOptionLabel(id),
      value: formatIndicatorSnapshotValue(id, latestPoint),
      timestamp: latestPoint?.timestamp,
    });
  });

  return metrics;
}

function findLatestIndicatorPoint(points: ChartWorkspaceIndicatorPoint[]) {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    const point = points[index];
    if (
      (point.value !== null && point.value !== undefined) ||
      (point.macd !== null && point.macd !== undefined) ||
      (point.signal !== null && point.signal !== undefined) ||
      (point.histogram !== null && point.histogram !== undefined)
    ) {
      return point;
    }
  }
  return undefined;
}

function formatIndicatorSnapshotValue(id: ChartWorkspaceIndicatorId, point?: ChartWorkspaceIndicatorPoint) {
  if (!point) return '--';
  if (id === 'macd') {
    return [
      `MACD ${formatIndicatorPointNumber(point.macd)}`,
      `Sig ${formatIndicatorPointNumber(point.signal)}`,
      `Hist ${formatIndicatorPointNumber(point.histogram)}`,
    ].join(' / ');
  }
  return formatIndicatorPointNumber(point.value);
}

function formatIndicatorPointNumber(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return '--';
  return Math.abs(value) >= 100 ? value.toFixed(2) : value.toFixed(4);
}

function orbLineTrace(x: string[], y: number, name: string, color: string) {
  return {
    x: [x[0], x[x.length - 1]],
    y: [y, y],
    type: 'scatter',
    mode: 'lines',
    name,
    line: { color, dash: 'dot', width: 1.5 },
  };
}

function formatOrbSessionStatus(status?: string) {
  if (!status) return '--';
  return status.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatOrbReadiness(readiness?: string) {
  if (!readiness) return '--';
  return readiness.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatOrbSessionLevelSummary(session: OrbSessionSummary) {
  const levels = session.levels ?? {};
  const lockedTimeframes = session.timeframes.filter((timeframe) => levels[timeframe]?.locked);
  if (lockedTimeframes.length) return `${lockedTimeframes.join(', ')} locked`;

  const validTimeframes = session.timeframes.filter((timeframe) => levels[timeframe]?.is_valid);
  if (validTimeframes.length) return `${validTimeframes.join(', ')} collecting`;

  return `${session.timeframes.join(', ')} configured`;
}

function formatOrbSessionReadinessDetail(session: OrbSessionSummary) {
  const parts: string[] = [];
  if (session.ready_timeframes.length) parts.push(`ready ${session.ready_timeframes.join(', ')}`);
  if (session.collecting_timeframes.length) parts.push(`collecting ${session.collecting_timeframes.join(', ')}`);
  if (session.missing_timeframes.length) parts.push(`missing ${session.missing_timeframes.join(', ')}`);
  return parts.length ? parts.join(' / ') : formatOrbReadiness(session.readiness);
}

function formatIndicatorPresetLabel(indicatorPreset: ChartWorkspaceIndicatorPresetId) {
  if (indicatorPreset === 'custom') return 'Custom';
  return INDICATOR_PRESET_OPTIONS.find((preset) => preset.id === indicatorPreset)?.label || 'Custom';
}

function formatSelectedIndicators(indicators: ChartWorkspaceIndicatorId[]) {
  if (!indicators.length) return 'None';
  return indicators
    .map(formatIndicatorOptionLabel)
    .join(', ');
}

function formatIndicatorOptionLabel(indicator: ChartWorkspaceIndicatorId) {
  return INDICATOR_OPTIONS.find((option) => option.id === indicator)?.label || indicator.toUpperCase();
}

function formatOrbOverlaySessionSummary(
  showOrbOverlays: boolean,
  orbOverlaySessions: ChartWorkspaceOrbOverlaySession[],
) {
  if (!showOrbOverlays) return 'Off';
  if (!orbOverlaySessions.length) return 'None';
  return orbOverlaySessions
    .map((session) => ORB_OVERLAY_SESSION_OPTIONS.find((option) => option.id === session)?.label || session)
    .join(', ');
}

function formatVolumeOverlay(showVolume: boolean) {
  return showVolume ? 'On' : 'Off';
}

function formatSimulationLabGate(
  simulationLabStatus: ChartWorkspaceSimulationLabStatus | null,
  simulationLabEnabled: boolean,
) {
  if (!simulationLabStatus) return 'Unknown';
  return simulationLabEnabled ? 'Enabled' : 'Hidden';
}

function formatChartType(chartType: ChartWorkspaceChartType) {
  return chartType === 'candlestick' ? 'Candle' : 'Line';
}

function formatLayoutMode(layoutMode: ChartWorkspaceLayoutMode) {
  return layoutMode.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatSimulationLabEndpoint(experiment: ChartWorkspaceSimulationLabExperiment) {
  const method = experiment.http_method || 'POST';
  const endpoint = experiment.endpoint_path || 'endpoint unavailable';
  const schemaVersion = experiment.result_schema_version || 'schema unknown';
  return `${method} ${endpoint} / ${schemaVersion}`;
}

function formatSimulationLabExperimentId(id?: string) {
  if (!id) return 'Experiment';
  return id.replace(/[_-]+/g, ' ').replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatSimulationLabResultTitle(result: ChartWorkspaceSimulationLabResult) {
  const schemaVersion = result.result.schema_version || 'schema_version unknown';
  return `${result.label} / ${schemaVersion}`;
}

function formatSimulationLabResultMeta(result: ChartWorkspaceSimulationLabResult) {
  const parts: string[] = [];
  if (result.symbol) parts.push(result.symbol);
  if (result.created_at) parts.push(formatSimulationLabResultTimestamp(result.created_at));
  return parts.length ? parts.join(' / ') : 'Session context unavailable';
}

function formatSimulationLabResultMismatch(result: ChartWorkspaceSimulationLabResult, activeChartSymbol: string) {
  return `Result symbol differs from active chart: ${result.symbol || 'Unknown'} vs ${activeChartSymbol}`;
}

function formatSimulationLabResultScopeLabel(hasSymbolMismatch: boolean) {
  return hasSymbolMismatch ? 'Different chart' : 'Current chart';
}

function formatSimulationLabResultScopeClass(hasSymbolMismatch: boolean) {
  const baseClass = 'rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase';
  return hasSymbolMismatch
    ? `${baseClass} border-amber-400/30 bg-amber-400/10 text-amber-200`
    : `${baseClass} border-emerald-400/30 bg-emerald-400/10 text-emerald-200`;
}

function formatSimulationLabResultTimestamp(value: string) {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return value;
  return timestamp.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function buildSimulationLabResultMetrics(result: ChartWorkspaceSimulationLabResult) {
  const summary = result.result.summary ?? {};
  const metrics = [
    {
      label: 'schema_version',
      value: result.result.schema_version || '--',
    },
    {
      label: 'run_id',
      value: result.result.run_id || '--',
    },
    {
      label: 'input_fp',
      value: formatSimulationLabFingerprint(result.result.input_fingerprint),
    },
  ];

  if (result.kind === 'orb_backtest') {
    metrics.push(
      { label: 'breakouts', value: formatSimulationLabResultMetric(summary.breakouts) },
      { label: 'sessions', value: formatSimulationLabResultMetric(summary.sessions) },
      { label: 'scored_breakouts', value: formatSimulationLabResultMetric(summary.scored_breakouts) },
      { label: 'avg_reward_r', value: formatSimulationLabResultMetric(summary.avg_reward_r_multiple) },
      { label: 'target_hits', value: formatSimulationLabResultMetric(summary.target_hits) },
      { label: 'stop_hits', value: formatSimulationLabResultMetric(summary.stop_hits) },
      { label: 'avg_realized_r', value: formatSimulationLabResultMetric(summary.avg_realized_r_multiple) },
    );
  }

  if (result.kind === 'buying_power_allocation') {
    metrics.push(
      { label: 'allocated_notional', value: formatSimulationLabResultMetric(summary.allocated_notional, 'currency') },
      { label: 'allocated_count', value: formatSimulationLabResultMetric(summary.allocated_count) },
      { label: 'fill_ratio', value: formatSimulationLabResultMetric(summary.fill_ratio, 'ratio') },
      { label: 'unfilled_requested', value: formatSimulationLabResultMetric(summary.unfilled_requested_notional, 'currency') },
      { label: 'position_limited', value: formatSimulationLabResultMetric(summary.position_limited_count) },
      { label: 'post_cap_fill', value: formatSimulationLabResultMetric(summary.post_cap_fill_ratio, 'ratio') },
    );
  }

  if (result.kind === 'stop_trailing_dca') {
    metrics.push(
      { label: 'best_plan', value: formatSimulationLabResultMetric(summary.best_plan) },
      { label: 'best_pnl', value: formatSimulationLabResultMetric(summary.best_pnl, 'currency') },
      { label: 'best_pnl_pct', value: formatSimulationLabResultMetric(summary.best_pnl_pct, 'percent') },
      { label: 'worst_pnl_pct', value: formatSimulationLabResultMetric(summary.worst_pnl_pct, 'percent') },
    );
  }

  return metrics;
}

function formatSimulationLabResultMetric(value: unknown, mode: 'plain' | 'currency' | 'percent' | 'ratio' = 'plain') {
  if (value === null || value === undefined || value === '') return '--';
  if (mode === 'currency' && typeof value === 'number') return `$${value.toLocaleString()}`;
  if (mode === 'percent' && typeof value === 'number') return `${value.toFixed(2)}%`;
  if (mode === 'ratio' && typeof value === 'number') return `${(value * 100).toFixed(2)}%`;
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value).replace(/[_-]+/g, ' ');
}

function formatSimulationLabFingerprint(value: unknown) {
  if (typeof value !== 'string' || !value) return '--';
  return value.length > 12 ? `${value.slice(0, 12)}...` : value;
}

function readChartWorkspaceLayout(): ChartWorkspaceLayoutState {
  if (typeof window === 'undefined') return cloneDefaultLayoutState();
  try {
    const storedLayout = window.localStorage.getItem(CHART_WORKSPACE_LAYOUT_STORAGE_KEY);
    if (!storedLayout) return cloneDefaultLayoutState();
    return normalizeChartWorkspaceLayout(JSON.parse(storedLayout));
  } catch {
    return cloneDefaultLayoutState();
  }
}

function persistChartWorkspaceLayout(layout: ChartWorkspaceLayoutState) {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(CHART_WORKSPACE_LAYOUT_STORAGE_KEY, JSON.stringify(layout));
    return true;
  } catch {
    return false;
  }
}

function clearChartWorkspaceLayout() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(CHART_WORKSPACE_LAYOUT_STORAGE_KEY);
  } catch {
    return;
  }
}

function readChartWorkspacePreferences(): ChartWorkspacePreferencesState {
  if (typeof window === 'undefined') return cloneDefaultPreferencesState();
  try {
    const storedPreferences = window.localStorage.getItem(CHART_WORKSPACE_PREFERENCES_STORAGE_KEY);
    if (!storedPreferences) return cloneDefaultPreferencesState();
    return normalizeChartWorkspacePreferences(JSON.parse(storedPreferences));
  } catch {
    return cloneDefaultPreferencesState();
  }
}

function persistChartWorkspacePreferences(preferences: ChartWorkspacePreferencesState) {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(CHART_WORKSPACE_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
    return true;
  } catch {
    return false;
  }
}

function clearChartWorkspacePreferences() {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(CHART_WORKSPACE_PREFERENCES_STORAGE_KEY);
  } catch {
    return;
  }
}

function readChartWorkspaceLabResult(): ChartWorkspaceSimulationLabResult | null {
  if (typeof window === 'undefined') return null;
  try {
    const storedResult = window.localStorage.getItem(CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY);
    if (!storedResult) return null;
    return normalizeChartWorkspaceLabResult(JSON.parse(storedResult));
  } catch {
    return null;
  }
}

function persistChartWorkspaceLabResult(result: ChartWorkspaceSimulationLabResult) {
  if (typeof window === 'undefined') return false;
  try {
    window.localStorage.setItem(CHART_WORKSPACE_LAB_RESULT_STORAGE_KEY, JSON.stringify(result));
    return true;
  } catch {
    return false;
  }
}

function clearChartWorkspaceLabResult() {
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
  return {
    layoutMode: isChartWorkspaceLayoutMode(value.layoutMode) ? value.layoutMode : DEFAULT_LAYOUT_STATE.layoutMode,
    panelVisibility: {
      snapshot: typeof storedPanels.snapshot === 'boolean' ? storedPanels.snapshot : DEFAULT_PANEL_VISIBILITY.snapshot,
      strategy:
        typeof storedPanels.strategy === 'boolean' ? storedPanels.strategy : DEFAULT_PANEL_VISIBILITY.strategy,
      lab: typeof storedPanels.lab === 'boolean' ? storedPanels.lab : DEFAULT_PANEL_VISIBILITY.lab,
      oscillators:
        typeof storedPanels.oscillators === 'boolean' ? storedPanels.oscillators : DEFAULT_PANEL_VISIBILITY.oscillators,
    },
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

function cloneDefaultLayoutState(): ChartWorkspaceLayoutState {
  return {
    layoutMode: DEFAULT_LAYOUT_STATE.layoutMode,
    panelVisibility: { ...DEFAULT_PANEL_VISIBILITY },
  };
}

function cloneDefaultPreferencesState(): ChartWorkspacePreferencesState {
  return {
    ...DEFAULT_PREFERENCES_STATE,
    selectedIndicators: [...DEFAULT_INDICATORS],
    orbOverlaySessions: [...DEFAULT_ORB_OVERLAY_SESSIONS],
  };
}

function isChartWorkspaceLayoutMode(value: unknown): value is ChartWorkspaceLayoutMode {
  return value === 'analysis' || value === 'execution' || value === 'research';
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

function normalizeChartWorkspaceSymbol(value: unknown) {
  if (typeof value !== 'string') return DEFAULT_PREFERENCES_STATE.activeSymbol;
  const symbol = value.trim().toUpperCase();
  return /^[A-Z0-9.-]{1,10}$/.test(symbol) ? symbol : DEFAULT_PREFERENCES_STATE.activeSymbol;
}

function normalizeChartWorkspaceIndicators(value: unknown) {
  if (!Array.isArray(value)) return [...DEFAULT_INDICATORS];
  return Array.from(new Set(value.filter(isChartWorkspaceIndicatorId)));
}

function inferIndicatorPreset(indicators: ChartWorkspaceIndicatorId[]): ChartWorkspaceIndicatorPresetId {
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

function getWorkspaceGridClass(layoutMode: ChartWorkspaceLayoutMode) {
  if (layoutMode === 'research') return 'grid grid-cols-1 gap-3';
  if (layoutMode === 'execution') return 'grid grid-cols-1 gap-3 2xl:grid-cols-[280px_minmax(0,1fr)]';
  return 'grid grid-cols-1 gap-3 2xl:grid-cols-[minmax(0,1fr)_280px]';
}

function getSidePanelClass(layoutMode: ChartWorkspaceLayoutMode) {
  if (layoutMode === 'research') return 'grid grid-cols-1 gap-3 2xl:grid-cols-2';
  if (layoutMode === 'execution') return 'space-y-3 2xl:order-first';
  return 'space-y-3';
}

const panelClass = 'rounded-lg border border-slate-800 bg-slate-950/80 p-3';
const activeToolClass =
  'inline-flex h-9 items-center gap-2 rounded-lg border border-cyan-300/60 bg-cyan-400/15 px-3 text-sm font-semibold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-60';
const inactiveToolClass =
  'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm font-semibold text-slate-300 hover:border-cyan-400/40 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-60';
const activeRadioClass = `${activeToolClass} cursor-pointer`;
const inactiveRadioClass = `${inactiveToolClass} cursor-pointer`;

export default ChartWorkspace;
