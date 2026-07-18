#!/usr/bin/env python3
"""Production-order entry point for the Edge/Pulse minute sweep."""

# The deployed Edge runtime installs metric compatibility before importing the
# enhanced signal engine. Keep the standalone research runner in the same order.
import edge_brain_metrics  # noqa: F401

from run_edge_pulse_minute_sweep import main


if __name__ == "__main__":
    raise SystemExit(main())
