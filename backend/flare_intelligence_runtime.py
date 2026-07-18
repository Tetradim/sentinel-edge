"""Bounded runtime bridge from Flare intelligence into Edge analysis."""
from __future__ import annotations

import edge_brain_runtime
from edge_brain_data import clamp
from flare_intelligence import flare_intelligence_store


_ORIGINAL_NON_EDGE_ADJUSTMENT = edge_brain_runtime._non_edge_observation_adjustment


def _combined_adjustment(engine, symbol: str) -> float:
    execution_feedback = float(_ORIGINAL_NON_EDGE_ADJUSTMENT(engine, symbol) or 0.0)
    dark_pool_adjustment = float(flare_intelligence_store.adjustment(symbol) or 0.0)
    return clamp(execution_feedback + dark_pool_adjustment, -1.5, 1.5)


def install() -> None:
    if getattr(edge_brain_runtime, "_flare_intelligence_installed", False):
        return
    edge_brain_runtime._non_edge_observation_adjustment = _combined_adjustment
    edge_brain_runtime._flare_intelligence_installed = True


install()
