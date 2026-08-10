"""Main window for AI-SW Workbench."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ui_desktop.services.job_store import (
    JobStatus,
    JobStore,
    REAL_RUN_CONFIRMATION,
    mock_output_summary,
)
from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter
from ui_desktop.services.execution_worker import ExecutionWorker
from ui_desktop.services.i18n import MESSAGES, NAVIGATION, SECTIONS, WINDOW_TITLE, tr_status
from ui_desktop.services.resource_utils import resource_path
from ui_desktop.views.execution_view import ExecutionView
from ui_desktop.views.home_view import HomeView
from ui_desktop.views.plan_view import PlanView
from ui_desktop.views.result_view import ResultView
from ui_desktop.views.settings_view import SettingsView
from ui_desktop.views.task_view import TaskView
from ui_desktop.views.validation_view import ValidationView
from ui_desktop.widgets.status_badge import StatusBadge


class WorkbenchWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(WINDOW_TITLE)
        self._set_app_icon()
        self.resize(1320, 860)
        self.job_store = JobStore()
        self.core_adapter = CoreEngineAdapter()
        self.current_job = None
        self.current_candidate: dict = {}
        self.current_validation_result: dict = {}
        self._active_threads: list[QThread] = []
        self._active_workers: list[ExecutionWorker] = []

        self.home_view = HomeView()
        self.task_view = TaskView()
        self.settings_view = SettingsView()
        self.plan_view = PlanView()
        self.validation_view = ValidationView()
        self.execution_view = ExecutionView()
        self.result_view = ResultView()

        self.nav = QListWidget()
        for name in (NAVIGATION["new_task"], NAVIGATION["task_history"], NAVIGATION["settings"]):
            self.nav.addItem(QListWidgetItem(name))
        self.nav.currentRowChanged.connect(self._handle_nav)

        self.stack = QStackedWidget()
        workbench_page = self._workbench_page()
        self.stack.addWidget(workbench_page)
        self.stack.addWidget(self.task_view)
        self.stack.addWidget(self.settings_view)
        self.nav.setCurrentRow(0)

        self.status_badge = StatusBadge(tr_status(JobStatus.CREATED.value))
        self.provider_label = QLabel("local")
        self.parse_source_label = QLabel("-")
        self.parse_source_label.setWordWrap(True)
        self.executor_label = QLabel("api_executor")
        self.validation_label = QLabel(MESSAGES["not_run"])
        self.dry_run_label = QLabel(MESSAGES["not_run"])
        self.real_run_label = QLabel(MESSAGES["not_confirmed"])
        self.output_summary = QLabel("-")
        self.output_summary.setWordWrap(True)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._left_nav())
        splitter.addWidget(self.stack)
        splitter.addWidget(self._right_status())
        splitter.setSizes([180, 900, 260])
        self.setCentralWidget(splitter)

        self._wire_events()
        self._load_styles()
        self._append_startup_diagnostics()

    def _workbench_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("WorkbenchPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self.execution_view, 1)
        layout.addWidget(self.home_view, 0)
        return page

    def _left_nav(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("LeftNav")
        layout = QVBoxLayout(panel)
        title = QLabel("AI-SW\nWorkbench")
        title.setObjectName("NavTitle")
        layout.addWidget(title)
        layout.addWidget(self.nav, 1)
        return panel

    def _right_status(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("RightStatus")
        layout = QVBoxLayout(panel)
        layout.addWidget(_box(SECTIONS["job_status"], self.status_badge))
        layout.addWidget(_box("provider", self.provider_label))
        layout.addWidget(_box("实际解析来源", self.parse_source_label))
        layout.addWidget(_box(SECTIONS["executor_mode"], self.executor_label))
        layout.addWidget(_box(SECTIONS["validation"], self.validation_label))
        layout.addWidget(_box(SECTIONS["dry_run"], self.dry_run_label))
        layout.addWidget(_box(SECTIONS["real_run"], self.real_run_label))
        layout.addWidget(_box(SECTIONS["outputs"], self.output_summary), 1)
        return panel

    def _wire_events(self) -> None:
        input_widget = self.home_view.input_widget
        input_widget.generate_button.clicked.connect(self.generate_mock_plan)
        input_widget.clear_button.clicked.connect(input_widget.clear)
        self.plan_view.parameter_table.parameter_changed.connect(self._mark_planned_modified)
        self.execution_view.validate_button.clicked.connect(self.validate_mock)
        self.execution_view.dry_run_button.clicked.connect(self.dry_run_mock)
        self.execution_view.real_run_button.clicked.connect(self.real_run_mock)
        self.execution_view.cancel_button.clicked.connect(self.cancel_mock)
        self.execution_view.confirm_button.clicked.connect(self._confirm_real_run)
        self.execution_view.regenerate_button.clicked.connect(self.generate_mock_plan)
        self.execution_view.dry_run_button.setEnabled(False)

    def _handle_nav(self, index: int) -> None:
        self.stack.setCurrentIndex(max(0, index))

    def generate_mock_plan(self) -> None:
        prompt = self.home_view.input_widget.text().strip() or "mock workbench task"
        provider = self.home_view.input_widget.provider()
        executor_mode = self.home_view.input_widget.executor_mode()
        self.current_job = self.job_store.create_job(prompt, provider=provider, executor_mode=executor_mode)
        self.current_validation_result = {}
        self.execution_view.show_real_run_confirmation(False)
        self.current_job.status = JobStatus.PLANNING
        self.job_store.save_job(self.current_job)
        self.provider_label.setText(provider)
        self.parse_source_label.setText(f"请求: {provider}\n实际: 待生成")
        self.executor_label.setText(executor_mode)
        self._set_status(JobStatus.PLANNING)
        self._append_log("用户", "input", prompt)
        self._set_busy(True)
        self._start_worker(
            "generate_plan",
            {"natural_language": prompt, "provider": provider, "job_id": self.current_job.job_id},
            on_plan=self._handle_plan_generated,
            on_failed=lambda message: self._handle_worker_failure("planning", message, JobStatus.VALIDATION_FAILED),
        )

    def _handle_plan_generated(self, result) -> None:
        if not result.ok:
            self.current_job.status = JobStatus.VALIDATION_FAILED
            self.current_job.logs.extend(result.logs)
            self.current_job.logs.append(_log_line("planning", "failed", result.message))
            self.job_store.save_job(self.current_job)
            self._append_log("planning", "failed", result.message)
            self._set_status(JobStatus.VALIDATION_FAILED)
            QMessageBox.warning(self, MESSAGES["plan_generation_failed"], result.message)
            return

        self.current_candidate = result.data.get("plan", {})
        self.current_job.featureplan_candidate = self.current_candidate
        self.current_job.status = JobStatus.NEED_USER_INPUT if result.status == "need_user_input" else JobStatus.PLANNED
        self.current_job.logs.extend(result.logs)
        self.job_store.save_job(self.current_job)
        self.provider_label.setText(self.current_job.provider)
        self.parse_source_label.setText(_format_parse_source(result.data.get("parse_info", {}), self.current_job.provider))
        self.executor_label.setText(self.current_job.executor_mode)
        self.plan_view.load_candidate(self.current_candidate)
        outputs = mock_output_summary(self.current_job.job_id)
        self.result_view.set_outputs(outputs)
        self.output_summary.setText("\n".join(outputs.values()))
        self.validation_view.panel.set_all(MESSAGES["not_run"])
        self.validation_label.setText(MESSAGES["not_run"])
        self.dry_run_label.setText(MESSAGES["not_run"])
        self.real_run_label.setText(MESSAGES["not_confirmed"])
        self.execution_view.dry_run_button.setEnabled(False)
        operations = self.current_candidate.get("operations", [])
        self._append_log("规划", result.status, f"已生成 FeaturePlan，包含 {len(operations)} 个建模步骤。")
        self._set_status(self.current_job.status)
        QTimer.singleShot(0, self.validate_mock)

    def validate_mock(self) -> None:
        if not self._ensure_job():
            return
        self._set_status(JobStatus.VALIDATING)
        self._set_busy(True)
        self._start_worker(
            "validate_plan",
            {"plan": self.current_candidate, "job_id": self.current_job.job_id},
            on_validation=self._handle_validation_finished,
            on_failed=lambda message: self._handle_worker_failure("validation", message, JobStatus.VALIDATION_FAILED),
        )

    def _handle_validation_finished(self, result) -> None:
        validation_data = result.data
        self.current_validation_result = validation_data
        self.validation_view.panel.load_result(validation_data)
        blocking_errors = validation_data.get("blocking_errors", [])
        warnings = validation_data.get("warnings", [])
        order = validation_data.get("execution_order", [])
        if result.ok:
            self.validation_label.setText(MESSAGES["passed"])
            self.execution_view.dry_run_button.setEnabled(True)
            self._append_log("validation", "passed", f"Execution order: {', '.join(order)}")
            if warnings:
                self._append_log("validation", "warning", "; ".join(warnings))
            self._set_status(JobStatus.VALIDATION_PASSED)
            QTimer.singleShot(0, self.dry_run_mock)
        else:
            self.validation_label.setText(MESSAGES["failed"])
            self.execution_view.dry_run_button.setEnabled(False)
            self._append_log("validation", "failed", "; ".join(blocking_errors))
            self._set_status(JobStatus.VALIDATION_FAILED)

    def dry_run_mock(self) -> None:
        if not self._ensure_job():
            return
        self._set_status(JobStatus.DRY_RUNNING)
        self._set_busy(True)
        self._start_worker(
            "dry_run",
            {
                "plan": self.current_candidate,
                "validation_result": self.current_validation_result,
                "job_id": self.current_job.job_id,
            },
            on_dry_run=self._handle_dry_run_finished,
            on_failed=lambda message: self._handle_worker_failure("dry_run", message, JobStatus.DRY_RUN_FAILED),
        )

    def _handle_dry_run_finished(self, result) -> None:
        for line in result.data.get("dry_run_log", []):
            self.execution_view.log_panel.append_log(line)
            self.current_job.logs.append(line)
        if result.ok:
            self.dry_run_label.setText(MESSAGES["passed"])
            self._append_log("dry_run", "passed", f"{len(result.data.get('steps', []))} operations planned.")
            self._set_status(JobStatus.DRY_RUN_PASSED)
            self.real_run_label.setText(tr_status(JobStatus.AWAITING_REAL_RUN_APPROVAL.value))
            self._append_log("确认", "waiting", MESSAGES["need_confirmation"])
            self.execution_view.show_real_run_confirmation(True)
        else:
            self.dry_run_label.setText(MESSAGES["failed"])
            self._append_log("dry_run", "failed", "; ".join(result.data.get("errors", [])))
            self._set_status(JobStatus.DRY_RUN_FAILED)

    def real_run_mock(self) -> None:
        if not self._ensure_job():
            return
        confirmation = REAL_RUN_CONFIRMATION
        previous_status = self.current_job.status.value
        self.execution_view.show_real_run_confirmation(False)
        self._set_status(JobStatus.RUNNING)
        self._set_busy(True)
        self._start_worker(
            "real_run",
            {
                "plan": self.current_candidate,
                "confirmation": confirmation,
                "job_context": {
                    "job_id": self.current_job.job_id,
                    "status": previous_status,
                    "validation_result": self.current_validation_result,
                    "output_dir": str(self.job_store.job_dir(self.current_job.job_id)),
                },
            },
            on_real_run=self._handle_real_run_finished,
            on_failed=lambda message: self._handle_worker_failure("real_run", message, JobStatus.FAILED),
        )

    def _handle_real_run_finished(self, result) -> None:
        if not result.ok:
            self.real_run_label.setText(MESSAGES["rejected"])
            self._append_log("real_run", "blocked", "; ".join(result.data.get("errors", [result.message])))
            QMessageBox.warning(self, MESSAGES["real_run_rejected"], result.message)
            self._set_status(JobStatus.FAILED)
            return
        self.real_run_label.setText(tr_status("succeeded"))
        self._append_log("real_run", result.status, result.message)
        outputs = _outputs_for_result_view(self.job_store.job_dir(self.current_job.job_id), result.data)
        self.result_view.set_outputs(outputs)
        self.output_summary.setText("\n".join(outputs.values()))
        self._set_status(JobStatus.SUCCEEDED)

    def _confirm_real_run(self) -> None:
        if not self._ensure_job():
            return
        if self.current_job.status != JobStatus.DRY_RUN_PASSED:
            self._append_log("确认", "blocked", "当前任务尚未通过预执行，不能继续真实执行。")
            return
        self._append_log("确认", "accepted", "用户已点击确认执行。")
        self.real_run_mock()

    def cancel_mock(self) -> None:
        if not self._ensure_job():
            return
        self._append_log("job", "cancelled", "Mock task cancelled.")
        self._set_status(JobStatus.CANCELLED)

    def _mark_planned_modified(self) -> None:
        if self.current_job and self.current_job.status == JobStatus.PLANNED:
            self._append_log("parameters", "modified", "Parameter table edited by user.")
            self._set_status(JobStatus.PLANNED_MODIFIED)

    def _ensure_job(self) -> bool:
        if self.current_job is not None:
            return True
        QMessageBox.information(self, "无任务", MESSAGES["need_generate_plan"])
        return False

    def _set_status(self, status: JobStatus) -> None:
        if self.current_job:
            self.current_job.status = status
            self.job_store.save_job(self.current_job)
        level = "neutral"
        if status in {JobStatus.VALIDATION_PASSED, JobStatus.DRY_RUN_PASSED, JobStatus.SUCCEEDED}:
            level = "success"
        elif status in {JobStatus.FAILED, JobStatus.VALIDATION_FAILED, JobStatus.DRY_RUN_FAILED, JobStatus.CANCELLED}:
            level = "danger"
        elif status in {JobStatus.AWAITING_REAL_RUN_APPROVAL, JobStatus.PLANNED_MODIFIED}:
            level = "warning"
        self.status_badge.set_status(tr_status(status.value), level)

    def _append_log(self, step: str, status: str, message: str) -> None:
        line = _log_line(step, status, message)
        self.execution_view.log_panel.append_log(line)
        if self.current_job:
            self.current_job.logs.append(line)
            self.job_store.save_job(self.current_job)

    def _handle_worker_log_message(self, step: str, status: str, message: str) -> None:
        self._append_log(step, status, message)

    def _start_worker(self, action: str, payload: dict, on_plan=None, on_validation=None, on_dry_run=None, on_real_run=None, on_failed=None) -> None:
        thread = QThread(self)
        worker = ExecutionWorker(action, payload, adapter=self.core_adapter)
        worker.moveToThread(thread)
        self._active_workers.append(worker)
        self._append_log(action, "queued", "后台任务已提交。")
        thread.started.connect(worker.run)
        worker.log_message.connect(self._handle_worker_log_message)
        if on_plan:
            worker.plan_generated.connect(on_plan)
        if on_validation:
            worker.validation_finished.connect(on_validation)
        if on_dry_run:
            worker.dry_run_finished.connect(on_dry_run)
        if on_real_run:
            worker.real_run_finished.connect(on_real_run)
        if on_failed:
            worker.job_failed.connect(on_failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._finish_worker(thread, worker))
        self._active_threads.append(thread)
        thread.start()

    def _finish_worker(self, thread: QThread, worker: ExecutionWorker) -> None:
        """Release worker references only after the owning thread has stopped."""

        if thread in self._active_threads:
            self._active_threads.remove(thread)
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.home_view.input_widget.generate_button.setEnabled(not busy)
        self.execution_view.validate_button.setEnabled(not busy)
        self.execution_view.dry_run_button.setEnabled(not busy and bool(self.current_validation_result.get("passed")))
        self.execution_view.real_run_button.setEnabled(not busy)
        self.execution_view.confirm_button.setEnabled(not busy)
        self.execution_view.regenerate_button.setEnabled(not busy)
        self.execution_view.cancel_button.setEnabled(not busy)
        if busy:
            self._append_log("worker", "running", MESSAGES["background_running"])

    def _handle_worker_failure(self, step: str, message: str, status: JobStatus) -> None:
        self._append_log(step, "failed", message)
        self._set_status(status)
        self.execution_view.show_real_run_confirmation(False)

    def _load_styles(self) -> None:
        qss_path = Path(resource_path("ui_desktop/styles/theme.qss"))
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        else:
            print(f"AI-SW Workbench stylesheet not found: {qss_path}", file=sys.stderr)

    def _append_startup_diagnostics(self) -> None:
        runtime_mode = "frozen" if getattr(sys, "frozen", False) else "source"
        executable = Path(sys.executable).resolve() if getattr(sys, "frozen", False) else Path(__file__).resolve()
        project_root = Path(sys.path[0]).resolve() if sys.path else Path.cwd().resolve()
        self.execution_view.log_panel.append_log(
            f"[startup] [info] mode={runtime_mode}; executable={executable}; project_root={project_root}"
        )

    def _set_app_icon(self) -> None:
        icon_path = Path(resource_path("ui_desktop/resources/app_icon.ico"))
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            print(f"AI-SW Workbench icon not found: {icon_path}", file=sys.stderr)


def _box(title: str, child: QWidget) -> QGroupBox:
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.addWidget(child)
    return box



def _outputs_for_result_view(job_dir: Path, result: dict) -> dict[str, str]:
    outputs = {
        "LOG": str(job_dir / "execution.log"),
        "OUTPUTS_JSON": str(job_dir / "outputs.json"),
        "JOB_DIR": str(job_dir),
    }
    executor_result = result.get("executor_result", {})
    raw_outputs = []
    if isinstance(executor_result, dict):
        raw_outputs = executor_result.get("outputs") or executor_result.get("files") or []
    if isinstance(raw_outputs, dict):
        paths = [str(value) for value in raw_outputs.values()]
    elif isinstance(raw_outputs, (list, tuple)):
        paths = [str(value) for value in raw_outputs]
    else:
        paths = []
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix == ".sldprt":
            outputs["SLDPRT"] = path
        elif suffix in {".step", ".stp"}:
            outputs["STEP"] = path
        elif suffix in {".png", ".jpg", ".jpeg"}:
            outputs["PNG"] = path
    return outputs



def _format_parse_source(parse_info: dict, requested_provider: str) -> str:
    requested = str(parse_info.get("requested_provider") or requested_provider or "-")
    actual = str(parse_info.get("actual_provider") or requested or "-")
    fallback = "是" if parse_info.get("fallback_used") else "否"
    repair_rounds = int(parse_info.get("repair_rounds", 0) or 0)
    return f"请求: {requested}\n实际: {actual}\n回退: {fallback}\n修复轮次: {repair_rounds}"



def _format_parse_source_inline(parse_info: dict, requested_provider: str) -> str:
    requested = str(parse_info.get("requested_provider") or requested_provider or "-")
    actual = str(parse_info.get("actual_provider") or requested or "-")
    fallback = "yes" if parse_info.get("fallback_used") else "no"
    repair_rounds = int(parse_info.get("repair_rounds", 0) or 0)
    return f"requested={requested}; actual={actual}; fallback={fallback}; repair_rounds={repair_rounds}"



def _log_line(step: str, status: str, message: str) -> str:
    return f"[{datetime.now().strftime('%H:%M:%S')}] [{step}] [{status}] {message}"

