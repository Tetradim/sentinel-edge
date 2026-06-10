import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Clock,
  Database,
  Radio,
  Shield,
  WifiOff,
  XCircle,
} from 'lucide-react';
import { MetricCard } from '../cards/MetricCard';
import { api, type EdgeLiveness, type EdgeReadinessCheckDetail, type NormalizedEdgeReadiness } from '@/lib/api';

interface ProviderStatus {
  healthy: boolean;
  last_success: string | null;
  error_count: number;
}

interface ProviderInfo {
  key: string;
  label: string;
  configured: boolean;
  requires_key: boolean;
  intraday?: boolean;
  eod?: boolean;
}

interface HealthState {
  connected: boolean;
  loading: boolean;
  error: string | null;
  live: EdgeLiveness | null;
  ready: NormalizedEdgeReadiness | null;
  health: any | null;
  stats: any | null;
  pulse: any | null;
  killSwitch: any | null;
  providers: Record<string, ProviderStatus>;
  providerMeta: ProviderInfo[];
  fallbackOrder: string[];
  decisionsCount: number;
  automation: any | null;
  refreshedAt: string | null;
}

const emptyState: HealthState = {
  connected: false,
  loading: true,
  error: null,
  live: null,
  ready: null,
  health: null,
  stats: null,
  pulse: null,
  killSwitch: null,
  providers: {},
  providerMeta: [],
  fallbackOrder: [],
  decisionsCount: 0,
  automation: null,
  refreshedAt: null,
};

const formatAge = (iso: string | null) => {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'unknown';
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`;
};

const formatDurationSeconds = (value: unknown) => {
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return 'unknown';
  if (seconds < 60) return `${Math.max(0, Math.floor(seconds))}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${Math.floor(seconds % 60)}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
};

const statusBadge = (ok: boolean, text: string) => (
  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
    ok ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'
  }`}>
    {ok ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
    {text}
  </span>
);

export const AdvisorHealth: React.FC = () => {
  const [state, setState] = useState<HealthState>(emptyState);

  const load = async () => {
    try {
      const [live, ready, health, stats, pulse, killSwitch, providerHealth, providerCatalog, decisions, automation] = await Promise.allSettled([
        api.getLiveness(),
        api.getReadiness(),
        api.getHealth(),
        api.getStats(),
        api.getPulseStatus(),
        api.getKillSwitchStatus(),
        api.getProviderHealth(),
        api.getMarketDataProviders(),
        api.getDecisions(),
        api.getAutomationStatus(),
      ]);

      setState({
        connected: live.status === 'fulfilled' || health.status === 'fulfilled',
        loading: false,
        error: null,
        live: live.status === 'fulfilled' ? live.value : null,
        ready: ready.status === 'fulfilled' ? ready.value : null,
        health: health.status === 'fulfilled' ? health.value : null,
        stats: stats.status === 'fulfilled' ? stats.value : null,
        pulse: pulse.status === 'fulfilled' ? pulse.value : null,
        killSwitch: killSwitch.status === 'fulfilled' ? killSwitch.value : null,
        providers: providerHealth.status === 'fulfilled' ? providerHealth.value.providers || {} : {},
        providerMeta: providerCatalog.status === 'fulfilled' ? providerCatalog.value.providers || [] : [],
        fallbackOrder: providerCatalog.status === 'fulfilled' ? providerCatalog.value.fallback_order || [] : [],
        decisionsCount: decisions.status === 'fulfilled' ? decisions.value.count ?? decisions.value.decisions?.length ?? 0 : 0,
        automation: automation.status === 'fulfilled' ? automation.value : null,
        refreshedAt: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        connected: false,
        error: err instanceof Error ? err.message : 'Unable to load advisor health',
      }));
    }
  };

  useEffect(() => {
    load();
    const id = window.setInterval(load, 10000);
    return () => window.clearInterval(id);
  }, []);

  const activeProviders = useMemo(
    () => state.fallbackOrder.map((key) => state.providerMeta.find((provider) => provider.key === key)?.label || key),
    [state.fallbackOrder, state.providerMeta],
  );

  const providerRows = useMemo(() => {
    const labels = new Map(state.providerMeta.map((provider) => [provider.key, provider]));
    const orderedKeys = Array.from(new Set([...state.fallbackOrder, ...Object.keys(state.providers)]));
    return orderedKeys.map((key) => ({ key, meta: labels.get(key), status: state.providers[key] }));
  }, [state.fallbackOrder, state.providerMeta, state.providers]);

  const pulseConnected = Boolean(state.pulse?.available || state.health?.pulse_available);
  const processAlive = state.live?.status === 'alive';
  const readinessChecks = state.ready?.checks ?? {};
  const readinessDetails: Record<string, EdgeReadinessCheckDetail> = state.ready?.check_details ?? {};
  const failingReadinessDetails: EdgeReadinessCheckDetail[] = state.ready?.failing_check_details ?? [];
  const runtimeReady = Boolean(state.ready?.ready);
  const readinessSubtitle = state.ready
    ? `${failingReadinessDetails.length} failing readiness checks`
    : 'Readiness unavailable';
  const paused = Boolean(state.health?.paused || state.stats?.paused);
  const running = Boolean(state.health?.running || state.stats?.running);
  const killSwitchActive = Boolean(state.killSwitch?.kill_switch_active);
  const retryQueueSize = state.stats?.retry_queue?.size ?? state.stats?.retry_queue?.pending ?? 0;
  const automationSettings = state.automation?.settings || {};
  const handoffEnabled = Boolean(automationSettings.global_enabled);
  const lastHandoff = state.automation?.last_handoff;
  const lastSuppressed = state.automation?.last_suppressed;

  return (
    <div className="space-y-6" data-testid="advisor-health">
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-white">Advisor Operations Health</h2>
            <p className="mt-1 text-sm text-gray-400">
              Operational status for Sentinel Edge automation, market-data readiness, and Pulse handoff.
            </p>
          </div>
          <div className="text-xs text-gray-500">
            {state.refreshedAt ? `Refreshed ${state.refreshedAt}` : 'Loading…'}
          </div>
        </div>
        {state.error && <p className="mt-3 text-sm text-red-300">{state.error}</p>}
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-6">
        <MetricCard
          title="Edge Service"
          value={state.connected ? (running ? 'Running' : 'Stopped') : 'Offline'}
          subtitle={processAlive ? `Process up ${formatDurationSeconds(state.live?.uptime_seconds)}` : 'Liveness unavailable'}
          icon={state.connected ? Activity : WifiOff}
          color={state.connected && running ? 'green' : 'red'}
        />
        <MetricCard
          title="Runtime Readiness"
          value={state.ready ? (runtimeReady ? 'Ready' : 'Blocked') : 'Unknown'}
          subtitle={readinessSubtitle}
          icon={runtimeReady ? CheckCircle : AlertTriangle}
          color={runtimeReady ? 'green' : state.ready ? 'red' : 'yellow'}
        />
        <MetricCard
          title="Pulse Link"
          value={pulseConnected ? 'Connected' : 'Standalone'}
          subtitle={`Circuit: ${state.pulse?.circuit_state || state.stats?.pulse_circuit_state || 'unknown'}`}
          icon={pulseConnected ? Radio : WifiOff}
          color={pulseConnected ? 'green' : 'yellow'}
        />
        <MetricCard
          title="Pulse Handoff"
          value={handoffEnabled ? automationSettings.mode || 'Enabled' : 'Off'}
          subtitle={handoffEnabled ? 'Autonomous commands allowed' : 'Recommendations only'}
          icon={Shield}
          color={handoffEnabled ? (automationSettings.mode === 'live' ? 'red' : 'yellow') : 'blue'}
        />
        <MetricCard
          title="Kill Switch"
          value={killSwitchActive ? 'Active' : 'Clear'}
          subtitle="Read-only indicator"
          icon={Shield}
          color={killSwitchActive ? 'red' : 'green'}
        />
        <MetricCard
          title="Recommendations"
          value={state.decisionsCount}
          subtitle="Recent advisor decisions"
          icon={CheckCircle}
          color="blue"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6 xl:col-span-2">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
                <Database className="h-5 w-5 text-emerald-400" />
                Market Data Providers
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                Active intraday order: {activeProviders.length > 0 ? activeProviders.join(' → ') : 'none'}
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {providerRows.length === 0 && (
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4 text-sm text-gray-500">
                Provider health is not available yet.
              </div>
            )}
            {providerRows.map(({ key, meta, status }) => {
              const active = state.fallbackOrder.includes(key);
              const healthy = status?.healthy ?? false;
              return (
                <div key={key} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-800 bg-gray-900/60 p-4">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-white">{meta?.label || key}</span>
                      {active && <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-xs text-blue-300">active</span>}
                      {meta?.eod && !meta?.intraday && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">EOD only</span>}
                      {meta?.requires_key && !meta?.configured && <span className="rounded-full bg-gray-500/10 px-2 py-0.5 text-xs text-gray-400">env key missing</span>}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-gray-500">
                      <span>last success: {formatAge(status?.last_success || null)}</span>
                      <span>errors: {status?.error_count ?? 0}</span>
                    </div>
                  </div>
                  {status ? statusBadge(healthy, healthy ? 'healthy' : 'degraded') : statusBadge(false, 'unseen')}
                </div>
              );
            })}
          </div>
        </section>

        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <Clock className="h-5 w-5 text-purple-400" />
            Runtime Details
          </h3>
          <dl className="mt-4 space-y-3 text-sm">
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Process</dt>
              <dd className="font-medium text-white">{processAlive ? `Alive · ${formatDurationSeconds(state.live?.uptime_seconds)}` : 'Unknown'}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Readiness</dt>
              <dd className="font-medium text-white">{state.ready ? (runtimeReady ? 'Ready' : 'Blocked') : 'Unknown'}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Scheduler</dt>
              <dd className="font-medium text-white">{paused ? 'Paused' : running ? 'Active' : 'Stopped'}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Position mode</dt>
              <dd className="font-medium text-white">{state.health?.position_tracking_mode || state.stats?.position_tracking_mode || 'unknown'}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Pulse failures</dt>
              <dd className="font-medium text-white">{state.pulse?.failure_count ?? state.stats?.pulse_failures ?? 0}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Retry queue</dt>
              <dd className="font-medium text-white">{retryQueueSize}</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">Automation cooldown</dt>
              <dd className="font-medium text-white">{automationSettings.cooldown_seconds ?? 0}s</dd>
            </div>
            <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
              <dt className="text-gray-500">ORB levels</dt>
              <dd className="font-medium text-white">{state.stats?.orb_levels_count ?? 0}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-gray-500">Active tickers</dt>
              <dd className="font-medium text-white">{state.health?.active_tickers ?? state.stats?.active_tickers?.length ?? 0}</dd>
            </div>
          </dl>

          {(lastHandoff || lastSuppressed) && (
            <div className="mt-5 rounded-lg border border-gray-700 bg-gray-950/50 p-3 text-xs text-gray-400">
              <div className="mb-1 font-medium text-white">Latest automation event</div>
              {lastHandoff ? (
                <p>{lastHandoff.symbol} {lastHandoff.action} · sent={String(lastHandoff.sent)} · {lastHandoff.reason}</p>
              ) : (
                <p>{lastSuppressed.symbol} {lastSuppressed.action} · suppressed={lastSuppressed.suppressed_reason}</p>
              )}
            </div>
          )}

          {state.ready && !runtimeReady && (
            <div data-testid="edge-readiness-checks" className="mt-5 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
              <div className="mb-2 flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4" />
                {failingReadinessDetails.length} failing readiness checks
              </div>
              {failingReadinessDetails.length > 0 && (
                <div data-testid="edge-readiness-blockers" className="mb-3 flex flex-wrap gap-2">
                  {failingReadinessDetails.map((detail) => (
                    <span
                      key={detail.name}
                      title={detail.description || detail.name}
                      className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-100"
                    >
                      {detail.label}
                    </span>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {Object.entries(readinessChecks).map(([check, ok]) => {
                  const detail = readinessDetails[check];
                  return (
                    <span
                      key={check}
                      title={detail.description || detail.name}
                      className={`rounded-full px-2 py-0.5 text-xs ${ok ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/15 text-red-200'}`}
                    >
                      {detail.label}: {ok ? 'ok' : 'blocked'}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {(paused || killSwitchActive || !pulseConnected) && (
            <div className="mt-5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
              <div className="mb-1 flex items-center gap-2 font-medium">
                <AlertTriangle className="h-4 w-4" />
                Attention
              </div>
              <p className="text-amber-200/80">
                {killSwitchActive
                  ? 'Kill switch is active. Autonomous handoff should not place new commands.'
                  : paused
                    ? 'Scheduler is paused. Recommendations may be stale.'
                    : 'Pulse is not connected. Edge is operating standalone; handoff attempts are suppressed/backed off.'}
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
