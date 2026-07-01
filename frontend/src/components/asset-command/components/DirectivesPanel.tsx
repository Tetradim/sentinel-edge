import { Bot, Download, Filter, Gauge, Lock, RefreshCw, ShieldCheck } from 'lucide-react';
import { useMemo, useState } from 'react';
import {
  botBridgeHealth,
  directiveLedger,
  marketRegime,
  outcomeAttribution,
  policyStackRules,
} from '../data';
import type { BotBridgeHealth, DirectiveLedgerEntry, OutcomeAttribution, PolicyStackRule, Tone } from '../types';

const allBots = 'All bots';

export function DirectivesPanel() {
  const [selectedBot, setSelectedBot] = useState(allBots);
  const [selectedPolicy, setSelectedPolicy] = useState(policyStackRules[0]?.id ?? '');

  const visibleLedger = useMemo(() => (
    selectedBot === allBots
      ? directiveLedger
      : directiveLedger.filter((entry) => entry.bot === selectedBot)
  ), [selectedBot]);

  const activePolicy = policyStackRules.find((policy) => policy.id === selectedPolicy) ?? policyStackRules[0];

  return (
    <section className="edge-tab-panel edge-directives-command" aria-label="Sentinel Edge directives command center">
      <header className="edge-tab-head">
        <div>
          <span>Directive command center</span>
          <h2>Sentinel Edge supervisory brain</h2>
        </div>
        <div className="edge-tab-actions">
          <button type="button">
            <RefreshCw size={14} />
            Run sweep
          </button>
          <button type="button">
            <Download size={14} />
            Export ledger
          </button>
          <button type="button" className="danger">
            <Lock size={14} />
            Emergency lock
          </button>
        </div>
      </header>

      <div className="edge-directives-command-shell">
        <section className="edge-directives-hero">
          <article className={`edge-directives-regime edge-tone-${marketRegime.tone}`}>
            <div>
              <span>Market regime</span>
              <strong>{marketRegime.label}</strong>
              <p>{marketRegime.detail}</p>
            </div>
            <div className="edge-regime-score" aria-label={`Regime score ${marketRegime.score}`}>
              <span>{marketRegime.score}</span>
              <small>{marketRegime.pressure}</small>
            </div>
          </article>
          <SummaryTile label="Allowed posture" value={marketRegime.allowedPosture} detail="Current bot permission envelope" tone="gold" />
          <SummaryTile label="Active blocks" value="3" detail="Bot or symbol scope suppressions" tone="red" />
          <SummaryTile label="Bridge median" value="42ms" detail="Acknowledgement latency" tone="cyan" />
        </section>

        <section className="edge-directives-layout">
          <aside className="edge-directives-column" aria-label="Bot bridge health">
            <div className="edge-directives-section-head">
              <div>
                <span>Bot bridge health</span>
                <strong>Ecosystem routes</strong>
              </div>
              <Bot size={18} />
            </div>
            <div className="edge-bridge-health-list">
              {botBridgeHealth.map((bridge) => (
                <BridgeCard key={bridge.name} bridge={bridge} selected={selectedBot === bridge.name} onSelect={() => setSelectedBot(bridge.name)} />
              ))}
            </div>
          </aside>

          <main className="edge-directives-ledger" aria-label="Directive ledger">
            <div className="edge-directives-section-head">
              <div>
                <span>Directive ledger</span>
                <strong>{selectedBot}</strong>
              </div>
              <label className="edge-ledger-filter">
                <Filter size={14} />
                <select value={selectedBot} onChange={(event) => setSelectedBot(event.target.value)}>
                  <option value={allBots}>{allBots}</option>
                  {botBridgeHealth.map((bridge) => (
                    <option key={bridge.name} value={bridge.name}>{bridge.name}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="edge-ledger-list">
              {visibleLedger.map((entry) => (
                <LedgerRow key={entry.id} entry={entry} />
              ))}
            </div>
          </main>

          <aside className="edge-directives-column" aria-label="Policy stack and outcomes">
            <section className="edge-policy-stack">
              <div className="edge-directives-section-head">
                <div>
                  <span>Policy stack</span>
                  <strong>Rules that tell bots no</strong>
                </div>
                <ShieldCheck size={18} />
              </div>
              <div className="edge-policy-list">
                {policyStackRules.map((policy) => (
                  <PolicyButton
                    key={policy.id}
                    policy={policy}
                    selected={policy.id === activePolicy.id}
                    onSelect={() => setSelectedPolicy(policy.id)}
                  />
                ))}
              </div>
              <div className={`edge-policy-detail edge-tone-${activePolicy.tone}`}>
                <span>{activePolicy.state}</span>
                <strong>{activePolicy.effect}</strong>
                <p>{activePolicy.reason}</p>
              </div>
            </section>

            <section className="edge-outcome-attribution">
              <div className="edge-directives-section-head">
                <div>
                  <span>Outcome attribution</span>
                  <strong>Did Edge help?</strong>
                </div>
                <Gauge size={18} />
              </div>
              <div className="edge-outcome-tiles">
                {outcomeAttribution.map((item) => (
                  <OutcomeTile key={item.label} item={item} />
                ))}
              </div>
            </section>
          </aside>
        </section>
      </div>
    </section>
  );
}

function SummaryTile({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}) {
  return (
    <article className={`edge-directives-summary edge-tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}

function BridgeCard({
  bridge,
  selected,
  onSelect,
}: {
  bridge: BotBridgeHealth;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      className={`edge-bridge-health-card edge-tone-${bridge.tone} ${selected ? 'active' : ''}`}
      onClick={onSelect}
    >
      <header>
        <strong>{bridge.name}</strong>
        <span>{bridge.status}</span>
      </header>
      <div className="edge-bridge-health-meta">
        <span>{bridge.heartbeat}</span>
        <span>{bridge.latency}</span>
        <span>{bridge.contract}</span>
      </div>
      <p>{bridge.detail}</p>
      <footer>
        <small>{bridge.lastDirective}</small>
        <small>
          Q
          {bridge.queueDepth}
          {' '}
          /
          R
          {bridge.rejectedEvents}
        </small>
      </footer>
    </button>
  );
}

function LedgerRow({ entry }: { entry: DirectiveLedgerEntry }) {
  return (
    <article className={`edge-ledger-row edge-decision-${entry.tone === 'green' ? 'ok' : entry.tone === 'red' ? 'danger' : entry.tone === 'gold' ? 'warn' : 'note'}`}>
      <header>
        <div>
          <span>{entry.time}</span>
          <strong>{entry.directive}</strong>
        </div>
        <b>{entry.confidence}</b>
      </header>
      <p>{entry.reason}</p>
      <footer>
        <small>
          {entry.bot}
          {' '}
          /
          {' '}
          {entry.symbol}
        </small>
        <small>
          {entry.regime}
          {' '}
          /
          {' '}
          {entry.acknowledgement}
        </small>
      </footer>
    </article>
  );
}

function PolicyButton({
  policy,
  selected,
  onSelect,
}: {
  policy: PolicyStackRule;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button type="button" className={`edge-policy-button edge-tone-${policy.tone} ${selected ? 'active' : ''}`} onClick={onSelect}>
      <span>{policy.label}</span>
      <strong>{policy.strictness}</strong>
      <i style={{ width: `${policy.strictness}%` }} />
    </button>
  );
}

function OutcomeTile({ item }: { item: OutcomeAttribution }) {
  return (
    <article className={`edge-outcome-tile edge-tone-${item.tone}`}>
      <span>{item.label}</span>
      <strong>{item.value}</strong>
      <p>{item.detail}</p>
    </article>
  );
}
