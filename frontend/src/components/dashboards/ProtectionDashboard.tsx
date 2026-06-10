import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  Lock,
  Pause,
  Play,
  Radio,
  RefreshCw,
  Shield,
  ShieldAlert,
  SlidersHorizontal,
  TrendingDown,
  Unlock,
  XCircle,
} from 'lucide-react';
import { MetricCard } from '../cards/MetricCard';
import { api, type EdgeReadinessCheckDetail } from '@/lib/api';

interface ProtectionPosition {
  symbol: string;
  size?: number;
  quantity?: number;
  qty?: number;
  entry_price?: number;
  current_price?: number;
  market_value?: number;
  pnl_pct?: number;
  pnl_dollar?: number;
  unrealized_pnl?: number;
  drawdown_pct?: number;
  trailing_enabled?: boolean;
  trailing_stop_enabled?: boolean;
  stop_loss?: number;
  stop_price?: number;
  side?: string;
}

interface ProtectionState {
  loading: boolean;
  error: string | null;
  refreshedAt: string | null;
  health: any | null;
  stats: any | null;
  ready: any | null;
  pulse: any | null;
  killSwitch: any | null;
  automation: any | null;
  queue: any | null;
  positions: ProtectionPosition[];
}

const emptyState: ProtectionState = {
  loading: true,
  error: null,
  refreshedAt: null,
  health: null,
  stats: null,
  ready: null,
  pulse: null,
  killSwitch: null,
  automation: null,
  queue: null,
  positions: [],
};

const numberOrZero = (value: unknown) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const currency = (value: number) => `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

const percent = (value: number) => `${value.toFixed(2)}%`;

const normalizePositions = (raw: unknown): ProtectionPosition[] => {
  if (Array.isArray(raw)) return raw.filter(Boolean).map((item) => ({ ...item, symbol: String(item.symbol || '').toUpperCase() }));
  if (!raw || typeof raw !== 'object') return [];
  return Object.entries(raw as Record<string, any>).map(([symbol, value]) => ({
    ...(typeof value === 'object' && value ? value : {}),
    symbol: String((value && typeof value === 'object' && value.symbol) || symbol).toUpperCase(),
  }));
};

const statusPill = (ok: boolean, label: string) => (
  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
    ok ? 'bg-emerald-500/10 text-emerald-300' : 'bg-red-500/10 text-red-300'
  }`}>
    {ok ? <CheckCircle className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
    {label}
  </span>
);

const formatHandoffTime = (createdAt: unknown) => {
  const seconds = Number(createdAt);
  if (!Number.isFinite(seconds) || seconds <= 0) return 'unknown time';
  return new Date(seconds * 1000).toLocaleTimeString();
};

export const ProtectionDashboard: React.FC = () => {
  const [state, setState] = useState<ProtectionState>(emptyState);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [trailingPercent, setTrailingPercent] = useState(1.5);

  const load = async () => {
    try {
      const [health, stats, ready, pulse, killSwitch, automation, positions, queue] = await Promise.allSettled([
        api.getHealth(),
        api.getStats(),
        api.getReadiness(),
        api.getPulseStatus(),
        api.getKillSwitchStatus(),
        api.getAutomationStatus(),
        api.getPulsePositions(),
        api.getPulseQueue(),
      ]);

      setState({
        loading: false,
        error: null,
        health: health.status === 'fulfilled' ? health.value : null,
        stats: stats.status === 'fulfilled' ? stats.value : null,
        ready: ready.status === 'fulfilled' ? ready.value : null,
        pulse: pulse.status === 'fulfilled' ? pulse.value : null,
        killSwitch: killSwitch.status === 'fulfilled' ? killSwitch.value : null,
        automation: automation.status === 'fulfilled' ? automation.value : null,
        positions: positions.status === 'fulfilled' ? normalizePositions(positions.value) : [],
        queue: queue.status === 'fulfilled' ? queue.value : null,
        refreshedAt: new Date().toLocaleTimeString(),
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Unable to load protection state',
      }));
    }
  };

  useEffect(() => {
    load();
    const id = window.setInterval(load, 10000);
    return () => window.clearInterval(id);
  }, []);

  const paused = Boolean(state.health?.paused || state.stats?.paused);
  const running = Boolean(state.health?.running || state.stats?.running);
  const killSwitchActive = Boolean(state.killSwitch?.kill_switch_active);
  const pulseConnected = Boolean(state.pulse?.available || state.health?.pulse_available);
  const circuitState = state.pulse?.circuit_state || state.stats?.pulse_circuit_state || 'unknown';
  const automationSettings = state.automation?.settings || {};
  const latestHandoff = state.automation?.last_handoff || null;
  const latestSuppression = state.automation?.last_suppressed || null;
  const automationEnabled = Boolean(automationSettings.global_enabled);
  const queueSize = numberOrZero(state.queue?.size ?? state.queue?.pending ?? state.stats?.retry_queue?.size ?? state.stats?.retry_queue?.pending);
  const runtimeReady = Boolean(state.ready?.ready);
  const readinessChecks = state.ready?.checks && typeof state.ready.checks === 'object' ? state.ready.checks : {};
  const readinessDetails: Record<string, EdgeReadinessCheckDetail> =
    state.ready?.check_details && typeof state.ready.check_details === 'object' ? state.ready.check_details : {};
  const readinessFailures: string[] = Array.isArray(state.ready?.failing_checks) ? state.ready.failing_checks : [];
  const failingReadinessDetails: EdgeReadinessCheckDetail[] = Array.isArray(state.ready?.failing_check_details)
    ? state.ready.failing_check_details
    : readinessFailures.map((check) => {
        const detail = readinessDetails[check];
        return {
          name: detail?.name || check,
          label: detail?.label || check,
          description: detail?.description || check,
          required: detail?.required ?? true,
          ready: detail?.ready ?? Boolean(readinessChecks[check]),
        };
      });
  const handoffBlocked = state.ready ? !runtimeReady : true;

  const positionStats = useMemo(() => {
    const totalExposure = state.positions.reduce((sum, item) => sum + Math.abs(numberOrZero(item.market_value)), 0);
    const totalPnl = state.positions.reduce((sum, item) => sum + numberOrZero(item.pnl_dollar ?? item.unrealized_pnl), 0);
    const worstDrawdown = state.positions.reduce((worst, item) => Math.max(worst, Math.abs(numberOrZero(item.drawdown_pct))), 0);
    const trailingCount = state.positions.filter((item) => item.trailing_enabled || item.trailing_stop_enabled).length;
    return { totalExposure, totalPnl, worstDrawdown, trailingCount };
  }, [state.positions]);

  const runGuardedAction = async (key: string, action: () => Promise<unknown>) => {
    setBusyAction(key);
    try {
      await action();
      await load();
    } finally {
      setBusyAction(null);
    }
  };

  const toggleScheduler = () => runGuardedAction('scheduler', paused ? api.resumeScheduler.bind(api) : api.pauseScheduler.bind(api));

  const toggleKillSwitch = () => {
    const next = !killSwitchActive;
    const message = next
      ? 'Activate the global kill switch? This halts autonomous trading decisions.'
      : 'Clear the global kill switch? This allows protection rules to return to their configured mode.';
    if (!window.confirm(message)) return;
    runGuardedAction('kill-switch', () => api.toggleKillSwitch(next));
  };

  const setAutomationRecommendOnly = () => runGuardedAction('automation', () => api.updateAutomationSettings({
    global_enabled: false,
    mode: 'recommend_only',
  }));

  const enablePaperHandoff = () => {
    if (handoffBlocked) return;
    runGuardedAction('automation', () => api.updateAutomationSettings({
      global_enabled: true,
      mode: 'paper',
    }));
  };

  const enableTrailing = (symbol: string) => {
    if (!window.confirm(`Enable a ${trailingPercent.toFixed(2)}% trailing stop for ${symbol} through Pulse?`)) return;
    runGuardedAction(`trail-${symbol}`, () => api.enablePulseTrailingStop(symbol, trailingPercent));
  };

  const emergencyExit = (symbol: string) => {
    if (!window.confirm(`Send emergency exit for ${symbol} through Pulse?`)) return;
    runGuardedAction(`exit-${symbol}`, () => api.sendPulseEmergencyExit(symbol, 'Manual Protection tab emergency exit'));
  };

  if (state.loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-emerald-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="protection-dashboard">
      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-white">Protection Command</h2>
            <p className="mt-1 text-sm text-gray-400">
              Live risk controls for Edge scheduling, Pulse handoff, kill switch state, position protection, and exit staging.
            </p>
          </div>
          <button
            type="button"
            onClick={load}
            className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
          <span>Updated: {state.refreshedAt || 'not yet'}</span>
          <span>Circuit: {circuitState}</span>
          <span>Mode: {automationSettings.mode || 'recommend_only'}</span>
        </div>
        {state.error && <p className="mt-3 text-sm text-red-300">{state.error}</p>}
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          title="Global Guard"
          value={killSwitchActive ? 'Locked' : 'Clear'}
          subtitle={killSwitchActive ? 'Kill switch active' : 'Trading guard clear'}
          icon={killSwitchActive ? Lock : Unlock}
          color={killSwitchActive ? 'red' : 'green'}
        />
        <MetricCard
          title="Scheduler"
          value={paused ? 'Paused' : running ? 'Active' : 'Stopped'}
          subtitle={paused ? 'No new analysis cycles' : 'Protection polling active'}
          icon={paused ? Pause : Play}
          color={paused || !running ? 'yellow' : 'green'}
        />
        <MetricCard
          title="Pulse Link"
          value={pulseConnected ? 'Connected' : 'Standalone'}
          subtitle={`Circuit ${circuitState}`}
          icon={pulseConnected ? Radio : ShieldAlert}
          color={pulseConnected ? 'green' : 'yellow'}
        />
        <MetricCard
          title="Exposure"
          value={currency(positionStats.totalExposure)}
          subtitle={`${state.positions.length} positions tracked`}
          icon={Shield}
          color={positionStats.totalExposure > 0 ? 'blue' : 'yellow'}
        />
        <MetricCard
          title="Worst Drawdown"
          value={percent(positionStats.worstDrawdown)}
          subtitle={`${positionStats.trailingCount}/${state.positions.length} trailing protected`}
          icon={TrendingDown}
          color={positionStats.worstDrawdown > 5 ? 'red' : positionStats.worstDrawdown > 2 ? 'yellow' : 'green'}
        />
      </div>

      {handoffBlocked && (
        <div data-testid="protection-readiness-guard" className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-100">
          <div className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4" />
            Readiness blockers
          </div>
          <p className="mt-2 text-red-100/80">
            Edge runtime must be ready before enabling paper handoff.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(failingReadinessDetails.length > 0 ? failingReadinessDetails : [{
              name: 'readiness_unknown',
              label: 'readiness_unknown',
              description: 'Readiness status is unavailable.',
              required: true,
              ready: false,
            }]).map((detail) => (
              <span
                key={detail.name}
                title={detail.description || detail.name}
                className="rounded-full bg-red-500/15 px-2 py-0.5 text-xs text-red-100"
              >
                {detail.label}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6 xl:col-span-2">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
                <Shield className="h-5 w-5 text-emerald-400" />
                Guardrails
              </h3>
              <p className="mt-1 text-sm text-gray-500">
                These controls call existing Edge and Pulse endpoints. Emergency actions require confirmation.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={toggleScheduler}
                disabled={busyAction === 'scheduler'}
                className="inline-flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-sm font-medium text-blue-300 transition-colors hover:bg-blue-500/20 disabled:opacity-50"
              >
                {paused ? <Play className="h-4 w-4" /> : <Pause className="h-4 w-4" />}
                {paused ? 'Resume scheduler' : 'Pause scheduler'}
              </button>
              <button
                type="button"
                onClick={toggleKillSwitch}
                disabled={busyAction === 'kill-switch'}
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors disabled:opacity-50 ${
                  killSwitchActive
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                    : 'border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20'
                }`}
              >
                {killSwitchActive ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
                {killSwitchActive ? 'Clear kill switch' : 'Activate kill switch'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <GuardrailCard title="Kill switch" ok={!killSwitchActive} value={killSwitchActive ? 'Active' : 'Clear'} detail="Global hard stop exposed by /api/emergency/kill-switch." />
            <GuardrailCard title="Scheduler" ok={!paused && running} value={paused ? 'Paused' : running ? 'Running' : 'Stopped'} detail="Pause blocks new scheduled analysis cycles while preserving UI visibility." />
            <GuardrailCard title="Pulse circuit" ok={pulseConnected && circuitState !== 'OPEN'} value={circuitState} detail="Open circuits queue or suppress broker handoff attempts." />
            <GuardrailCard title="Retry queue" ok={queueSize === 0} value={String(queueSize)} detail="Emergency exits take priority when Pulse retry queue is active." />
          </div>
        </section>

        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <SlidersHorizontal className="h-5 w-5 text-blue-400" />
            Handoff Mode
          </h3>
          <dl className="mt-4 space-y-3 text-sm">
            <ProtectionDetail label="Automation" value={automationEnabled ? 'Enabled' : 'Recommend only'} />
            <ProtectionDetail label="Mode" value={automationSettings.mode || 'recommend_only'} />
            <ProtectionDetail label="Min confidence" value={String(automationSettings.min_confidence ?? 0.6)} />
            <ProtectionDetail label="Cooldown" value={`${automationSettings.cooldown_seconds ?? 0}s`} />
          </dl>
          <div className="mt-5 grid gap-2">
            <button
              type="button"
              onClick={setAutomationRecommendOnly}
              disabled={busyAction === 'automation'}
              className="rounded-lg border border-gray-700 bg-gray-950/60 px-3 py-2 text-sm font-medium text-gray-200 transition-colors hover:bg-gray-800 disabled:opacity-50"
            >
              Recommend only
            </button>
            <button
              type="button"
              onClick={enablePaperHandoff}
              disabled={busyAction === 'automation' || handoffBlocked}
              className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-300 transition-colors hover:bg-amber-500/20 disabled:opacity-50"
            >
              Enable paper handoff
            </button>
          </div>
          <div className="mt-5 grid gap-3">
            <HandoffEventCard
              title="Latest handoff"
              handoff={latestHandoff}
              empty="No handoff has been attempted yet."
            />
            <HandoffEventCard
              title="Latest suppression"
              handoff={latestSuppression}
              empty="No suppressed handoff has been recorded yet."
              suppressed
            />
          </div>
          <div className="mt-5 rounded-lg border border-gray-800 bg-gray-950/50 p-3 text-xs text-gray-400">
            Live mode is intentionally not enabled from this tab. Use Settings after reviewing ticker-level permissions.
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
              <AlertTriangle className="h-5 w-5 text-amber-400" />
              Position Protection
            </h3>
            <p className="mt-1 text-sm text-gray-500">
              Positions are read from Edge's Pulse sync. Trailing stop and emergency exit actions are sent to Pulse.
            </p>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-400">
            Trail %
            <input
              type="number"
              min="0.1"
              max="20"
              step="0.1"
              value={trailingPercent}
              onChange={(event) => setTrailingPercent(Number(event.target.value))}
              className="w-20 rounded-lg border border-gray-700 bg-gray-950 px-2 py-1 text-right text-white"
            />
          </label>
        </div>

        <div className="overflow-x-auto rounded-lg border border-gray-800">
          <table className="min-w-full divide-y divide-gray-800 text-sm">
            <thead className="bg-gray-950/60 text-left text-xs uppercase tracking-wide text-gray-500">
              <tr>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Entry</th>
                <th className="px-4 py-3">Current</th>
                <th className="px-4 py-3">P&L</th>
                <th className="px-4 py-3">Drawdown</th>
                <th className="px-4 py-3">Stop</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {state.positions.map((position) => {
                const symbol = position.symbol || 'UNKNOWN';
                const size = numberOrZero(position.size ?? position.quantity ?? position.qty);
                const pnl = numberOrZero(position.pnl_dollar ?? position.unrealized_pnl);
                const pnlPct = numberOrZero(position.pnl_pct);
                const drawdown = Math.abs(numberOrZero(position.drawdown_pct));
                const trailing = Boolean(position.trailing_enabled || position.trailing_stop_enabled);
                return (
                  <tr key={symbol} className="bg-gray-900/40">
                    <td className="px-4 py-3">
                      <div className="font-medium text-white">{symbol}</div>
                      <div className="text-xs uppercase text-gray-500">{position.side || 'position'}</div>
                    </td>
                    <td className="px-4 py-3 text-gray-300">{size.toFixed(2)}</td>
                    <td className="px-4 py-3 text-gray-300">{currency(numberOrZero(position.entry_price))}</td>
                    <td className="px-4 py-3 text-gray-300">{currency(numberOrZero(position.current_price))}</td>
                    <td className={`px-4 py-3 ${pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {currency(pnl)}
                      {pnlPct ? <span className="ml-2 text-xs text-gray-500">{percent(pnlPct)}</span> : null}
                    </td>
                    <td className={`px-4 py-3 ${drawdown > 5 ? 'text-red-400' : drawdown > 2 ? 'text-amber-300' : 'text-gray-300'}`}>
                      {percent(drawdown)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-gray-300">{currency(numberOrZero(position.stop_loss ?? position.stop_price))}</div>
                      <div className="mt-1">{statusPill(trailing, trailing ? 'trailing' : 'not trailing')}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => enableTrailing(symbol)}
                          disabled={busyAction === `trail-${symbol}`}
                          className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300 transition-colors hover:bg-emerald-500/20 disabled:opacity-50"
                        >
                          Trail
                        </button>
                        <button
                          type="button"
                          onClick={() => emergencyExit(symbol)}
                          disabled={busyAction === `exit-${symbol}`}
                          className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-xs font-medium text-red-300 transition-colors hover:bg-red-500/20 disabled:opacity-50"
                        >
                          Exit
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
              {state.positions.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-gray-500">
                    No Pulse-synced positions are currently available.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};

const GuardrailCard: React.FC<{ title: string; ok: boolean; value: string; detail: string }> = ({ title, ok, value, detail }) => (
  <div className={`rounded-lg border p-4 ${ok ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-red-500/20 bg-red-500/5'}`}>
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm font-medium text-gray-400">{title}</span>
      {statusPill(ok, ok ? 'ok' : 'attention')}
    </div>
    <div className="mt-3 text-2xl font-bold text-white">{value}</div>
    <p className="mt-2 text-sm text-gray-500">{detail}</p>
  </div>
);

const HandoffEventCard: React.FC<{ title: string; handoff: any | null; empty: string; suppressed?: boolean }> = ({
  title,
  handoff,
  empty,
  suppressed = false,
}) => {
  if (!handoff) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-3 text-xs text-gray-500">
        <div className="font-medium text-gray-300">{title}</div>
        <div className="mt-1">{empty}</div>
      </div>
    );
  }

  const failed = handoff.sent === false;
  const status = suppressed
    ? handoff.suppressed_reason || 'suppressed'
    : failed
      ? 'Delivery failed'
      : 'Delivered';
  const tone = failed || suppressed
    ? 'border-red-500/30 bg-red-500/10 text-red-100'
    : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100';

  return (
    <div className={`rounded-lg border p-3 text-xs ${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium text-white">{title}</span>
        <span className="shrink-0 rounded-full bg-black/20 px-2 py-0.5">{status}</span>
      </div>
      <div className="mt-2 grid gap-1 text-gray-200/90">
        <span>{String(handoff.symbol || 'UNKNOWN')} / {String(handoff.action || 'unknown')} / {String(handoff.mode || 'unknown')}</span>
        <span>{formatHandoffTime(handoff.created_at)}</span>
        {handoff.reason && <span className="break-words text-gray-300/80">{String(handoff.reason)}</span>}
        {handoff.suppressed_reason && <span className="break-words text-red-100/80">Blocked: {String(handoff.suppressed_reason)}</span>}
      </div>
    </div>
  );
};

const ProtectionDetail: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
    <dt className="text-gray-500">{label}</dt>
    <dd className="font-medium text-white">{value}</dd>
  </div>
);
