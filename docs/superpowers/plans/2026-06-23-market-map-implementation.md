# Market Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Sentinel Edge's Market Map as an evolution of the existing Chart Workspace so the operator can inspect candles, levels, indicators, alert proof, Edge context, and options quality without creating a broker-order surface.

**Architecture:** Keep the existing `ChartWorkspace` component and `/api/chart-workspace/{symbol}` endpoint as the compatibility foundation. Add Market Map language, deterministic server-side level calculations, read-only proof/context endpoints, and focused frontend panels that consume typed payloads.

**Tech Stack:** Python FastAPI backend, unittest static and behavior tests, React/TypeScript frontend, Plotly chart traces, Tailwind utility classes, existing `api.ts` client.

---

## File Structure

- Modify `backend/chart_workspace.py`: add Market Map levels, VWAP, ATR bands, indicator support, marker/context payload helpers, and stable schemas.
- Modify `backend/server.py`: keep `/api/chart-workspace/{symbol}` and add read-only `/api/market-map/context` and `/api/market-map/proof-markers/{symbol}` endpoints.
- Modify `backend/tests/test_chart_workspace.py`: cover levels, VWAP, ATR, and schema shape.
- Modify `backend/tests/test_chart_workspace_static.py`: update static expectations from Chart Workspace to Market Map while preserving compatibility names.
- Create `backend/tests/test_market_map_context.py`: behavior tests for deterministic pass/review/block market context.
- Modify `frontend/src/types/index.ts`: extend chart snapshot types with levels, markers, Edge context, and option context.
- Modify `frontend/src/lib/api.ts`: add Market Map API client methods and widened indicator ID type usage.
- Modify `frontend/src/components/asset-command/data.ts`: relabel the Operations navigation item to `Market Map`.
- Modify `frontend/src/components/asset-command/components/OperationsPanel.tsx`: keep `ChartWorkspace` import and render path, only user-facing label changes through data.
- Modify `frontend/src/components/dashboards/ChartWorkspace.tsx`: add Market Map presets, level overlays, level table, Edge confidence panel, proof markers, and options cockpit while preserving the component export.
- Modify `README.md`: document Market Map endpoint compatibility, support/resistance payload, presets, proof markers, and safety boundaries.

---

### Task 1: Market Map Shell And Presets

**Files:**
- Modify: `frontend/src/components/asset-command/data.ts`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
- Modify: `backend/tests/test_chart_workspace_static.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing static test**

Add assertions in `backend/tests/test_chart_workspace_static.py`:

```python
def test_operations_deck_exposes_market_map_tab(self):
    data = ASSET_DATA.read_text(encoding="utf-8")
    dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

    self.assertIn("{ id: 'charts', label: 'Market Map'", data)
    self.assertIn("Market Map", dashboard)
    self.assertIn("MarketMapLayoutPreset", dashboard)
    self.assertIn("Morning Plan", dashboard)
    self.assertIn("Intraday Alerts", dashboard)
    self.assertIn("Replay Proof", dashboard)
    self.assertIn("sentinel-edge.market-map.layout.v1", dashboard)
    self.assertIn("sentinel-edge.market-map.preferences.v1", dashboard)
```

- [ ] **Step 2: Run the focused failing tests**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static
```

Expected: fail because Market Map labels and presets are not present yet.

- [ ] **Step 3: Relabel the Operations navigation**

Change `frontend/src/components/asset-command/data.ts`:

```ts
{ id: 'charts', label: 'Market Map', icon: LineChart },
```

- [ ] **Step 4: Add Market Map layout preset state**

In `frontend/src/components/dashboards/ChartWorkspace.tsx`, introduce:

```ts
type MarketMapLayoutPreset = 'morning_plan' | 'intraday_alerts' | 'replay_proof';

const MARKET_MAP_LAYOUT_STORAGE_KEY = 'sentinel-edge.market-map.layout.v1';
const MARKET_MAP_PREFERENCES_STORAGE_KEY = 'sentinel-edge.market-map.preferences.v1';

const MARKET_MAP_LAYOUT_PRESETS: {
  id: MarketMapLayoutPreset;
  label: string;
  detail: string;
  layoutMode: ChartWorkspaceLayoutMode;
  panelVisibility: ChartWorkspacePanelVisibility;
}[] = [
  {
    id: 'morning_plan',
    label: 'Morning Plan',
    detail: 'Levels, VWAP, trend, and watched tickers before the session.',
    layoutMode: 'analysis',
    panelVisibility: { snapshot: true, strategy: true, lab: false, oscillators: true },
  },
  {
    id: 'intraday_alerts',
    label: 'Intraday Alerts',
    detail: 'Live alert context, Edge confidence, and options quality.',
    layoutMode: 'execution',
    panelVisibility: { snapshot: true, strategy: true, lab: false, oscillators: true },
  },
  {
    id: 'replay_proof',
    label: 'Replay Proof',
    detail: 'Alert-chain proof, chart markers, and reconciliation evidence.',
    layoutMode: 'research',
    panelVisibility: { snapshot: true, strategy: true, lab: true, oscillators: true },
  },
];
```

Replace the old storage keys with the new Market Map keys while reading old keys as fallback inside the storage readers so existing operator preferences are preserved.

- [ ] **Step 5: Render the preset controls**

Add a preset segmented control near the chart header:

```tsx
<div className="flex flex-wrap items-center gap-2" aria-label="Market Map layout presets">
  {MARKET_MAP_LAYOUT_PRESETS.map((preset) => (
    <button
      key={preset.id}
      type="button"
      className={activeMarketMapPreset === preset.id ? activeToolClass : inactiveToolClass}
      onClick={() => applyMarketMapPreset(preset.id)}
      title={preset.detail}
    >
      {preset.label}
    </button>
  ))}
</div>
```

- [ ] **Step 6: Update README language**

Add a short Market Map section to `README.md`:

```md
### Market Map

The Operations deck exposes Market Map as the operator chart cockpit. It keeps the legacy `/api/chart-workspace/{symbol}` compatibility endpoint while adding Market Map presets for Morning Plan, Intraday Alerts, and Replay Proof. Market Map is read-only for broker activity and does not arm or submit live trades.
```

- [ ] **Step 7: Run tests and commit**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static
```

Expected: pass.

Commit:

```powershell
git add frontend/src/components/asset-command/data.ts frontend/src/components/dashboards/ChartWorkspace.tsx backend/tests/test_chart_workspace_static.py README.md
git commit -m "Add Market Map shell and presets"
```

---

### Task 2: Deterministic Levels, VWAP, And ATR Bands

**Files:**
- Modify: `backend/chart_workspace.py`
- Modify: `backend/tests/test_chart_workspace.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `backend/tests/test_chart_workspace_static.py`

- [ ] **Step 1: Write the failing backend behavior test**

Add to `backend/tests/test_chart_workspace.py`:

```python
def test_payload_adds_market_map_levels_vwap_and_atr_bands(self):
    result = build_chart_workspace_payload(
        symbol="SPY",
        bars=[
            {"timestamp": "2026-06-09T08:00:00-04:00", "open": 100, "high": 101, "low": 99, "close": 100, "volume": 100},
            {"timestamp": "2026-06-09T09:30:00-04:00", "open": 100, "high": 104, "low": 99, "close": 103, "volume": 200},
            {"timestamp": "2026-06-09T09:31:00-04:00", "open": 103, "high": 105, "low": 102, "close": 104, "volume": 300},
            {"timestamp": "2026-06-09T09:32:00-04:00", "open": 104, "high": 106, "low": 103, "close": 105, "volume": 400},
        ],
        indicators=["vwap", "atr_3"],
        limit=4,
    )

    self.assertEqual(result["levels"]["schema_version"], "edge.market_map.levels.v1")
    kinds = {level["kind"] for level in result["levels"]["items"]}
    self.assertIn("session_high", kinds)
    self.assertIn("session_low", kinds)
    self.assertIn("premarket_high", kinds)
    self.assertIn("premarket_low", kinds)
    self.assertIn("vwap", kinds)
    self.assertIn("atr_upper", kinds)
    self.assertIn("atr_lower", kinds)
    self.assertEqual(result["indicators"]["vwap"]["label"], "VWAP")
    self.assertEqual(result["indicators"]["atr_3"]["label"], "ATR 3")
```

- [ ] **Step 2: Run the focused failing test**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace.ChartWorkspacePayloadTests.test_payload_adds_market_map_levels_vwap_and_atr_bands
```

Expected: fail because `vwap`, `atr_3`, and `levels` are not implemented.

- [ ] **Step 3: Extend indicator normalization and payloads**

In `backend/chart_workspace.py`, update `DEFAULT_INDICATORS`:

```python
DEFAULT_INDICATORS = ("ema_9", "ema_20", "sma_20", "rsi_14", "macd")
```

Keep defaults stable, then allow explicit `vwap` and `atr_N` in `_normalise_indicators`:

```python
if indicator_id == "vwap":
    if indicator_id not in normalised:
        normalised.append(indicator_id)
    continue
if indicator_id.startswith("atr_"):
    _indicator_period(indicator_id, "atr")
    if indicator_id not in normalised:
        normalised.append(indicator_id)
    continue
```

Add indicator payload branches:

```python
elif indicator_id == "vwap":
    payloads[indicator_id] = _single_value_indicator(
        label="VWAP",
        kind="overlay",
        timestamps=timestamps[start_index:],
        values=_vwap_series(bars)[start_index:],
    )
elif indicator_id.startswith("atr_"):
    period = _indicator_period(indicator_id, "atr")
    payloads[indicator_id] = _single_value_indicator(
        label=f"ATR {period}",
        kind="oscillator",
        timestamps=timestamps[start_index:],
        values=_atr_series(bars, period)[start_index:],
    )
```

Pass full normalized bars into `_indicator_payloads` so VWAP and ATR can use high/low/close/volume.

- [ ] **Step 4: Add deterministic helper functions**

Add helpers in `backend/chart_workspace.py`:

```python
def _vwap_series(bars: Sequence[Dict[str, Any]]) -> List[float | None]:
    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    values: List[float | None] = []
    for bar in bars:
        volume = max(float(bar.get("volume") or 0.0), 0.0)
        typical_price = (bar["high"] + bar["low"] + bar["close"]) / 3
        cumulative_price_volume += typical_price * volume
        cumulative_volume += volume
        values.append(round(cumulative_price_volume / cumulative_volume, 4) if cumulative_volume > 0 else None)
    return values

def _true_range_series(bars: Sequence[Dict[str, Any]]) -> List[float]:
    ranges: List[float] = []
    previous_close: float | None = None
    for bar in bars:
        high = bar["high"]
        low = bar["low"]
        if previous_close is None:
            ranges.append(high - low)
        else:
            ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
        previous_close = bar["close"]
    return [round(value, 4) for value in ranges]

def _atr_series(bars: Sequence[Dict[str, Any]], period: int) -> List[float | None]:
    true_ranges = _true_range_series(bars)
    series: List[float | None] = []
    for index, _ in enumerate(true_ranges):
        if index + 1 < period:
            series.append(None)
            continue
        window = true_ranges[index + 1 - period : index + 1]
        series.append(round(sum(window) / period, 4))
    return series
```

- [ ] **Step 5: Add level payload builder**

Add:

```python
def _market_map_levels(bars: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    latest = bars[-1]
    session_bars = [bar for bar in bars if _is_regular_session_bar(bar["timestamp"])] or list(bars)
    premarket_bars = [bar for bar in bars if _is_premarket_bar(bar["timestamp"])]
    vwap_values = _vwap_series(bars)
    atr_values = _atr_series(bars, min(14, max(2, len(bars))))
    latest_vwap = _latest_value(vwap_values)
    latest_atr = _latest_value(atr_values)
    items = [
        _level_item("session_high", "Session high", "session_high", max(bar["high"] for bar in session_bars), "ohlcv", "regular", latest["timestamp"], 0.9, False),
        _level_item("session_low", "Session low", "session_low", min(bar["low"] for bar in session_bars), "ohlcv", "regular", latest["timestamp"], 0.9, False),
    ]
    if premarket_bars:
        items.extend([
            _level_item("premarket_high", "Premarket high", "premarket_high", max(bar["high"] for bar in premarket_bars), "ohlcv", "premarket", latest["timestamp"], 0.8, True),
            _level_item("premarket_low", "Premarket low", "premarket_low", min(bar["low"] for bar in premarket_bars), "ohlcv", "premarket", latest["timestamp"], 0.8, True),
        ])
    if latest_vwap is not None:
        items.append(_level_item("vwap", "VWAP", "vwap", latest_vwap, "computed", "session", latest["timestamp"], 0.85, False))
    if latest_atr is not None:
        items.append(_level_item("atr_upper", "ATR upper", "atr_upper", latest["close"] + latest_atr, "computed", "session", latest["timestamp"], 0.7, False))
        items.append(_level_item("atr_lower", "ATR lower", "atr_lower", latest["close"] - latest_atr, "computed", "session", latest["timestamp"], 0.7, False))
    return {"schema_version": "edge.market_map.levels.v1", "items": items}
```

Also add `_level_item`, `_is_regular_session_bar`, `_is_premarket_bar`, and `_latest_value` helpers.

- [ ] **Step 6: Add levels to the snapshot**

In `build_chart_workspace_payload`, include:

```python
"levels": _market_map_levels(normalised_bars),
```

- [ ] **Step 7: Update frontend types**

In `frontend/src/types/index.ts`, extend:

```ts
export type ChartWorkspaceIndicatorId = 'ema_9' | 'ema_20' | 'sma_20' | 'sma_50' | 'sma_200' | 'rsi_14' | 'macd' | 'vwap' | 'atr_14';

export interface MarketMapLevel {
  id: string;
  label: string;
  kind: string;
  price: number;
  source: string;
  session: string;
  confidence: number;
  timestamp: string;
  locked: boolean;
}

export interface MarketMapLevelsPayload {
  schema_version: string;
  items: MarketMapLevel[];
}

export interface ChartWorkspaceSnapshot {
  levels?: MarketMapLevelsPayload;
}
```

Merge the new property into the existing `ChartWorkspaceSnapshot` interface, not as a second duplicate interface.

- [ ] **Step 8: Run tests and commit**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace backend.tests.test_chart_workspace_static
```

Expected: pass.

Commit:

```powershell
git add backend/chart_workspace.py backend/tests/test_chart_workspace.py backend/tests/test_chart_workspace_static.py frontend/src/types/index.ts
git commit -m "Add Market Map levels and indicators"
```

---

### Task 3: Level Overlays And Briefing Panel

**Files:**
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
- Modify: `backend/tests/test_chart_workspace_static.py`
- Modify: `README.md`

- [ ] **Step 1: Write the failing static test**

Add to `backend/tests/test_chart_workspace_static.py`:

```python
def test_market_map_renders_levels_and_briefing_panel(self):
    dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")
    text = README.read_text(encoding="utf-8")

    self.assertIn("buildMarketMapLevelTraces", dashboard)
    self.assertIn("Market Map Briefing", dashboard)
    self.assertIn("Morning Levels", dashboard)
    self.assertIn("Level proximity", dashboard)
    self.assertIn("formatMarketMapLevelPrice", dashboard)
    self.assertIn("snapshot?.levels?.items", dashboard)
    self.assertIn("support/resistance levels", text)
```

- [ ] **Step 2: Run the focused failing test**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static.ChartWorkspaceStaticTests.test_market_map_renders_levels_and_briefing_panel
```

Expected: fail because the UI does not render Market Map levels yet.

- [ ] **Step 3: Add level traces to the chart**

In `ChartWorkspace.tsx`, update `buildPriceTraces` to append:

```ts
...buildMarketMapLevelTraces(snapshot),
```

Add:

```ts
function buildMarketMapLevelTraces(snapshot: ChartWorkspaceSnapshot | null) {
  const bars = snapshot?.bars ?? [];
  const levels = snapshot?.levels?.items ?? [];
  if (!bars.length || !levels.length) return [];
  const x = [bars[0].timestamp, bars[bars.length - 1].timestamp];
  return levels
    .filter((level) => Number.isFinite(level.price))
    .map((level) => ({
      x,
      y: [level.price, level.price],
      type: 'scatter',
      mode: 'lines',
      name: level.label,
      line: {
        color: marketMapLevelColor(level.kind),
        dash: level.locked ? 'solid' : 'dot',
        width: 1.25,
      },
      hovertemplate: `${level.label}: $${level.price.toFixed(2)}<extra></extra>`,
    }));
}
```

- [ ] **Step 4: Add briefing and levels panel**

Inside side panels, add:

```tsx
<section className={panelClass}>
  <div className="mb-3 text-sm font-semibold text-white">Market Map Briefing</div>
  <div className="grid grid-cols-2 gap-2 text-sm">
    <Metric label="Bias" value={buildMarketMapBias(snapshot)} />
    <Metric label="Level proximity" value={formatNearestMarketMapLevel(snapshot)} />
  </div>
  <div className="mt-3 text-[11px] font-semibold uppercase text-slate-500">Morning Levels</div>
  <div className="mt-2 space-y-1">
    {(snapshot?.levels?.items ?? []).slice(0, 8).map((level) => (
      <div key={level.id} className="flex items-center justify-between gap-2 border-t border-slate-800/80 pt-1 first:border-t-0">
        <span className="truncate text-slate-300">{level.label}</span>
        <span className="shrink-0 font-mono text-slate-100">{formatMarketMapLevelPrice(level.price)}</span>
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 5: Add formatting helpers**

Add:

```ts
function formatMarketMapLevelPrice(value: number) {
  return Number.isFinite(value) ? `$${value.toFixed(2)}` : '--';
}

function buildMarketMapBias(snapshot: ChartWorkspaceSnapshot | null) {
  const latest = snapshot?.bars?.[snapshot.bars.length - 1];
  const vwap = snapshot?.levels?.items?.find((level) => level.kind === 'vwap');
  if (!latest || !vwap) return 'Review';
  if (latest.close > vwap.price) return 'Above VWAP';
  if (latest.close < vwap.price) return 'Below VWAP';
  return 'At VWAP';
}

function formatNearestMarketMapLevel(snapshot: ChartWorkspaceSnapshot | null) {
  const latest = snapshot?.bars?.[snapshot.bars.length - 1];
  const levels = snapshot?.levels?.items ?? [];
  if (!latest || !levels.length) return '--';
  const nearest = levels.reduce((best, level) => {
    const distance = Math.abs(level.price - latest.close);
    return distance < best.distance ? { level, distance } : best;
  }, { level: levels[0], distance: Math.abs(levels[0].price - latest.close) });
  return `${nearest.level.label} ${formatMarketMapLevelPrice(nearest.level.price)}`;
}
```

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static
```

Expected: pass.

Commit:

```powershell
git add frontend/src/components/dashboards/ChartWorkspace.tsx backend/tests/test_chart_workspace_static.py README.md
git commit -m "Render Market Map levels"
```

---

### Task 4: Alert Proof Markers

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/tests/test_chart_workspace_static.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`

- [ ] **Step 1: Write static contract tests**

Add:

```python
def test_market_map_exposes_proof_marker_endpoint_and_ui(self):
    server = SERVER.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    types = TYPES.read_text(encoding="utf-8")
    dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")

    self.assertIn('@api_router.get("/market-map/proof-markers/{symbol}")', server)
    self.assertIn("async getMarketMapProofMarkers", api)
    self.assertIn("export interface MarketMapProofMarker", types)
    self.assertIn("buildMarketMapProofMarkerTraces", dashboard)
    self.assertIn("Alert Proof", dashboard)
    self.assertIn("parser confidence", dashboard)
```

- [ ] **Step 2: Run the focused failing test**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static.ChartWorkspaceStaticTests.test_market_map_exposes_proof_marker_endpoint_and_ui
```

Expected: fail because the endpoint/client/types/UI are absent.

- [ ] **Step 3: Add backend endpoint**

In `backend/server.py`, add a read-only endpoint:

```python
@api_router.get("/market-map/proof-markers/{symbol}")
async def get_market_map_proof_markers(symbol: str, limit: int = 100):
    requested_symbol = symbol.strip().upper()
    events = []
    try:
        from shared.bot_event_bus import event_bus
        events = event_bus.recent(limit=max(1, min(int(limit), 500)))
    except Exception:
        events = []
    markers = []
    for event in events:
        payload = event.payload if hasattr(event, "payload") else event.get("payload", {})
        event_symbol = str(payload.get("symbol") or payload.get("ticker") or "").upper()
        if event_symbol and event_symbol != requested_symbol:
            continue
        markers.append({
            "id": str(getattr(event, "event_id", "") or payload.get("event_id") or payload.get("id") or len(markers) + 1),
            "symbol": requested_symbol,
            "timestamp": str(payload.get("timestamp") or payload.get("received_at") or getattr(event, "created_at", "")),
            "kind": str(payload.get("kind") or payload.get("event_type") or getattr(event, "event_type", "event")),
            "label": str(payload.get("label") or payload.get("decision") or payload.get("kind") or "Event"),
            "status": str(payload.get("status") or "review"),
            "parser_confidence": payload.get("parser_confidence"),
            "raw_text": payload.get("raw_text"),
            "proof": payload,
        })
    return {"schema_version": "edge.market_map.proof_markers.v1", "symbol": requested_symbol, "items": markers}
```

- [ ] **Step 4: Add frontend types and API method**

In `frontend/src/types/index.ts`:

```ts
export interface MarketMapProofMarker {
  id: string;
  symbol: string;
  timestamp: string;
  kind: string;
  label: string;
  status: string;
  parser_confidence?: number | null;
  raw_text?: string | null;
  proof?: Record<string, unknown>;
}

export interface MarketMapProofMarkersPayload {
  schema_version: string;
  symbol: string;
  items: MarketMapProofMarker[];
}
```

In `frontend/src/lib/api.ts`:

```ts
async getMarketMapProofMarkers(symbol: string, limit = 100) {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJSON<MarketMapProofMarkersPayload>(`/api/market-map/proof-markers/${encodeURIComponent(symbol)}?${params}`);
}
```

- [ ] **Step 5: Render markers and proof panel**

In `ChartWorkspace.tsx`, load markers when `activeSymbol` changes. Add trace builder:

```ts
function buildMarketMapProofMarkerTraces(markers: MarketMapProofMarker[]) {
  return markers
    .filter((marker) => marker.timestamp)
    .map((marker) => ({
      x: [marker.timestamp],
      y: [0],
      yaxis: 'y',
      type: 'scatter',
      mode: 'markers+text',
      name: marker.label,
      text: [marker.kind],
      marker: { size: 10, color: marker.status === 'accepted' ? '#22c55e' : '#f59e0b' },
    }));
}
```

Add an `Alert Proof` panel listing marker label, status, parser confidence, and raw text if present.

- [ ] **Step 6: Run tests and commit**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static
```

Expected: pass.

Commit:

```powershell
git add backend/server.py backend/tests/test_chart_workspace_static.py frontend/src/types/index.ts frontend/src/lib/api.ts frontend/src/components/dashboards/ChartWorkspace.tsx
git commit -m "Add Market Map proof markers"
```

---

### Task 5: Edge Context Scoring API

**Files:**
- Modify: `backend/chart_workspace.py`
- Modify: `backend/server.py`
- Create: `backend/tests/test_market_map_context.py`
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`

- [ ] **Step 1: Write backend behavior tests**

Create `backend/tests/test_market_map_context.py`:

```python
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chart_workspace import build_market_map_context


class MarketMapContextTests(unittest.TestCase):
    def test_context_blocks_when_levels_are_missing(self):
        result = build_market_map_context(symbol="SPY", latest_price=100.0, levels=[])

        self.assertEqual(result["schema_version"], "edge.market_map.context.v1")
        self.assertEqual(result["status"], "block")
        self.assertIn("No Market Map levels available", result["reasons"])

    def test_context_reviews_when_price_is_far_from_vwap(self):
        result = build_market_map_context(
            symbol="SPY",
            latest_price=110.0,
            levels=[{"kind": "vwap", "label": "VWAP", "price": 100.0}],
        )

        self.assertEqual(result["status"], "review")
        self.assertIn("Price is extended from VWAP", result["reasons"])

    def test_context_accepts_when_price_is_near_vwap(self):
        result = build_market_map_context(
            symbol="SPY",
            latest_price=100.25,
            levels=[{"kind": "vwap", "label": "VWAP", "price": 100.0}],
        )

        self.assertEqual(result["status"], "pass")
        self.assertIn("Price is near VWAP", result["reasons"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m unittest backend.tests.test_market_map_context
```

Expected: fail because `build_market_map_context` is absent.

- [ ] **Step 3: Add deterministic context helper**

In `backend/chart_workspace.py`:

```python
def build_market_map_context(*, symbol: str, latest_price: float | None, levels: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    normalized_symbol = symbol.strip().upper()
    reasons: List[str] = []
    warnings: List[str] = []
    if latest_price is None or not isfinite(float(latest_price)):
        return {
            "schema_version": "edge.market_map.context.v1",
            "symbol": normalized_symbol,
            "status": "block",
            "score": 0,
            "directional_bias": "unknown",
            "trend_state": "unknown",
            "momentum_state": "unknown",
            "volatility_state": "unknown",
            "level_proximity": None,
            "reasons": ["Latest price unavailable"],
            "warnings": [],
        }
    if not levels:
        return {
            "schema_version": "edge.market_map.context.v1",
            "symbol": normalized_symbol,
            "status": "block",
            "score": 0,
            "directional_bias": "unknown",
            "trend_state": "unknown",
            "momentum_state": "unknown",
            "volatility_state": "unknown",
            "level_proximity": None,
            "reasons": ["No Market Map levels available"],
            "warnings": [],
        }
    vwap = next((level for level in levels if level.get("kind") == "vwap"), None)
    nearest = min(levels, key=lambda level: abs(float(level.get("price", latest_price)) - float(latest_price)))
    distance_pct = abs(float(nearest.get("price", latest_price)) - float(latest_price)) / max(float(latest_price), 0.01)
    if vwap:
        vwap_distance_pct = abs(float(vwap.get("price", latest_price)) - float(latest_price)) / max(float(latest_price), 0.01)
        if vwap_distance_pct <= 0.005:
            status = "pass"
            score = 82
            reasons.append("Price is near VWAP")
        elif vwap_distance_pct <= 0.015:
            status = "review"
            score = 58
            reasons.append("Price is moderately away from VWAP")
        else:
            status = "review"
            score = 42
            reasons.append("Price is extended from VWAP")
    else:
        status = "review"
        score = 50
        reasons.append("VWAP level unavailable")
        warnings.append("VWAP is missing from Market Map levels")
    return {
        "schema_version": "edge.market_map.context.v1",
        "symbol": normalized_symbol,
        "status": status,
        "score": score,
        "directional_bias": "above_vwap" if vwap and float(latest_price) >= float(vwap.get("price", latest_price)) else "below_vwap",
        "trend_state": "context_only",
        "momentum_state": "context_only",
        "volatility_state": "context_only",
        "level_proximity": {
            "id": nearest.get("id"),
            "label": nearest.get("label"),
            "price": nearest.get("price"),
            "distance_pct": round(distance_pct, 4),
        },
        "reasons": reasons,
        "warnings": warnings,
    }
```

- [ ] **Step 4: Add read-only route and frontend rendering**

Add `/api/market-map/context/{symbol}` in `backend/server.py` that loads chart workspace payload and passes latest price plus levels to `build_market_map_context`.

Add frontend types and an API method:

```ts
async getMarketMapContext(symbol: string) {
  return fetchJSON<MarketMapContext>(`/api/market-map/context/${encodeURIComponent(symbol)}`);
}
```

Render an `Edge Confidence` panel showing status, score, level proximity, reasons, and warnings.

- [ ] **Step 5: Run tests and commit**

Run:

```powershell
python -m unittest backend.tests.test_market_map_context backend.tests.test_chart_workspace_static
```

Expected: pass.

Commit:

```powershell
git add backend/chart_workspace.py backend/server.py backend/tests/test_market_map_context.py frontend/src/types/index.ts frontend/src/lib/api.ts frontend/src/components/dashboards/ChartWorkspace.tsx
git commit -m "Add Market Map context scoring"
```

---

### Task 6: Options Cockpit And Safety Documentation

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/dashboards/ChartWorkspace.tsx`
- Modify: `backend/tests/test_chart_workspace_static.py`
- Modify: `README.md`

- [ ] **Step 1: Write static UI test**

Add:

```python
def test_market_map_options_cockpit_is_read_only(self):
    dashboard = CHART_DASHBOARD.read_text(encoding="utf-8")
    text = README.read_text(encoding="utf-8")

    self.assertIn("Options Cockpit", dashboard)
    self.assertIn("options market data unavailable", dashboard)
    self.assertIn("bid/ask spread", dashboard)
    self.assertIn("liquidity warning", dashboard)
    self.assertIn("Market Map never submits broker orders", text)
```

- [ ] **Step 2: Run failing test**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace_static.ChartWorkspaceStaticTests.test_market_map_options_cockpit_is_read_only
```

Expected: fail because the options cockpit is absent.

- [ ] **Step 3: Add read-only option context type**

In `frontend/src/types/index.ts`:

```ts
export interface MarketMapOptionContext {
  ticker: string;
  strike?: number | null;
  side?: 'CALL' | 'PUT' | string | null;
  expiration?: string | null;
  entry_price?: number | null;
  bid?: number | null;
  ask?: number | null;
  spread?: number | null;
  liquidity_warning?: string | null;
  delta_target?: number | null;
  status: 'available' | 'review' | 'unavailable' | string;
}
```

- [ ] **Step 4: Render options cockpit**

Add a read-only panel in `ChartWorkspace.tsx`:

```tsx
<section className={panelClass}>
  <div className="mb-3 text-sm font-semibold text-white">Options Cockpit</div>
  <div className="space-y-2 text-xs text-slate-300">
    <div className="rounded border border-amber-400/30 bg-amber-400/10 p-2 text-amber-100">
      options market data unavailable; contract context remains review-only
    </div>
    <Metric label="bid/ask spread" value="--" />
    <Metric label="liquidity warning" value="Market data required" />
    <Metric label="delta target" value="--" />
  </div>
</section>
```

- [ ] **Step 5: Document safety boundaries**

Add to `README.md`:

```md
Market Map never submits broker orders, never arms live trading, and treats missing chart, option, or proof data as review/block context instead of a silent default.
```

- [ ] **Step 6: Run final verification and commit**

Run:

```powershell
python -m unittest backend.tests.test_chart_workspace backend.tests.test_chart_workspace_static backend.tests.test_market_map_context
npm --prefix frontend run build
```

Expected: backend tests pass and frontend build completes.

Commit:

```powershell
git add frontend/src/types/index.ts frontend/src/components/dashboards/ChartWorkspace.tsx backend/tests/test_chart_workspace_static.py README.md
git commit -m "Add Market Map options cockpit"
```

---

## Self-Review

Spec coverage:

- Market Map shell and presets: Task 1.
- Morning support/resistance levels: Task 2 and Task 3.
- Indicator additions for VWAP and ATR: Task 2.
- Alert and trade markers: Task 4.
- Edge confidence panel and deterministic reasons: Task 5.
- Options cockpit: Task 6.
- Read-only safety rules: Task 5 and Task 6.

Gaps intentionally deferred:

- Full TradingView-style drawing tools remain excluded by the approved spec.
- Real broker order entry remains excluded by the approved spec.
- Grafana is parked in `docs/superpowers/specs/2026-06-23-market-map-grafana-parking-lot.md` and is not part of this implementation plan.

Placeholder scan:

- Tasks use concrete files, test commands, implementation snippets, and commit commands.
- No task relies on an unspecified future fill-in step.

Type consistency:

- `MarketMapLevel`, `MarketMapProofMarker`, `MarketMapContext`, and `MarketMapOptionContext` are separate frontend types.
- Existing `ChartWorkspace` export and `/api/chart-workspace/{symbol}` route remain compatible while user-facing language shifts to Market Map.
