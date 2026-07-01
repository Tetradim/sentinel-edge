# Advisory Charting Tab Design

## Status

Accepted design direction from the browser companion mock:

- Companion URL: `http://localhost:64047`
- Mock file: `.superpowers/brainstorm/codex-2588-20260629210914/content/charting-tab-advisory-revision-20260630.html`
- Accepted revision: advisory-only charting workspace with bot-scoped P&L calendar.

## Goal

Create a dedicated `Charting` tab for Sentinel Edge that makes the chart the primary workspace while keeping Sentinel Edge's role clear: it is an advisory and risk calculation system, not a brokerage or trade execution surface.

The tab should help the operator inspect breakouts, support and resistance, invalidation, risk state, bot directives, and outcome tracking for connected bots.

## Non-Goals

- Do not add buy, sell, order book, brokerage, account, or execution controls.
- Do not add a separate GEX/VEX top-level tab. GEX/VEX can appear later as a mini map or overlay inside Charting.
- Do not build backtesting in this tab. Strategy testing belongs to the separate Backtest Engine app.
- Do not allow floating configuration popups to cover the chart by default.

## Layout

The `Charting` tab uses a dense desktop trading-workspace layout:

1. Top app navigation includes `Charting` as a first-class mode.
2. Toolbar includes symbol, timeframe, period selector, indicators, drawings, risk overlays, templates, clean-chart toggle, pin config, save view, and export snapshot.
3. Left icon rail provides quick access to symbols, indicators, drawings, risk, mini maps, P&L, and configuration.
4. Left inspector is the default home for chart configuration and can collapse into the icon rail.
5. Center workspace contains the large chart and a compact lower signal/volume/invalidation strip.
6. Right analytics rail contains P&L and outcome modules and can collapse to give the chart more horizontal room.
7. Bottom dock contains current advisory directives, selected-period P&L trend, and clean-chart/menu behavior notes.

The default layout may show both side panels, but the operator must be able to collapse `Docked Chart Controls` and `Composition and outcome` independently. When both are collapsed, the chart becomes the dominant full-width surface while the left icon rail and compact toolbar remain available.

## Chart Workspace

The chart should prioritize wide visual inspection:

- Support, resistance, invalidation, and risk thresholds appear as chart overlays.
- A visible directive callout explains current advisory state, such as "support weakening" or "stop trading this setup if support closes below X."
- The lower strip shows pressure, volume, or invalidation context without becoming a heatmap module.
- A `Hide Overlays` control clears annotations and temporary overlays immediately for an unobstructed chart.

## Menus And Configuration

Indicator and chart-style controls should be docked, not chart-blocking:

- Default open location is the left inspector.
- The left inspector can collapse without losing access to its controls; reopening from the icon rail restores the docked panel.
- Users can pin or unpin config groups.
- Temporary menus close through Esc, click-away, or toolbar toggle.
- Chart style settings, indicator stack, risk thresholds, support levels, resistance levels, and bot directive settings live in inspector accordions.

## Advisory Actions

Language and actions must reflect Sentinel Edge's role:

- Allow
- Warn
- Block
- Stop trading this setup
- Support broken
- Resistance failed
- Risk corridor holding
- Breakout invalidated

The UI should not imply that Sentinel Edge places trades. It tells connected bots what is unsafe, invalid, or actionable from a risk perspective.

## Right Analytics Rail

The right rail replaces brokerage controls with advisory analytics:

- The rail can collapse independently so the main chart can expand horizontally.
- A compact reopen affordance should remain visible when collapsed.

1. Period selector:
   - Day
   - Week
   - Month
   - Custom range

2. P&L counter:
   - Shows selected-period P&L.
   - Preserves day, week, and month summary tiles.
   - Uses green/red sign and compact trade/call count details.

3. Win/loss composition:
   - Donut visualization with win rate.
   - Shows wins, losses, average win, and average loss.

4. Bot P&L calendar:
   - Replaces the earlier bubble composition map.
   - Includes a bot selector with at least:
     - Sentinel Pulse
     - Discord Trading Bot
     - All connected bots
   - Calendar cells are green for profitable days, red for losing days, and dim for inactive days.
   - Each active cell shows daily P&L and bot call count.
   - Weekly total chips summarize each week.
   - Summary tiles update for the selected bot.

## Data Model Needs

The first implementation can use static local data, but structure it so real data can replace it later:

- Bot registry:
  - `id`
  - `label`
  - `status`

- Bot P&L calendar entry:
  - `botId`
  - `date`
  - `pnl`
  - `callCount`
  - `winRate`
  - `state`: `win`, `loss`, or `inactive`

- Advisory directive:
  - `symbol`
  - `message`
  - `severity`
  - `action`

- Period selection:
  - `day`
  - `week`
  - `month`
  - `custom`
  - optional `startDate` and `endDate`

## Implementation Shape

Expected production implementation:

- Add a `charting` mode to the existing `Mode` union and mode list.
- Add a `ChartingPanel` component rather than folding this into `MonitorPanel`.
- Keep charting-specific static data near the asset-command data module or in a scoped charting data file.
- Reuse existing dark Sentinel Edge styling and panel conventions.
- Keep this visually aligned with the accepted browser mock while fitting the current app frame.

## Testing

Minimum verification:

- Layout test confirms `Charting` mode exists.
- Layout test confirms no buy/sell/order controls appear in Charting.
- Layout test confirms bot P&L calendar, bot selector, win/loss composition, and P&L counters are present.
- Build must pass.
- Browser screenshot check should verify the chart remains the dominant area on desktop and the analytics rail does not crowd the chart.

## Open Follow-Up

The next tab can be brainstormed separately. Since GEX/VEX is now scoped as an in-chart mini map or overlay, the next top-level tab should be selected from the remaining Sentinel Edge workflows instead of assuming a dedicated GEX/VEX tab.
