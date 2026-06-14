"""Static regressions for P1 review fixes.

These tests avoid importing the FastAPI app because the local review
environment may not have runtime dependencies installed. They verify the code
contracts that previously drifted.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class P1RegressionStaticTests(unittest.TestCase):
    def test_scheduler_does_not_optimistically_update_position_on_failed_handoff(self):
        text = read("backend/scheduler.py")
        self.assertIn("handoff_sent = False", text)
        self.assertIn("if handoff_sent:", text)
        self.assertIn("self.position_tracker.on_decision(symbol, decision, entry_price=price)", text)

    def test_daily_pnl_guard_uses_real_sources_not_constant_zero_stub(self):
        text = read("backend/scheduler.py")
        self.assertIn("get_account_status()", text)
        self.assertIn("_extract_daily_pnl_pct", text)
        self.assertNotIn("# For now, return 0.0", text)

    def test_ticker_config_handles_missing_mongo_for_unit_paths(self):
        text = read("backend/server.py")
        self.assertIn("_get_ticker_config_doc", text)
        self.assertIn("_save_ticker_config", text)
        self.assertIn("if db is None:", text)
        self.assertIn("_memory_ticker_configs", text)

    def test_price_provider_config_contract_is_backend_supported(self):
        server = read("backend/server.py")
        api = read("frontend/src/lib/api.ts")
        modal = read("frontend/src/components/TickerConfigModal.tsx")

        self.assertIn("price_providers: List[str]", server)
        self.assertIn('doc.get("price_providers"', server)
        self.assertIn('"price_providers": price_providers', server)
        self.assertNotIn("/api/tickers/${symbol}/price-providers", api)
        self.assertIn("DEFAULT_PROVIDERS = ['yfinance']", modal)

    def test_alpaca_is_not_presented_as_selectable_until_runtime_support_exists(self):
        fetcher = read("backend/price_fetcher.py")
        catalog = read("backend/providers/catalog.py")
        modal = read("frontend/src/components/TickerConfigModal.tsx")

        self.assertNotIn('"alpaca":', fetcher)
        self.assertNotIn('key="alpaca"', catalog)
        self.assertNotIn("'alpaca'", modal)


if __name__ == "__main__":
    unittest.main()
