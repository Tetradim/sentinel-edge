"""Full Correlation Engine — Sentinel Edge analyst/correlation/engine.py

Canonical location.  The root correlation.py is now a backward-compat shim
that re-exports from here.
"""
import hashlib
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

from analyst.signals.base import Signal  # canonical Signal dataclass

logger = logging.getLogger(__name__)


# Lazy-import metrics so this module is usable before FastAPI starts
def _get_counter():
    from metrics import correlation_clusters_total
    return correlation_clusters_total


_BULLISH = {"BUY"}
_BEARISH = {"SELL", "STOP_BUYING", "EMERGENCY_EXIT"}


def _build_risk_recommendation(cluster: Dict) -> Dict[str, str]:
    direction = cluster["direction"]
    strength = cluster["strength"]

    if direction == "BEARISH" and strength > 0.65:
        return {
            "action": "tighten_trailing_global",
            "priority": "high",
            "scope": "global",
            "trailing_stop_action": "tighten",
            "operator_summary": (
                "High-strength bearish correlation cluster: tighten trailing stops globally, "
                "pause new long entries, and verify Pulse override delivery."
            ),
        }

    if direction == "BEARISH":
        return {
            "action": "review_trailing_stops",
            "priority": "medium",
            "scope": "cluster_symbols",
            "trailing_stop_action": "review",
            "operator_summary": (
                "Bearish correlation cluster: review trailing stops for affected symbols "
                "before adding new exposure."
            ),
        }

    return {
        "action": "observe_momentum",
        "priority": "low",
        "scope": "watchlist",
        "trailing_stop_action": "maintain",
        "operator_summary": (
            "Bullish correlation cluster: observe momentum and maintain existing trailing-stop policy."
        ),
    }


class CorrelationEngine:
    """
    Detect correlation clusters across multiple symbols.

    Maintains a per-symbol rolling window of signal events.  When ≥ min_symbols
    break out in the same direction within the window, a cluster is emitted,
    persisted to MongoDB, Prometheus counter incremented, and an optional
    Pulse override is fired.

    Configuration
    ─────────────
    window_sec   : look-back window in seconds          (default 120)
    min_symbols  : minimum symbols to form a cluster    (default 3)
    cooldown_sec : minimum gap between alerts, per dir  (default 300)
    """

    def __init__(
        self,
        db=None,                                    # Motor async DB (optional)
        pulse_base_url: Optional[str] = "http://pulse:8001",
        pulse_overrides_enabled: bool = True,
        window_sec: int = 120,
        min_symbols: int = 3,
        cooldown_sec: int = 300,
    ):
        self.db = db
        self.pulse_base_url = pulse_base_url
        self.pulse_overrides_enabled = pulse_overrides_enabled
        self.window_sec = window_sec
        self.min_symbols = min_symbols
        self.cooldown_sec = cooldown_sec

        # symbol → deque[(timestamp, action, confidence)]
        self.events: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # per-direction cooldown
        self.last_alert_time: Dict[str, datetime] = {}

        # in-memory cache for REST API
        self._recent_clusters: List[Dict] = []

        logger.info(
            "CorrelationEngine ready  window=%ds  min=%d  cooldown=%ds",
            window_sec, min_symbols, cooldown_sec,
        )

    # ── Public API ───────────────────────────────────────────────────────

    async def record_signal(
        self,
        symbol: str,
        action: str,
        confidence: float = 1.0,
        timestamp: Optional[datetime] = None,
    ) -> Optional[Dict]:
        """
        Record one signal event.  Returns the cluster dict when a new cluster
        is detected; otherwise returns None.
        """
        ts = timestamp or datetime.utcnow()
        self.events[symbol].append((ts, action, confidence))
        cluster = self._detect_cluster(ts)
        if cluster:
            await self._handle_cluster(cluster)
        return cluster

    async def record_signal_obj(self, symbol: str, signal: Signal) -> Optional[Dict]:
        """Convenience wrapper accepting a Signal dataclass."""
        return await self.record_signal(symbol, signal.action, signal.confidence)

    def get_recent_clusters(self, limit: int = 10) -> List[Dict]:
        return self._recent_clusters[:limit]

    def get_latest_cluster(self) -> Optional[Dict]:
        return self._recent_clusters[0] if self._recent_clusters else None

    def get_current_breadth(self) -> Dict:
        """Bull / bear / neutral snapshot of the last window_sec seconds."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_sec)
        bullish = bearish = neutral = 0
        for history in self.events.values():
            recent = [e for e in history if e[0] >= cutoff]
            if not recent:
                neutral += 1
                continue
            action = recent[-1][1]
            if action in _BULLISH:
                bullish += 1
            elif action in _BEARISH:
                bearish += 1
            else:
                neutral += 1
        total = max(bullish + bearish + neutral, 1)
        return {
            "bullish": bullish,
            "bearish": bearish,
            "neutral": neutral,
            "total": total,
            "bullish_pct": round(bullish / total * 100, 1),
            "bearish_pct": round(bearish / total * 100, 1),
        }

    # ── Internal ─────────────────────────────────────────────────────────

    def _detect_cluster(self, now: datetime) -> Optional[Dict]:
        cutoff = now - timedelta(seconds=self.window_sec)
        bullish_syms: List[tuple] = []
        bearish_syms: List[tuple] = []

        for symbol, history in self.events.items():
            recent = [e for e in history if e[0] >= cutoff]
            if not recent:
                continue
            _, action, conf = recent[-1]
            if action in _BULLISH:
                bullish_syms.append((symbol, conf))
            elif action in _BEARISH:
                bearish_syms.append((symbol, conf))

        for direction, sym_list in [("BULLISH", bullish_syms), ("BEARISH", bearish_syms)]:
            if len(sym_list) < self.min_symbols:
                continue
            last = self.last_alert_time.get(direction)
            sym_list.sort(key=lambda x: -x[1])
            top = [s[0] for s in sym_list[:8]]
            strength = round(min(1.0, len(sym_list) / 8), 2)
            cluster = {
                "direction": direction,
                "count": len(sym_list),
                "symbols": top,
                "strength": strength,
                "score": round(len(sym_list) / max(len(self.events), 1), 2),
                "timestamp": now.isoformat(),
            }
            cluster["risk_recommendation"] = _build_risk_recommendation(cluster)
            if last and (now - last).total_seconds() < self.cooldown_sec:
                latest = self._latest_cluster_for_direction(direction)
                if latest and cluster["count"] > latest.get("count", 0):
                    cluster["_cooldown_update"] = True
                    return cluster
                continue
            return cluster
        return None

    def _latest_cluster_for_direction(self, direction: str) -> Optional[Dict]:
        for cluster in self._recent_clusters:
            if cluster.get("direction") == direction:
                return cluster
        return None

    async def _handle_cluster(self, cluster: Dict) -> None:
        direction = cluster["direction"]
        is_cooldown_update = bool(cluster.pop("_cooldown_update", False))
        previous_cluster = self._latest_cluster_for_direction(direction)
        previous_strength = previous_cluster.get("strength", 0) if previous_cluster else 0

        if not is_cooldown_update:
            self.last_alert_time[direction] = datetime.utcnow()

        if is_cooldown_update and previous_cluster:
            index = self._recent_clusters.index(previous_cluster)
            self._recent_clusters[index] = cluster
        else:
            self._recent_clusters.insert(0, cluster)
            self._recent_clusters = self._recent_clusters[:20]

        strength_label = "high" if cluster["strength"] > 0.7 else "medium"
        previous_strength_label = "high" if previous_strength > 0.7 else "medium"
        if not is_cooldown_update or strength_label != previous_strength_label:
            try:
                _get_counter().labels(
                    direction=direction.lower(), strength=strength_label
                ).inc()
            except Exception:
                pass

        logger.warning(
            "🔗 CLUSTER: %d-symbol %s [%s] strength=%.2f",
            cluster["count"], direction,
            ", ".join(cluster["symbols"]), cluster["strength"],
        )

        await self._persist_cluster(cluster)

        should_trigger_override = (
            direction == "BEARISH"
            and cluster["strength"] > 0.65
            and (not is_cooldown_update or previous_strength <= 0.65)
        )
        if should_trigger_override:
            await self._trigger_pulse_override(cluster)

    async def _persist_cluster(self, cluster: Dict) -> None:
        if self.db is None:
            return
        try:
            doc = {**cluster, "persisted_at": datetime.utcnow()}
            await self.db.correlation_events.insert_one(doc)
        except Exception as exc:
            logger.error("Cluster persist failed: %s", exc)

    async def _trigger_pulse_override(self, cluster: Dict) -> None:
        if not self.pulse_overrides_enabled or not self.pulse_base_url:
            logger.info("Pulse override suppressed: standalone mode")
            return

        handoff_action = "tighten_trailing_stop"
        trailing_percent = 1.0
        try:
            configured_trailing_percent = float(os.getenv("ALERT_TRAILING_PERCENT", "1.0"))
            if configured_trailing_percent > 0:
                trailing_percent = configured_trailing_percent
        except (TypeError, ValueError):
            pass

        fingerprint = f"correlation:{cluster['direction']}:{cluster['count']}:{cluster['strength']:.4f}"
        nonce = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:10]
        minute_bucket = int(time.time() // 60)
        payload = {
            "contract_version": "edge.pulse.handoff.v1",
            "symbol": "GLOBAL",
            "action": handoff_action,
            "confidence": max(0.0, min(float(cluster["strength"]), 1.0)),
            "reason": "correlation_bearish_cluster",
            "mode": os.getenv("PULSE_HANDOFF_MODE", "paper"),
            "orb_session": "market_open",
            "stop_type": "tighten_trailing",
            "trailing_percent": trailing_percent,
            "idempotency_key": f"edge:GLOBAL:{handoff_action}:market_open:{minute_bucket}:{nonce}",
            "source": "sentinel_edge",
            "created_at": time.time(),
            "metadata": {
                "source": "correlation_engine",
                "direction": cluster["direction"],
                "count": cluster["count"],
                "symbols": cluster["symbols"],
                "strength": cluster["strength"],
                "risk_recommendation": cluster.get("risk_recommendation"),
            },
        }
        headers = {}
        edge_api_key = os.getenv("PULSE_API_KEY") or os.getenv("EDGE_API_KEY")
        if edge_api_key:
            headers["X-API-Key"] = edge_api_key
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.post(
                    f"{self.pulse_base_url}/api/edge/handoff",
                    json=payload,
                    headers=headers,
                )
                logger.info("Pulse override → %s %s", resp.status_code, resp.text[:80])
        except Exception as exc:
            logger.warning("Pulse override skipped (%s)", exc)
