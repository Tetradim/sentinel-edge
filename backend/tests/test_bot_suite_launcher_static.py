"""Static checks for the Sentinel bot suite launcher."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BAT = ROOT / "Launch-Sentinel-Bot-Suite.bat"
PS1 = ROOT / "Launch-Sentinel-Bot-Suite.ps1"


class BotSuiteLauncherStaticTests(unittest.TestCase):
    def test_batch_wrapper_invokes_powershell_launcher(self):
        batch = BAT.read_text(encoding="utf-8")

        self.assertIn("Launch-Sentinel-Bot-Suite.ps1", batch)
        self.assertIn("%*", batch)
        self.assertIn("Sentinel Bot Suite", batch)

    def test_powershell_launcher_targets_local_sentinel_components(self):
        script = PS1.read_text(encoding="utf-8")

        self.assertIn("Sentinel-Pulse-branch-audit", script)
        self.assertIn("darkpool-mon-frontend-check", script)
        self.assertIn("Consolidation", script)
        self.assertIn("Auto-Crypto", script)
        self.assertIn("Tandem-Suite", script)
        self.assertIn("sentinel-edge", script)
        self.assertIn("Launch-Sentinel-Pulse-Local.ps1", script)
        self.assertIn("Launch-Sentinel-Edge-Local.ps1", script)
        self.assertIn("Launch-Darkpool-Monitor.ps1", script)
        self.assertIn("Launch-Consolidation-Bot.ps1", script)
        self.assertIn("Launch-Auto-Crypto.ps1", script)
        self.assertIn("Launch-Sentinel-Tandem.ps1", script)
        self.assertIn("OpenComponentBrowsers", script)
        self.assertIn("SkipDarkpool", script)
        self.assertIn("SkipDiscord", script)
        self.assertIn("SkipCrypto", script)

    def test_powershell_launcher_uses_requested_port_map(self):
        script = PS1.read_text(encoding="utf-8")

        expected_defaults = [
            "[int]$EdgeBackendPort = 8000",
            "[int]$EdgeFrontendPort = 3000",
            "[int]$PulseBackendPort = 8001",
            "[int]$PulseFrontendPort = 3001",
            "[int]$DarkpoolBackendPort = 8002",
            "[int]$DarkpoolFrontendPort = 3002",
            "[int]$DiscordBackendPort = 8003",
            "[int]$DiscordFrontendPort = 3003",
            "[int]$CryptoBackendPort = 8004",
            "[int]$CryptoFrontendPort = 3004",
            "[int]$TandemBackendPort = 8005",
            "[int]$TandemFrontendPort = 3005",
        ]
        for default in expected_defaults:
            with self.subTest(default=default):
                self.assertIn(default, script)

    def test_powershell_argument_list_is_not_enumerated_to_null(self):
        script = PS1.read_text(encoding="utf-8")

        self.assertIn("return ,$list", script)
        self.assertIn("$args = New-ArgumentList", script)
        self.assertIn('$args.Add("-BackendPort")', script)


if __name__ == "__main__":
    unittest.main()
