"""SolidWorks 专用 STA 工作线程。

背景：
- pywin32 访问 SolidWorks COM 对象受 COM 单元(apartment)约束——一个 COM 对象只能在
  它被创建/绑定的线程里使用；跨线程调用会导致未定义行为，甚至把 SolidWorks 主进程
  一并搞崩(表现为建模完成后 SW 立即闪退)。
- 我们的 HTTP 服务是 `ThreadingHTTPServer` 多线程模型，每个请求可能来自不同线程，
  直接在请求线程里连 SW 会踩上面的坑。

解决方案：
- 启动一个**长期运行的专用工作线程**(STA)，服务生命周期内所有 SW 相关工作都提交到
  这个线程串行执行。线程内 `CoInitialize` 一次、持有唯一的 SolidWorksSession，避免
  跨线程 COM、避免每次请求都重新连接。

用法：
    worker = SolidWorksWorker()
    worker.start()
    result = worker.submit(lambda: SolidWorksApiExecutor().execute(plan, ...))
"""

from __future__ import annotations

import queue
import sys
import threading
import traceback
from typing import Callable, Any


class _Job:
    """一个待执行的任务：调用 fn()，把结果/异常放回 event。"""

    __slots__ = ("fn", "result", "error", "done")

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.fn = fn
        self.result: Any = None
        self.error: BaseException | None = None
        self.done = threading.Event()


class SolidWorksWorker:
    """SolidWorks 专用 STA 工作线程。

    - 单例模式(整个服务进程只启一个)
    - 线程内 `pythoncom.CoInitialize` 一次，保证所有 SW COM 调用都在同一个 apartment
    - 提交的任务(fn)会在工作线程内被同步执行，`submit()` 阻塞直到返回结果
    """

    _instance: "SolidWorksWorker | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "SolidWorksWorker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._queue: "queue.Queue[_Job | None]" = queue.Queue()
        self._thread: threading.Thread | None = None
        self._started = False

    def start(self) -> None:
        """启动工作线程(幂等)。"""
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._loop, name="SolidWorksWorker", daemon=True)
        self._thread.start()

    def submit(self, fn: Callable[[], Any], timeout: float | None = None) -> Any:
        """把 fn 提交给工作线程执行，阻塞等待结果。
        原 fn 抛出的异常会在调用方重新抛出。"""
        if not self._started:
            self.start()

        job = _Job(fn)
        self._queue.put(job)
        finished = job.done.wait(timeout)
        if not finished:
            raise TimeoutError("SolidWorks 工作线程等待任务超时")
        if job.error is not None:
            raise job.error
        return job.result

    def _loop(self) -> None:
        """工作线程主循环：CoInitialize 一次，之后串行执行提交的任务。"""
        # 在专用线程里初始化 COM(STA)，让本线程创建/引用的所有 SolidWorks COM
        # 对象都属于这个 apartment，跨线程使用问题不再存在。
        try:
            import pythoncom  # type: ignore[import-not-found]
            pythoncom.CoInitialize()
            co_inited = True
        except Exception:
            co_inited = False
            pythoncom = None  # noqa: F841 未安装 pythoncom 时降级：直接跑，win32com 会自行处理

        try:
            while True:
                job = self._queue.get()
                if job is None:
                    return   # 收到停止信号
                try:
                    job.result = job.fn()
                except BaseException as exc:
                    job.error = exc
                    sys.stderr.write(
                        "[sw-worker] 任务执行异常: " + repr(exc) + "\n"
                        + traceback.format_exc(limit=6) + "\n")
                finally:
                    job.done.set()
        finally:
            if co_inited and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass