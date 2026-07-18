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
from edge_profitability import coordinator
from edge_orb_squeeze import short_squeeze_store
from flare_intelligence import flare_intelligence_store


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


@router.post("/intelligence/flare")
async def record_flare_intelligence(request: Request, payload: dict):
    """Accept expiring dark-pool intelligence; never an execution command."""
    _require_operator_action_secret(request)
    try:
        intelligence = flare_intelligence_store.record({"source_bot": "sentinel-flare", **payload})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    event = publish_event(
        "flare.intelligence.recorded",
        payload=intelligence,
        correlation_id=intelligence["symbol"],
        dedupe_key=intelligence["intelligence_id"],
        target_bots=["sentinel-edge"],
        trace={"source_bot": "sentinel-flare"},
    )
    return {"status": "recorded", "intelligence": intelligence, "event": event.model_dump(mode="json")}


@router.get("/intelligence/flare/status")
async def flare_intelligence_status():
    return flare_intelligence_store.status()


@router.post("/intelligence/short-squeeze")
async def record_short_squeeze_snapshot(request: Request, payload: dict):
    """Accept validated short-interest pressure; never an execution command."""
    _require_operator_action_secret(request)
    try:
        snapshot = short_squeeze_store.record(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    event = publish_event(
        "edge.squeeze.snapshot.recorded",
        payload=snapshot,
        correlation_id=snapshot["symbol"],
        dedupe_key=snapshot["snapshot_id"],
        target_bots=["sentinel-edge"],
        trace={"source": snapshot.get("source")},
    )
    return {"status": "recorded", "snapshot": snapshot, "event": event.model_dump(mode="json")}


@router.get("/intelligence/short-squeeze/status")
async def short_squeeze_status():
    return short_squeeze_store.status()


@router.post("/profitability/opportunities")
async def evaluate_specialist_opportunity(request: Request, payload: dict):
    """Rank and authorize a specialist bot's proposed trade before execution."""
    _require_operator_action_secret(request)
    authorization = coordinator.evaluate_external_proposal(payload)
    target_bot = str(authorization.get("target_bot") or payload.get("source_bot") or "")
    event = publish_event(
        "edge.strategy.authorization",
        payload=authorization,
        correlation_id=str(payload.get("correlation_id") or authorization.get("symbol") or ""),
        dedupe_key=str(payload.get("proposal_id") or authorization.get("trade_card", {}).get("card_id") or ""),
        target_bots=[target_bot] if target_bot else EDGE_ACTION_TARGET_BOTS,
        trace={"source_proposal_id": payload.get("proposal_id")},
    )
    return {
        "status": "authorized" if authorization.get("authorized") else "rejected",
        "authorization": authorization,
        "event": event.model_dump(mode="json"),
    }


@router.post("/profitability/feedback")
async def record_specialist_execution_feedback(request: Request, payload: dict):
    """Record execution quality and lifecycle feedback from any specialist bot."""
    _require_operator_action_secret(request)
    card_id = str(payload.get("card_id") or "")
    card = coordinator.cards.get(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Unknown trade card")
    action = str(payload.get("action") or "feedback").lower()
    position = payload.get("position") if isinstance(payload.get("position"), dict) else None
    feedback = payload.get("feedback") if isinstance(payload.get("feedback"), dict) else dict(payload)
    if position is not None and action in {"position_update", "position_reconciliation", "reconcile", "exit"}:
        feedback.setdefault("accepted", True)
        feedback.setdefault("status", "accepted")
        if position.get("realized_pnl") is not None:
            feedback.setdefault("realized_pnl", position.get("realized_pnl"))
        if position.get("realized_return_pct") is not None:
            feedback.setdefault("realized_return_pct", position.get("realized_return_pct"))
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    coordinator.record_feedback(card, action=action, feedback=feedback, metadata=metadata)
    if position is not None:
        coordinator.observe_position(
            card.symbol,
            position,
            current_price=float(payload.get("current_price") or position.get("current_price") or 0.0),
        )
    event = publish_event(
        "edge.strategy.feedback.recorded",
        payload={
            "contract_version": "edge.strategy.feedback.v1",
            "card_id": card.card_id,
            "position_id": card.position_id,
            "symbol": card.symbol,
            "target_bot": card.target_bot,
            "action": action,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        },
        correlation_id=card.position_id,
        dedupe_key=str(payload.get("feedback_id") or ""),
        target_bots=[card.target_bot],
    )
    return {"status": "recorded", "trade_card": card.public_dict(), "event": event.model_dump(mode="json")}


@router.get("/profitability/status")
async def profitability_status():
    return coordinator.portfolio_status(include_cards=True)


@router.get("/profitability/trade-cards")
async def profitability_trade_cards(include_terminal: bool = False):
    cards = [card.public_dict() for card in coordinator.cards.values()]
    if not include_terminal:
        cards = [card for card in cards if card.get("state") not in {"completed", "invalidated", "expired"}]
    cards.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    return {"trade_cards": cards}


@router.get("/profitability/outcomes")
async def profitability_outcomes(limit: int = 100):
    return {"outcomes": coordinator.recent_outcomes(limit=limit)}


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
        "profitability": coordinator.portfolio_status(include_cards=False),
        "flare_intelligence": flare_intelligence_store.status(),
        "short_squeeze": short_squeeze_store.status(),
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
