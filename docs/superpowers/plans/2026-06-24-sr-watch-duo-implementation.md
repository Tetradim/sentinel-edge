# S/R Watch Duo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first production-grade backend slice for Edge + Consolidation S/R Watch: Edge can rank intraday support/resistance levels and produce deterministic close/scale directives for option positions, while Consolidation can store per-source S/R Watch settings and safely consume Edge directives without giving Edge broker-control ownership.

**Architecture:** Edge owns market-structure observation and read-only directive generation. Consolidation owns channel/source settings, broker execution, position state, and all risk-enforcement decisions. Integration uses explicit JSON contracts so Edge never mutates Consolidation broker/risk settings directly.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, existing Edge bot event bus, existing Consolidation source config and ingestion modules.

---

## Task 1: Edge S/R Engine Contract and Pure Evaluation

- [ ] Add failing Edge tests in `backend/tests/test_support_resistance.py`.
  - [ ] Verify ranked levels include opening range, session high/low, prior day, premarket, VWAP, ATR bands, and intraday swing levels when present.
  - [ ] Verify levels re-rank after a new intraday high or low by nearest actionable distance from current price and priority.
  - [ ] Verify long call + support break produces a close directive.
  - [ ] Verify long put + resistance break produces a close directive.
  - [ ] Verify long call + resistance break produces a scale-in directive.
  - [ ] Verify long put + support break produces a scale-in directive.
  - [ ] Command: `python -m pytest backend/tests/test_support_resistance.py -q`
- [ ] Implement `backend/support_resistance.py`.
  - [ ] Define dataclasses or Pydantic-safe dictionaries for `SupportResistanceLevel`, `OptionPositionSnapshot`, `SupportResistanceSettings`, and `SupportResistanceDirective`.
  - [ ] Implement `build_support_resistance_levels(bars, current_price, settings)` as a pure function.
  - [ ] Implement `evaluate_support_resistance_position(position, levels, current_price, settings)` as a pure function.
  - [ ] Default scale-in sizing must be `0.25` and expressed as a directive hint, not as a broker order.
  - [ ] Default 0DTE strict-exit behavior must be enabled in settings and represented in directive metadata.
- [ ] Re-run Edge test command until the new tests pass.

## Task 2: Edge API Endpoint and Event Directive Publication

- [ ] Add failing Edge API tests in `backend/tests/test_support_resistance_api.py`.
  - [ ] Verify `POST /api/support-resistance/evaluate` accepts bars plus a position snapshot and returns ranked levels plus directive.
  - [ ] Verify `emit_event=true` publishes a `edge.sr.directive.v1` event through the existing bot event bus with `target_bots=["consolidation"]`.
  - [ ] Command: `python -m pytest backend/tests/test_support_resistance_api.py -q`
- [ ] Update `backend/server.py`.
  - [ ] Import the new S/R engine.
  - [ ] Add request and response models local to the server module or import them from the S/R module if existing server conventions support that cleanly.
  - [ ] Add `POST /api/support-resistance/evaluate`.
  - [ ] Keep the endpoint offline-testable by accepting supplied bars in the request.
  - [ ] Publish Edge directive events only when the request explicitly sets `emit_event=true`.
- [ ] Re-run the Edge API tests and existing market-map tests:
  - [ ] `python -m pytest backend/tests/test_support_resistance_api.py backend/tests/test_market_map_context.py backend/tests/test_chart_workspace.py -q`

## Task 3: Consolidation Source Settings for S/R Watch

- [ ] Add failing Consolidation tests in `backend/tests/test_source_config_sr_watch.py`.
  - [ ] Verify defaults are safe: S/R Watch disabled, Edge auto-action disabled, strict 0DTE exits enabled, stop-trading-after-time disabled.
  - [ ] Verify per-channel overrides can enable S/R Watch and replace ORB gating for that channel/source.
  - [ ] Verify buying-power scale-in is the default add sizing mode with a `0.25` fraction.
  - [ ] Command: `python -m pytest backend/tests/test_source_config_sr_watch.py -q`
- [ ] Update `backend/source_config.py`.
  - [ ] Extend `DEFAULT_SOURCE_CONFIG` with S/R Watch keys.
  - [ ] Preserve existing behavior for channels with no overrides.
  - [ ] Do not add broker execution logic to source config.
- [ ] Re-run source-config and settings tests:
  - [ ] `python -m pytest backend/tests/test_source_config_sr_watch.py backend/tests/test_source_config.py backend/tests/test_settings_source_overrides.py -q`

## Task 4: Consolidation Edge Directive Contract

- [ ] Add failing Consolidation tests in `backend/tests/test_edge_sr_directives.py`.
  - [ ] Verify close directives validate required contract identity fields: underlying, side, expiry, strike, quantity, and directive id.
  - [ ] Verify scale-in directives validate sizing hints and cap intent but do not create orders by themselves.
  - [ ] Verify stale or duplicate directive ids are rejected by the helper.
  - [ ] Command: `python -m pytest backend/tests/test_edge_sr_directives.py -q`
- [ ] Implement `backend/edge_sr_directives.py`.
  - [ ] Parse and validate `edge.sr.directive.v1`.
  - [ ] Normalize directive actions to internal intents: `close_position` and `request_scale_in`.
  - [ ] Provide a small idempotency helper that can be backed by existing event ids for now.
  - [ ] Return structured validation errors instead of raising raw exceptions from the consumer boundary.
- [ ] Re-run directive tests until they pass.

## Task 5: Consolidation Pre-Entry S/R Gate Hook

- [ ] Add failing Consolidation tests in `backend/tests/test_discord_ingestion_sr_watch.py`.
  - [ ] Verify enabling S/R Watch for a source records the parsed source setting on alerts as today.
  - [ ] Verify disabled S/R Watch leaves the current ingestion path unchanged.
  - [ ] Verify an injected Edge S/R gate can block a new entry before broker order processing.
  - [ ] Command: `python -m pytest backend/tests/test_discord_ingestion_sr_watch.py -q`
- [ ] Update `backend/discord_ingestion.py`.
  - [ ] Add an optional dependency callback for S/R pre-entry decisions.
  - [ ] Invoke it only when the resolved source config has S/R Watch enabled.
  - [ ] Fail closed only when the source config requests strict S/R gating; otherwise fail open with a structured log entry.
  - [ ] Do not change broker order placement in this task.
- [ ] Re-run ingestion tests:
  - [ ] `python -m pytest backend/tests/test_discord_ingestion_sr_watch.py backend/tests/test_discord_ingestion.py -q`

## Task 6: Documentation and Verification

- [ ] Update Edge and Consolidation docs with the implemented backend contracts.
  - [ ] Edge: document endpoint, request, response, directive event type, and non-broker authority boundary.
  - [ ] Consolidation: document source config keys, default safety settings, and directive validation boundaries.
- [ ] Run focused cross-repo verification.
  - [ ] Edge command: `python -m pytest backend/tests/test_support_resistance.py backend/tests/test_support_resistance_api.py backend/tests/test_cross_bot_event_bus.py -q`
  - [ ] Consolidation command: `python -m pytest backend/tests/test_source_config_sr_watch.py backend/tests/test_edge_sr_directives.py backend/tests/test_discord_ingestion_sr_watch.py -q`
- [ ] Review git diffs for unrelated changes.
  - [ ] Edge command: `git diff --stat && git diff -- backend docs`
  - [ ] Consolidation command: `git diff --stat && git diff -- backend docs`
- [ ] Commit each repo separately after verification.
  - [ ] Edge commit message: `feat: add support resistance watch engine`
  - [ ] Consolidation commit message: `feat: add edge sr watch contracts`

## Acceptance Criteria

- [ ] Edge can evaluate supplied OHLCV bars and an option position into ranked S/R levels plus either no directive, a close directive, or a scale-in directive.
- [ ] Edge can emit the directive through the existing event bus only by explicit request.
- [ ] Consolidation can store S/R Watch source settings with safe defaults.
- [ ] Consolidation can validate Edge S/R directives without executing broker orders inside the validator.
- [ ] Consolidation ingestion can call an injected S/R pre-entry gate only for sources where S/R Watch is enabled.
- [ ] Existing ORB behavior remains available for sources that do not enable S/R Watch.
- [ ] Tests cover the new contracts and existing nearby behavior still passes.
