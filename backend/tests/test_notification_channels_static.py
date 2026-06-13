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
        self.assertIn("notification_confirmation_feedback", text)
        self.assertIn("notification_confirmation_preview", text)
        self.assertIn('@api_router.get("/notifications/status")', text)
        self.assertIn('@api_router.post("/notifications/confirmation/preview")', text)
        self.assertIn('@api_router.post("/notifications/confirmation/feedback")', text)
        notification_text = (ROOT / "backend" / "notification_channels.py").read_text(encoding="utf-8")
        self.assertIn("edge.notifications.status.v1", notification_text)
        self.assertIn("edge.notifications.confirmation_preview.v1", notification_text)
        self.assertIn("edge.notifications.confirmation_feedback.v1", notification_text)

    def test_settings_surfaces_operator_notification_paths(self):
        text = SETTINGS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("notificationsStatus", text)
        self.assertIn("api.getNotificationsStatus()", text)
        self.assertIn("Operator notification paths", text)
        self.assertIn("Telegram", text)
        self.assertIn("Discord", text)
        self.assertIn("WhatsApp", text)
        self.assertIn("secret_values", text)
        self.assertIn("confirmation_actions", text)
        self.assertIn("confirmation_feedback", text)
        self.assertIn("Confirmation workflows", text)
        self.assertIn("Feedback contract", text)
        self.assertIn("feedback_decisions", text)
        self.assertIn("idempotency_fields", text)
        self.assertIn("operator notification channel discovery", readme)
        self.assertIn("notification confirmation preview contract", readme)
        self.assertIn("notification confirmation feedback contract", readme)
        self.assertIn("mode/target idempotency scope", readme)


if __name__ == "__main__":
    unittest.main()
