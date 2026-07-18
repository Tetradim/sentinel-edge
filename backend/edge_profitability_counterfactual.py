"""Counterfactual marking for selected, rejected, and no-trade opportunities."""
from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from edge_profitability_models import env_int, finite, iso_now


_LEDGER_KEY = "__COUNTERFACTUAL_LEDGER__"


class ProfitabilityCounterfactualMixin:
    """Measure whether portfolio selection outperforms rejected alternatives."""

    def _init_counterfactual_state(self) -> None:
        self._counterfactual_pending: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def _counterfactual_payload(self) -> Dict[str, Any]:
        payload = self.latest_decisions.get(_LEDGER_KEY)
        if not isinstance(payload, dict):
            payload = {
                "contract_version": "edge.counterfactual.ledger.v1",
                "updated_at": iso_now(),
                "records": [],
            }
            self.latest_decisions[_LEDGER_KEY] = payload
        payload.setdefault("records", [])
        return payload

    def _mark_counterfactuals(self, symbol: str, price: float) -> None:
        current = finite(price)
        if current <= 0:
            return
        payload = self._counterfactual_payload()
        changed = False
        horizon = env_int("EDGE_COUNTERFACTUAL_HORIZON_CYCLES", 30, minimum=1)
        for record in payload["records"]:
            if record.get("closed") or str(record.get("symbol")) != symbol.upper():
                continue
            reference = finite(record.get("reference_price"))
            if reference <= 0:
                continue
            return_pct = ((current - reference) / reference) * 100.0
            record["observations"] = int(record.get("observations") or 0) + 1
            record["mark_price"] = round(current, 6)
            record["mark_return_pct"] = round(return_pct, 6)
            record["maximum_favorable_pct"] = round(
                max(finite(record.get("maximum_favorable_pct")), return_pct), 6
            )
            record["maximum_adverse_pct"] = round(
                min(finite(record.get("maximum_adverse_pct")), return_pct), 6
            )
            record["updated_at"] = iso_now()
            if record["observations"] >= horizon:
                record["closed"] = True
                record["closed_at"] = record["updated_at"]
                record["close_reason"] = "counterfactual_horizon_reached"
            changed = True
        if changed:
            payload["updated_at"] = iso_now()
            self.latest_decisions[_LEDGER_KEY] = payload
            self._save()

    def stage_cycle_candidate(
        self,
        cycle_id: str,
        analysis: Any,
        thesis: Dict[str, Any],
        *,
        base_decision: str,
        target_bot: Optional[str] = None,
    ):
        symbol = str(getattr(analysis, "symbol", None) or thesis.get("symbol") or "").upper()
        price = finite(getattr(analysis, "price", thesis.get("entry")))
        self._mark_counterfactuals(symbol, price)
        assessment, opportunity = super().stage_cycle_candidate(
            cycle_id,
            analysis,
            thesis,
            base_decision=base_decision,
            target_bot=target_bot,
        )
        if not hasattr(self, "_counterfactual_pending"):
            self._init_counterfactual_state()
        self._counterfactual_pending.setdefault(cycle_id, {})[symbol] = {
            "symbol": symbol,
            "target_bot": opportunity.target_bot,
            "reference_price": price,
            "base_decision": str(base_decision).lower(),
        }
        return assessment, opportunity

    def finalize_evaluation_cycle(self, cycle_id: str) -> Dict[str, Any]:
        result = super().finalize_evaluation_cycle(cycle_id)
        if not hasattr(self, "_counterfactual_pending"):
            self._init_counterfactual_state()
        pending = self._counterfactual_pending.pop(cycle_id, {})
        selected = set(result["summary"].get("selected_symbols") or [])
        payload = self._counterfactual_payload()
        horizon = env_int("EDGE_COUNTERFACTUAL_HORIZON_CYCLES", 30, minimum=1)

        for symbol in result["summary"].get("scored_symbols", []):
            staged = pending.get(symbol) or {}
            reference = finite(staged.get("reference_price"))
            if reference <= 0:
                continue
            latest = self.latest_decisions.get(symbol) or {}
            opportunity = latest.get("opportunity") if isinstance(latest.get("opportunity"), dict) else {}
            seed = f"{cycle_id}:{symbol}"
            payload["records"].append(
                {
                    "record_id": f"edge-counterfactual:{hashlib.sha256(seed.encode()).hexdigest()[:24]}",
                    "cycle_id": cycle_id,
                    "symbol": symbol,
                    "target_bot": staged.get("target_bot"),
                    "selected": symbol in selected,
                    "selection_status": latest.get("selection_status"),
                    "reference_price": round(reference, 6),
                    "mark_price": round(reference, 6),
                    "mark_return_pct": 0.0,
                    "maximum_favorable_pct": 0.0,
                    "maximum_adverse_pct": 0.0,
                    "observations": 0,
                    "horizon_cycles": horizon,
                    "opened_at": result["summary"].get("finalized_at"),
                    "updated_at": result["summary"].get("finalized_at"),
                    "closed": False,
                    "base_decision": staged.get("base_decision"),
                    "rank": opportunity.get("rank"),
                    "score": opportunity.get("score"),
                    "expected_value_pct": opportunity.get("expected_value_pct"),
                    "reasons": list(opportunity.get("reasons") or []),
                }
            )
        payload["records"] = payload["records"][-5000:]
        payload["updated_at"] = iso_now()
        self.latest_decisions[_LEDGER_KEY] = payload
        self._save()
        return result

    def counterfactual_status(self, *, include_records: bool = False, limit: int = 100) -> Dict[str, Any]:
        payload = self._counterfactual_payload()
        records = list(payload.get("records") or [])
        closed = [record for record in records if record.get("closed")]
        selected = [record for record in closed if record.get("selected")]
        rejected = [record for record in closed if not record.get("selected")]

        def average(items: list[Dict[str, Any]]) -> float:
            if not items:
                return 0.0
            return sum(finite(item.get("mark_return_pct")) for item in items) / len(items)

        selected_average = average(selected)
        rejected_average = average(rejected)
        result = {
            "contract_version": "edge.counterfactual.summary.v1",
            "updated_at": payload.get("updated_at"),
            "horizon_cycles": env_int("EDGE_COUNTERFACTUAL_HORIZON_CYCLES", 30, minimum=1),
            "record_count": len(records),
            "open_count": sum(1 for record in records if not record.get("closed")),
            "closed_count": len(closed),
            "selected_closed_count": len(selected),
            "rejected_closed_count": len(rejected),
            "selected_average_return_pct": round(selected_average, 6),
            "rejected_average_return_pct": round(rejected_average, 6),
            "selection_edge_pct": round(selected_average - rejected_average, 6),
        }
        if include_records:
            result["records"] = records[-max(1, min(int(limit), 1000)):][::-1]
        return result

    def portfolio_status(self, *, include_cards: bool = True) -> Dict[str, Any]:
        payload = super().portfolio_status(include_cards=include_cards)
        payload["counterfactuals"] = self.counterfactual_status(include_records=False)
        return payload
