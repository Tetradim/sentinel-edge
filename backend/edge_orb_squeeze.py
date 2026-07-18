"""Authoritative ORB and short-squeeze evidence for Edge.

Short interest is stored as pressure, not as an execution command.  A squeeze can
become actionable only when price/volume evidence confirms that covering has
started.  ORB, chart structure and the existing portfolio gates retain authority.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Optional

from edge_profitability_models import clamp, finite, iso_now


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any, *, field: str) -> datetime:
    raw = str(value or "").strip().replace("Z", "+00:00")
    if not raw:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _bounded(value: Any, low: float, high: float) -> float:
    return clamp(finite(value), low, high)


def calculate_squeeze_pressure(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a bounded, explainable pressure score from independent inputs."""
    short_float = _bounded(payload.get("short_float_pct"), 0.0, 100.0)
    days_to_cover = _bounded(payload.get("days_to_cover"), 0.0, 30.0)
    borrow_rate = _bounded(payload.get("borrow_rate_pct"), 0.0, 500.0)
    utilization = _bounded(payload.get("utilization_pct"), 0.0, 100.0)
    gamma = _bounded(payload.get("gamma_squeeze_score"), 0.0, 100.0)
    catalyst = _bounded(payload.get("catalyst_score"), 0.0, 100.0)
    availability_change = _bounded(payload.get("availability_change_pct"), -100.0, 100.0)

    components = {
        "short_float": min(30.0, short_float),
        "days_to_cover": min(25.0, days_to_cover * 2.5),
        "borrow_rate": min(15.0, borrow_rate * 0.15),
        "utilization": min(15.0, utilization * 0.15),
        "gamma": gamma * 0.10,
        "catalyst": catalyst * 0.05,
        "borrow_availability": min(5.0, max(0.0, -availability_change) * 0.05),
    }
    score = clamp(sum(components.values()), 0.0, 100.0)
    probability = clamp((score - 20.0) / 75.0, 0.02, 0.95)
    pressure_state = (
        "extreme" if score >= 80.0 else
        "armed" if score >= 60.0 else
        "watch" if score >= 40.0 else
        "low"
    )
    return {
        "pressure_score": round(score, 4),
        "pressure_probability": round(probability, 4),
        "pressure_state": pressure_state,
        "components": {key: round(value, 4) for key, value in components.items()},
    }


class ShortSqueezeStore:
    """Latest validated short-interest snapshot per symbol with persistence."""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        configured = os.getenv("EDGE_SHORT_SQUEEZE_STATE_FILE", "").strip()
        self.state_path = state_path or (
            Path(configured) if configured else Path(__file__).parent / "data" / "short-squeeze.json"
        )
        self._lock = RLock()
        self._latest: Dict[str, Dict[str, Any]] = {}
        self._seen: set[str] = set()
        self._load()

    def record(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Short-squeeze payload must be an object")
        payload = dict(raw)
        if str(payload.get("contract_version") or "") != "edge.squeeze.snapshot.v1":
            raise ValueError("Unsupported short-squeeze contract")
        snapshot_id = str(payload.get("snapshot_id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot_id is required")
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol or len(symbol) > 32:
            raise ValueError("symbol is required")
        observed_at = _parse_time(payload.get("observed_at"), field="observed_at")
        expires_at = _parse_time(payload.get("expires_at"), field="expires_at")
        now = _utc_now()
        if expires_at <= observed_at:
            raise ValueError("expires_at must be after observed_at")
        if expires_at <= now:
            raise ValueError("Short-squeeze snapshot is already expired")
        max_ttl = max(300.0, finite(os.getenv("EDGE_SHORT_SQUEEZE_MAX_TTL_SECONDS"), 604800.0))
        if (expires_at - observed_at).total_seconds() > max_ttl:
            raise ValueError("Short-squeeze snapshot validity window is too long")

        metrics = {
            "short_float_pct": _bounded(payload.get("short_float_pct"), 0.0, 100.0),
            "days_to_cover": _bounded(payload.get("days_to_cover"), 0.0, 30.0),
            "borrow_rate_pct": _bounded(payload.get("borrow_rate_pct"), 0.0, 500.0),
            "utilization_pct": _bounded(payload.get("utilization_pct"), 0.0, 100.0),
            "available_to_borrow": max(0.0, finite(payload.get("available_to_borrow"))),
            "availability_change_pct": _bounded(payload.get("availability_change_pct"), -100.0, 100.0),
            "gamma_squeeze_score": _bounded(payload.get("gamma_squeeze_score"), 0.0, 100.0),
            "catalyst_score": _bounded(payload.get("catalyst_score"), 0.0, 100.0),
            "short_interest_change_pct": _bounded(payload.get("short_interest_change_pct"), -100.0, 500.0),
        }
        normalized = {
            "contract_version": "edge.squeeze.snapshot.v1",
            "snapshot_id": snapshot_id,
            "source": str(payload.get("source") or "short-interest-provider"),
            "symbol": symbol,
            "observed_at": observed_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "received_at": now.isoformat(),
            **{key: round(value, 6) for key, value in metrics.items()},
            **calculate_squeeze_pressure(metrics),
            "evidence": payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {},
        }
        with self._lock:
            if snapshot_id in self._seen:
                existing = self._latest.get(symbol)
                return dict(existing) if existing else normalized
            current = self._latest.get(symbol)
            if current and observed_at < _parse_time(current.get("observed_at"), field="observed_at"):
                raise ValueError("Short-squeeze snapshot is older than the current symbol snapshot")
            self._latest[symbol] = normalized
            self._seen.add(snapshot_id)
            self._save()
        return dict(normalized)

    def active(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = str(symbol or "").upper()
        with self._lock:
            payload = self._latest.get(key)
            if not payload:
                return None
            try:
                expires_at = _parse_time(payload.get("expires_at"), field="expires_at")
            except ValueError:
                return None
            if expires_at <= _utc_now():
                self._latest.pop(key, None)
                self._save()
                return None
            return dict(payload)

    def status(self) -> Dict[str, Any]:
        with self._lock:
            symbols = list(self._latest)
        active = {symbol: snapshot for symbol in symbols if (snapshot := self.active(symbol))}
        return {
            "contract_version": "edge.squeeze.status.v1",
            "active_symbols": active,
            "count": len(active),
        }

    def _load(self) -> None:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        if isinstance(payload, dict):
            latest = payload.get("latest") if isinstance(payload.get("latest"), dict) else {}
            seen = payload.get("seen") if isinstance(payload.get("seen"), list) else []
            self._latest = {str(key).upper(): value for key, value in latest.items() if isinstance(value, dict)}
            self._seen = {str(value) for value in seen if value}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps({"latest": self._latest, "seen": sorted(self._seen)[-5000:]}, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.state_path)


def _orb_evidence(scheduler: Any, symbol: str, price: float) -> Dict[str, Any]:
    tracker = getattr(scheduler, "orb", None)
    if tracker is None or price <= 0:
        return {"contract_version": "edge.orb.evidence.v1", "available": False, "direction": "neutral", "confidence": 0.0}
    sessions = tracker.get_session_levels(symbol) if hasattr(tracker, "get_session_levels") else {}
    confirmations: list[Dict[str, Any]] = []
    weights = {5: 0.40, 15: 0.72, 30: 0.90}
    for session_id, levels in (sessions or {}).items():
        for timeframe, level in (levels or {}).items():
            if not bool(getattr(level, "locked", False)) or not bool(getattr(level, "is_valid", False)):
                continue
            high = finite(getattr(level, "high", 0.0))
            low = finite(getattr(level, "low", 0.0))
            direction = "bullish" if high > 0 and price > high else "bearish" if low > 0 and price < low else "inside"
            if direction == "inside":
                continue
            confidence = weights.get(int(timeframe), 0.50)
            if str(session_id) != "market_open":
                confidence *= 0.75
            confirmations.append({
                "session_id": str(session_id),
                "timeframe_minutes": int(timeframe),
                "direction": direction,
                "confidence": round(confidence, 4),
                "orb_high": round(high, 6),
                "orb_low": round(low, 6),
                "price": round(price, 6),
            })
    strongest = max(confirmations, key=lambda item: item["confidence"], default=None)
    return {
        "contract_version": "edge.orb.evidence.v1",
        "available": bool(confirmations),
        "direction": strongest["direction"] if strongest else "neutral",
        "confidence": strongest["confidence"] if strongest else 0.0,
        "strongest": strongest,
        "confirmations": confirmations,
    }


def _pattern_evidence(analysis: Any) -> Dict[str, Any]:
    bullish: list[str] = []
    bearish: list[str] = []
    strongest_bullish = 0.0
    strongest_bearish = 0.0
    for pattern in list(getattr(analysis, "patterns", None) or []):
        if not bool(getattr(pattern, "detected", False)):
            continue
        name = str(getattr(getattr(pattern, "pattern_type", None), "value", getattr(pattern, "pattern_type", "")))
        direction = str(getattr(getattr(pattern, "direction", None), "name", "neutral")).lower()
        strength = clamp(finite(getattr(pattern, "confidence", 0.0)), 0.0, 1.0)
        if direction == "bullish":
            bullish.append(name)
            strongest_bullish = max(strongest_bullish, strength)
        elif direction == "bearish":
            bearish.append(name)
            strongest_bearish = max(strongest_bearish, strength)
    return {
        "bullish": bullish,
        "bearish": bearish,
        "strongest_bullish_confidence": round(strongest_bullish, 4),
        "strongest_bearish_confidence": round(strongest_bearish, 4),
    }


def fuse_orb_and_squeeze(analysis: Any, scheduler: Any) -> Any:
    """Return an AnalysisResult augmented with non-duplicative market evidence."""
    symbol = str(getattr(analysis, "symbol", "")).upper()
    price = finite(getattr(analysis, "price", 0.0))
    metadata = dict(getattr(analysis, "metadata", None) or {})
    orb = _orb_evidence(scheduler, symbol, price)
    patterns = _pattern_evidence(analysis)
    snapshot = short_squeeze_store.active(symbol)

    structure = metadata.get("market_structure") if isinstance(metadata.get("market_structure"), dict) else {}
    structure_state = str(structure.get("state") or "").lower()
    bullish_structure = structure_state == "resistance_breakout" or patterns["strongest_bullish_confidence"] >= 0.60
    bearish_structure = structure_state == "support_breakdown" or patterns["strongest_bearish_confidence"] >= 0.65

    avg_volume = finite(getattr(getattr(scheduler, "signals", None), "avg_volume", {}).get(symbol)) if scheduler else 0.0
    observed_volume = finite(getattr(analysis, "volume", 0.0))
    volume_ratio = observed_volume / avg_volume if avg_volume > 0 and observed_volume > 0 else finite(metadata.get("volume_ratio"), 1.0)
    indicators = metadata.get("indicators") if isinstance(metadata.get("indicators"), dict) else {}
    volume_zscore = finite(metadata.get("volume_zscore"), finite(indicators.get("volume_zscore")))
    volume_confirmed = volume_ratio >= finite(os.getenv("EDGE_SQUEEZE_MIN_VOLUME_RATIO"), 1.50) or volume_zscore >= finite(os.getenv("EDGE_SQUEEZE_MIN_VOLUME_ZSCORE"), 2.0)

    squeeze: Dict[str, Any] = {
        "contract_version": "edge.squeeze.evidence.v1",
        "available": bool(snapshot),
        "state": "unavailable",
        "pressure_score": 0.0,
        "pressure_probability": 0.0,
        "trigger_confirmed": False,
        "trigger_reason": None,
        "volume_ratio": round(volume_ratio, 4),
        "volume_zscore": round(volume_zscore, 4),
        "volume_confirmed": volume_confirmed,
    }
    squeeze_adjustment = 0.0
    if snapshot:
        pressure = finite(snapshot.get("pressure_score"))
        probability = finite(snapshot.get("pressure_probability"))
        minimum_pressure = finite(os.getenv("EDGE_SQUEEZE_TRIGGER_SCORE"), 60.0)
        bullish_trigger = orb.get("direction") == "bullish" or bullish_structure
        trigger_confirmed = pressure >= minimum_pressure and bullish_trigger and volume_confirmed and not bearish_structure
        if trigger_confirmed:
            state = "triggering"
            trigger_reason = "orb_volume_squeeze_confirmation" if orb.get("direction") == "bullish" else "pattern_volume_squeeze_confirmation"
            trigger_quality = max(finite(orb.get("confidence")), patterns["strongest_bullish_confidence"], 0.50)
            squeeze_adjustment = min(1.50, probability * trigger_quality * 1.75)
        else:
            state = "armed" if pressure >= minimum_pressure else str(snapshot.get("pressure_state") or "watch")
            trigger_reason = "pressure_without_price_volume_trigger" if pressure >= minimum_pressure else "pressure_below_trigger_threshold"
        squeeze.update({
            **snapshot,
            "contract_version": "edge.squeeze.evidence.v1",
            "available": True,
            "state": state,
            "trigger_confirmed": trigger_confirmed,
            "trigger_reason": trigger_reason,
            "volume_ratio": round(volume_ratio, 4),
            "volume_zscore": round(volume_zscore, 4),
            "volume_confirmed": volume_confirmed,
        })

    orb_adjustment = 0.0
    if orb.get("direction") == "bullish":
        orb_adjustment = finite(orb.get("confidence")) * 1.25
    elif orb.get("direction") == "bearish":
        orb_adjustment = -finite(orb.get("confidence")) * 1.25
    adjustment = clamp(orb_adjustment + squeeze_adjustment, -1.50, 2.25)
    signal = clamp(finite(getattr(analysis, "signal_strength", 0.0)) + adjustment, -10.0, 10.0)

    confidence = replace(getattr(analysis, "confidence"))
    evidence_confidence = max(
        finite(orb.get("confidence")),
        finite(squeeze.get("pressure_probability")) if squeeze.get("trigger_confirmed") else 0.0,
    )
    confidence.overall = clamp(finite(confidence.overall) * 0.92 + evidence_confidence * 0.08, 0.0, 1.0)
    metadata.update({
        "orb_evidence": orb,
        "short_squeeze": squeeze,
        "market_event_fusion": {
            "contract_version": "edge.market_event_fusion.v1",
            "orb_adjustment": round(orb_adjustment, 4),
            "squeeze_adjustment": round(squeeze_adjustment, 4),
            "total_adjustment": round(adjustment, 4),
            "patterns_already_counted": True,
            "generated_at": iso_now(),
        },
    })
    return replace(analysis, signal_strength=signal, confidence=confidence, metadata=metadata)


short_squeeze_store = ShortSqueezeStore()
