import { BarChart3, CalendarDays, Expand, Gauge, RefreshCw, Shield, Target, X, Zap } from 'lucide-react';
import type React from 'react';
import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import type { RuntimeState, Ticker, Watcher } from '../types';
import { VolumeHeatmap } from './VolumeHeatmap';

const botNames = [
  'Sentinel Pulse',
  'Discord Trading Bot',
  'Sentinel Chain',
  'Futures',
  'Sentinel Core',
  'Darkpool Mon',
  'APK Alerts',
  'Extension External',
];

const botOffset: Record<string, number> = {
  'Sentinel Pulse': 0,
  'Discord Trading Bot': 2,
  'Sentinel Chain': 4,
  Futures: 6,
  'Sentinel Core': 8,
  'Darkpool Mon': 10,
  'APK Alerts': 12,
  'Extension External': 14,
};

export function UnifiedChartingPanel({
  selected,
  watcher,
  tickers,
  runtime,
  onSelect,
  onAction,
  onCommand,
}: {
  selected: Ticker;
  watcher?: Watcher;
  tickers: Ticker[];
  runtime: RuntimeState;
  onSelect: (symbol: string) => void;
  onAction: (action: string) => void;
  onCommand: (action: string) => void;
}) {
  const [revision, setRevision] = useState(0);
  const [botView, setBotView] = useState(botNames[0]);
  const [calendarWindow, setCalendarWindow] = useState<'day' | 'week' | 'month'>('month');
  const [expanded, setExpanded] = useState(false);

  const support = selected.price * 0.992;
  const resistance = selected.price * 1.008;
  const pnlCalendar = useMemo(() => buildCalendar(botView, calendarWindow), [botView, calendarWindow]);
  const wins = pnlCalendar.filter((day) => day.pnl >= 0).length;
  const losses = pnlCalendar.length - wins;
  const pnlTotal = pnlCalendar.reduce((total, day) => total + day.pnl, 0);
  const winRate = Math.round((wins / Math.max(1, pnlCalendar.length)) * 100);
  const directive = selected.change.startsWith('-') ? 'Reduce size' : watcher ? 'Allow with guard' : 'Watch';

  const handleRunSweep = () => {
    setRevision((value) => value + 1);
    onAction('Run sweep');
  };

  return (
    <section className="edge-tab-panel edge-unified-chart-panel" aria-label="Unified charting and market map">
      <header className="edge-tab-head">
        <div>
          <span>Charting / market map / monitor</span>
          <h2>
            Sentinel chart map
            {' '}
            /
            {' '}
            {selected.symbol}
          </h2>
        </div>
        <div className="edge-tab-actions">
          <button type="button" onClick={handleRunSweep}>
            <RefreshCw size={14} />
            Run sweep
          </button>
          <button type="button" onClick={() => onAction('Inject break')}>
            <Zap size={14} />
            Inject break
          </button>
          <button type="button" onClick={() => setExpanded(true)}>
            <Expand size={14} />
            Expand
          </button>
        </div>
      </header>

      <div className="edge-unified-chart-shell">
        <section className="edge-workspace-command-row" aria-label="Selected asset summary">
          <SummaryCard label="Asset" value={selected.symbol} detail={`${selected.change} / ${selected.signal}`} tone="gold" />
          <SummaryCard label="Support" value={support.toFixed(2)} detail="Break below blocks entries" tone="green" />
          <SummaryCard label="Resistance" value={resistance.toFixed(2)} detail="Breakout confirmation shelf" tone="cyan" />
          <SummaryCard
            label="Bridge health"
            value={runtime.pulseAvailable ? 'Pulse online' : 'Standalone'}
            detail={runtime.pulseCircuitState || (runtime.pulseAvailable ? 'advisory bridge ready' : 'no handoff active')}
            tone={runtime.pulseAvailable ? 'green' : 'gold'}
          />
        </section>

        <section className="edge-unified-chart-grid">
          <div className="edge-unified-chart-main">
            <VolumeHeatmap
              symbol={selected.symbol}
              liveRevision={revision}
              onExpand={() => setExpanded(true)}
              className="edge-volume-heatmap-command"
            />
          </div>

          <aside className="edge-unified-outcome-stack" aria-label="Composition and outcome side panel">
            <section className="edge-chart-directive-card">
              <div className="edge-chart-mini-head">
                <div>
                  <span>Advisory posture</span>
                  <strong>{directive}</strong>
                </div>
                <Shield size={17} />
              </div>
              <div className="edge-chart-directive-list">
                <div>
                  <span>Watcher</span>
                  <strong>{watcher ? `${watcher.plugin} / ${watcher.status}` : 'No active watcher'}</strong>
                </div>
                <div>
                  <span>Risk action</span>
                  <strong>{selected.change.startsWith('-') ? 'Stop trading if support fails' : 'Guard breakout only'}</strong>
                </div>
                <div>
                  <span>Command path</span>
                  <strong>Calculate / advise / block</strong>
                </div>
              </div>
            </section>

            <section className="edge-chart-calendar-card">
              <div className="edge-chart-mini-head">
                <div>
                  <span>Bot P&L calendar</span>
                  <strong>{botView}</strong>
                </div>
                <CalendarDays size={17} />
              </div>
              <div className="edge-chart-filter-row">
                <select value={botView} onChange={(event) => setBotView(event.target.value)}>
                  {botNames.map((name) => (
                    <option key={name} value={name}>{name}</option>
                  ))}
                </select>
                <div className="edge-chart-segments" role="group" aria-label="P&L window">
                  {(['day', 'week', 'month'] as const).map((window) => (
                    <button
                      key={window}
                      type="button"
                      className={calendarWindow === window ? 'active' : ''}
                      onClick={() => setCalendarWindow(window)}
                    >
                      {window}
                    </button>
                  ))}
                </div>
              </div>
              <div className="edge-chart-calendar-grid">
                {pnlCalendar.map((day) => (
                  <div key={day.label} className={`edge-chart-calendar-cell ${day.pnl >= 0 ? 'win' : 'loss'}`}>
                    <small>{day.label}</small>
                    <strong>
                      {day.pnl >= 0 ? '+' : ''}
                      {day.pnl}
                    </strong>
                  </div>
                ))}
              </div>
            </section>

            <section className="edge-chart-winloss-card">
              <div className="edge-chart-mini-head">
                <div>
                  <span>Outcome counter</span>
                  <strong>
                    {wins}
                    {' '}
                    /
                    {' '}
                    {losses}
                  </strong>
                </div>
                <Target size={17} />
              </div>
              <div
                className="edge-chart-donut"
                style={{ '--win-rate': `${winRate}%` } as React.CSSProperties}
                aria-label={`${winRate}% win rate`}
              >
                <span>
                  {wins}
                  W
                </span>
                <small>
                  {losses}
                  L
                </small>
              </div>
              <p>
                {calendarWindow}
                {' '}
                P&L:
                {' '}
                <strong className={pnlTotal >= 0 ? 'profit' : 'loss'}>
                  {pnlTotal >= 0 ? '+' : ''}
                  $
                  {Math.abs(pnlTotal).toLocaleString()}
                </strong>
              </p>
            </section>
          </aside>
        </section>

        <section className="edge-market-map-deck" aria-label="Market map and key levels">
          <article className="edge-market-ladder-card">
            <div className="edge-chart-mini-head">
              <div>
                <span>Key level monitor</span>
                <strong>Support / resistance / breakout radar</strong>
              </div>
              <Gauge size={17} />
            </div>
            <div className="edge-market-ladder">
              {[
                ['Resistance shelf', resistance.toFixed(2), 'Confirm before advisory allow'],
                ['Spot line', selected.price.toFixed(2), selected.status],
                ['Support shelf', support.toFixed(2), 'Break below blocks buy-side bots'],
                ['Risk corridor', '2.18R', 'Reduce size above threshold'],
              ].map(([label, value, detail]) => (
                <div key={label} className="edge-market-ladder-row">
                  <span>{label}</span>
                  <strong>{value}</strong>
                  <small>{detail}</small>
                </div>
              ))}
            </div>
          </article>

          <article className="edge-market-flow-card">
            <div className="edge-chart-mini-head">
              <div>
                <span>Market map</span>
                <strong>Tracked assets</strong>
              </div>
              <BarChart3 size={17} />
            </div>
            <div className="edge-chart-asset-strip">
              {tickers.map((ticker) => (
                <button
                  key={ticker.symbol}
                  type="button"
                  className={ticker.symbol === selected.symbol ? 'active' : ''}
                  onClick={() => onSelect(ticker.symbol)}
                >
                  <span>{ticker.symbol}</span>
                  <strong>{ticker.change}</strong>
                  <small>{ticker.status}</small>
                </button>
              ))}
            </div>
          </article>

          <article className="edge-chart-directive-card">
            <div className="edge-chart-mini-head">
              <div>
                <span>Command feed</span>
                <strong>Advisory only</strong>
              </div>
              <Shield size={17} />
            </div>
            <div className="edge-chart-directive-list">
              {['Allow guarded breakout', 'Block buy below support', 'Reduce size on heat spike'].map((item) => (
                <button key={item} type="button" onClick={() => onCommand(item)}>
                  <span>{selected.symbol}</span>
                  <strong>{item}</strong>
                </button>
              ))}
            </div>
          </article>
        </section>
      </div>

      {expanded && createPortal(
        <section className="edge-popout-shell edge-popout-dark" role="presentation" onClick={() => setExpanded(false)}>
          <article className="edge-popout-panel edge-popout-panel-chart" onClick={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span>Expanded chart map</span>
                <strong>
                  {selected.symbol}
                  {' '}
                  GEX / VEX / VOL command surface
                </strong>
              </div>
              <button type="button" onClick={() => setExpanded(false)} aria-label="Close expanded chart map">
                <X size={14} />
              </button>
            </header>
            <VolumeHeatmap symbol={selected.symbol} liveRevision={revision} className="edge-volume-heatmap-expanded" />
          </article>
        </section>,
        document.body,
      )}
    </section>
  );
}

function SummaryCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: 'green' | 'cyan' | 'gold' | 'red';
}) {
  return (
    <article className={`edge-workspace-command-card edge-tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function buildCalendar(botView: string, window: 'day' | 'week' | 'month') {
  const length = window === 'day' ? 7 : window === 'week' ? 14 : 28;
  const offset = botOffset[botView] ?? 0;

  return Array.from({ length }, (_, index) => {
    const wave = Math.sin((index + offset) * 1.42) * 220;
    const drift = Math.cos((index + offset) * 0.64) * 130;
    const pnl = Math.round(wave + drift + (index % 5 === 0 ? -180 : 110));
    return {
      label: String(index + 1).padStart(2, '0'),
      pnl,
    };
  });
}
