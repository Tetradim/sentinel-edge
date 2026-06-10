"""Browser-safe operator notification channel discovery."""

from __future__ import annotations

import os
from typing import Dict, Mapping


SCHEMA_VERSION = "edge.notifications.status.v1"
_PLACEHOLDER_VALUES = {"", "0", "placeholder", "none", "null", "unset", "http://placeholder/no-slack"}

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
        "summary": {
            "configured_count": len(configured_channels),
            "total_count": len(channels),
            "configured_channels": configured_channels,
            "missing_channels": missing_channels,
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
