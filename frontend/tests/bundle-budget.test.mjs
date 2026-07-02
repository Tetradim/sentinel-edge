import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(testDir, '..');
const repoDir = path.resolve(frontendDir, '..');
const assetsDir = path.resolve(testDir, '../dist/assets');

function readSource(relativePath) {
  return readFileSync(path.join(frontendDir, relativePath), 'utf8');
}

function readRepoSource(relativePath) {
  return readFileSync(path.join(repoDir, relativePath), 'utf8');
}

function listJsAssets() {
  return readdirSync(assetsDir).filter((name) => name.endsWith('.js'));
}

function listRelativeFiles(rootDir, currentDir = rootDir) {
  return readdirSync(currentDir, { withFileTypes: true }).flatMap((entry) => {
    const absolutePath = path.join(currentDir, entry.name);
    if (entry.isDirectory()) return listRelativeFiles(rootDir, absolutePath);
    return path.relative(rootDir, absolutePath).replaceAll(path.sep, '/');
  });
}

function findBuiltAsset(prefix) {
  return listJsAssets().find((name) => name.startsWith(prefix));
}

function readBuiltAsset(assetName) {
  return readFileSync(path.join(assetsDir, assetName), 'utf8');
}

function extractStaticJsImports(assetName) {
  const source = readBuiltAsset(assetName);
  const imports = new Set();
  const sideEffectImportPattern = /(?:^|;)\s*import\s*["']([^"']+\.js)["']/g;
  const fromImportPattern = /(?:^|;)\s*import(?!\s*\()[^;]*?from\s*["']([^"']+\.js)["']/g;

  for (const pattern of [sideEffectImportPattern, fromImportPattern]) {
    let match = pattern.exec(source);
    while (match) {
      imports.add(path.basename(match[1]));
      match = pattern.exec(source);
    }
  }

  return [...imports];
}

function findStaticImportPath(startAsset, targetPredicate) {
  const queue = [[startAsset]];
  const visited = new Set();

  while (queue.length > 0) {
    const pathToAsset = queue.shift();
    const currentAsset = pathToAsset.at(-1);
    if (!currentAsset || visited.has(currentAsset)) continue;
    visited.add(currentAsset);

    if (targetPredicate(currentAsset)) return pathToAsset;

    extractStaticJsImports(currentAsset).forEach((importedAsset) => {
      if (!visited.has(importedAsset) && existsSync(path.join(assetsDir, importedAsset))) {
        queue.push([...pathToAsset, importedAsset]);
      }
    });
  }

  return null;
}

test('app entry mounts the unified shell without legacy console navigation', () => {
  const appSource = readSource('src/App.tsx');
  const shellSource = readSource('src/components/sentinel-edge/SentinelEdgeUnifiedShell.tsx');
  const shellStyles = readSource('src/components/sentinel-edge/SentinelEdgeUnifiedShell.css');

  assert.match(appSource, /SentinelEdgeUnifiedShell/);
  assert.doesNotMatch(appSource, /AssetCommandConsole|Legacy Console/);
  assert.match(shellSource, /Risk Control Brain/);
  assert.doesNotMatch(shellSource, /Legacy Console|Legacy Asset Command Console/);
  assert.match(shellStyles, /@media \(max-width:980px\)/);
  assert.match(shellStyles, /\.se-readiness-details\{grid-template-columns:repeat\(auto-fit,minmax\(220px,1fr\)\)\}/);
});

test('unified shell keeps required backend control surfaces wired', () => {
  const shellSource = readSource('src/components/sentinel-edge/SentinelEdgeUnifiedShell.tsx');
  const requiredCalls = [
    'api.getHealth()',
    'api.getLiveness()',
    'api.getReadiness()',
    'api.getProviderHealth()',
    'api.getMarketDataProviders()',
    'api.getPulseStatus()',
    'api.getPulseHandoffSchema()',
    'api.getPulseQueue()',
    'api.getPulseAccount()',
    'api.getPulsePositions()',
    'api.getStats()',
    'api.getTickers()',
    'api.getDecisions()',
    'api.getCorrelation()',
    'api.getAutomationStatus()',
    'api.getKillSwitchStatus()',
    'api.getOrbLevels(symbol)',
    'api.getChartWorkspace(symbol, { limit: 180 })',
    'api.getMarketMapContext(symbol)',
    'api.getMarkets()',
    'api.getRateLimitStatus()',
    'api.evaluateSupportResistance(supportResistancePayload)',
    'api.updateAutomationSettings({ mode })',
    'api.pauseScheduler()',
    'api.resumeScheduler()',
    'api.updateTickerAutomation(symbol, true)',
    'api.updateTickerAutomation(symbol, false)',
    'api.enablePulseTrailingStop(symbol, pct)',
    "api.sendPulseEmergencyExit(symbol, 'Sentinel Edge operator control')",
  ];

  requiredCalls.forEach((call) => {
    assert.ok(shellSource.includes(call), `expected unified shell to include ${call}`);
  });

  [
    'current_price',
    'emit_event: false',
    'S/R API',
    'Market data providers',
    'Market Data',
    'const providerRows = collectionRows(providers',
    'collectionRows(snapshot.providers.data',
    'collectionRows(snapshot.marketDataProviders.data',
    'provider.healthy === false',
    'Needs key',
    'const queueSize = Number(queuePayload?.queue_size',
    'Default TTL',
    'Emergency TTL',
    'pulseHandoffSchema',
    'Pulse handoff schema',
    'Handoff Contract',
    'Contract version',
    'Recommended endpoint',
    'Idempotency header',
    'function isKillSwitchActive',
    'kill_switch_active',
  ].forEach((token) => {
    assert.ok(shellSource.includes(token), `expected unified shell to include ${token}`);
  });
});

test('key levels monitor uses live chart bars, current price, and S/R API priority', () => {
  const shellSource = readSource('src/components/sentinel-edge/SentinelEdgeUnifiedShell.tsx');

  [
    'const bars = extractChartBars(chart);',
    'const currentPrice = extractLastPrice(snapshot, symbol);',
    'current_price: currentPrice',
    'emit_event: false',
    '? await settle(api.evaluateSupportResistance(supportResistancePayload), snapshot.supportResistance)',
    ': createLoad(snapshot.supportResistance.data, \'Chart bars unavailable for S/R evaluation\'',
    'function payloadMatchesSymbol(payload: any, symbol: string)',
    'if (!payloadMatchesSymbol(chart, symbol)) return null;',
    'if (!payloadMatchesSymbol(supportResistance, symbol)) return [];',
    'const refreshSequenceRef = useRef(0);',
    'if (refreshSequenceRef.current !== refreshSequence) return;',
    '<Panel title="Key Levels Monitor" meta={`${derived.levelSource} support / resistance`}',
    '<LevelsTable rows={derived.levelRows}',
    'const orderedSymbols = Array.from(new Set([selected, ...symbols])).slice(0, 9);',
  ].forEach((token) => {
    assert.ok(shellSource.includes(token), `expected S/R monitor contract token ${token}`);
  });

  assert.match(
    shellSource,
    /const possible = \[[\s\S]*map\?\.price[\s\S]*map\?\.current_price[\s\S]*chart\?\.current_price[\s\S]*stats\?\.prices\?\.\[symbol\][\s\S]*\];/,
    'expected current price extraction to prefer live market-map/chart/stats sources',
  );
  assert.match(
    shellSource,
    /\{ source: 'S\/R API', levels: supportResistanceLevels\(snapshot, symbol, price\) \},[\s\S]*\{ source: 'chart workspace', levels: chartWorkspaceLevels\(snapshot, symbol, price\) \},[\s\S]*\{ source: 'ORB', levels: orbLevels\(snapshot, symbol, price\) \},[\s\S]*\{ source: 'OHLCV fallback', levels: barDerivedLevels\(snapshot, symbol, price\) \}/,
    'expected S/R API levels to be evaluated before chart, ORB, and OHLCV fallbacks',
  );
  assert.match(
    shellSource,
    /levelSets\.find\(\(set\) => nearestLevel\(set\.levels, price, 'support'\) && nearestLevel\(set\.levels, price, 'resistance'\)\)/,
    'expected key levels to require both support and resistance from the selected source',
  );
  assert.match(
    shellSource,
    /role === 'support'[\s\S]*filtered\.filter\(\(level\) => level\.price <= price\)\.sort\(\(a, b\) => b\.price - a\.price\)/,
    'expected nearest support to prefer the highest support at or below current price',
  );
  assert.match(
    shellSource,
    /filtered\.filter\(\(level\) => level\.price >= price\)\.sort\(\(a, b\) => a\.price - b\.price\)/,
    'expected nearest resistance to prefer the lowest resistance at or above current price',
  );
  assert.match(
    shellSource,
    /const last = extractLastPrice\(snapshot, selected\);[\s\S]*const sr = extractSupportResistance\(snapshot, selected, last\);[\s\S]*const support = symbol === selected \? sr\.support[\s\S]*const resistance = symbol === selected \? sr\.resistance/,
    'expected selected Key Levels row to use support/resistance derived from the selected current price',
  );
});

test('api client encodes symbol-bearing control routes', () => {
  const apiSource = readSource('src/lib/api.ts');

  [
    '/api/tickers/${encodeURIComponent(symbol)}',
    '/api/tickers/${encodeURIComponent(symbol)}/config',
    '/api/orb/${encodeURIComponent(symbol)}',
    '/api/chart-workspace/${encodeURIComponent(symbol)}',
    '/api/market-map/context/${encodeURIComponent(symbol)}',
    '/api/automation/tickers/${encodeURIComponent(symbol)}',
    '/api/pulse/trailing-stop/${encodeURIComponent(symbol)}',
    '/api/pulse/emergency-exit/${encodeURIComponent(symbol)}',
  ].forEach((token) => {
    assert.ok(apiSource.includes(token), `expected API client route token ${token}`);
  });
});

test('new shell API client routes have matching FastAPI declarations', () => {
  const apiSource = readSource('src/lib/api.ts');
  const serverSource = readRepoSource('backend/server.py');
  const routePairs = [
    ["fetchJSON('/api/health')", '@api_router.get("/health")'],
    ["fetchJSON<EdgeLiveness>('/api/live')", '@api_router.get("/live")'],
    ["fetchJSON<EdgeReadiness>('/api/ready')", '@api_router.get("/ready")'],
    ["fetchJSON('/api/providers/health')", '@api_router.get("/providers/health")'],
    ["fetchJSON('/api/market-data/providers')", '@api_router.get("/market-data/providers")'],
    ["fetchJSON('/api/pulse/status')", '@api_router.get("/pulse/status")'],
    ["fetchJSON('/api/pulse/handoff/schema')", '@api_router.get("/pulse/handoff/schema")'],
    ["fetchJSON('/api/pulse/account')", '@api_router.get("/pulse/account")'],
    ["fetchJSON('/api/pulse/positions')", '@api_router.get("/pulse/positions")'],
    ["fetchJSON('/api/pulse/queue')", '@api_router.get("/pulse/queue")'],
    ["fetchJSON('/api/stats')", '@api_router.get("/stats")'],
    ["fetchJSON('/api/tickers')", '@api_router.get("/tickers")'],
    ['fetchJSON(`/api/tickers/${encodeURIComponent(symbol)}`', '@api_router.post("/tickers/{symbol}"'],
    ['fetchJSON(`/api/tickers/${encodeURIComponent(symbol)}`', '@api_router.delete("/tickers/{symbol}")'],
    ['fetchJSON(`/api/tickers/${encodeURIComponent(symbol)}/config`', '@api_router.get("/tickers/{symbol}/config")'],
    ['fetchJSON(`/api/tickers/${encodeURIComponent(symbol)}/config`,', '@api_router.put("/tickers/{symbol}/config")'],
    ['fetchJSON(`/api/orb/${encodeURIComponent(symbol)}`', '@api_router.get("/orb/{symbol}")'],
    ['fetchJSON<ChartWorkspaceSnapshot>(`/api/chart-workspace/${encodeURIComponent(symbol)}', '@api_router.get("/chart-workspace/{symbol}")'],
    ['fetchJSON<MarketMapProofMarkersPayload>(', '@api_router.get("/market-map/proof-markers/{symbol}")'],
    ['fetchJSON<MarketMapContext>(`/api/market-map/context/${encodeURIComponent(symbol)}`', '@api_router.get("/market-map/context/{symbol}")'],
    ["fetchJSON('/api/markets')", '@api_router.get("/markets")'],
    ["fetchJSON('/api/backtest',", '@api_router.post("/backtest")'],
    ["fetchJSON('/api/backtest/optimize',", '@api_router.post("/backtest/optimize")'],
    ["fetchJSON<RateLimitStatus>('/api/rate-limit/status')", '@api_router.get("/rate-limit/status")'],
    ['return fetchJSON(FRONTEND_RUM_PATH,', '@api_router.post("/frontend/rum")'],
    ["fetchJSON('/api/frontend/rum/status')", '@api_router.get("/frontend/rum/status")'],
    ["fetchJSON<ScannerWorkbenchCatalog>('/api/scanner-workbench/catalog')", '@api_router.get("/scanner-workbench/catalog")'],
    ["fetchJSON<ScannerWorkbenchWatchIntentValidation>('/api/scanner-workbench/watch-intent/validate'", '@api_router.post("/scanner-workbench/watch-intent/validate")'],
    ["fetchJSON('/api/dry-run/status')", '@api_router.get("/dry-run/status")'],
    ["fetchJSON('/api/simulation-lab/status')", '@api_router.get("/simulation-lab/status")'],
    ["fetchJSON('/api/simulation-lab/orb/backtest',", '@api_router.post("/simulation-lab/orb/backtest")'],
    ["fetchJSON('/api/simulation-lab/buying-power/allocation',", '@api_router.post("/simulation-lab/buying-power/allocation")'],
    ["fetchJSON('/api/simulation-lab/stop-trailing-dca/compare',", '@api_router.post("/simulation-lab/stop-trailing-dca/compare")'],
    ["fetchJSON('/api/notifications/status')", '@api_router.get("/notifications/status")'],
    ["fetchJSON('/api/config/validate',", '@api_router.post("/config/validate")'],
    ["fetchJSON('/api/support-resistance/evaluate'", '@api_router.post("/support-resistance/evaluate")'],
    ["fetchJSON('/api/control/pause'", '@api_router.post("/control/pause")'],
    ["fetchJSON('/api/control/resume'", '@api_router.post("/control/resume")'],
    ['fetchJSON(`/api/emergency/kill-switch?state=${state}`', '@api_router.post("/emergency/kill-switch")'],
    ["fetchJSON('/api/emergency/kill-switch')", '@api_router.get("/emergency/kill-switch")'],
    ["fetchJSON('/api/automation')", '@api_router.get("/automation")'],
    ["fetchJSON('/api/automation',", '@api_router.put("/automation")'],
    ['fetchJSON(`/api/automation/tickers/${encodeURIComponent(symbol)}`', '@api_router.put("/automation/tickers/{symbol}")'],
    ["fetchJSON('/api/correlation')", '@api_router.get("/correlation")'],
    ["fetchJSON('/api/decisions')", '@api_router.get("/decisions")'],
    ['fetchJSON(`/api/pulse/trailing-stop/${encodeURIComponent(symbol)}', '@api_router.post("/pulse/trailing-stop/{symbol}")'],
    ['fetchJSON(`/api/pulse/emergency-exit/${encodeURIComponent(symbol)}', '@api_router.post("/pulse/emergency-exit/{symbol}")'],
  ];

  routePairs.forEach(([clientToken, serverToken]) => {
    assert.ok(apiSource.includes(clientToken), `expected API client token ${clientToken}`);
    assert.ok(serverSource.includes(serverToken), `expected FastAPI route declaration ${serverToken}`);
  });
});

test('live UI probe is packaged as a reproducible frontend script', () => {
  const packageSource = readSource('package.json');
  const lockSource = readSource('package-lock.json');
  const probeSource = readSource('tests/sentinel-edge-unified-live-probe.mjs');
  const apiSmokeSource = readSource('tests/sentinel-edge-unified-api-smoke.mjs');

  assert.ok(packageSource.includes('"test:unified-api-smoke": "node tests/sentinel-edge-unified-api-smoke.mjs"'));
  assert.ok(packageSource.includes('"test:unified-ui-live": "node tests/sentinel-edge-unified-live-probe.mjs"'));
  assert.ok(packageSource.includes('"playwright-core"'));
  assert.ok(lockSource.includes('"node_modules/playwright-core"'));
  [
    "import { chromium } from 'playwright-core';",
    "process.env.SENTINEL_EDGE_UI_URL || 'http://127.0.0.1:5173/'",
    'interceptedControls',
    '"mode":"paper"',
    '"mode":"recommend_only"',
    'PUT\', \'/api/automation\'',
    '/api/pulse/trailing-stop/SPY',
    '/api/emergency/kill-switch',
    'expandedPopouts',
    "selectOption('QQQ')",
    'qqqFirstRowCells',
    "topActions.locator('input').fill('NVDA')",
    'nvdaInputRowCells',
    'Topbar symbol input did not issue intercepted POST /api/tickers/NVDA',
    '__sentinelCopiedSnapshot',
    'Copy Status Snapshot',
    'safeUiControls',
    'assertKpiDashboard',
    'kpiSnapshot',
    'Bots Monitored KPI was not a count pair',
    'assertBotEcosystem',
    'botEcosystemSnapshot',
    'Bot mesh missing',
    'Bot Directive Matrix missing',
    'expectedProviderHealthRows',
    'Consolidation did not reflect provider-health context',
    'Sentinel Pulse',
    'Auto-Crypto',
    'assertProviderReadinessDetails',
    'providerReadinessSnapshot',
    'Provider / Readiness Details missing',
    'expectedMarketDataRows',
    'expectedReadinessRows',
    'Provider health rendered generic labels',
    'Market Data rendered generic labels',
    'Market Data did not render provider configuration status',
    'assertSystemHealthAndPulseContext',
    'systemHealthPulseSnapshot',
    'System Health missing',
    'Pulse Context missing Positions heading',
    'Pulse Context missing Handoff Contract heading',
    'Pulse Context did not render backend queue_size',
    'Pulse Context did not render default TTL',
    'Pulse Context did not render backend contract_version',
    'Pulse Context did not render backend recommended_endpoint',
    'Pulse Context did not render Idempotency-Key header state',
    'handoffSchema',
    'queueMetadata',
    'assertDecisionFeed',
    'decisionFeedSnapshot',
    'Decision feed row did not include a leading symbol',
    'assertPolicyStack',
    'policyStackSnapshot',
    'Pulse handoff gates',
    'assertCanvasDrawn',
    'canvasStats',
    'assertHeatmapTooltip',
    'heatmapTooltipText',
    'Heatmap tooltip did not include active symbol',
    'assertSupportResistanceFallback',
    'probe forced S/R outage',
    'Fallback warning did not name supportResistance',
    'fallbackProbe',
    'assertKillSwitchStatusRendering',
    'killSwitchStatusProbe',
    'kill_switch_active true did not render KILL SWITCH Pulse Gate',
    'main VEX heatmap',
    'main gamma by strike',
    'main breakout radar',
    'canvas looked blank or only background colored',
    'Manual Refresh did not trigger additional API calls',
    'Local Settings checkbox did not pause live polling',
    'Local Settings heat mode select did not activate VOL',
    'toleratedRateLimitFailures',
    'mobileToleratedRateLimitFailures',
    'isToleratedOrbEmptyResponse',
    'splitConsoleErrors',
    'toleratedOrbEmptyResponses',
    'toleratedOrbConsoleErrors',
    'mobileToleratedOrbEmptyResponses',
    'mobileToleratedOrbConsoleErrors',
    'tolerated empty ORB console entries',
    'tolerated empty ORB routes',
    'Unexpected mobile HTTP failures',
    'Unexpected HTTP failures',
    'Expand VEX Heat Map',
    'Expand Risk Exposure Brain',
    'Expand Gamma by Strike',
    'Expand Breakout / Breakdown Radar',
    'Expand Key Levels Monitor',
    'Mobile layout has horizontal overflow',
    'moduleDeepChecks',
    'Validate watch intent',
    'Scanner Workbench validate did not call watch-intent validation endpoint',
    'Operator notification paths',
    'System Settings did not surface operator notification paths',
    'secret_values',
    'rumStatusVisible',
  ].forEach((token) => {
    assert.ok(probeSource.includes(token), `expected live probe token ${token}`);
  });

  [
    '/api/support-resistance/evaluate',
    '/api/chart-workspace/${encodeURIComponent(symbol)}?limit=180',
    "okStatuses: [200, 404]",
    '/api/pulse/handoff/schema',
    '/api/dry-run/status',
    '/api/simulation-lab/status',
    '/api/notifications/status',
    '/api/scanner-workbench/watch-intent/validate',
    'emit_event: false',
    'readOnlyEndpoints',
    'safeValidationResults',
    'optionalMissingEndpoints',
    'backendOpenApiDiagnostics',
    'requiredOpenApiRoutes',
    'missingRequiredRoutes',
    'registeredRequiredRoutes',
    "['POST', '/api/pulse/emergency-exit/{symbol}']",
    'SENTINEL_EDGE_BACKEND_URL',
    'dryRunStatusRegistered',
    'unregisteredOptionalPaths',
    'scanner watch-intent validation',
    'SENTINEL_EDGE_SMOKE_SYMBOLS',
    'symbolResults',
    'support/resistance evaluation returned no support levels',
    'support/resistance evaluation returned no resistance levels',
  ].forEach((token) => {
    assert.ok(apiSmokeSource.includes(token), `expected API smoke token ${token}`);
  });
});

test('unified shell exposes recovered operator controls and confirmations', () => {
  const shellSource = readSource('src/components/sentinel-edge/SentinelEdgeUnifiedShell.tsx');
  const requiredLabels = [
    'Arm Trigger',
    'Risk Sweep',
    'Convert Alert',
    'Mute Watch',
    'Diagnostics',
    'Ack Alerts',
    'Lock Buys',
    'Advise Stops',
    'Reduce Size',
    'Inject Break',
    'Allow Guarded Breakout',
    'Block Buy Below Support',
    'Reduce Size On Heat Spike',
    'Resimulate Greeks',
    'Export Levels',
    'Refresh Heatmap',
    'Save Heatmap',
    'All Activity',
    'Backend/System',
    'Trailing Stop',
    'Emergency Exit',
    'Kill Switch',
  ];

  requiredLabels.forEach((label) => {
    assert.ok(shellSource.includes(label), `expected unified shell to include ${label}`);
  });

  [
    'Enable global kill switch?',
    'Send Pulse emergency-exit bridge command',
    'Remove SPY from the active Sentinel Edge ticker list?',
    'Trailing stop percent',
  ].forEach((prompt) => {
    assert.ok(shellSource.includes(prompt) || shellSource.includes(prompt.replace('SPY', '${symbol}')), `expected confirmation/prompt ${prompt}`);
  });
});

test('integration audit lists approval-only legacy removal candidates', () => {
  const auditSource = readSource('docs/unified-ui-integration-audit.md');
  [
    'Legacy Coverage Matrix',
    'ActivityLog.tsx',
    'CommandModePanel.tsx',
    'DirectivesPanel.tsx',
    'EdgeCoreHeatmap.tsx',
    'GreeksPanel.tsx',
    'MonitorPanel.tsx',
    'OperationsPanel.tsx',
    'ProtectionPanel.tsx',
    'SettingsPanel.tsx',
    'TickerPicker.tsx',
    'UnifiedChartingPanel.tsx',
    'VolumeHeatmap.tsx',
    'UiIterationLab.tsx',
    'useAssetCommandNavigation.ts',
    'useAssetCommandState.ts',
    'useRuntimeStatus.ts',
    'frontend/src/components/asset-command/**',
    'legacy components, hooks, seed data, types, and CSS',
    'frontend/tests/asset-command-monitor-layout.test.mjs',
    'stubbed operator-control requests',
    'Pulse trailing stop',
    'Pause/Resume feed',
    'Apply settings',
    'Standalone Mode',
    'Bridge mode',
    'topbar Live/Pause',
    'Local Settings polling/heat-mode controls',
    'Discord Trading Bot',
    'Sentinel Chain',
    'Sentinel Core',
    'Sentinel Echo',
    'configurable hex core heatmap',
  ].forEach((token) => {
    assert.ok(auditSource.includes(token), `expected integration audit to include ${token}`);
  });
});

test('legacy asset-command source files stay preserved or explicitly documented', () => {
  const auditSource = readSource('docs/unified-ui-integration-audit.md');
  const legacyRoot = path.join(frontendDir, 'src/components/asset-command');
  const legacyFiles = listRelativeFiles(legacyRoot).sort();
  const expectedLegacyFiles = [
    'AssetCommandConsole.activity.css',
    'AssetCommandConsole.core.css',
    'AssetCommandConsole.css',
    'AssetCommandConsole.greeks.css',
    'AssetCommandConsole.iterations.css',
    'AssetCommandConsole.panels.css',
    'AssetCommandConsole.picker.css',
    'AssetCommandConsole.tsx',
    'components/ActivityLog.tsx',
    'components/CommandModePanel.tsx',
    'components/DirectivesPanel.tsx',
    'components/EdgeCoreHeatmap.tsx',
    'components/GreeksPanel.tsx',
    'components/LazyPanelFallback.tsx',
    'components/ModeTabs.tsx',
    'components/MonitorPanel.tsx',
    'components/OperationsPanel.tsx',
    'components/ProtectionPanel.tsx',
    'components/SettingsPanel.tsx',
    'components/TickerPicker.tsx',
    'components/UiIterationLab.tsx',
    'components/UnifiedChartingPanel.tsx',
    'components/VolumeHeatmap.tsx',
    'components/shared.tsx',
    'data.ts',
    'hooks/useAssetCommandNavigation.ts',
    'hooks/useAssetCommandState.ts',
    'hooks/useRuntimeStatus.ts',
    'types.ts',
  ];

  assert.deepEqual(legacyFiles, expectedLegacyFiles);
  assert.match(auditSource, /Removal Candidates Requiring Approval/);
  assert.match(auditSource, /src\/components\/asset-command\/\*\*/);

  const explicitlyDocumented = new Set([
    'AssetCommandConsole.tsx',
    'ActivityLog.tsx',
    'CommandModePanel.tsx',
    'DirectivesPanel.tsx',
    'EdgeCoreHeatmap.tsx',
    'GreeksPanel.tsx',
    'LazyPanelFallback.tsx',
    'ModeTabs.tsx',
    'MonitorPanel.tsx',
    'OperationsPanel.tsx',
    'ProtectionPanel.tsx',
    'SettingsPanel.tsx',
    'TickerPicker.tsx',
    'UiIterationLab.tsx',
    'UnifiedChartingPanel.tsx',
    'VolumeHeatmap.tsx',
    'shared.tsx',
    'useAssetCommandNavigation.ts',
    'useAssetCommandState.ts',
    'useRuntimeStatus.ts',
    'data.ts',
    'types.ts',
  ]);

  const undocumentedFiles = legacyFiles.filter((relativeFile) => {
    const fileName = path.basename(relativeFile);
    if (explicitlyDocumented.has(fileName) && auditSource.includes(fileName)) return false;
    if (relativeFile.endsWith('.css') && auditSource.includes('legacy CSS files')) return false;
    return true;
  });

  assert.deepEqual(undocumentedFiles, []);
});

test('built app entry chunk stays below the Sentinel Edge budget', { skip: !existsSync(assetsDir) }, () => {
  const entry = listJsAssets()
    .filter((name) => name.startsWith('index-'))
    .map((name) => ({ name, size: statSync(path.join(assetsDir, name)).size }))
    .sort((a, b) => b.size - a.size)[0];

  assert.ok(entry, 'expected an index JS asset after npm run build');
  assert.ok(
    entry.size < 900 * 1024,
    `expected app entry below 900 KB, received ${Math.round(entry.size / 1024)} KB in ${entry.name}`,
  );
});

test('recovered operations modules are emitted as lazy chunks', { skip: !existsSync(assetsDir) }, () => {
  const jsAssets = listJsAssets();
  const entryAsset = findBuiltAsset('index-');
  const recoveredModulePrefixes = [
    'TradingOverview-',
    'ScannerWorkbench-',
    'AdvisorHealth-',
    'ExperienceDashboard-',
    'ProtectionDashboard-',
    'PnLTracking-',
    'MarketCoverage-',
    'PortfolioAnalytics-',
    'SettingsDashboard-',
    'tutorials-',
  ];

  assert.ok(entryAsset, `expected index chunk, received ${jsAssets.join(', ')}`);

  recoveredModulePrefixes.forEach((prefix) => {
    const moduleAsset = findBuiltAsset(prefix);
    assert.ok(moduleAsset, `expected recovered operations module chunk ${prefix}, received ${jsAssets.join(', ')}`);

    const startupModulePath = findStaticImportPath(entryAsset, (assetName) => assetName === moduleAsset);
    assert.equal(
      startupModulePath,
      null,
      `expected ${prefix} outside static startup graph, found ${startupModulePath?.join(' -> ')}`,
    );
  });
});

test('asset command console stays out of the unified shell build', { skip: !existsSync(assetsDir) }, () => {
  const jsAssets = listJsAssets();
  const entryAsset = findBuiltAsset('index-');

  assert.ok(entryAsset, `expected index chunk, received ${jsAssets.join(', ')}`);
  assert.ok(
    !readBuiltAsset(entryAsset).includes('AssetCommandConsole'),
    'expected app entry not to reference AssetCommandConsole',
  );
  assert.ok(
    !jsAssets.some((name) => name.startsWith('AssetCommandConsole-')),
    `expected AssetCommandConsole chunk to be absent, received ${jsAssets.join(', ')}`,
  );
});
