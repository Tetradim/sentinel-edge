"""Alertmanager Webhook Handler — Sentinel Edge

Receives POST callbacks from Alertmanager and translates them into
Pulse override commands via SentinelEdge.send_override().

Auth
────
Set WEBHOOK_SECRET in the environment (and in alertmanager.yml
  http_config.basic_auth.password) to enable basic-auth verification.
Leave unset only for health checks; action webhooks fail closed without it.

Alert → Action mapping
───────────────────────
  action=global_risk_reduction  → tighten_trailing_global
  action=pause_new_buys         → pause_new_entries
  direction=bearish + severity=critical  → tighten_trailing_global
  alertname=EdgeEngineDown      → logged only (engine not running)
  send_resolved=true            → resumption logged; can be wired to actions
"""
import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.security import HTTPBasicCredentials
import secrets

# Access the live SentinelEdge instance without capturing it at import time
import analyst.core as _core

router = APIRouter(tags=["alertmanager"])
logger = logging.getLogger(__name__)

_WEBHOOK_USER = os.getenv("WEBHOOK_USER", "sentinel-edge")
_WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")


# ── Auth helper ───────────────────────────────────────────────────────────────

def _verify_basic_auth(request: Request) -> None:
    """Validate HTTP Basic auth for action-bearing webhook requests."""
    if not _WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WEBHOOK_SECRET is required before analyst webhooks are accepted.",
        )
    import base64
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    try:
        decoded = base64.b64decode(auth_header[6:]).decode()
        user, pwd = decoded.split(":", 1)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")

    valid = (
        secrets.compare_digest(user, _WEBHOOK_USER)
        and secrets.compare_digest(pwd, _WEBHOOK_SECRET)
    )
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials")


# ── Action dispatch ───────────────────────────────────────────────────────────

async def _dispatch(alert: Dict[str, Any]) -> str:
    """Map a single Alertmanager alert to a Pulse override action."""
    edge = _core.analyst_instance
    if not edge:
        logger.warning("analyst_instance not ready — skipping dispatch")
        return "not_ready"

    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    status_val = alert.get("status", "firing")   # "firing" | "resolved"
    alertname = labels.get("alertname", "")
    action = labels.get("action", "")
    direction = labels.get("direction", "")
    severity = labels.get("severity", "")

    logger.info(
        "Alert [%s] status=%s  alertname=%s  direction=%s  severity=%s",
        action or alertname, status_val, alertname, direction, severity,
    )

    # ── Resolved handling ────────────────────────────────────────────────
    if status_val == "resolved":
        logger.info("Alert resolved: %s — no automatic action", alertname)
        return "resolved_ack"

    # ── Firing: map to Pulse overrides ───────────────────────────────────
    payload_base = {
        "reason": "alertmanager_webhook",
        "alertname": alertname,
        "severity": severity,
        "summary": annotations.get("summary", ""),
        "alert": alert,
    }

    if action == "global_risk_reduction" or (direction == "bearish" and severity == "critical"):
        logger.warning("🔴 Global risk reduction triggered — tightening trailing stops")
        await edge.send_override("tighten_trailing_global", payload_base)
        edge.prom_exporter.record_override("tighten_trailing_global")
        return "tighten_trailing_global"

    elif action == "pause_new_buys":
        logger.warning("⏸️  Pausing new buy entries via Pulse override")
        await edge.send_override("pause_new_entries", payload_base)
        edge.prom_exporter.record_override("pause_new_entries")
        return "pause_new_entries"

    elif alertname == "BearishClusterOverride":
        logger.error("🚨 BearishClusterOverride alert — tightening trailing stops")
        await edge.send_override("tighten_trailing_global", payload_base)
        edge.prom_exporter.record_override("tighten_trailing_global")
        return "tighten_trailing_global"

    elif alertname == "EdgeEngineDown":
        logger.error("💀 EdgeEngineDown alert received — scheduler may have crashed")
        # Could trigger PagerDuty / Telegram here in future
        return "engine_down_logged"

    elif alertname == "HighDrawdown":
        logger.error("📉 HighDrawdown alert — triggering emergency exit override")
        await edge.send_override("emergency_exit_all", payload_base)
        edge.prom_exporter.record_override("emergency_exit_all")
        return "emergency_exit_all"

    elif alertname == "StrongCorrelationCluster":
        logger.warning("🔗 StrongCorrelationCluster alert — tightening trailing stops")
        await edge.send_override("tighten_trailing_global", payload_base)
        edge.prom_exporter.record_override("tighten_trailing_global")
        return "tighten_trailing_global"

    else:
        logger.info("No specific action mapped for alertname=%s — acknowledged", alertname)
        return "no_action"


# ── Main webhook endpoint ─────────────────────────────────────────────────────

@router.post("/webhook/alert", status_code=status.HTTP_200_OK)
async def handle_alert(request: Request) -> Dict[str, Any]:
    """
    Alertmanager webhook receiver.

    Alertmanager POSTs a payload of the form:
        {
          "alerts": [ { "labels": {...}, "annotations": {...}, "status": "firing" }, ... ],
          "commonLabels": {...},
          "groupLabels": {...},
          "receiver": "sentinel-webhook",
          "status": "firing"
        }
    """
    _verify_basic_auth(request)

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    alerts: List[Dict[str, Any]] = payload.get("alerts", [])
    if not alerts:
        return {"status": "no_alerts", "processed": 0}

    results = []
    for alert in alerts:
        action_taken = await _dispatch(alert)
        results.append({
            "alertname": alert.get("labels", {}).get("alertname", "unknown"),
            "status": alert.get("status", "unknown"),
            "action_taken": action_taken,
        })

    logger.info("Webhook processed %d alert(s): %s", len(results), results)
    return {"status": "acknowledged", "processed": len(results), "results": results}


# ── Health check for alertmanager receiver ────────────────────────────────────

@router.get("/webhook/health", status_code=status.HTTP_200_OK)
async def webhook_health() -> Dict[str, Any]:
    """Verify the webhook receiver is reachable (used by alertmanager to test config)."""
    return {
        "status": "ok",
        "analyst_ready": _core.analyst_instance is not None,
        "auth_enabled": bool(_WEBHOOK_SECRET),
    }


# ── Dedicated pulse-override endpoint ────────────────────────────────────────

@router.post("/webhook/pulse-override", status_code=status.HTTP_200_OK)
async def handle_pulse_override(request: Request) -> Dict[str, Any]:
    """
    Dedicated receiver for the 'pulse-override' Alertmanager route.

    Handles critical-severity alerts that require an immediate Pulse action.
    Maps `action` label → specific override command.

    Alertmanager sends this to all critical alerts routed via 'pulse-override'.
    """
    _verify_basic_auth(request)

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    edge = _core.analyst_instance
    if not edge:
        logger.warning("analyst_instance not ready — pulse-override skipped")
        return {"status": "not_ready"}

    alerts: list = payload.get("alerts", [])
    results = []

    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alert_status = alert.get("status", "firing")
        alertname = labels.get("alertname", "")
        action = labels.get("action", "")
        direction = labels.get("direction", "")
        severity = labels.get("severity", "")

        logger.warning(
            "⚡ PULSE-OVERRIDE: alertname=%s action=%s severity=%s direction=%s status=%s",
            alertname, action, severity, direction, alert_status,
        )

        if alert_status == "resolved":
            results.append({"alertname": alertname, "action": "resolved_ack"})
            continue

        override_action = None

        # Map alert labels → Pulse override command
        if action == "global_risk_reduction" or alertname == "CriticalBearishCorrelation":
            override_action = "tighten_trailing_global"

        elif action == "increase_aggression" or alertname == "BullishMomentumRegime":
            override_action = "relax_trailing_stops"

        elif action == "pause_new_buys":
            override_action = "pause_new_entries"

        elif alertname == "HighDrawdown":
            override_action = "emergency_exit_all"

        elif alertname == "EdgeEngineDown":
            logger.critical("💀 EdgeEngineDown via pulse-override — manual intervention needed")
            results.append({"alertname": alertname, "action": "engine_down_critical"})
            continue

        if override_action:
            await edge.send_override(override_action, {
                "source": "alertmanager_pulse_override",
                "alertname": alertname,
                "severity": severity,
                "direction": direction,
                "summary": annotations.get("summary", ""),
                "cluster_id": labels.get("cluster_id", ""),
            })
            edge.prom_exporter.record_override(override_action)
            logger.warning("✅ Override dispatched: %s", override_action)
            results.append({"alertname": alertname, "action": override_action})
        else:
            logger.info("No override mapped for alertname=%s action=%s", alertname, action)
            results.append({"alertname": alertname, "action": "no_override_mapped"})

    return {"status": "acknowledged", "processed": len(results), "results": results}


# ── General alert endpoint ────────────────────────────────────────────────────

@router.post("/webhook/general", status_code=status.HTTP_200_OK)
async def handle_general(request: Request) -> Dict[str, Any]:
    """
    General-purpose alert receiver — logs all alerts and returns ACK.

    Used by 'default' and 'trading-team' receivers as a reliable fallback.
    Extend this to forward to Telegram / PagerDuty / Slack as needed.
    """
    _verify_basic_auth(request)

    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")

    alerts: list = payload.get("alerts", [])
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        logger.info(
            "📋 GENERAL alert [%s]: alertname=%s severity=%s — %s",
            alert.get("status", "?"),
            labels.get("alertname", "unknown"),
            labels.get("severity", "unknown"),
            annotations.get("summary", ""),
        )

    return {"status": "acknowledged", "processed": len(alerts)}
