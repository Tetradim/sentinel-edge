"""Static checks for Settings dashboard automation save error feedback."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SETTINGS = ROOT / "frontend" / "src" / "components" / "dashboards" / "SettingsDashboard.tsx"


class SettingsActionErrorsStaticTests(unittest.TestCase):
    def test_automation_save_failures_are_visible_and_rollback_optimistic_state(self):
        text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("const [settingsError, setSettingsError] = useState('')", text)
        self.assertIn("const previous = automation", text)
        self.assertIn("setSettingsError('')", text)
        self.assertIn("if (!response.ok) throw new Error('Automation settings failed to save')", text)
        self.assertIn("setAutomation(previous)", text)
        self.assertIn("setSettingsError(error instanceof Error ? error.message : 'Automation settings failed to save')", text)
        self.assertIn("{settingsError &&", text)
        self.assertIn("{settingsError}", text)

    def test_ticker_handoff_save_failures_are_visible(self):
        text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("if (!response.ok) throw new Error(`Failed to save ${symbol} handoff setting`)", text)
        self.assertIn("setSettingsError(error instanceof Error ? error.message : `Failed to save ${symbol} handoff setting`)", text)

    def test_config_validation_failures_are_visible_after_local_save(self):
        text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("const response = await fetch('/api/config/validate'", text)
        self.assertIn("if (!response.ok) throw new Error('Backend config validation failed')", text)
        self.assertIn("if (validation.valid === false) throw new Error('Backend config validation reported issues')", text)
        self.assertIn("setSettingsError(error instanceof Error ? error.message : 'Backend config validation unavailable')", text)
        self.assertIn("setSaved(true)", text)

    def test_corrupt_local_settings_are_visible_and_cleared(self):
        text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("console.error('Failed to load saved config', error)", text)
        self.assertIn("localStorage.removeItem('edge_config')", text)
        self.assertIn("setSettingsError('Saved settings could not be loaded; defaults are shown.')", text)

    def test_runtime_metadata_refresh_failures_are_visible(self):
        text = SETTINGS.read_text(encoding="utf-8")

        self.assertIn("const [runtimeSettingsError, setRuntimeSettingsError] = useState('')", text)
        self.assertIn("const failedRuntimeLoads = [", text)
        self.assertIn("providerResponse.status === 'rejected' || !providerResponse.value.ok", text)
        self.assertIn("automationResponse.status === 'rejected' || !automationResponse.value.ok", text)
        self.assertIn("tickersResponse.status === 'rejected' || !tickersResponse.value.ok", text)
        self.assertIn("setRuntimeSettingsError(failedRuntimeLoads.length > 0 ? 'Settings metadata failed to refresh. Showing latest available data.' : '')", text)
        self.assertIn("setRuntimeSettingsError('Settings metadata failed to refresh. Showing latest available data.')", text)
        self.assertIn("{runtimeSettingsError &&", text)
        self.assertIn("{runtimeSettingsError}", text)


if __name__ == "__main__":
    unittest.main()
