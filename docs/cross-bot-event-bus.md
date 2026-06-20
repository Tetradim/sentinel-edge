# Cross Bot Event Bus

Sentinel Edge publishes strategic bot instructions through a local append-only event stream. This is separate from the direct Pulse handoff path: Pulse can keep its split-second execution loop, while Edge broadcasts higher-level state/action changes for any bot that needs them.

## Storage

Events are written as JSONL files under:

```text
backend/data/event-bus
```

Override with:

```text
BOT_EVENT_BUS_DIR=C:\path\to\shared\event-bus
```

## Endpoints

```text
POST /api/bus/events
GET /api/bus/events?limit=100
POST /api/bus/edge-actions
```

## Event Shape

All bots should use `bot-event.v1`:

```json
{
  "version": "bot-event.v1",
  "event_id": "uuid",
  "event_type": "edge.action",
  "source_bot": "sentinel-edge",
  "source_instance": "local",
  "created_at": "2026-06-19T14:30:00+00:00",
  "correlation_id": "edge:SPY:stop_buying:market_open:123:test",
  "dedupe_key": "edge:SPY:stop_buying:market_open:123:test",
  "target_bots": ["sentinel-pulse", "consolidation", "auto-crypto", "darkpool-mon"],
  "payload": {},
  "trace": {}
}
```

## Edge Actions

Sentinel Edge emits `edge.action` after market and automation gates pass, before the direct Pulse HTTP handoff is attempted. It emits `edge.action.feedback` after Pulse feedback is known.

The action payload uses `edge.action.v1`:

```json
{
  "contract_version": "edge.action.v1",
  "symbol": "SPY",
  "action": "stop_buying",
  "confidence": 0.92,
  "reason": "Bearish ORB/signal risk",
  "mode": "paper",
  "orb_session": "market_open",
  "idempotency_key": "edge:SPY:stop_buying:market_open:123:test",
  "metadata": {
    "trend": "bearish"
  },
  "pulse_feedback": {}
}
```

Consumers should dedupe by `dedupe_key` and treat Edge actions as strategic instructions, not broker orders. Each bot remains responsible for its own fast local execution loop and safety checks.
