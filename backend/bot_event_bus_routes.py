"""FastAPI routes for the Cross Bot Event Bus."""
from __future__ import annotations

from fastapi import APIRouter

from shared.bot_event_bus import BotEvent, event_bus, publish_event


router = APIRouter(prefix="/bus", tags=["Cross Bot Event Bus"])


@router.post("/events")
async def publish_bot_event(payload: BotEvent):
    event = event_bus.publish(payload)
    return {"status": "accepted", "event": event.model_dump(mode="json")}


@router.get("/events")
async def recent_bot_events(limit: int = 100, event_type: str | None = None):
    return {"events": event_bus.recent(limit=limit, event_type=event_type)}


@router.post("/edge-actions")
async def publish_edge_action(payload: dict):
    """Publish a manual Edge strategic action for other bots to consume."""
    action_event = publish_event(
        "edge.action",
        payload={
            "contract_version": "edge.action.v1",
            **payload,
        },
        dedupe_key=str(payload.get("idempotency_key") or ""),
        target_bots=["sentinel-pulse", "consolidation", "auto-crypto", "darkpool-mon"],
    )
    return {"status": "accepted", "event": action_event.model_dump(mode="json")}
