import edge_entry_policy_contract  # noqa: F401
from automation import AutomationAction, AutomationMode, HandoffCommand


def test_buy_intent_carries_execution_style_orb_and_squeeze():
    command = HandoffCommand(
        symbol="GME",
        action=AutomationAction.BUY,
        confidence=0.85,
        reason="confirmed squeeze",
        mode=AutomationMode.PAPER,
        metadata={
            "price": 101.0,
            "expected_value_pct": 0.80,
            "estimated_cost_pct": 0.10,
            "trade_thesis": {
                "strategy": "short_squeeze_breakout",
                "entry_trigger": 100.0,
                "execution_style_preference": "breakout_stop_limit",
                "execution_style_policy": {
                    "contract_version": "edge.execution_style.v1",
                    "preferred_style": "breakout_stop_limit",
                    "timeout_seconds": 6,
                    "aggressive_limit_buffer_bps": 5,
                    "stop_trigger_price": 100.0,
                    "post_fill_horizons_seconds": [30, 60, 300],
                    "orb_confirmation": {"direction": "bullish", "confidence": 0.72},
                    "squeeze_state": "triggering",
                },
                "orb_evidence": {"direction": "bullish"},
                "short_squeeze": {"state": "triggering", "trigger_confirmed": True},
            },
            "trade_card": {
                "card_id": "edge-card:test",
                "position_id": "edge-position:test",
                "entry_price": 101.0,
                "maximum_entry_price": 102.0,
                "expected_value_pct": 0.80,
                "metadata": {},
            },
        },
    )

    policy = command.payload()["metadata"]["execution_intent"]["entry_policy"]
    style = policy["execution_style_policy"]

    assert style["contract_version"] == "edge.execution_style.v1"
    assert style["preferred_style"] == "breakout_stop_limit"
    assert style["stop_trigger_price"] == 100.0
    assert style["orb_confirmation"]["direction"] == "bullish"
    assert style["squeeze_state"] == "triggering"
    assert policy["short_squeeze"]["trigger_confirmed"] is True
    assert policy["maximum_entry_price"] == 102.0
