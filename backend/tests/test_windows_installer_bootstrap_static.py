"""Static checks for the Windows beta installer first-run bootstrap."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PACKAGED_BAT = ROOT / "Launch-Sentinel-Edge.bat"
PACKAGED_PS1 = ROOT / "Launch-Sentinel-Edge.ps1"
LOCAL_BAT = ROOT / "Launch-Sentinel-Edge-Local.bat"
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
README = ROOT / "README.md"


class WindowsInstallerBootstrapStaticTests(unittest.TestCase):
    def test_packaged_launcher_entrypoint_is_installed_app_oriented(self):
        batch = PACKAGED_BAT.read_text(encoding="utf-8")
        script = PACKAGED_PS1.read_text(encoding="utf-8")

        self.assertIn("Launch-Sentinel-Edge.ps1", batch)
        self.assertIn("extract the full Sentinel Edge installer folder", batch)
        self.assertIn("SentinelEdge-Setup", batch)
        self.assertIn("Sentinel Edge - Installed App", script)
        self.assertIn("SentinelEdge.exe", script)
        self.assertIn("SENTINEL_EDGE_PORT", script)
        self.assertIn("SENTINEL_EDGE_HOST", script)
        self.assertIn("SENTINEL_EDGE_OPEN_BROWSER", script)
        self.assertIn("SENTINEL_EDGE_UI_URL", script)
        self.assertIn("/api/ready", script)
        self.assertIn("-SmokeTest", script)

    def test_packaged_launcher_downloads_missing_runtime_dependencies(self):
        script = PACKAGED_PS1.read_text(encoding="utf-8")

        self.assertIn("Sentinel Edge", script)
        self.assertIn("dependencies", script)
        self.assertIn("Ensure-LauncherDependencies", script)
        self.assertIn("Test-VcRuntimeInstalled", script)
        self.assertIn("vc_redist.x64.exe", script)
        self.assertIn("Install-MongoDbPortableDependency", script)
        self.assertIn("fastdl.mongodb.org/windows/mongodb-windows-x86_64-", script)
        self.assertIn("Expand-Archive", script)
        self.assertIn("Find-MongoDbExecutable", script)
        self.assertIn("Test-MongoPort", script)
        self.assertIn("Start-MongoDb", script)
        self.assertIn("Sentinel-Edge-MongoDB.log", script)

    def test_installer_workflow_uses_launcher_instead_of_bundled_dependencies(self):
        workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("Copy launchers into package", workflow)
        self.assertIn("Launch-Sentinel-Edge.bat", workflow)
        self.assertIn("Launch-Sentinel-Edge.ps1", workflow)
        self.assertIn('Filename: "{app}\\Launch-Sentinel-Edge.bat"', workflow)
        self.assertNotIn("Download MongoDB", workflow)
        self.assertNotIn("Download VC++ Redist", workflow)
        self.assertNotIn('Source: "mongodb\\mongod.exe"', workflow)
        self.assertNotIn("{tmp}\\vc_redist.x64.exe", workflow)

    def test_local_batch_wrapper_reports_partial_extracts_cleanly(self):
        batch = LOCAL_BAT.read_text(encoding="utf-8")

        self.assertIn("Launch-Sentinel-Edge-Local.ps1", batch)
        self.assertIn("if not exist", batch.lower())
        self.assertIn("extract the full Sentinel Edge folder", batch)
        self.assertIn("SentinelEdge-Setup", batch)

    def test_readme_documents_beta_installer_first_run_behavior(self):
        readme = README.read_text(encoding="utf-8")

        self.assertIn("SentinelEdge-Setup-<version>.exe", readme)
        self.assertIn("downloads missing runtime dependencies on first launch", readme)
        self.assertIn("Visual C++ Runtime", readme)
        self.assertIn("MongoDB", readme)


if __name__ == "__main__":
    unittest.main()
