import { ChevronLeft, ChevronRight, FileDown, PanelRightClose, RefreshCw, X } from 'lucide-react';
import { useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Ticker } from '../types';
import { VolumeHeatmap, type HeatMode } from './VolumeHeatmap';

interface GammaPoint {
  strike: number;
  gamma: number;
  delta: number;
  exposure: number;
}

type GreeksViewMode = 'main' | 'heatmap' | 'gamma' | 'risk' | 'levels';

const greekSymbols = ['SPY', 'QQQ', 'TSLA', 'NVDA', 'ESU6', 'NQU6', 'BTC-USD', 'ETH-USD'];
const flowMetrics = [
  { label: 'Net Flow', value: '+$948.7M', change: '+69.4%', tone: 'positive' },
  { label: 'Net Drift', value: '-$56.1M', change: '-3.26%', tone: 'negative' },
  { label: 'Net Premium', value: '+$1.28B', change: '+8.42%', tone: 'positive' },
];
const greekHeatColumns = ['Dec 18', 'Dec 19', 'Dec 22', 'Dec 24', 'Dec 26', 'Jan 3', 'Jan 9'];
const greekHeatRows = [
  { strike: 683, values: [51.4, 67.8, 12.0, 28.0, 16.1, 6.3, 13.1] },
  { strike: 682, values: [27.6, 100.0, 68.4, 16.3, 27.5, 15.7, 8.5] },
  { strike: 681, values: [97.4, 148.6, 61.3, 53.4, 16.8, 9.0, 39.0] },
  { strike: 680, values: [169.2, 200.1, 49.6, 28.0, 48.5, 9.1, 2.6] },
  { strike: 679, values: [527.0, 1.16, 44.6, 72.5, 59.3, 21.9, 91.5] },
  { strike: 678, values: [249.5, -89.9, 43.8, 38.5, 8.3, 2.1, -5.2] },
  { strike: 677, values: [1.08, 198.5, 57.9, -6.5, -3.3, 7.2, -7.7] },
  { strike: 676, values: [3.70, -109.3, 220.6, 18.0, 5.1, -4.2, 181.3] },
  { strike: 675, values: [-915.6, 163.2, -21.8, 45.4, 12.3, -31.6, 8.6] },
  { strike: 674, values: [-188.0, 119.1, -26.7, 19.6, 31.0, -1.6, -5.0] },
  { strike: 673, values: [-269.2, -234.5, 152.1, -1.1, 21.3, -20.0, -59.6] },
];
const gainersLosersRows = [
  { rank: 1, ticker: 'SPY', bearish: '-$16.60B', bullish: '$16.69B', ratio: '0.99' },
  { rank: 2, ticker: 'SPX', bearish: '-$6.90B', bullish: '$6.45B', ratio: '1.07' },
  { rank: 3, ticker: 'MSTR', bearish: '-$1.93B', bullish: '$1.83B', ratio: '1.05' },
  { rank: 4, ticker: 'TSLA', bearish: '-$1.28B', bullish: '$1.41B', ratio: '0.91' },
  { rank: 5, ticker: 'QQQ', bearish: '-$912.70M', bullish: '$945.56M', ratio: '0.97' },
  { rank: 6, ticker: 'NVDA', bearish: '-$640.90M', bullish: '$674.64M', ratio: '0.95' },
  { rank: 7, ticker: 'ORCL', bearish: '-$653.00M', bullish: '$840.13M', ratio: '0.78' },
  { rank: 8, ticker: 'UNH', bearish: '-$592.03M', bullish: '$788.55M', ratio: '0.75' },
  { rank: 9, ticker: 'AVGO', bearish: '-$771.95M', bullish: '$504.65M', ratio: '1.53' },
  { rank: 10, ticker: 'META', bearish: '-$547.01M', bullish: '$484.84M', ratio: '1.13' },
];

const generateGammaPoints = (symbol: string, revision = 0): GammaPoint[] => {
  const base = Math.abs(symbol.length * 7 + 26 + revision * 3);
  const points: GammaPoint[] = [];
  const center = 3400 + (base % 11) * 20;

  for (let i = 0; i < 20; i += 1) {
    const strike = center + (i - 9.5) * 25;
    const distance = Math.abs(i - 9.5);
    const gamma = clamp(65 - distance * 4.2 - ((i % 3) - 1) * 2 + (base % 11) * 0.12, 6, 74);
    const delta = clamp(48 + (9 - distance) * 2.8, 12, 93);
    const exposure = clamp(0.6 + (gamma / 100) * 1.45 + (base % 7) * 0.08, 0.45, 2.2);
    points.push({
      strike,
      gamma: Number(gamma.toFixed(1)),
      delta: Number(delta.toFixed(1)),
      exposure: Number(exposure.toFixed(2)),
    });
  }

  return points;
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function formatGreekHeatValue(value: number) {
  if (value === 1.08 || value === 3.70) return `${value.toFixed(2)}B`;
  return `${value.toFixed(1)}M`;
}

function greekHeatTone(value: number) {
  if (value < 0) return 'negative';
  if (value > 180) return 'strong';
  return 'positive';
}

export function GreeksPanel({ selected }: { selected: Ticker }) {
  const [symbol, setSymbol] = useState(selected.symbol);
  const [mode, setMode] = useState<HeatMode>('GEX');
  const [showLeftRail, setShowLeftRail] = useState(false);
  const [showRightRail, setShowRightRail] = useState(false);
  const [revision, setRevision] = useState(0);
  const [viewMode, setViewMode] = useState<GreeksViewMode>('main');
  const [timeframe, setTimeframe] = useState<'1m' | '5m' | '15m'>('5m');

  const gammaRows = useMemo(() => generateGammaPoints(symbol, revision), [symbol, revision]);

  const chartSummary = useMemo(() => {
    const top = gammaRows.reduce((best, row) => (row.gamma > best.gamma ? row : best), gammaRows[0]);
    const ranked = [...gammaRows].sort((left, right) => right.gamma - left.gamma);
    const second = ranked[1] ?? top;
    const totalExposure = gammaRows.reduce((total, row) => total + row.exposure, 0);
    const totalGamma = gammaRows.reduce((total, row) => total + row.gamma, 0) / gammaRows.length;
    const callWall = gammaRows.reduce((best, row) => (row.delta > best.delta ? row : best), gammaRows[0]);
    const putWall = gammaRows.reduce((best, row) => (row.delta < best.delta ? row : best), gammaRows[0]);
    return { top, second, callWall, putWall, totalExposure, totalGamma };
  }, [gammaRows]);

  return (
    <section className="edge-tab-panel edge-greeks-panel">
      <header className="edge-tab-head">
        <div>
          <span>Greek Heat Map command deck</span>
          <h2>
            Greek Workbench
            {' '}
            /
            {' '}
            {symbol}
          </h2>
        </div>
        <div className="edge-tab-actions">
          <button type="button" onClick={() => setShowLeftRail((value) => !value)}>
            {showLeftRail ? <PanelRightClose size={14} /> : <ChevronRight size={14} />}
            Controls
          </button>
          <button type="button" onClick={() => setShowRightRail((value) => !value)}>
            {showRightRail ? <PanelRightClose size={14} /> : <ChevronLeft size={14} />}
            Outcomes
          </button>
          <button type="button" onClick={() => setRevision((value) => value + 1)}>
            <RefreshCw size={14} />
            Resimulate
          </button>
          <button type="button" onClick={() => setViewMode('levels')}>
            <FileDown size={14} />
            Export levels
          </button>
        </div>
      </header>

      <div className={`edge-greeks-workspace ${showLeftRail ? 'rail-open' : 'rail-closed'} ${showRightRail ? 'outcome-open' : 'outcome-closed'}`}>
        <aside className={`edge-greeks-rail edge-greeks-left ${showLeftRail ? 'open' : 'collapsed'}`}>
          <div className="edge-greeks-rail-head">
            <span>Controls</span>
            <strong>Chart stack</strong>
          </div>
          <label>
            Symbol
            <select value={symbol} onChange={(event) => setSymbol(event.target.value)}>
              {greekSymbols.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label>
            Timeframe
            <select value={timeframe} onChange={(event) => setTimeframe(event.target.value as '1m' | '5m' | '15m')}>
              <option value="1m">1m</option>
              <option value="5m">5m</option>
              <option value="15m">15m</option>
            </select>
          </label>
          <label>
            Session notes
            <textarea readOnly value={`${symbol} ${mode} profile active on ${timeframe}.`} />
          </label>
          <button type="button" onClick={() => setViewMode('gamma')}>
            Open gamma panel
          </button>
          <button type="button" onClick={() => setViewMode('risk')}>
            Open risk panel
          </button>
        </aside>

        <section className="edge-greeks-main">
            <VolumeHeatmap
              symbol={symbol}
              initialMode={mode}
              liveRevision={revision}
              onExpand={() => setViewMode('heatmap')}
            />
          <section className="edge-greeks-lower">
            <section className="edge-greeks-level-box">
              <span>Active profile</span>
              <strong>{chartSummary.top.strike}</strong>
              <p>
                Gamma:
                {' '}
                {chartSummary.top.gamma}
                {' '}
                / Delta:
                {' '}
                {chartSummary.top.delta}
              </p>
              <small>
                Total exposure
                {' '}
                {chartSummary.totalExposure.toFixed(2)}
                {' '}
                / Mean gamma
                {' '}
                {chartSummary.totalGamma.toFixed(1)}
              </small>
            </section>
            <section className="edge-greeks-gamma-panel">
              <div className="edge-greeks-gamma-head">
                <span>Gamma by strike</span>
                <button type="button" onClick={() => setViewMode('gamma')}>
                  Expand
                  {' '}
                  {mode}
                </button>
              </div>
              <div className="edge-greeks-gamma-grid">
                {gammaRows.map((point) => (
                  <div key={point.strike} className="edge-greeks-gamma-row">
                    <strong>{point.strike}</strong>
                    <div className="edge-greeks-gamma-track">
                      <i style={{ width: `${point.gamma}%` }} />
                      <span>G {point.gamma}</span>
                    </div>
                    <div className="edge-greeks-gamma-meta">
                      <b>{point.exposure.toFixed(2)}x</b>
                      <em>Delta {point.delta}</em>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </section>
          <section className="edge-greeks-premium-deck" aria-label="Greek premium flow and gainers losers">
            <article className="edge-greeks-flow-panel">
              <div className="edge-greeks-table-head">
                <div>
                  <span>Net Flows</span>
                  <strong>Premium</strong>
                </div>
                <small>Today</small>
              </div>
              <div className="edge-greeks-flow-grid">
                {flowMetrics.map((metric) => (
                  <div key={metric.label} className={`edge-greeks-flow-metric ${metric.tone}`}>
                    <span>{metric.label}</span>
                    <strong>{metric.value}</strong>
                    <small>{metric.change}</small>
                  </div>
                ))}
              </div>
              <div className="edge-greeks-heat-table-wrap">
                <div className="edge-greeks-table-head">
                  <div>
                    <span>Net GEX Heat Map</span>
                    <strong>Premium</strong>
                  </div>
                  <div className="edge-greeks-mini-toggle">
                    <button type="button" className={mode === 'GEX' ? 'active' : ''} onClick={() => setMode('GEX')}>GEX</button>
                    <button type="button" className={mode === 'VEX' ? 'active' : ''} onClick={() => setMode('VEX')}>VEX</button>
                  </div>
                </div>
                <div className="edge-greeks-heat-table" role="table" aria-label="Net GEX heat map by strike and date">
                  <div className="edge-greeks-heat-row head" role="row">
                    <span role="columnheader">Strike</span>
                    {greekHeatColumns.map((column) => <span key={column} role="columnheader">{column}</span>)}
                  </div>
                  {greekHeatRows.map((row) => (
                    <div key={row.strike} className="edge-greeks-heat-row" role="row">
                      <strong role="cell">{row.strike}</strong>
                      {row.values.map((value, index) => (
                        <em key={`${row.strike}-${greekHeatColumns[index]}`} className={greekHeatTone(value)} role="cell">
                          {formatGreekHeatValue(value)}
                        </em>
                      ))}
                    </div>
                  ))}
                </div>
                <div className="edge-greeks-scale" aria-hidden="true">
                  <i />
                  <span>&lt;-500M</span>
                  <span>-250M</span>
                  <span>-50M</span>
                  <span>0</span>
                  <span>50M</span>
                  <span>250M</span>
                  <span>&gt;500M</span>
                </div>
              </div>
            </article>

            <article className="edge-greeks-gainers-panel">
              <div className="edge-greeks-table-head">
                <div>
                  <span>Gainers / Losers</span>
                  <strong>By Net Premium</strong>
                </div>
                <div className="edge-greeks-mini-toggle">
                  <button type="button">All</button>
                  <button type="button" className="active">Gainers</button>
                </div>
              </div>
              <div className="edge-greeks-gainers-table" role="table" aria-label="Gainers and losers by net premium">
                <div className="edge-greeks-gainers-row head" role="row">
                  <span role="columnheader">Rank</span>
                  <span role="columnheader">Ticker</span>
                  <span role="columnheader">Bearish Premium</span>
                  <span role="columnheader">Bullish Premium</span>
                  <span role="columnheader">Ratio</span>
                </div>
                {gainersLosersRows.map((row) => (
                  <div key={`${row.rank}-${row.ticker}`} className="edge-greeks-gainers-row" role="row">
                    <span role="cell">{row.rank}</span>
                    <strong role="cell">{row.ticker}</strong>
                    <em className="negative" role="cell">{row.bearish}</em>
                    <em className="positive" role="cell">{row.bullish}</em>
                    <span role="cell">{row.ratio}</span>
                  </div>
                ))}
              </div>
            </article>
          </section>
        </section>

        <aside className={`edge-greeks-rail edge-greeks-right ${showRightRail ? 'open' : 'collapsed'}`}>
          <div className="edge-greeks-rail-head">
            <span>Outcome pane</span>
            <strong>Heat + policy</strong>
          </div>
          <section className="edge-greeks-metric-card">
            <span>Net gamma</span>
            <strong>{chartSummary.totalGamma.toFixed(1)}</strong>
          </section>
          <section className="edge-greeks-metric-card">
            <span>Flow pressure</span>
            <strong>{mode === 'VOL' ? 'Vol heavy' : mode}</strong>
          </section>
          <section className="edge-greeks-metric-card">
            <span>Bridge health</span>
            <strong>Pulse live</strong>
          </section>
          <button type="button" onClick={() => setViewMode('gamma')}>
            View gamma stack
          </button>
          <button type="button" onClick={() => setViewMode('risk')}>
            Open risk stack
          </button>
        </aside>
      </div>

      {viewMode !== 'main' && createPortal(
        <section className="edge-popout-shell" role="presentation" onClick={() => setViewMode('main')}>
          <article
            className={`edge-popout-panel ${viewMode === 'heatmap' ? 'edge-popout-panel-chart' : ''}`}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <div>
                <span>Popout</span>
                <strong>
                  {viewMode === 'heatmap'
                    ? 'Expanded GEX / VEX heat map'
                    : viewMode === 'gamma'
                      ? 'Expanded gamma by strike'
                      : viewMode === 'risk'
                        ? 'Risk surface detail'
                        : 'Level surface'}
                </strong>
              </div>
              <button type="button" onClick={() => setViewMode('main')}>
                <X size={14} />
              </button>
            </header>
            {viewMode === 'heatmap' && (
              <VolumeHeatmap
                symbol={symbol}
                initialMode={mode}
                liveRevision={revision}
                className="edge-volume-heatmap-expanded"
              />
            )}
            {viewMode === 'gamma' && (
              <div className="edge-gamma-popout-layout">
                <aside className="edge-gamma-popout-summary">
                  <section>
                    <span>Highest sensitivity</span>
                    <strong>{chartSummary.top.strike}</strong>
                    <p>
                      Gamma
                      {' '}
                      {chartSummary.top.gamma}
                      {' '}
                      / Exposure
                      {' '}
                      {chartSummary.top.exposure.toFixed(2)}
                      x
                    </p>
                  </section>
                  <section>
                    <span>Secondary shelf</span>
                    <strong>{chartSummary.second.strike}</strong>
                    <p>
                      Gamma
                      {' '}
                      {chartSummary.second.gamma}
                      {' '}
                      / Delta
                      {' '}
                      {chartSummary.second.delta}
                    </p>
                  </section>
                  <section>
                    <span>Call wall</span>
                    <strong>{chartSummary.callWall.strike}</strong>
                    <p>
                      Delta
                      {' '}
                      {chartSummary.callWall.delta}
                    </p>
                  </section>
                  <section>
                    <span>Put wall</span>
                    <strong>{chartSummary.putWall.strike}</strong>
                    <p>
                      Delta
                      {' '}
                      {chartSummary.putWall.delta}
                    </p>
                  </section>
                </aside>
                <div className="edge-greeks-gamma-grid edge-greeks-gamma-grid-popout">
                  {gammaRows.map((point) => (
                    <div key={point.strike} className="edge-greeks-gamma-row">
                      <strong>{point.strike}</strong>
                      <div className="edge-greeks-gamma-track">
                        <i style={{ width: `${point.gamma}%` }} />
                        <span>G {point.gamma}</span>
                      </div>
                      <div className="edge-greeks-gamma-meta">
                        <b>{point.exposure.toFixed(2)}x</b>
                        <em>Delta {point.delta}</em>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {viewMode === 'risk' && (
              <div className="edge-greeks-risk-grid">
                <p>Risk surface diagnostics placeholder for the selected symbol and mode.</p>
                <ul>
                  <li>Pressure trend: stable with slight mean-reverting slope</li>
                  <li>Skew: mild convexity build</li>
                  <li>Squeeze risk: medium; watch breakout timing</li>
                </ul>
              </div>
            )}
            {viewMode === 'levels' && (
              <div className="edge-greeks-risk-grid">
                <p>Levels snapshot exported to advisory feed.</p>
                <ul>
                  <li>Gamma stack: top line at highest sweep concentration</li>
                  <li>VEX pressure concentrated around central strikes</li>
                  <li>VOL channel stable across the last 30 bars</li>
                </ul>
              </div>
            )}
          </article>
        </section>,
        document.body,
      )}
    </section>
  );
}
