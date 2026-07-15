"""Install live-money command-delivery behavior for every Edge entry point.

This module is imported by :mod:`runtime_mode`, which is shared by the API and
the scheduler. Installation is deliberately idempotent so tests, reloaders and
packaged entry points cannot stack wrappers.
"""
from __future__ import annotations

from handoff_delivery_patch import install as _install_handoff_delivery
from pending_command_patch import install as _install_pending_commands


_installed = False


def install() -> None:
    global _installed
    if _installed:
        return
    _install_pending_commands()
    _install_handoff_delivery()
    _installed = True


install()
