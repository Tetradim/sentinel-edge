"""FastAPI routes for the Cross Bot Event Bus."""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, HTTPException, Request, status

from shared.bot_event_bus import EDGE_ACTION_TARGET_BOTS, BotEvent, event_bus, publish_event


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
        payload={
            "contract_version": "edge.action.v1",
            **payload,
        },
        dedupe_key=str(payload.get("idempotency_key") or ""),
        target_bots=EDGE_ACTION_TARGET_BOTS,
    )
    return {"status": "accepted", "event": action_event.model_dump(mode="json")}


def _require_operator_action_secret(request: Request) -> None:
    expected = os.getenv(_OPERATOR_ACTION_SECRET_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{_OPERATOR_ACTION_SECRET_ENV} is required before event-bus write endpoints are accepted.",
        )

    provided = request.headers.get(_OPERATOR_ACTION_SECRET_HEADER, "")
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator action secret.",
        )
