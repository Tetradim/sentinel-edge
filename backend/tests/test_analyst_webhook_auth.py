import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from analyst.webhook import alert_handler  # noqa: E402


def _basic_auth(user: str = "sentinel-edge", password: str = "secret") -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


class AnalystWebhookAuthTests(unittest.TestCase):
    def _client(self) -> TestClient:
        app = FastAPI()
        app.include_router(alert_handler.router)
        return TestClient(app)

    def test_post_webhooks_fail_closed_when_webhook_secret_is_missing(self):
        payload = {"alerts": []}

        with patch.object(alert_handler, "_WEBHOOK_SECRET", "", create=True):
            for path in ("/webhook/alert", "/webhook/pulse-override", "/webhook/general"):
                with self.subTest(path=path):
                    response = self._client().post(path, json=payload)

                    self.assertEqual(503, response.status_code)
                    self.assertIn("WEBHOOK_SECRET", response.json()["detail"])

    def test_post_webhooks_require_basic_auth_when_webhook_secret_is_configured(self):
        payload = {"alerts": []}

        with (
            patch.object(alert_handler, "_WEBHOOK_USER", "sentinel-edge", create=True),
            patch.object(alert_handler, "_WEBHOOK_SECRET", "secret", create=True),
        ):
            for path in ("/webhook/alert", "/webhook/pulse-override", "/webhook/general"):
                with self.subTest(path=path):
                    response = self._client().post(path, json=payload)

                    self.assertEqual(401, response.status_code)

    def test_health_remains_available_without_webhook_secret(self):
        with patch.object(alert_handler, "_WEBHOOK_SECRET", "", create=True):
            response = self._client().get("/webhook/health")

        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json()["status"])
        self.assertFalse(response.json()["auth_enabled"])

    def test_configured_secret_and_matching_basic_auth_allows_empty_payloads(self):
        payload = {"alerts": []}

        with (
            patch.object(alert_handler, "_WEBHOOK_USER", "sentinel-edge", create=True),
            patch.object(alert_handler, "_WEBHOOK_SECRET", "secret", create=True),
        ):
            response = self._client().post(
                "/webhook/alert",
                json=payload,
                headers=_basic_auth(),
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("no_alerts", response.json()["status"])


if __name__ == "__main__":
    unittest.main()
