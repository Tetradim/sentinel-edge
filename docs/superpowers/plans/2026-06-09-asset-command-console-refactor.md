# Asset Command Console Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deepen the Asset Command Console module so market command state, runtime state, activity filtering, ticker-picking, and UI rendering can change independently without editing one 900-line TSX file and one 1,300-line CSS file.

**Architecture:** Keep `AssetCommandConsole` as the app-root adapter, but move reusable Edge command concepts into modules with small interfaces. First extract pure data/types, then hooks for navigation/runtime/activity/picker behavior, then presentational modules, and split CSS last after selectors have stable owners.

**Tech Stack:** React 18, TypeScript, Vite, Python `unittest` static regressions, existing `npm run build`.

---

## Scope And Current State

Current pressure points:

- `frontend/src/components/asset-command/AssetCommandConsole.tsx` is 909 lines and mixes data fixtures, domain types, hash navigation, runtime polling, activity log behavior, ticker picker behavior, and rendering.
- `frontend/src/components/asset-command/AssetCommandConsole.css` is 1,377 lines and owns every visual state for the command surface.
- `backend/tests/test_asset_command_ui_static.py` asserts exact source strings inside `AssetCommandConsole.tsx`, so it must be updated before moving code or it will block safe refactoring.
- The current worktree already has uncommitted activity-log and ticker-picker improvements. Execute this plan only after deciding whether those changes are committed as the baseline or intentionally included in the refactor branch.

Recommended order:

1. Preserve behavior with static contract tests that allow modules to move.
2. Extract data and types.
3. Extract command-state hooks.
4. Extract presentational modules.
5. Split CSS by owned surface.
6. Run the same verification after every task.

---

## Target File Structure

- Create: `frontend/src/components/asset-command/types.ts`
  - Owns exported domain types: `Mode`, `OperationsView`, `Tone`, `EventFilter`, `Watcher`, `Metric`, `Ticker`, `EventLine`, `RuntimeState`, `OperationViewItem`.
- Create: `frontend/src/components/asset-command/data.ts`
  - Owns static command-console fixtures and derived constants: `tickers`, `eventSymbols`, `initialEvents`, `eventFilterOptions`, `allMetricOptions`, `serviceRows`, `protectionRows`, `operationsViews`, `modes`, `modeLabel`, `money`, `nowTime`.
- Create: `frontend/src/components/asset-command/hooks/useAssetCommandNavigation.ts`
  - Owns hash parsing/writing, mode state, operations view state, and keyboard roving for top-level mode tabs and operations tabs.
- Create: `frontend/src/components/asset-command/hooks/useRuntimeStatus.ts`
  - Owns runtime polling, scheduler pause/resume, and runtime control error event emission.
- Create: `frontend/src/components/asset-command/hooks/useAssetCommandState.ts`
  - Owns selected ticker, metric selection, activity events, activity filters, picker movement, command actions, protection actions, and signal intelligence.
- Create: `frontend/src/components/asset-command/components/ActivityLog.tsx`
  - Renders activity filters, empty state, and focusable event rows.
- Create: `frontend/src/components/asset-command/components/TickerPicker.tsx`
  - Renders kinetic watchlist and owns wheel/key DOM handlers through props from the state hook.
- Create: `frontend/src/components/asset-command/components/CommandModePanel.tsx`
  - Renders the command-mode signal intelligence, plugin watcher, prediction controls, and metric reels.
- Create: `frontend/src/components/asset-command/components/ModeTabs.tsx`
  - Renders the top mode tablist.
- Create: `frontend/src/components/asset-command/components/OperationsPanel.tsx`
  - Moves the existing operations deck out of the app-root adapter.
- Create: `frontend/src/components/asset-command/components/MonitorPanel.tsx`
  - Moves monitor mode rendering out of the app-root adapter.
- Create: `frontend/src/components/asset-command/components/ProtectionPanel.tsx`
  - Moves protect mode rendering out of the app-root adapter.
- Create: `frontend/src/components/asset-command/components/SettingsPanel.tsx`
  - Moves metric settings rendering out of the app-root adapter.
- Create: `frontend/src/components/asset-command/components/shared.tsx`
  - Owns small presentational modules used across panels: `RuntimeBadges`, `StatusMetric`, `PanelTitle`, `HealthCard`, `SectionHead`, `ServiceRow`.
- Create: `frontend/src/components/asset-command/AssetCommandConsole.activity.css`
  - Owns `.edge-events`, `.edge-event-*`.
- Create: `frontend/src/components/asset-command/AssetCommandConsole.picker.css`
  - Owns `.edge-picker-*`.
- Create: `frontend/src/components/asset-command/AssetCommandConsole.panels.css`
  - Owns panel-specific command, monitor, protect, operations, and settings selectors.
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`
  - Becomes a thin app-root adapter that composes hooks and modules.
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.css`
  - Retains page shell, layout, shared tokens, and imports the split CSS files.
- Modify: `backend/tests/test_asset_command_ui_static.py`
  - Tests module contracts instead of exact implementation location.

---

### Task 1: Make Static Tests Module-Aware

**Files:**
- Modify: `backend/tests/test_asset_command_ui_static.py`

- [ ] **Step 1: Add paths for the target modules before extracting code**

Add these constants after `ASSET_COMMAND_CSS`:

```python
ASSET_COMMAND_DATA = ROOT / "frontend" / "src" / "components" / "asset-command" / "data.ts"
ASSET_COMMAND_STATE_HOOK = ROOT / "frontend" / "src" / "components" / "asset-command" / "hooks" / "useAssetCommandState.ts"
ASSET_COMMAND_ACTIVITY = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "ActivityLog.tsx"
ASSET_COMMAND_PICKER = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "TickerPicker.tsx"
ASSET_COMMAND_NAVIGATION_HOOK = ROOT / "frontend" / "src" / "components" / "asset-command" / "hooks" / "useAssetCommandNavigation.ts"
```

- [ ] **Step 2: Add helper readers that fall back during the migration**

Add this helper after the constants:

```python
def read_existing(*paths: Path) -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())
```

- [ ] **Step 3: Update activity-log tests to read app-root plus future modules**

Change the first line in each activity-log test from:

```python
text = ASSET_COMMAND.read_text(encoding="utf-8")
```

to:

```python
text = read_existing(ASSET_COMMAND, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_ACTIVITY)
```

Apply this to:

- `test_activity_log_can_be_filtered_without_losing_total_context`
- `test_activity_log_filter_buttons_expose_event_counts`
- `test_activity_log_empty_state_can_return_to_all_events`
- `test_activity_log_events_can_focus_tracked_symbols`
- `test_reselecting_current_symbol_does_not_add_noise_event`

- [ ] **Step 4: Update picker tests to read app-root plus future modules**

Change the first line in each picker test from:

```python
text = ASSET_COMMAND.read_text(encoding="utf-8")
```

to:

```python
text = read_existing(ASSET_COMMAND, ASSET_COMMAND_DATA, ASSET_COMMAND_STATE_HOOK, ASSET_COMMAND_PICKER)
```

Apply this to:

- `test_ticker_picker_supports_keyboard_navigation`
- `test_ticker_picker_keyboard_controls_are_discoverable`
- `test_ticker_picker_exposes_selected_item_to_assistive_tech`

- [ ] **Step 5: Add a characterization test for migration-safe readers**

Add this test near the end of `AssetCommandUiStaticTests`:

```python
def test_asset_command_refactor_readers_tolerate_future_modules(self):
    text = read_existing(
        ASSET_COMMAND,
        ASSET_COMMAND_DATA,
        ASSET_COMMAND_STATE_HOOK,
        ASSET_COMMAND_ACTIVITY,
        ASSET_COMMAND_PICKER,
        ASSET_COMMAND_NAVIGATION_HOOK,
    )

    self.assertIn("tickers", text)
    self.assertNotIn(str(ASSET_COMMAND_DATA), text)
```

This test passes before extraction because `tickers` exists in `AssetCommandConsole.tsx`, and it proves `read_existing` ignores not-yet-created module paths instead of leaking path names into the search text.

- [ ] **Step 6: Run the static tests before production refactor**

Run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
```

Expected: `OK`.

- [ ] **Step 7: Commit test harness update**

```powershell
git add backend/tests/test_asset_command_ui_static.py
git commit -m "test: prepare asset command static regressions for refactor"
```

---

### Task 2: Extract Asset Command Types And Static Data

**Files:**
- Create: `frontend/src/components/asset-command/types.ts`
- Create: `frontend/src/components/asset-command/data.ts`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`
- Modify: `backend/tests/test_asset_command_ui_static.py`

- [ ] **Step 1: Create `types.ts` with exported interfaces**

Create:

```ts
import type React from 'react';

export type Mode = 'monitor' | 'command' | 'protect' | 'operations' | 'settings';
export type OperationsView = 'overview' | 'advisor' | 'experience' | 'protection' | 'pnl' | 'markets' | 'portfolio' | 'settings' | 'tutorials';
export type Tone = 'green' | 'cyan' | 'gold' | 'red';
export type EventFilter = 'all' | 'selected' | 'system';

export interface Watcher {
  plugin: string;
  status: string;
  trigger: string;
  source: string;
}

export interface Metric {
  id: string;
  label: string;
  value: string;
  detail: string;
  tone: Tone;
}

export interface Ticker {
  symbol: string;
  change: string;
  status: string;
  signal: string;
  price: number;
  watchers: Watcher[];
  metrics: Metric[];
}

export interface EventLine {
  id: string;
  symbol: string;
  title: string;
  detail: string;
  time: string;
}

export interface RuntimeState {
  connected: boolean;
  loading: boolean;
  pulseAvailable: boolean;
  killSwitchActive: boolean;
  schedulerPaused: boolean;
}

export interface OperationViewItem {
  id: OperationsView;
  label: string;
  icon: React.ElementType;
}
```

- [ ] **Step 2: Create `data.ts` by moving pure constants and helpers**

Move these exact declarations out of `AssetCommandConsole.tsx` into `data.ts`:

```ts
money
metricMap
createTicker
tickers
eventSymbols
initialEvents
eventFilterOptions
allMetricOptions
serviceRows
protectionRows
nowTime
operationsViews
modes
modeLabel
```

`data.ts` imports icon modules and types like this:

```ts
import { Activity, Bell, CheckCircle, Gauge, Save, Shield, SlidersHorizontal, Target, Zap } from 'lucide-react';
import type { EventFilter, EventLine, Metric, Mode, OperationViewItem, Ticker, Tone, Watcher } from './types';
```

Every moved declaration must be exported.

- [ ] **Step 3: Replace local types/data in `AssetCommandConsole.tsx` with imports**

At the top of `AssetCommandConsole.tsx`, keep React and UI imports, but import the new data/types:

```ts
import type { EventLine, EventFilter, Mode, OperationsView, RuntimeState, Tone } from './types';
import {
  allMetricOptions,
  eventFilterOptions,
  eventSymbols,
  initialEvents,
  modeLabel,
  modes,
  money,
  nowTime,
  operationsViews,
  protectionRows,
  serviceRows,
  tickers,
} from './data';
```

Then delete the moved local declarations.

- [ ] **Step 4: Fix the `SignalIntelligence` prop type while types are nearby**

Replace:

```ts
function SignalIntelligence({ intelligence }: { intelligence: ReturnType<typeof AssetCommandConsole> extends never ? never : any }) {
```

with a local type near the function:

```ts
interface SignalIntelligenceModel {
  move: string;
  price: string;
  delta: string;
  state: string;
  pressure: string;
  contributors: { label: string; value: string; tone: Tone }[];
}

function SignalIntelligence({ intelligence }: { intelligence: SignalIntelligenceModel }) {
```

- [ ] **Step 5: Run verification**

Run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
npm run build
```

Expected:

- Static tests pass.
- TypeScript build passes.

- [ ] **Step 6: Commit data/type extraction**

```powershell
git add frontend/src/components/asset-command/types.ts frontend/src/components/asset-command/data.ts frontend/src/components/asset-command/AssetCommandConsole.tsx backend/tests/test_asset_command_ui_static.py
git commit -m "refactor: extract asset command data and types"
```

---

### Task 3: Extract Navigation And Runtime Hooks

**Files:**
- Create: `frontend/src/components/asset-command/hooks/useAssetCommandNavigation.ts`
- Create: `frontend/src/components/asset-command/hooks/useRuntimeStatus.ts`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`

- [ ] **Step 1: Create `useAssetCommandNavigation.ts`**

Move hash parsing/writing and keyboard handling behind this interface:

```ts
import React, { useEffect, useState } from 'react';
import { modeLabel, modes, operationsViews } from '../data';
import type { Mode, OperationsView } from '../types';

export { modeLabel, modes };

const parseHashState = (): { mode: Mode; operationsView: OperationsView } => {
  if (typeof window === 'undefined') return { mode: 'command', operationsView: 'overview' };
  const raw = window.location.hash.replace('#', '');
  const [modePart, viewPart] = raw.split(':');
  const mode = modes.includes(modePart as Mode) ? (modePart as Mode) : 'command';
  const operationsView = operationsViews.some((item) => item.id === viewPart) ? (viewPart as OperationsView) : 'overview';
  return { mode, operationsView };
};

const writeHashState = (mode: Mode, operationsView = 'overview') => {
  if (typeof window === 'undefined') return;
  const hash = mode === 'operations' ? `#operations:${operationsView}` : `#${mode}`;
  if (window.location.hash !== hash) window.history.replaceState(null, '', hash);
};

export function useAssetCommandNavigation() {
  const initialHashState = parseHashState();
  const [mode, setModeState] = useState<Mode>(initialHashState.mode);
  const [operationsView, setOperationsViewState] = useState<OperationsView>(initialHashState.operationsView);

  useEffect(() => {
    const onHashChange = () => {
      const next = parseHashState();
      setModeState(next.mode);
      setOperationsViewState(next.operationsView);
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  const setMode = (nextMode: Mode) => {
    setModeState(nextMode);
    writeHashState(nextMode, operationsView);
  };

  const setOperationsView = (nextView: OperationsView) => {
    setOperationsViewState(nextView);
    writeHashState('operations', nextView);
  };

  const handleModeKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, currentMode: Mode) => {
    const currentIndex = modes.indexOf(currentMode);
    const nextMode =
      event.key === 'ArrowRight' ? modes[(currentIndex + 1) % modes.length] :
      event.key === 'ArrowLeft' ? modes[(currentIndex - 1 + modes.length) % modes.length] :
      event.key === 'Home' ? modes[0] :
      event.key === 'End' ? modes[modes.length - 1] :
      null;
    if (!nextMode) return;
    event.preventDefault();
    setMode(nextMode);
    window.requestAnimationFrame(() => document.getElementById(`edge-mode-tab-${nextMode}`)?.focus());
  };

  const handleOperationsKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, currentView: OperationsView) => {
    const viewIds = operationsViews.map((item) => item.id);
    const currentIndex = viewIds.indexOf(currentView);
    const nextView =
      event.key === 'ArrowDown' || event.key === 'ArrowRight' ? viewIds[(currentIndex + 1) % viewIds.length] :
      event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? viewIds[(currentIndex - 1 + viewIds.length) % viewIds.length] :
      event.key === 'Home' ? viewIds[0] :
      event.key === 'End' ? viewIds[viewIds.length - 1] :
      null;
    if (!nextView) return;
    event.preventDefault();
    setOperationsView(nextView);
    window.requestAnimationFrame(() => document.getElementById(`edge-ops-tab-${nextView}`)?.focus());
  };

  return { mode, operationsView, setMode, setOperationsView, handleModeKeyDown, handleOperationsKeyDown };
}
```

- [ ] **Step 2: Create `useRuntimeStatus.ts`**

Move runtime polling and scheduler toggling behind this interface:

```ts
import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import type { RuntimeState } from '../types';

const initialRuntime: RuntimeState = {
  connected: false,
  loading: true,
  pulseAvailable: false,
  killSwitchActive: false,
  schedulerPaused: false,
};

export function useRuntimeStatus(addEvent: (symbol: string, title: string, detail: string) => void) {
  const [runtime, setRuntime] = useState<RuntimeState>(initialRuntime);

  useEffect(() => {
    let cancelled = false;
    const loadRuntime = async () => {
      try {
        const [health, pulse, kill] = await Promise.allSettled([
          api.getHealth(),
          api.getPulseStatus(),
          api.getKillSwitchStatus(),
        ]);
        if (cancelled) return;
        const healthValue = health.status === 'fulfilled' ? health.value : null;
        const pulseValue = pulse.status === 'fulfilled' ? pulse.value : null;
        const killValue = kill.status === 'fulfilled' ? kill.value : null;
        setRuntime({
          connected: health.status === 'fulfilled',
          loading: false,
          pulseAvailable: Boolean(pulseValue?.available || healthValue?.pulse_available),
          killSwitchActive: Boolean(killValue?.kill_switch_active),
          schedulerPaused: Boolean(healthValue?.paused),
        });
      } catch {
        if (!cancelled) {
          setRuntime((current) => ({ ...current, connected: false, loading: false, pulseAvailable: false }));
        }
      }
    };
    loadRuntime();
    const id = window.setInterval(loadRuntime, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const toggleScheduler = async () => {
    if (runtime.loading || !runtime.connected) return;
    try {
      if (runtime.schedulerPaused) {
        await api.resumeScheduler();
      } else {
        await api.pauseScheduler();
      }
      setRuntime((current) => ({ ...current, schedulerPaused: !current.schedulerPaused }));
      addEvent('EDGE', runtime.schedulerPaused ? 'Scheduler resumed' : 'Scheduler paused', 'Runtime control updated from Asset Command');
    } catch {
      addEvent('EDGE', 'Scheduler control failed', 'Backend control endpoint unavailable');
    }
  };

  return { runtime, toggleScheduler };
}
```

- [ ] **Step 3: Wire hooks into `AssetCommandConsole.tsx`**

Replace local navigation and runtime state with:

```ts
const { mode, operationsView, setMode, setOperationsView, handleModeKeyDown, handleOperationsKeyDown } = useAssetCommandNavigation();
const { runtime, toggleScheduler } = useRuntimeStatus(addEvent);
```

Move this line after `addEvent` exists. If that creates ordering friction, move `addEvent` into `useAssetCommandState` in Task 4 first and then return to this task.

- [ ] **Step 4: Remove duplicated imports**

Remove `api` from `AssetCommandConsole.tsx` after `useRuntimeStatus` owns it.

- [ ] **Step 5: Run verification**

Run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
npm run build
```

Expected: tests and build pass.

- [ ] **Step 6: Commit hook extraction**

```powershell
git add frontend/src/components/asset-command/hooks frontend/src/components/asset-command/AssetCommandConsole.tsx
git commit -m "refactor: extract asset command navigation and runtime hooks"
```

---

### Task 4: Extract Asset Command State Hook

**Files:**
- Create: `frontend/src/components/asset-command/hooks/useAssetCommandState.ts`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`

- [ ] **Step 1: Create `useAssetCommandState.ts`**

Move selected asset state, metric state, event state, filters, picker movement, command actions, protection actions, and intelligence into one module:

```ts
import React, { useMemo, useRef, useState } from 'react';
import { initialEvents, money, nowTime, tickers } from '../data';
import type { EventFilter, EventLine, Tone } from '../types';

export function useAssetCommandState() {
  const [selectedSymbol, setSelectedSymbol] = useState('SPY');
  const [horizon, setHorizon] = useState('30m');
  const [menuOpen, setMenuOpen] = useState(false);
  const [customHorizon, setCustomHorizon] = useState('90m');
  const [visibleReels, setVisibleReels] = useState(5);
  const [selectedMetrics, setSelectedMetrics] = useState(['hist', 'vscore', 'emaTop', 'invalid', 'momentum']);
  const [events, setEvents] = useState<EventLine[]>(() => initialEvents.map((event) => ({ ...event, time: nowTime() })));
  const [eventFilter, setEventFilter] = useState<EventFilter>('all');
  const [feedPaused, setFeedPaused] = useState(false);
  const [protectionMode, setProtectionMode] = useState('armed');
  const wheelDelta = useRef(0);
  const wheelLocked = useRef(false);

  const selected = tickers.find((ticker) => ticker.symbol === selectedSymbol) || tickers[0];
  const selectedIndex = tickers.findIndex((ticker) => ticker.symbol === selected.symbol);
  const watcher = selected.watchers[0];
  const reels = selected.metrics.filter((metric) => selectedMetrics.includes(metric.id)).slice(0, visibleReels);
  const eventFilterCounts: Record<EventFilter, number> = {
    all: events.length,
    selected: events.filter((event) => event.symbol === selected.symbol).length,
    system: events.filter((event) => event.symbol === 'EDGE' || event.symbol === 'PROTECT').length,
  };
  const visibleEvents = events.filter((event) => {
    if (eventFilter === 'selected') return event.symbol === selected.symbol;
    if (eventFilter === 'system') return event.symbol === 'EDGE' || event.symbol === 'PROTECT';
    return true;
  });

  const intelligence = useMemo(() => {
    const pluginBoost = selected.watchers.length ? 18 : 4;
    return {
      move: selected.watchers.some((item) => item.plugin === 'MACD-V') ? '+0.8%' : '+0.4%',
      price: money(selected.price),
      delta: selected.watchers.length ? '+4 pts' : '+1 pt',
      state: selected.watchers.length ? 'strengthening' : 'monitoring',
      pressure: selected.watchers.length ? `${selected.watchers[0].plugin} pressure rising` : 'baseline pressure stable',
      contributors: [
        { label: 'Trend', value: '+22', tone: 'green' as Tone },
        { label: 'Volume', value: '+14', tone: 'cyan' as Tone },
        { label: 'Risk', value: '-6', tone: 'red' as Tone },
        { label: 'Plugin', value: `+${pluginBoost}`, tone: 'gold' as Tone },
      ],
    };
  }, [selected]);

  const addEvent = (symbol: string, title: string, detail: string) => {
    setEvents((current) => [{ id: `${Date.now()}`, symbol, title, detail, time: nowTime() }, ...current].slice(0, 12));
  };

  const selectSymbol = (symbol: string) => {
    const ticker = tickers.find((item) => item.symbol === symbol);
    if (!ticker) return;
    if (symbol === selectedSymbol) return;
    setSelectedSymbol(symbol);
    setSelectedMetrics(ticker.metrics.slice(0, visibleReels).map((metric) => metric.id));
    addEvent(symbol, 'Ticker selected', `${symbol} command state loaded`);
  };

  const movePicker = (direction: number) => {
    const nextIndex = (selectedIndex + direction + tickers.length) % tickers.length;
    selectSymbol(tickers[nextIndex].symbol);
  };

  const handleWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (wheelLocked.current) return;
    wheelDelta.current += event.deltaY;
    if (Math.abs(wheelDelta.current) < 95) return;
    const direction = wheelDelta.current > 0 ? 1 : -1;
    wheelDelta.current = 0;
    wheelLocked.current = true;
    movePicker(direction);
    window.setTimeout(() => {
      wheelLocked.current = false;
    }, 240);
  };

  const handlePickerKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    const nextAction =
      event.key === 'ArrowDown' ? () => movePicker(1) :
      event.key === 'ArrowUp' ? () => movePicker(-1) :
      event.key === 'Home' ? () => selectSymbol(tickers[0].symbol) :
      event.key === 'End' ? () => selectSymbol(tickers[tickers.length - 1].symbol) :
      null;
    if (!nextAction) return;
    event.preventDefault();
    nextAction();
  };

  const setPrediction = (next: string) => {
    setHorizon(next);
    setMenuOpen(false);
    addEvent(selected.symbol, 'Prediction horizon changed', `Forecast window set to ${next}`);
  };

  const runCommand = (action: string) => {
    const labels: Record<string, string> = {
      arm: 'Arm Trigger',
      backtest: 'Backtest Window',
      alert: 'Convert to Alert',
      mute: 'Mute Watch',
    };
    addEvent(selected.symbol, labels[action] || action, `${selected.status} command acknowledged`);
  };

  const runMonitorAction = (action: string) => {
    if (action === 'toggle-feed') setFeedPaused((value) => !value);
    if (action === 'ack') addEvent('EDGE', 'Monitor alerts acknowledged', '3 alerts cleared');
    if (action === 'diagnostics') addEvent('EDGE', 'Diagnostics completed', 'Plugin bus, Pulse bridge, and prediction core checked');
    if (action === 'refresh') addEvent('EDGE', 'Monitor refreshed', 'Health probes and watcher telemetry updated');
  };

  const runProtectionAction = (action: string) => {
    const labels: Record<string, [string, string]> = {
      refresh: ['Protection refreshed', 'Stops, heat, hedge ratio, and invalidation bands updated'],
      tighten: ['Stops tightened', 'Stops trailed toward current price across protected positions'],
      hedge: ['Hedge staged', 'Coverage raised toward the target corridor'],
      reduce: ['Exposure reduced', 'Highest heat symbol reduced and redline corridor recalculated'],
      clear: ['Protection alerts acknowledged', 'Protection queue cleared'],
    };
    if (action === 'tighten') setProtectionMode('tightened');
    if (action === 'hedge') setProtectionMode('hedged');
    if (action === 'reduce') setProtectionMode('de-risked');
    const [title, detail] = labels[action] || labels.refresh;
    addEvent('PROTECT', title, detail);
  };

  const toggleMetric = (id: string) => {
    setSelectedMetrics((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  };

  const pickerItems = Array.from({ length: 7 }, (_, offset) => tickers[(selectedIndex + offset - 3 + tickers.length) % tickers.length]);

  return {
    selected,
    selectedIndex,
    watcher,
    reels,
    horizon,
    menuOpen,
    setMenuOpen,
    customHorizon,
    setCustomHorizon,
    visibleReels,
    setVisibleReels,
    selectedMetrics,
    eventFilter,
    setEventFilter,
    eventFilterCounts,
    visibleEvents,
    events,
    intelligence,
    feedPaused,
    protectionMode,
    pickerItems,
    addEvent,
    selectSymbol,
    handleWheel,
    handlePickerKeyDown,
    setPrediction,
    runCommand,
    runMonitorAction,
    runProtectionAction,
    toggleMetric,
  };
}
```

- [ ] **Step 2: Replace local state in `AssetCommandConsole.tsx`**

In `AssetCommandConsole`, replace all moved `useState`, `useMemo`, `useRef`, and action functions with:

```ts
const command = useAssetCommandState();
const { runtime, toggleScheduler } = useRuntimeStatus(command.addEvent);
```

Then pass `command.*` values into child modules.

- [ ] **Step 3: Remove now-unused React imports**

After moving state, `AssetCommandConsole.tsx` should not import `useMemo` or `useRef`. Keep only the hooks it still uses directly.

- [ ] **Step 4: Run verification**

Run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
npm run build
```

Expected: tests and build pass.

- [ ] **Step 5: Commit state extraction**

```powershell
git add frontend/src/components/asset-command/hooks/useAssetCommandState.ts frontend/src/components/asset-command/AssetCommandConsole.tsx
git commit -m "refactor: extract asset command state hook"
```

---

### Task 5: Extract Presentational Modules

**Files:**
- Create: `frontend/src/components/asset-command/components/shared.tsx`
- Create: `frontend/src/components/asset-command/components/ActivityLog.tsx`
- Create: `frontend/src/components/asset-command/components/TickerPicker.tsx`
- Create: `frontend/src/components/asset-command/components/CommandModePanel.tsx`
- Create: `frontend/src/components/asset-command/components/ModeTabs.tsx`
- Create: `frontend/src/components/asset-command/components/MonitorPanel.tsx`
- Create: `frontend/src/components/asset-command/components/ProtectionPanel.tsx`
- Create: `frontend/src/components/asset-command/components/OperationsPanel.tsx`
- Create: `frontend/src/components/asset-command/components/SettingsPanel.tsx`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.tsx`

- [ ] **Step 1: Move shared presentational modules**

Move these functions unchanged into `components/shared.tsx`, importing types from `../types`:

```ts
RuntimeBadges
StatusMetric
PanelTitle
HealthCard
SectionHead
ServiceRow
```

Export each function.

- [ ] **Step 2: Extract `ActivityLog.tsx`**

Create a module with this interface:

```ts
import { eventFilterOptions, eventSymbols } from '../data';
import type { EventFilter, EventLine } from '../types';
import { PanelTitle } from './shared';

export function ActivityLog({
  selectedSymbol,
  events,
  visibleEvents,
  eventFilter,
  eventFilterCounts,
  setEventFilter,
  selectSymbol,
}: {
  selectedSymbol: string;
  events: EventLine[];
  visibleEvents: EventLine[];
  eventFilter: EventFilter;
  eventFilterCounts: Record<EventFilter, number>;
  setEventFilter: (filter: EventFilter) => void;
  selectSymbol: (symbol: string) => void;
}) {
  return (
    <aside className="edge-glass edge-events" aria-label="Activity log">
      <PanelTitle eyebrow="Event log" title="Activity" chip={`${visibleEvents.length} of ${events.length} live`} />
      <div className="edge-event-filters" aria-label="Activity log filters">
        {eventFilterOptions.map((option) => (
          <button key={option.id} type="button" aria-pressed={eventFilter === option.id} className={eventFilter === option.id ? 'active' : ''} onClick={() => setEventFilter(option.id)}>
            <span>{option.id === 'selected' ? `${option.label} ${selectedSymbol}` : option.label}</span>
            <b>{eventFilterCounts[option.id]}</b>
          </button>
        ))}
      </div>
      <div className="edge-event-list">
        {visibleEvents.length === 0 ? (
          <div className="edge-event-empty">
            <span>No activity for this filter</span>
            <button type="button" onClick={() => setEventFilter('all')}>Show all activity</button>
          </div>
        ) : visibleEvents.map((event, index) => {
          const canFocusEvent = eventSymbols.has(event.symbol);
          return (
            <button key={event.id} type="button" disabled={!canFocusEvent} aria-label={canFocusEvent ? `Focus ${event.symbol} activity` : `${event.symbol} system activity`} className={`edge-event ${index === 0 ? 'active' : ''} ${canFocusEvent ? 'focusable' : 'system'}`} onClick={() => selectSymbol(event.symbol)}>
              <div><strong>{event.title}</strong>{event.detail}</div>
              <div><span className="edge-gold">{event.symbol}</span><br /><span>{event.time}</span></div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Extract `TickerPicker.tsx`**

Create a module with this interface:

```ts
import React from 'react';
import type { Ticker } from '../types';
import { PanelTitle } from './shared';

export function TickerPicker({
  selectedSymbol,
  pickerItems,
  onWheel,
  onKeyDown,
  selectSymbol,
}: {
  selectedSymbol: string;
  pickerItems: Ticker[];
  onWheel: (event: React.WheelEvent<HTMLDivElement>) => void;
  onKeyDown: (event: React.KeyboardEvent<HTMLDivElement>) => void;
  selectSymbol: (symbol: string) => void;
}) {
  return (
    <section className="edge-glass edge-picker-panel" aria-label="Kinetic watchlist">
      <PanelTitle eyebrow="Kinetic watchlist" title="Picker" chip="wheel / keys" />
      <div className="edge-ticker-picker" tabIndex={0} aria-label="Ticker picker: use mouse wheel or arrow keys" onWheel={onWheel} onKeyDown={onKeyDown}>
        {pickerItems.map((ticker, index) => {
          const active = ticker.symbol === selectedSymbol;
          return (
            <button type="button" key={`${ticker.symbol}-${index}`} className={`edge-picker-item ${active ? 'active' : ''}`} style={{ opacity: active ? 1 : Math.max(0.16, 0.75 - Math.abs(index - 3) * 0.18) }} aria-current={active ? 'true' : undefined} aria-label={active ? `${ticker.symbol} selected in ticker picker` : `Select ${ticker.symbol} in ticker picker`} onClick={() => selectSymbol(ticker.symbol)}>
              <b>{ticker.symbol}</b>
              {ticker.watchers[0] ? <em>{ticker.watchers[0].plugin}</em> : <span>{ticker.status}</span>}
              <span>{ticker.change}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Move remaining panels one at a time**

Move these functions into matching files and export them:

```ts
CommandModePanel
ModeTabs
MonitorPanel
ProtectionPanel
OperationsPanel
SettingsPanel
```

Keep their JSX initially unchanged except for imports. Do not redesign during this task.

- [ ] **Step 5: Replace inline JSX in `AssetCommandConsole.tsx`**

The main command grid should compose modules like this:

```tsx
<section className="edge-command-grid">
  <ActivityLog
    selectedSymbol={command.selected.symbol}
    events={command.events}
    visibleEvents={command.visibleEvents}
    eventFilter={command.eventFilter}
    eventFilterCounts={command.eventFilterCounts}
    setEventFilter={command.setEventFilter}
    selectSymbol={command.selectSymbol}
  />

  <section id={`edge-mode-panel-${mode}`} className="edge-glass edge-center" role="tabpanel" aria-label="Asset command center">
    {/* existing header and per-mode modules */}
  </section>

  <aside className="edge-right-stack">
    <TickerPicker
      selectedSymbol={command.selected.symbol}
      pickerItems={command.pickerItems}
      onWheel={command.handleWheel}
      onKeyDown={command.handlePickerKeyDown}
      selectSymbol={command.selectSymbol}
    />
    {/* existing command panel */}
  </aside>
</section>
```

- [ ] **Step 6: Run verification after each extracted module**

After each module move, run:

```powershell
npm run build
```

After all modules are moved, run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
npm run build
```

Expected: tests and build pass.

- [ ] **Step 7: Commit presentational extraction**

```powershell
git add frontend/src/components/asset-command/components frontend/src/components/asset-command/AssetCommandConsole.tsx
git commit -m "refactor: split asset command panels into modules"
```

---

### Task 6: Split CSS By Owned Surface

**Files:**
- Create: `frontend/src/components/asset-command/AssetCommandConsole.activity.css`
- Create: `frontend/src/components/asset-command/AssetCommandConsole.picker.css`
- Create: `frontend/src/components/asset-command/AssetCommandConsole.panels.css`
- Modify: `frontend/src/components/asset-command/AssetCommandConsole.css`

- [ ] **Step 1: Add imports at the top of `AssetCommandConsole.css`**

```css
@import './AssetCommandConsole.activity.css';
@import './AssetCommandConsole.picker.css';
@import './AssetCommandConsole.panels.css';
```

- [ ] **Step 2: Move activity selectors**

Move these selectors and their media-query overrides to `AssetCommandConsole.activity.css`:

```css
.edge-events
.edge-event-filters
.edge-event-filters button
.edge-event-filters button b
.edge-event-filters button:hover
.edge-event-filters button:focus-visible
.edge-event-filters button.active
.edge-event-list
.edge-event-empty
.edge-event-empty span
.edge-event-empty button
.edge-event-empty button:hover
.edge-event-empty button:focus-visible
.edge-event
.edge-event.focusable:hover
.edge-event.focusable:focus-visible
.edge-event.system
.edge-event strong
```

- [ ] **Step 3: Move picker selectors**

Move these selectors and their media-query overrides to `AssetCommandConsole.picker.css`:

```css
.edge-right-stack
.edge-picker-panel
.edge-ticker-picker
.edge-ticker-picker:focus-visible
.edge-picker-item
.edge-picker-item.active
.edge-picker-item em
```

- [ ] **Step 4: Move panel selectors**

Move command, monitor, protect, operations, and settings selectors that are not global shell/layout selectors to `AssetCommandConsole.panels.css`. Keep these shell selectors in `AssetCommandConsole.css`:

```css
.edge-console
.edge-frame
.edge-glass
.edge-top-nav
.edge-brand
.edge-brand-mark
.edge-mode-switch
.edge-clock
.edge-status-strip
.edge-primary-metric
.edge-status-metric
.edge-command-grid
.edge-center
.edge-command-header
.edge-chip
.edge-gold
.edge-green
.edge-cyan
.edge-red
.edge-tone-green
.edge-tone-cyan
.edge-tone-gold
.edge-tone-red
```

- [ ] **Step 5: Run CSS regression checks**

Run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
npm run build
```

Expected: tests and build pass.

- [ ] **Step 6: Commit CSS split**

```powershell
git add frontend/src/components/asset-command/*.css backend/tests/test_asset_command_ui_static.py
git commit -m "refactor: split asset command styles by surface"
```

---

### Task 7: Final Cleanup And Verification

**Files:**
- Modify only files touched by earlier tasks if cleanup is needed.

- [ ] **Step 1: Check the app-root adapter for size and responsibility**

Run:

```powershell
(Get-Content frontend/src/components/asset-command/AssetCommandConsole.tsx).Count
```

Expected: below 350 lines. If it is still above 350 lines, identify the largest remaining inline rendering block and extract it before continuing.

- [ ] **Step 2: Check imports for unused leftovers**

Run:

```powershell
npm run build
```

Expected: TypeScript catches no unused imports that are configured as errors and the Vite build completes.

- [ ] **Step 3: Run final static UI regressions**

Run:

```powershell
python -m unittest backend.tests.test_asset_command_ui_static
```

Expected: all tests pass.

- [ ] **Step 4: Inspect final diff**

Run:

```powershell
git diff --stat
git status --short
```

Expected:

- New asset-command modules are listed.
- `AssetCommandConsole.tsx` is much smaller.
- No unrelated files are changed.

- [ ] **Step 5: Commit final cleanup if needed**

```powershell
git add frontend/src/components/asset-command backend/tests/test_asset_command_ui_static.py
git commit -m "refactor: finish asset command console module split"
```

---

## Self-Review

- Spec coverage: The plan covers the identified high-leverage module: Asset Command Console. It addresses data/types, behavior hooks, presentational modules, CSS ownership, and tests.
- Placeholder scan: No task relies on unspecified future behavior. Each task names files, commands, expected outcomes, and either exact snippets or explicit move-only instructions.
- Type consistency: Shared types originate in `types.ts`; data imports types from `types.ts`; hooks import data/types; presentational modules import types/data/shared modules; the app-root adapter composes hooks and presentational modules.
- Risk note: Existing static tests use source-string assertions, so Task 1 intentionally makes them module-aware before production code moves.
