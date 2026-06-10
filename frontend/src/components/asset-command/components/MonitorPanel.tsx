import { CheckCircle, Gauge, Pause, Play, RefreshCw } from 'lucide-react';
import { serviceRows } from '../data';
import type { Ticker } from '../types';
import { HealthCard, SectionHead, ServiceRow } from './shared';

export function MonitorPanel({
  feedPaused,
  tickers,
  onAction,
  onSelect,
}: {
  feedPaused: boolean;
  tickers: Ticker[];
  onAction: (action: string) => void;
  onSelect: (symbol: string) => void;
}) {
  return (
    <section className="edge-tab-panel">
      <div className="edge-tab-head">
        <div><span>Monitor</span><h2>Edge observability</h2></div>
        <div className="edge-tab-actions">
          <button type="button" onClick={() => onAction('refresh')}><RefreshCw size={14} />Refresh</button>
          <button type="button" onClick={() => onAction('diagnostics')}><Gauge size={14} />Diagnostics</button>
          <button type="button" onClick={() => onAction('ack')}><CheckCircle size={14} />Ack alerts</button>
          <button type="button" onClick={() => onAction('toggle-feed')}>{feedPaused ? <Play size={14} /> : <Pause size={14} />}{feedPaused ? 'Resume feed' : 'Pause feed'}</button>
        </div>
      </div>
      <div className="edge-card-grid">
        <HealthCard label="Sentinel Pulse" value={feedPaused ? 'Paused' : 'Synced'} detail="7 tickers / 5 watchers" tone={feedPaused ? 'gold' : 'green'} />
        <HealthCard label="Prediction Engine" value="18ms" detail="p95 inference latency" tone="cyan" />
        <HealthCard label="Plugin Bus" value="5 active" detail="MACD-V, EMA, FLOW, RISK, GAP" tone="gold" />
        <HealthCard label="Alert Queue" value="3 open" detail="1 high priority" tone="red" />
      </div>
      <div className="edge-section-grid">
        <section className="edge-tab-section wide"><SectionHead label="Services" value="ops telemetry" />{serviceRows.map((row) => <ServiceRow key={row[0]} row={row} />)}</section>
        <section className="edge-tab-section"><SectionHead label="Watcher coverage" value="Sentinel Pulse" /><div className="edge-watcher-map">{tickers.map((ticker) => <button type="button" key={ticker.symbol} onClick={() => onSelect(ticker.symbol)}><strong>{ticker.symbol}</strong><em>{ticker.watchers[0] ? `${ticker.watchers[0].plugin} / ${ticker.watchers[0].status}` : 'Pulse idle'}</em></button>)}</div></section>
      </div>
    </section>
  );
}
