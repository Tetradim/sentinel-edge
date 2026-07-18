"""Validated, expiring intelligence supplied by Sentinel Flare.

Flare is an observer.  Its payloads may influence Edge's analysis score, but they
never become executable commands and can never bypass Edge's portfolio gate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from threading import RLock
from typing import Any


_ALLOWED_DIRECTIONS = {"bullish", "bearish", "neutral"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: Any, *, field: str) -> datetime:
    if not value:
        raise ValueError(f"{field} is required")
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _unit(value: Any, *, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return number


class FlareIntelligenceStore:
    """Thread-safe latest-intelligence store with JSON persistence."""

    def __init__(self, state_path: Path | None = None) -> None:
        configured = os.getenv("EDGE_FLARE_INTELLIGENCE_STATE_FILE", "").strip()
        self.state_path = state_path or (Path(configured) if configured else Path(__file__).parent / "data" / "flare-intelligence.json")
        self._lock = RLock()
        self._latest: dict[str, dict[str, Any]] = {}
        self._seen: set[str] = set()
        self._load()

    def record(self, raw: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raise ValueError("Flare intelligence payload must be an object")
        payload = dict(raw)
        version = str(payload.get("contract_version") or "").strip()
        if version != "flare.intelligence.v1":
            raise ValueError("Unsupported Flare intelligence contract")
        source_bot = str(payload.get("source_bot") or "sentinel-flare").strip().lower()
        if source_bot != "sentinel-flare":
            raise ValueError("Flare intelligence must identify sentinel-flare as source_bot")
        intelligence_id = str(payload.get("intelligence_id") or "").strip()
        if not intelligence_id:
            raise ValueError("intelligence_id is required")
        symbol = str(payload.get("symbol") or "").strip().upper()
        if not symbol or len(symbol) > 32:
            raise ValueError("symbol is required")
        direction = str(payload.get("direction") or "neutral").strip().lower()
        if direction not in _ALLOWED_DIRECTIONS:
            raise ValueError("direction must be bullish, bearish, or neutral")
        confidence = _unit(payload.get("confidence"), field="confidence")
        strength = _unit(payload.get("strength"), field="strength")
        observed_at = _parse_time(payload.get("observed_at"), field="observed_at")
        expires_at = _parse_time(payload.get("expires_at"), field="expires_at")
        now = _utc_now()
        if expires_at <= observed_at:
            raise ValueError("expires_at must be after observed_at")
        if expires_at <= now:
            raise ValueError("Flare intelligence is already expired")
        max_ttl = float(os.getenv("EDGE_FLARE_MAX_TTL_SECONDS", "21600") or 21600)
        if (expires_at - observed_at).total_seconds() > max(60.0, max_ttl):
            raise ValueError("Flare intelligence validity window is too long")
        evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        normalized = {
            "contract_version": version,
            "intelligence_id": intelligence_id,
            "source_bot": source_bot,
            "symbol": symbol,
            "direction": direction,
            "confidence": round(confidence, 6),
            "strength": round(strength, 6),
            "observed_at": observed_at.isoformat(),
            "expires_at": expires_at.isoformat(),
            "evidence": evidence,
            "received_at": now.isoformat(),
        }
        with self._lock:
            if intelligence_id in self._seen:
                existing = self._latest.get(symbol)
                return dict(existing) if existing and existing.get("intelligence_id") == intelligence_id else normalized
            current = self._latest.get(symbol)
            if current:
                current_observed = _parse_time(current.get("observed_at"), field="observed_at")
                if observed_at < current_observed:
                    raise ValueError("Flare intelligence is older than the current symbol observation")
            self._latest[symbol] = normalized
            self._seen.add(intelligence_id)
            self._save()
        return dict(normalized)

    def active(self, symbol: str) -> dict[str, Any] | None:
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

    def adjustment(self, symbol: str) -> float:
        payload = self.active(symbol)
        if not payload:
            return 0.0
        sign = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}[str(payload["direction"])]
        max_adjustment = max(0.0, min(2.0, float(os.getenv("EDGE_FLARE_MAX_SIGNAL_ADJUSTMENT", "1.25") or 1.25)))
        reliability = max(0.0, min(1.0, float(os.getenv("EDGE_FLARE_RELIABILITY", "0.75") or 0.75)))
        value = sign * float(payload["confidence"]) * float(payload["strength"]) * reliability * max_adjustment
        return round(max(-max_adjustment, min(max_adjustment, value)), 6)

    def status(self) -> dict[str, Any]:
        symbols: dict[str, Any] = {}
        with self._lock:
            keys = list(self._latest)
        for symbol in keys:
            active = self.active(symbol)
            if active:
                symbols[symbol] = {**active, "signal_adjustment": self.adjustment(symbol)}
        return {"contract_version": "flare.intelligence.status.v1", "active_symbols": symbols, "count": len(symbols)}

    def _load(self) -> None:
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return
        if not isinstance(raw, dict):
            return
        latest = raw.get("latest") if isinstance(raw.get("latest"), dict) else {}
        seen = raw.get("seen") if isinstance(raw.get("seen"), list) else []
        self._latest = {str(key).upper(): value for key, value in latest.items() if isinstance(value, dict)}
        self._seen = {str(value) for value in seen if value}

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"latest": self._latest, "seen": sorted(self._seen)[-5000:]}, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_path)


flare_intelligence_store = FlareIntelligenceStore()
