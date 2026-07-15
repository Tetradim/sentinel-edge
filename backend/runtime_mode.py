"""Runtime mode helpers shared by Edge API and scheduler."""

from __future__ import annotations

import os

# Importing this module is part of every production API/scheduler entry point.
# Install exactly-once delivery and unresolved-command persistence here so the
# live behavior cannot exist only in test-importable patch files.
import live_runtime_install as _live_runtime_install  # noqa: F401,E402


def env_flag_enabled(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def is_dry_run_enabled() -> bool:
    """Default Edge to dry-run unless the operator explicitly disables it."""
    return env_flag_enabled("DRY_RUN", default="true")
