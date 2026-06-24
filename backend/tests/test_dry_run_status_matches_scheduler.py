import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DryRunRuntimeModeTests(unittest.TestCase):
    def test_dry_run_defaults_to_enabled_when_env_is_unset(self):
        from runtime_mode import is_dry_run_enabled

        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(is_dry_run_enabled())

    def test_dry_run_env_parsing_is_shared_by_server_and_scheduler(self):
        from runtime_mode import is_dry_run_enabled

        with patch.dict(os.environ, {"DRY_RUN": "false"}, clear=True):
            self.assertFalse(is_dry_run_enabled())
        with patch.dict(os.environ, {"DRY_RUN": "on"}, clear=True):
            self.assertTrue(is_dry_run_enabled())

    def test_server_and_scheduler_use_shared_dry_run_helper(self):
        server = (ROOT / "server.py").read_text(encoding="utf-8")
        scheduler = (ROOT / "scheduler.py").read_text(encoding="utf-8")

        self.assertIn("from runtime_mode import is_dry_run_enabled", server)
        self.assertIn("from runtime_mode import is_dry_run_enabled", scheduler)
        self.assertIn('"dry_run_enabled": is_dry_run_enabled()', server)
        self.assertIn("if is_dry_run_enabled():", scheduler)


if __name__ == "__main__":
    unittest.main()
