import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestDesktopPackagingEntry(unittest.TestCase):
    def test_ui_desktop_main_exists(self):
        self.assertTrue((PROJECT_ROOT / "ui_desktop" / "main.py").exists())

    def test_build_desktop_bat_exists(self):
        script = PROJECT_ROOT / "build_desktop.bat"
        self.assertTrue(script.exists())
        content = script.read_text(encoding="utf-8")
        self.assertIn('--name "AI-SW Workbench"', content)
        self.assertIn("--windowed", content)
        self.assertIn("ui_desktop\\main.py", content)

    def test_cli_entry_still_exists(self):
        self.assertTrue((PROJECT_ROOT / "app" / "main.py").exists())

    def test_provider_directory_still_exists(self):
        provider_dir = PROJECT_ROOT / "app" / "providers"
        self.assertTrue(provider_dir.exists())
        self.assertTrue((provider_dir / "openai_provider.py").exists())
        self.assertTrue((provider_dir / "local_provider.py").exists())
        self.assertTrue((provider_dir / "rule_based_provider.py").exists())

    def test_legacy_vba_still_exists(self):
        self.assertTrue((PROJECT_ROOT / "macros" / "AI_MVP_Runner.bas").exists())
        self.assertTrue((PROJECT_ROOT / "macros" / "AI_Enterprise_Runner.bas").exists())


if __name__ == "__main__":
    unittest.main()
