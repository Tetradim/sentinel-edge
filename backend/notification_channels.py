"""Browser-safe operator notification channel discovery."""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Sequence


SCHEMA_VERSION = "edge.notifications.status.v1"
CONFIRMATION_PREVIEW_SCHEMA_VERSION = "edge.notifications.confirmation_preview.v1"
CONFIRMATION_FEEDBACK_SCHEMA_VERSION = "edge.notifications.confirmation_feedback.v1"
CONFIRMATION_IDEMPOTENCY_PREFIX = "edge:notification-confirmation:"
_PLACEHOLDER_VALUES = {"", "0", "placeholder", "none", "null", "unset", "http://placeholder/no-slack"}
_SENSITIVE_METADATA_FRAGMENTS = (
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "webhook",
)

_CHANNELS = [
    {
        "id": "telegram",
        "label": "Telegram",
        "required_env": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_TRADING_CHAT"],
        "delivery_path": "Alertmanager telegram_configs",
        "purpose": "Trading/regime notifications and operator review prompts.",
        "confirmation_path": "Future human-in-the-loop confirmation messages.",
    },
    {
        "id": "discord",
        "label": "Discord / Sentinel Echo",
        "required_env": ["DISCORD_WEBHOOK_URL"],
        "delivery_path": "Alertmanager webhook relay or Sentinel Echo bridge",
        "purpose": "Discord-style team relay for regime and automation events.",
        "confirmation_path": "Future Discord button or bot-mediated confirmations.",
    },
    {
        "id": "slack",
        "label": "Slack",
        "required_env": ["SLACK_WEBHOOK_URL"],
        "delivery_path": "Alertmanager slack_configs",
        "purpose": "Existing trading-alert channel notifications.",
        "confirmation_path": "Notification-only until an operator confirmation workflow is added.",
    },
    {
        "id": "whatsapp",
        "label": "WhatsApp",
        "required_env": ["WHATSAPP_WEBHOOK_URL"],
        "delivery_path": "External WhatsApp webhook relay",
        "purpose": "Future mobile operator notifications for critical safety events.",
        "confirmation_path": "Future mobile confirmation relay; currently discovery only.",
    },
]

_CONFIRMATION_ACTIONS = [
    {
        "id": "live_handoff",
        "label": "Live Pulse handoff",
        "description": "Ask an operator to approve a live Edge to Pulse handoff before broker-facing side effects.",
        "risk": "high",
        "requires_confirmation": True,
        "default_channels": ["telegram", "discord", "slack", "whatsapp"],
        "paper_live_semantics": "Paper mode can rehearse the prompt; live mode must wait for an operator approval.",
        "confirm_label": "Confirm live handoff",
        "reject_label": "Reject handoff",
        "expires_in_seconds": 300,
    },
    {
        "id": "emergency_exit",
        "label": "Emergency exit",
        "description": "Ask an operator to approve a position exit instruction before it is relayed to Pulse.",
        "risk": "critical",
        "requires_confirmation": True,
        "default_channels": ["telegram", "discord", "slack", "whatsapp"],
        "paper_live_semantics": "Paper mode rehearses the prompt; live mode must be explicit because it may close risk.",
        "confirm_label": "Confirm emergency exit",
        "reject_label": "Reject exit",
        "expires_in_seconds": 180,
    },
    {
        "id": "risk_reduction",
        "label": "Risk reduction",
        "description": "Ask an operator to approve a portfolio or symbol-level exposure reduction.",
        "risk": "critical",
        "requires_confirmation": True,
        "default_channels": ["telegram", "discord", "slack", "whatsapp"],
        "paper_live_semantics": "Paper mode is informational; live mode must preserve a human approval step.",
        "confirm_label": "Confirm risk reduction",
        "reject_label": "Reject reduction",
        "expires_in_seconds": 300,
    },
    {
        "id": "trailing_stop",
        "label": "Trailing-stop change",
        "description": "Ask an operator to approve a trailing-stop enablement or adjustment before Pulse receives it.",
        "risk": "medium",
        "requires_confirmation": True,
        "default_channels": ["telegram", "discord", "slack", "whatsapp"],
        "paper_live_semantics": "Paper mode can preview the guardrail; live mode must include operator confirmation.",
        "confirm_label": "Confirm trailing stop",
        "reject_label": "Reject trailing stop",
        "expires_in_seconds": 300,
    },
]


def notification_channel_status(env: Mapping[str, str] | None = None) -> Dict:
    """Return redacted notification channel readiness for UI discovery."""
    source = env if env is not None else os.environ
    channels = [_channel_status(channel, source) for channel in _CHANNELS]
    configured_channels = [channel["id"] for channel in channels if channel["configured"]]
    missing_channels = [channel["id"] for channel in channels if not channel["configured"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": "read_only_discovery",
        "secret_values": "redacted",
        "channels": channels,
        "confirmation_preview": {
            "schema_version": CONFIRMATION_PREVIEW_SCHEMA_VERSION,
            "endpoint": "POST /api/notifications/confirmation/preview",
            "send_side_effect": "none_preview_only",
            "secret_values": "redacted",
        },
        "confirmation_feedback": {
            "schema_version": CONFIRMATION_FEEDBACK_SCHEMA_VERSION,
            "endpoint": "POST /api/notifications/confirmation/feedback",
            "notification_side_effect": "none",
            "pulse_side_effect": "none",
            "secret_values": "redacted",
        },
        "confirmation_actions": [_confirmation_action_status(action) for action in _CONFIRMATION_ACTIONS],
        "summary": {
            "configured_count": len(configured_channels),
            "total_count": len(channels),
            "configured_channels": configured_channels,
            "missing_channels": missing_channels,
        },
    }


def notification_confirmation_preview(
    action_type: str,
    *,
    symbol: str | None = None,
    mode: str = "paper",
    channel_ids: Sequence[str] | None = None,
    reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    env: Mapping[str, str] | None = None,
) -> Dict:
    """Build a redacted operator confirmation prompt without sending a message."""
    source = env if env is not None else os.environ
    action = _confirmation_action(action_type)
    normalized_mode = _normalize_mode(mode)
    normalized_symbol = _normalize_symbol(symbol)
    selected_channel_ids = _normalize_channel_ids(channel_ids, action["default_channels"])
    channels_by_id = {channel["id"]: channel for channel in _CHANNELS}
    channel_statuses = [
        _confirmation_channel_preview(_channel_status(channels_by_id[channel_id], source))
        for channel_id in selected_channel_ids
    ]
    target = normalized_symbol or "GLOBAL"
    normalized_reason = str(reason or "").strip()

    return {
        "schema_version": CONFIRMATION_PREVIEW_SCHEMA_VERSION,
        "action_type": action["id"],
        "idempotency_key": (
            f"edge:notification-confirmation:{normalized_mode}:{action['id']}:{target.lower()}"
        ),
        "mode": normalized_mode,
        "requires_confirmation": action["requires_confirmation"],
        "expires_in_seconds": action["expires_in_seconds"],
        "channels": channel_statuses,
        "message": {
            "title": action["label"],
            "body": _confirmation_body(action, target, normalized_mode, normalized_reason),
            "summary_lines": [
                f"Action: {action['label']}",
                f"Target: {target}",
                f"Mode: {normalized_mode}",
                f"Reason: {normalized_reason or 'not provided'}",
                "Delivery: preview only; no message sent",
            ],
            "confirm_label": action["confirm_label"],
            "reject_label": action["reject_label"],
        },
        "safety": {
            "send_side_effect": "none_preview_only",
            "secret_values": "redacted",
            "requires_operator_confirmation": True,
            "live_mode_requires_operator": normalized_mode == "live",
            "paper_mode_semantics": "rehearsal_only",
        },
        "context": {
            "symbol": normalized_symbol,
            "reason": normalized_reason,
            "metadata": _redact_metadata(metadata or {}),
        },
    }


def notification_confirmation_feedback(
    *,
    idempotency_key: str,
    action_type: str,
    decision: str,
    channel_id: str,
    operator_ref: str | None = None,
    reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Dict:
    """Normalize a relay/operator confirmation response without side effects."""
    normalized_idempotency_key = _normalize_confirmation_idempotency_key(idempotency_key)
    action = _confirmation_action(action_type)
    _validate_confirmation_idempotency_action(normalized_idempotency_key, action["id"])
    normalized_decision = _normalize_confirmation_decision(decision)
    normalized_channel_id = _normalize_channel_id(channel_id)
    normalized_reason = str(reason or "").strip()
    accepted = normalized_decision == "approved"

    return {
        "schema_version": CONFIRMATION_FEEDBACK_SCHEMA_VERSION,
        "idempotency_key": normalized_idempotency_key,
        "action_type": action["id"],
        "channel_id": normalized_channel_id,
        "decision": normalized_decision,
        "accepted": accepted,
        "status": normalized_decision,
        "operator_ref": str(operator_ref or "").strip(),
        "reason": normalized_reason,
        "safety": {
            "notification_side_effect": "none",
            "pulse_side_effect": "none",
            "secret_values": "redacted",
            "requires_operator_confirmation": True,
        },
        "context": {
            "metadata": _redact_metadata(metadata or {}),
        },
    }


def _channel_status(channel: Dict, env: Mapping[str, str]) -> Dict:
    required_env = list(channel["required_env"])
    missing_env = [name for name in required_env if not _env_has_value(env, name)]
    configured_env = [name for name in required_env if name not in missing_env]
    configured = len(missing_env) == 0

    return {
        "id": channel["id"],
        "label": channel["label"],
        "configured": configured,
        "status": "configured" if configured else "missing_env",
        "required_env": required_env,
        "configured_env": configured_env,
        "missing_env": missing_env,
        "delivery_path": channel["delivery_path"],
        "purpose": channel["purpose"],
        "confirmation_path": channel["confirmation_path"],
    }


def _env_has_value(env: Mapping[str, str], name: str) -> bool:
    value = str(env.get(name, "") or "").strip()
    if value.lower() in _PLACEHOLDER_VALUES:
        return False
    if "placeholder" in value.lower():
        return False
    return True


def _confirmation_action_status(action: Dict[str, Any]) -> Dict:
    return {
        "id": action["id"],
        "label": action["label"],
        "description": action["description"],
        "risk": action["risk"],
        "requires_confirmation": action["requires_confirmation"],
        "default_channels": list(action["default_channels"]),
        "paper_live_semantics": action["paper_live_semantics"],
        "preview_contract": CONFIRMATION_PREVIEW_SCHEMA_VERSION,
        "expires_in_seconds": action["expires_in_seconds"],
    }


def _confirmation_action(action_type: str) -> Dict[str, Any]:
    normalized = str(action_type or "").strip().lower()
    for action in _CONFIRMATION_ACTIONS:
        if action["id"] == normalized:
            return action
    valid_actions = ", ".join(action["id"] for action in _CONFIRMATION_ACTIONS)
    raise ValueError(f"Unknown confirmation action '{action_type}'. Expected one of: {valid_actions}.")


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "paper").strip().lower()
    if normalized not in {"recommend_only", "paper", "live"}:
        raise ValueError("Notification confirmation preview mode must be recommend_only, paper, or live.")
    return normalized


def _normalize_symbol(symbol: str | None) -> str | None:
    if symbol is None:
        return None
    normalized = str(symbol).strip().upper()
    return normalized or None


def _normalize_channel_ids(channel_ids: Sequence[str] | None, default_channel_ids: Sequence[str]) -> list[str]:
    known_channels = {channel["id"] for channel in _CHANNELS}
    if isinstance(channel_ids, str):
        requested = [channel_ids]
    else:
        requested = list(default_channel_ids if channel_ids is None else channel_ids)
    selected: list[str] = []
    for channel_id in requested:
        normalized = str(channel_id or "").strip().lower()
        if not normalized or normalized in selected:
            continue
        if normalized not in known_channels:
            valid_channels = ", ".join(sorted(known_channels))
            raise ValueError(f"Unknown notification channel '{channel_id}'. Expected one of: {valid_channels}.")
        selected.append(normalized)
    return selected or list(default_channel_ids)


def _normalize_channel_id(channel_id: str) -> str:
    selected = _normalize_channel_ids([channel_id], [])
    if not selected:
        raise ValueError("Notification channel is required.")
    return selected[0]


def _normalize_confirmation_idempotency_key(idempotency_key: str) -> str:
    normalized = str(idempotency_key or "").strip()
    if not normalized:
        raise ValueError("Notification confirmation feedback requires an idempotency_key.")
    if not normalized.startswith(CONFIRMATION_IDEMPOTENCY_PREFIX):
        raise ValueError(
            "Notification confirmation feedback idempotency_key must start with "
            f"{CONFIRMATION_IDEMPOTENCY_PREFIX}."
        )
    return normalized


def _validate_confirmation_idempotency_action(idempotency_key: str, action_id: str) -> None:
    parts = idempotency_key.split(":")
    if len(parts) < 5 or parts[3] != action_id:
        raise ValueError("Notification confirmation feedback action_type must match the idempotency_key action.")


def _normalize_confirmation_decision(decision: str) -> str:
    normalized = str(decision or "").strip().lower()
    aliases = {
        "approve": "approved",
        "approved": "approved",
        "confirm": "approved",
        "confirmed": "approved",
        "reject": "rejected",
        "rejected": "rejected",
        "deny": "rejected",
        "denied": "rejected",
        "expire": "expired",
        "expired": "expired",
        "timeout": "expired",
    }
    if normalized not in aliases:
        raise ValueError("Notification confirmation decision must be approved, rejected, or expired.")
    return aliases[normalized]


def _confirmation_channel_preview(channel: Dict[str, Any]) -> Dict:
    return {
        "id": channel["id"],
        "label": channel["label"],
        "configured": channel["configured"],
        "status": channel["status"],
        "delivery_path": channel["delivery_path"],
        "confirmation_path": channel["confirmation_path"],
        "missing_env": list(channel["missing_env"]),
    }


def _confirmation_body(action: Dict[str, Any], target: str, mode: str, reason: str) -> str:
    reason_clause = f" Reason: {reason}." if reason else ""
    return (
        f"{action['label']} confirmation requested for {target} in {mode} mode."
        f"{reason_clause} This is a preview contract only; Edge does not send a message from this endpoint."
    )


def _redact_metadata(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(value, Mapping):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            redacted[key_text] = "[redacted]" if _is_sensitive_metadata_key(key_text) else _redact_metadata(item, depth + 1)
        return redacted
    if isinstance(value, (list, tuple)):
        return [_redact_metadata(item, depth + 1) for item in value[:25]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _is_sensitive_metadata_key(key: str) -> bool:
    normalized = key.lower()
    return (
        any(fragment in normalized for fragment in _SENSITIVE_METADATA_FRAGMENTS)
        or normalized == "key"
        or normalized.endswith("_key")
        or normalized.endswith("-key")
    )
