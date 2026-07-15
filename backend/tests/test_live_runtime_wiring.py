import asyncio
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from automation import (
    AutomationAction,
    AutomationController,
    AutomationMode,
    AutomationSettings,
    HandoffCommand,
)
from pulse_client import PulseClient
import runtime_mode  # noqa: F401  installs production live behavior


def _settings():
    return AutomationSettings(
        global_enabled=True,
        mode=AutomationMode.LIVE,
        default_ticker_enabled=True,
        min_confidence=0.1,
        cooldown_seconds=0,
    )


def _command(created_at=1_800_000_000.0):
    return HandoffCommand(
        symbol="ASTS",
        action=AutomationAction.BUY,
        confidence=0.9,
        reason="runtime wiring test",
        mode=AutomationMode.LIVE,
        created_at=created_at,
        metadata={"price": 90.0, "signal_strength": 8.0, "trend": "bullish"},
    )


def test_runtime_installs_pending_command_and_safe_delivery_methods():
    assert AutomationController.plan.__name__ == "_plan_with_pending"
    assert AutomationController.record_sent.__name__ == "_record_sent_with_pending"
    assert PulseClient.send_handoff_command.__name__ == "_send_handoff_without_ambiguous_legacy_fallback"


def test_ambiguous_delivery_never_calls_legacy_execution(monkeypatch):
    client = PulseClient(base_url="http://pulse", api_key="configured")
    client.pulse_available = True
    calls = {"structured": 0, "legacy": 0}

    async def failed_structured(*_args, **_kwargs):
        calls["structured"] += 1
        return {"sent": False, "status": "failed", "reason": "pulse_timeout", "status_code": None}

    async def legacy(*_args, **_kwargs):
        calls["legacy"] += 1
        return True

    monkeypatch.setattr(client, "_post_with_feedback", failed_structured)
    monkeypatch.setattr(client, "send_decision", legacy)

    result = asyncio.run(client.send_handoff_command(_command().payload()))
    assert calls == {"structured": 1, "legacy": 0}
    assert result["ambiguous_delivery"] is True
    assert result["reconciliation_required"] is True


def test_ambiguous_command_reuses_same_id_after_restart(tmp_path):
    state_path = tmp_path / "automation.json"
    first_controller = AutomationController(settings=_settings(), state_path=state_path)
    first = _command()
    assert first_controller.plan(first) == (True, "allowed")
    first_controller.record_sent(
        first,
        {
            "sent": False,
            "status": "failed",
            "reason": "pulse_timeout",
            "ambiguous_delivery": True,
        },
    )

    restored = AutomationController(settings=_settings(), state_path=state_path)
    retry = _command(created_at=first.created_at + 120)
    assert retry.idempotency_key != first.idempotency_key
    assert restored.plan(retry) == (True, "allowed")
    assert retry.idempotency_key == first.idempotency_key
    assert retry.metadata["pending_retry"] is True
