import asyncio
import time

from automation import (
    AutomationAction,
    AutomationController,
    AutomationMode,
    AutomationSettings,
)
from price_fetcher import PriceFetcher
from scheduler import EvaluationScheduler
import live_scheduler_patch as patch


def _scheduler(tmp_path):
    scheduler = EvaluationScheduler.__new__(EvaluationScheduler)
    scheduler.prices = PriceFetcher()
    scheduler.automation = AutomationController(
        settings=AutomationSettings(
            global_enabled=True,
            mode=AutomationMode.LIVE,
            default_ticker_enabled=True,
            min_confidence=0.1,
            cooldown_seconds=0,
        ),
        state_path=tmp_path / "automation.json",
    )
    return scheduler


def test_live_buy_is_suppressed_without_fresh_streaming_data(tmp_path, monkeypatch):
    scheduler = _scheduler(tmp_path)
    calls = {"original": 0}

    async def original(*_args, **_kwargs):
        calls["original"] += 1
        return {"sent": True, "status": "accepted"}

    monkeypatch.setattr(patch, "_original_handoff", original)
    result = asyncio.run(
        patch._handoff_with_fresh_data_and_single_action(
            scheduler,
            symbol="ASTS",
            action=AutomationAction.BUY,
            confidence=0.9,
            reason="test",
            metadata={"price": 90.0},
        )
    )

    assert calls["original"] == 0
    assert result["status"] == "suppressed"
    assert result["reason"] == "live_execution_data_stale"
    assert result["execution_data"]["source"] == "unavailable"


def test_fresh_websocket_data_allows_one_action_but_blocks_conflict(tmp_path, monkeypatch):
    scheduler = _scheduler(tmp_path)
    scheduler.prices._live_prices["ASTS"] = (90.0, 1000.0, time.time())
    calls = []

    async def original(_self, **kwargs):
        calls.append(kwargs["action"].value)
        return {"sent": True, "status": "accepted", "reason": "pulse_accepted"}

    monkeypatch.setattr(patch, "_original_handoff", original)

    async def scenario():
        first = await patch._handoff_with_fresh_data_and_single_action(
            scheduler,
            symbol="ASTS",
            action=AutomationAction.BUY,
            confidence=0.9,
            reason="main strategy",
            metadata={"price": 90.0},
        )
        second = await patch._handoff_with_fresh_data_and_single_action(
            scheduler,
            symbol="ASTS",
            action=AutomationAction.SELL,
            confidence=0.9,
            reason="conflicting plugin",
            metadata={"price": 90.0},
        )
        return first, second

    first, second = asyncio.run(scenario())
    assert calls == ["buy"]
    assert first["sent"] is True
    assert second["status"] == "suppressed"
    assert second["reason"] == "evaluation_action_already_selected"
    assert second["selected_action"] == "buy"


def test_risk_control_action_does_not_require_market_price(tmp_path, monkeypatch):
    scheduler = _scheduler(tmp_path)
    calls = {"original": 0}

    async def original(*_args, **_kwargs):
        calls["original"] += 1
        return {"sent": True, "status": "accepted"}

    monkeypatch.setattr(patch, "_original_handoff", original)
    result = asyncio.run(
        patch._handoff_with_fresh_data_and_single_action(
            scheduler,
            symbol="ASTS",
            action=AutomationAction.STOP_BUYING,
            confidence=0.9,
            reason="risk control",
        )
    )
    assert calls["original"] == 1
    assert result["sent"] is True
