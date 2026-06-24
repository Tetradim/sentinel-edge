"""Operator-secret gate tests for manual Pulse action endpoints."""

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


class FakeScheduler:
    def __init__(self):
        self.paused = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False


class FakePulseClient:
    def __init__(self):
        self.calls = []

    async def start_bot(self, enable_all: bool = True):
        self.calls.append(("start", enable_all))
        return True

    async def stop_bot(self, disable_all: bool = True):
        self.calls.append(("stop", disable_all))
        return True

    async def enable_trailing_stop(self, symbol: str, trailing_percent: float):
        self.calls.append(("trailing_stop", symbol, trailing_percent))
        return True


class FakePulseScheduler:
    def __init__(self):
        self.pulse = FakePulseClient()


def _request(headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/pulse/emergency-exit/SPY",
            "headers": encoded_headers,
        }
    )


class OperatorActionSecretTests(unittest.TestCase):
    def test_missing_operator_action_secret_fails_closed(self):
        helper = getattr(server, "_require_operator_action_secret", None)
        self.assertIsNotNone(helper, "manual Pulse actions must have an operator-secret gate")
        if helper is None:
            return

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            with self.assertRaises(HTTPException) as raised:
                helper(_request())

        self.assertEqual(503, raised.exception.status_code)
        self.assertIn("EDGE_OPERATOR_ACTION_SECRET", raised.exception.detail)

    def test_wrong_operator_action_secret_is_rejected(self):
        helper = getattr(server, "_require_operator_action_secret", None)
        self.assertIsNotNone(helper, "manual Pulse actions must have an operator-secret gate")
        if helper is None:
            return

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                helper(_request({"X-Edge-Operator-Secret": "wrong-secret"}))

        self.assertEqual(401, raised.exception.status_code)

    def test_matching_operator_action_secret_is_accepted(self):
        helper = getattr(server, "_require_operator_action_secret", None)
        self.assertIsNotNone(helper, "manual Pulse actions must have an operator-secret gate")
        if helper is None:
            return

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            self.assertIsNone(
                helper(_request({"X-Edge-Operator-Secret": "correct-secret"}))
            )

    def test_manual_pulse_routes_call_operator_action_gate(self):
        text = (BACKEND / "server.py").read_text(encoding="utf-8")

        for route in (
            '@api_router.post("/pulse/emergency-exit/{symbol}")',
            '@api_router.post("/pulse/trailing-stop/{symbol}")',
            '@api_router.post("/pulse/bot/start")',
            '@api_router.post("/pulse/bot/stop")',
        ):
            start = text.index(route)
            next_route = text.find("\n@api_router.", start + 1)
            segment = text[start : next_route if next_route != -1 else len(text)]
            self.assertIn("_require_operator_action_secret(request)", segment)

    def test_docs_and_compose_require_operator_action_secret(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

        self.assertIn("EDGE_OPERATOR_ACTION_SECRET", readme)
        self.assertIn("X-Edge-Operator-Secret", readme)
        self.assertIn("EDGE_OPERATOR_ACTION_SECRET is required", compose)


class KillSwitchOperatorSecretTests(unittest.IsolatedAsyncioTestCase):
    async def test_disarming_kill_switch_requires_operator_secret(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.toggle_kill_switch(False, _request())

        self.assertEqual(401, raised.exception.status_code)

    async def test_matching_operator_secret_can_disarm_kill_switch(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.toggle_kill_switch(
                False,
                _request({"X-Edge-Operator-Secret": "correct-secret"}),
            )

        self.assertFalse(response["kill_switch_active"])

    async def test_arming_kill_switch_does_not_require_operator_secret(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            response = await server.toggle_kill_switch(True, _request())

        self.assertTrue(response["kill_switch_active"])

    def test_kill_switch_route_documents_disarm_guard(self):
        text = (BACKEND / "server.py").read_text(encoding="utf-8")

        start = text.index('@api_router.post("/emergency/kill-switch")')
        next_route = text.find("\n@api_router.", start + 1)
        segment = text[start : next_route if next_route != -1 else len(text)]

        self.assertIn("request: Request", segment)
        self.assertIn("if state is False:", segment)
        self.assertIn("_require_operator_action_secret(request)", segment)


class SchedulerControlOperatorSecretTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.previous_scheduler = server.scheduler
        server.scheduler = FakeScheduler()

    def tearDown(self):
        server.scheduler = self.previous_scheduler

    async def test_pause_scheduler_does_not_require_operator_secret(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": ""}):
            response = await server.pause_scheduler()

        self.assertEqual({"message": "Scheduler paused"}, response)
        self.assertTrue(server.scheduler.paused)

    async def test_resume_scheduler_requires_operator_secret(self):
        server.scheduler.paused = True

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.resume_scheduler(_request())

        self.assertEqual(401, raised.exception.status_code)
        self.assertTrue(server.scheduler.paused)

    async def test_matching_operator_secret_can_resume_scheduler(self):
        server.scheduler.paused = True

        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.resume_scheduler(
                _request({"X-Edge-Operator-Secret": "correct-secret"})
            )

        self.assertEqual({"message": "Scheduler resumed"}, response)
        self.assertFalse(server.scheduler.paused)

    def test_resume_route_calls_operator_action_gate(self):
        text = (BACKEND / "server.py").read_text(encoding="utf-8")

        start = text.index('@api_router.post("/control/resume")')
        next_route = text.find("\n@api_router.", start + 1)
        segment = text[start : next_route if next_route != -1 else len(text)]

        self.assertIn("request: Request", segment)
        self.assertIn("_require_operator_action_secret(request)", segment)


class PulseBotLifecycleOperatorSecretTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.previous_scheduler = server.scheduler
        server.scheduler = FakePulseScheduler()

    def tearDown(self):
        server.scheduler = self.previous_scheduler

    async def test_start_pulse_bot_requires_operator_secret(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.pulse_start_bot(_request())

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual([], server.scheduler.pulse.calls)

    async def test_matching_operator_secret_can_start_pulse_bot(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.pulse_start_bot(
                _request({"X-Edge-Operator-Secret": "correct-secret"}),
                enable_all=False,
            )

        self.assertEqual(
            {"status": "sent", "action": "start", "enable_all": False},
            response,
        )
        self.assertEqual([("start", False)], server.scheduler.pulse.calls)

    async def test_stop_pulse_bot_requires_operator_secret(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.pulse_stop_bot(_request())

        self.assertEqual(401, raised.exception.status_code)
        self.assertEqual([], server.scheduler.pulse.calls)

    async def test_matching_operator_secret_can_stop_pulse_bot(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            response = await server.pulse_stop_bot(
                _request({"X-Edge-Operator-Secret": "correct-secret"}),
                disable_all=False,
            )

        self.assertEqual(
            {"status": "sent", "action": "stop", "disable_all": False},
            response,
        )
        self.assertEqual([("stop", False)], server.scheduler.pulse.calls)

    async def test_trailing_stop_rejects_non_positive_percent_before_pulse_command(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.pulse_enable_trailing(
                    "SPY",
                    _request({"X-Edge-Operator-Secret": "correct-secret"}),
                    percent=0,
                )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("trailing", raised.exception.detail.lower())
        self.assertEqual([], server.scheduler.pulse.calls)

    async def test_trailing_stop_rejects_nan_percent_before_pulse_command(self):
        with patch.dict(os.environ, {"EDGE_OPERATOR_ACTION_SECRET": "correct-secret"}):
            with self.assertRaises(HTTPException) as raised:
                await server.pulse_enable_trailing(
                    "SPY",
                    _request({"X-Edge-Operator-Secret": "correct-secret"}),
                    percent=float("nan"),
                )

        self.assertEqual(422, raised.exception.status_code)
        self.assertIn("finite", raised.exception.detail.lower())
        self.assertEqual([], server.scheduler.pulse.calls)


if __name__ == "__main__":
    unittest.main()
