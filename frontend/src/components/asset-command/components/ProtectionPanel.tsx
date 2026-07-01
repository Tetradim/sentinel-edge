import { AlertTriangle, Bot, Lock, RadioTower, RefreshCw, Shield, ShieldAlert } from 'lucide-react';
import { botBridgeHealth, botLockouts, nowTime, policyStackRules, protectionRows } from '../data';
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
        <div><span>Protect</span><h2>Emergency control room</h2></div>
        <div className="edge-tab-actions">
          <button type="button" onClick={() => onAction('refresh')}><RefreshCw size={14} />Refresh</button>
          <button type="button" onClick={() => onAction('tighten')}><Lock size={14} />Lock buys</button>
          <button type="button" onClick={() => onAction('hedge')}><Shield size={14} />Advise stops</button>
          <button type="button" onClick={() => onAction('reduce')}><AlertTriangle size={14} />Reduce size</button>
        </div>
      </div>
      <div className="edge-protect-overview">
        <div><span>Protection posture</span><strong>{mode}</strong></div>
        <div><span>Last update</span><strong>{nowTime()}</strong></div>
      </div>
      <div className="edge-card-grid">
        <HealthCard label="Suppression state" value="3 active" detail="Scoped bot locks and symbol blocks" tone="red" />
        <HealthCard label="Policy strictness" value="82/100" detail="Guardrails enforcing confirmation" tone="gold" />
        <HealthCard label="Bridge routes" value="6/9" detail="Healthy or read-only bot connections" tone="cyan" />
        <HealthCard label="Emergency lock" value="Clear" detail="No global stop directive armed" tone="green" />
      </div>

      <div className="edge-protect-command-grid">
        <section className="edge-tab-section">
          <SectionHead label="Active bot lockouts" value="scope / reason / release condition" />
          <div className="edge-lockout-list">
            {botLockouts.map((lockout) => (
              <article key={`${lockout.bot}-${lockout.scope}`} className={`edge-lockout-row edge-tone-${lockout.tone}`}>
                <div>
                  <strong>{lockout.bot}</strong>
                  <span>{lockout.scope}</span>
                </div>
                <div>
                  <b>{lockout.state}</b>
                  <small>{lockout.until}</small>
                </div>
                <p>{lockout.reason}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="edge-tab-section">
          <SectionHead label="Policy guards" value="what currently blocks or caps bots" />
          <div className="edge-protect-policy-list">
            {policyStackRules.slice(0, 4).map((policy) => (
              <article key={policy.id} className={`edge-protect-policy edge-tone-${policy.tone}`}>
                <header>
                  <strong>{policy.label}</strong>
                  <span>{policy.strictness}</span>
                </header>
                <p>{policy.effect}</p>
                <small>{policy.reason}</small>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className="edge-tab-section edge-protect-bridge-section">
        <SectionHead label="Bridge route health" value="heartbeat / latency / queues" />
        <div className="edge-protect-bridge-grid">
          {botBridgeHealth.map((bridge) => (
            <article key={bridge.name} className={`edge-protect-bridge edge-tone-${bridge.tone}`}>
              <header>
                <div>
                  <strong>{bridge.name}</strong>
                  <span>{bridge.status}</span>
                </div>
                {bridge.status === 'offline' ? <ShieldAlert size={16} /> : bridge.status === 'standalone' ? <Bot size={16} /> : <RadioTower size={16} />}
              </header>
              <div>
                <small>{bridge.heartbeat}</small>
                <small>{bridge.latency}</small>
                <small>
                  Q
                  {bridge.queueDepth}
                  {' '}
                  /
                  R
                  {bridge.rejectedEvents}
                </small>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="edge-tab-section">
        <SectionHead label="Symbol guardrails" value="support / invalidation / exposure pressure" />
        <div className="edge-risk-table">
          {protectionRows.map((row) => (
            <button type="button" key={row.symbol} className={`edge-risk-row edge-tone-${row.tone} ${selectedSymbol === row.symbol ? 'active' : ''}`} onClick={() => onSelect(row.symbol)}>
              <div><strong>{row.symbol}</strong><span>{row.guard}</span></div>
              <div><span>Exposure</span><b>{row.exposure}</b></div>
              <div><span>Advised stop</span><b>{row.stop}</b></div>
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
