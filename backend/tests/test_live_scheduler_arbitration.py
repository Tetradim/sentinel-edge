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
    scheduler.prices._live_prices["ASTS"] = (90.0, 1000.0, time.time())
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


def test_definitively_suppressed_main_action_does_not_block_plugin(tmp_path, monkeypatch):
    scheduler = _scheduler(tmp_path)
    calls = []

    async def original(_self, **kwargs):
        action = kwargs["action"].value
        calls.append(action)
        if action == "buy":
            return {"sent": False, "status": "suppressed", "reason": "confidence_below_threshold"}
        return {"sent": True, "status": "accepted", "reason": "pulse_accepted"}

    monkeypatch.setattr(patch, "_original_handoff", original)

    async def scenario():
        first = await patch._handoff_with_fresh_data_and_single_action(
            scheduler,
            symbol="ASTS",
            action=AutomationAction.BUY,
            confidence=0.2,
            reason="weak main signal",
        )
        second = await patch._handoff_with_fresh_data_and_single_action(
            scheduler,
            symbol="ASTS",
            action=AutomationAction.SELL,
            confidence=0.9,
            reason="strong plugin signal",
        )
        return first, second

    first, second = asyncio.run(scenario())
    assert calls == ["buy", "sell"]
    assert first["status"] == "suppressed"
    assert second["sent"] is True


def test_evaluation_action_context_is_cleared_after_every_evaluation(monkeypatch):
    scheduler = EvaluationScheduler.__new__(EvaluationScheduler)
    observed = []

    async def original(_self, symbol, *args, **kwargs):
        observed.append(patch._selected_action(symbol))
        patch._claim_action(symbol, "buy")
        assert patch._selected_action(symbol) == "buy"

    monkeypatch.setattr(patch, "_original_evaluate", original)

    async def scenario():
        await patch._evaluate_with_action_context(scheduler, "ASTS")
        await patch._evaluate_with_action_context(scheduler, "ASTS")

    asyncio.run(scenario())
    assert observed == [None, None]
