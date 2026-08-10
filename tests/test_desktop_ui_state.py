import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.services.job_store import JobStatus, can_enter_real_run, next_real_run_status


class TestDesktopUiState(unittest.TestCase):
    def test_real_run_without_confirmation_does_not_enter_running(self):
        self.assertFalse(can_enter_real_run(""))
        self.assertNotEqual(next_real_run_status(""), JobStatus.RUNNING)

    def test_real_run_confirmation_enters_awaiting_approval(self):
        self.assertTrue(can_enter_real_run("YES_RUN_SOLIDWORKS_API"))
        self.assertEqual(next_real_run_status("YES_RUN_SOLIDWORKS_API"), JobStatus.AWAITING_REAL_RUN_APPROVAL)

    def test_cli_and_provider_files_still_exist(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "app" / "main.py").exists())
        self.assertTrue((root / "app" / "providers" / "openai_provider.py").exists())
        self.assertTrue((root / "app" / "providers" / "local_provider.py").exists())
        self.assertTrue((root / "app" / "providers" / "rule_based_provider.py").exists())


if __name__ == "__main__":
    unittest.main()
