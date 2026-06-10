import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  BarChart3,
  CandlestickChart,
  FlaskConical,
  LineChart,
  RefreshCw,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { ChartWorkspaceIndicatorId, ChartWorkspaceSnapshot } from '@/types';
import { PlotlyChart } from '../ui/PlotlyCharts';

const INDICATOR_OPTIONS: { id: ChartWorkspaceIndicatorId; label: string }[] = [
  { id: 'ema_9', label: 'EMA 9' },
  { id: 'ema_20', label: 'EMA 20' },
  { id: 'sma_20', label: 'SMA 20' },
  { id: 'rsi_14', label: 'RSI 14' },
  { id: 'macd', label: 'MACD' },
];

const DEFAULT_INDICATORS: ChartWorkspaceIndicatorId[] = ['ema_9', 'ema_20', 'sma_20', 'rsi_14', 'macd'];

export const ChartWorkspace: React.FC = () => {
  const [symbolInput, setSymbolInput] = useState('SPY');
  const [activeSymbol, setActiveSymbol] = useState('SPY');
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');
  const [selectedIndicators, setSelectedIndicators] = useState<ChartWorkspaceIndicatorId[]>(DEFAULT_INDICATORS);
  const [snapshot, setSnapshot] = useState<ChartWorkspaceSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [labMessage, setLabMessage] = useState('');

  useEffect(() => {
    let cancelled = false;
    const loadSnapshot = async () => {
      setLoading(true);
      setError('');
      try {
        const nextSnapshot = await api.getChartWorkspace(activeSymbol, {
          indicators: selectedIndicators,
          limit: 240,
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
  }, [activeSymbol, selectedIndicators]);

  const priceData = useMemo(() => buildPriceTraces(snapshot, chartType), [snapshot, chartType]);
  const oscillatorData = useMemo(() => buildOscillatorTraces(snapshot), [snapshot]);
  const latestBar = snapshot?.bars[snapshot.bars.length - 1];

  const submitSymbol = (event: React.FormEvent) => {
    event.preventDefault();
    const symbol = symbolInput.trim().toUpperCase();
    if (!symbol || !/^[A-Z0-9.-]{1,10}$/.test(symbol)) {
      setError('Enter a valid symbol');
      return;
    }
    setActiveSymbol(symbol);
  };

  const toggleIndicator = (indicator: ChartWorkspaceIndicatorId, checked: boolean) => {
    setSelectedIndicators((current) => {
      if (checked) return current.includes(indicator) ? current : [...current, indicator];
      return current.filter((item) => item !== indicator);
    });
  };

  const runOrbReplay = async () => {
    if (!snapshot?.bars.length) return;
    setLabMessage('Running ORB replay');
    try {
      const result = await api.runSimulationLabOrbBacktest({
        symbol: snapshot.symbol,
        session_id: 'market_open',
        timeframe_minutes: 30,
        breakout_side: 'both',
        bars: snapshot.bars,
      });
      setLabMessage(`ORB replay: ${result.summary?.breakouts ?? 0} breakouts`);
    } catch (err) {
      setLabMessage(err instanceof Error ? err.message : 'ORB replay unavailable');
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

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setChartType('candlestick')}
                className={chartType === 'candlestick' ? activeToolClass : inactiveToolClass}
                aria-pressed={chartType === 'candlestick'}
              >
                <CandlestickChart className="h-4 w-4" />
                Candle
              </button>
              <button
                type="button"
                onClick={() => setChartType('line')}
                className={chartType === 'line' ? activeToolClass : inactiveToolClass}
                aria-pressed={chartType === 'line'}
              >
                <LineChart className="h-4 w-4" />
                Line
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
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
              height={430}
              layout={{
                showlegend: true,
                legend: { orientation: 'h', y: 1.08, x: 0 },
                xaxis: { rangeslider: { visible: false } },
                yaxis: { title: 'Price' },
              }}
            />
          )}
        </section>

        <aside className="space-y-3">
          <section className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <Activity className="h-4 w-4 text-cyan-300" />
              Snapshot
            </div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <Metric label="Last" value={latestBar ? `$${latestBar.close.toFixed(2)}` : '--'} />
              <Metric label="Bars" value={snapshot?.summary.bar_count ?? '--'} />
              <Metric label="Indicators" value={snapshot?.summary.indicator_count ?? '--'} />
              <Metric label="ORB" value={snapshot?.summary.orb_overlay_count ?? '--'} />
            </div>
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-white">
              <FlaskConical className="h-4 w-4 text-amber-300" />
              Simulation Lab
            </div>
            <div className="flex flex-col gap-2">
              <button type="button" onClick={runOrbReplay} className={inactiveToolClass}>
                <BarChart3 className="h-4 w-4" />
                ORB Replay
              </button>
              <button type="button" onClick={runExitComparison} className={inactiveToolClass}>
                <Activity className="h-4 w-4" />
                Stop/DCA
              </button>
            </div>
            {labMessage && <p className="mt-3 text-xs text-slate-300">{labMessage}</p>}
          </section>
        </aside>
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-950/80 p-3">
        <PlotlyChart
          data={oscillatorData}
          height={220}
          layout={{
            showlegend: true,
            legend: { orientation: 'h', y: 1.15, x: 0 },
            yaxis: { title: 'Oscillators' },
          }}
        />
      </section>
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

function buildPriceTraces(snapshot: ChartWorkspaceSnapshot | null, chartType: 'candlestick' | 'line') {
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
  const orbTraces = snapshot.orb_overlays.flatMap((overlay) => [
    orbLineTrace(x, overlay.high, `${overlay.label} ${overlay.timeframe} high`, '#f59e0b'),
    orbLineTrace(x, overlay.low, `${overlay.label} ${overlay.timeframe} low`, '#38bdf8'),
  ]);
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

const activeToolClass =
  'inline-flex h-9 items-center gap-2 rounded-lg border border-cyan-300/60 bg-cyan-400/15 px-3 text-sm font-semibold text-cyan-100';
const inactiveToolClass =
  'inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 text-sm font-semibold text-slate-300 hover:border-cyan-400/40 hover:text-cyan-100';

export default ChartWorkspace;
