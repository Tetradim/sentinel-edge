"""Portfolio strategy coordinator assembly."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from edge_profitability_counterfactual import ProfitabilityCounterfactualMixin
from edge_profitability_cycle import ProfitabilityCycleMixin
from edge_profitability_lifecycle import ProfitabilityLifecycleMixin
from edge_profitability_models import MarketRegime, TradeCardState
from edge_profitability_scoring import ProfitabilityScoringMixin
from edge_profitability_state import ProfitabilityStateMixin


class EdgeProfitabilityCoordinator(
    ProfitabilityCounterfactualMixin,
    ProfitabilityCycleMixin,
    ProfitabilityLifecycleMixin,
    ProfitabilityScoringMixin,
    ProfitabilityStateMixin,
):
    """Regime gate, cycle ranker, counterfactual learner, allocator, and lifecycle owner."""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._init_state(state_path)
        self._init_cycle_state()
        self._init_counterfactual_state()


coordinator = EdgeProfitabilityCoordinator()

__all__ = [
    "EdgeProfitabilityCoordinator",
    "MarketRegime",
    "TradeCardState",
    "coordinator",
]
