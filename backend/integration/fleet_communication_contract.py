"""Cross-repository contract replay for Flare, Edge, Chain, and Iron."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
CHECKOUT = ROOT.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(CHECKOUT / "flare"))
sys.path.insert(0, str(CHECKOUT / "chain" / "src"))
sys.path.insert(0, str(CHECKOUT / "iron" / "src"))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sentinel-fleet-contract-") as temp:
        os.environ["EDGE_PROFITABILITY_STATE_FILE"] = str(Path(temp) / "profitability.json")
        os.environ["EDGE_FLARE_INTELLIGENCE_STATE_FILE"] = str(Path(temp) / "flare.json")
        os.environ["EDGE_MAX_RANKED_ENTRY_SLOTS"] = "5"
        os.environ["EDGE_TOTAL_RISK_BUDGET_PCT"] = "5"

        from edge_intelligence import EdgeIntelligencePublisher, FlarePublishRequest
        from flare_intelligence import FlareIntelligenceStore
        from edge_profitability import EdgeProfitabilityCoordinator
        from sentinel_chain.edge_strategy import EdgeAuthorizationStore
        from sentinel_iron.edge_strategy import EdgeAuthorizedOrderService

        flare_document = EdgeIntelligencePublisher().build(
            FlarePublishRequest(
                symbol="NVDA",
                direction="bullish",
                confidence=0.9,
                strength=0.8,
                evidence={"buy_volume": 900000, "sell_volume": 100000, "zscore": 2.5, "adv_pct": 3.0},
            )
        )
        flare_store = FlareIntelligenceStore(Path(temp) / "flare-contract.json")
        recorded = flare_store.record(flare_document)
        assert recorded["intelligence_id"] == flare_document["intelligence_id"]
        assert flare_store.adjustment("NVDA") > 0
        assert not any(key in flare_document for key in ("action", "quantity", "order_type"))

        coordinator = EdgeProfitabilityCoordinator(Path(temp) / "coordinator.json")
        chain_proposal = {
            "contract_version": "edge.strategy.proposal.v1",
            "proposal_id": "fleet-chain-1",
            "source_bot": "sentinel-chain",
            "target_bot": "sentinel-chain",
            "symbol": "BTCUSDT",
            "strategy": "momentum_breakout",
            "direction": "long",
            "confidence": 0.9,
            "regime": "trending_up",
            "expected_reward_pct": 4.0,
            "expected_risk_pct": 1.0,
            "estimated_cost_pct": 0.05,
            "entry_price": 100.0,
            "stop_price": 99.0,
            "targets": [104.0],
        }
        chain_auth = coordinator.evaluate_external_proposal(chain_proposal)
        assert chain_auth["authorized"] is True, chain_auth
        chain_store = EdgeAuthorizationStore(Path(temp) / "chain-auth.json")
        chain_store.record(chain_auth)
        assert chain_store.validation_reasons(
            chain_auth,
            symbol="BTCUSDT",
            side="buy",
            requested_notional=None,
        ) == []

        iron_proposal = {
            "contract_version": "edge.strategy.proposal.v1",
            "proposal_id": "fleet-iron-1",
            "source_bot": "sentinel-iron",
            "target_bot": "sentinel-iron",
            "symbol": "ES-202609-CME",
            "instrument_id": "ES-202609-CME",
            "strategy": "trend_following",
            "direction": "long",
            "side": "buy",
            "quantity": 1,
            "order_type": "market",
            "confidence": 0.9,
            "regime": "trending_up",
            "expected_reward_pct": 4.0,
            "expected_risk_pct": 1.0,
            "estimated_cost_pct": 0.05,
            "estimated_notional": 500.0,
        }
        iron_auth = coordinator.evaluate_external_proposal(iron_proposal)
        assert iron_auth["authorized"] is True, iron_auth
        normalized_iron = EdgeAuthorizedOrderService._normalize_proposal(iron_proposal)
        assert EdgeAuthorizedOrderService.validate_authorization(
            iron_auth,
            normalized_iron,
            datetime.now(timezone.utc),
        ) == []
        intent = EdgeAuthorizedOrderService.build_order_intent(iron_auth, normalized_iron)
        assert intent.instrument_id == "ES-202609-CME"
        assert intent.quantity == 1

        report = {
            "passed": True,
            "flare": {
                "intelligence_id": flare_document["intelligence_id"],
                "edge_adjustment": flare_store.adjustment("NVDA"),
            },
            "chain": {
                "card_id": chain_auth["trade_card"]["card_id"],
                "position_id": chain_auth["trade_card"]["position_id"],
            },
            "iron": {
                "card_id": iron_auth["trade_card"]["card_id"],
                "position_id": iron_auth["trade_card"]["position_id"],
                "client_order_id": intent.client_order_id,
            },
        }
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
