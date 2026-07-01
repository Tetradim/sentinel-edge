import { BarChart3, CheckCircle, ChevronLeft, ChevronRight, Gauge, Pause, Play, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import { serviceRows } from '../data';
import type { RuntimeState, Ticker, Tone, Watcher } from '../types';
import { HealthCard, SectionHead, ServiceRow } from './shared';

type MonitorView = 'monitor' | 'assets' | 'diagnostics';

export function MonitorPanel({
  runtime,
  feedPaused,
  selected,
  watcher,
  tickers,
  onAction,
  onCommand,
  onSelect,
}: {
  runtime: RuntimeState;
  feedPaused: boolean;
  selected: Ticker;
  watcher?: Watcher;
  tickers: Ticker[];
  onAction: (action: string) => void;
  onCommand: (action: string) => void;
  onSelect: (symbol: string) => void;
}) {
  const [activeView, setActiveView] = useState<MonitorView>('monitor');
  const [railCollapsed, setRailCollapsed] = useState(true);
  const edgeApiTone: Tone = runtime.connected ? 'green' : runtime.loading ? 'gold' : 'red';
  const schedulerTone: Tone = runtime.schedulerPaused ? 'gold' : runtime.connected ? 'green' : 'red';
  const pulseTone: Tone = runtime.pulseAvailable ? 'green' : 'gold';
  const pulseCircuitTone = getPulseCircuitTone(runtime.pulseCircuitState);
  const killSwitchTone: Tone = runtime.killSwitchActive ? 'red' : 'green';
  const readinessTone: Tone = !runtime.connected ? 'red' : runtime.runtimeReady ? 'green' : 'gold';
  const livenessTone: Tone = runtime.edgeLive ? 'green' : runtime.connected ? 'gold' : 'red';
  const rateLimitTone: Tone = runtime.rateLimitPressure === 'normal' ? 'green' : runtime.rateLimitPressure === 'warning' ? 'gold' : 'red';
  const frontendRumTone: Tone = runtime.frontendRumStatus === 'receiving' ? 'green' : runtime.frontendRumStatus === 'waiting' ? 'gold' : 'red';
  const schedulerValue = !runtime.connected ? 'Unknown' : runtime.schedulerPaused ? 'Paused' : 'Active';
  const pulseCircuitValue = formatPulseCircuitState(runtime.pulseCircuitState);
  const readinessValue = !runtime.connected ? 'Unknown' : runtime.runtimeReady ? 'Ready' : 'Not ready';
  const readinessDetail = getReadinessDetail(runtime.readinessFailingChecks);
  const livenessValue = runtime.edgeLive ? 'Alive' : runtime.connected ? 'Unknown' : 'Offline';
  const livenessDetail = getLivenessDetail(runtime.edgePid, runtime.edgeUptimeSeconds);
  const rateLimitValue = runtime.rateLimitPressure === 'unknown' ? 'Unknown' : runtime.rateLimitPressure === 'warning' ? 'Warning' : 'Normal';
  const rateLimitDetail = getRateLimitDetail(runtime.rateLimitRemaining, runtime.rateLimitResetSeconds);
  const frontendRumValue = runtime.frontendRumStatus === 'receiving' ? 'Receiving' : runtime.frontendRumStatus === 'waiting' ? 'Waiting' : 'Unknown';
  const frontendRumDetail = getFrontendRumDetail(
    runtime.frontendRumStatus,
    runtime.frontendRumSampleCount,
    runtime.frontendRumRouteCount,
    runtime.frontendRumLastRoute,
    runtime.frontendRumAgeSeconds,
  );
  const runtimePollAge = formatRuntimePollAge(runtime.updatedAt);
  const runtimeSignalRows = [
    [
      'Edge API',
      runtime.loading ? 'checking' : runtime.connected ? 'online' : 'offline',
      runtime.connected ? 'health ok' : runtime.error || 'not connected',
      '15s poll',
    ],
    [
      'Scheduler',
      !runtime.connected ? 'unknown' : runtime.schedulerPaused ? 'paused' : 'active',
      !runtime.connected ? 'backend unavailable' : runtime.schedulerPaused ? 'operator hold' : 'evaluation loop',
      'control',
    ],
    [
      'Edge process',
      livenessValue.toLowerCase(),
      runtime.edgeLive ? livenessDetail : runtime.connected ? 'liveness unavailable' : 'backend unavailable',
      runtime.edgeLive ? 'live' : 'unknown',
    ],
    [
      'Runtime readiness',
      readinessValue.toLowerCase(),
      !runtime.connected ? 'backend unavailable' : runtime.runtimeReady ? 'all required checks' : readinessDetail,
      runtime.runtimeReady ? 'ready' : runtime.connected ? 'blocked' : 'unknown',
    ],
    [
      'API pressure',
      rateLimitValue.toLowerCase(),
      runtime.rateLimitPressure === 'unknown' ? 'rate-limit status unavailable' : rateLimitDetail,
      runtime.rateLimitPressure,
    ],
    [
      'Frontend RUM',
      frontendRumValue.toLowerCase(),
      frontendRumDetail,
      runtime.frontendRumStatus,
    ],
    [
      'Pulse bridge',
      runtime.pulseAvailable ? 'online' : 'standalone',
      runtime.pulseAvailable ? 'handoff ready' : 'handoff gated',
      'health',
    ],
    [
      'Pulse circuit',
      pulseCircuitValue.toLowerCase(),
      getPulseCircuitDetail(runtime.pulseCircuitState, runtime.pulseAvailable),
      runtime.pulseCircuitState || 'unknown',
    ],
    [
      'Kill switch',
      runtime.killSwitchActive ? 'active' : 'clear',
      runtime.killSwitchActive ? 'global stop' : 'guard clear',
      'safety',
    ],
    [
      'Last runtime poll',
      runtimePollAge,
      runtime.updatedAt ? 'runtime status freshness' : 'waiting for first poll',
      runtime.updatedAt ? 'freshness' : 'pending',
    ],
  ];

  return (
    <section className="edge-tab-panel edge-monitor-panel">
      <div className="edge-tab-head">
        <div><span>Monitor</span><h2>Wide signal chart</h2></div>
        <div className="edge-tab-actions">
          <button type="button" onClick={() => onAction('refresh')}><RefreshCw size={14} />Refresh</button>
          <button type="button" onClick={() => onAction('diagnostics')}><Gauge size={14} />Diagnostics</button>
          <button type="button" onClick={() => onAction('ack')}><CheckCircle size={14} />Ack alerts</button>
          <button type="button" onClick={() => onAction('toggle-feed')}>{feedPaused ? <Play size={14} /> : <Pause size={14} />}{feedPaused ? 'Resume feed' : 'Pause feed'}</button>
        </div>
      </div>

      <div className="edge-monitor-tabs" role="tablist" aria-label="Monitor workspace tabs">
        {[
          ['monitor', 'Monitor'],
          ['assets', 'Assets'],
          ['diagnostics', 'Diagnostics'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={activeView === id ? 'active' : ''}
            role="tab"
            aria-selected={activeView === id}
            onClick={() => setActiveView(id as MonitorView)}
          >
            {label}
          </button>
        ))}
      </div>

      {activeView === 'monitor' && (
        <section className={`edge-monitor-chart-shell ${railCollapsed ? 'rail-collapsed' : 'rail-open'}`} aria-label="Chart-centric monitor workspace">
          <aside className="edge-monitor-rail" aria-label="Collapsed asset rail">
            <button
              type="button"
              className="edge-monitor-rail-toggle"
              aria-expanded={!railCollapsed}
              onClick={() => setRailCollapsed((value) => !value)}
            >
              {railCollapsed ? <ChevronRight size={15} /> : <ChevronLeft size={15} />}
              <span>{railCollapsed ? 'Open rail' : 'Collapse rail'}</span>
            </button>
            <div className="edge-monitor-rail-list">
              {tickers.map((ticker) => {
                const active = ticker.symbol === selected.symbol;
                return (
                  <button
                    type="button"
                    key={ticker.symbol}
                    className={`edge-monitor-rail-item ${active ? 'active' : ''}`}
                    aria-current={active ? 'true' : undefined}
                    aria-label={`Select ${ticker.symbol}`}
                    onClick={() => onSelect(ticker.symbol)}
                  >
                    <strong>{ticker.symbol}</strong>
                    {!railCollapsed && (
                      <>
                        <em>{ticker.watchers[0]?.plugin || ticker.status}</em>
                        <span>{ticker.change}</span>
                      </>
                    )}
                  </button>
                );
              })}
            </div>
          </aside>

          <div className="edge-monitor-main">
            <section className="edge-monitor-chart" aria-label={`${selected.symbol} wide signal chart`}>
              <div className="edge-monitor-chart-topline">
                <div>
                  <span>Wide signal chart</span>
                  <strong>{selected.symbol}</strong>
                </div>
                <div className="edge-monitor-chart-badge">{watcher ? `${watcher.plugin} / ${watcher.status}` : 'Pulse idle'}</div>
              </div>
              <svg className="edge-monitor-chart-path" viewBox="0 0 760 300" aria-hidden="true" preserveAspectRatio="none">
                <path d="M18 232 C84 205 126 220 184 182 S290 132 356 154 468 214 544 120 650 88 742 58" />
                <path className="fill" d="M18 232 C84 205 126 220 184 182 S290 132 356 154 468 214 544 120 650 88 742 58 L742 300 L18 300 Z" />
                <path className="signal" d="M18 178 C96 166 132 186 210 146 S334 100 424 122 558 172 742 92" />
              </svg>
              <div className="edge-monitor-chart-footer">
                <span>Last 12 candles</span>
                <span>{watcher ? watcher.trigger : 'no trigger'}</span>
                <span>{selected.signal}</span>
              </div>
            </section>

            <div className="edge-monitor-metrics">
              <StatusMetricBlock label="P&L" value="+$12,500.75" tone="green" />
              <StatusMetricBlock label="Trigger" value={watcher ? watcher.trigger : 'none'} tone="gold" />
              <StatusMetricBlock label="Pulse" value={runtime.pulseAvailable ? 'connected' : 'standalone'} tone={pulseTone} />
              <StatusMetricBlock label="Confidence" value={watcher ? 'watch active' : selected.status} tone="cyan" />
            </div>

            <div className="edge-monitor-command-strip" aria-label="Monitor command strip">
              <button type="button" className="primary" onClick={() => onCommand('arm')}>Arm Trigger</button>
              <button type="button" onClick={() => onCommand('mute')}>Mute</button>
              <button type="button" onClick={() => onAction('toggle-feed')}>{feedPaused ? 'Resume Feed' : 'Pause Feed'}</button>
              <button type="button" className="secondary" onClick={() => onCommand('risk sweep')}>Risk Sweep</button>
              <button type="button" className="secondary" onClick={() => onCommand('alert')}>Convert</button>
            </div>
          </div>
        </section>
      )}

      {activeView === 'assets' && (
        <section className="edge-monitor-asset-tab" aria-label="Asset tab">
          <section className="edge-tab-section wide">
            <SectionHead label="Full picker" value="asset tab" />
            <div className="edge-monitor-asset-grid">
              {tickers.map((ticker) => {
                const active = ticker.symbol === selected.symbol;
                return (
                  <button
                    type="button"
                    key={ticker.symbol}
                    className={`edge-monitor-asset-card edge-tone-${ticker.metrics[0]?.tone || 'cyan'} ${active ? 'active' : ''}`}
                    onClick={() => onSelect(ticker.symbol)}
                  >
                    <strong>{ticker.symbol}</strong>
                    <span>{ticker.status}</span>
                    <em>{ticker.change}</em>
                  </button>
                );
              })}
            </div>
          </section>
          <section className="edge-tab-section">
            <SectionHead label="Selected asset" value={selected.symbol} />
            <div className="edge-monitor-asset-detail">
              <div>Signal <strong>{selected.signal}</strong></div>
              <div>Price <strong>{selected.price.toFixed(2)}</strong></div>
              <div>Watcher <strong>{watcher ? watcher.plugin : 'None'}</strong></div>
              <div>Source <strong>{watcher ? watcher.source : 'Sentinel Pulse'}</strong></div>
            </div>
          </section>
          <section className="edge-tab-section">
            <SectionHead label="Asset actions" value="bulk" />
            <div className="edge-monitor-asset-actions">
              <button type="button" onClick={() => onCommand('arm')}>Enable watch</button>
              <button type="button" onClick={() => onCommand('risk sweep')}>Run risk sweep</button>
              <button type="button" onClick={() => onAction('diagnostics')}>Check runtime</button>
            </div>
          </section>
        </section>
      )}

      {activeView === 'diagnostics' && (
        <>
          <div className="edge-card-grid">
            <HealthCard
              label="Edge API"
              value={runtime.loading ? 'Checking' : runtime.connected ? 'Online' : 'Offline'}
              detail={runtime.error || 'Health endpoint'}
              tone={edgeApiTone}
            />
            <HealthCard
              label="Scheduler"
              value={schedulerValue}
              detail={runtime.connected ? 'Runtime control available' : 'Backend unavailable'}
              tone={schedulerTone}
            />
            <HealthCard
              label="Edge process"
              value={livenessValue}
              detail={runtime.edgeLive ? livenessDetail : runtime.connected ? 'Liveness unavailable' : 'Backend unavailable'}
              tone={livenessTone}
            />
            <HealthCard
              label="Readiness"
              value={readinessValue}
              detail={!runtime.connected ? 'Backend unavailable' : runtime.runtimeReady ? 'All required checks' : readinessDetail}
              tone={readinessTone}
            />
            <HealthCard
              label="API pressure"
              value={rateLimitValue}
              detail={runtime.rateLimitPressure === 'unknown' ? 'Rate-limit status unavailable' : rateLimitDetail}
              tone={rateLimitTone}
            />
            <HealthCard
              label="Frontend RUM"
              value={frontendRumValue}
              detail={frontendRumDetail}
              tone={frontendRumTone}
            />
            <HealthCard
              label="Pulse bridge"
              value={runtime.pulseAvailable ? 'Online' : 'Standalone'}
              detail={runtime.pulseAvailable ? 'Execution bridge detected' : 'Handoff suppressed'}
              tone={pulseTone}
            />
            <HealthCard
              label="Pulse circuit"
              value={pulseCircuitValue}
              detail={getPulseCircuitDetail(runtime.pulseCircuitState, runtime.pulseAvailable)}
              tone={pulseCircuitTone}
            />
            <HealthCard
              label="Kill switch"
              value={runtime.killSwitchActive ? 'Active' : 'Clear'}
              detail={runtime.killSwitchActive ? 'Global automation stop' : 'Safety guard clear'}
              tone={killSwitchTone}
            />
          </div>
          <div className="edge-section-grid">
            <section className="edge-tab-section wide">
              <SectionHead label="Runtime signals" value="live API" />
              {runtimeSignalRows.map((row) => <ServiceRow key={row[0]} row={row} />)}
            </section>
            <section className="edge-tab-section wide"><SectionHead label="Services" value="ops telemetry" />{serviceRows.map((row) => <ServiceRow key={row[0]} row={row} />)}</section>
            <section className="edge-tab-section"><SectionHead label="Watcher coverage" value="Sentinel Pulse" /><div className="edge-watcher-map">{tickers.map((ticker) => <button type="button" key={ticker.symbol} onClick={() => onSelect(ticker.symbol)}><strong>{ticker.symbol}</strong><em>{ticker.watchers[0] ? `${ticker.watchers[0].plugin} / ${ticker.watchers[0].status}` : 'Pulse idle'}</em></button>)}</div></section>
          </div>
        </>
      )}
    </section>
  );
}

function StatusMetricBlock({ label, value, tone }: { label: string; value: string; tone: Tone }) {
  return (
    <div className={`edge-monitor-metric edge-tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}


function formatRuntimePollAge(updatedAt?: string) {
  if (!updatedAt) return 'pending';

  const ageMs = Date.now() - new Date(updatedAt).getTime();
  if (!Number.isFinite(ageMs) || ageMs < 5000) return 'just now';

  const seconds = Math.floor(ageMs / 1000);
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}

function getReadinessDetail(failingChecks: string[]) {
  if (!failingChecks.length) return 'No failing checks reported';

  const visibleChecks = failingChecks.slice(0, 3).join(', ');
  const overflowCount = failingChecks.length - 3;
  return overflowCount > 0 ? `${visibleChecks} +${overflowCount} more failing` : `Failing: ${visibleChecks}`;
}

function getRateLimitDetail(remaining?: number, resetSeconds?: number) {
  const remainingText = typeof remaining === 'number' && Number.isFinite(remaining) ? `${remaining} requests remaining` : 'remaining unknown';
  const resetText = typeof resetSeconds === 'number' && Number.isFinite(resetSeconds) ? `reset in ${resetSeconds}s` : 'reset unknown';
  return `${remainingText}; ${resetText}`;
}

function getLivenessDetail(pid?: number, uptimeSeconds?: number) {
  const pidText = typeof pid === 'number' && Number.isFinite(pid) ? `pid ${pid}` : 'pid unknown';
  return `${pidText}; uptime ${formatUptime(uptimeSeconds)}`;
}

function getPulseCircuitTone(circuitState?: string): Tone {
  const normalizedState = normalizePulseCircuitState(circuitState);
  if (normalizedState === 'closed') return 'green';
  if (normalizedState === 'half_open') return 'gold';
  if (normalizedState === 'open') return 'red';
  return 'gold';
}

function formatPulseCircuitState(circuitState?: string) {
  const normalizedState = normalizePulseCircuitState(circuitState);
  if (normalizedState === 'closed') return 'Closed';
  if (normalizedState === 'half_open') return 'Half-open';
  if (normalizedState === 'open') return 'Open';
  return 'Unknown';
}

function getPulseCircuitDetail(circuitState: string | undefined, pulseAvailable: boolean) {
  const normalizedState = normalizePulseCircuitState(circuitState);
  if (normalizedState === 'closed') return 'Pulse requests allowed';
  if (normalizedState === 'half_open') return 'Probing Pulse recovery';
  if (normalizedState === 'open') return 'Pulse requests suppressed';
  return pulseAvailable ? 'Circuit status unavailable' : 'Pulse unavailable';
}

function normalizePulseCircuitState(circuitState?: string) {
  return String(circuitState || '').trim().toLowerCase().replace(/-/g, '_');
}

function formatUptime(uptimeSeconds?: number) {
  if (typeof uptimeSeconds !== 'number' || !Number.isFinite(uptimeSeconds)) return 'unknown';

  const seconds = Math.max(0, Math.floor(uptimeSeconds));
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;

  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

function getFrontendRumDetail(
  status: RuntimeState['frontendRumStatus'],
  sampleCount?: number,
  routeCount?: number,
  lastRoute?: string | null,
  ageSeconds?: number | null,
) {
  if (status === 'unknown') return 'RUM status unavailable';
  if (status === 'waiting') return 'Waiting for first browser sample';

  const samples = typeof sampleCount === 'number' && Number.isFinite(sampleCount) ? sampleCount : 0;
  const routes = typeof routeCount === 'number' && Number.isFinite(routeCount) ? routeCount : 0;
  const age = typeof ageSeconds === 'number' && Number.isFinite(ageSeconds) ? `${Math.round(ageSeconds)}s ago` : 'fresh';
  return `${samples} samples across ${routes} routes; ${lastRoute || '/'} ${age}`;
}
