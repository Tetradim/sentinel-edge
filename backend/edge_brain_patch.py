"""Production install hook for Edge's strategist and supervisory brain."""
import edge_brain_metrics  # noqa: F401 - complete enhanced metric contract first
import edge_supervision_contract  # noqa: F401 - typed execution-intent v3

from edge_brain_indicators import safe_compute_rsi
from edge_brain_runtime import install as install_brain
from edge_supervision_runtime import install as install_supervision
from signals_enhanced import TechnicalIndicators

TechnicalIndicators.compute_rsi = staticmethod(safe_compute_rsi)
install_brain()
install_supervision()
