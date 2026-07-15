import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ChevronDown, ChevronUp, Clock, Radio, RefreshCw } from 'lucide-react';

interface PendingCommand {
  action?: string;
  idempotency_key?: string;
  created_at?: number | string;
  reason?: string;
}

interface ExecutionDataStatus {
  source?: string;
  price?: number;
  volume?: number;
  age_seconds?: number | null;
  max_age_seconds?: number;
  executable?: boolean;
  cached_live_execution_enabled?: boolean;
}

interface AutomationOperationsPayload {
  generated_at?: string;
  automation?: {
    settings?: Record<string, unknown>;
    pending_commands?: Record<string, PendingCommand>;
    pending_count?: number;
    last_handoff?: Record<string, unknown> | null;
    last_suppressed?: Record<string, unknown> | null;
  };
  delivery?: {
    pulse_available?: boolean;
    circuit_state?: string;
    failure_count?: number;
    retry_queue?: Record<string, unknown>;
  };
  execution_data?: Record<string, ExecutionDataStatus>;
  summary?: {
    symbols?: number;
    executable_symbols?: number;
    stale_or_unavailable_symbols?: number;
    pending_commands?: number;
  };
}

function formatAge(value?: number | null) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return 'unknown';
  const seconds = Math.max(0, Number(value));
  if (seconds < 1) return '<1s';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  return `${(seconds / 60).toFixed(1)}m`;
}

function commandTime(value?: number | string) {
  if (value === undefined || value === null || value === '') return 'unknown';
  const numeric = Number(value);
  const date = Number.isFinite(numeric)
    ? new Date(numeric < 10_000_000_000 ? numeric * 1000 : numeric)
    : new Date(String(value));
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function safeJson(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? '');
  }
}

export function AutomationOperationsDrawer() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<AutomationOperationsPayload | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/bus/automation-operations', {
        headers: { Accept: 'application/json' },
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        const detail = typeof payload?.detail === 'string' ? payload.detail : `HTTP ${response.status}`;
        throw new Error(detail);
      }
      setData(payload);
      setError('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Automation operations unavailable');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, []);

  const pending = Object.entries(data?.automation?.pending_commands || {});
  const executionRows = useMemo(
    () => Object.entries(data?.execution_data || {}).sort(([a], [b]) => a.localeCompare(b)),
    [data?.execution_data],
  );
  const staleCount = data?.summary?.stale_or_unavailable_symbols || 0;
  const pendingCount = data?.automation?.pending_count || pending.length;
  const pulseAvailable = Boolean(data?.delivery?.pulse_available);
  const attention = Boolean(error || pendingCount || staleCount || !pulseAvailable);

  return (
    <aside className={`fixed bottom-4 right-4 z-[100] w-[min(94vw,34rem)] rounded-xl border shadow-2xl backdrop-blur ${attention ? 'border-amber-500/40 bg-gray-950/95' : 'border-emerald-500/30 bg-gray-950/95'}`} data-testid="automation-operations-drawer">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="flex min-w-0 items-center gap-3">
          <span className={`h-2.5 w-2.5 rounded-full ${attention ? 'bg-amber-400' : 'bg-emerald-400'}`} />
          <span className="min-w-0">
            <span className="block font-semibold text-white">Live Handoff Operations</span>
            <span className="block truncate text-xs text-gray-400">
              {error || `${pendingCount} pending · ${staleCount} stale · Pulse ${pulseAvailable ? 'connected' : 'unavailable'}`}
            </span>
          </span>
        </span>
        <span className="flex items-center gap-2 text-gray-400">
          {loading && <RefreshCw className="h-4 w-4 animate-spin" />}
          {open ? <ChevronDown className="h-5 w-5" /> : <ChevronUp className="h-5 w-5" />}
        </span>
      </button>

      {open && (
        <div className="max-h-[70vh] overflow-y-auto border-t border-gray-800 px-4 py-4">
          {error && (
            <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatusCard label="Pending" value={pendingCount} tone={pendingCount ? 'amber' : 'green'} />
            <StatusCard label="Executable" value={data?.summary?.executable_symbols || 0} tone="green" />
            <StatusCard label="Stale" value={staleCount} tone={staleCount ? 'amber' : 'green'} />
            <StatusCard label="Pulse" value={pulseAvailable ? 'Up' : 'Down'} tone={pulseAvailable ? 'green' : 'red'} />
          </div>

          <section className="mt-5">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-white"><Clock className="h-4 w-4 text-amber-400" />Pending exactly-once commands</h3>
              <span className="text-xs text-gray-500">Circuit {data?.delivery?.circuit_state || 'unknown'}</span>
            </div>
            {pending.length === 0 ? (
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-sm text-gray-500">No unresolved handoff commands.</div>
            ) : (
              <div className="space-y-2">
                {pending.map(([symbol, command]) => (
                  <div key={symbol} className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <strong className="text-white">{symbol} · {command.action || 'unknown'}</strong>
                      <span className="text-xs text-amber-300">{commandTime(command.created_at)}</span>
                    </div>
                    <div className="mt-2 break-all font-mono text-[11px] text-gray-400">{command.idempotency_key || 'missing idempotency key'}</div>
                    {command.reason && <div className="mt-2 text-xs text-gray-400">{command.reason}</div>}
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="mt-5">
            <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-white"><Activity className="h-4 w-4 text-cyan-400" />Executable market data</h3>
            {executionRows.length === 0 ? (
              <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3 text-sm text-gray-500">No active ticker data status.</div>
            ) : (
              <div className="space-y-2">
                {executionRows.map(([symbol, status]) => (
                  <div key={symbol} className="flex items-center justify-between gap-4 rounded-lg border border-gray-800 bg-gray-900/60 p-3">
                    <div>
                      <div className="font-medium text-white">{symbol}</div>
                      <div className="mt-1 text-xs text-gray-500">{status.source || 'unknown'} · age {formatAge(status.age_seconds)}</div>
                    </div>
                    <div className="text-right">
                      <div className={status.executable ? 'text-sm font-semibold text-emerald-300' : 'text-sm font-semibold text-red-300'}>{status.executable ? 'Executable' : 'Blocked'}</div>
                      <div className="mt-1 text-xs text-gray-500">{status.price ? `$${Number(status.price).toLocaleString()}` : 'no price'}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="mt-5 grid gap-3 sm:grid-cols-2">
            <DetailPanel title="Last handoff" icon={<Radio className="h-4 w-4 text-cyan-400" />} value={data?.automation?.last_handoff} />
            <DetailPanel title="Last suppressed" icon={<AlertTriangle className="h-4 w-4 text-amber-400" />} value={data?.automation?.last_suppressed} />
          </section>

          <div className="mt-4 flex items-center justify-between text-xs text-gray-600">
            <span>Failures: {data?.delivery?.failure_count || 0}</span>
            <span>{data?.generated_at ? new Date(data.generated_at).toLocaleTimeString() : 'not refreshed'}</span>
          </div>
        </div>
      )}
    </aside>
  );
}

function StatusCard({ label, value, tone }: { label: string; value: string | number; tone: 'green' | 'amber' | 'red' }) {
  const toneClass = tone === 'green' ? 'text-emerald-300' : tone === 'red' ? 'text-red-300' : 'text-amber-300';
  return <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3"><div className={`text-xl font-bold ${toneClass}`}>{value}</div><div className="mt-1 text-xs text-gray-500">{label}</div></div>;
}

function DetailPanel({ title, icon, value }: { title: string; icon: JSX.Element; value: unknown }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-3">
      <h4 className="flex items-center gap-2 text-sm font-medium text-white">{icon}{title}</h4>
      <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words text-[10px] leading-4 text-gray-500">{safeJson(value)}</pre>
    </div>
  );
}
