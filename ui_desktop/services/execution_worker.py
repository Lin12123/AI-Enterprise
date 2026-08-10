"""Background workers for AI-SW Workbench core operations."""

from __future__ import annotations

from typing import Any

try:
    from PySide6.QtCore import QObject, Signal, Slot
except ModuleNotFoundError:  # pragma: no cover - exercised when PySide6 is not installed in CI.

    class QObject:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            pass

        def moveToThread(self, _thread) -> None:
            pass

        def deleteLater(self) -> None:
            pass

    class _BoundSignal:
        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback) -> None:
            self._callbacks.append(callback)

        def emit(self, *args) -> None:
            for callback in list(self._callbacks):
                callback(*args)

    class Signal:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs) -> None:
            self.name = ""

        def __set_name__(self, _owner, name: str) -> None:
            self.name = f"_{name}_signal"

        def __get__(self, instance, _owner):
            if instance is None:
                return self
            signal = instance.__dict__.get(self.name)
            if signal is None:
                signal = _BoundSignal()
                instance.__dict__[self.name] = signal
            return signal

    def Slot(*_args, **_kwargs):  # type: ignore[no-redef]
        def decorator(func):
            return func

        return decorator


from ui_desktop.adapters.core_engine_adapter import CoreEngineAdapter


class ExecutionWorker(QObject):
    """Run CoreEngineAdapter work away from the main UI thread."""

    log_message = Signal(str, str, str)
    step_started = Signal(str)
    step_succeeded = Signal(str)
    step_failed = Signal(str)
    plan_generated = Signal(object)
    validation_finished = Signal(object)
    dry_run_finished = Signal(object)
    real_run_finished = Signal(object)
    job_failed = Signal(str)
    finished = Signal()

    def __init__(self, action: str, payload: dict[str, Any], adapter: CoreEngineAdapter | None = None) -> None:
        super().__init__()
        self.action = str(action)
        self.payload = dict(payload)
        self.adapter = adapter or CoreEngineAdapter()

    @Slot()
    def run(self) -> None:
        try:
            self.step_started.emit(self.action)
            self.log_message.emit(self.action, "running", f"{self.action} started")
            if self.action == "generate_plan":
                self._run_generate_plan()
            elif self.action == "validate_plan":
                self._run_validate_plan()
            elif self.action == "dry_run":
                self._run_dry_run()
            elif self.action == "real_run":
                self._run_real_run()
            else:
                raise ValueError(f"Unsupported worker action: {self.action}")
        except Exception as exc:
            message = _redact(str(exc))
            self.step_failed.emit(self.action)
            self.job_failed.emit(message)
        finally:
            self.finished.emit()

    def _run_generate_plan(self) -> None:
        provider = self.payload.get("provider", "")
        if provider == "local":
            self.log_message.emit(self.action, "running", "正在调用 Local AI 生成 FeaturePlan；首次加载模型可能较慢，超时后会返回错误或回退。")
        elif provider == "openai":
            self.log_message.emit(self.action, "running", "正在调用 OpenAI 生成 FeaturePlan；如果鉴权、配额或网络不可用，将按既有链路失败或回退。")
        else:
            self.log_message.emit(self.action, "running", "正在使用 rule_based 解析器生成 FeaturePlan。")

        result = self.adapter.generate_plan(
            self.payload.get("natural_language", ""),
            provider,
            job_id=self.payload.get("job_id"),
        )
        self._emit_adapter_logs(result.logs)
        if result.ok:
            self.step_succeeded.emit(self.action)
            self.plan_generated.emit(result)
        else:
            self.step_failed.emit(self.action)
            self.job_failed.emit(result.message)

    def _run_validate_plan(self) -> None:
        result = self.adapter.validate_plan(
            self.payload.get("plan", {}),
            job_id=self.payload.get("job_id"),
        )
        self._emit_adapter_logs(result.logs)
        if result.ok:
            self.step_succeeded.emit(self.action)
        else:
            self.step_failed.emit(self.action)
        self.validation_finished.emit(result)

    def _run_dry_run(self) -> None:
        result = self.adapter.dry_run(
            self.payload.get("plan", {}),
            validation_result=self.payload.get("validation_result"),
            job_id=self.payload.get("job_id"),
        )
        self._emit_adapter_logs(result.logs)
        if result.ok:
            self.step_succeeded.emit(self.action)
        else:
            self.step_failed.emit(self.action)
        self.dry_run_finished.emit(result)

    def _run_real_run(self) -> None:
        result = self.adapter.real_run(
            self.payload.get("plan", {}),
            self.payload.get("confirmation", ""),
            self.payload.get("job_context", {}),
            executor=self.payload.get("executor"),
        )
        self._emit_adapter_logs(result.logs)
        if result.ok:
            self.step_succeeded.emit(self.action)
        else:
            self.step_failed.emit(self.action)
        self.real_run_finished.emit(result)

    def _emit_adapter_logs(self, logs: tuple[str, ...] | list[str]) -> None:
        for line in logs:
            self.log_message.emit(self.action, "running", _redact(str(line)))



def _redact(text: str) -> str:
    redacted = str(text)
    for token in ("api_key", "apikey", "openai_api_key", "secret", "token"):
        marker = token + "="
        lowered = redacted.lower()
        index = lowered.find(marker)
        if index >= 0:
            end = redacted.find(" ", index)
            if end < 0:
                end = len(redacted)
            redacted = redacted[: index + len(marker)] + "[redacted]" + redacted[end:]
    return redacted
