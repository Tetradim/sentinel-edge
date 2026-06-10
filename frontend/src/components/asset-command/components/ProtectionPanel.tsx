import { AlertTriangle, Lock, RefreshCw, Shield } from 'lucide-react';
import { nowTime, protectionRows } from '../data';
import { HealthCard, SectionHead } from './shared';

export function ProtectionPanel({
  mode,
  onAction,
  onSelect,
  selectedSymbol,
}: {
  mode: string;
  onAction: (action: string) => void;
  onSelect: (symbol: string) => void;
  selectedSymbol: string;
}) {
  return (
    <section className="edge-tab-panel edge-protect-panel">
      <div className="edge-tab-head">
        <div><span>Protect</span><h2>Risk shield</h2></div>
        <div className="edge-tab-actions">
          <button type="button" onClick={() => onAction('refresh')}><RefreshCw size={14} />Refresh</button>
          <button type="button" onClick={() => onAction('tighten')}><Lock size={14} />Tighten stops</button>
          <button type="button" onClick={() => onAction('hedge')}><Shield size={14} />Stage hedge</button>
          <button type="button" onClick={() => onAction('reduce')}><AlertTriangle size={14} />Reduce exposure</button>
        </div>
      </div>
      <div className="edge-protect-overview">
        <div><span>Protection mode</span><strong>{mode}</strong></div>
        <div><span>Last update</span><strong>{nowTime()}</strong></div>
      </div>
      <div className="edge-card-grid">
        <HealthCard label="Portfolio heat" value="46/100" detail="inside protection band" tone="gold" />
        <HealthCard label="Stop discipline" value="100%" detail="4 stops / 4 positions protected" tone="green" />
        <HealthCard label="Hedge coverage" value="34%" detail="coverage below target" tone="cyan" />
        <HealthCard label="Breach risk" value="1 active" detail="SPY invalidates at $626.80" tone="red" />
      </div>
      <section className="edge-tab-section">
        <SectionHead label="Position risk" value="stops / invalidation / exposure" />
        <div className="edge-risk-table">
          {protectionRows.map((row) => (
            <button type="button" key={row.symbol} className={`edge-risk-row edge-tone-${row.tone} ${selectedSymbol === row.symbol ? 'active' : ''}`} onClick={() => onSelect(row.symbol)}>
              <div><strong>{row.symbol}</strong><span>{row.guard}</span></div>
              <div><span>Exposure</span><b>{row.exposure}</b></div>
              <div><span>Stop</span><b>{row.stop}</b></div>
              <div><span>Invalid</span><b>{row.invalid}</b></div>
              <div><span>Heat</span><b>{row.heat}</b></div>
              <em>{row.action}</em>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}
