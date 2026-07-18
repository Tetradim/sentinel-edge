"""Production install hook for Edge's strategist brain."""
import edge_brain_metrics  # noqa: F401 - complete enhanced metric contract first

from edge_brain_runtime import install

install()
