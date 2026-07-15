"""Live handoff transport rules for ambiguous delivery.

A timeout or server error after POSTing a broker-capable command is not proof
that Pulse did not receive it. Such failures must be retried with the same
idempotency key, never sent to a second legacy endpoint.
"""
from __future__ import annotations

import os
from typing import Any, Dict

from pydantic import ValidationError

from pulse_client import PulseClient
from shared.handoff import PulseHandoffRequest


async def _send_handoff_without_ambiguous_legacy_fallback(
    self: PulseClient,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    symbol = str(payload.get("symbol", "")).upper()
    if not symbol:
        return self.suppressed_handoff_feedback(
            "/api/edge/handoff",
            "missing_symbol",
        )

    try:
        request = PulseHandoffRequest.from_edge_payload(payload)
    except ValidationError as exc:
        feedback = self.suppressed_handoff_feedback(
            "/api/edge/handoff",
            "invalid_handoff_contract",
        )
        feedback["validation_errors"] = self._json_safe_validation_errors(exc)
        return feedback

    if not self._has_api_key():
        return self.suppressed_handoff_feedback(
            "/api/edge/handoff",
            "missing_pulse_api_key",
        )

    payload = request.model_dump(mode="json", exclude_none=True)
    symbol = payload["symbol"]
    action = payload["action"]
    mode = str(payload.get("mode") or "").lower()

    if not self.pulse_available or self.state.name == "OPEN":
        reason = "pulse_unavailable" if not self.pulse_available else "circuit_open"
        return self.suppressed_handoff_feedback("/api/edge/handoff", reason)

    endpoint = os.getenv("PULSE_HANDOFF_ENDPOINT", "/api/edge/handoff").strip()
    if endpoint:
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        feedback = await self._post_with_feedback(
            endpoint,
            payload,
            headers=self.handoff_headers(payload),
        )
        if feedback.get("status") != "failed":
            return feedback

        status_code = feedback.get("status_code")
        # Only a definitive unsupported-route response can use the compatibility
        # fallback. Timeouts, connection failures, and 5xx responses may have
        # reached Pulse and must preserve the same command ID for reconciliation.
        if status_code not in {404, 405, 501}:
            ambiguous = status_code is None or int(status_code) >= 500
            if ambiguous:
                feedback["ambiguous_delivery"] = True
                feedback["reconciliation_required"] = True
                feedback["reason"] = feedback.get("reason") or "ambiguous_delivery"
            return feedback

        if mode == "live":
            return {
                **feedback,
                "reason": "structured_live_handoff_unavailable",
                "legacy_fallback": False,
            }
    else:
        feedback = None
        if mode == "live":
            return self.suppressed_handoff_feedback(
                "/api/edge/handoff",
                "structured_live_handoff_required",
            )

    legacy_endpoint = f"/api/edge/tickers/{symbol}/decision"
    legacy_payload = self.legacy_handoff_payload(payload)
    legacy_sent = await self.send_decision(symbol, action, **legacy_payload)
    legacy_feedback = self.normalise_handoff_feedback(
        endpoint=legacy_endpoint,
        status_code=200 if legacy_sent else None,
        response_body={"accepted": legacy_sent},
        legacy_fallback=bool(endpoint),
    )
    if feedback is not None:
        legacy_feedback["primary_feedback"] = feedback
    return legacy_feedback


def install() -> None:
    PulseClient.send_handoff_command = _send_handoff_without_ambiguous_legacy_fallback
