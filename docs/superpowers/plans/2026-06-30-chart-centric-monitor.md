# Chart-Centric Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework Sentinel Edge Monitor into a chart-first workspace with a collapsible asset rail and a dedicated Asset tab.

**Architecture:** Keep the change scoped to the Asset Command Console. `MonitorPanel` owns the chart-centric layout and local Monitor sub-tabs; the existing global right-stack stays available for other top-level modes. CSS stays in the existing asset-command CSS slices, with new Monitor-specific classes in `AssetCommandConsole.panels.css`.

**Tech Stack:** React 18, TypeScript, Vite, existing CSS modules by import, lucide-react icons.

---

### Task 1: Structural Guard

**Files:**
- Create: `frontend/tests/asset-command-monitor-layout.test.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: Write the failing structural test**

```js
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

const monitorSource = readFileSync(new URL('../src/components/asset-command/components/MonitorPanel.tsx', import.meta.url), 'utf8');
const consoleSource = readFileSync(new URL('../src/components/asset-command/AssetCommandConsole.tsx', import.meta.url), 'utf8');

test('MonitorPanel owns the chart-centric workspace structure', () => {
  assert.match(monitorSource, /edge-monitor-chart-shell/);
  assert.match(monitorSource, /edge-monitor-rail/);
  assert.match(monitorSource, /edge-monitor-tabs/);
  assert.match(monitorSource, /edge-monitor-asset-tab/);
  assert.match(monitorSource, /Wide signal chart/);
});

test('Monitor receives selected asset and command actions from the console shell', () => {
  assert.match(consoleSource, /selected=\{selected\}/);
  assert.match(consoleSource, /watcher=\{watcher\}/);
  assert.match(consoleSource, /onCommand=\{runCommand\}/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:layout -- --test-reporter=spec`

Expected: FAIL because the new Monitor structure and props do not exist yet.

### Task 2: Monitor Component

**Files:**
- Modify: `frontend/src/components/asset-command/components/MonitorPanel.tsx`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`

- [ ] **Step 1: Add Monitor local state and props**

Pass `selected`, `watcher`, and `onCommand` into `MonitorPanel`. Inside `MonitorPanel`, add local state for the sub-tab (`monitor`, `assets`, `diagnostics`) and whether the rail is collapsed.

- [ ] **Step 2: Implement chart-centric Monitor layout**

Render:
- top Monitor actions
- local tabs for Monitor, Assets, Diagnostics
- collapsed ticker rail with active symbol
- wide signal chart placeholder using selected asset data
- chart metrics row
- compact command strip under the chart
- Asset tab with full picker/detail/bulk action content
- Diagnostics tab with the existing health/service/runtime sections

### Task 3: Monitor Styling

**Files:**
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.panels.css`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.picker.css`

- [ ] **Step 1: Add chart-centric CSS**

Create CSS for `.edge-monitor-chart-shell`, `.edge-monitor-rail`, `.edge-monitor-chart`, `.edge-monitor-command-strip`, `.edge-monitor-asset-tab`, and responsive variants.

- [ ] **Step 2: Keep text contained**

Ensure ticker rail labels, command buttons, metrics, and Asset tab cells have stable dimensions and do not resize the grid on hover.

### Task 4: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run structural test**

Run: `npm run test:layout -- --test-reporter=spec`

Expected: PASS.

- [ ] **Step 2: Run build**

Run: `npm run build`

Expected: PASS.

- [ ] **Step 3: Browser check**

Open `http://localhost:3000/#monitor`, inspect desktop and narrow widths, and verify the chart is larger/wider, the rail collapses, the Asset tab holds the picker detail, and no text overlaps.
