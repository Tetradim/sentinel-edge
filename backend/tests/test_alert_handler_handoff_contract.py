"""Alertmanager root webhook contract tests."""
import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import alert_handler  # noqa: E402


class _FakePulseClient:
    def __init__(self):
        self.calls = []

    async def post(self, path: str, json=None, headers=None):
        self.calls.append({"path": path, "json": json or {}, "headers": headers or {}})
        return True


def _basic_auth(user: str = "sentinel-edge", password: str = "secret") -> dict:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


class AlertHandlerHandoffContractTests(unittest.TestCase):
    def _client(self) -> TestClient:
        app = FastAPI()
        app.include_router(alert_handler.router)
        return TestClient(app)

    def test_alerts_requires_basic_auth_when_webhook_secret_set(self):
        fake = _FakePulseClient()

        with (
            patch.object(alert_handler, "pulse_client", fake),
            patch.object(alert_handler, "_WEBHOOK_USER", "sentinel-edge", create=True),
            patch.object(alert_handler, "_WEBHOOK_SECRET", "secret", create=True),
        ):
            response = self._client().post("/alerts", json={"alerts": []})

        self.assertEqual(401, response.status_code)
        self.assertEqual([], fake.calls)

    def test_bearish_cluster_alert_posts_stop_buying_handoff_with_edge_api_key(self):
        fake = _FakePulseClient()
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "BearishClusterOverride",
                        "action": "bearish_cluster",
                        "symbol": "aapl",
                    },
                    "annotations": {"summary": "bearish cluster detected"},
                }
            ]
        }

        with (
            patch.object(alert_handler, "pulse_client", fake),
            patch.object(alert_handler, "_WEBHOOK_USER", "sentinel-edge", create=True),
            patch.object(alert_handler, "_WEBHOOK_SECRET", "secret", create=True),
            patch.object(alert_handler, "_EDGE_API_KEY", "edge-key", create=True),
        ):
            response = self._client().post("/alerts", json=payload, headers=_basic_auth())

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(fake.calls))
        call = fake.calls[0]
        self.assertEqual("/api/edge/handoff", call["path"])
        self.assertEqual("edge-key", call["headers"].get("X-API-Key"))
        self.assertEqual("AAPL", call["json"]["symbol"])
        self.assertEqual("stop_buying", call["json"]["action"])
        self.assertEqual("edge.pulse.handoff.v1", call["json"]["contract_version"])
        self.assertIn("edge:AAPL:stop_buying:market_open:", call["json"]["idempotency_key"])

    def test_global_risk_reduction_posts_global_tighten_trailing_handoff(self):
        fake = _FakePulseClient()
        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "CriticalBearishCorrelation",
                        "action": "global_risk_reduction",
                        "trailing_percent": "0.75",
                    },
                    "annotations": {"summary": "portfolio risk elevated"},
                }
            ]
        }

        with (
            patch.object(alert_handler, "pulse_client", fake),
            patch.object(alert_handler, "_WEBHOOK_USER", "sentinel-edge", create=True),
            patch.object(alert_handler, "_WEBHOOK_SECRET", "secret", create=True),
            patch.object(alert_handler, "_EDGE_API_KEY", "edge-key", create=True),
        ):
            response = self._client().post("/alerts", json=payload, headers=_basic_auth())

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(fake.calls))
        handoff = fake.calls[0]["json"]
        self.assertEqual("GLOBAL", handoff["symbol"])
        self.assertEqual("tighten_trailing_stop", handoff["action"])
        self.assertEqual("tighten_trailing", handoff["stop_type"])
        self.assertEqual(0.75, handoff["trailing_percent"])

    def test_alertmanager_edge_webhook_targets_edge_service_port(self):
        text = (ROOT / "prometheus" / "alertmanager.yml").read_text(encoding="utf-8")

        self.assertIn("url: 'http://sentinel-edge:8001/alerts'", text)
        self.assertNotIn("url: 'http://sentinel-edge:8000/alerts'", text)

    def test_analyst_override_path_uses_structured_handoff_not_legacy_control_route(self):
        text = (BACKEND / "analyst" / "core.py").read_text(encoding="utf-8")

        self.assertIn("/api/edge/handoff", text)
        self.assertIn("tighten_trailing_global", text)
        self.assertIn("emergency_exit_all", text)
        self.assertNotIn("/control/override", text)

    def test_correlation_override_path_uses_structured_handoff_not_legacy_control_route(self):
        text = (BACKEND / "analyst" / "correlation" / "engine.py").read_text(encoding="utf-8")

        self.assertIn("/api/edge/handoff", text)
        self.assertIn("tighten_trailing_stop", text)
        self.assertNotIn("/control/override", text)


if __name__ == "__main__":
    unittest.main()
