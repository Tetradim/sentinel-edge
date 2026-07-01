# Greeks Volume Heatmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the first production feature from the new UI direction: an interactive Greeks tab with a canvas-based volume heatmap adapted from the provided standalone HTML mock.

**Architecture:** Extend the existing asset command console mode system with a `greeks` tab. Keep the heatmap drawing isolated in a reusable `VolumeHeatmap` component and place workspace framing in a `GreeksPanel` component. Add CSS in a dedicated imported stylesheet so the new visuals do not destabilize the existing Monitor work.

**Tech Stack:** React 18, TypeScript, Vite, HTML canvas, CSS modules by convention through existing global component styles, Node test runner for layout/source assertions.

---

### Task 1: Add the Greeks tab route

**Files:**
- Modify: `frontend/src/components/asset-command/types.ts`
- Modify: `frontend/src/components/asset-command/data.ts`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`

- [ ] **Step 1: Extend the mode type**

Update `Mode` so the console can represent the new tab:

```ts
export type Mode = 'monitor' | 'command' | 'charting' | 'greeks' | 'directives' | 'market-map' | 'protect' | 'operations' | 'settings';
```

- [ ] **Step 2: Update the ordered tab list and labels**

In `data.ts`, expose the new top-level tabs:

```ts
export const modes: Mode[] = ['monitor', 'command', 'charting', 'greeks', 'directives', 'market-map', 'protect', 'operations', 'settings'];
```

Update `modeLabel` to return `Charting`, `Greeks`, and `Directives` for those modes.

- [ ] **Step 3: Render the Greeks panel**

Import `GreeksPanel` into `AssetCommandConsole.tsx` and render it when `mode === 'greeks'`.

### Task 2: Build the interactive heatmap component

**Files:**
- Create: `frontend/src/components/asset-command/components/VolumeHeatmap.tsx`
- Create: `frontend/src/components/asset-command/components/GreeksPanel.tsx`
- Create: `frontend/src/components/asset-command/AssetCommandConsole.greeks.css`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.css`

- [ ] **Step 1: Port the standalone heatmap behavior**

Create `VolumeHeatmap.tsx` with typed session bars, generated intraday sample data, blurred volume-by-price matrix construction, heatmap canvas rendering, volume bar rendering, price/time axes, hover tooltip/crosshair, refresh, and snapshot download.

- [ ] **Step 2: Host it in a Greeks workspace**

Create `GreeksPanel.tsx` with top metrics, the `VolumeHeatmap`, and adjacent Greek readout cards for GEX/VEX, spot, strike wall, put/call pressure, and bridge status.

- [ ] **Step 3: Style the Greeks workspace**

Import `AssetCommandConsole.greeks.css` from `AssetCommandConsole.css`. Add stable responsive dimensions, dark chart-centric panels, axis columns, legend, controls, tooltip, and bottom readout cards.

### Task 3: Verify wiring and build

**Files:**
- Modify: `frontend/tests/asset-command-monitor-layout.test.mjs`

- [ ] **Step 1: Add source-level assertions**

Assert that `data.ts` includes `greeks`, `AssetCommandConsole.tsx` renders `GreeksPanel`, and `VolumeHeatmap.tsx` contains the canvas/crosshair/save hooks.

- [ ] **Step 2: Run focused tests**

Run:

```powershell
npm run test:layout -- --test-reporter=spec
```

Expected: all layout assertions pass.

- [ ] **Step 3: Run production build**

Run:

```powershell
npm run build
```

Expected: TypeScript and Vite complete successfully.
