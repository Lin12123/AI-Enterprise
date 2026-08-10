import os
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


class TestDesktopResourcePaths(unittest.TestCase):
    def test_resource_path_imports(self):
        from ui_desktop.services.resource_utils import resource_path

        self.assertTrue(callable(resource_path))

    def test_resource_path_uses_project_relative_input(self):
        from ui_desktop.services.resource_utils import resource_path

        resolved = Path(resource_path("ui_desktop/resources/app_icon.ico"))

        self.assertTrue(resolved.is_absolute())
        self.assertIn(PROJECT_ROOT, [resolved, *resolved.parents])

    def test_resource_path_supports_pyinstaller_meipass(self):
        from ui_desktop.services import resource_utils

        previous = getattr(sys, "_MEIPASS", None)
        try:
            sys._MEIPASS = str(PROJECT_ROOT)  # type: ignore[attr-defined]
            resolved = Path(resource_utils.resource_path("ui_desktop/resources/app_icon.ico"))
        finally:
            if previous is None:
                try:
                    delattr(sys, "_MEIPASS")
                except AttributeError:
                    pass
            else:
                sys._MEIPASS = previous  # type: ignore[attr-defined]

        self.assertEqual(resolved, PROJECT_ROOT / "ui_desktop" / "resources" / "app_icon.ico")

    def test_missing_icon_does_not_break_window_construction(self):
        try:
            from PySide6.QtWidgets import QApplication
        except ModuleNotFoundError:
            self.skipTest("PySide6 is not installed in this environment")

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui_desktop.app_window import WorkbenchWindow

        app = QApplication.instance() or QApplication([])
        window = WorkbenchWindow()

        self.assertIsNotNone(window)
        self.assertIsNotNone(app)

    def test_build_script_contains_icon_parameter(self):
        content = (PROJECT_ROOT / "build_desktop.bat").read_text(encoding="utf-8")

        self.assertIn("--icon ui_desktop\\resources\\app_icon.ico", content)

    def test_build_script_collects_stylesheet_data(self):
        content = (PROJECT_ROOT / "build_desktop.bat").read_text(encoding="utf-8")

        self.assertIn("--add-data \"ui_desktop\\styles\\theme.qss;ui_desktop\\styles\"", content)
        self.assertTrue((PROJECT_ROOT / "ui_desktop" / "styles" / "theme.qss").exists())

    def test_build_script_collects_core_src_packages(self):
        content = (PROJECT_ROOT / "build_desktop.bat").read_text(encoding="utf-8")

        self.assertIn("--paths src", content)
        self.assertIn("--collect-submodules cad_dsl", content)
        self.assertIn("--collect-submodules policy", content)
        self.assertIn("--collect-submodules solidworks_api", content)


if __name__ == "__main__":
    unittest.main()
