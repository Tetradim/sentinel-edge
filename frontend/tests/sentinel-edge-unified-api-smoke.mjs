/* global console, fetch, process, URL */

const appUrl = process.env.SENTINEL_EDGE_UI_URL || 'http://127.0.0.1:5173/';
const backendUrl =
  process.env.SENTINEL_EDGE_BACKEND_URL ||
  process.env.VITE_BACKEND_URL ||
  process.env.REACT_APP_BACKEND_URL ||
  'http://127.0.0.1:8000/';
const symbols = (process.env.SENTINEL_EDGE_SMOKE_SYMBOLS || process.env.SENTINEL_EDGE_SMOKE_SYMBOL || 'SPY,QQQ,NVDA,TSLA')
  .split(',')
  .map((item) => item.trim().toUpperCase())
  .filter(Boolean);
const primarySymbol = symbols[0] ?? 'SPY';

const readOnlyEndpoints = [
  { label: 'health', path: '/api/health' },
  { label: 'liveness', path: '/api/live' },
  { label: 'readiness', path: '/api/ready', okStatuses: [200, 503] },
  { label: 'provider health', path: '/api/providers/health' },
  { label: 'market-data providers', path: '/api/market-data/providers' },
  { label: 'Pulse status', path: '/api/pulse/status' },
  { label: 'Pulse handoff schema', path: '/api/pulse/handoff/schema' },
  { label: 'Pulse queue', path: '/api/pulse/queue' },
  { label: 'Pulse account', path: '/api/pulse/account' },
  { label: 'Pulse positions', path: '/api/pulse/positions' },
  { label: 'stats', path: '/api/stats' },
  { label: 'tickers', path: '/api/tickers' },
  { label: 'decisions', path: '/api/decisions' },
  { label: 'correlation', path: '/api/correlation' },
  { label: 'automation', path: '/api/automation' },
  { label: 'kill switch status', path: '/api/emergency/kill-switch' },
  { label: 'markets', path: '/api/markets' },
  { label: 'rate limits', path: '/api/rate-limit/status' },
  { label: 'scanner catalog', path: '/api/scanner-workbench/catalog' },
  { label: 'frontend RUM status', path: '/api/frontend/rum/status' },
  { label: 'dry-run status', path: '/api/dry-run/status', okStatuses: [200, 404], optional: true },
  { label: 'simulation-lab status', path: '/api/simulation-lab/status' },
  { label: 'notifications status', path: '/api/notifications/status' },
];
const symbolEndpoints = [
  { label: 'ORB levels', path: (symbol) => `/api/orb/${encodeURIComponent(symbol)}`, okStatuses: [200, 404], optional: true },
  { label: 'chart workspace', path: (symbol) => `/api/chart-workspace/${encodeURIComponent(symbol)}?limit=180` },
  { label: 'market-map context', path: (symbol) => `/api/market-map/context/${encodeURIComponent(symbol)}` },
];

const requiredOpenApiRoutes = [
  ['GET', '/api/health'],
  ['GET', '/api/live'],
  ['GET', '/api/ready'],
  ['GET', '/api/providers/health'],
  ['GET', '/api/market-data/providers'],
  ['GET', '/api/pulse/status'],
  ['GET', '/api/pulse/account'],
  ['GET', '/api/pulse/positions'],
  ['GET', '/api/pulse/queue'],
  ['GET', '/api/pulse/handoff/schema'],
  ['POST', '/api/frontend/rum'],
  ['GET', '/api/frontend/rum/status'],
  ['GET', '/api/rate-limit/status'],
  ['GET', '/api/stats'],
  ['GET', '/api/tickers'],
  ['POST', '/api/tickers/{symbol}'],
  ['DELETE', '/api/tickers/{symbol}'],
  ['PUT', '/api/tickers/{symbol}/config'],
  ['GET', '/api/tickers/{symbol}/config'],
  ['GET', '/api/orb/{symbol}'],
  ['GET', '/api/chart-workspace/{symbol}'],
  ['GET', '/api/market-map/proof-markers/{symbol}'],
  ['GET', '/api/market-map/context/{symbol}'],
  ['GET', '/api/scanner-workbench/catalog'],
  ['POST', '/api/scanner-workbench/watch-intent/validate'],
  ['GET', '/api/markets'],
  ['POST', '/api/backtest'],
  ['POST', '/api/backtest/optimize'],
  ['GET', '/api/simulation-lab/status'],
  ['GET', '/api/notifications/status'],
  ['POST', '/api/config/validate'],
  ['POST', '/api/simulation-lab/orb/backtest'],
  ['POST', '/api/simulation-lab/buying-power/allocation'],
  ['POST', '/api/simulation-lab/stop-trailing-dca/compare'],
  ['POST', '/api/support-resistance/evaluate'],
  ['POST', '/api/control/pause'],
  ['POST', '/api/control/resume'],
  ['POST', '/api/emergency/kill-switch'],
  ['GET', '/api/emergency/kill-switch'],
  ['GET', '/api/automation'],
  ['PUT', '/api/automation'],
  ['PUT', '/api/automation/tickers/{symbol}'],
  ['GET', '/api/correlation'],
  ['GET', '/api/decisions'],
  ['POST', '/api/pulse/trailing-stop/{symbol}'],
  ['POST', '/api/pulse/emergency-exit/{symbol}'],
];
const optionalOpenApiRoutes = [
  ['GET', '/api/dry-run/status'],
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function urlFor(path) {
  return new URL(path, appUrl).toString();
}

function backendUrlFor(path) {
  return new URL(path, backendUrl).toString();
}

async function fetchJson(path, options = {}, okStatuses = [200]) {
  const response = await fetch(urlFor(path), options);
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    const body = await response.text();
    throw new Error(`${path} returned non-JSON ${response.status} ${contentType}: ${body.slice(0, 120)}`);
  }
  const payload = await response.json();
  assert(okStatuses.includes(response.status), `${path} returned ${response.status}: ${JSON.stringify(payload).slice(0, 240)}`);
  return { status: response.status, payload };
}

async function diagnoseBackendOpenApi(optionalEndpoints) {
  const diagnostics = {
    backendUrl,
    checked: true,
    requiredRouteCount: requiredOpenApiRoutes.length,
    missingRequiredRoutes: [],
    registeredRequiredRoutes: [],
    missingOptionalPaths: optionalEndpoints.map((endpoint) => endpoint.path),
    registeredOptionalPaths: [],
    unregisteredOptionalPaths: [],
    dryRunStatusRegistered: null,
    openApiStatus: null,
    error: null,
  };

  try {
    const response = await fetch(backendUrlFor('/openapi.json'));
    diagnostics.openApiStatus = response.status;
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('application/json')) {
      const body = await response.text();
      diagnostics.error = `OpenAPI returned non-JSON ${response.status} ${contentType}: ${body.slice(0, 120)}`;
      return diagnostics;
    }

    const payload = await response.json();
    const paths = payload?.paths && typeof payload.paths === 'object' ? payload.paths : {};
    const pathSet = new Set(Object.keys(paths));
    diagnostics.registeredRequiredRoutes = requiredOpenApiRoutes
      .filter(([method, path]) => pathSet.has(path) && Boolean(paths[path]?.[method.toLowerCase()]))
      .map(([method, path]) => `${method} ${path}`);
    diagnostics.missingRequiredRoutes = requiredOpenApiRoutes
      .filter(([method, path]) => !pathSet.has(path) || !paths[path]?.[method.toLowerCase()])
      .map(([method, path]) => `${method} ${path}`);
    diagnostics.registeredOptionalPaths = optionalEndpoints
      .map((endpoint) => endpoint.path)
      .filter((path) => pathSet.has(path));
    diagnostics.unregisteredOptionalPaths = optionalOpenApiRoutes
      .filter(([method, path]) => !pathSet.has(path) || !paths[path]?.[method.toLowerCase()])
      .map(([method, path]) => `${method} ${path}`);
    diagnostics.dryRunStatusRegistered = pathSet.has('/api/dry-run/status');
    assert(
      diagnostics.missingRequiredRoutes.length === 0,
      `Live backend OpenAPI is missing required unified UI routes: ${diagnostics.missingRequiredRoutes.join(', ')}`,
    );
  } catch (error) {
    diagnostics.error = error instanceof Error ? error.message : String(error);
    throw error;
  }
  return diagnostics;
}

const endpointResults = [];
for (const endpoint of readOnlyEndpoints) {
  const result = await fetchJson(endpoint.path, {}, endpoint.okStatuses ?? [200]);
  endpointResults.push({
    label: endpoint.label,
    path: endpoint.path,
    status: result.status,
    optional: Boolean(endpoint.optional),
  });
}
const optionalMissingEndpoints = endpointResults.filter((result) => result.optional && result.status !== 200);
const backendOpenApiDiagnostics = await diagnoseBackendOpenApi(optionalMissingEndpoints);

const symbolResults = [];
const safeValidationResults = [];

const scannerValidation = await fetchJson('/api/scanner-workbench/watch-intent/validate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    scanners: [],
    tickers: [],
    strategies: [],
    indicators: [],
  }),
});
assert(typeof scannerValidation.payload?.valid === 'boolean', 'scanner watch-intent validation did not return a valid boolean');
safeValidationResults.push({
  label: 'scanner watch-intent validation',
  path: '/api/scanner-workbench/watch-intent/validate',
  status: scannerValidation.status,
  valid: scannerValidation.payload.valid,
  invalidCount: scannerValidation.payload.invalid_count ?? null,
});

for (const symbol of symbols) {
  for (const endpoint of symbolEndpoints) {
    const result = await fetchJson(endpoint.path(symbol), {}, endpoint.okStatuses ?? [200]);
    endpointResults.push({
      label: `${symbol} ${endpoint.label}`,
      path: endpoint.path(symbol),
      status: result.status,
      optional: Boolean(endpoint.optional),
    });
  }

  const chart = (await fetchJson(`/api/chart-workspace/${encodeURIComponent(symbol)}?limit=180`)).payload;
  const bars = Array.isArray(chart?.bars) ? chart.bars : [];
  assert(bars.length > 20, `chart workspace returned ${bars.length} bars for ${symbol}`);
  const currentPrice = Number(chart?.current_price ?? chart?.last_price ?? bars.at(-1)?.close);
  assert(Number.isFinite(currentPrice) && currentPrice > 0, `chart workspace did not expose a usable current price for ${symbol}`);

  const supportResistance = await fetchJson('/api/support-resistance/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      symbol,
      bars,
      current_price: currentPrice,
      settings: {
        opening_range_minutes: 30,
        swing_window: 2,
      },
      emit_event: false,
    }),
  });
  const levels = supportResistance.payload?.levels?.items;
  assert(Array.isArray(levels) && levels.length > 0, `${symbol} support/resistance evaluation did not return levels.items`);
  assert(levels.some((level) => level.role === 'support'), `${symbol} support/resistance evaluation returned no support levels`);
  assert(levels.some((level) => level.role === 'resistance'), `${symbol} support/resistance evaluation returned no resistance levels`);
  symbolResults.push({
    symbol,
    currentPrice,
    levelCount: levels.length,
    supports: levels.filter((level) => level.role === 'support').length,
    resistances: levels.filter((level) => level.role === 'resistance').length,
  });
}

console.log(JSON.stringify({
  ok: true,
  appUrl,
  backendUrl,
  primarySymbol,
  symbols,
  readOnlyEndpointCount: endpointResults.length,
  endpointResults,
  optionalMissingEndpoints,
  backendOpenApiDiagnostics,
  safeValidationResults,
  symbolResults,
}, null, 2));
