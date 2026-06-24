"""Tests for structured Pulse handoff feedback handling."""
import asyncio
import json
import logging
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch

import httpx


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pulse_client import PulseClient  # noqa: E402


class PulseHandoffFeedbackTests(unittest.TestCase):
    def test_client_uses_edge_api_key_env_as_pulse_auth_fallback(self):
        with patch.dict(os.environ, {"EDGE_API_KEY": "edge-env-key"}, clear=True):
            client = PulseClient(base_url="http://pulse.invalid")

        try:
            self.assertEqual(client._build_headers().get("X-API-Key"), "edge-env-key")
        finally:
            asyncio.run(client.aclose())

    def test_handoff_is_suppressed_when_pulse_api_key_is_missing(self):
        captured_requests = []

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(202, json={"accepted": True}, request=request)

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                return await client.send_handoff_command(
                    {
                        "symbol": "AAPL",
                        "action": "buy",
                        "confidence": 0.8,
                        "reason": "missing key test",
                        "mode": "paper",
                        "orb_session": "market_open",
                        "idempotency_key": "edge:AAPL:buy:market_open:123:missing-key",
                        "source": "sentinel_edge",
                        "created_at": 1760000000.0,
                        "metadata": {},
                    }
                )
            finally:
                await client.aclose()

        result = asyncio.run(run())

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(result["reason"], "missing_pulse_api_key")
        self.assertEqual([], captured_requests)

    def test_legacy_handoff_fallback_uses_edge_decision_route(self):
        captured_requests = []

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(200, json={"accepted": True}, request=request)

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="edge-key")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                with patch.dict(os.environ, {"PULSE_HANDOFF_ENDPOINT": ""}):
                    return await client.send_handoff_command(
                        {
                            "symbol": "AAPL",
                            "action": "buy",
                            "confidence": 0.8,
                            "reason": "route test",
                            "mode": "paper",
                            "orb_session": "market_open",
                            "idempotency_key": "edge:AAPL:buy:market_open:123:route",
                            "source": "sentinel_edge",
                            "created_at": 1760000000.0,
                            "metadata": {},
                        }
                    )
            finally:
                await client.aclose()

        result = asyncio.run(run())

        self.assertTrue(result["sent"])
        self.assertEqual("/api/edge/tickers/AAPL/decision", captured_requests[0].url.path)

    def test_start_bot_posts_to_pulse_edge_bot_start_endpoint(self):
        captured_requests = []

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(200, json={"running": True, "paused": False}, request=request)

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="edge-key")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                return await client.start_bot(enable_all=False)
            finally:
                await client.aclose()

        result = asyncio.run(run())

        self.assertTrue(result)
        self.assertEqual("/api/edge/bot/start", captured_requests[0].url.path)
        self.assertEqual({"enable_all": False}, json.loads(captured_requests[0].content))
        self.assertEqual("edge-key", captured_requests[0].headers.get("X-API-Key"))

    def test_stop_bot_posts_to_pulse_edge_bot_stop_endpoint(self):
        captured_requests = []

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(200, json={"running": False, "paused": False}, request=request)

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="edge-key")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                return await client.stop_bot(disable_all=False)
            finally:
                await client.aclose()

        result = asyncio.run(run())

        self.assertTrue(result)
        self.assertEqual("/api/edge/bot/stop", captured_requests[0].url.path)
        self.assertEqual({"disable_all": False}, json.loads(captured_requests[0].content))
        self.assertEqual("edge-key", captured_requests[0].headers.get("X-API-Key"))

    def test_enable_trailing_stop_rejects_non_positive_percent_before_transport(self):
        async def run():
            client = PulseClient(base_url="http://pulse.invalid")
            client.pulse_available = True
            client.send_decision = AsyncMock(return_value=True)
            try:
                result = await client.enable_trailing_stop("SPY", 0)
                return result, client.send_decision.await_count
            finally:
                await client.aclose()

        result, send_count = asyncio.run(run())

        self.assertFalse(result)
        self.assertEqual(0, send_count)

    def test_enable_trailing_stop_rejects_nan_percent_before_transport(self):
        async def run():
            client = PulseClient(base_url="http://pulse.invalid")
            client.pulse_available = True
            client.send_decision = AsyncMock(return_value=True)
            try:
                result = await client.enable_trailing_stop("SPY", float("nan"))
                return result, client.send_decision.await_count
            finally:
                await client.aclose()

        result, send_count = asyncio.run(run())

        self.assertFalse(result)
        self.assertEqual(0, send_count)

    def test_get_position_uses_edge_position_route_without_recursing(self):
        captured_requests = []

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(
                200,
                json={
                    "symbol": "AAPL",
                    "has_position": True,
                    "pnl": 12.5,
                    "pnl_pct": 1.25,
                    "trailing_enabled": True,
                    "trailing_percent": 1.5,
                    "entry_price": 100.0,
                    "drawdown_pct": 0.5,
                },
                request=request,
            )

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="edge-key")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                return await client.get_position("AAPL")
            finally:
                await client.aclose()

        result = asyncio.run(run())

        self.assertEqual("/api/edge/positions/AAPL", captured_requests[0].url.path)
        self.assertTrue(result["has_position"])
        self.assertEqual(1.25, result["pnl_pct"])

    def test_get_account_status_uses_edge_account_route(self):
        captured_requests = []

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(200, json={"account_balance": 1000.0, "available": 750.0}, request=request)

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="edge-key")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                return await client.get_account_status()
            finally:
                await client.aclose()

        result = asyncio.run(run())

        self.assertEqual("/api/edge/account/status", captured_requests[0].url.path)
        self.assertEqual(1000.0, result["account_balance"])

    def test_structured_handoff_sends_idempotency_and_mode_headers(self):
        captured_requests = []
        idempotency_key = "edge:AAPL:buy:market_open:123:test"

        async def handler(request: httpx.Request):
            captured_requests.append(request)
            return httpx.Response(202, json={"accepted": True, "handoff_id": "ph-headers"}, request=request)

        async def run():
            client = PulseClient(base_url="http://pulse.invalid", api_key="edge-key")
            await client._client.aclose()
            client._client = httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                timeout=client.TIMEOUT_SECONDS,
                headers=client._build_headers(),
            )
            client.pulse_available = True
            try:
                with patch.dict(os.environ, {"PULSE_HANDOFF_ENDPOINT": "/api/edge/handoff"}):
                    return await client.send_handoff_command(
                        {
                            "symbol": "aapl",
                            "action": "buy",
                            "confidence": 0.8,
                            "reason": "test",
                            "mode": "paper",
                            "orb_session": "market_open",
                            "idempotency_key": idempotency_key,
                            "source": "sentinel_edge",
                            "created_at": 1760000000.0,
                            "metadata": {},
                        }
                    )
            finally:
                await client.aclose()

        with (
            patch.object(logging.getLogger("httpx"), "disabled", True),
            patch.object(logging.getLogger("pulse_client"), "disabled", True),
        ):
            result = asyncio.run(run())

        self.assertTrue(result["sent"])
        self.assertEqual(len(captured_requests), 1)
        request = captured_requests[0]
        self.assertEqual(request.headers.get("Idempotency-Key"), idempotency_key)
        self.assertEqual(request.headers.get("X-Edge-Mode"), "paper")
        self.assertEqual(request.headers.get("X-Edge-Contract-Version"), "edge.pulse.handoff.v1")
        self.assertEqual(request.headers.get("X-API-Key"), "edge-key")

    def test_invalid_handoff_payload_is_suppressed_before_transport(self):
        async def run():
            client = PulseClient(base_url="http://pulse.invalid")
            client.pulse_available = True
            client.send_decision = AsyncMock(return_value=True)
            try:
                result = await client.send_handoff_command(
                    {
                        "symbol": "AAPL",
                        "action": "buy",
                        "confidence": 0.8,
                        "reason": "test",
                        "mode": "recommend_only",
                        "orb_session": "market_open",
                        "idempotency_key": "edge:AAPL:buy:test",
                        "source": "sentinel_edge",
                        "created_at": 1760000000.0,
                        "metadata": {},
                    }
                )
                return result, client.send_decision.await_count
            finally:
                await client.aclose()

        with self.assertLogs("pulse_client", level="WARNING"):
            result, send_count = asyncio.run(run())

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "suppressed")
        self.assertEqual(result["reason"], "invalid_handoff_contract")
        self.assertEqual(send_count, 0)

    def test_invalid_handoff_feedback_validation_errors_are_json_safe(self):
        async def run():
            client = PulseClient(base_url="http://pulse.invalid")
            client.pulse_available = True
            client.send_decision = AsyncMock(return_value=True)
            try:
                return await client.send_handoff_command(
                    {
                        "symbol": "AAPL",
                        "action": "trailing_stop",
                        "confidence": 0.8,
                        "reason": "test",
                        "mode": "paper",
                        "orb_session": "market_open",
                        "stop_type": "trailing",
                        "idempotency_key": "edge:AAPL:trailing_stop:test",
                        "source": "sentinel_edge",
                        "created_at": 1760000000.0,
                        "metadata": {},
                    }
                )
            finally:
                await client.aclose()

        with self.assertLogs("pulse_client", level="WARNING"):
            result = asyncio.run(run())

        self.assertEqual(result["reason"], "invalid_handoff_contract")
        self.assertIn("validation_errors", result)
        try:
            json.dumps(result["validation_errors"])
        except TypeError as exc:
            self.fail(f"validation_errors must be JSON serializable: {exc}")

    def test_acceptance_feedback_preserves_pulse_response(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=202,
            response_body={"accepted": True, "handoff_id": "ph-123"},
        )

        self.assertTrue(result["sent"])
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["reason"], "pulse_accepted")
        self.assertEqual(result["endpoint"], "/api/edge/handoff")
        self.assertEqual(result["status_code"], 202)
        self.assertEqual(result["handoff_id"], "ph-123")
        self.assertEqual(result["response"]["handoff_id"], "ph-123")

    def test_rejection_feedback_preserves_rejection_reason(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=200,
            response_body={"accepted": False, "reason": "risk_limit", "message": "Buying power exhausted"},
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "risk_limit")
        self.assertEqual(result["message"], "Buying power exhausted")
        self.assertEqual(result["response"]["message"], "Buying power exhausted")

    def test_sent_false_feedback_is_not_treated_as_accepted(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=200,
            response_body={"sent": False, "reason": "risk_limit", "message": "Buying power exhausted"},
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "risk_limit")
        self.assertEqual(result["message"], "Buying power exhausted")
        self.assertEqual(result["response"]["sent"], False)

    def test_failed_feedback_promotes_operator_message(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=422,
            response_body={"error": "schema_mismatch", "message": "Pulse contract version is unsupported"},
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "schema_mismatch")
        self.assertEqual(result["message"], "Pulse contract version is unsupported")

    def test_failed_status_is_not_treated_as_rejection(self):
        result = PulseClient.normalise_handoff_feedback(
            endpoint="/api/edge/handoff",
            status_code=200,
            response_body={"status": "failed", "error": "schema_mismatch"},
        )

        self.assertFalse(result["sent"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["reason"], "schema_mismatch")

    def test_legacy_payload_preserves_stop_trail_and_dca_fields(self):
        payload = {
            "reason": "scale in",
            "confidence": 0.9,
            "idempotency_key": "edge:AAPL:dca:test",
            "source": "sentinel_edge",
            "mode": "paper",
            "orb_session": "market_open",
            "stop_type": "trailing",
            "trailing_percent": 1.25,
            "dca": {"steps": 2, "interval_seconds": 60},
            "metadata": {"source": "test"},
        }

        legacy = PulseClient.legacy_handoff_payload(payload)

        self.assertEqual(legacy["stop_type"], "trailing")
        self.assertEqual(legacy["trailing_percent"], 1.25)
        self.assertEqual(legacy["dca"], {"steps": 2, "interval_seconds": 60})


if __name__ == "__main__":
    unittest.main()
