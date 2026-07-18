"""Production install hook for Edge's strategist and supervisory brain."""
import edge_brain_metrics  # noqa: F401 - complete enhanced metric contract first
import edge_supervision_contract  # noqa: F401 - typed execution-intent v3

import edge_brain_runtime as brain_runtime
from edge_brain_indicators import safe_compute_rsi
from edge_brain_runtime import install as install_brain
from engine import DecisionEngine
from signals_enhanced import TechnicalIndicators

TechnicalIndicators.compute_rsi = staticmethod(safe_compute_rsi)
install_brain()

# Import only after the enhanced runtime is installed. Explicitly capture the
# currently installed wrappers here rather than at module-import time so test
# collection, reloaders, and alternate entry points cannot make supervision
# delegate to the legacy DecisionEngine by accident.
import edge_supervision_runtime as supervision_runtime  # noqa: E402

supervision_runtime._ORIGINAL_DECIDE = DecisionEngine.decide
supervision_runtime._ORIGINAL_EMIT = brain_runtime._emit_supervisory_sell
supervision_runtime.install()
