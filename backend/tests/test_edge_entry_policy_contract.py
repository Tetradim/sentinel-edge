import edge_supervision_contract  # noqa: F401 - preserve production wrapper order
import edge_entry_policy_contract  # noqa: F401 - installs BUY entry policy
from automation import AutomationAction, AutomationMode, HandoffCommand


def _command(*, expected_value=0.60, estimated_cost=0.10):
    card = {
        "card_id": "edge-card:test",
        "strategy_id": "edge-strategy:test",
        "thesis_id": "edge-thesis:test",
        "position_id": "edge-position:test",
        "symbol": "AAPL",
        "target_bot": "sentinel-pulse",
        "state": "armed",
        "entry_price": 100.0,
        "maximum_entry_price": 100.30,
        "expected_value_pct": expected_value,
        "metadata": {
            "estimated_cost_pct": estimated_cost,
            "entry_trigger_state": "triggered",
        },
    }
    return HandoffCommand(
        symbol="AAPL",
        action=AutomationAction.BUY,
        confidence=0.80,
        reason="ranked entry",
        mode=AutomationMode.PAPER,
        metadata={
            "price": 100.05,
            "trade_card": card,
            "position_id": card["position_id"],
            "expected_value_pct": expected_value,
            "estimated_cost_pct": estimated_cost,
        },
    )


def test_buy_intent_contains_position_scoped_entry_policy(monkeypatch):
    monkeypatch.setenv("EDGE_MIN_REMAINING_NET_EV_PCT", "0.15")
    intent = _command().payload()["metadata"]["execution_intent"]
    policy = intent["entry_policy"]

    assert intent["contract_version"] == "edge.execution_intent.v2"
    assert policy["contract_version"] == "edge.entry_policy.v1"
    assert policy["reference_price"] == 100.0
    assert policy["maximum_entry_price"] == 100.30
    assert policy["estimated_cost_pct"] == 0.10
    assert policy["maximum_execution_cost_pct"] == 0.55
    assert policy["minimum_remaining_expected_value_pct"] == 0.15
    assert policy["position_id"] == "edge-position:test"
    assert policy["trigger_state"] == "triggered"


def test_threshold_trade_receives_no_extra_cost_budget(monkeypatch):
    monkeypatch.setenv("EDGE_MIN_REMAINING_NET_EV_PCT", "0.15")
    policy = _command(expected_value=0.15, estimated_cost=0.10).execution_intent()["entry_policy"]
    assert policy["maximum_execution_cost_pct"] == 0.10


def test_non_buy_intent_does_not_carry_entry_policy():
    command = HandoffCommand(
        symbol="AAPL",
        action=AutomationAction.SELL,
        confidence=0.80,
        reason="exit",
        mode=AutomationMode.PAPER,
        metadata={"position_id": "edge-position:test"},
    )
    assert "entry_policy" not in command.execution_intent()
