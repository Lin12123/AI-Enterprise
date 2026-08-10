"""SOLIDWORKS session boundary.

No COM connection is opened by default. pywin32 is optional and must be
installed manually by the user when real executor work begins.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SolidWorksSession:
    visible: bool = True
    connected: bool = False
    app: object | None = None

    def connect(self) -> None:
        if self.connected and self.app is not None:
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
        if not self.connected or self.app is None:
            raise RuntimeError("SOLIDWORKS session is not connected")
        return self.app
