"""Pytest collection rules for backend tests."""
import os
from pathlib import Path

import pytest


EXTERNAL_API_TEST_MODULES = {
    "test_correlation_engine.py",
    "test_decision_feed_and_tickers.py",
    "test_p1_features.py",
    "test_sentinel_edge.py",
}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: requires REACT_APP_BACKEND_URL pointing at a running Sentinel Edge backend",
    )


def pytest_collection_modifyitems(config, items):
    has_backend_url = bool(os.environ.get("REACT_APP_BACKEND_URL", "").strip())
    skip_without_backend = pytest.mark.skip(
        reason="requires REACT_APP_BACKEND_URL pointing at a running Sentinel Edge backend"
    )

    for item in items:
        path = Path(str(getattr(item, "path", getattr(item, "fspath", ""))))
        if path.name not in EXTERNAL_API_TEST_MODULES:
            continue

        item.add_marker(pytest.mark.integration)
        if not has_backend_url:
            item.add_marker(skip_without_backend)
