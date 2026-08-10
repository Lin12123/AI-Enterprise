import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.services.settings_store import SettingsStore
from ui_desktop.services.job_store import OUTPUT_ROOT


class TestDesktopSettingsStore(unittest.TestCase):
    def setUp(self):
        self.path = OUTPUT_ROOT / ("test_settings_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")) / "settings.json"
        self.store = SettingsStore(self.path)

    def test_settings_store_does_not_save_api_key(self):
        self.store.save(
            {
                "default_provider": "local",
                "OPENAI_API_KEY": "secret-value",
                "local_llm_api_key": "local-secret",
            }
        )

        text = self.path.read_text(encoding="utf-8")
        self.assertNotIn("secret-value", text)
        self.assertNotIn("local-secret", text)
        self.assertNotIn("OPENAI_API_KEY", text)

    def test_settings_store_loads_defaults(self):
        settings = self.store.load()

        self.assertEqual(settings["default_provider"], "local")
        self.assertEqual(settings["executor_mode"], "api_executor")


if __name__ == "__main__":
    unittest.main()
