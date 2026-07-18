"""Bridge Edge's existing ShortInterestEngine into the squeeze evidence store."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Any

from edge_orb_squeeze import short_squeeze_store
from edge_profitability_models import finite
from options.short_interest import ShortInterestEngine


logger = logging.getLogger(__name__)
_ORIGINAL_ANALYZE = ShortInterestEngine.analyze
_INSTALLED = False


def _aware(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _percent(value: Any) -> float:
    number = max(0.0, finite(value))
    # The legacy short-interest engine represents borrow and utilization as
    # fractions in common call paths; preserve explicit percentages above 5.
    return number * 100.0 if number <= 5.0 else number


async def _analyze_and_publish(self: ShortInterestEngine, *args: Any, **kwargs: Any):
    metrics = await _ORIGINAL_ANALYZE(self, *args, **kwargs)
    current = getattr(metrics, "current", None)
    if current is None:
        return metrics
    observed = _aware(getattr(current, "timestamp", None) or getattr(metrics, "timestamp", None))
    ttl_hours = max(1.0, finite(os.getenv("EDGE_SHORT_SQUEEZE_SNAPSHOT_TTL_HOURS"), 48.0))
    expires = observed + timedelta(hours=min(ttl_hours, 168.0))
    symbol = str(getattr(metrics, "symbol", None) or getattr(current, "symbol", "")).upper()
    try:
        short_squeeze_store.record(
            {
                "contract_version": "edge.squeeze.snapshot.v1",
                "snapshot_id": f"short-interest:{symbol}:{observed.isoformat()}",
                "symbol": symbol,
                "source": "edge-short-interest-engine",
                "observed_at": observed.isoformat(),
                "expires_at": expires.isoformat(),
                "short_float_pct": finite(getattr(current, "short_interest_pct", 0.0)),
                "days_to_cover": finite(getattr(current, "days_to_cover", 0.0)),
                "borrow_rate_pct": _percent(getattr(current, "borrow_rate", 0.0)),
                "utilization_pct": _percent(getattr(current, "utilization", 0.0)),
                "available_to_borrow": finite(
                    getattr(current, "available_to_borrow", 0.0)
                    or getattr(current, "shortable_shares", 0.0)
                ),
                "availability_change_pct": finite(getattr(current, "availability_change_pct", 0.0)),
                "gamma_squeeze_score": finite(getattr(current, "gamma_squeeze_potential", 0.0)),
                "catalyst_score": finite(getattr(current, "catalyst_score", 0.0)),
                "short_interest_change_pct": finite(getattr(current, "short_interest_change_pct", 0.0)),
                "evidence": {
                    "recommendation": getattr(metrics, "recommendation", "neutral"),
                    "confidence": finite(getattr(metrics, "confidence", 0.0)),
                    "signals": list(getattr(metrics, "squeeze_signals", None) or []),
                    "warnings": list(getattr(metrics, "warnings", None) or []),
                },
            }
        )
    except ValueError as exc:
        # A stale or duplicate provider observation must not break the underlying
        # options/short-interest API response.
        logger.debug("Short-interest snapshot for %s was not published: %s", symbol, exc)
    except Exception:
        logger.exception("Could not publish short-interest squeeze snapshot for %s", symbol)
    return metrics


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    ShortInterestEngine.analyze = _analyze_and_publish
    _INSTALLED = True
    logger.info("Existing ShortInterestEngine now publishes Edge squeeze snapshots")
