import json
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.services.job_store import OUTPUT_ROOT, JobStatus, JobStore, mock_featureplan_candidate


class TestDesktopJobStore(unittest.TestCase):
    def setUp(self):
        self.root = OUTPUT_ROOT / ("test_job_store_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
        self.store = JobStore(self.root)

    def test_job_store_creates_task_directory(self):
        job = self.store.create_job("mock prompt")

        self.assertTrue(self.store.job_dir(job.job_id).is_dir())
        self.assertTrue((self.store.job_dir(job.job_id) / "input.txt").exists())

    def test_job_store_output_path_stays_under_outputs_jobs(self):
        job = self.store.create_job("mock prompt")
        job_dir = self.store.job_dir(job.job_id)

        self.assertIn(self.root.resolve(), job_dir.parents)

    def test_job_store_rejects_project_external_root(self):
        with self.assertRaises(ValueError):
            JobStore(OUTPUT_ROOT.parent / "outside_jobs")

    def test_job_store_does_not_save_api_key(self):
        job = self.store.create_job("mock prompt")
        plan = mock_featureplan_candidate()
        plan["OPENAI_API_KEY"] = "secret-value"
        plan["nested"] = {"api_key": "another-secret"}
        job.featureplan_candidate = plan
        self.store.save_job(job)

        saved = (self.store.job_dir(job.job_id) / "featureplan_candidate.json").read_text(encoding="utf-8")
        self.assertNotIn("secret-value", saved)
        self.assertNotIn("another-secret", saved)
        self.assertNotIn("OPENAI_API_KEY", saved)

    def test_job_status_can_change_created_to_planned(self):
        job = self.store.create_job("mock prompt")
        job.status = JobStatus.PLANNED
        self.store.save_job(job)

        state = json.loads((self.store.job_dir(job.job_id) / "job_state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["status"], "planned")


if __name__ == "__main__":
    unittest.main()
