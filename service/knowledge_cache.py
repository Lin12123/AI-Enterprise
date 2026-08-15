"""知识规则本地缓存客户端(带 TTL)。

职责：把云平台知识库的“已发布规则”拉到本地 Python 服务，并在内存中缓存一段
时间(默认 1 小时)。出图(3D 转 2D)时优先读缓存，缓存有效期内不再请求云平台；
过期或首次访问才刷新一次，从而减少云平台请求、提升响应速度。

设计要点：
- 仅使用标准库 urllib，零额外依赖，符合内网离线约束(禁装第三方包)。
- 云平台不可达/超时时不阻断出图：返回上一次的旧缓存(stale)，没有旧缓存则返回空规则。
- 线程安全：使用锁保护缓存读写(HTTP 服务为多线程)。
- 支持按 material / feature / standard_no 过滤，与云平台 /api/knowledge/pull 一致。
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from datetime import datetime


# ---- 配置 ----------------------------------------------------------------------

DEFAULT_BASE_URL = "http://127.0.0.1:8000"  # 云平台后端地址
DEFAULT_TTL_SECONDS = 1800                  # 缓存有效期：30 分钟(程序每 30 分钟刷新一次)
DEFAULT_TIMEOUT = 5                         # 单次拉取超时(秒)


def _base_url() -> str:
    return os.environ.get("AI_SW_CLOUD_URL", DEFAULT_BASE_URL).rstrip("/")


def _ttl_seconds() -> int:
    try:
        return int(os.environ.get("AI_SW_KNOWLEDGE_TTL", DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS


def _log(message: str) -> None:
    """统一带时间戳打印知识库获取日志(获取前后均打印，便于溯源与排障)。"""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{stamp}] [知识库] {message}", flush=True)


class KnowledgeCache:
    """带 TTL 的知识规则缓存。

    典型用法(模块级单例)::

        cache = get_cache()
        rules = cache.get_rules(material="Q235", feature="hole")
    """

    def __init__(self, base_url: str | None = None, ttl: int | None = None) -> None:
        self._base_url = base_url or _base_url()
        self._ttl = ttl if ttl is not None else _ttl_seconds()
        self._lock = threading.Lock()
        self._rules: list[dict] = []       # 上一次成功拉取的全量规则
        self._fetched_at: float = 0.0      # 上次成功拉取时间戳(0 表示从未拉取)

    # -- 内部：真正请求云平台 ---------------------------------------------------

    def _fetch_from_cloud(self) -> list[dict]:
        """从云平台拉取全部已发布规则。失败抛异常，由调用方兜底。"""
        url = f"{self._base_url}/api/knowledge/pull"
        _log(f"开始从云平台获取标准与规范: {url}")
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        # 云平台返回 {"ok": true, "data": {"hits": [...], "count": N}} 或直接 {"hits": [...]}
        payload = data.get("data", data) if isinstance(data, dict) else {}
        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        result = hits if isinstance(hits, list) else []
        _log(f"云平台标准与规范获取成功: 共 {len(result)} 条规则")
        return result

    def _is_expired(self) -> bool:
        if self._fetched_at <= 0:
            return True
        return (time.time() - self._fetched_at) >= self._ttl

    # --对外：获取规则(带缓存 + 兜底) ------------------------------------------

    def refresh(self, force: bool = False) -> dict:
        """确保缓存有效。返回 {"refreshed": bool, "count": int, "age": float, "stale": bool}。

        - force=True 时强制刷新(忽略 TTL)。
        - 云平台不可达时保留旧缓存并标记 stale=True，不抛异常。
        """
        with self._lock:
            if not force and not self._is_expired():
                return {
                    "refreshed": False,
                    "count": len(self._rules),
                    "age": round(time.time() - self._fetched_at, 1),
                    "stale": False,
                }
        # 拉取放在锁外，避免网络请求长时间占锁
        try:
            hits = self._fetch_from_cloud()
        except Exception as exc:
            _log(f"云平台标准与规范获取失败(将沿用旧缓存): {exc}")
            with self._lock:
                return {
                    "refreshed": False,
                    "count": len(self._rules),
                    "age": round(time.time() - self._fetched_at, 1) if self._fetched_at else -1,
                    "stale": True,
                }
        with self._lock:
            self._rules = hits
            self._fetched_at = time.time()
            return {"refreshed": True, "count": len(hits), "age": 0.0, "stale": False}

    def get_rules(
        self,
        material: str | None = None,
        feature: str | None = None,
        standard_no: str | None = None,
        force: bool = False,
    ) -> list[dict]:
        """获取(必要时刷新)并按条件过滤规则。用于出图时取标准规范。"""
        self.refresh(force=force)
        with self._lock:
            rules = list(self._rules)

        def _match(rule: dict) -> bool:
            if material:
                rm = str(rule.get("scope_material", "") or "")
                if rm and rm != material:
                    return False
            if feature:
                rf = str(rule.get("scope_feature", "") or "")
                if rf and rf != feature:
                    return False
            if standard_no and str(rule.get("standard_no", "")) != standard_no:
                return False
            return True

        return [r for r in rules if _match(r)]


# ---- 模块级单例 ----------------------------------------------------------------

_singleton: KnowledgeCache | None = None
_singleton_lock = threading.Lock()


def get_cache() -> KnowledgeCache:
    """获取进程内共享的知识缓存单例(会话/一段时间内复用)。"""
    global _singleton
    if _singleton is None:
        with _singleton_lock:
            if _singleton is None:
                _singleton = KnowledgeCache()
    return _singleton


# ---- 启动预取 + 后台定时刷新 -----------------------------------------------------

_prefetch_thread: threading.Thread | None = None
_prefetch_lock = threading.Lock()


def start_background_refresh(interval_seconds: int | None = None) -> None:
    """程序启动时调用：立即预取一次标准与规范，之后每个 TTL(默认 30 分钟)后台刷新一次。

    - interval_seconds: 可选，覆盖后台刷新间隔(秒)；默认取缓存 TTL(30 分钟)。
    - 幂等：重复调用只会启动一个后台线程。
    - 守护线程：不阻塞进程退出。
    - 云平台不可达时不影响主流程(refresh 内部已兜底并打印日志)。
    """
    global _prefetch_thread
    with _prefetch_lock:
        if _prefetch_thread is not None and _prefetch_thread.is_alive():
            return

        def _loop() -> None:
            cache = get_cache()
            if interval_seconds and interval_seconds > 0:
                interval = interval_seconds
            else:
                interval = cache._ttl if cache._ttl > 0 else DEFAULT_TTL_SECONDS
            _log(f"启动预取：程序启动后立即获取一次标准与规范，之后每 {interval} 秒刷新一次")
            while True:
                try:
                    cache.refresh(force=True)
                except Exception as exc:  # 兜底，绝不让后台线程崩溃
                    _log(f"后台刷新异常(忽略，等待下一轮): {exc}")
                time.sleep(interval)

        _prefetch_thread = threading.Thread(
            target=_loop, name="knowledge-prefetch", daemon=True
        )
        _prefetch_thread.start()