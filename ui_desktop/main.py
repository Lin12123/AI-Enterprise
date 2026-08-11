"""AI-SW Workbench 桌面客户端的程序入口。"""

from __future__ import annotations

import faulthandler
import os
import sys
import traceback
from pathlib import Path


def _runtime_root() -> Path:
    """返回运行时根目录。

    - 打包（PyInstaller，sys.frozen 为 True）时：使用可执行文件所在目录。
    - 源码运行时：使用本文件上一级目录（即项目根目录）。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _looks_like_project_root(path: Path) -> bool:
    """判断给定路径是否像项目根目录：需同时包含 app、src、ui_desktop 三个目录。"""
    return (path / "app").is_dir() and (path / "src").is_dir() and (path / "ui_desktop").is_dir()


def _discover_project_root() -> Path:
    """自动探测项目根目录，供后续把核心包加入 sys.path 使用。

    查找优先级：
    1. 环境变量 AI_SW_PROJECT_ROOT（若设置且校验通过则直接使用）。
    2. 依次从当前工作目录、运行时根目录、本文件父目录出发，逐级向上遍历。
    3. 均未命中时，退回到运行时根目录作为兜底。
    """
    # 1. 优先读取环境变量指定的根目录
    env_root = os.environ.get("AI_SW_PROJECT_ROOT", "").strip()
    if env_root:
        candidate = Path(env_root)
        if _looks_like_project_root(candidate):
            return candidate.resolve()

    # 2. 收集候选目录：三个起点各自及其所有上级目录
    candidates: list[Path] = []
    for base in (Path.cwd(), _runtime_root(), Path(__file__).resolve().parents[1]):
        try:
            resolved = base.resolve()
        except Exception:
            # 路径解析失败（如权限/无效路径）时跳过该起点
            continue
        candidates.append(resolved)
        candidates.extend(resolved.parents)

    # 使用小写路径去重，避免重复校验；命中即返回
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_project_root(candidate):
            return candidate

    # 3. 全部未命中时的兜底
    return _runtime_root()


def _ensure_project_root() -> None:
    """确保项目根目录及其 src 子目录位于 sys.path 最前，使核心包可被正确导入。"""
    project_root = _discover_project_root()
    # 回写环境变量，供适配层等其他模块复用同一根目录
    os.environ["AI_SW_PROJECT_ROOT"] = str(project_root)
    for path in (project_root, project_root / "src"):
        path_text = str(path)
        # 先移除已存在的相同路径，再插到最前，保证导入优先级
        if path_text in sys.path:
            sys.path.remove(path_text)
        sys.path.insert(0, path_text)


def _crash_log_path() -> Path:
    """返回崩溃日志文件路径，并确保其所在目录（outputs/jobs）已创建。"""
    output_dir = _runtime_root() / "outputs" / "jobs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "workbench_crash.log"


def _install_crash_logging() -> None:
    """安装崩溃日志机制，便于打包后无控制台时定位闪退问题。"""
    crash_log = _crash_log_path()
    # 以追加模式打开日志文件，供 faulthandler 写入底层崩溃（如段错误）堆栈
    crash_file = crash_log.open("a", encoding="utf-8")
    faulthandler.enable(file=crash_file, all_threads=True)

    def excepthook(exc_type, exc_value, exc_traceback):
        # 捕获未处理的 Python 异常，追加写入崩溃日志
        with crash_log.open("a", encoding="utf-8") as handle:
            handle.write("\n=== Unhandled Workbench Exception ===\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=handle)
        # 继续调用系统默认异常钩子，保留原有输出行为
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = excepthook


def main() -> int:
    """程序主入口：初始化环境后启动 Qt 主窗口，返回事件循环退出码。"""
    _ensure_project_root()       # 先配置导入路径，保证后续能加载核心包
    _install_crash_logging()     # 再安装崩溃日志
    # 延迟导入 Qt 与主窗口：确保 sys.path 已就绪后再加载相关模块
    from PySide6.QtWidgets import QApplication

    from ui_desktop.app_window import WorkbenchWindow

    app = QApplication(sys.argv)
    window = WorkbenchWindow()
    window.show()
    return app.exec()  # 进入 Qt 事件循环，直到窗口关闭


if __name__ == "__main__":
    # 以脚本方式运行时，用 main() 的返回值作为进程退出码
    raise SystemExit(main())
