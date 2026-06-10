"""Static checks for the native scanner workbench catalog and UI wiring."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "backend" / "scanner_workbench_catalog.py"
SERVER = ROOT / "backend" / "server.py"
API = ROOT / "frontend" / "src" / "lib" / "api.ts"
TYPES = ROOT / "frontend" / "src" / "types" / "index.ts"
OPERATIONS_PANEL = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "OperationsPanel.tsx"
ASSET_DATA = ROOT / "frontend" / "src" / "components" / "asset-command" / "data.ts"
ASSET_TYPES = ROOT / "frontend" / "src" / "components" / "asset-command" / "types.ts"
SCANNER_WORKBENCH = ROOT / "frontend" / "src" / "components" / "dashboards" / "ScannerWorkbench.tsx"


class ScannerWorkbenchStaticTests(unittest.TestCase):
    def test_backend_catalog_defines_native_scanner_contract(self):
        text = CATALOG.read_text(encoding="utf-8")

        self.assertIn('SCANNER_WORKBENCH_SCHEMA_VERSION = "edge.scanner_workbench.v1"', text)
        self.assertIn('SCANNER_WORKBENCH_WATCH_INTENT_VALIDATION_VERSION = "edge.scanner_workbench.watch_intent_validation.v1"', text)
        self.assertIn("edge_native_paraphrased_public_research_not_trendspider_import", text)
        self.assertIn("scanner_workbench_catalog", text)
        self.assertIn("validate_scanner_watch_intent", text)
        self.assertIn("Bullish Engulfing Recent 3-Day", text)
        self.assertIn("Ascending Triangle Breakup", text)
        self.assertIn("BB/KC Squeeze + Anchored VWAP", text)
        self.assertIn("15-Min ORB High Breakout", text)
        self.assertIn("Daily Pivot Breakout", text)
        self.assertIn("Sector Rotation Matrix", text)
        self.assertIn("Legends-Inspired Technical Growth Pack", text)
        self.assertIn("source_urls", text)

    def test_backend_catalog_exposes_recommended_tickers_strategies_and_indicators(self):
        text = CATALOG.read_text(encoding="utf-8")

        for symbol in ["SPY", "QQQ", "AMD", "SHOP", "OXY", "NVDA", "TSLA", "AVGO", "ES1!"]:
            self.assertIn(f'"symbol": "{symbol}"', text)

        for phrase in [
            "ORB Momentum Continuation",
            "Squeeze Breakout Confirmation",
            "Squeeze Entry Long 1-Hour",
            "Bollinger Band Breakout Long 1-Hour",
            "Williams %R and MACD Long 15-Min",
            "Hammer Candlestick Reversal Long 1-Hour",
            "Williams %R Reversal Long Daily",
            "DEMA Crossover Long 30-Min",
            "EMA Crossover Long 30-Min",
            "SuperTrend Scalper Long",
            "Turtle Breakout Long",
            "MACD Crossover Long",
            "Sector Rotation Relative Momentum",
            "Anchored VWAP",
            "Williams %R",
            "DEMA Pair",
            "SMA 20/50 Trend Pair",
            "Trailing Stop State",
            "Vortex Indicator",
            "Relative Volume",
            "Opening Range",
        ]:
            self.assertIn(phrase, text)

    def test_backend_catalog_keeps_strategy_references_resolvable(self):
        import sys

        sys.path.insert(0, str(ROOT / "backend"))
        from scanner_workbench_catalog import INDICATORS, SCANNERS, STRATEGIES  # noqa: E402

        scanner_ids = {scanner["id"] for scanner in SCANNERS}
        indicator_ids = {indicator["id"] for indicator in INDICATORS}

        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy["id"]):
                self.assertTrue(set(strategy["scanner_ids"]).issubset(scanner_ids))
                self.assertTrue(set(strategy["indicator_ids"]).issubset(indicator_ids))

    def test_server_exposes_scanner_workbench_catalog_route(self):
        text = SERVER.read_text(encoding="utf-8")

        self.assertIn("from scanner_workbench_catalog import scanner_workbench_catalog", text)
        self.assertIn("validate_scanner_watch_intent", text)
        self.assertIn('@api_router.get("/scanner-workbench/catalog")', text)
        self.assertIn('@api_router.post("/scanner-workbench/watch-intent/validate")', text)
        self.assertIn("return scanner_workbench_catalog()", text)
        self.assertIn("return validate_scanner_watch_intent(intent)", text)

    def test_frontend_api_and_types_include_scanner_workbench_contract(self):
        api = API.read_text(encoding="utf-8")
        types = TYPES.read_text(encoding="utf-8")

        self.assertIn("ScannerWorkbenchCatalog", api)
        self.assertIn("async getScannerWorkbenchCatalog", api)
        self.assertIn("fetchJSON<ScannerWorkbenchCatalog>", api)
        self.assertIn("async validateScannerWorkbenchWatchIntent", api)
        self.assertIn("fetchJSON<ScannerWorkbenchWatchIntentValidation>", api)
        self.assertIn("export interface ScannerWorkbenchCatalog", types)
        self.assertIn("export interface ScannerWorkbenchWatchIntent", types)
        self.assertIn("export interface ScannerWorkbenchWatchIntentValidation", types)
        self.assertIn("export interface ScannerWorkbenchScanner", types)
        self.assertIn("export interface ScannerWorkbenchTicker", types)
        self.assertIn("export interface ScannerWorkbenchStrategy", types)
        self.assertIn("export interface ScannerWorkbenchIndicator", types)

    def test_operations_deck_exposes_scanner_workbench_tab(self):
        panel = OPERATIONS_PANEL.read_text(encoding="utf-8")
        data = ASSET_DATA.read_text(encoding="utf-8")
        types = ASSET_TYPES.read_text(encoding="utf-8")

        self.assertIn("ScannerWorkbench", panel)
        self.assertIn("activeView === 'scanners'", panel)
        self.assertIn("{ id: 'scanners', label: 'Scanner Workbench'", data)
        self.assertIn("'scanners'", types)

    def test_scanner_workbench_ui_has_watch_tabs_and_no_collection_tab(self):
        dashboard = SCANNER_WORKBENCH.read_text(encoding="utf-8")

        self.assertIn("SCANNER_WORKBENCH_STORAGE_KEY", dashboard)
        self.assertIn("sentinel-edge.scanner-workbench.watchlist.v1", dashboard)
        self.assertIn("getScannerWorkbenchCatalog", dashboard)
        self.assertIn("validateScannerWorkbenchWatchIntent", dashboard)
        self.assertIn("Validate watch intent", dashboard)
        self.assertIn("validation?.invalid_count", dashboard)
        self.assertIn("applySanitizedWatchIntent", dashboard)
        self.assertIn("tabs = [", dashboard)
        self.assertIn("Scanners", dashboard)
        self.assertIn("Tickers", dashboard)
        self.assertIn("Strategies", dashboard)
        self.assertIn("Indicators", dashboard)
        self.assertIn("selectedTickerSymbols", dashboard)
        self.assertIn('WatchSummary label="Ticker watch"', dashboard)
        self.assertIn("collection_packs", dashboard)
        self.assertIn("Collections distilled into packs", dashboard)
        self.assertNotIn("id: 'collections'", dashboard)
        self.assertNotIn("Collections</button>", dashboard)


if __name__ == "__main__":
    unittest.main()
