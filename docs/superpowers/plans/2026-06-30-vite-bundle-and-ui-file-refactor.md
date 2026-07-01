# Vite Bundle And UI File Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the initial Vite production chunk and split the largest Sentinel Edge UI files into maintainable, focused modules.

**Architecture:** First move heavy mode panels and legacy dashboards behind React lazy boundaries so the initial app shell only loads what the active screen needs. Then split `ChartWorkspace.tsx` into focused chart-workspace modules without changing behavior. Finally add Vite chunk naming and bundle guard tests so future UI work does not silently reintroduce eager imports.

**Tech Stack:** React 18, TypeScript, Vite 8, Plotly, Recharts, Node test runner, ESLint.

---

## Current Findings

- Production build currently emits one dominant JS chunk: `dist/assets/index-*.js` at about `5,136 KB`.
- `frontend/src/components/dashboards/ChartWorkspace.tsx` is about `2,509` lines and imports Plotly through `PlotlyCharts.tsx`.
- `frontend/src/components/asset-command/components/OperationsPanel.tsx` imports every legacy dashboard eagerly, including tutorials, settings, scanners, protection, portfolio, and charts.
- `frontend/src/components/asset-command/AssetCommandConsole.tsx` imports heavy tab panels eagerly, including Charting, Greeks, Directives, Operations, Protect, and Settings.
- Splitting source files alone will not fix the Vite warning. The bundle warning requires async boundaries and dependency chunking.

## File Structure Target

- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`
  - Owns top-level mode selection.
  - Uses lazy imports for heavy mode panels.

- Modify: `frontend/src/components/asset-command/components/OperationsPanel.tsx`
  - Owns legacy operations tab navigation.
  - Uses lazy imports for each legacy dashboard view.

- Create: `frontend/src/components/asset-command/components/LazyPanelFallback.tsx`
  - Shared loading shell for lazy tabs.

- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceTypes.ts`
  - Chart-workspace-only UI types currently embedded in `ChartWorkspace.tsx`.

- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceConstants.ts`
  - Indicator options, layout presets, storage keys, fallback anchors, button class strings.

- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceFallbackData.ts`
  - `buildFallbackChartWorkspaceSnapshot`, proof marker/context fallback builders, indicator math helpers.

- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceTraces.ts`
  - Plotly trace builders for price, levels, proof markers, oscillators, ORB overlays.

- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceFormatters.ts`
  - Display formatting helpers for ORB state, levels, proof markers, Simulation Lab, indicators.

- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceStorage.ts`
  - Local storage read/write/normalization helpers.

- Create: `frontend/src/components/dashboards/chart-workspace/Metric.tsx`
  - Small reusable metric tile.

- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
  - Keep as the container/orchestrator only: state, effects, event handlers, and layout composition.

- Modify: `frontend/src/components/ui/PlotlyCharts.tsx`
  - Keep the Plotly wrapper, but load it only from lazy chart routes.

- Modify: `frontend/vite.config.ts`
  - Add named manual chunks so vendor, charting, icons, and motion dependencies are separated and build output is readable.

- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`
  - Add guardrails that heavy dashboard imports remain lazy and `ChartWorkspace.tsx` no longer contains fallback-data and storage implementations inline.

---

### Task 1: Add A Shared Lazy Panel Fallback

**Files:**
- Create: `frontend/src/components/asset-command/components/LazyPanelFallback.tsx`
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Create the fallback component**

Add:

```tsx
export function LazyPanelFallback({ label = 'Loading workspace' }: { label?: string }) {
  return (
    <div className="edge-tab-panel" aria-busy="true">
      <div className="edge-tab-head">
        <div>
          <span>Loading</span>
          <h2>{label}</h2>
        </div>
        <div className="edge-chip">streaming module</div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add a source guard**

In `frontend/tests/asset-command-monitor-layout.test.mjs`, add:

```js
const lazyPanelFallbackSource = src('../src/components/asset-command/components/LazyPanelFallback.tsx');

test('Lazy panel fallback provides a stable shell for split UI modules', () => {
  assert.match(lazyPanelFallbackSource, /export function LazyPanelFallback/);
  assert.match(lazyPanelFallbackSource, /aria-busy="true"/);
});
```

- [ ] **Step 3: Verify**

Run:

```powershell
npm run test:layout
```

Expected: all layout tests pass.

---

### Task 2: Lazy-Load Heavy Asset Command Modes

**Files:**
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Replace eager imports with lazy imports**

Change the top of `AssetCommandConsole.tsx` from eager heavy panel imports to:

```tsx
import { Suspense, lazy, useEffect, useState } from 'react';
import { tickers } from './data';
import { ActivityLog } from './components/ActivityLog';
import { CommandModePanel } from './components/CommandModePanel';
import { LazyPanelFallback } from './components/LazyPanelFallback';
import { ModeTabs } from './components/ModeTabs';
import { MonitorPanel } from './components/MonitorPanel';
import { TickerPicker } from './components/TickerPicker';
import { PanelTitle, RuntimeBadges, StatusMetric } from './components/shared';
import { useAssetCommandNavigation } from './hooks/useAssetCommandNavigation';
import { useAssetCommandState } from './hooks/useAssetCommandState';
import { useRuntimeStatus } from './hooks/useRuntimeStatus';
import './AssetCommandConsole.css';

const ChartWorkspace = lazy(() =>
  import('../dashboards/ChartWorkspace').then((module) => ({ default: module.ChartWorkspace })),
);
const DirectivesPanel = lazy(() =>
  import('./components/DirectivesPanel').then((module) => ({ default: module.DirectivesPanel })),
);
const GreeksPanel = lazy(() =>
  import('./components/GreeksPanel').then((module) => ({ default: module.GreeksPanel })),
);
const OperationsPanel = lazy(() =>
  import('./components/OperationsPanel').then((module) => ({ default: module.OperationsPanel })),
);
const ProtectionPanel = lazy(() =>
  import('./components/ProtectionPanel').then((module) => ({ default: module.ProtectionPanel })),
);
const SettingsPanel = lazy(() =>
  import('./components/SettingsPanel').then((module) => ({ default: module.SettingsPanel })),
);
```

- [ ] **Step 2: Wrap lazy panels in Suspense**

Use `LazyPanelFallback` around lazy-rendered mode content:

```tsx
if (directivesOnly) {
  return (
    <main className="edge-console edge-console-directives-only" aria-label="Sentinel Edge directives command center">
      <Suspense fallback={<LazyPanelFallback label="Directives" />}>
        <DirectivesPanel />
      </Suspense>
    </main>
  );
}
```

Inside the normal tab panel, wrap only the lazy modes:

```tsx
<Suspense fallback={<LazyPanelFallback label="Workspace" />}>
  {mode === 'charting' && <ChartWorkspace />}
  {mode === 'market-map' && <ChartWorkspace />}
  {mode === 'greeks' && <GreeksPanel selected={selected} />}
  {mode === 'protect' && (
    <ProtectionPanel mode={protectionMode} onAction={runProtectionAction} onSelect={selectSymbol} selectedSymbol={selected.symbol} />
  )}
  {mode === 'operations' && (
    <OperationsPanel
      activeView={operationsView}
      setActiveView={setOperationsView}
      handleOperationsKeyDown={handleOperationsKeyDown}
    />
  )}
  {mode === 'settings' && (
    <SettingsPanel
      visibleReels={visibleReels}
      setVisibleReels={setVisibleReels}
      selectedMetrics={selectedMetrics}
      toggleMetric={toggleMetric}
      onSave={() => addEvent(selected.symbol, 'Metric reel settings updated', `${visibleReels} reels visible`)}
    />
  )}
</Suspense>
```

Keep `CommandModePanel` and `MonitorPanel` outside the lazy boundary because they are normal app shell workflows.

- [ ] **Step 3: Add eager-import guardrails**

In `frontend/tests/asset-command-monitor-layout.test.mjs`, add assertions:

```js
test('Asset command heavy modes are lazy-loaded', () => {
  assert.match(consoleSource, /lazy\(\(\) =>\s*import\('\.\.\/dashboards\/ChartWorkspace'\)/);
  assert.match(consoleSource, /lazy\(\(\) =>\s*import\('\.\/components\/GreeksPanel'\)/);
  assert.match(consoleSource, /lazy\(\(\) =>\s*import\('\.\/components\/OperationsPanel'\)/);
  assert.doesNotMatch(consoleSource, /import \{ ChartWorkspace \} from '\.\.\/dashboards\/ChartWorkspace'/);
  assert.match(consoleSource, /<Suspense fallback=\{<LazyPanelFallback/);
});
```

- [ ] **Step 4: Verify**

Run:

```powershell
npm run test:layout
npm run lint
npm run build
```

Expected: build emits multiple JS chunks instead of one dominant app chunk.

---

### Task 3: Lazy-Load Legacy Operations Dashboards

**Files:**
- Modify: `frontend/src/components/asset-command/components/OperationsPanel.tsx`
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Replace eager dashboard imports**

Change `OperationsPanel.tsx` imports to:

```tsx
import { Suspense, lazy } from 'react';
import type React from 'react';
import { LazyPanelFallback } from './LazyPanelFallback';
import { operationsViews } from '../data';
import type { OperationsView } from '../types';
import type { TutorialModuleView } from '../../tutorials';

const TradingOverview = lazy(() =>
  import('../../dashboards/TradingOverview').then((module) => ({ default: module.TradingOverview })),
);
const ChartWorkspace = lazy(() =>
  import('../../dashboards/ChartWorkspace').then((module) => ({ default: module.ChartWorkspace })),
);
const ScannerWorkbench = lazy(() =>
  import('../../dashboards/ScannerWorkbench').then((module) => ({ default: module.ScannerWorkbench })),
);
const AdvisorHealth = lazy(() =>
  import('../../dashboards/AdvisorHealth').then((module) => ({ default: module.AdvisorHealth })),
);
const ExperienceDashboard = lazy(() =>
  import('../../dashboards/ExperienceDashboard').then((module) => ({ default: module.ExperienceDashboard })),
);
const OperationsProtectionDashboard = lazy(() =>
  import('../../dashboards/ProtectionDashboard').then((module) => ({ default: module.ProtectionDashboard })),
);
const PnLTracking = lazy(() =>
  import('../../dashboards/PnLTracking').then((module) => ({ default: module.PnLTracking })),
);
const MarketCoverage = lazy(() =>
  import('../../dashboards/MarketCoverage').then((module) => ({ default: module.MarketCoverage })),
);
const PortfolioAnalytics = lazy(() =>
  import('../../dashboards/PortfolioAnalytics').then((module) => ({ default: module.PortfolioAnalytics })),
);
const SettingsDashboard = lazy(() =>
  import('../../dashboards/SettingsDashboard').then((module) => ({ default: module.SettingsDashboard })),
);
const TutorialsDashboard = lazy(() =>
  import('../../tutorials').then((module) => ({ default: module.TutorialsDashboard })),
);
```

- [ ] **Step 2: Wrap operations content**

Inside `.edge-ops-content`, wrap dashboard switches:

```tsx
<Suspense fallback={<LazyPanelFallback label="Operations module" />}>
  {activeView === 'overview' && <TradingOverview />}
  {activeView === 'charts' && <ChartWorkspace />}
  {activeView === 'scanners' && <ScannerWorkbench />}
  {activeView === 'advisor' && <AdvisorHealth />}
  {activeView === 'experience' && <ExperienceDashboard />}
  {activeView === 'protection' && <OperationsProtectionDashboard />}
  {activeView === 'pnl' && <PnLTracking />}
  {activeView === 'markets' && <MarketCoverage />}
  {activeView === 'portfolio' && <PortfolioAnalytics />}
  {activeView === 'settings' && <SettingsDashboard />}
  {activeView === 'tutorials' && <TutorialsDashboard onOpenModule={(view: TutorialModuleView) => setActiveView(view)} />}
</Suspense>
```

- [ ] **Step 3: Add guardrails**

Add:

```js
const operationsPanelSource = src('../src/components/asset-command/components/OperationsPanel.tsx');

test('Operations legacy dashboards are lazy-loaded', () => {
  assert.match(operationsPanelSource, /lazy\(\(\) =>\s*import\('\.\.\/\.\.\/dashboards\/SettingsDashboard'\)/);
  assert.match(operationsPanelSource, /lazy\(\(\) =>\s*import\('\.\.\/\.\.\/tutorials'\)/);
  assert.doesNotMatch(operationsPanelSource, /import \{ SettingsDashboard \} from '\.\.\/\.\.\/dashboards\/SettingsDashboard'/);
  assert.match(operationsPanelSource, /<Suspense fallback=\{<LazyPanelFallback label="Operations module" \/>/);
});
```

- [ ] **Step 4: Verify**

Run:

```powershell
npm run test:layout
npm run lint
npm run build
```

Expected: legacy dashboard modules move out of the initial JS chunk.

---

### Task 4: Add Vite Manual Chunk Names

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Add manual chunks**

Add `build.rollupOptions.output.manualChunks`:

```ts
build: {
  rollupOptions: {
    output: {
      manualChunks(id) {
        if (!id.includes('node_modules')) return undefined;
        if (id.includes('react') || id.includes('react-dom')) return 'vendor-react';
        if (id.includes('plotly') || id.includes('react-plotly') || id.includes('recharts')) return 'vendor-charts';
        if (id.includes('framer-motion')) return 'vendor-motion';
        if (id.includes('lucide-react')) return 'vendor-icons';
        if (id.includes('zustand')) return 'vendor-state';
        return 'vendor';
      },
    },
  },
},
```

Keep `chunkSizeWarningLimit` unchanged for this task. Do not silence the warning until after the split is measured.

- [ ] **Step 2: Verify chunk output**

Run:

```powershell
npm run build
Get-ChildItem -Path dist\assets -File | Sort-Object Length -Descending | Select-Object @{Name='KB';Expression={[math]::Round($_.Length/1KB,1)}},Name
```

Expected: output includes named chunks such as `vendor-charts-*.js`, `vendor-react-*.js`, and a smaller app entry chunk.

---

### Task 5: Split ChartWorkspace Types, Constants, And Storage

**Files:**
- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceTypes.ts`
- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceConstants.ts`
- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceStorage.ts`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Move local UI types**

Move these local declarations from `ChartWorkspace.tsx` to `chartWorkspaceTypes.ts` and export them:

```ts
import type { ChartWorkspaceIndicatorId } from '@/types';

export type ChartWorkspaceIndicatorPresetId = 'core' | 'trend' | 'momentum' | 'clean' | 'custom';
export type ChartWorkspaceLayoutMode = 'analysis' | 'execution' | 'research';
export type ChartWorkspacePanelId = 'snapshot' | 'strategy' | 'lab' | 'oscillators';
export type ChartWorkspaceChartType = 'candlestick' | 'line';
export type ChartWorkspaceBarLimit = 120 | 240 | 390;
export type ChartWorkspaceOrbReplaySession = 'market_open' | 'premarket_30m';
export type ChartWorkspaceOrbOverlaySession = 'market_open' | 'premarket_30m';
export type MarketMapLayoutPreset = 'morning_plan' | 'intraday_alerts' | 'replay_proof';

export interface ChartWorkspaceIndicatorPresetOption {
  id: Exclude<ChartWorkspaceIndicatorPresetId, 'custom'>;
  label: string;
  indicators: ChartWorkspaceIndicatorId[];
}

export interface ChartWorkspacePanelVisibility {
  snapshot: boolean;
  strategy: boolean;
  lab: boolean;
  oscillators: boolean;
}

export interface ChartWorkspaceLayoutState {
  marketMapPreset: MarketMapLayoutPreset;
  layoutMode: ChartWorkspaceLayoutMode;
  panelVisibility: ChartWorkspacePanelVisibility;
}

export interface ChartWorkspacePreferencesState {
  activeSymbol: string;
  chartType: ChartWorkspaceChartType;
  indicatorPreset: ChartWorkspaceIndicatorPresetId;
  selectedIndicators: ChartWorkspaceIndicatorId[];
  barLimit: ChartWorkspaceBarLimit;
  showOrbOverlays: boolean;
  showVolume: boolean;
  orbOverlaySessions: ChartWorkspaceOrbOverlaySession[];
}

export interface ChartWorkspaceSimulationLabExperiment {
  id?: string;
  label?: string;
  runnable?: boolean;
  http_method?: string;
  endpoint_path?: string;
  result_schema_version?: string;
  result_metadata_fields?: string[];
}

export interface ChartWorkspaceSimulationLabStatus {
  enabled?: boolean;
  default_hidden?: boolean;
  disabled_reason?: string | null;
  experiments?: ChartWorkspaceSimulationLabExperiment[];
}

export interface ChartWorkspaceSimulationLabResult {
  kind: 'orb_backtest' | 'buying_power_allocation' | 'stop_trailing_dca';
  label: string;
  symbol?: string;
  created_at?: string;
  result: Record<string, unknown> & {
    schema_version?: string;
    run_id?: string;
    input_fingerprint?: string;
    input_fingerprint_algorithm?: string;
    summary?: Record<string, unknown>;
  };
}

export interface ChartWorkspaceIndicatorSnapshotMetric {
  label: string;
  value: string;
  timestamp?: string;
}
```

- [ ] **Step 2: Move constants**

Move constant declarations to `chartWorkspaceConstants.ts`, importing needed types from `chartWorkspaceTypes.ts`.

- [ ] **Step 3: Move storage helpers**

Move `readChartWorkspaceLayout`, `persistChartWorkspaceLayout`, `clearChartWorkspaceLayout`, `readChartWorkspacePreferences`, `persistChartWorkspacePreferences`, `clearChartWorkspacePreferences`, `readChartWorkspaceLabResult`, `persistChartWorkspaceLabResult`, `clearChartWorkspaceLabResult`, and all related normalization/type-guard helpers into `chartWorkspaceStorage.ts`.

- [ ] **Step 4: Import the extracted modules**

In `ChartWorkspace.tsx`, import from the new modules:

```ts
import {
  BAR_LIMIT_OPTIONS,
  DEFAULT_INDICATORS,
  DEFAULT_LAYOUT_STATE,
  DEFAULT_ORB_OVERLAY_SESSIONS,
  INDICATOR_OPTIONS,
  INDICATOR_PRESET_OPTIONS,
  LAYOUT_OPTIONS,
  LOCAL_PREVIEW_FEED_MESSAGE,
  MARKET_MAP_LAYOUT_PRESETS,
  ORB_OVERLAY_SESSION_OPTIONS,
  ORB_REPLAY_SESSION_OPTIONS,
  PANEL_OPTIONS,
} from './chart-workspace/chartWorkspaceConstants';
import {
  clearChartWorkspaceLabResult,
  clearChartWorkspaceLayout,
  clearChartWorkspacePreferences,
  cloneDefaultPreferencesState,
  inferIndicatorPreset,
  inferMarketMapPreset,
  normalizeChartWorkspaceIndicators,
  normalizeChartWorkspaceSymbol,
  persistChartWorkspaceLabResult,
  persistChartWorkspaceLayout,
  persistChartWorkspacePreferences,
  readChartWorkspaceLabResult,
  readChartWorkspaceLayout,
  readChartWorkspacePreferences,
} from './chart-workspace/chartWorkspaceStorage';
```

- [ ] **Step 5: Add guardrails**

Add:

```js
const chartWorkspaceTypesSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceTypes.ts');
const chartWorkspaceStorageSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceStorage.ts');

test('Chart workspace types and storage are split from the UI container', () => {
  assert.match(chartWorkspaceTypesSource, /export type ChartWorkspaceLayoutMode/);
  assert.match(chartWorkspaceStorageSource, /export function readChartWorkspaceLayout/);
  assert.doesNotMatch(chartWorkspaceSource, /function readChartWorkspaceLayout/);
});
```

- [ ] **Step 6: Verify**

Run:

```powershell
npm run test:layout
npm run lint
npm run build
```

Expected: behavior unchanged; `ChartWorkspace.tsx` line count drops materially.

---

### Task 6: Split ChartWorkspace Fallback Data And Plotly Traces

**Files:**
- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceFallbackData.ts`
- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceTraces.ts`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Move fallback data builders**

Move these functions to `chartWorkspaceFallbackData.ts` and export the public builders:

```ts
export function buildFallbackChartWorkspaceSnapshot(...) { ... }
export function buildFallbackProofMarkers(...) { ... }
export function buildFallbackMarketMapContext(...) { ... }
```

Keep helper functions private inside the fallback module:

```ts
function buildFallbackBars(...) { ... }
function buildFallbackIndicators(...) { ... }
function calculateSimpleMovingAverage(...) { ... }
function calculateExponentialMovingAverage(...) { ... }
function calculateRelativeStrengthIndex(...) { ... }
function calculateMovingAverageConvergenceDivergence(...) { ... }
function calculateAverageTrueRange(...) { ... }
```

- [ ] **Step 2: Move trace builders**

Move these functions to `chartWorkspaceTraces.ts` and export only the UI-facing builders:

```ts
export function buildPriceTraces(...) { ... }
export function buildOscillatorTraces(...) { ... }
export function buildIndicatorSnapshotMetrics(...) { ... }
```

Keep helpers private:

```ts
function buildMarketMapLevelTraces(...) { ... }
function buildMarketMapProofMarkerTraces(...) { ... }
function orbLineTrace(...) { ... }
function marketMapLevelColor(...) { ... }
function indicatorTraceColor(...) { ... }
function resolveProofMarkerPrice(...) { ... }
```

- [ ] **Step 3: Import the extracted functions**

In `ChartWorkspace.tsx`:

```ts
import {
  buildFallbackChartWorkspaceSnapshot,
  buildFallbackMarketMapContext,
  buildFallbackProofMarkers,
} from './chart-workspace/chartWorkspaceFallbackData';
import {
  buildIndicatorSnapshotMetrics,
  buildOscillatorTraces,
  buildPriceTraces,
} from './chart-workspace/chartWorkspaceTraces';
```

- [ ] **Step 4: Add guardrails**

Add:

```js
const chartWorkspaceFallbackSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceFallbackData.ts');
const chartWorkspaceTracesSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceTraces.ts');

test('Chart workspace data generation and traces live outside the UI container', () => {
  assert.match(chartWorkspaceFallbackSource, /export function buildFallbackChartWorkspaceSnapshot/);
  assert.match(chartWorkspaceTracesSource, /export function buildPriceTraces/);
  assert.doesNotMatch(chartWorkspaceSource, /function calculateRelativeStrengthIndex/);
  assert.doesNotMatch(chartWorkspaceSource, /function buildPriceTraces/);
});
```

- [ ] **Step 5: Verify chart screens**

Run:

```powershell
npm run test:layout
npm run lint
npm run build
```

Then run a Playwright smoke check against `http://localhost:64047/#charting`, `#market-map`, and `#greeks`:

```powershell
$env:NODE_PATH='C:\Users\Lite OS\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules;C:\Users\Lite OS\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules\.pnpm\node_modules'
@'
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  for (const route of ['charting', 'market-map', 'greeks']) {
    await page.goto(`http://localhost:64047/#${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2500);
    const result = await page.evaluate(() => ({
      apiError: document.body.innerText.includes('Expected JSON response'),
      plotCount: document.querySelectorAll('.js-plotly-plot').length,
      canvasCount: document.querySelectorAll('canvas').length,
    }));
    console.log(route, result);
  }
  await browser.close();
})();
'@ | & 'C:\Users\Lite OS\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' -
```

Expected: Charting and Market Map have Plotly charts; Greeks has a canvas; no API error text appears.

---

### Task 7: Split ChartWorkspace Formatters And Small Components

**Files:**
- Create: `frontend/src/components/dashboards/chart-workspace/chartWorkspaceFormatters.ts`
- Create: `frontend/src/components/dashboards/chart-workspace/Metric.tsx`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Move formatting helpers**

Move all pure display helpers into `chartWorkspaceFormatters.ts`, including:

```ts
export function formatOrbSessionStatus(...) { ... }
export function formatOrbReadiness(...) { ... }
export function formatOrbSessionLevelSummary(...) { ... }
export function formatOrbSessionReadinessDetail(...) { ... }
export function formatIndicatorPresetLabel(...) { ... }
export function formatSelectedIndicators(...) { ... }
export function formatIndicatorOptionLabel(...) { ... }
export function formatMarketMapLevelPrice(...) { ... }
export function buildMarketMapBias(...) { ... }
export function formatNearestMarketMapLevel(...) { ... }
export function formatParserConfidence(...) { ... }
export function formatProofMarkerTimestamp(...) { ... }
export function formatMarketMapContextStatus(...) { ... }
export function formatMarketMapContextProximity(...) { ... }
export function formatOrbOverlaySessionSummary(...) { ... }
export function formatVolumeOverlay(...) { ... }
export function formatSimulationLabGate(...) { ... }
export function formatSimulationLabDisabledReason(...) { ... }
export function formatChartType(...) { ... }
export function formatLayoutMode(...) { ... }
export function formatSimulationLabEndpoint(...) { ... }
export function formatSimulationLabExperimentId(...) { ... }
export function formatSimulationLabResultTitle(...) { ... }
export function formatSimulationLabResultMeta(...) { ... }
export function formatSimulationLabResultMismatch(...) { ... }
export function formatSimulationLabResultScopeLabel(...) { ... }
export function formatSimulationLabResultScopeClass(...) { ... }
export function formatSimulationLabResultTimestamp(...) { ... }
export function buildSimulationLabResultMetrics(...) { ... }
```

- [ ] **Step 2: Move Metric tile**

Create `Metric.tsx`:

```tsx
export function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-2">
      <div className="text-[11px] uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}
```

- [ ] **Step 3: Add guardrails**

Add:

```js
const chartWorkspaceFormattersSource = src('../src/components/dashboards/chart-workspace/chartWorkspaceFormatters.ts');
const chartWorkspaceMetricSource = src('../src/components/dashboards/chart-workspace/Metric.tsx');

test('Chart workspace formatters and metric tile are split from the UI container', () => {
  assert.match(chartWorkspaceFormattersSource, /export function formatMarketMapContextStatus/);
  assert.match(chartWorkspaceMetricSource, /export function Metric/);
  assert.doesNotMatch(chartWorkspaceSource, /function formatSimulationLabResultMetric/);
  assert.doesNotMatch(chartWorkspaceSource, /function Metric/);
});
```

- [ ] **Step 4: Verify**

Run:

```powershell
npm run test:layout
npm run lint
npm run build
```

Expected: no visual behavior change; `ChartWorkspace.tsx` becomes mostly orchestration/render code.

---

### Task 8: Add A Bundle Budget Check

**Files:**
- Create: `frontend/tests/bundle-budget.test.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: Add bundle budget test**

Create:

```js
import assert from 'node:assert/strict';
import { existsSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';

const assetsDir = path.resolve(process.cwd(), 'dist/assets');

test('built app entry chunk stays below the Sentinel Edge budget', { skip: !existsSync(assetsDir) }, () => {
  const jsAssets = readdirSync(assetsDir).filter((name) => name.endsWith('.js'));
  const entry = jsAssets
    .filter((name) => name.startsWith('index-'))
    .map((name) => ({ name, size: statSync(path.join(assetsDir, name)).size }))
    .sort((a, b) => b.size - a.size)[0];

  assert.ok(entry, 'expected an index JS asset after npm run build');
  assert.ok(
    entry.size < 900 * 1024,
    `expected app entry below 900 KB, received ${Math.round(entry.size / 1024)} KB in ${entry.name}`,
  );
});

test('chart vendor code is emitted as a separate async chunk', { skip: !existsSync(assetsDir) }, () => {
  const jsAssets = readdirSync(assetsDir).filter((name) => name.endsWith('.js'));
  assert.ok(
    jsAssets.some((name) => name.startsWith('vendor-charts-')),
    `expected vendor-charts chunk, received ${jsAssets.join(', ')}`,
  );
});
```

- [ ] **Step 2: Add npm script**

In `frontend/package.json`:

```json
"test:bundle": "node --test tests/bundle-budget.test.mjs"
```

- [ ] **Step 3: Verify**

Run:

```powershell
npm run build
npm run test:bundle
```

Expected: the entry chunk budget test passes after lazy loading and manual chunks. If the entry is still above budget, inspect which eager import remains before raising the threshold.

---

### Task 9: Optional Plotly Reduction Investigation

**Files:**
- Modify only after measuring: `frontend/package.json`, `frontend/src/components/ui/PlotlyCharts.tsx`

- [ ] **Step 1: Measure whether `vendor-charts` is still too large**

Run:

```powershell
npm run build
Get-ChildItem -Path dist\assets -File -Filter 'vendor-charts-*.js' | Select-Object @{Name='KB';Expression={[math]::Round($_.Length/1KB,1)}},Name
```

- [ ] **Step 2: Decide based on actual size**

If `vendor-charts` is large but async-loaded only by chart screens, leave it alone for now. If chart tab load feels slow, investigate replacing Plotly for `ChartWorkspace` with a lighter candlestick/line renderer or a custom Plotly bundle that includes only candlestick, scatter, and bar traces.

- [ ] **Step 3: Do not hide the warning prematurely**

Only set `build.chunkSizeWarningLimit` after the entry chunk is under budget and the remaining large chart chunk is intentionally isolated.

---

## Execution Order

1. Task 1: shared lazy fallback.
2. Task 2: top-level mode lazy loading.
3. Task 3: legacy operations lazy loading.
4. Task 4: manual chunk naming and measurement.
5. Task 8: bundle budget guard.
6. Task 5: ChartWorkspace types/constants/storage split.
7. Task 6: ChartWorkspace fallback/traces split.
8. Task 7: ChartWorkspace formatters/components split.
9. Task 9: Plotly reduction only if measurement justifies it.

## Verification Checklist

- `npm run test:layout`
- `npm run lint`
- `npm run build`
- `npm run test:bundle` after Task 8
- Playwright smoke check for:
  - `http://localhost:64047/#monitor`
  - `http://localhost:64047/#charting`
  - `http://localhost:64047/#market-map`
  - `http://localhost:64047/#greeks`
  - `http://localhost:64047/#directives`
  - `http://localhost:64047/#operations`

## Expected Outcome

- Initial app JS chunk should drop substantially because Plotly, Recharts, tutorials, and legacy dashboard code stop loading at startup.
- Remaining large chart code should be isolated into named async chunks.
- `ChartWorkspace.tsx` should shrink from about `2,509` lines to a focused container file.
- Future work on Charting, Market Map, Greeks, and Operations should be easier because data generation, trace generation, formatting, storage, and UI rendering will have separate ownership.
