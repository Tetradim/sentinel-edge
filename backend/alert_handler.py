"""Alertmanager webhook bridge for Sentinel Edge -> Sentinel Pulse actions."""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
import time
from typing import Any, Dict, Optional

import aiohttp
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


PULSE_URL = os.getenv("PULSE_API_URL", "http://pulse:8002")
DEFAULT_POWER = _env_int("ALERT_DEFAULT_POWER", 1000)
DEFAULT_TRAILING_PERCENT = _env_float("ALERT_TRAILING_PERCENT", 1.0)

_WEBHOOK_USER = os.getenv("WEBHOOK_USER", "sentinel-edge")
_WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
_EDGE_API_KEY = (
    os.getenv("PULSE_API_KEY")
    or os.getenv("EDGE_API_KEY")
    or os.getenv("EDGE_SHARED_API_KEY")
    or ""
)


class AlertPayload(BaseModel):
    """Subset of the Alertmanager webhook payload used by this bridge."""

    alerts: list[Dict[str, Any]] = Field(default_factory=list)


class PulseClient:
    """Small HTTP client for Pulse API calls made from Alertmanager alerts."""

    def __init__(self, base_url: str = PULSE_URL):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                base_url=self.base_url,
                timeout=aiohttp.ClientTimeout(total=10.0),
            )
        return self._session

    async def post(self, path: str, json: Dict[str, Any] | None = None, headers: Dict[str, str] | None = None) -> bool:
        """POST to Pulse and return whether Pulse accepted the request."""
        request_headers = dict(headers or {})
        if _EDGE_API_KEY:
            request_headers.setdefault("X-API-Key", _EDGE_API_KEY)

        try:
            session = await self._get_session()
            async with session.post(path, json=json, headers=request_headers) as resp:
                if resp.status >= 400:
                    logger.error("Pulse API error: %s %s", resp.status, await resp.text())
                    return False
                logger.info("Pulse API POST %s -> %s", path, resp.status)
                return True
        except Exception as exc:
            logger.error("Failed to call Pulse API: %s", exc)
            return False

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


pulse_client = PulseClient()


def _verify_basic_auth(request: Request) -> None:
    """Validate Alertmanager Basic auth when WEBHOOK_SECRET is configured."""
    if not _WEBHOOK_SECRET:
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        user, password = decoded.split(":", 1)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials") from exc

    if not (
        secrets.compare_digest(user, _WEBHOOK_USER)
        and secrets.compare_digest(password, _WEBHOOK_SECRET)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")


def _normalise_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def _coerce_float(*values: Any, default: float) -> float:
    for value in values:
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return default


def _alert_reason(alert: Dict[str, Any], fallback: str) -> str:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    return (
        str(annotations.get("summary") or labels.get("alertname") or fallback)
        .strip()
        or fallback
    )


def _idempotency_key(symbol: str, action: str, alert: Dict[str, Any]) -> str:
    labels = alert.get("labels", {})
    fingerprint = alert.get("fingerprint") or labels.get("alertname") or f"{symbol}:{action}"
    nonce = hashlib.sha1(str(fingerprint).encode("utf-8")).hexdigest()[:10]
    minute_bucket = int(time.time() // 60)
    return f"edge:{symbol}:{action}:market_open:{minute_bucket}:{nonce}"


def _handoff_payload(
    *,
    symbol: str,
    action: str,
    alert: Dict[str, Any],
    reason: str,
    confidence: float = 1.0,
    stop_type: str | None = None,
    trailing_percent: float | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "contract_version": "edge.pulse.handoff.v1",
        "symbol": symbol,
        "action": action,
        "confidence": confidence,
        "reason": reason,
        "mode": os.getenv("PULSE_HANDOFF_MODE", "paper"),
        "orb_session": "market_open",
        "idempotency_key": _idempotency_key(symbol, action, alert),
        "source": "sentinel_edge",
        "created_at": time.time(),
        "metadata": {"source": "alertmanager", **(metadata or {})},
    }
    if stop_type:
        payload["stop_type"] = stop_type
    if trailing_percent is not None:
        payload["trailing_percent"] = trailing_percent
    return payload


async def _post_handoff(payload: Dict[str, Any]) -> bool:
    return await pulse_client.post(
        "/api/edge/handoff",
        json=payload,
        headers={"X-API-Key": _EDGE_API_KEY} if _EDGE_API_KEY else {},
    )


async def handle_global_risk_reduction(alert: Dict[str, Any]) -> bool:
    """Tighten trailing stops across Pulse-managed tickers."""
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    trailing_percent = _coerce_float(
        labels.get("trailing_percent"),
        annotations.get("trailing_percent"),
        default=DEFAULT_TRAILING_PERCENT,
    )
    payload = _handoff_payload(
        symbol="GLOBAL",
        action="tighten_trailing_stop",
        alert=alert,
        reason=_alert_reason(alert, "Global risk reduction alert"),
        stop_type="tighten_trailing",
        trailing_percent=trailing_percent,
        metadata={"scope": "global", "alert": alert},
    )
    logger.warning("Alertmanager global risk reduction -> Pulse handoff")
    return await _post_handoff(payload)


async def handle_bearish_cluster(symbol: str, alert: Dict[str, Any]) -> bool:
    """Stop new buys for a symbol after a bearish cluster alert."""
    payload = _handoff_payload(
        symbol=symbol,
        action="stop_buying",
        alert=alert,
        reason=_alert_reason(alert, "Bearish cluster alert"),
        metadata={"alert": alert},
    )
    logger.warning("Alertmanager bearish cluster for %s -> Pulse stop_buying", symbol)
    return await _post_handoff(payload)


async def handle_add_ticker(symbol: str, base_power: int = DEFAULT_POWER) -> bool:
    """Add a new ticker to Pulse using its user-facing ticker API."""
    logger.info("Alertmanager add_ticker for %s", symbol)
    return await pulse_client.post(
        "/api/tickers",
        json={"symbol": symbol, "base_power": base_power},
    )


async def handle_remove_ticker(symbol: str, alert: Dict[str, Any]) -> bool:
    """Disable buying for a ticker instead of deleting configuration from an alert."""
    payload = _handoff_payload(
        symbol=symbol,
        action="stop_buying",
        alert=alert,
        reason=_alert_reason(alert, "Remove ticker alert"),
        metadata={"requested_action": "remove_ticker", "alert": alert},
    )
    logger.info("Alertmanager remove_ticker for %s -> Pulse stop_buying", symbol)
    return await _post_handoff(payload)


@router.post("/alerts")
async def handle_alertmanager_webhook(request: Request, payload: AlertPayload):
    """Receive Alertmanager webhooks and dispatch Pulse handoff commands."""
    _verify_basic_auth(request)

    processed = 0
    failed = 0

    for alert in payload.alerts:
        if alert.get("status") != "firing":
            continue

        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        action = labels.get("action")
        symbol = _normalise_symbol(annotations.get("symbol") or labels.get("symbol"))

        logger.info(
            "Alert webhook: alertname=%s action=%s symbol=%s",
            labels.get("alertname"),
            action,
            symbol,
        )

        sent = False
        if action == "global_risk_reduction":
            sent = await handle_global_risk_reduction(alert)
        elif action == "bearish_cluster":
            if symbol:
                sent = await handle_bearish_cluster(symbol, alert)
            else:
                logger.warning("BearishCluster alert missing symbol")
        elif action == "add_ticker":
            if symbol:
                try:
                    base_power = int(labels.get("base_power", DEFAULT_POWER))
                except (TypeError, ValueError):
                    base_power = DEFAULT_POWER
                sent = await handle_add_ticker(symbol, base_power)
            else:
                logger.warning("AddTicker alert missing symbol")
        elif action == "remove_ticker":
            if symbol:
                sent = await handle_remove_ticker(symbol, alert)
            else:
                logger.warning("RemoveTicker alert missing symbol")
        else:
            logger.debug("Unknown alert action: %s", action)

        if sent:
            processed += 1
        elif action:
            failed += 1

    return {"status": "processed", "count": processed, "failed": failed}


@router.get("/health")
async def health_check():
    """Health endpoint for the root Alertmanager receiver."""
    return {
        "status": "healthy",
        "service": "alert-handler",
        "auth_enabled": bool(_WEBHOOK_SECRET),
        "pulse_url": PULSE_URL,
    }


async def shutdown() -> None:
    """Cleanup on shutdown."""
    await pulse_client.close()
