"""Static checks for local launcher browser/process lifecycle coupling."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "Launch-Sentinel-Edge-Local.ps1"


class LocalLauncherLifecycleStaticTests(unittest.TestCase):
    def test_browser_window_close_stops_owned_processes(self):
        script = LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("$BrowserProcessIds = @()", script)
        self.assertIn("$BrowserWindowProcessIds = @()", script)
        self.assertIn("$BrowserStartedAt = $null", script)
        self.assertIn("function Get-BrowserProfileProcesses", script)
        self.assertIn("function Wait-BrowserWindowProcesses", script)
        self.assertIn("function Test-BrowserWindowClosed", script)
        self.assertIn("Wait-BrowserProfileProcesses -Seconds 10", script)
        self.assertIn("Wait-BrowserWindowProcesses -Seconds 10", script)
        self.assertIn("if (Test-BrowserWindowClosed)", script)
        self.assertIn("Browser window closed; shutting down Sentinel Edge", script)

    def test_launcher_close_stops_browser_and_owned_processes(self):
        script = LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("$LauncherWatchdogStopFile = $null", script)
        self.assertIn("function Start-LauncherShutdownWatchdog", script)
        self.assertIn("function Stop-LauncherShutdownWatchdog", script)
        self.assertIn("Launcher process $ParentProcessId ended; closing browser and owned processes", script)
        self.assertIn("Get-ProfileProcesses", script)
        self.assertIn("Stop-ProcessTreeById", script)
        self.assertIn("Start-LauncherShutdownWatchdog", script)
        self.assertIn("Stop-LauncherShutdownWatchdog", script)


if __name__ == "__main__":
    unittest.main()
