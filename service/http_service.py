"""AI-SW 本地 HTTP 服务。

职责：把现有 Python 引擎(自然语言解析 → FeaturePlan → policy 校验 → dry_run/真实建模)
封装为本地 HTTP 接口，供 C# SolidWorks 插件调用。

设计要点：
- 仅使用标准库 http.server，零额外依赖，便于随插件一起分发。
- 只监听本机回环地址(127.0.0.1)，不对外暴露，降低安全风险。
- SolidWorks 建模复用现有 pywin32 代码(model_builder.py)，插件端不重写建模逻辑。

接口一览：
  GET  /api/health          健康检查
  POST /api/generate_plan   自然语言 → FeaturePlan(复用 provider router)
  POST /api/validate        FeaturePlan → policy 校验
  POST /api/dry_run         FeaturePlan → 预演(不连接 SolidWorks)
  POST /api/execute         FeaturePlan → 真实建模(通过 pywin32 连接当前 SW)
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# ---- 项目路径引导：确保能导入 app 与 src 下的核心包 ----------------------------

def _project_root() -> Path:
    """返回项目根目录(本文件位于 <root>/service/ 下)。"""
    return Path(__file__).resolve().parents[1]


def _bootstrap_paths() -> None:
    """将项目根目录及 src 加入 sys.path 最前，保证核心包可被导入。"""
    root = _project_root()
    for path in (root, root / "src"):
        text = str(path)
        if text in sys.path:
            sys.path.remove(text)
        sys.path.insert(0, text)


_bootstrap_paths()


# ---- 默认配置 ------------------------------------------------------------------

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765  # 与 Ollama(11434) 区分，避免端口冲突


def _host() -> str:
    return os.environ.get("AI_SW_SERVICE_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST


def _port() -> int:
    raw = os.environ.get("AI_SW_SERVICE_PORT", "").strip()
    try:
        return int(raw) if raw else DEFAULT_PORT
    except ValueError:
        return DEFAULT_PORT


# ---- 请求处理器 ----------------------------------------------------------------

class AiSwRequestHandler(BaseHTTPRequestHandler):
    """处理来自 C# 插件的 HTTP 请求，分发到各业务处理函数。"""

    server_version = "AiSwService/1.0"

    # 关闭默认的访问日志噪音，改为简洁输出
    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        sys.stderr.write("[service] " + (fmt % args) + "\n")

    # ---- 统一响应工具 ----

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    # ---- 路由 ----

    def do_GET(self) -> None:  # noqa: N802 (BaseHTTPRequestHandler 约定命名)
        if self.path.rstrip("/") == "/api/health":
            self._send_json(200, {"ok": True, "status": "healthy", "service": self.server_version})
            return
        self._send_json(404, {"ok": False, "error": f"未知路径: {self.path}"})

    def do_POST(self) -> None:  # noqa: N802
        route = self.path.rstrip("/")
        handlers = {
            "/api/generate_plan": _handle_generate_plan,
            "/api/validate": _handle_validate,
            "/api/dry_run": _handle_dry_run,
            "/api/execute": _handle_execute,
            "/api/diagnose": _handle_diagnose,
        }
        handler = handlers.get(route)
        if handler is None:
            self._send_json(404, {"ok": False, "error": f"未知路径: {self.path}"})
            return

        try:
            payload = self._read_json_body()
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": f"请求体不是合法 JSON: {exc}"})
            return

        try:
            result = handler(payload)
            self._send_json(200, result)
        except Exception as exc:
            # 统一异常处理：返回 500 并附带简要堆栈，便于插件端排查
            self._send_json(500, {
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc(limit=5),
            })


# ---- 业务处理函数(复用现有 Python 引擎) ---------------------------------------

# 服务进程内唯一的 SolidWorksSession 实例，只在 SW 工作线程里被访问。
_SHARED_SESSION = None


def _shared_session():
    """返回服务进程内唯一的 SolidWorksSession(仅供 SW 工作线程调用)。"""
    global _SHARED_SESSION
    if _SHARED_SESSION is None:
        from solidworks_api.session import SolidWorksSession
        _SHARED_SESSION = SolidWorksSession()
    return _SHARED_SESSION


def _handle_generate_plan(payload: dict) -> dict:
    """自然语言 → FeaturePlan。

    复用 app.providers.router 的 provider 路由(local/openai/rule_based)。
    请求体: {"natural_language": "...", "provider": "local"}
    返回: {"ok": True, "plan": {...}, "provider": "local"}
    """
    natural_language = str(payload.get("natural_language", "")).strip()
    if not natural_language:
        return {"ok": False, "error": "缺少 natural_language 字段"}

    provider = str(payload.get("provider", "local")).strip().lower() or "local"

    # 通过环境变量指定 provider，与现有 router 的读取方式保持一致
    previous = os.environ.get("AI_SW_LLM_PROVIDER")
    os.environ["AI_SW_LLM_PROVIDER"] = provider
    try:
        from app.providers.router import parse_featureplan_with_provider
        from cad_dsl.semantic_binding import canonicalize_featureplan_structure

        plan = canonicalize_featureplan_structure(parse_featureplan_with_provider(natural_language))
    finally:
        if previous is None:
            os.environ.pop("AI_SW_LLM_PROVIDER", None)
        else:
            os.environ["AI_SW_LLM_PROVIDER"] = previous

    if not isinstance(plan, dict):
        return {"ok": False, "error": "解析器返回的不是合法计划对象"}

    return {"ok": True, "provider": provider, "plan": plan}


def _handle_validate(payload: dict) -> dict:
    """FeaturePlan → policy 校验。

    请求体: {"plan": {...}}
    返回: {"ok": bool, "allowed": bool, "violations": [...]}
    """
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        return {"ok": False, "error": "缺少 plan 字段或格式错误"}

    from policy.policy_engine import PolicyEngine

    result = PolicyEngine().validate(plan)
    violations = [
        {"operation_id": v.operation_id, "code": v.code, "message": v.message}
        for v in result.violations
    ]
    return {"ok": True, "allowed": bool(result.allowed), "violations": violations}


def _handle_dry_run(payload: dict) -> dict:
    """FeaturePlan → 预演(不连接 SolidWorks)。

    请求体: {"plan": {...}}
    返回: {"ok": bool, "status": str, "message": str, "operations": [...], "outputs": [...]}
    """
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        return {"ok": False, "error": "缺少 plan 字段或格式错误"}

    from solidworks_api.executor import SolidWorksApiExecutor

    result = SolidWorksApiExecutor().dry_run(plan)
    return _execution_result_to_dict(result)


def _handle_execute(payload: dict) -> dict:
    """FeaturePlan → 真实建模(通过 pywin32 连接当前打开的 SolidWorks)。

    请求体: {"plan": {...}}
    返回: {"ok": bool, "status": str, "message": str, "operations": [...], "outputs": [...]}

    注意：需目标机已安装 SolidWorks 且已打开，同时 Python 环境已安装 pywin32。

    实现细节：本函数并不直接调用 SolidWorks——真正的 COM 调用必须在专用 STA
    工作线程内完成，否则可能因跨线程 COM 使用导致 SolidWorks 闪退。见 sw_worker.py。
    """
    plan = payload.get("plan")
    if not isinstance(plan, dict):
        return {"ok": False, "error": "缺少 plan 字段或格式错误"}

    use_active_doc = bool(payload.get("use_active_doc", False))
    # 用户原始自然语言：当活动文档已有零件时，用于判断"修改当前"还是"新增零件"
    prompt = str(payload.get("prompt", "") or "")

    def _do_execute():
        from solidworks_api.executor import SolidWorksApiExecutor
        from solidworks_api.session import SolidWorksSession

        # 复用工作线程内的单例 session：只需 GetActiveObject 一次，之后所有请求
        # 都用同一份 SolidWorks COM 引用，避免重复连接/跨请求 COM 悬空。
        session = _shared_session()
        return SolidWorksApiExecutor(session=session).execute(
            plan, dry_run=False, use_active_doc=use_active_doc, prompt=prompt)

    from service.sw_worker import SolidWorksWorker
    worker = SolidWorksWorker()
    worker.start()
    # 建模可能耗时较久，给一个宽松的超时(10 分钟)
    result = worker.submit(_do_execute, timeout=600)
    return _execution_result_to_dict(result)


def _handle_diagnose(payload: dict) -> dict:
    """FeaturePlan → 规则合规与几何质量诊断清单(软性诊断, 不阻断执行)。

    请求体: {"plan": {...}}
    返回:   {"ok": True, "warning_count": N, "suggestion_count": M, "items": [...]}
    每个 item: {level, code, title, feature, body, reference, fix_hint}
    """
    plan = payload.get("plan")
    if plan is not None and not isinstance(plan, dict):
        return {"ok": False, "error": "plan 字段格式错误"}

    from policy.diagnostics import diagnose_to_response
    return diagnose_to_response(plan)


def _execution_result_to_dict(result) -> dict:
    """把 ExecutionResult 转成可 JSON 序列化的响应字典。"""
    operations = [
        {
            "operation_id": op.operation_id,
            "operation_type": op.operation_type,
            "status": op.status,
            "message": op.message,
        }
        for op in getattr(result, "operations", ())
    ]
    ok = result.status in {"dry_run", "executed"}
    return {
        "ok": ok,
        "status": result.status,
        "message": result.message,
        "operations": operations,
        "outputs": list(getattr(result, "outputs", ()) or ()),
    }


# ---- 服务入口 ------------------------------------------------------------------

def serve() -> None:
    host, port = _host(), _port()
    # 预先启动 SW 专用 STA 工作线程：让 CoInitialize 提前完成，
    # 后续第一次 /api/execute 请求不必等待线程冷启动。
    try:
        from service.sw_worker import SolidWorksWorker
        SolidWorksWorker().start()
    except Exception as exc:   # 未装 pythoncom 也不阻断服务启动
        sys.stderr.write("[service] 警告: SW 工作线程未能启动: " + str(exc) + "\n")

    server = ThreadingHTTPServer((host, port), AiSwRequestHandler)
    print(f"AI-SW 本地服务已启动: http://{host}:{port}")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n收到停止信号，正在关闭服务...")
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()