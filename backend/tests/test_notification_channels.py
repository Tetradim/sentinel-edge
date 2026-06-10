"""Tests for browser-safe operator notification channel discovery."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notification_channels import (
    notification_channel_status,
    notification_confirmation_feedback,
    notification_confirmation_preview,
)


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

    def test_status_lists_confirmation_actions_without_delivery_side_effects(self):
        status = notification_channel_status({})
        actions = {action["id"]: action for action in status["confirmation_actions"]}

        self.assertEqual(
            status["confirmation_preview"]["schema_version"],
            "edge.notifications.confirmation_preview.v1",
        )
        self.assertEqual(status["confirmation_preview"]["send_side_effect"], "none_preview_only")
        self.assertEqual(
            status["confirmation_feedback"]["schema_version"],
            "edge.notifications.confirmation_feedback.v1",
        )
        self.assertEqual(status["confirmation_feedback"]["pulse_side_effect"], "none")
        self.assertEqual(status["confirmation_feedback"]["accepted_decisions"], ["approved", "rejected", "expired"])
        self.assertEqual(
            status["confirmation_feedback"]["idempotency_fields"],
            ["namespace", "mode", "action_type", "target"],
        )
        self.assertIn("live_handoff", actions)
        self.assertIn("emergency_exit", actions)
        self.assertIn("trailing_stop", actions)
        self.assertTrue(actions["live_handoff"]["requires_confirmation"])
        self.assertEqual(actions["emergency_exit"]["risk"], "critical")

    def test_confirmation_preview_redacts_metadata_and_selects_channels(self):
        env = {
            "TELEGRAM_BOT_TOKEN": "telegram-secret-token",
            "TELEGRAM_TRADING_CHAT": "12345",
            "DISCORD_WEBHOOK_URL": "https://discord.example/webhook",
        }

        preview = notification_confirmation_preview(
            "live_handoff",
            symbol="spy",
            mode="live",
            channel_ids=["telegram"],
            reason="Opening range breakout",
            metadata={
                "confidence": 0.91,
                "api_key": "should-not-render",
                "broker_key": "key-hidden",
                "nested": {"auth_token": "also-hidden", "note": "visible"},
            },
            env=env,
        )

        self.assertEqual(preview["schema_version"], "edge.notifications.confirmation_preview.v1")
        self.assertEqual(preview["action_type"], "live_handoff")
        self.assertEqual(preview["mode"], "live")
        self.assertEqual(preview["context"]["symbol"], "SPY")
        self.assertEqual(preview["safety"]["send_side_effect"], "none_preview_only")
        self.assertEqual(preview["channels"][0]["id"], "telegram")
        self.assertTrue(preview["channels"][0]["configured"])
        self.assertEqual(preview["context"]["metadata"]["api_key"], "[redacted]")
        self.assertEqual(preview["context"]["metadata"]["broker_key"], "[redacted]")
        self.assertEqual(preview["context"]["metadata"]["nested"]["auth_token"], "[redacted]")
        self.assertIn("edge:notification-confirmation:live:live_handoff:spy", preview["idempotency_key"])
        rendered = repr(preview)
        self.assertNotIn("telegram-secret-token", rendered)
        self.assertNotIn("should-not-render", rendered)
        self.assertNotIn("key-hidden", rendered)
        self.assertNotIn("also-hidden", rendered)

    def test_confirmation_preview_rejects_unknown_channels(self):
        with self.assertRaises(ValueError):
            notification_confirmation_preview(
                "live_handoff",
                channel_ids=["telegram", "unknown-relay"],
                env={},
            )

    def test_confirmation_feedback_normalizes_approval_without_side_effects(self):
        feedback = notification_confirmation_feedback(
            idempotency_key="edge:notification-confirmation:live:live_handoff:spy",
            action_type="live_handoff",
            decision="approve",
            channel_id="telegram",
            operator_ref="@sentinel-operator",
            reason="ORB breakout confirmed",
            metadata={"confidence": 0.92, "webhook_secret": "do-not-render"},
        )

        self.assertEqual(feedback["schema_version"], "edge.notifications.confirmation_feedback.v1")
        self.assertEqual(feedback["idempotency_key"], "edge:notification-confirmation:live:live_handoff:spy")
        self.assertEqual(feedback["action_type"], "live_handoff")
        self.assertEqual(feedback["mode"], "live")
        self.assertEqual(feedback["target"], "SPY")
        self.assertEqual(feedback["channel_id"], "telegram")
        self.assertEqual(feedback["decision"], "approved")
        self.assertTrue(feedback["accepted"])
        self.assertEqual(feedback["paper_live_semantics"], "Paper mode can rehearse the prompt; live mode must wait for an operator approval.")
        self.assertEqual(feedback["idempotency_scope"]["mode"], "live")
        self.assertEqual(feedback["idempotency_scope"]["action_type"], "live_handoff")
        self.assertEqual(feedback["idempotency_scope"]["target"], "SPY")
        self.assertEqual(feedback["safety"]["pulse_side_effect"], "none")
        self.assertEqual(feedback["safety"]["notification_side_effect"], "none")
        self.assertEqual(feedback["context"]["metadata"]["webhook_secret"], "[redacted]")
        rendered = repr(feedback)
        self.assertNotIn("do-not-render", rendered)

    def test_confirmation_feedback_rejects_bad_idempotency_and_channel(self):
        with self.assertRaises(ValueError):
            notification_confirmation_feedback(
                idempotency_key="edge:bad-prefix",
                action_type="live_handoff",
                decision="approve",
                channel_id="telegram",
            )

        with self.assertRaises(ValueError):
            notification_confirmation_feedback(
                idempotency_key="edge:notification-confirmation:paper:live_handoff:spy",
                action_type="live_handoff",
                decision="approve",
                channel_id="unknown-relay",
            )

        with self.assertRaises(ValueError):
            notification_confirmation_feedback(
                idempotency_key="edge:notification-confirmation:paper:trailing_stop:spy",
                action_type="live_handoff",
                decision="approve",
                channel_id="telegram",
            )

        with self.assertRaises(ValueError):
            notification_confirmation_feedback(
                idempotency_key="edge:notification-confirmation:backtest:live_handoff:spy",
                action_type="live_handoff",
                decision="approve",
                channel_id="telegram",
            )

        with self.assertRaises(ValueError):
            notification_confirmation_feedback(
                idempotency_key="edge:notification-confirmation:live:live_handoff:",
                action_type="live_handoff",
                decision="approve",
                channel_id="telegram",
            )


if __name__ == "__main__":
    unittest.main()
