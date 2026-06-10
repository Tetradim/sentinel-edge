"""Static checks for Learning Center related module actions."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TUTORIALS = ROOT / "frontend" / "src" / "components" / "tutorials" / "TutorialsDashboard.tsx"
TUTORIAL_INDEX = ROOT / "frontend" / "src" / "components" / "tutorials" / "index.ts"
ASSET_COMMAND = ROOT / "frontend" / "src" / "components" / "asset-command" / "AssetCommandConsole.tsx"
OPERATIONS_PANEL = ROOT / "frontend" / "src" / "components" / "asset-command" / "components" / "OperationsPanel.tsx"


class TutorialRelatedModuleStaticTests(unittest.TestCase):
    def test_tutorial_detail_can_open_related_module(self):
        tutorials = TUTORIALS.read_text(encoding="utf-8")
        index = TUTORIAL_INDEX.read_text(encoding="utf-8")
        asset_command = ASSET_COMMAND.read_text(encoding="utf-8")
        operations_panel = OPERATIONS_PANEL.read_text(encoding="utf-8")

        self.assertIn("TutorialModuleView", tutorials)
        self.assertIn("tutorialModuleTargets", tutorials)
        self.assertIn("onOpenModule", tutorials)
        self.assertIn("moduleTarget", tutorials)
        self.assertIn("Open related module", tutorials)
        self.assertIn("Related module", tutorials)
        self.assertIn("export type { TutorialModuleView }", index)
        self.assertIn("OperationsPanel", asset_command)
        self.assertIn("type TutorialModuleView", operations_panel)
        self.assertIn("onOpenModule={(view: TutorialModuleView) => setActiveView(view)}", operations_panel)


if __name__ == "__main__":
    unittest.main()
