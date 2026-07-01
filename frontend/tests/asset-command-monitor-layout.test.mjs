import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const testDir = path.dirname(fileURLToPath(import.meta.url));
const src = (relativePath) => readFileSync(path.resolve(testDir, relativePath), 'utf8');

const unifiedChartingSource = src('../src/components/asset-command/components/UnifiedChartingPanel.tsx');
const consoleSource = src('../src/components/asset-command/AssetCommandConsole.tsx');
const dataSource = src('../src/components/asset-command/data.ts');
const heatmapSource = src('../src/components/asset-command/components/VolumeHeatmap.tsx');
const greeksStyles = src('../src/components/asset-command/AssetCommandConsole.greeks.css');
const directivesSource = src('../src/components/asset-command/components/DirectivesPanel.tsx');
const greeksSource = src('../src/components/asset-command/components/GreeksPanel.tsx');
const lazyPanelFallbackSource = src('../src/components/asset-command/components/LazyPanelFallback.tsx');
const operationsPanelSource = src('../src/components/asset-command/components/OperationsPanel.tsx');
const chartWorkspaceSource = src('../src/components/dashboards/ChartWorkspace.tsx');
const chartWorkspaceTypesSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceTypes.ts');
const chartWorkspaceStorageSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceStorage.ts');
const chartWorkspaceConstantsSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceConstants.ts');
const chartWorkspaceFallbackSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceFallbackData.ts');
const chartWorkspaceTracesSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceTraces.ts');
const chartWorkspaceFormattersSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceFormatters.ts');
const chartWorkspaceMetricSource = src('../src/components/dashboards/chart-workspace/Metric.tsx');
const chartWorkspaceSymbolsSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceSymbols.ts');

function assertLazyBinding(source, name) {
  assert.match(source, new RegExp(`const\\s+${name}\\s*=\\s*lazy\\b`));
}

function assertNoEagerComponentImport(source, name) {
  assert.doesNotMatch(source, new RegExp(`^import\\s+${name}\\s+from\\s+`, 'm'));
  assert.doesNotMatch(source, new RegExp(`^import\\s*\\{[^}]*\\b${name}\\b[^}]*\\}\\s+from\\s+`, 'm'));
}

test('UnifiedChartingPanel owns the consolidated chart-centric workspace structure', () => {
  assert.match(unifiedChartingSource, /edge-unified-chart-grid/);
  assert.match(unifiedChartingSource, /VolumeHeatmap/);
  assert.match(unifiedChartingSource, /Bot P&L calendar/);
  assert.match(unifiedChartingSource, /Key level monitor/);
});

test('Unified charting receives selected asset and command actions from the console shell', () => {
  const chartingPanelBlock = consoleSource.match(/<UnifiedChartingPanel[\s\S]*?\/>/)?.[0];

  assert.ok(chartingPanelBlock, 'Expected AssetCommandConsole to render UnifiedChartingPanel');
  assert.match(chartingPanelBlock, /selected=\{selected\}/);
  assert.match(chartingPanelBlock, /watcher=\{watcher\}/);
  assert.match(chartingPanelBlock, /onCommand=\{runCommand\}/);
  assert.match(chartingPanelBlock, /onAction=\{runMonitorAction\}/);
  assert.match(chartingPanelBlock, /onSelect=\{selectSymbol\}/);
});

test('Mode list consolidates monitor and market-map into charting', () => {
  assert.match(dataSource, /charting/);
  assert.match(dataSource, /greeks/);
  assert.match(dataSource, /directives/);
  assert.match(consoleSource, /mode === 'charting'/);
  assert.doesNotMatch(consoleSource, /mode === 'market-map'/);
  assert.doesNotMatch(consoleSource, /mode === 'monitor'/);
  assert.match(consoleSource, /mode === 'greeks'/);
  assert.match(consoleSource, /mode === 'directives'/);
  assert.match(consoleSource, /'charting', 'greeks', 'directives', 'operations'\]\.includes\(mode\)/);
  assert.match(consoleSource, /edge-command-grid-chart-mode/);
  assert.doesNotMatch(consoleSource, /edge-console-directives-only/);
});

test('Heatmap, greeks, and directives tabs are wired', () => {
  assert.match(heatmapSource, /function VolumeHeatmap/);
  assert.match(consoleSource, /<GreeksPanel/);
  assert.match(consoleSource, /<DirectivesPanel/);
  assert.match(heatmapSource, /onDownload/);
  assert.match(directivesSource, /edge-directives-command/);
  assert.match(directivesSource, /Directive ledger/);
  assert.match(directivesSource, /Bot bridge health/);
  assert.match(directivesSource, /Policy stack/);
  assert.match(directivesSource, /Outcome attribution/);
  assert.match(directivesSource, /botBridgeHealth/);
  assert.match(directivesSource, /directiveLedger/);
  assert.match(directivesSource, /policyStackRules/);
  assert.match(directivesSource, /outcomeAttribution/);
  assert.doesNotMatch(directivesSource, /sentinel-edge-directives-preview\.html/);
  assert.doesNotMatch(directivesSource, /iframe/);
  assert.match(greeksSource, /gamma by strike/);
  assert.match(greeksSource, /setViewMode\('heatmap'\)/);
  assert.match(greeksSource, /setViewMode\('gamma'\)/);
  assert.match(greeksSource, /createPortal/);
  assert.match(greeksSource, /edge-popout-panel-chart/);
  assert.match(greeksSource, /Highest sensitivity/);
});

test('Lazy panel fallback provides a stable shell for split UI modules', () => {
  assert.match(lazyPanelFallbackSource, /export function LazyPanelFallback/);
  assert.match(lazyPanelFallbackSource, /label = 'Loading workspace'/);
  assert.match(lazyPanelFallbackSource, /edge-tab-panel/);
  assert.match(lazyPanelFallbackSource, /edge-tab-head/);
  assert.match(lazyPanelFallbackSource, /<span>Loading<\/span>/);
  assert.match(lazyPanelFallbackSource, /aria-busy="true"/);
  assert.match(lazyPanelFallbackSource, /edge-chip/);
  assert.match(lazyPanelFallbackSource, /streaming module/);
});

test('AssetCommandConsole lazy-loads split workspace panels', () => {
  [
    'UnifiedChartingPanel',
    'DirectivesPanel',
    'GreeksPanel',
    'OperationsPanel',
    'ProtectionPanel',
    'SettingsPanel',
  ].forEach((name) => {
    assertLazyBinding(consoleSource, name);
    assertNoEagerComponentImport(consoleSource, name);
  });

  assert.match(consoleSource, /<Suspense\s+fallback=\{<LazyPanelFallback\s+label="Workspace"\s*\/>\}/);
  assert.match(consoleSource, /mode === 'directives' && <DirectivesPanel/);
});

test('Operations legacy dashboards are lazy-loaded', () => {
  [
    'TradingOverview',
    'ScannerWorkbench',
    'AdvisorHealth',
    'ExperienceDashboard',
    'OperationsProtectionDashboard',
    'PnLTracking',
    'MarketCoverage',
    'PortfolioAnalytics',
    'SettingsDashboard',
    'TutorialsDashboard',
  ].forEach((name) => assertLazyBinding(operationsPanelSource, name));

  [
    'TradingOverview',
    'ScannerWorkbench',
    'AdvisorHealth',
    'ExperienceDashboard',
    'PnLTracking',
    'MarketCoverage',
    'PortfolioAnalytics',
    'SettingsDashboard',
    'TutorialsDashboard',
  ].forEach((name) => assertNoEagerComponentImport(operationsPanelSource, name));
  assertNoEagerComponentImport(operationsPanelSource, 'ProtectionDashboard');

  assert.match(operationsPanelSource, /<Suspense\s+fallback=\{<LazyPanelFallback\s+label="Operations module"\s*\/>\}/);
});

test('VolumeHeatmap canvas sizing cannot grow its own container', () => {
  assert.match(greeksStyles, /\.edge-volume-heatmap-canvas-wrap\s*\{[\s\S]*height:\s*clamp/);
  assert.doesNotMatch(heatmapSource, /canvas\.style\.(width|height)\s*=/);
  assert.match(heatmapSource, /requestAnimationFrame\(animate\)/);
  assert.match(greeksStyles, /\.edge-greeks-rail\.collapsed > :not\(\.edge-greeks-rail-head\)/);
});

test('VolumeHeatmap follows the accepted Sentinel heatmap visual contract', () => {
  assert.match(heatmapSource, /SPY:\s*603\.47/);
  assert.match(heatmapSource, /\[0\.82,\s*235,\s*150,\s*32\]/);
  assert.match(heatmapSource, /yFromGuardFlow/);
  assert.match(heatmapSource, /drawPath\(bars\.map\(\(bar\) => bar\.support\)/);
  assert.match(heatmapSource, /drawPath\(bars\.map\(\(bar\) => bar\.resistance\)/);
  assert.match(heatmapSource, /\{symbol\} GEX \/ VEX Heat Map/);
});

test('Chart workspace keeps a full local preview when APIs are unavailable', () => {
  assert.match(chartWorkspaceFallbackSource, /buildFallbackChartWorkspaceSnapshot/);
  assert.match(chartWorkspaceSource, /LOCAL_PREVIEW_FEED_MESSAGE/);
  assert.match(chartWorkspaceFallbackSource, /buildFallbackMarketMapContext/);
  assert.match(chartWorkspaceFallbackSource, /buildFallbackProofMarkers/);
  assert.match(chartWorkspaceConstantsSource, /SPY:\s*603\.47/);
});

test('Chart workspace data generation and traces live outside the UI container', () => {
  assert.match(chartWorkspaceFallbackSource, /export function buildFallbackChartWorkspaceSnapshot/);
  assert.match(chartWorkspaceTracesSource, /export function buildPriceTraces/);
  assert.doesNotMatch(chartWorkspaceSource, /function calculateRelativeStrengthIndex/);
  assert.doesNotMatch(chartWorkspaceSource, /function buildPriceTraces/);
  assert.doesNotMatch(chartWorkspaceFallbackSource, /chartWorkspaceStorage/);
  assert.match(chartWorkspaceSymbolsSource, /export function normalizeChartWorkspaceSymbol/);
  assert.match(chartWorkspaceFormattersSource, /export function formatMarketMapLevelPrice/);
  assert.match(chartWorkspaceTracesSource, /formatMarketMapLevelPrice/);
  assert.doesNotMatch(chartWorkspaceTracesSource, /function formatMarketMapLevelPrice/);
});

test('Chart workspace types and storage are split from the UI container', () => {
  assert.match(chartWorkspaceTypesSource, /export type ChartWorkspaceLayoutMode/);
  assert.match(chartWorkspaceStorageSource, /export function readChartWorkspaceLayout/);
  assert.match(chartWorkspaceConstantsSource, /DEFAULT_PREFERENCES_STATE|INDICATOR_OPTIONS/);
  assert.doesNotMatch(chartWorkspaceSource, /function readChartWorkspaceLayout/);
  assert.doesNotMatch(chartWorkspaceTypesSource, /^import\s+(?!type\b)/m);
  assert.doesNotMatch(chartWorkspaceTypesSource, /chartWorkspace(Constants|Storage)|\.\.\/ChartWorkspace/);
  assert.doesNotMatch(chartWorkspaceConstantsSource, /chartWorkspaceStorage|\.\.\/ChartWorkspace/);
  assert.doesNotMatch(chartWorkspaceStorageSource, /\.\.\/ChartWorkspace/);
});

test('Chart workspace formatters and metric tile are split from the UI container', () => {
  assert.match(chartWorkspaceFormattersSource, /export function formatMarketMapContextStatus/);
  assert.match(chartWorkspaceFormattersSource, /export function buildSimulationLabResultMetrics/);
  assert.doesNotMatch(chartWorkspaceFormattersSource, /export function formatSimulationLabResultMetric/);
  assert.doesNotMatch(chartWorkspaceFormattersSource, /export function humanizeWorkspaceLabel/);
  assert.match(chartWorkspaceMetricSource, /export function Metric/);
  assert.doesNotMatch(chartWorkspaceSource, /function formatSimulationLabResultMetric/);
  assert.doesNotMatch(chartWorkspaceSource, /function Metric/);
});
