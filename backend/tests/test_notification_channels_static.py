"""Static coverage for notification channel discovery UI and API."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "backend" / "server.py"
SETTINGS = ROOT / "frontend" / "src" / "components" / "dashboards" / "SettingsDashboard.tsx"
README = ROOT / "README.md"


class NotificationChannelStaticTests(unittest.TestCase):
    def test_server_exposes_notification_status_endpoint(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("notification_channel_status", text)
        self.assertIn('@api_router.get("/notifications/status")', text)
        self.assertIn("edge.notifications.status.v1", (ROOT / "backend" / "notification_channels.py").read_text(encoding="utf-8"))

    def test_settings_surfaces_operator_notification_paths(self):
        text = SETTINGS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("notificationsStatus", text)
        self.assertIn("/api/notifications/status", text)
        self.assertIn("Operator notification paths", text)
        self.assertIn("Telegram", text)
        self.assertIn("Discord", text)
        self.assertIn("WhatsApp", text)
        self.assertIn("secret_values", text)
        self.assertIn("operator notification channel discovery", readme)


if __name__ == "__main__":
    unittest.main()
