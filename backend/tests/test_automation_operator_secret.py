"""Operator-secret gate tests for live automation escalation."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import server  # noqa: E402
from automation import AutomationMode  # noqa: E402


def _request(headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/api/automation",
            "headers": encoded_headers,
        }
    )


class FakeAutomationSettings:
    def __init__(self):
        self.global_enabled = False
        self.mode = AutomationMode.RECOMMEND_ONLY
        self.default_ticker_enabled = False
        self.per_ticker_enabled = {}
        self.min_confidence = 0.6
        self.cooldown_seconds = 60
        self.quiet_when_pulse_absent = True

    def public_dict(self):
        return {
            "global_enabled": self.global_enabled,
            "mode": self.mode.value,
            "default_ticker_enabled": self.default_ticker_enabled,
            "per_ticker_enabled": dict(self.per_ticker_enabled),
            "min_confidence": self.min_confidence,
            "cooldown_seconds": self.cooldown_seconds,
            "quiet_when_pulse_absent": self.quiet_when_pulse_absent,
        }


class FakeAutomation:
    def __init__(self):
        self.settings = FakeAutomationSettings()

    def status(self):
        return {"settings": self.settings.public_dict()}

    def update_settings(self, patch):
        if "global_enabled" in patch:
            self.settings.global_enabled = bool(patch["global_enabled"])
        if "mode" in patch:
            self.settings.mode = AutomationMode(str(patch["mode"]))
        if "default_ticker_enabled" in patch:
            self.settings.default_ticker_enabled = bool(patch["default_ticker_enabled"])
        if "per_ticker_enabled" in patch:
            self.settings.per_ticker_enabled = {
                str(symbol).upper(): bool(enabled)
                for symbol, enabled in patch["per_ticker_enabled"].items()
            }
        return self.settings

    def set_ticker(self, symbol, enabled):
        self.settings.per_ticker_enabled[symbol.upper()] = bool(enabled)
        return self.settings


class FakeScheduler:
    def __init__(self):
        self.automation = FakeAutomation()
        self.active_tickers = []

    def add_ticker(self, symbol):
        if symbol not in self.active_tickers:
            self.active_tickers.append(symbol)

    def remove_ticker(self, symbol):
        if symbol in self.active_tickers:
            self.active_tickers.remove(symbol)


class AutomationOperatorSecretTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.previous_scheduler = server.scheduler
        server.scheduler = FakeScheduler()

    def tearDown(self):
        server.scheduler = self.previous_scheduler

    async def test_live_automation_mode_requires_operator_secret(self):
        body = server.AutomationSettingsBody(mode=AutomationMode.LIVE)

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.update_automation_settings(body, _request())

        self.assertEqual(401, raised.exception.status_code)

    async def test_live_automation_mode_requires_readiness_signoff_after_operator_secret(self):
        body = server.AutomationSettingsBody(mode=AutomationMode.LIVE)

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.update_automation_settings(
                    body,
                    _request({"X-Edge-Operator-Secret": "correct-secret"}),
                )

        self.assertEqual(409, raised.exception.status_code)
        self.assertEqual("live_automation_readiness_signoff_required", raised.exception.detail["error"])

    async def test_matching_operator_secret_can_enable_live_automation(self):
        body = server.AutomationSettingsBody(
            mode=AutomationMode.LIVE,
            global_enabled=True,
            default_ticker_enabled=True,
            live_readiness_signoff="ENABLE LIVE AUTOMATION",
        )

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.update_automation_settings(
                body,
                _request({"X-Edge-Operator-Secret": "correct-secret"}),
            )

        self.assertEqual("live", response["settings"]["mode"])
        self.assertTrue(response["settings"]["global_enabled"])
        self.assertTrue(response["settings"]["default_ticker_enabled"])

    async def test_recommend_only_and_paper_changes_do_not_require_operator_secret(self):
        body = server.AutomationSettingsBody(mode=AutomationMode.PAPER, global_enabled=True)

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            response = await server.update_automation_settings(body, _request())

        self.assertEqual("paper", response["settings"]["mode"])
        self.assertTrue(response["settings"]["global_enabled"])

    async def test_enabling_ticker_handoff_while_live_requires_operator_secret(self):
        server.scheduler.automation.settings.mode = AutomationMode.LIVE
        server.scheduler.automation.settings.global_enabled = True
        body = server.TickerAutomationBody(enabled=True)

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.update_ticker_automation("SPY", body, _request())

        self.assertEqual(401, raised.exception.status_code)

    async def test_matching_operator_secret_can_enable_ticker_handoff_while_live(self):
        server.scheduler.automation.settings.mode = AutomationMode.LIVE
        server.scheduler.automation.settings.global_enabled = True
        body = server.TickerAutomationBody(enabled=True)

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.update_ticker_automation(
                "SPY",
                server.TickerAutomationBody(enabled=True, live_readiness_signoff="ENABLE LIVE AUTOMATION"),
                _request({"X-Edge-Operator-Secret": "correct-secret"}),
            )

        self.assertTrue(response["settings"]["per_ticker_enabled"]["SPY"])

    async def test_adding_ticker_while_live_default_handoff_requires_operator_secret(self):
        server.scheduler.automation.settings.mode = AutomationMode.LIVE
        server.scheduler.automation.settings.global_enabled = True
        server.scheduler.automation.settings.default_ticker_enabled = True

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.add_ticker("SPY", _request())

        self.assertEqual(401, raised.exception.status_code)
        self.assertNotIn("SPY", server.scheduler.active_tickers)

    async def test_matching_operator_secret_can_add_ticker_while_live_default_handoff_enabled(self):
        server.scheduler.automation.settings.mode = AutomationMode.LIVE
        server.scheduler.automation.settings.global_enabled = True
        server.scheduler.automation.settings.default_ticker_enabled = True

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.add_ticker(
                "SPY",
                _request({
                    "X-Edge-Operator-Secret": "correct-secret",
                    "X-Edge-Live-Readiness-Signoff": "ENABLE LIVE AUTOMATION",
                }),
            )

        self.assertEqual({"message": "Added SPY to watch list"}, response)
        self.assertIn("SPY", server.scheduler.active_tickers)

    async def test_adding_ticker_in_recommend_only_mode_does_not_require_operator_secret(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            response = await server.add_ticker("SPY", _request())

        self.assertEqual({"message": "Added SPY to watch list"}, response)
        self.assertIn("SPY", server.scheduler.active_tickers)

    async def test_removing_ticker_while_live_automation_requires_operator_secret(self):
        server.scheduler.active_tickers = ["SPY"]
        server.scheduler.automation.settings.mode = AutomationMode.LIVE
        server.scheduler.automation.settings.global_enabled = True

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.remove_ticker("SPY", _request())

        self.assertEqual(401, raised.exception.status_code)
        self.assertIn("SPY", server.scheduler.active_tickers)

    async def test_matching_operator_secret_can_remove_ticker_while_live_automation_is_active(self):
        server.scheduler.active_tickers = ["SPY"]
        server.scheduler.automation.settings.mode = AutomationMode.LIVE
        server.scheduler.automation.settings.global_enabled = True

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.remove_ticker(
                "SPY",
                _request({
                    "X-Edge-Operator-Secret": "correct-secret",
                    "X-Edge-Live-Readiness-Signoff": "ENABLE LIVE AUTOMATION",
                }),
            )

        self.assertEqual({"message": "Removed SPY from watch list"}, response)
        self.assertNotIn("SPY", server.scheduler.active_tickers)

    async def test_removing_ticker_in_recommend_only_mode_does_not_require_operator_secret(self):
        server.scheduler.active_tickers = ["SPY"]

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            response = await server.remove_ticker("SPY", _request())

        self.assertEqual({"message": "Removed SPY from watch list"}, response)
        self.assertNotIn("SPY", server.scheduler.active_tickers)

    def test_removing_ticker_route_is_guarded_when_live_automation_is_active(self):
        text = (BACKEND / "server.py").read_text(encoding="utf-8")

        start = text.index('@api_router.delete("/tickers/{symbol}")')
        next_route = text.find("\n@api_router.", start + 1)
        segment = text[start : next_route if next_route != -1 else len(text)]

        self.assertIn("request: Request", segment)
        self.assertIn("_remove_ticker_requires_operator_secret", text)
        self.assertIn("_require_operator_action_secret(request)", segment)


if __name__ == "__main__":
    unittest.main()
