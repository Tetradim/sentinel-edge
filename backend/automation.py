"""Automation controls for Sentinel Edge -> Sentinel Pulse handoff.

The controls are deliberately separate from signal generation. Edge may score
opportunities continuously, but live Pulse commands are allowed only when the
global handoff switch, the selected mode, and the per-ticker switch all permit
it. Turning the global switch off never erases per-ticker preferences.
"""
from __future__ import annotations

import os
import json
import time
import uuid
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

    @classmethod
    def from_env(cls) -> "AutomationSettings":
        enabled = os.getenv("EDGE_PULSE_HANDOFF_ENABLED", "false").lower() in ("1", "true", "yes", "on")
        mode_raw = os.getenv("EDGE_AUTOMATION_MODE", AutomationMode.RECOMMEND_ONLY.value).lower()
        try:
            mode = AutomationMode(mode_raw)
        except ValueError:
            mode = AutomationMode.RECOMMEND_ONLY
        default_ticker = os.getenv("EDGE_PULSE_HANDOFF_DEFAULT_TICKERS", "false").lower() in ("1", "true", "yes", "on")
        return cls(global_enabled=enabled, mode=mode, default_ticker_enabled=default_ticker)

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
            bucket = int(self.created_at // 60)
            self.idempotency_key = f"edge:{self.symbol}:{self.action.value}:{self.orb_session}:{bucket}:{uuid.uuid4().hex[:8]}"

    def payload(self) -> Dict[str, Any]:
        return {
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
            "metadata": self.metadata,
        }


def _metric_reason(reason: str) -> str:
    reason = str(reason or "unknown").lower()
    return reason.replace(":", "_")


def _record_handoff_metric(command: HandoffCommand, result: str, reason: str) -> None:
    edge_automation_handoffs_total.labels(
        action=command.action.value,
        mode=command.mode.value,
        result=result,
        reason=_metric_reason(reason),
    ).inc()


class AutomationController:
    """Runtime state and cooldowns for Pulse handoff."""

    def __init__(self, settings: Optional[AutomationSettings] = None, state_path: Optional[Path] = None):
        self.state_path = state_path or Path(
            os.getenv("EDGE_AUTOMATION_STATE_FILE", "data/automation_settings.json")
        )
        self.settings = settings or self._load_settings() or AutomationSettings.from_env()
        self.last_handoff: Optional[Dict[str, Any]] = None
        self.last_suppressed: Optional[Dict[str, Any]] = None
        self._last_action_at: Dict[str, float] = {}

    def _load_settings(self) -> Optional[AutomationSettings]:
        try:
            if not self.state_path.exists():
                return None
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            settings = AutomationSettings.from_env()
            if isinstance(data, dict):
                if "global_enabled" in data:
                    settings.global_enabled = bool(data["global_enabled"])
                if "mode" in data:
                    settings.mode = AutomationMode(str(data["mode"]))
                if "default_ticker_enabled" in data:
                    settings.default_ticker_enabled = bool(data["default_ticker_enabled"])
                if "per_ticker_enabled" in data and isinstance(data["per_ticker_enabled"], dict):
                    settings.per_ticker_enabled = {
                        str(symbol).upper(): bool(enabled)
                        for symbol, enabled in data["per_ticker_enabled"].items()
                    }
                if "min_confidence" in data:
                    settings.min_confidence = max(0.0, min(1.0, float(data["min_confidence"])))
                if "cooldown_seconds" in data:
                    settings.cooldown_seconds = max(0, int(data["cooldown_seconds"]))
                if "quiet_when_pulse_absent" in data:
                    settings.quiet_when_pulse_absent = bool(data["quiet_when_pulse_absent"])
            return settings
        except Exception:
            return None

    def save_settings(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self.settings.public_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def update_settings(self, patch: Dict[str, Any]) -> AutomationSettings:
        if "global_enabled" in patch:
            self.settings.global_enabled = bool(patch["global_enabled"])
        if "mode" in patch:
            self.settings.mode = AutomationMode(str(patch["mode"]))
        if "default_ticker_enabled" in patch:
            self.settings.default_ticker_enabled = bool(patch["default_ticker_enabled"])
        if "min_confidence" in patch:
            self.settings.min_confidence = max(0.0, min(1.0, float(patch["min_confidence"])))
        if "cooldown_seconds" in patch:
            self.settings.cooldown_seconds = max(0, int(patch["cooldown_seconds"]))
        if "quiet_when_pulse_absent" in patch:
            self.settings.quiet_when_pulse_absent = bool(patch["quiet_when_pulse_absent"])
        if "per_ticker_enabled" in patch and isinstance(patch["per_ticker_enabled"], dict):
            self.settings.per_ticker_enabled = {
                str(symbol).upper(): bool(enabled)
                for symbol, enabled in patch["per_ticker_enabled"].items()
            }
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

        key = f"{command.symbol}:{command.action.value}"
        now = time.time()
        last_at = self._last_action_at.get(key, 0.0)
        if self.settings.cooldown_seconds and now - last_at < self.settings.cooldown_seconds:
            self.record_suppressed(command, "cooldown")
            return False, "cooldown"

        self._last_action_at[key] = now
        return True, "allowed"

    def record_sent(self, command: HandoffCommand, sent: Any) -> None:
        if isinstance(sent, dict):
            feedback = sent
            accepted = bool(feedback.get("sent", False))
            status = str(feedback.get("status") or ("accepted" if accepted else "failed"))
            reason = str(
                feedback.get("reason")
                or feedback.get("rejection_reason")
                or ("pulse_accepted" if accepted else "pulse_send_failed")
            )
            metric_result = "sent" if status == "accepted" else status
            self.last_handoff = {
                **command.payload(),
                "sent": accepted,
                "handoff_status": status,
                "pulse_feedback": feedback,
            }
            _record_handoff_metric(command, metric_result, reason)
            return

        self.last_handoff = {**command.payload(), "sent": sent}
        if sent:
            _record_handoff_metric(command, "sent", "pulse_accepted")
        else:
            _record_handoff_metric(command, "failed", "pulse_send_failed")

    def record_suppressed(self, command: HandoffCommand, reason: str) -> None:
        self.last_suppressed = {**command.payload(), "suppressed_reason": reason}
        _record_handoff_metric(command, "suppressed", reason)

    def status(self) -> Dict[str, Any]:
        return {
            "settings": self.settings.public_dict(),
            "last_handoff": self.last_handoff,
            "last_suppressed": self.last_suppressed,
        }
