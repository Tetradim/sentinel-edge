"""Portfolio strategy coordinator assembly."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from edge_profitability_lifecycle import ProfitabilityLifecycleMixin
from edge_profitability_models import MarketRegime, TradeCardState
from edge_profitability_scoring import ProfitabilityScoringMixin
from edge_profitability_state import ProfitabilityStateMixin


class EdgeProfitabilityCoordinator(
    ProfitabilityLifecycleMixin,
    ProfitabilityScoringMixin,
    ProfitabilityStateMixin,
):
    """Regime gate, opportunity ranker, allocator, lifecycle owner, and learner."""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._init_state(state_path)


coordinator = EdgeProfitabilityCoordinator()

__all__ = [
    "EdgeProfitabilityCoordinator",
    "MarketRegime",
    "TradeCardState",
    "coordinator",
]
