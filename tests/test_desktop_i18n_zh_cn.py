import unittest

from ui_desktop.services.i18n import BUTTONS, JOB_STATUS_ZH, WINDOW_TITLE, tr_button, tr_status
from ui_desktop.services.job_store import JobStatus


class TestDesktopI18nZhCn(unittest.TestCase):
    def test_job_status_maps_to_chinese(self):
        self.assertEqual(tr_status("created"), "已创建")
        self.assertEqual(tr_status("planning"), "正在生成计划")
        self.assertEqual(tr_status("dry_run_passed"), "预执行通过")
        self.assertEqual(tr_status("succeeded"), "执行成功")

    def test_button_copy_exists_in_chinese(self):
        expected = {
            "发送",
            "重新生成",
            "校验",
            "预执行（Dry Run）",
            "真实执行",
            "取消任务",
            "打开输出文件夹",
            "清空输入",
        }
        self.assertTrue(expected.issubset(set(BUTTONS.values())))
        self.assertEqual(tr_button("send"), "发送")

    def test_window_title_contains_local_workbench_chinese(self):
        self.assertIn("AI SolidWorks 本地工作台", WINDOW_TITLE)

    def test_internal_english_status_values_are_unchanged(self):
        self.assertEqual(JobStatus.CREATED.value, "created")
        self.assertEqual(JobStatus.DRY_RUN_PASSED.value, "dry_run_passed")
        self.assertIn(JobStatus.FAILED.value, JOB_STATUS_ZH)


if __name__ == "__main__":
    unittest.main()
