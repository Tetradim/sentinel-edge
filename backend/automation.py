"""Automation controls for Edge-to-Pulse handoff.

Command acceptance and broker execution are separate states. Edge persists
command identity/cooldown state, while positions remain authoritative only when
reported back by Pulse.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from metrics import edge_automation_handoffs_total


class AutomationMode(str, Enum):
    RECOMMEND_ONLY = "recommend_only"
    PAPER = "paper"
    LIVE = "live"


class AutomationAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    STOP_BUYING = "stop_buying"
    STOP_ALL = "stop_all"
    REGULAR_STOP = "regular_stop"
    TRAILING_STOP = "trailing_stop"
    OPENING_TRAILING_STOP = "opening_trailing_stop"
    TIGHTEN_STOP = "tighten_stop"
    TIGHTEN_TRAILING_STOP = "tighten_trailing_stop"
    DCA = "dca"
    EMERGENCY_EXIT = "emergency_exit"


@dataclass
class AutomationSettings:
    global_enabled: bool = False
    mode: AutomationMode = AutomationMode.RECOMMEND_ONLY
    default_ticker_enabled: bool = False
    per_ticker_enabled: Dict[str, bool] = field(default_factory=dict)
    min_confidence: float = 0.6
    cooldown_seconds: int = 60
    quiet_when_pulse_absent: bool = True
    command_ttl_seconds: int = 30

    @classmethod
    def from_env(cls) -> "AutomationSettings":
        enabled = os.getenv("EDGE_PULSE_HANDOFF_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        mode_raw = os.getenv("EDGE_AUTOMATION_MODE", AutomationMode.RECOMMEND_ONLY.value).lower()
        try:
            mode = AutomationMode(mode_raw)
        except ValueError:
            mode = AutomationMode.RECOMMEND_ONLY
        default_ticker = os.getenv("EDGE_PULSE_HANDOFF_DEFAULT_TICKERS", "false").lower() in ("1", "true", "yes", "on")
        ttl = max(5, int(os.getenv("EDGE_HANDOFF_TTL_SECONDS", "30")))
        return cls(
            global_enabled=enabled,
            mode=mode,
            default_ticker_enabled=default_ticker,
            command_ttl_seconds=ttl,
        )

    def is_ticker_enabled(self, symbol: str) -> bool:
        return self.per_ticker_enabled.get(symbol.upper(), self.default_ticker_enabled)

    def can_handoff(self, symbol: str, confidence: float) -> tuple[bool, str]:
        if not self.global_enabled:
            return False, "global_disabled"
        if self.mode == AutomationMode.RECOMMEND_ONLY:
            return False, "recommend_only"
        if not self.is_ticker_enabled(symbol):
            return False, "ticker_disabled"
        if confidence < self.min_confidence:
            return False, "confidence_below_threshold"
        return True, "allowed"

    def public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["mode"] = self.mode.value
        return data


@dataclass
class HandoffCommand:
    symbol: str
    action: AutomationAction
    confidence: float
    reason: str
    mode: AutomationMode
    orb_session: str = "market_open"
    stop_type: Optional[str] = None
    trailing_percent: Optional[float] = None
    dca: Optional[Dict[str, Any]] = None
    idempotency_key: str = ""
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = self.symbol.upper()
        if not self.idempotency_key:
            self.idempotency_key = self._deterministic_key()

    def _deterministic_key(self) -> str:
        explicit = str(self.metadata.get("decision_id") or self.metadata.get("event_id") or "").strip()
        if explicit:
            seed = explicit
        else:
            # Stable within one decision window, including process restarts.
            bucket_seconds = max(5, int(self.metadata.get("idempotency_window_seconds") or 60))
            bucket = int(self.created_at // bucket_seconds)
            stable_metadata = {
                key: self.metadata.get(key)
                for key in ("signal_strength", "trend", "price", "strategy", "cycle_id")
                if key in self.metadata
            }
            seed = json.dumps(
                {
                    "symbol": self.symbol,
                    "action": self.action.value,
                    "mode": self.mode.value,
                    "orb_session": self.orb_session,
                    "bucket": bucket,
                    "reason": self.reason,
                    "metadata": stable_metadata,
                },
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        return f"edge:{self.symbol}:{self.action.value}:{digest}"

    def execution_intent(self) -> Dict[str, Any]:
        trailing_policy = None
        if self.trailing_percent is not None or self.stop_type in {"trailing", "tighten_trailing"}:
            trailing_policy = {
                "type": self.stop_type or "trailing",
                "trailing_percent": self.trailing_percent,
            }
        stop_policy = None
        if self.stop_type and self.stop_type not in {"trailing", "tighten_trailing"}:
            stop_policy = {"type": self.stop_type}

        max_notional = self.metadata.get("max_notional")
        target_notional = self.metadata.get("target_notional")
        ttl = max(5, int(self.metadata.get("command_ttl_seconds") or 30))
        return {
            "contract_version": "edge.execution_intent.v2",
            "intent_id": self.idempotency_key,
            "source_bot": "sentinel-edge",
            "target_bot": "sentinel-pulse",
            "symbol": self.symbol,
            "action": self.action.value,
            "mode": self.mode.value,
            "quantity_policy": {
                "type": "target_notional" if target_notional is not None else "pulse_strategy_capital",
                "target_notional": target_notional,
            },
            "max_notional": max_notional,
            "stop_policy": stop_policy,
            "trailing_policy": trailing_policy,
            "reason": self.reason,
            "expires_at": self.created_at + ttl,
            "idempotency_key": self.idempotency_key,
        }

    def payload(self) -> Dict[str, Any]:
        metadata = dict(self.metadata)
        metadata["execution_intent"] = self.execution_intent()
        return {
            "contract_version": "edge.pulse.handoff.v1",
            "symbol": self.symbol,
            "action": self.action.value,
            "confidence": round(float(self.confidence), 4),
            "reason": self.reason,
            "mode": self.mode.value,
            "orb_session": self.orb_session,
            "stop_type": self.stop_type,
            "trailing_percent": self.trailing_percent,
            "dca": self.dca,
            "idempotency_key": self.idempotency_key,
            "source": "sentinel_edge",
            "created_at": self.created_at,
            "metadata": metadata,
        }


def _metric_reason(reason: str) -> str:
    return str(reason or "unknown").lower().replace(":", "_")


def _record_handoff_metric(command: HandoffCommand, result: str, reason: str) -> None:
    edge_automation_handoffs_total.labels(
        action=command.action.value,
        mode=command.mode.value,
        result=result,
        reason=_metric_reason(reason),
    ).inc()


class AutomationController:
    """Persistent command state and acceptance-based cooldowns."""

    def __init__(self, settings: Optional[AutomationSettings] = None, state_path: Optional[Path] = None):
        self.state_path = state_path or Path(os.getenv("EDGE_AUTOMATION_STATE_FILE", "data/automation_settings.json"))
        loaded = self._load_state()
        self.settings = settings or loaded.get("settings") or AutomationSettings.from_env()
        self.last_handoff: Optional[Dict[str, Any]] = loaded.get("last_handoff")
        self.last_suppressed: Optional[Dict[str, Any]] = loaded.get("last_suppressed")
        self._last_action_at: Dict[str, float] = loaded.get("last_action_at", {})

    def _load_state(self) -> Dict[str, Any]:
        try:
            if not self.state_path.exists():
                return {}
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            settings_data = data.get("settings") if isinstance(data.get("settings"), dict) else data
            settings = AutomationSettings.from_env()
            if isinstance(settings_data, dict):
                if "global_enabled" in settings_data:
                    settings.global_enabled = bool(settings_data["global_enabled"])
                if "mode" in settings_data:
                    settings.mode = AutomationMode(str(settings_data["mode"]))
                if "default_ticker_enabled" in settings_data:
                    settings.default_ticker_enabled = bool(settings_data["default_ticker_enabled"])
                if isinstance(settings_data.get("per_ticker_enabled"), dict):
                    settings.per_ticker_enabled = {str(k).upper(): bool(v) for k, v in settings_data["per_ticker_enabled"].items()}
                if "min_confidence" in settings_data:
                    settings.min_confidence = max(0.0, min(1.0, float(settings_data["min_confidence"])))
                if "cooldown_seconds" in settings_data:
                    settings.cooldown_seconds = max(0, int(settings_data["cooldown_seconds"]))
                if "quiet_when_pulse_absent" in settings_data:
                    settings.quiet_when_pulse_absent = bool(settings_data["quiet_when_pulse_absent"])
                if "command_ttl_seconds" in settings_data:
                    settings.command_ttl_seconds = max(5, int(settings_data["command_ttl_seconds"]))
            return {
                "settings": settings,
                "last_handoff": data.get("last_handoff") if isinstance(data, dict) else None,
                "last_suppressed": data.get("last_suppressed") if isinstance(data, dict) else None,
                "last_action_at": {
                    str(k): float(v) for k, v in (data.get("last_action_at") or {}).items()
                } if isinstance(data, dict) else {},
            }
        except Exception:
            return {}

    def save_settings(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "settings": self.settings.public_dict(),
                    "last_handoff": self.last_handoff,
                    "last_suppressed": self.last_suppressed,
                    "last_action_at": self._last_action_at,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def update_settings(self, patch: Dict[str, Any]) -> AutomationSettings:
        for field_name in ("global_enabled", "default_ticker_enabled", "quiet_when_pulse_absent"):
            if field_name in patch:
                setattr(self.settings, field_name, bool(patch[field_name]))
        if "mode" in patch:
            self.settings.mode = AutomationMode(str(patch["mode"]))
        if "min_confidence" in patch:
            self.settings.min_confidence = max(0.0, min(1.0, float(patch["min_confidence"])))
        if "cooldown_seconds" in patch:
            self.settings.cooldown_seconds = max(0, int(patch["cooldown_seconds"]))
        if "command_ttl_seconds" in patch:
            self.settings.command_ttl_seconds = max(5, int(patch["command_ttl_seconds"]))
        if isinstance(patch.get("per_ticker_enabled"), dict):
            self.settings.per_ticker_enabled = {str(k).upper(): bool(v) for k, v in patch["per_ticker_enabled"].items()}
        self.save_settings()
        return self.settings

    def set_ticker(self, symbol: str, enabled: bool) -> AutomationSettings:
        self.settings.per_ticker_enabled[symbol.upper()] = bool(enabled)
        self.save_settings()
        return self.settings

    def plan(self, command: HandoffCommand) -> tuple[bool, str]:
        allowed, reason = self.settings.can_handoff(command.symbol, command.confidence)
        if not allowed:
            self.record_suppressed(command, reason)
            return False, reason

        # One accepted command per symbol during cooldown prevents plugin/main conflicts.
        key = command.symbol
        last_at = self._last_action_at.get(key, 0.0)
        if self.settings.cooldown_seconds and time.time() - last_at < self.settings.cooldown_seconds:
            self.record_suppressed(command, "cooldown")
            return False, "cooldown"
        return True, "allowed"

    def record_sent(self, command: HandoffCommand, sent: Any) -> None:
        if isinstance(sent, dict):
            feedback = sent
            accepted = bool(feedback.get("sent", False))
            status = str(feedback.get("status") or ("accepted" if accepted else "failed"))
            reason = str(feedback.get("reason") or feedback.get("rejection_reason") or ("pulse_accepted" if accepted else "pulse_send_failed"))
            self.last_handoff = {
                **command.payload(),
                "sent": accepted,
                "handoff_status": status,
                "pulse_feedback": feedback,
            }
            if accepted:
                self._last_action_at[command.symbol] = time.time()
            _record_handoff_metric(command, "sent" if status == "accepted" else status, reason)
            self.save_settings()
            return

        accepted = bool(sent)
        self.last_handoff = {**command.payload(), "sent": accepted}
        if accepted:
            self._last_action_at[command.symbol] = time.time()
        _record_handoff_metric(command, "sent" if accepted else "failed", "pulse_accepted" if accepted else "pulse_send_failed")
        self.save_settings()

    def record_suppressed(self, command: HandoffCommand, reason: str) -> None:
        self.last_suppressed = {**command.payload(), "suppressed_reason": reason}
        _record_handoff_metric(command, "suppressed", reason)
        self.save_settings()

    def status(self) -> Dict[str, Any]:
        return {
            "settings": self.settings.public_dict(),
            "last_handoff": self.last_handoff,
            "last_suppressed": self.last_suppressed,
        }


# Scheduler imports this module before PositionTracker. Replace optimistic
# decision bookkeeping with fill-authoritative reads from DecisionEngine.
try:
    from position_tracker import PositionTracker, _empty_pos

    _original_get = PositionTracker.get

    def _authoritative_get(self, symbol: str) -> Dict[str, Any]:
        position = None
        if self.decision_engine and hasattr(self.decision_engine, "get_position"):
            position = self.decision_engine.get_position(symbol)
        if isinstance(position, dict):
            quantity = float(position.get("quantity", position.get("qty", 0)) or 0)
            pnl = float(position.get("current_pnl_dollar", position.get("pnl", 0)) or 0)
            pnl_pct = float(position.get("current_pnl_pct", position.get("pnl_pct", 0)) or 0)
            return {
                "has_position": quantity > 0 or bool(position.get("has_position", position.get("active", True))),
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "trailing_enabled": bool(position.get("trailing_enabled", position.get("trailing_stop_enabled", False))),
                "trailing_percent": position.get("trailing_percent"),
                "peak_pnl_pct": float(position.get("peak_pnl_pct", pnl_pct) or 0),
                "drawdown_pct": float(position.get("drawdown_pct", 0) or 0),
                "entry_price": position.get("entry_price", position.get("avg_entry")),
                "entry_time": position.get("entry_time"),
                "source": "pulse_decision_engine",
            }
        state = _original_get(self, symbol)
        if state.get("source") == "optimistic":
            return _empty_pos()
        return state

    def _record_command_only(self, symbol: str, decision: Any, entry_price: Optional[float] = None) -> None:
        state = self._state.setdefault(symbol, _empty_pos())
        state["last_command"] = getattr(decision, "value", str(decision))
        state["last_command_at"] = time.time()
        # Do not set/clear position, P&L, or trailing state on command acceptance.

    PositionTracker.get = _authoritative_get
    PositionTracker.on_decision = _record_command_only
except Exception:
    pass
