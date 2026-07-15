"""Install live-money command-delivery behavior for every Edge entry point.

This module is imported by :mod:`runtime_mode`, which is shared by the API and
the scheduler. Installation is deliberately idempotent so tests, reloaders and
packaged entry points cannot stack wrappers.
"""
from __future__ import annotations

from automation import HandoffCommand
from handoff_delivery_patch import install as _install_handoff_delivery
from pending_command_patch import install as _install_pending_commands


_installed = False
_original_deterministic_key = HandoffCommand._deterministic_key


def _contract_compatible_deterministic_key(self: HandoffCommand) -> str:
    """Return a stable key that also satisfies the versioned handoff schema.

    The merged deterministic implementation produced four components, while the
    shared PulseHandoffRequest contract still requires:
    edge:{symbol}:{action}:{orb_session}:{minute_bucket}:{nonce}
    """
    compact = _original_deterministic_key(self)
    nonce = compact.rsplit(":", 1)[-1]
    explicit = str(
        self.metadata.get("decision_id")
        or self.metadata.get("event_id")
        or ""
    ).strip()
    if explicit:
        bucket = 0
    else:
        bucket_seconds = max(
            5,
            int(self.metadata.get("idempotency_window_seconds") or 60),
        )
        bucket = int(self.created_at // bucket_seconds)
    return (
        f"edge:{self.symbol}:{self.action.value}:{self.orb_session}:"
        f"{bucket}:{nonce}"
    )


def install() -> None:
    global _installed
    if _installed:
        return
    HandoffCommand._deterministic_key = _contract_compatible_deterministic_key
    _install_pending_commands()
    _install_handoff_delivery()
    _installed = True


install()
