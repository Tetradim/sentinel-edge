"""Preserve entry timing observations when cycle summaries replace decisions."""
from __future__ import annotations

from typing import Any, Dict


class ProfitabilityEntryTimingPersistenceMixin:
    def finalize_evaluation_cycle(self, cycle_id: str) -> Dict[str, Any]:
        cycle = dict((getattr(self, "_evaluation_cycles", {}) or {}).get(cycle_id) or {})
        candidates = cycle.get("candidates") if isinstance(cycle.get("candidates"), dict) else {}
        timing_by_symbol = {
            str(symbol).upper(): dict(candidate.get("entry_timing") or {})
            for symbol, candidate in candidates.items()
            if isinstance(candidate, dict) and isinstance(candidate.get("entry_timing"), dict)
        }
        result = super().finalize_evaluation_cycle(cycle_id)
        for symbol, timing in timing_by_symbol.items():
            latest = self.latest_decisions.setdefault(symbol, {})
            latest["entry_timing"] = timing
            if isinstance(latest.get("trade_card"), dict):
                latest["trade_card"].setdefault("metadata", {})["entry_timing"] = timing
        summary = result.get("summary") if isinstance(result, dict) else None
        if isinstance(summary, dict):
            for candidate in summary.get("candidates") or []:
                if isinstance(candidate, dict):
                    candidate["entry_timing"] = timing_by_symbol.get(str(candidate.get("symbol") or "").upper())
        self._save()
        return result
