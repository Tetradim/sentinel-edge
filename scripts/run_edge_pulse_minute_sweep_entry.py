#!/usr/bin/env python3
"""Production-order entry point for the Edge/Pulse minute sweep."""

# The deployed Edge runtime installs metric compatibility before importing the
# enhanced signal engine. Keep the standalone research runner in the same order.
import edge_brain_metrics  # noqa: F401

from edge_brain_data import configure_engine
from signals_enhanced import SignalEngineEnhanced


_original_engine_init = SignalEngineEnhanced.__init__


def _configured_engine_init(self, *args, **kwargs):
    _original_engine_init(self, *args, **kwargs)
    configure_engine(self)


SignalEngineEnhanced.__init__ = _configured_engine_init

from run_edge_pulse_minute_sweep import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
