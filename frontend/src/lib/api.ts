const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const FRONTEND_RUM_PATH = '/api/frontend/rum';
const FRONTEND_RUM_BEACON_MAX_BYTES = 60 * 1024;
const FRONTEND_RUM_BEACON_LIST_LIMIT = 5;

export interface RateLimitStatus {
  tracked_clients: number;
  remaining_requests: number;
  reset_seconds: number;
  window_seconds: number;
  max_requests_per_window: number;
  bucket_pressure_warning_threshold: number;
  pressure: 'normal' | 'warning';
}

export interface EdgeLiveness {
  status: 'alive';
  service: string;
  pid: number;
  uptime_seconds: number;
  timestamp: string;
}

export interface EdgeReadinessCheckDetail {
  label: string;
  description: string;
  required: boolean;
  ready: boolean;
}

export interface EdgeReadiness {
  ready: boolean;
  status: 'ready' | 'not_ready';
  checks: Record<string, boolean>;
  check_details?: Record<string, EdgeReadinessCheckDetail>;
  failing_checks: string[];
  timestamp?: string;
}

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail: unknown;
  retryAfterSeconds?: number;
  rateLimitLimit?: number;
  rateLimitRemaining?: number;
  rateLimitResetSeconds?: number;

  constructor(
    status: number,
    statusText: string,
    detail: unknown,
    retryAfterSeconds?: number,
    rateLimit?: Partial<Pick<ApiError, 'rateLimitLimit' | 'rateLimitRemaining' | 'rateLimitResetSeconds'>>,
  ) {
    const message = getApiErrorMessage(status, statusText, detail);
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.statusText = statusText;
    this.detail = detail;
    this.retryAfterSeconds = retryAfterSeconds;
    this.rateLimitLimit = rateLimit?.rateLimitLimit;
    this.rateLimitRemaining = rateLimit?.rateLimitRemaining;
    this.rateLimitResetSeconds = rateLimit?.rateLimitResetSeconds;
  }
}

async function fetchJSON<T = any>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const payload = await parseResponsePayload(res);
    const retryAfterSeconds =
      parseRetryAfterSeconds(res.headers.get('Retry-After')) ??
      parseRetryAfterSeconds(payload?.detail?.retry_after_seconds);
    const rateLimit = parseRateLimitHeaders(res.headers);
    throw new ApiError(res.status, res.statusText, payload?.detail ?? payload, retryAfterSeconds, rateLimit);
  }
  if (!isJsonResponse(res)) {
    throw new ApiError(res.status, res.statusText, {
      error: `Expected JSON response from ${path}, received ${res.headers.get('Content-Type') || 'unknown content type'}`,
    });
  }
  return res.json();
}

class ApiClient {
  async getHealth() {
    return fetchJSON('/api/health');
  }

  async getLiveness() {
    return fetchJSON<EdgeLiveness>('/api/live');
  }

  async getReadiness() {
    try {
      return await fetchJSON<EdgeReadiness>('/api/ready');
    } catch (err) {
      if (err instanceof ApiError && err.status === 503 && isEdgeReadiness(err.detail)) {
        return err.detail;
      }
      throw err;
    }
  }

  async getProviderHealth() {
    return fetchJSON('/api/providers/health');
  }

  async getMarketDataProviders() {
    return fetchJSON('/api/market-data/providers');
  }

  async getPulseStatus() {
    return fetchJSON('/api/pulse/status');
  }

  async getPulsePositions() {
    return fetchJSON('/api/pulse/positions');
  }

  async getPulseQueue() {
    return fetchJSON('/api/pulse/queue');
  }

  async postFrontendRum(snapshot: any) {
    return fetchJSON(FRONTEND_RUM_PATH, {
      method: 'POST',
      body: JSON.stringify(snapshot),
    });
  }

  sendFrontendRumBeacon(snapshot: any) {
    const body = toFrontendRumBeaconBody(snapshot);
    const url = `${BACKEND_URL}${FRONTEND_RUM_PATH}`;

    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const payload = new Blob([body], { type: 'application/json' });
      if (navigator.sendBeacon(url, payload)) return true;
    }

    if (typeof fetch !== 'undefined') {
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true,
      }).catch(() => undefined);
      return true;
    }

    return false;
  }

  async getFrontendRumStatus() {
    return fetchJSON('/api/frontend/rum/status');
  }

  async getRateLimitStatus() {
    return fetchJSON<RateLimitStatus>('/api/rate-limit/status');
  }

  async getStats() {
    return fetchJSON('/api/stats');
  }

  async getTickers() {
    return fetchJSON('/api/tickers');
  }

  async addTicker(symbol: string) {
    return fetchJSON(`/api/tickers/${symbol}`, { method: 'POST' });
  }

  async removeTicker(symbol: string) {
    return fetchJSON(`/api/tickers/${symbol}`, { method: 'DELETE' });
  }

  async updateTickerConfig(symbol: string, config: any) {
    return fetchJSON(`/api/tickers/${symbol}/config`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async getTickerConfig(symbol: string) {
    return fetchJSON(`/api/tickers/${symbol}/config`);
  }

  async getOrbLevels(symbol: string) {
    return fetchJSON(`/api/orb/${symbol}`);
  }

  async getMarkets() {
    return fetchJSON('/api/markets');
  }

  async runBacktest(symbol: string, startDate: string, endDate: string, initialCapital?: number, monteCarlo: any = {}) {
    return fetchJSON('/api/backtest', {
      method: 'POST',
      body: JSON.stringify({
        symbol,
        start_date: startDate,
        end_date: endDate,
        initial_capital: initialCapital || 10000,
        monte_carlo_enabled: monteCarlo.enabled ?? true,
        monte_carlo_method: monteCarlo.method || 'bootstrap',
        num_simulations: monteCarlo.simulations || 1000,
        volatility_multiplier: monteCarlo.volatilityMultiplier || 1,
        monte_carlo_confidence_level: monteCarlo.confidenceLevel || 0.95,
        monte_carlo_random_seed: monteCarlo.randomSeed === '' ? null : monteCarlo.randomSeed,
        monte_carlo_include_paths: monteCarlo.includePaths ?? true,
        monte_carlo_saved_charts: monteCarlo.savedCharts ?? true,
        monte_carlo_sample_path_count: monteCarlo.samplePathCount || 25,
        monte_carlo_histogram_bins: monteCarlo.histogramBins || 20,
        monte_carlo_ruin_threshold_pct: monteCarlo.ruinThresholdPct || 50,
        monte_carlo_block_size: monteCarlo.blockSize || 5,
      }),
    });
  }

  async optimizeStrategy(symbol: string, startDate: string, endDate: string, paramGrid: any, initialCapital?: number) {
    return fetchJSON('/api/backtest/optimize', {
      method: 'POST',
      body: JSON.stringify({
        symbol,
        start_date: startDate,
        end_date: endDate,
        param_grid: paramGrid,
        initial_capital: initialCapital || 10000,
      }),
    });
  }

  async getDryRunStatus() {
    return fetchJSON('/api/dry-run/status');
  }

  async pauseScheduler() {
    return fetchJSON('/api/control/pause', { method: 'POST' });
  }

  async resumeScheduler() {
    return fetchJSON('/api/control/resume', { method: 'POST' });
  }

  async toggleKillSwitch(state: boolean) {
    return fetchJSON(`/api/emergency/kill-switch?state=${state}`, { method: 'POST' });
  }

  async getKillSwitchStatus() {
    return fetchJSON('/api/emergency/kill-switch');
  }

  async getAutomationStatus() {
    return fetchJSON('/api/automation');
  }

  async updateAutomationSettings(settings: any) {
    return fetchJSON('/api/automation', {
      method: 'PUT',
      body: JSON.stringify(settings),
    });
  }

  async updateTickerAutomation(symbol: string, enabled: boolean) {
    return fetchJSON(`/api/automation/tickers/${symbol}`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    });
  }

  async getCorrelation() {
    return fetchJSON('/api/correlation');
  }

  async getDecisions() {
    return fetchJSON('/api/decisions');
  }

  async enablePulseTrailingStop(symbol: string, percent: number) {
    return fetchJSON(`/api/pulse/trailing-stop/${encodeURIComponent(symbol)}?percent=${encodeURIComponent(String(percent))}`, {
      method: 'POST',
    });
  }

  async sendPulseEmergencyExit(symbol: string, reason = 'Manual Protection tab trigger') {
    return fetchJSON(`/api/pulse/emergency-exit/${encodeURIComponent(symbol)}?reason=${encodeURIComponent(reason)}`, {
      method: 'POST',
    });
  }
}

function toFrontendRumBeaconBody(snapshot: any) {
  const fullBody = JSON.stringify(snapshot);
  if (rumBodyByteLength(fullBody) <= FRONTEND_RUM_BEACON_MAX_BYTES) return fullBody;

  const compactBody = JSON.stringify(compactFrontendRumSnapshot(snapshot));
  if (rumBodyByteLength(compactBody) <= FRONTEND_RUM_BEACON_MAX_BYTES) return compactBody;

  return JSON.stringify({
    ...compactFrontendRumSnapshot(snapshot),
    slowInteractions: [],
    longTasks: [],
  });
}

function compactFrontendRumSnapshot(snapshot: any) {
  const slowInteractions = Array.isArray(snapshot?.slowInteractions) ? snapshot.slowInteractions : [];
  const longTasks = Array.isArray(snapshot?.longTasks) ? snapshot.longTasks : [];

  return {
    route: snapshot?.route || '/',
    collectedAt: snapshot?.collectedAt,
    metrics: Array.isArray(snapshot?.metrics) ? snapshot.metrics : [],
    navigation: snapshot?.navigation,
    slowInteractions: slowInteractions.slice(0, FRONTEND_RUM_BEACON_LIST_LIMIT),
    longTasks: longTasks.slice(0, FRONTEND_RUM_BEACON_LIST_LIMIT),
  };
}

function rumBodyByteLength(body: string) {
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(body).length;
  return body.length;
}

async function parseResponsePayload(res: Response): Promise<any | null> {
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function isJsonResponse(res: Response) {
  return (res.headers.get('Content-Type') || '').toLowerCase().includes('application/json');
}

function parseRetryAfterSeconds(value: unknown) {
  if (value === null || value === undefined || value === '') return undefined;
  const numericValue = Number(value);
  if (Number.isFinite(numericValue) && numericValue >= 0) return Math.ceil(numericValue);

  if (typeof value === 'string') {
    const retryAt = Date.parse(value);
    if (Number.isFinite(retryAt)) return Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
  }

  return undefined;
}

function parseRateLimitHeaders(headers: Headers) {
  return {
    rateLimitLimit: parseHeaderNumber(headers.get('RateLimit-Limit') ?? headers.get('X-RateLimit-Limit')),
    rateLimitRemaining: parseHeaderNumber(headers.get('RateLimit-Remaining') ?? headers.get('X-RateLimit-Remaining')),
    rateLimitResetSeconds: parseRetryAfterSeconds(headers.get('RateLimit-Reset') ?? headers.get('X-RateLimit-Reset')),
  };
}

function parseHeaderNumber(value: unknown) {
  if (value === null || value === undefined || value === '') return undefined;
  const numericValue = Number(value);
  if (Number.isFinite(numericValue) && numericValue >= 0) return numericValue;
  return undefined;
}

function isEdgeReadiness(value: unknown): value is EdgeReadiness {
  return Boolean(
    value &&
      typeof value === 'object' &&
      'ready' in value &&
      typeof value.ready === 'boolean' &&
      'checks' in value &&
      value.checks &&
      typeof value.checks === 'object',
  );
}

function getApiErrorMessage(status: number, statusText: string, detail: unknown) {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'error' in detail && typeof detail.error === 'string') {
    return detail.error;
  }
  return `HTTP ${status}: ${statusText}`;
}

export const api = new ApiClient();
export default api;
