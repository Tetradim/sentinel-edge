"""Static checks for Learning Center learning-state export/import."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
TUTORIALS = ROOT / "frontend" / "src" / "components" / "tutorials" / "TutorialsDashboard.tsx"


class TutorialLearningStatePortabilityStaticTests(unittest.TestCase):
    def test_learning_center_can_export_and_import_learning_state(self):
        text = TUTORIALS.read_text(encoding="utf-8")

        self.assertIn("LEARNING_CENTER_EXPORT_VERSION", text)
        self.assertIn("learningStateFileInputRef", text)
        self.assertIn("exportLearningCenterState", text)
        self.assertIn("importLearningCenterState", text)
        self.assertIn("sanitizeTutorialIds", text)
        self.assertIn("sanitizeTutorialNotes", text)
        self.assertIn("Download learning data", text)
        self.assertIn("Import learning data", text)
        self.assertIn("learning-center-state", text)
        self.assertIn("importStatus", text)

    def test_learning_state_persistence_failures_are_visible(self):
        text = TUTORIALS.read_text(encoding="utf-8")

        self.assertIn("const persistTutorialState = (", text)
        self.assertIn("console.error('Failed to persist tutorial state:', error)", text)
        self.assertIn("onFailure('Learning progress could not be saved in this browser.')", text)
        self.assertIn("const [persistenceStatus, setPersistenceStatus] = useState('')", text)
        self.assertIn(
            "persistTutorialState(COMPLETED_TUTORIALS_STORAGE_KEY, JSON.stringify(completedTutorialIds), setPersistenceStatus)",
            text,
        )
        self.assertIn(
            "persistTutorialState(SAVED_TUTORIALS_STORAGE_KEY, JSON.stringify(savedTutorialIds), setPersistenceStatus)",
            text,
        )
        self.assertIn(
            "persistTutorialState(RECENT_TUTORIALS_STORAGE_KEY, JSON.stringify(recentTutorialIds), setPersistenceStatus)",
            text,
        )
        self.assertIn(
            "persistTutorialState(TUTORIAL_NOTES_STORAGE_KEY, JSON.stringify(tutorialNotes), setPersistenceStatus)",
            text,
        )
        self.assertIn(
            "persistTutorialState(TUTORIAL_READING_MODE_STORAGE_KEY, selectedReadingMode, setPersistenceStatus)",
            text,
        )
        self.assertIn(
            "persistTutorialState(TUTORIAL_PRACTICE_CHECKS_STORAGE_KEY, JSON.stringify(tutorialPracticeChecks), setPersistenceStatus)",
            text,
        )
        self.assertIn("{persistenceStatus &&", text)
        self.assertIn('role="alert"', text)
        self.assertIn("{persistenceStatus}", text)


if __name__ == "__main__":
    unittest.main()
