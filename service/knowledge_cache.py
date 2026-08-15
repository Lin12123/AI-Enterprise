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


# ---- 配置 ----------------------------------------------------------------------

DEFAULT_BASE_URL = "http://127.0.0.1:8000"  # 云平台后端地址
DEFAULT_TTL_SECONDS = 3600                  # 缓存有效期：1 小时
DEFAULT_TIMEOUT = 5                         # 单次拉取超时(秒)


def _base_url() -> str:
    return os.environ.get("AI_SW_CLOUD_URL", DEFAULT_BASE_URL).rstrip("/")


def _ttl_seconds() -> int:
    try:
        return int(os.environ.get("AI_SW_KNOWLEDGE_TTL", DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS


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
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        # 云平台返回 {"ok": true, "data": {"hits": [...], "count": N}} 或直接 {"hits": [...]}
        payload = data.get("data", data) if isinstance(data, dict) else {}
        hits = payload.get("hits", []) if isinstance(payload, dict) else []
        return hits if isinstance(hits, list) else []

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
        except Exception:
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