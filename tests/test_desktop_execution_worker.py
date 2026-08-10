import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ui_desktop.adapters.core_engine_adapter import AdapterResult
from ui_desktop.services.execution_worker import ExecutionWorker
from ui_desktop.services.job_store import JobStore


class FakeAdapter:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def generate_plan(self, natural_language, provider, job_id=None):
        self.calls.append("generate_plan")
        if self.fail:
            raise RuntimeError("OPENAI_API_KEY=secret-value failed")
        return AdapterResult(
            ok=True,
            status="planned",
            message="generated",
            data={"plan": {"version": "2.0", "operations": []}},
            logs=("generated log",),
        )

    def validate_plan(self, plan, job_id=None):
        self.calls.append("validate_plan")
        if self.fail:
            raise RuntimeError("validation failed")
        return AdapterResult(
            ok=True,
            status="validation_passed",
            message="validated",
            data={"passed": True, "blocking_errors": []},
            logs=("validated log",),
        )

    def dry_run(self, plan, validation_result=None, job_id=None):
        self.calls.append("dry_run")
        if self.fail:
            raise RuntimeError("dry run failed")
        return AdapterResult(
            ok=True,
            status="dry_run_passed",
            message="dry run",
            data={"passed": True, "steps": [{"operation_id": "op_001"}], "dry_run_log": ["step log"]},
            logs=("dry run log",),
        )


class TestDesktopExecutionWorker(unittest.TestCase):
    def test_worker_executes_mock_generate_plan(self):
        adapter = FakeAdapter()
        received = []
        worker = ExecutionWorker(
            "generate_plan",
            {"natural_language": "make part", "provider": "rule_based", "job_id": "job_20260624_120000"},
            adapter=adapter,
        )
        worker.plan_generated.connect(received.append)

        worker.run()

        self.assertEqual(adapter.calls, ["generate_plan"])
        self.assertEqual(received[0].status, "planned")

    def test_worker_executes_mock_validate_plan(self):
        adapter = FakeAdapter()
        received = []
        worker = ExecutionWorker("validate_plan", {"plan": {}, "job_id": "job_20260624_120000"}, adapter=adapter)
        worker.validation_finished.connect(received.append)

        worker.run()

        self.assertEqual(adapter.calls, ["validate_plan"])
        self.assertTrue(received[0].data["passed"])

    def test_worker_executes_mock_dry_run(self):
        adapter = FakeAdapter()
        received = []
        worker = ExecutionWorker(
            "dry_run",
            {"plan": {}, "validation_result": {"passed": True}, "job_id": "job_20260624_120000"},
            adapter=adapter,
        )
        worker.dry_run_finished.connect(received.append)

        worker.run()

        self.assertEqual(adapter.calls, ["dry_run"])
        self.assertEqual(received[0].status, "dry_run_passed")

    def test_worker_failure_emits_job_failed_and_redacts_key(self):
        adapter = FakeAdapter(fail=True)
        failures = []
        worker = ExecutionWorker("generate_plan", {"natural_language": "x", "provider": "local"}, adapter=adapter)
        worker.job_failed.connect(failures.append)

        worker.run()

        self.assertTrue(failures)
        self.assertNotIn("secret-value", failures[0])

    def test_worker_does_not_directly_call_solidworks_api(self):
        adapter = FakeAdapter()
        worker = ExecutionWorker("dry_run", {"plan": {}, "validation_result": {"passed": True}}, adapter=adapter)

        with patch("solidworks_api.session.SolidWorksSession.connect", side_effect=AssertionError("connect called")):
            worker.run()

        self.assertEqual(adapter.calls, ["dry_run"])

    def test_job_store_still_creates_jobs(self):
        job = JobStore().create_job("worker test", provider="rule_based")

        self.assertTrue(job.job_id.startswith("job_"))


if __name__ == "__main__":
    unittest.main()
