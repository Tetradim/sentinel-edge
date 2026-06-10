"""Tests for browser-safe operator notification channel discovery."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notification_channels import notification_channel_status


class NotificationChannelStatusTests(unittest.TestCase):
    def test_status_reports_channel_configuration_without_secret_values(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "telegram-secret-token",
            "TELEGRAM_TRADING_CHAT": "12345",
            "SLACK_WEBHOOK_URL": "http://placeholder/no-slack",
            "DISCORD_WEBHOOK_URL": "https://discord.example/webhook",
            "WHATSAPP_WEBHOOK_URL": "",
        }

        status = notification_channel_status(env)
        channels = {channel["id"]: channel for channel in status["channels"]}

        self.assertEqual(status["schema_version"], "edge.notifications.status.v1")
        self.assertEqual(status["secret_values"], "redacted")
        self.assertTrue(channels["telegram"]["configured"])
        self.assertTrue(channels["discord"]["configured"])
        self.assertFalse(channels["slack"]["configured"])
        self.assertFalse(channels["whatsapp"]["configured"])
        self.assertIn("SLACK_WEBHOOK_URL", channels["slack"]["missing_env"])
        self.assertIn("WHATSAPP_WEBHOOK_URL", channels["whatsapp"]["missing_env"])
        rendered = repr(status)
        self.assertNotIn("telegram-secret-token", rendered)
        self.assertNotIn("https://discord.example/webhook", rendered)

    def test_zero_chat_and_placeholder_urls_are_not_configured(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "token",
            "TELEGRAM_TRADING_CHAT": "0",
            "SLACK_WEBHOOK_URL": "http://placeholder/no-slack",
            "DISCORD_WEBHOOK_URL": "placeholder",
            "WHATSAPP_WEBHOOK_URL": "placeholder",
        }

        channels = {channel["id"]: channel for channel in notification_channel_status(env)["channels"]}

        self.assertFalse(channels["telegram"]["configured"])
        self.assertIn("TELEGRAM_TRADING_CHAT", channels["telegram"]["missing_env"])
        self.assertFalse(channels["slack"]["configured"])
        self.assertFalse(channels["discord"]["configured"])
        self.assertFalse(channels["whatsapp"]["configured"])


if __name__ == "__main__":
    unittest.main()
