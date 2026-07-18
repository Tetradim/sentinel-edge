"""Production install hook for Edge's strategist brain."""
import edge_brain_metrics  # noqa: F401 - complete enhanced metric contract first

from edge_brain_indicators import safe_compute_rsi
from edge_brain_runtime import install
from signals_enhanced import TechnicalIndicators

TechnicalIndicators.compute_rsi = staticmethod(safe_compute_rsi)
install()
