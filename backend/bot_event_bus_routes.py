"""FastAPI routes for the Cross Bot Event Bus and live handoff operations."""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from shared.bot_event_bus import EDGE_ACTION_TARGET_BOTS, BotEvent, event_bus, publish_event

# server.py imports scheduler and alert_handler first, so the freshness/exactly-once
# wrappers are already installed before Edge's strategist brain wraps the pipeline.
import edge_brain_patch as _edge_brain_patch  # noqa: F401,E402


router = APIRouter(prefix="/bus", tags=["Cross Bot Event Bus"])
_OPERATOR_ACTION_SECRET_ENV = "EDGE_OPERATOR_ACTION_SECRET"
_OPERATOR_ACTION_SECRET_HEADER = "X-Edge-Operator-Secret"


@router.post("/events")
async def publish_bot_event(request: Request, payload: BotEvent):
    _require_operator_action_secret(request)
    event = event_bus.publish(payload)
    return {"status": "accepted", "event": event.model_dump(mode="json")}


@router.get("/events")
async def recent_bot_events(limit: int = 100, event_type: str | None = None):
    return {"events": event_bus.recent(limit=limit, event_type=event_type)}


@router.post("/edge-actions")
async def publish_edge_action(request: Request, payload: dict):
    """Publish a manual Edge strategic action for other bots to consume."""
    _require_operator_action_secret(request)
    action_event = publish_event(
        "edge.action",
        payload={"contract_version": "edge.action.v1", **payload},
        dedupe_key=str(payload.get("idempotency_key") or ""),
        target_bots=EDGE_ACTION_TARGET_BOTS,
    )
    return {"status": "accepted", "event": action_event.model_dump(mode="json")}


@router.get("/automation-operations")
async def automation_operations():
    """Expose pending exactly-once handoffs and per-symbol execution-data status."""
    import server

    scheduler = server.scheduler
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not initialised")

    controller = scheduler.automation
    pending = dict(getattr(controller, "_pending_commands", {}) or {})
    execution_data = {}
    for symbol in list(getattr(scheduler, "active_tickers", []) or []):
        getter = getattr(scheduler.prices, "execution_data_status", None)
        execution_data[str(symbol).upper()] = (
            getter(symbol)
            if callable(getter)
            else {"source": "unknown", "executable": False, "age_seconds": None}
        )

    queue_stats = scheduler.pulse.queue_stats() if hasattr(scheduler.pulse, "queue_stats") else {}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automation": {
            "settings": controller.settings.public_dict(),
            "pending_commands": pending,
            "pending_count": len(pending),
            "last_handoff": controller.last_handoff,
            "last_suppressed": controller.last_suppressed,
        },
        "delivery": {
            "pulse_available": bool(getattr(scheduler.pulse, "pulse_available", False)),
            "circuit_state": getattr(getattr(scheduler.pulse, "state", None), "name", "unknown"),
            "failure_count": int(getattr(scheduler.pulse, "failure_count", 0) or 0),
            "retry_queue": queue_stats,
        },
        "execution_data": execution_data,
        "summary": {
            "symbols": len(execution_data),
            "executable_symbols": sum(1 for value in execution_data.values() if value.get("executable")),
            "stale_or_unavailable_symbols": sum(1 for value in execution_data.values() if not value.get("executable")),
            "pending_commands": len(pending),
        },
    }


def _require_operator_action_secret(request: Request) -> None:
    expected = os.getenv(_OPERATOR_ACTION_SECRET_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{_OPERATOR_ACTION_SECRET_ENV} is required before event-bus write endpoints are accepted.",
        )

    provided = request.headers.get(_OPERATOR_ACTION_SECRET_HEADER, "")
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid operator action secret.")
