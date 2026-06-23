# Market Map Grafana Parking Lot

## Status

Parked. These ideas are intentionally not part of the active Market Map implementation unless they are explicitly revived later.

Market Map should remain the main operator chart and context surface. Grafana should be treated as an optional evidence and telemetry layer, not as a replacement for Sentinel Edge's charting UI.

## Why This Exists

Grafana may be useful for operational proof, system health, and historical telemetry around Market Map decisions. It may also be unnecessary visual weight inside the main trading cockpit. This note preserves the integration design so the idea can be resumed without re-discovering the repo shape.

## Recommended Future Approach

Start with Grafana deep links and annotations before iframe embeds.

Deep links are safer because they avoid Grafana authentication, cookie, CORS, and frame policy problems. Iframe embeds can be added later only if local Grafana configuration supports it cleanly.

## Existing Dashboards To Reuse

- `grafana/dashboards/market-breadth.json`
- `grafana/dashboards/correlation-breadth.json`
- `grafana/dashboards/options-gex-vex-gamma.json`
- `grafana/dashboards/options-greeks-analysis.json`
- `grafana/dashboards/signal-quality.json`
- `grafana/dashboards/broker_health.json`
- `grafana/dashboards/frontend-experience.json`
- `grafana/dashboards/sentinel-mission-control.json`
- `grafana/dashboards/sentinel-the-brain.json`
- `grafana/dashboards/sentinel-performance-lab.json`
- `grafana/dashboards/risk-ops.json`
- `grafana/dashboards/trading_overview.json`

## Future File Layout

Backend:

- `backend/grafana_links.py`
  - Builds Grafana dashboard and panel URLs from symbol, timestamp, time window, and dashboard variables.
  - Keeps dashboard IDs, slugs, panel IDs, and variable names out of route handlers.

- `backend/market_map_grafana.py`
  - Optional route helpers for Market Map Grafana evidence.
  - Returns read-only links and embed metadata.
  - Should not block Market Map if Grafana is unavailable.

- `backend/grafana_annotations.py`
  - Optional adapter for sending alert, level, decision, order, and reconciliation annotations to Grafana.
  - Must fail soft and log warnings only.

- `backend/tests/test_grafana_links.py`
  - Verifies URL generation, symbol variables, and time-window query parameters.

- `backend/tests/test_market_map_grafana_contract.py`
  - Verifies the API response shape for the frontend evidence panel.

Frontend:

- `frontend/src/components/market-map/GrafanaEvidenceDrawer.tsx`
  - Collapsible drawer for Grafana evidence.
  - Shows dashboard links first.
  - Supports embedded panels only when explicitly enabled.

- `frontend/src/components/market-map/GrafanaHealthStrip.tsx`
  - Compact status row under the chart.
  - Shows bridge, source, parser, broker, market data, and UI health.

- `frontend/src/components/market-map/GrafanaPanelLink.tsx`
  - Small reusable link card for one Grafana dashboard or panel.

- `frontend/src/hooks/useMarketMapGrafanaLinks.ts`
  - Fetches Grafana links for selected symbol and chart time window.

- `frontend/src/types/marketMapGrafana.ts`
  - Shared frontend types for Grafana evidence responses.

- `frontend/src/components/market-map/__tests__/GrafanaEvidenceDrawer.test.tsx`
  - Verifies links render, unavailable Grafana is explicit, and iframe mode is opt-in.

Config and docs:

- `config/grafana.market-map.example.json`
  - Maps friendly dashboard names to Grafana dashboard UIDs, panel IDs, and variables.

- `docs/market-map-grafana-evidence.md`
  - Operator-facing explanation of how Market Map links to Grafana proof.

## API Shape

Potential endpoint:

```text
GET /api/market-map/grafana-links?symbol=SPY&from=2026-06-22T14:20:00Z&to=2026-06-22T14:35:00Z
```

Potential response:

```json
{
  "enabled": true,
  "symbol": "SPY",
  "from": "2026-06-22T14:20:00Z",
  "to": "2026-06-22T14:35:00Z",
  "dashboards": [
    {
      "id": "market-breadth",
      "label": "Market Breadth",
      "url": "http://localhost:3000/d/market-breadth?...",
      "embedUrl": null,
      "category": "market"
    }
  ],
  "warnings": []
}
```

## Integration Ideas

### Evidence Drawer

Add a collapsible `Evidence` drawer inside Market Map. When a symbol is selected, the drawer shows Grafana links for market breadth, signal quality, bridge health, broker health, frontend health, options positioning, and mission control.

### Alert Time Sync

When the operator clicks an alert marker, Market Map can request Grafana links scoped to a small time window around the alert. Example: 5 minutes before and 10 minutes after the alert.

This helps prove whether Discord ingestion, bridge telemetry, parser state, data freshness, broker health, and UI state were healthy at the moment the alert arrived.

### Grafana Annotations

Market Map or backend services can emit Grafana annotations for:

- morning support/resistance levels calculated
- alert observed
- parse accepted or rejected
- decision accepted, blocked, or marked review
- order submitted
- fill received
- trailing stop updated
- position closed
- reconciliation passed or failed

Annotations should be optional. A Grafana failure must never break alert handling, chart rendering, or trading safety.

### Morning Brief Links

Market Map's Morning Plan preset can include a small Grafana brief section with links to:

- market breadth
- correlation breadth
- options gamma/GEX/VEX
- mission control
- signal quality

This should remain link-based unless embedded panels add clear operator value.

### Health Strip

Add a telemetry strip under the Market Map chart:

- Bridge: healthy, stale, down
- Discord source: connected, stale, unauthorized
- Parser: accepting, rejecting, degraded
- Broker: paper, live-disabled, unavailable
- Market data: fresh, delayed, stale
- UI telemetry: healthy, degraded

Each item can link to the matching Grafana panel.

### Replay Proof Bundle

For replay and beta-test evidence, Market Map can export or display a proof bundle containing:

- selected symbol and chart time range
- alert-chain row
- decision proof
- broker/order reconciliation proof
- Grafana dashboard links for the same time range

## Safety Rules

- Grafana integration must be read-only from Market Map.
- Grafana must never arm live trading.
- Grafana must never submit orders.
- Grafana availability must not be required for core Market Map rendering.
- Missing Grafana configuration should produce explicit disabled UI, not hidden failures.
- Embedded panel mode must be opt-in.
- Annotation posting must fail soft.

## When To Revive This

Revive this after Market Map can already show:

1. deterministic support/resistance levels
2. candlestick and line charts
3. alert markers
4. decision proof
5. broker/order reconciliation proof

Grafana is most valuable after those core proof objects exist. Before then, it risks becoming dashboard decoration instead of useful evidence.
