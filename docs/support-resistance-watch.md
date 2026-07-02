# Support/Resistance Watch Contract

Sentinel Edge owns market-structure observation for S/R Watch. It does not place broker orders and does not mutate Sentinel Echo risk settings.

## Endpoint

`POST /api/support-resistance/evaluate`

Request fields:

- `symbol`: underlying ticker.
- `bars`: supplied OHLCV bars used to build levels when `levels` is omitted.
- `current_price`: current underlying price. Required.
- `position`: optional option position snapshot.
- `levels`: optional prebuilt S/R levels. When supplied, Edge evaluates against these levels instead of rebuilding them from bars.
- `settings`: optional engine settings such as `opening_range_minutes`, `swing_window`, `break_buffer_pct`, `scale_in_fraction`, and strict 0DTE metadata flags.
- `emit_event`: when `true`, Edge publishes an event only if a directive is produced.

Response fields:

- `schema_version`: `edge.support_resistance.evaluation.v1`.
- `levels`: ranked `edge.support_resistance.levels.v1` items.
- `directive`: `edge.sr.directive.v1` when a close or scale-in directive is warranted, otherwise `null`.
- `event`: published bot-event payload when `emit_event=true`, otherwise `null`.

## Directive Rules

- Long call + support break: `close_position`.
- Long put + resistance break: `close_position`.
- Long call + resistance break: `request_scale_in`.
- Long put + support break: `request_scale_in`.

Close directives include `execution_hint.immediate=true` and prefer a marketable limit. Scale-in directives include a sizing hint only; Sentinel Echo remains responsible for buying-power checks, position caps, and broker execution.

## Event Bus

When requested, Edge publishes `edge.sr.directive.v1` through the existing bot event bus with `target_bots=["sentinel-echo"]`. The directive includes `directive_id` and UTC `created_at` so consumers can reject duplicates and stale events.
