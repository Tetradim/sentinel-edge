#!/usr/bin/env python3
"""Install the production Edge patch stack before loading the profit replay."""
import edge_brain_patch  # noqa: F401 - metrics, enhanced brain, supervision
from integration.historical_profit_replay import main


if __name__ == "__main__":
    raise SystemExit(main())
