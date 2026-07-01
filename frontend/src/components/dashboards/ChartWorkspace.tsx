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
  ChartWorkspaceSnapshot,
  MarketMapContext,
  MarketMapProofMarker,
} from '@/types';
import {
  BAR_LIMIT_OPTIONS,
  DEFAULT_LAYOUT_STATE,
  INDICATOR_OPTIONS,
  INDICATOR_PRESET_OPTIONS,
  LAYOUT_OPTIONS,
  LOCAL_PREVIEW_FEED_MESSAGE,
  MARKET_MAP_LAYOUT_PRESETS,
  ORB_OVERLAY_SESSION_OPTIONS,
  ORB_REPLAY_SESSION_OPTIONS,
  PANEL_OPTIONS,
  activeRadioClass,
  activeToolClass,
  inactiveRadioClass,
  inactiveToolClass,
  panelClass,
} from './chart-workspace/chartWorkspaceConstants';
import { Metric } from './chart-workspace/Metric';
import {
  clearChartWorkspaceLabResult,
  clearChartWorkspaceLayout,
  clearChartWorkspacePreferences,
  inferMarketMapPreset,
  cloneDefaultPreferencesState,
  persistChartWorkspaceLabResult,
  persistChartWorkspaceLayout,
  persistChartWorkspacePreferences,
  readChartWorkspaceLabResult,
  readChartWorkspaceLayout,
  readChartWorkspacePreferences,
} from './chart-workspace/chartWorkspaceStorage';
import {
  buildMarketMapBias,
  buildSimulationLabResultMetrics,
  formatChartType,
  formatIndicatorPresetLabel,
  formatLayoutMode,
  formatMarketMapContextProximity,
  formatMarketMapContextStatus,
  formatMarketMapLevelPrice,
  formatNearestMarketMapLevel,
  formatOrbOverlaySessionSummary,
  formatOrbReadiness,
  formatOrbSessionLevelSummary,
  formatOrbSessionReadinessDetail,
  formatOrbSessionStatus,
  formatParserConfidence,
  formatProofMarkerTimestamp,
  formatSelectedIndicators,
  formatSimulationLabDisabledReason,
  formatSimulationLabEndpoint,
  formatSimulationLabExperimentId,
  formatSimulationLabGate,
  formatSimulationLabResultMeta,
  formatSimulationLabResultMismatch,
  formatSimulationLabResultScopeClass,
  formatSimulationLabResultScopeLabel,
  formatSimulationLabResultTitle,
  formatVolumeOverlay,
} from './chart-workspace/chartWorkspaceFormatters';
import type {
  ChartWorkspaceBarLimit,
  ChartWorkspaceChartType,
  ChartWorkspaceIndicatorPresetOption,
  ChartWorkspaceLayoutMode,
  ChartWorkspaceLayoutState,
  ChartWorkspaceOrbOverlaySession,
  ChartWorkspaceOrbReplaySession,
  ChartWorkspacePanelId,
  ChartWorkspacePreferencesState,
  ChartWorkspaceSimulationLabResult,
  ChartWorkspaceSimulationLabStatus,
  MarketMapLayoutPreset,
} from './chart-workspace/chartWorkspaceTypes';
import {
  buildFallbackChartWorkspaceSnapshot,
  buildFallbackMarketMapContext,
  buildFallbackProofMarkers,
} from './chart-workspace/chartWorkspaceFallbackData';
import {
  buildIndicatorSnapshotMetrics,
  buildOscillatorTraces,
  buildPriceTraces,
} from './chart-workspace/chartWorkspaceTraces';
import { PlotlyChart } from '../ui/PlotlyCharts';

const chartCrosshairAxis = {
  showspikes: true,
  spikemode: 'across',
  spikesnap: 'cursor',
  spikethickness: 1,
  spikecolor: '#f5b342',
};

type ChartWorkspaceMode = 'charting' | 'market-map';

const chartOutcomeCells = [
  { day: 'Mon', value: '+$420', tone: 'win' },
  { day: 'Tue', value: '-$85', tone: 'loss' },
  { day: 'Wed', value: '+$610', tone: 'win' },
  { day: 'Thu', value: '+$240', tone: 'win' },
  { day: 'Fri', value: '-$120', tone: 'loss' },
  { day: 'Sat', value: '+$0', tone: 'flat' },
  { day: 'Sun', value: '+$0', tone: 'flat' },
  { day: 'Mon', value: '+$530', tone: 'win' },
  { day: 'Tue', value: '+$180', tone: 'win' },
  { day: 'Wed', value: '-$260', tone: 'loss' },
  { day: 'Thu', value: '+$390', tone: 'win' },
  { day: 'Fri', value: '+$710', tone: 'win' },
  { day: 'Sat', value: '+$0', tone: 'flat' },
  { day: 'Sun', value: '+$0', tone: 'flat' },
];

const marketMapTiles = [
  { label: 'Upper resistance', value: '604.80', tone: 'red' },
  { label: 'Breakout shelf', value: '603.47', tone: 'gold' },
  { label: 'VWAP magnet', value: '601.20', tone: 'cyan' },
  { label: 'Lower support', value: '599.10', tone: 'green' },
  { label: 'Risk pocket', value: '596.85', tone: 'red' },
  { label: 'Liquidity pocket', value: '605.35', tone: 'gold' },
];

export const ChartWorkspace: React.FC<{ workspaceMode?: ChartWorkspaceMode }> = ({ workspaceMode = 'market-map' }) => {
  const [workspacePreferences, setWorkspacePreferences] =
    useState<ChartWorkspacePreferencesState>(readChartWorkspacePreferences);
  const workspacePreferencesRef = useRef(workspacePreferences);
  const [symbolInput, setSymbolInput] = useState(workspacePreferences.activeSymbol);
  const [workspaceLayout, setWorkspaceLayout] = useState<ChartWorkspaceLayoutState>(readChartWorkspaceLayout);
  const [snapshot, setSnapshot] = useState<ChartWorkspaceSnapshot | null>(null);
  const [marketMapContext, setMarketMapContext] = useState<MarketMapContext | null>(null);
  const [marketMapContextMessage, setMarketMapContextMessage] = useState('');
  const [proofMarkers, setProofMarkers] = useState<MarketMapProofMarker[]>([]);
  const [proofMarkerMessage, setProofMarkerMessage] = useState('');
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
  const [feedMessage, setFeedMessage] = useState('');
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
        if (!cancelled) {
          setSnapshot(nextSnapshot);
          setFeedMessage('');
        }
      } catch {
        if (!cancelled) {
          setError('');
          setSnapshot(buildFallbackChartWorkspaceSnapshot(activeSymbol, selectedIndicators, barLimit));
          setFeedMessage(LOCAL_PREVIEW_FEED_MESSAGE);
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

  useEffect(() => {
    let cancelled = false;
    setProofMarkerMessage('');
    api.getMarketMapProofMarkers(activeSymbol)
      .then((payload) => {
        if (cancelled) return;
        setProofMarkers(payload.items ?? []);
      })
      .catch(() => {
        if (cancelled) return;
        setProofMarkers(buildFallbackProofMarkers(activeSymbol, barLimit));
        setProofMarkerMessage('Local proof preview');
      });
    return () => {
      cancelled = true;
    };
  }, [activeSymbol, barLimit]);

  useEffect(() => {
    let cancelled = false;
    setMarketMapContextMessage('');
    api.getMarketMapContext(activeSymbol)
      .then((context) => {
        if (cancelled) return;
        setMarketMapContext(context);
      })
      .catch(() => {
        if (cancelled) return;
        setMarketMapContext(buildFallbackMarketMapContext(activeSymbol, barLimit));
        setMarketMapContextMessage('Local Edge context preview');
      });
    return () => {
      cancelled = true;
    };
  }, [activeSymbol, barLimit]);

  const priceData = useMemo(
    () => buildPriceTraces(snapshot, chartType, showOrbOverlays, showVolume, orbOverlaySessions, proofMarkers),
    [snapshot, chartType, showOrbOverlays, showVolume, orbOverlaySessions, proofMarkers],
  );
  const oscillatorData = useMemo(() => buildOscillatorTraces(snapshot), [snapshot]);
  const indicatorSnapshotMetrics = useMemo(
    () => buildIndicatorSnapshotMetrics(snapshot, selectedIndicators),
    [snapshot, selectedIndicators],
  );
  const latestBar = snapshot?.bars[snapshot.bars.length - 1];
  const { marketMapPreset, layoutMode, panelVisibility } = workspaceLayout;
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
  const isChartingWorkspace = workspaceMode === 'charting';
  const oscillatorHeight = layoutMode === 'research' ? 280 : 240;
  const priceChartHeight = isChartingWorkspace
    ? layoutMode === 'research'
      ? 680
      : 620
    : layoutMode === 'research'
      ? 600
      : 540;
  const labActionsReady = Boolean(snapshot?.bars.length && latestBar);
  const labActionDisabled = labRunInProgress || !labActionsReady;
  const labUnavailableMessage = 'Load chart data to run Simulation Lab.';
  const activeChartSymbol = snapshot?.symbol || activeSymbol;
  const workspaceCopy = isChartingWorkspace
    ? {
      eyebrow: 'Charting command deck',
      heading: `${activeChartSymbol} signal chart`,
      controlsTitle: 'Docked Chart Controls',
      layoutLabel: 'Chart layout presets',
      briefingTitle: 'Chart Outcome Strip',
    }
    : {
      eyebrow: 'Market map command deck',
      heading: `${activeChartSymbol} support / resistance map`,
      controlsTitle: 'Market Map Layout',
      layoutLabel: 'Market Map layout presets',
      briefingTitle: 'Market Structure Strip',
    };
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
      marketMapPreset: inferMarketMapPreset(nextLayoutMode, workspaceLayout.panelVisibility),
      layoutMode: nextLayoutMode,
    });
  };

  const applyMarketMapPreset = (presetId: MarketMapLayoutPreset) => {
    const preset = MARKET_MAP_LAYOUT_PRESETS.find((option) => option.id === presetId);
    if (!preset) return;
    updateWorkspaceLayout({
      marketMapPreset: preset.id,
      layoutMode: preset.layoutMode,
      panelVisibility: { ...preset.panelVisibility },
    });
  };

  const toggleWorkspacePanel = (panel: ChartWorkspacePanelId, checked: boolean) => {
    const nextPanelVisibility = {
      ...workspaceLayout.panelVisibility,
      [panel]: checked,
    };
    updateWorkspaceLayout({
      ...workspaceLayout,
      marketMapPreset: inferMarketMapPreset(workspaceLayout.layoutMode, nextPanelVisibility),
      panelVisibility: nextPanelVisibility,
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

      {panelVisibility.snapshot && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <LineChart className="h-4 w-4 text-emerald-300" />
            Market Map Briefing
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Metric label="Bias" value={buildMarketMapBias(snapshot)} />
            <Metric label="Level proximity" value={formatNearestMarketMapLevel(snapshot)} />
          </div>
          <div className="mt-3 text-[11px] font-semibold uppercase text-slate-500">Morning Levels</div>
          <div className="mt-2 space-y-1">
            {(snapshot?.levels?.items ?? []).slice(0, 8).map((level) => (
              <div key={level.id} className="flex items-center justify-between gap-2 border-t border-slate-800/80 pt-1 first:border-t-0">
                <span className="truncate text-slate-300">{level.label}</span>
                <span className="shrink-0 font-mono text-slate-100">{formatMarketMapLevelPrice(level.price)}</span>
              </div>
            ))}
            {!(snapshot?.levels?.items ?? []).length && (
              <div className="text-[11px] text-slate-500">No support/resistance levels loaded</div>
            )}
          </div>
        </section>
      )}

      {panelVisibility.snapshot && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Activity className="h-4 w-4 text-cyan-300" />
            Edge Confidence
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Metric label="Status" value={formatMarketMapContextStatus(marketMapContext?.status)} />
            <Metric label="Score" value={marketMapContext ? marketMapContext.score : '--'} />
            <Metric label="Bias" value={formatMarketMapContextStatus(marketMapContext?.directional_bias)} />
            <Metric label="Nearest" value={formatMarketMapContextProximity(marketMapContext)} />
          </div>
          <div className="mt-3 space-y-1 text-[11px] text-slate-400">
            {(marketMapContext?.reasons ?? []).map((reason) => (
              <div key={reason} className="rounded border border-slate-800 bg-slate-900/60 px-2 py-1 text-slate-300">
                {reason}
              </div>
            ))}
            {(marketMapContext?.warnings ?? []).map((warning) => (
              <div key={warning} className="rounded border border-amber-400/30 bg-amber-400/10 px-2 py-1 text-amber-100">
                {warning}
              </div>
            ))}
            {!marketMapContext && (
              <div className="text-slate-500">{marketMapContextMessage || 'Edge context loading'}</div>
            )}
          </div>
        </section>
      )}

      {panelVisibility.snapshot && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <Activity className="h-4 w-4 text-amber-300" />
            Alert Proof
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Metric label="Markers" value={proofMarkers.length} />
            <Metric label="parser confidence" value={formatParserConfidence(proofMarkers[0]?.parser_confidence)} />
          </div>
          <div className="mt-3 space-y-1 text-[11px] text-slate-400">
            {proofMarkers.slice(0, 5).map((marker) => (
              <div key={marker.id} className="border-t border-slate-800/80 pt-1 first:border-t-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-slate-300">{marker.label}</span>
                  <span className="shrink-0 text-slate-500">{formatProofMarkerTimestamp(marker.timestamp)}</span>
                </div>
                <div className="truncate text-slate-500">
                  {marker.kind} / {marker.status} / parser confidence {formatParserConfidence(marker.parser_confidence)}
                </div>
                {marker.raw_text && <div className="truncate text-slate-500">{marker.raw_text}</div>}
              </div>
            ))}
            {!proofMarkers.length && (
              <div className="text-slate-500">{proofMarkerMessage || 'No alert proof markers for this symbol'}</div>
            )}
          </div>
        </section>
      )}

      {panelVisibility.snapshot && (
        <section className={panelClass}>
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
            <CandlestickChart className="h-4 w-4 text-violet-300" />
            Options Cockpit
          </div>
          <div className="rounded border border-amber-400/30 bg-amber-400/10 p-2 text-xs text-amber-100">
            options market data unavailable; contract context remains review-only
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
            <Metric label="bid/ask spread" value="--" />
            <Metric label="liquidity warning" value="Market data required" />
            <Metric label="delta target" value="--" />
            <Metric label="contract status" value="Review" />
          </div>
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
            <Metric label="Lab reason" value={formatSimulationLabDisabledReason(simulationLabStatus)} />
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
    <div
      className={`edge-chart-workspace edge-chart-workspace-${workspaceMode} space-y-4`}
      data-testid="chart-workspace"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-cyan-300">{workspaceCopy.eyebrow}</p>
          <h2 className="text-2xl font-bold text-white">{workspaceCopy.heading}</h2>
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

      <section className="edge-workspace-command-row" aria-label={workspaceCopy.briefingTitle}>
        {isChartingWorkspace ? (
          <>
            <article className="edge-workspace-command-card edge-tone-cyan">
              <span>Trend gate</span>
              <strong>Permission line rising</strong>
              <small>Sentinel Edge keeps buys gated until support confirms.</small>
            </article>
            <article className="edge-workspace-command-card edge-tone-green">
              <span>Outcome counter</span>
              <strong>8W / 3L</strong>
              <small>Current bot PNL calendar window.</small>
            </article>
            <article className="edge-workspace-command-card edge-tone-gold">
              <span>P&amp;L pulse</span>
              <strong>+$2.6K week</strong>
              <small>View can switch day, week, month.</small>
            </article>
            <article className="edge-workspace-command-card edge-tone-red">
              <span>Risk pressure</span>
              <strong>Reduce over 2.18R</strong>
              <small>Directive bus can throttle bots without brokerage actions.</small>
            </article>
          </>
        ) : (
          marketMapTiles.slice(0, 4).map((tile) => (
            <article key={tile.label} className={`edge-workspace-command-card edge-tone-${tile.tone}`}>
              <span>{tile.label}</span>
              <strong>{tile.value}</strong>
              <small>Live support / resistance map level.</small>
            </article>
          ))
        )}
      </section>

      <section className={panelClass}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-white">
            <BarChart3 className="h-4 w-4 text-cyan-300" />
            {workspaceCopy.controlsTitle}
          </div>
          <button type="button" onClick={resetWorkspaceLayout} className={inactiveToolClass}>
            <RefreshCw className="h-4 w-4" />
            Reset
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2" aria-label={workspaceCopy.layoutLabel}>
          {MARKET_MAP_LAYOUT_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={marketMapPreset === preset.id ? activeToolClass : inactiveToolClass}
              onClick={() => applyMarketMapPreset(preset.id)}
              title={preset.detail}
              aria-pressed={marketMapPreset === preset.id}
            >
              {preset.label}
            </button>
          ))}
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
          {(viewMessage || feedMessage) && (
            <p className="mb-3 text-xs text-slate-400">{viewMessage || feedMessage}</p>
          )}

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

      {isChartingWorkspace ? (
        <section className="edge-chart-outcome-deck" aria-label="Charting outcome and PNL tracking">
          <article className="edge-chart-calendar-card">
            <div className="edge-chart-mini-head">
              <span>Bot P&amp;L calendar</span>
              <strong>Sentinel Pulse</strong>
            </div>
            <div className="edge-chart-calendar-grid">
              {chartOutcomeCells.map((cell, index) => (
                <div key={`${cell.day}-${index}`} className={`edge-chart-calendar-cell ${cell.tone}`}>
                  <small>{cell.day}</small>
                  <strong>{cell.value}</strong>
                </div>
              ))}
            </div>
          </article>
          <article className="edge-chart-winloss-card">
            <div className="edge-chart-mini-head">
              <span>Win / loss counter</span>
              <strong>72.7%</strong>
            </div>
            <div className="edge-chart-donut" aria-label="8 wins and 3 losses">
              <span>8W</span>
              <small>3L</small>
            </div>
          </article>
          <article className="edge-chart-directive-card">
            <div className="edge-chart-mini-head">
              <span>Directive posture</span>
              <strong>Calculation only</strong>
            </div>
            <div className="edge-chart-directive-list">
              <div><span>Breakout</span><strong>Watch</strong></div>
              <div><span>Support</span><strong className="edge-green">Holding</strong></div>
              <div><span>Risk</span><strong className="edge-gold">Reduce size</strong></div>
            </div>
          </article>
        </section>
      ) : (
        <section className="edge-market-map-deck" aria-label="Market map breadth and levels">
          <article className="edge-market-ladder-card">
            <div className="edge-chart-mini-head">
              <span>Level ladder</span>
              <strong>{activeChartSymbol}</strong>
            </div>
            <div className="edge-market-ladder">
              {marketMapTiles.map((tile) => (
                <div key={tile.label} className={`edge-market-ladder-row edge-tone-${tile.tone}`}>
                  <span>{tile.label}</span>
                  <strong>{tile.value}</strong>
                </div>
              ))}
            </div>
          </article>
          <article className="edge-market-flow-card">
            <div className="edge-chart-mini-head">
              <span>Map bias</span>
              <strong>{buildMarketMapBias(snapshot)}</strong>
            </div>
            <div className="edge-market-flow-grid">
              <div><span>Nearest level</span><strong>{formatNearestMarketMapLevel(snapshot)}</strong></div>
              <div><span>Context</span><strong>{formatMarketMapContextStatus(marketMapContext?.status)}</strong></div>
              <div><span>Proof markers</span><strong>{proofMarkers.length}</strong></div>
              <div><span>ORB readiness</span><strong>{formatOrbReadiness(orbSessionStatus?.active_readiness)}</strong></div>
            </div>
          </article>
        </section>
      )}

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

function getWorkspaceGridClass(layoutMode: ChartWorkspaceLayoutMode) {
  if (layoutMode === 'research') return 'grid grid-cols-1 items-start gap-3';
  if (layoutMode === 'execution') return 'grid grid-cols-1 items-start gap-3 2xl:grid-cols-[280px_minmax(0,1fr)]';
  return 'grid grid-cols-1 items-start gap-3 2xl:grid-cols-[minmax(0,1fr)_280px]';
}

function getSidePanelClass(layoutMode: ChartWorkspaceLayoutMode) {
  if (layoutMode === 'research') return 'grid grid-cols-1 gap-3 2xl:grid-cols-2';
  if (layoutMode === 'execution') return 'space-y-3 2xl:order-first 2xl:max-h-[760px] 2xl:overflow-y-auto 2xl:pr-1';
  return 'space-y-3 2xl:max-h-[760px] 2xl:overflow-y-auto 2xl:pr-1';
}

export default ChartWorkspace;
