"""Persistent unresolved command tracking for Edge handoffs."""
from __future__ import annotations

import json
from typing import Any

from automation import AutomationController


_original_init = AutomationController.__init__
_original_save = AutomationController.save_settings
_original_plan = AutomationController.plan
_original_record_sent = AutomationController.record_sent


def _load_pending(controller: AutomationController) -> dict[str, dict[str, Any]]:
    try:
        if not controller.state_path.exists():
            return {}
        data = json.loads(controller.state_path.read_text(encoding="utf-8"))
        pending = data.get("pending_commands")
        if not isinstance(pending, dict):
            return {}
        return {
            str(symbol).upper(): dict(value)
            for symbol, value in pending.items()
            if isinstance(value, dict)
        }
    except Exception:
        return {}


def _init_with_pending(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self._pending_commands = _load_pending(self)


def _save_with_pending(self) -> None:
    _original_save(self)
    try:
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data["pending_commands"] = getattr(self, "_pending_commands", {})
    temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
    temporary.write_text(
        json.dumps(data, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(self.state_path)


def _plan_with_pending(self, command):
    pending_commands = getattr(self, "_pending_commands", {})
    pending = pending_commands.get(command.symbol)
    if pending:
        if str(pending.get("action")) != command.action.value:
            self.record_suppressed(command, "pending_command_unresolved")
            return False, "pending_command_unresolved"
        pending_key = str(pending.get("idempotency_key") or "").strip()
        if pending_key:
            command.idempotency_key = pending_key
            command.metadata["pending_retry"] = True

    allowed, reason = _original_plan(self, command)
    if not allowed:
        return allowed, reason

    if not pending:
        pending_commands[command.symbol] = {
            "action": command.action.value,
            "idempotency_key": command.idempotency_key,
            "created_at": command.created_at,
            "reason": command.reason,
        }
        self._pending_commands = pending_commands
        self.save_settings()
    return True, reason


def _record_sent_with_pending(self, command, sent):
    _original_record_sent(self, command, sent)
    feedback = sent if isinstance(sent, dict) else {}
    accepted = bool(feedback.get("sent", sent if not isinstance(sent, dict) else False))
    status = str(feedback.get("status") or ("accepted" if accepted else "failed"))
    ambiguous = bool(feedback.get("ambiguous_delivery"))

    pending_commands = getattr(self, "_pending_commands", {})
    if accepted or status in {"accepted", "rejected", "suppressed"}:
        pending_commands.pop(command.symbol, None)
    elif status == "failed" and not ambiguous:
        pending_commands.pop(command.symbol, None)
    # Ambiguous delivery stays pending so the next evaluation reuses the exact
    # idempotency key instead of creating a second executable command.
    self._pending_commands = pending_commands
    self.save_settings()


def install() -> None:
    AutomationController.__init__ = _init_with_pending
    AutomationController.save_settings = _save_with_pending
    AutomationController.plan = _plan_with_pending
    AutomationController.record_sent = _record_sent_with_pending
