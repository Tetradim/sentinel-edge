"""Install ORB and short-squeeze evidence above the enhanced analysis engine."""
from __future__ import annotations

import logging
from typing import Any

import edge_brain_runtime as brain_runtime
from edge_orb_squeeze import fuse_orb_and_squeeze
from signals_enhanced import SignalEngineEnhanced


logger = logging.getLogger(__name__)
_ORIGINAL_ANALYZE = SignalEngineEnhanced.analyze
_INSTALLED = False


async def _analyze_with_market_event_fusion(
    self: SignalEngineEnhanced,
    symbol: str,
    price_data,
    timeframe: str = "1m",
    higher_tf_data=None,
):
    analysis = await _ORIGINAL_ANALYZE(
        self,
        symbol,
        price_data,
        timeframe=timeframe,
        higher_tf_data=higher_tf_data,
    )
    context: dict[str, Any] = brain_runtime._BRAIN_CONTEXT.get() or {}
    scheduler = context.get("scheduler")
    fused = fuse_orb_and_squeeze(analysis, scheduler)
    if context is not None:
        context["analysis"] = fused
        context["orb_evidence"] = (fused.metadata or {}).get("orb_evidence")
        context["short_squeeze"] = (fused.metadata or {}).get("short_squeeze")
    if scheduler is not None:
        state = getattr(scheduler, "_edge_brain_state", None)
        if state is None:
            state = {}
            scheduler._edge_brain_state = state
        state[str(symbol).upper()] = fused
    return fused


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    SignalEngineEnhanced.analyze = _analyze_with_market_event_fusion
    _INSTALLED = True
    logger.info("Edge ORB + short-squeeze market-event fusion installed")
