import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestDesktopPySideRuntime(unittest.TestCase):
    def test_workbench_window_constructs_when_pyside6_is_available(self):
        try:
            from PySide6.QtWidgets import QApplication
        except ModuleNotFoundError:
            self.skipTest("PySide6 is not installed in this environment")

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from ui_desktop.app_window import WorkbenchWindow

        app = QApplication.instance() or QApplication([])
        window = WorkbenchWindow()

        self.assertEqual(window.windowTitle(), "AI-SW Workbench - AI SolidWorks 本地工作台")
        self.assertEqual(window.home_view.input_widget.provider(), "local")
        self.assertEqual(window.home_view.input_widget.executor_mode(), "api_executor")
        self.assertFalse(window.execution_view.validate_button.isVisible())
        self.assertFalse(window.execution_view.dry_run_button.isVisible())
        self.assertFalse(window.execution_view.real_run_button.isVisible())
        self.assertFalse(window.execution_view.confirm_panel.isVisible())
        self.assertEqual(window.execution_view.confirm_button.text(), "确认执行")
        self.assertIsNotNone(app)


if __name__ == "__main__":
    unittest.main()
