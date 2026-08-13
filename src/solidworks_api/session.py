"""SOLIDWORKS session boundary.

No COM connection is opened by default. pywin32 is optional and must be
installed manually by the user when real executor work begins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import threading


@dataclass
class SolidWorksSession:
    visible: bool = True
    connected: bool = False
    app: object | None = None
    # 记录哪些线程已经调过 CoInitialize，避免重复初始化。
    # 关键：HTTP 服务是多线程的(ThreadingHTTPServer)，每个新线程都必须先 CoInitialize
    # 才能通过 pywin32 访问 COM 对象；否则第 2 次请求(来自新线程)会失败。
    _co_initialized_threads: set[int] = field(default_factory=set, repr=False, compare=False)

    def connect(self) -> None:
        # 每次都要确认当前线程的 COM 已经初始化；即便 self.app 已缓存，
        # 若换到了新线程仍需在该线程 CoInitialize 一次。
        self._ensure_co_initialized()

        if self.connected and self.app is not None:
            # 已连接过；返回之前缓存的 app 对象即可
            return

        try:
            import win32com.client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError("未安装 pywin32。请用户手动安装后再启用真实 SolidWorks API 执行。") from exc

        try:
            self.app = win32com.client.GetActiveObject("SldWorks.Application")
        except Exception as exc:
            raise RuntimeError("未检测到已打开的 SolidWorks。请先手动启动 SolidWorks，再执行 API 模式。") from exc

        self.connected = True
        try:
            self.app.Visible = bool(self.visible)
        except Exception:
            pass

    def require_connected(self) -> object:
        # 每次取用前确认当前线程 COM 已初始化，避免跨线程访问 COM 对象时报错
        self._ensure_co_initialized()
        if not self.connected or self.app is None:
            raise RuntimeError("SOLIDWORKS session is not connected")
        return self.app

    def _ensure_co_initialized(self) -> None:
        """为当前线程初始化 COM apartment（一次），确保跨线程访问 SolidWorks COM 不失败。"""
        tid = threading.get_ident()
        if tid in self._co_initialized_threads:
            return
        try:
            import pythoncom  # type: ignore[import-not-found]
        except ImportError:
            # 没装 pythoncom 就直接跳过：如果后续 win32com 调用需要它自会报错
            self._co_initialized_threads.add(tid)
            return
        try:
            pythoncom.CoInitialize()
        except Exception:
            # 已经初始化过(RPC_E_CHANGED_MODE 等)也算成功；只记录一次
            pass
        self._co_initialized_threads.add(tid)
