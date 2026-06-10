"""Static checks for Trading Overview action error feedback."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TRADING_OVERVIEW = ROOT / "frontend" / "src" / "components" / "dashboards" / "TradingOverview.tsx"


class TradingOverviewActionErrorsStaticTests(unittest.TestCase):
    def test_ticker_remove_and_metric_errors_are_visible(self):
        text = TRADING_OVERVIEW.read_text(encoding="utf-8")

        self.assertIn("const [actionError, setActionError] = useState('')", text)
        self.assertIn("setActionError('')", text)
        self.assertIn("setActionError(`Failed to remove ${symbol}`)", text)
        self.assertIn("setActionError(`Failed to update ${symbol} metrics`)", text)
        self.assertIn("{actionError &&", text)
        self.assertIn("{actionError}", text)

    def test_remove_ticker_failure_is_caught_before_store_mutation(self):
        text = TRADING_OVERVIEW.read_text(encoding="utf-8")

        self.assertIn("try {\n      setActionError('');\n      await api.removeTicker(symbol);\n      removeTicker(symbol);", text)
        self.assertIn("} catch {\n      setActionError(`Failed to remove ${symbol}`);\n    }", text)


if __name__ == "__main__":
    unittest.main()
