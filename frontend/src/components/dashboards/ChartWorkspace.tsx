import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  CandlestickChart,
  FlaskConical,
  LineChart,
  RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { ChartWorkspaceIndicatorId, ChartWorkspaceSnapshot, OrbSessionSummary } from '@/types';
import { PlotlyChart } from '../ui/PlotlyCharts';

const INDICATOR_OPTIONS: { id: ChartWorkspaceIndicatorId; label: string }[] = [
  { id: 'ema_9', label: 'EMA 9' },
  { id: 'ema_20', label: 'EMA 20' },
  { id: 'sma_20', label: 'SMA 20' },
  { id: 'rsi_14', label: 'RSI 14' },
  { id: 'macd', label: 'MACD' },
];

const DEFAULT_INDICATORS: ChartWorkspaceIndicatorId[] = ['ema_9', 'ema_20', 'sma_20', 'rsi_14', 'macd'];

type ChartWorkspaceLayoutMode = 'analysis' | 'execution' | 'research';
type ChartWorkspacePanelId = 'snapshot' | 'lab' | 'oscillators';
type ChartWorkspaceChartType = 'candlestick' | 'line';
type ChartWorkspaceBarLimit = 120 | 240 | 390;
type ChartWorkspaceOrbReplaySession = 'market_open' | 'premarket_30m';

interface ChartWorkspacePanelVisibility {
  snapshot: boolean;
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
  selectedIndicators: ChartWorkspaceIndicatorId[];
  barLimit: ChartWorkspaceBarLimit;
  showOrbOverlays: boolean;
}

interface ChartWorkspaceSimulationLabExperiment {
  id?: string;
  label?: string;
  runnable?: boolean;
  http_method?: string;
  endpoint_path?: string;
  result_schema_version?: string;
}

interface ChartWorkspaceSimulationLabStatus {
  enabled?: boolean;
  default_hidden?: boolean;
  experiments?: ChartWorkspaceSimulationLabExperiment[];
}

const CHART_WORKSPACE_LAYOUT_STORAGE_KEY = 'sentinel-edge.chart-workspace.layout.v1';
const CHART_WORKSPACE_PREFERENCES_STORAGE_KEY = 'sentinel-edge.chart-workspace.preferences.v1';

const DEFAULT_PANEL_VISIBILITY: ChartWorkspacePanelVisibility = {
  snapshot: true,
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
  selectedIndicators: DEFAULT_INDICATORS,
  barLimit: 240,
  showOrbOverlays: true,
};

const LAYOUT_OPTIONS: { id: ChartWorkspaceLayoutMode; label: string }[] = [
  { id: 'analysis', label: 'Analysis' },
  { id: 'execution', label: 'Execution' },
  { id: 'research', label: 'Research' },
];

const PANEL_OPTIONS: { id: ChartWorkspacePanelId; label: string }[] = [
  { id: 'snapshot', label: 'Snapshot' },
  { id: 'lab', label: 'Lab' },
  { id: 'oscillators', label: 'Oscillators' },
];

const BAR_LIMIT_OPTIONS: { value: ChartWorkspaceBarLimit; label: string }[] = [
  { value: 120, label: '120 bars' },
  { value: 240, label: '240 bars' },
  { value: 390, label: '390 bars' },
];

const ORB_REPLAY_SESSION_OPTIONS: {
  id: ChartWorkspaceOrbReplaySession;
  label: string;
  timeframeMinutes: 30;
}[] = [
  { id: 'market_open', label: 'Market open', timeframeMinutes: 30 },
  { id: 'premarket_30m', label: 'Premarket 30m', timeframeMinutes: 30 },
];

export const ChartWorkspace: React.FC = () => {
  const [workspacePreferences, setWorkspacePreferences] =
    useState<ChartWorkspacePreferencesState>(readChartWorkspacePreferences);
  const workspacePreferencesRef = useRef(workspacePreferences);
  const [symbolInput, setSymbolInput] = useState(workspacePreferences.activeSymbol);
  const [workspaceLayout, setWorkspaceLayout] = useState<ChartWorkspaceLayoutState>(readChartWorkspaceLayout);
  const [snapshot, setSnapshot] = useState<ChartWorkspaceSnapshot | null>(null);
  const [simulationLabStatus, setSimulationLabStatus] = useState<ChartWorkspaceSimulationLabStatus | null>(null);
  const [orbReplaySession, setOrbReplaySession] = useState<ChartWorkspaceOrbReplaySession>('market_open');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [labMessage, setLabMessage] = useState('');
  const [layoutMessage, setLayoutMessage] = useState('');
  const [viewMessage, setViewMessage] = useState('');
  const { activeSymbol, chartType, selectedIndicators, barLimit, showOrbOverlays } = workspacePreferences;

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
    () => buildPriceTraces(snapshot, chartType, showOrbOverlays),
    [snapshot, chartType, showOrbOverlays],
  );
  const oscillatorData = useMemo(() => buildOscillatorTraces(snapshot), [snapshot]);
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
  const hasSidePanels = panelVisibility.snapshot || (panelVisibility.lab && simulationLabEnabled);
  const workspaceGridClass = getWorkspaceGridClass(layoutMode);
  const sidePanelClass = getSidePanelClass(layoutMode);
  const pricePanelClass = `${panelClass} ${layoutMode === 'execution' ? '2xl:order-last' : ''}`;
  const selectedOrbReplaySession =
    ORB_REPLAY_SESSION_OPTIONS.find((option) => option.id === orbReplaySession) || ORB_REPLAY_SESSION_OPTIONS[0];
  const orbSessionStatus = snapshot?.orb_session_status;
  const orbSessionEntries = useMemo(() => Object.values(orbSessionStatus?.sessions ?? {}), [orbSessionStatus]);
  const oscillatorHeight = layoutMode === 'research' ? 260 : 220;
  const priceChartHeight = layoutMode === 'research' ? 500 : 430;

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
        selectedIndicators: nextIndicators,
      };
    });
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

  const runOrbReplay = async () => {
    if (!snapshot?.bars.length) return;
    setLabMessage(`Running ${selectedOrbReplaySession.label} ORB replay`);
    try {
      const result = await api.runSimulationLabOrbBacktest({
        symbol: snapshot.symbol,
        session_id: orbReplaySession,
        timeframe_minutes: selectedOrbReplaySession.timeframeMinutes,
        breakout_side: 'both',
        bars: snapshot.bars,
      });
      setLabMessage(`${selectedOrbReplaySession.label} ORB replay: ${result.summary?.breakouts ?? 0} breakouts`);
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'ORB replay unavailable');
    }
  };

  const runAllocationExperiment = async () => {
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
      setLabMessage(
        `Allocation: $${Number(result.summary?.allocated_notional ?? 0).toLocaleString()} across ${
          result.summary?.allocated_count ?? 0
        } candidates`,
      );
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'Allocation experiment unavailable');
    }
  };

  const runExitComparison = async () => {
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
      setLabMessage(`Exit comparison: ${result.summary?.best_plan ?? 'n/a'} best`);
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'Exit comparison unavailable');
    }
  };

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
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {panelVisibility.lab && simulationLabEnabled && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <FlaskConical className="h-4 w-4 text-amber-300" />
            Simulation Lab
          </div>
          <div className="flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2" role="group" aria-label="ORB replay session">
              {ORB_REPLAY_SESSION_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setOrbReplaySession(option.id)}
                  className={orbReplaySession === option.id ? activeToolClass : inactiveToolClass}
                  aria-pressed={orbReplaySession === option.id}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <button type="button" onClick={runOrbReplay} className={inactiveToolClass}>
              <BarChart3 className="h-4 w-4" />
              ORB Replay
            </button>
            <button type="button" onClick={runAllocationExperiment} className={inactiveToolClass}>
              <Activity className="h-4 w-4" />
              Buying Power
            </button>
            <button type="button" onClick={runExitComparison} className={inactiveToolClass}>
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
                xaxis: { rangeslider: { visible: false } },
                yaxis: { title: 'Price' },
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
              yaxis: { title: 'Oscillators' },
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
      <div className="mt-1 text-sm font-semibold text-slate-100">{value}</div>
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
  const orbTraces = includeOrbOverlays
    ? snapshot.orb_overlays.flatMap((overlay) => [
        orbLineTrace(x, overlay.high, `${overlay.label} ${overlay.timeframe} high`, '#f59e0b'),
        orbLineTrace(x, overlay.low, `${overlay.label} ${overlay.timeframe} low`, '#38bdf8'),
      ])
    : [];
  return [baseTrace, ...indicatorTraces, ...orbTraces];
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

function formatOrbSessionLevelSummary(session: OrbSessionSummary) {
  const levels = session.levels ?? {};
  const lockedTimeframes = session.timeframes.filter((timeframe) => levels[timeframe]?.locked);
  if (lockedTimeframes.length) return `${lockedTimeframes.join(', ')} locked`;

  const validTimeframes = session.timeframes.filter((timeframe) => levels[timeframe]?.is_valid);
  if (validTimeframes.length) return `${validTimeframes.join(', ')} collecting`;

  return `${session.timeframes.join(', ')} configured`;
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

function normalizeChartWorkspaceLayout(value: unknown): ChartWorkspaceLayoutState {
  if (!isRecord(value)) return cloneDefaultLayoutState();
  const storedPanels = isRecord(value.panelVisibility) ? value.panelVisibility : {};
  return {
    layoutMode: isChartWorkspaceLayoutMode(value.layoutMode) ? value.layoutMode : DEFAULT_LAYOUT_STATE.layoutMode,
    panelVisibility: {
      snapshot: typeof storedPanels.snapshot === 'boolean' ? storedPanels.snapshot : DEFAULT_PANEL_VISIBILITY.snapshot,
      lab: typeof storedPanels.lab === 'boolean' ? storedPanels.lab : DEFAULT_PANEL_VISIBILITY.lab,
      oscillators:
        typeof storedPanels.oscillators === 'boolean' ? storedPanels.oscillators : DEFAULT_PANEL_VISIBILITY.oscillators,
    },
  };
}

function normalizeChartWorkspacePreferences(value: unknown): ChartWorkspacePreferencesState {
  if (!isRecord(value)) return cloneDefaultPreferencesState();
  return {
    activeSymbol: normalizeChartWorkspaceSymbol(value.activeSymbol),
    chartType: isChartWorkspaceChartType(value.chartType) ? value.chartType : DEFAULT_PREFERENCES_STATE.chartType,
    selectedIndicators: normalizeChartWorkspaceIndicators(value.selectedIndicators),
    barLimit: isChartWorkspaceBarLimit(value.barLimit) ? value.barLimit : DEFAULT_PREFERENCES_STATE.barLimit,
    showOrbOverlays:
      typeof value.showOrbOverlays === 'boolean'
        ? value.showOrbOverlays
        : DEFAULT_PREFERENCES_STATE.showOrbOverlays,
  };
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

function normalizeChartWorkspaceSymbol(value: unknown) {
  if (typeof value !== 'string') return DEFAULT_PREFERENCES_STATE.activeSymbol;
  const symbol = value.trim().toUpperCase();
  return /^[A-Z0-9.-]{1,10}$/.test(symbol) ? symbol : DEFAULT_PREFERENCES_STATE.activeSymbol;
}

function normalizeChartWorkspaceIndicators(value: unknown) {
  if (!Array.isArray(value)) return [...DEFAULT_INDICATORS];
  const indicators = Array.from(new Set(value.filter(isChartWorkspaceIndicatorId)));
  return indicators.length ? indicators : [...DEFAULT_INDICATORS];
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
  'inline-flex h-9 items-center gap-2 rounded-lg border border-cyan-300/60 bg-cyan-400/15 px-3 text-sm font-semibold text-cyan-100';
const inactiveToolClass =
  'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm font-semibold text-slate-300 hover:border-cyan-400/40 hover:text-cyan-100';
const activeRadioClass = `${activeToolClass} cursor-pointer`;
const inactiveRadioClass = `${inactiveToolClass} cursor-pointer`;

export default ChartWorkspace;
