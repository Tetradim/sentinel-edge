import sys
from pathlib import Path
from unittest.mock import patch


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
from engine import Decision, DecisionEngine
from position_tracker import PositionTracker


def _settings(cooldown=60):
    return AutomationSettings(
        global_enabled=True,
        mode=AutomationMode.LIVE,
        default_ticker_enabled=True,
        min_confidence=0.1,
        cooldown_seconds=cooldown,
    )


def _command(action=AutomationAction.BUY, created_at=1_800_000_000.0):
    return HandoffCommand(
        symbol="asts",
        action=action,
        confidence=0.9,
        reason="range strategy",
        mode=AutomationMode.LIVE,
        created_at=created_at,
        metadata={
            "price": 90.0,
            "signal_strength": 8.0,
            "trend": "bullish",
            "target_notional": 100.0,
            "max_notional": 100.0,
        },
    )


def test_command_id_is_deterministic_for_same_decision_window():
    first = _command()
    second = _command()
    assert first.idempotency_key == second.idempotency_key
    assert _command(AutomationAction.SELL).idempotency_key != first.idempotency_key


def test_execution_intent_has_notional_and_expiry():
    command = _command()
    intent = command.execution_intent()
    assert intent["contract_version"] == "edge.execution_intent.v2"
    assert intent["quantity_policy"]["target_notional"] == 100.0
    assert intent["max_notional"] == 100.0
    assert intent["expires_at"] > command.created_at


def test_controller_ttl_is_applied_to_planned_command(tmp_path):
    settings = _settings()
    settings.command_ttl_seconds = 75
    controller = AutomationController(
        settings=settings,
        state_path=tmp_path / "automation.json",
    )
    command = _command()
    assert controller.plan(command)[0]
    assert command.execution_intent()["expires_at"] == command.created_at + 75


def test_failed_submission_does_not_start_cooldown(tmp_path):
    controller = AutomationController(
        settings=_settings(cooldown=60),
        state_path=tmp_path / "automation.json",
    )
    command = _command()
    allowed, _ = controller.plan(command)
    assert allowed

    controller.record_sent(
        command,
        {"sent": False, "status": "failed", "reason": "pulse_timeout"},
    )
    retry_allowed, retry_reason = controller.plan(command)
    assert retry_allowed
    assert retry_reason == "allowed"


def test_accepted_command_starts_symbol_cooldown_and_blocks_conflict(tmp_path):
    controller = AutomationController(
        settings=_settings(cooldown=60),
        state_path=tmp_path / "automation.json",
    )
    buy = _command(AutomationAction.BUY)
    assert controller.plan(buy)[0]
    with patch("automation.time.time", return_value=buy.created_at + 1):
        controller.record_sent(
            buy,
            {"sent": True, "status": "accepted", "reason": "pulse_accepted"},
        )
        allowed, reason = controller.plan(_command(AutomationAction.SELL))
    assert not allowed
    assert reason == "cooldown"


def test_accepted_cooldown_survives_restart(tmp_path):
    state_path = tmp_path / "automation.json"
    command = _command()
    controller = AutomationController(settings=_settings(), state_path=state_path)
    with patch("automation.time.time", return_value=command.created_at + 1):
        controller.record_sent(
            command,
            {"sent": True, "status": "accepted", "reason": "pulse_accepted"},
        )
    restored = AutomationController(state_path=state_path)
    with patch("automation.time.time", return_value=command.created_at + 2):
        assert restored.plan(command) == (False, "cooldown")


class _DecisionPositions:
    def __init__(self, position=None):
        self.position = position

    def get_position(self, _symbol):
        return self.position


def test_handoff_acceptance_does_not_create_optimistic_position():
    tracker = PositionTracker(decision_engine=_DecisionPositions(None))
    tracker.on_decision("ASTS", Decision.BUY, entry_price=90.0)
    state = tracker.get("ASTS")
    assert state["has_position"] is False
    assert state["source"] == "empty"
    assert state["last_command"] == Decision.BUY.value


def test_empty_decision_position_is_not_treated_as_open():
    tracker = PositionTracker(decision_engine=_DecisionPositions({}))
    assert tracker.get("ASTS")["has_position"] is False


def test_tracker_reads_pulse_decision_engine_position():
    tracker = PositionTracker(
        decision_engine=_DecisionPositions(
            {
                "quantity": 2,
                "entry_price": 90.0,
                "current_pnl_dollar": 20.0,
                "current_pnl_pct": 11.11,
                "trailing_enabled": True,
                "drawdown_pct": 1.2,
            }
        )
    )
    state = tracker.get("ASTS")
    assert state["has_position"] is True
    assert state["pnl"] == 20.0
    assert state["pnl_pct"] == 11.11
    assert state["trailing_enabled"] is True
    assert state["source"] == "pulse_decision_engine"


def test_command_bus_position_update_refreshes_decision_snapshot():
    engine = DecisionEngine()
    engine.update_position_state(
        symbol="ASTS",
        position_size=3.5,
        entry_price=91.25,
        pnl_pct=4.2,
        pnl_dollar=13.44,
    )
    position = engine.get_position("ASTS")
    assert position["quantity"] == 3.5
    assert position["entry_price"] == 91.25
    assert position["current_pnl_pct"] == 4.2
    assert position["current_pnl_dollar"] == 13.44

    tracker = PositionTracker(decision_engine=engine)
    state = tracker.get("ASTS")
    assert state["has_position"] is True
    assert state["pnl"] == 13.44
    assert state["pnl_pct"] == 4.2


def test_zero_position_update_closes_decision_snapshot():
    engine = DecisionEngine()
    engine.update_position_state("ASTS", 2.0, 90.0, 1.0, 2.0)
    engine.update_position_state("ASTS", 0.0, 90.0, 0.0, 0.0)
    assert engine.get_position("ASTS") is None
