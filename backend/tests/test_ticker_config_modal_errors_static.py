"""Static checks for Ticker Config modal action error feedback."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TICKER_CONFIG_MODAL = ROOT / "frontend" / "src" / "components" / "TickerConfigModal.tsx"


class TickerConfigModalErrorsStaticTests(unittest.TestCase):
    def test_save_backtest_and_optimization_failures_are_visible(self):
        text = TICKER_CONFIG_MODAL.read_text(encoding="utf-8")

        self.assertIn("const [actionError, setActionError] = useState('')", text)
        self.assertIn("setActionError('')", text)
        self.assertIn("setActionError('Failed to save ticker configuration')", text)
        self.assertIn(
            "setActionError('Backtest failed. Check backend availability and parameters.')",
            text,
        )
        self.assertIn(
            "setActionError('Optimization failed. Check backend availability and parameter ranges.')",
            text,
        )
        self.assertIn("{actionError &&", text)
        self.assertIn("{actionError}", text)

    def test_analysis_retries_clear_previous_errors_before_requests(self):
        text = TICKER_CONFIG_MODAL.read_text(encoding="utf-8")

        self.assertIn("setActionError('');\n      const result = await api.runBacktest", text)
        self.assertIn("setBacktestResults(result)", text)
        self.assertIn("setActionError('');\n      const result = await api.optimizeStrategy", text)
        self.assertIn("setBacktestResults(result.best_results)", text)


if __name__ == "__main__":
    unittest.main()
