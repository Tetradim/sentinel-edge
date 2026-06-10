import { CheckCircle, Gauge, Pause, Play, RefreshCw } from 'lucide-react';
import { serviceRows } from '../data';
import type { RuntimeState, Ticker, Tone } from '../types';
import { HealthCard, SectionHead, ServiceRow } from './shared';

export function MonitorPanel({
  runtime,
  feedPaused,
  tickers,
  onAction,
  onSelect,
}: {
  runtime: RuntimeState;
  feedPaused: boolean;
  tickers: Ticker[];
  onAction: (action: string) => void;
  onSelect: (symbol: string) => void;
}) {
  const edgeApiTone: Tone = runtime.connected ? 'green' : runtime.loading ? 'gold' : 'red';
  const schedulerTone: Tone = runtime.schedulerPaused ? 'gold' : runtime.connected ? 'green' : 'red';
  const pulseTone: Tone = runtime.pulseAvailable ? 'green' : 'gold';
  const killSwitchTone: Tone = runtime.killSwitchActive ? 'red' : 'green';
  const readinessTone: Tone = !runtime.connected ? 'red' : runtime.runtimeReady ? 'green' : 'gold';
  const rateLimitTone: Tone = runtime.rateLimitPressure === 'normal' ? 'green' : runtime.rateLimitPressure === 'warning' ? 'gold' : 'red';
  const frontendRumTone: Tone = runtime.frontendRumStatus === 'receiving' ? 'green' : runtime.frontendRumStatus === 'waiting' ? 'gold' : 'red';
  const schedulerValue = !runtime.connected ? 'Unknown' : runtime.schedulerPaused ? 'Paused' : 'Active';
  const readinessValue = !runtime.connected ? 'Unknown' : runtime.runtimeReady ? 'Ready' : 'Not ready';
  const readinessDetail = getReadinessDetail(runtime.readinessFailingChecks);
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
    </section>
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
