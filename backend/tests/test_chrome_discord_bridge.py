"""Chrome Discord bridge route contract tests."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class ChromeDiscordBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.old_event_dir = os.environ.get("BOT_EVENT_BUS_DIR")
        os.environ["BOT_EVENT_BUS_DIR"] = self.tmpdir.name

    def tearDown(self):
        if self.old_event_dir is None:
            os.environ.pop("BOT_EVENT_BUS_DIR", None)
        else:
            os.environ["BOT_EVENT_BUS_DIR"] = self.old_event_dir
        self.tmpdir.cleanup()

    def test_bridge_message_publishes_signal_observed(self):
        from chrome_bridge_routes import router
        from shared.bot_event_bus import event_bus

        app = FastAPI()
        app.include_router(router, prefix="/api")
        client = TestClient(app)

        response = client.post(
            "/api/discord/chrome-bridge/message",
            json={
                "event_id": "edge-chrome-1",
                "channel_id": "123",
                "channel_name": "mike-alerts",
                "channel_url": "https://discord.com/channels/1/123",
                "bridge_target_id": "sentinel-edge",
                "bridge_target_name": "Sentinel Edge",
                "author_name": "MikeInvesting [MIKE]",
                "content": "$SPY\n$744 PUTS\nEXPIRATION 6/22/2026\n$.4 Entry\n@everyone alert",
                "observed_at": "2026-06-22T14:23:00+00:00",
            },
        )
        events = event_bus.recent(event_type="signal.observed")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "accepted")
        self.assertEqual(events[0]["source_bot"], "chrome-discord-bridge")
        self.assertEqual(events[0]["target_bots"], ["sentinel-edge"])
        self.assertEqual(events[0]["payload"]["contract_version"], "chrome.discord.message.v1")
        self.assertEqual(events[0]["payload"]["bridge_target_id"], "sentinel-edge")

    def test_bridge_heartbeat_records_health(self):
        from chrome_bridge_routes import get_bridge_health, router
        from shared.bot_event_bus import event_bus

        app = FastAPI()
        app.include_router(router, prefix="/api")
        client = TestClient(app)

        response = client.post(
            "/api/discord/chrome-bridge/heartbeat",
            json={
                "status": "ok",
                "bridge_enabled": True,
                "channel_id": "123",
                "channel_url": "https://discord.com/channels/1/123",
                "bridge_target_id": "sentinel-edge",
                "observed_at": "2026-06-22T14:23:30+00:00",
            },
        )
        health = get_bridge_health()
        events = event_bus.recent(event_type="bridge.health")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "healthy")
        self.assertTrue(health["healthy"])
        self.assertEqual(events[0]["payload"]["bridge_target_id"], "sentinel-edge")


if __name__ == "__main__":
    unittest.main()
