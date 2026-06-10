"""Static checks for the macOS smoke workflow."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MACOS_WORKFLOW = ROOT / ".github" / "workflows" / "macos-smoke.yml"
README = ROOT / "README.md"


class MacOSSmokeWorkflowStaticTests(unittest.TestCase):
    def test_macos_smoke_workflow_runs_backend_static_and_frontend_build(self):
        text = MACOS_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: macOS Smoke Checks", text)
        self.assertIn("runs-on: macos-latest", text)
        self.assertIn("actions/setup-python@v5", text)
        self.assertIn("actions/setup-node@v4", text)
        self.assertIn('python -m unittest discover -s backend/tests -p "test_*static.py"', text)
        self.assertIn("npm ci", text)
        self.assertIn("npm run lint", text)
        self.assertIn("npm run build", text)
        self.assertIn("actions/upload-artifact@v4", text)
        self.assertIn("frontend/dist", text)

    def test_macos_smoke_workflow_is_documented_as_non_packaging(self):
        text = README.read_text(encoding="utf-8")

        self.assertIn("macOS Smoke Checks", text)
        self.assertIn("macOS workflow is a smoke gate", text)
        self.assertIn("Windows installer remains the packaging path", text)


if __name__ == "__main__":
    unittest.main()
