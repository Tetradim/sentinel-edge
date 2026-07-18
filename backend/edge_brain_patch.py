"""Production install hook for Edge's strategist, supervisor, and portfolio brain."""
import edge_brain_metrics  # noqa: F401 - complete enhanced metric contract first
import edge_supervision_contract  # noqa: F401 - execution-intent v3 + lifecycle metadata

import edge_brain_runtime as brain_runtime
from edge_brain_indicators import safe_compute_rsi
from edge_brain_runtime import install as install_brain
from engine import DecisionEngine
from scheduler import EvaluationScheduler
from signals_enhanced import TechnicalIndicators


TechnicalIndicators.compute_rsi = staticmethod(safe_compute_rsi)
install_brain()

# Flare is intelligence-only. Its expiring dark-pool observations are blended
# into the authoritative signal with a strict bounded adjustment.
import flare_intelligence_runtime  # noqa: F401,E402

# Install concrete supervision above the enhanced decision wrapper.
import edge_supervision_runtime as supervision_runtime  # noqa: E402

supervision_runtime._ORIGINAL_DECIDE = DecisionEngine.decide
supervision_runtime._ORIGINAL_EMIT = brain_runtime._emit_supervisory_sell
supervision_runtime.install()

# Install the per-symbol profitability gate above supervision.
import edge_profitability_runtime as profitability_runtime  # noqa: E402

profitability_runtime._ORIGINAL_DECIDE = DecisionEngine.decide
profitability_runtime._ORIGINAL_HANDOFF = EvaluationScheduler._handoff_to_pulse_with_feedback
profitability_runtime._ORIGINAL_EVALUATE = EvaluationScheduler.evaluate_ticker
profitability_runtime.install()

# Install the two-phase portfolio cycle outer-most. During a scheduler sweep it
# scores every unpositioned symbol first, then releases only the top-ranked entry.
import edge_profitability_cycle_runtime as cycle_runtime  # noqa: E402

cycle_runtime._BASE_DECIDE = DecisionEngine.decide
cycle_runtime._PRE_PROFITABILITY_DECIDE = profitability_runtime._ORIGINAL_DECIDE
cycle_runtime._BASE_EVALUATE_ALL = EvaluationScheduler.evaluate_all
cycle_runtime.install()
