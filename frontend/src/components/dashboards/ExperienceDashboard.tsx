import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  Copy,
  Gauge,
  MousePointerClick,
  Timer,
  Zap,
} from 'lucide-react';
import { MetricCard } from '../cards/MetricCard';
import {
  WebVitalMetric,
  WebVitalsSnapshot,
  startWebVitalsCollection,
  subscribeToWebVitals,
  toPrometheusText,
} from '@/lib/webVitals';
import { api, ApiError, RateLimitStatus } from '@/lib/api';
import { formatElapsedAge } from '@/lib/time';

const ratingClasses = {
  good: 'bg-emerald-500/10 text-emerald-300',
  'needs-improvement': 'bg-amber-500/10 text-amber-300',
  poor: 'bg-red-500/10 text-red-300',
  pending: 'bg-gray-500/10 text-gray-400',
};

const ratingIcon = {
  good: CheckCircle,
  'needs-improvement': AlertTriangle,
  poor: AlertTriangle,
  pending: Timer,
};

const rateLimitPressureClasses = {
  normal: 'bg-emerald-500/10 text-emerald-300',
  warning: 'bg-amber-500/10 text-amber-300',
};

type ObservabilityPanelId = 'frontend_vitals' | 'rum_ingest' | 'api_rate_limits' | 'bucket_pressure';

interface ObservabilityPanelCard {
  id: ObservabilityPanelId;
  title: string;
  description: string;
  prometheusExpr: string;
  runbook: string;
}

interface FrontendRumBackendStatus {
  status?: string;
  last_route?: string;
  seconds_since_last?: number | null;
  sample_count?: number;
  route_count?: number;
}

const OBSERVABILITY_PANEL_CARDS: ObservabilityPanelCard[] = [
  {
    id: 'frontend_vitals',
    title: 'Frontend Web Vitals',
    description: 'Current browser session quality from RUM samples.',
    prometheusExpr: 'edge_frontend_web_vital_value',
    runbook: 'docs/runbooks/frontend-core-web-vitals.md',
  },
  {
    id: 'rum_ingest',
    title: 'RUM Ingest Freshness',
    description: 'Backend freshness for accepted browser telemetry.',
    prometheusExpr: 'edge_frontend_rum_last_received_timestamp_seconds',
    runbook: 'docs/runbooks/frontend-rum-ingest-missing.md',
  },
  {
    id: 'api_rate_limits',
    title: 'API Rate-Limit Rejections',
    description: 'Operator-facing pressure state for rejected requests.',
    prometheusExpr: 'edge_rate_limit_rejections_total',
    runbook: 'docs/runbooks/api-rate-limit-rejections.md',
  },
  {
    id: 'bucket_pressure',
    title: 'API Bucket Pressure',
    description: 'Tracked in-memory API limiter buckets.',
    prometheusExpr: 'edge_rate_limit_active_buckets',
    runbook: 'docs/runbooks/api-rate-limit-bucket-pressure.md',
  },
];

const formatMetric = (item: WebVitalMetric) => {
  if (item.value === null) return 'Pending';
  if (item.unit === 'score') return item.value.toFixed(3);
  return `${Math.round(item.value)}ms`;
};

const metricSubtitle = (item: WebVitalMetric) => {
  if (item.name === 'INP') return 'Responsiveness';
  if (item.name === 'LCP') return 'Largest content paint';
  if (item.name === 'CLS') return 'Layout stability';
  if (item.name === 'TTFB') return 'Backend response';
  return 'First content paint';
};

const metricColor = (item: WebVitalMetric): 'green' | 'yellow' | 'red' | 'blue' => {
  if (item.rating === 'good') return 'green';
  if (item.rating === 'needs-improvement') return 'yellow';
  if (item.rating === 'poor') return 'red';
  return 'blue';
};

export const ExperienceDashboard: React.FC = () => {
  const [snapshot, setSnapshot] = useState<WebVitalsSnapshot | null>(null);
  const [copied, setCopied] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);
  const [ingestStatus, setIngestStatus] = useState<'idle' | 'sent' | 'failed' | 'rate-limited'>('idle');
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number | null>(null);
  const [backendStatus, setBackendStatus] = useState<FrontendRumBackendStatus | null>(null);
  const [rateLimitStatus, setRateLimitStatus] = useState<RateLimitStatus | null>(null);
  const lastPostAt = useRef(0);
  const nextRumPostAfter = useRef(0);
  const latestSnapshot = useRef<WebVitalsSnapshot | null>(null);

  useEffect(() => {
    startWebVitalsCollection();
    return subscribeToWebVitals((nextSnapshot) => {
      latestSnapshot.current = nextSnapshot;
      setSnapshot(nextSnapshot);
    });
  }, []);

  useEffect(() => {
    const flushRum = () => {
      const currentSnapshot = latestSnapshot.current;
      if (!currentSnapshot || !hasRumPayload(currentSnapshot)) return;
      api.sendFrontendRumBeacon(currentSnapshot);
    };

    window.addEventListener('pagehide', flushRum);
    return () => window.removeEventListener('pagehide', flushRum);
  }, []);

  useEffect(() => {
    const loadRateLimitStatus = () => {
      api.getRateLimitStatus()
        .then(setRateLimitStatus)
        .catch(() => undefined);
    };

    loadRateLimitStatus();
    const interval = window.setInterval(loadRateLimitStatus, 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    const loadFrontendRumStatus = () => {
      api.getFrontendRumStatus()
        .then(setBackendStatus)
        .catch(() => undefined);
    };

    loadFrontendRumStatus();
    const interval = window.setInterval(loadFrontendRumStatus, 30000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!snapshot) return;
    if (!hasRumPayload(snapshot)) return;

    const now = Date.now();
    if (now < nextRumPostAfter.current) return;
    if (now - lastPostAt.current < 15000) return;
    lastPostAt.current = now;

    api.postFrontendRum(snapshot)
      .then(() => {
        setIngestStatus('sent');
        setRetryAfterSeconds(null);
        nextRumPostAfter.current = 0;
        return api.getFrontendRumStatus();
      })
      .then(setBackendStatus)
      .catch((error) => {
        if (error instanceof ApiError && error.status === 429 && error.retryAfterSeconds) {
          nextRumPostAfter.current = Date.now() + error.retryAfterSeconds * 1000;
          setRetryAfterSeconds(error.retryAfterSeconds);
          setIngestStatus('rate-limited');
          return;
        }
        setIngestStatus('failed');
      });
  }, [snapshot]);

  const metrics = snapshot?.metrics || [];
  const webVitalScore = useMemo(() => {
    if (metrics.length === 0) return 0;
    const observed = metrics.filter((item) => item.rating !== 'pending');
    if (observed.length === 0) return 0;
    const good = observed.filter((item) => item.rating === 'good').length;
    return Math.round((good / observed.length) * 100);
  }, [metrics]);

  const worstMetric = useMemo(() => {
    const ranked = [...metrics].sort((a, b) => ratingRank(b.rating) - ratingRank(a.rating));
    return ranked[0];
  }, [metrics]);

  const copyPrometheus = async () => {
    if (!snapshot) return;
    try {
      setCopyFailed(false);
      await navigator.clipboard.writeText(toPrometheusText(snapshot));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
      setCopyFailed(true);
      window.setTimeout(() => setCopyFailed(false), 1800);
    }
  };

  return (
    <div className="space-y-6" data-testid="experience-dashboard">
      <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-white">Frontend Experience</h2>
            <p className="mt-1 text-sm text-gray-400">
              Real-user browser responsiveness, paint timing, layout stability, and long-task signals for this Edge UI session.
            </p>
          </div>
          <button
            type="button"
            onClick={copyPrometheus}
            disabled={!snapshot}
            className="inline-flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-2 text-sm font-medium text-blue-300 transition-colors hover:bg-blue-500/20 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Copy className="h-4 w-4" />
            {copied ? 'Copied' : copyFailed ? 'Copy failed' : 'Copy Prometheus'}
          </button>
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-gray-500">
          <span>Route: {snapshot?.route || window.location.pathname || '/'}</span>
          <span>Updated: {snapshot ? new Date(snapshot.collectedAt).toLocaleTimeString() : 'collecting'}</span>
          <span>Backend ingest: {formatIngestStatus(ingestStatus, retryAfterSeconds)}</span>
          {backendStatus?.last_route && (
            <span>Last accepted: {backendStatus.last_route} {formatElapsedAge(backendStatus.seconds_since_last)}</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <RumStatusTile
          label="Backend RUM"
          value={formatRumBackendStatus(backendStatus?.status)}
          detail={backendStatus?.last_route ? `Last route ${backendStatus.last_route}` : 'Waiting for browser samples'}
        />
        <RumStatusTile
          label="Backend samples"
          value={String(backendStatus?.sample_count ?? 'Pending')}
          detail="Accepted browser telemetry snapshots"
        />
        <RumStatusTile
          label="Routes monitored"
          value={String(backendStatus?.route_count ?? 'Pending')}
          detail={`Freshness ${formatRumFreshness(backendStatus?.seconds_since_last)}`}
          tone={rumFreshnessTone(backendStatus?.seconds_since_last)}
        />
      </div>

      <section className="border-y border-gray-800 bg-gray-950/40 px-4 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
              <Gauge className="h-5 w-5 text-cyan-400" />
              Observability Panels
            </h3>
            <p className="mt-1 text-sm text-gray-400">
              Grafana-style observability panels inside Experience, mapped to Prometheus expressions and local runbooks.
            </p>
          </div>
          <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs font-semibold text-cyan-200">
            /metrics
          </span>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {OBSERVABILITY_PANEL_CARDS.map((panel) => (
            <ObservabilityPanelTile
              key={panel.id}
              panel={panel}
              value={formatObservabilityPanelValue(panel.id, webVitalScore, backendStatus, rateLimitStatus)}
            />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-5">
        {metrics.map((item) => (
          <MetricCard
            key={item.name}
            title={item.name}
            value={formatMetric(item)}
            subtitle={metricSubtitle(item)}
            icon={item.name === 'INP' ? MousePointerClick : item.name === 'CLS' ? Gauge : Timer}
            color={metricColor(item)}
          />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-4">
        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <Activity className="h-5 w-5 text-emerald-400" />
            Session Score
          </h3>
          <div className="mt-5">
            <div className="flex items-end gap-2">
              <span className="text-5xl font-bold text-white">{webVitalScore}</span>
              <span className="pb-2 text-sm text-gray-500">/ 100</span>
            </div>
            <div className="mt-4 h-2 rounded-full bg-gray-800">
              <div
                className="h-2 rounded-full bg-emerald-400 transition-all"
                style={{ width: `${webVitalScore}%` }}
              />
            </div>
            <p className="mt-4 text-sm text-gray-400">
              {worstMetric?.rating === 'poor'
                ? `${worstMetric.name} is currently the limiting experience signal.`
                : worstMetric?.rating === 'needs-improvement'
                  ? `${worstMetric.name} has room to improve.`
                  : 'Observed Web Vitals are currently within target.'}
            </p>
          </div>
        </section>

        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <Gauge className="h-5 w-5 text-blue-400" />
            API Limiter
          </h3>
          <div className="mt-5 space-y-4">
            <div>
              <div className="text-xs uppercase tracking-wide text-gray-500">Pressure</div>
              <div className="mt-2">
                <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${rateLimitPressureClasses[rateLimitStatus?.pressure || 'normal']}`}>
                  {formatRateLimitPressure(rateLimitStatus?.pressure)}
                </span>
              </div>
            </div>
            <dl className="space-y-3 text-sm">
              <RuntimeRow label="Tracked buckets" value={String(rateLimitStatus?.tracked_clients ?? 'Pending')} />
              <RuntimeRow label="Remaining" value={String(rateLimitStatus?.remaining_requests ?? 'Pending')} />
              <RuntimeRow label="Reset" value={rateLimitStatus ? `${rateLimitStatus.reset_seconds}s` : 'Pending'} />
              <RuntimeRow label="Warning threshold" value={String(rateLimitStatus?.bucket_pressure_warning_threshold ?? 'Pending')} />
              <RuntimeRow label="Window" value={rateLimitStatus ? `${rateLimitStatus.window_seconds}s` : 'Pending'} />
            </dl>
          </div>
        </section>

        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6 xl:col-span-2">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <Zap className="h-5 w-5 text-yellow-400" />
            Metric Status
          </h3>
          <div className="mt-4 overflow-hidden rounded-lg border border-gray-800">
            <table className="min-w-full divide-y divide-gray-800 text-sm">
              <thead className="bg-gray-950/60 text-left text-xs uppercase tracking-wide text-gray-500">
                <tr>
                  <th className="px-4 py-3">Metric</th>
                  <th className="px-4 py-3">Value</th>
                  <th className="px-4 py-3">Rating</th>
                  <th className="px-4 py-3">Source</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {metrics.map((item) => {
                  const Icon = ratingIcon[item.rating];
                  return (
                    <tr key={item.name} className="bg-gray-900/40">
                      <td className="px-4 py-3 font-medium text-white">{item.name}</td>
                      <td className="px-4 py-3 text-gray-300">{formatMetric(item)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${ratingClasses[item.rating]}`}>
                          <Icon className="h-3 w-3" />
                          {item.rating}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500">{item.source}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <MousePointerClick className="h-5 w-5 text-blue-400" />
            Slow Interactions
          </h3>
          <div className="mt-4 space-y-3">
            {(snapshot?.slowInteractions.length || 0) === 0 && (
              <div className="rounded-lg border border-gray-800 bg-gray-950/50 p-4 text-sm text-gray-500">
                No interaction timings have been captured yet.
              </div>
            )}
            {snapshot?.slowInteractions.map((item, index) => (
              <div key={`${item.startTime}-${index}`} className="flex items-center justify-between gap-4 rounded-lg border border-gray-800 bg-gray-950/50 p-4">
                <div className="min-w-0">
                  <div className="truncate font-medium text-white">{item.target}</div>
                  <div className="mt-1 text-xs text-gray-500">{item.type}</div>
                </div>
                <div className="shrink-0 text-sm font-semibold text-gray-200">{Math.round(item.duration)}ms</div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-gray-800 bg-gradient-to-br from-gray-900/90 to-gray-800/50 p-6">
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <Timer className="h-5 w-5 text-purple-400" />
            Runtime Timing
          </h3>
          <dl className="mt-4 space-y-3 text-sm">
            <RuntimeRow label="DOM ready" value={formatMs(snapshot?.navigation.domContentLoadedMs)} />
            <RuntimeRow label="Load complete" value={formatMs(snapshot?.navigation.loadCompleteMs)} />
            <RuntimeRow label="Transfer size" value={formatBytes(snapshot?.navigation.transferSize)} />
            <RuntimeRow label="Long tasks" value={String(snapshot?.longTasks.length || 0)} />
          </dl>
          {(snapshot?.longTasks.length || 0) > 0 && (
            <div className="mt-5 space-y-2">
              {snapshot?.longTasks.slice(0, 5).map((item, index) => (
                <div key={`${item.startTime}-${index}`} className="flex justify-between rounded-lg bg-gray-950/50 px-3 py-2 text-xs">
                  <span className="text-gray-500">{Math.round(item.startTime)}ms after navigation</span>
                  <span className="font-medium text-gray-200">{Math.round(item.duration)}ms</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
};

const RuntimeRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between gap-3 border-b border-gray-800 pb-3">
    <dt className="text-gray-500">{label}</dt>
    <dd className="font-medium text-white">{value}</dd>
  </div>
);

const rumStatusToneClasses = {
  normal: 'border-emerald-500/20 bg-emerald-500/5 text-emerald-200',
  warning: 'border-amber-500/20 bg-amber-500/5 text-amber-200',
};

const RumStatusTile: React.FC<{ label: string; value: string; detail: string; tone?: keyof typeof rumStatusToneClasses }> = ({
  label,
  value,
  detail,
  tone = 'normal',
}) => (
  <div className={`rounded-xl border p-4 ${rumStatusToneClasses[tone]}`}>
    <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
    <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    <div className="mt-1 text-xs text-gray-400">{detail}</div>
  </div>
);

const ObservabilityPanelTile: React.FC<{ panel: ObservabilityPanelCard; value: string }> = ({ panel, value }) => (
  <div className="min-w-0 rounded-lg border border-gray-800 bg-gray-950/60 p-4">
    <div className="text-xs uppercase text-gray-500">{panel.title}</div>
    <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    <p className="mt-1 text-xs text-gray-400">{panel.description}</p>
    <div className="mt-3 space-y-2 border-t border-gray-800 pt-3 text-xs">
      <div>
        <div className="text-gray-500">Prometheus expression</div>
        <code className="mt-1 block break-words rounded bg-gray-900 px-2 py-1 text-cyan-200">
          {panel.prometheusExpr}
        </code>
      </div>
      <div>
        <div className="text-gray-500">Runbook</div>
        <code className="mt-1 block break-words rounded bg-gray-900 px-2 py-1 text-amber-200">
          {panel.runbook}
        </code>
      </div>
    </div>
  </div>
);

function ratingRank(rating: WebVitalMetric['rating']) {
  if (rating === 'poor') return 3;
  if (rating === 'needs-improvement') return 2;
  if (rating === 'good') return 1;
  return 0;
}

function hasRumPayload(snapshot: WebVitalsSnapshot) {
  return (
    snapshot.metrics.some((item) => item.value !== null) ||
    snapshot.longTasks.length > 0 ||
    snapshot.slowInteractions.length > 0
  );
}

function formatIngestStatus(status: 'idle' | 'sent' | 'failed' | 'rate-limited', retryAfterSeconds: number | null) {
  if (status === 'sent') return 'active';
  if (status === 'failed') return 'unavailable';
  if (status === 'rate-limited') {
    return retryAfterSeconds ? `rate-limited, retrying in ${retryAfterSeconds}s` : 'rate-limited';
  }
  return 'waiting';
}

function formatRateLimitPressure(pressure?: RateLimitStatus['pressure']) {
  if (pressure === 'warning') return 'Warning';
  return 'Normal';
}

function formatRumBackendStatus(status?: string) {
  if (status === 'receiving') return 'Receiving';
  return 'Waiting';
}

function formatRumFreshness(value?: number | null) {
  if (value === null || value === undefined) return 'Pending';
  if (value < 1) return 'just now';
  if (value < 60) return `${Math.round(value)}s ago`;
  return `${Math.round(value / 60)}m ago`;
}

function formatObservabilityPanelValue(
  panelId: ObservabilityPanelId,
  webVitalScore: number,
  backendStatus: FrontendRumBackendStatus | null,
  rateLimitStatus: RateLimitStatus | null,
) {
  if (panelId === 'frontend_vitals') return `${webVitalScore}/100`;
  if (panelId === 'rum_ingest') return formatRumFreshness(backendStatus?.seconds_since_last);
  if (panelId === 'api_rate_limits') return formatRateLimitPressure(rateLimitStatus?.pressure);
  return String(rateLimitStatus?.tracked_clients ?? 'Pending');
}

function rumFreshnessTone(value?: number | null): keyof typeof rumStatusToneClasses {
  if (value === null || value === undefined) return 'warning';
  return value > 1800 ? 'warning' : 'normal';
}

function formatMs(value?: number | null) {
  if (value === null || value === undefined) return 'Pending';
  return `${Math.round(value)}ms`;
}

function formatBytes(value?: number | null) {
  if (value === null || value === undefined) return 'Unknown';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}
