"""企业级智能工程图(3D 转 2D)相关纯逻辑单测。

覆盖:
- drawing._extract_tolerance_grade: 从企业标准规则 params_json 解析公差等级
- knowledge_cache.start_background_refresh: 后台预取线程幂等/守护属性

真机 COM 相关(InsertModelAnnotations3/公差 API)无法在离线环境验证，
这里只测可离线运行的确定性纯逻辑与线程管理。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from solidworks_api.drawing import _extract_tolerance_grade  # noqa: E402


def test_extract_tolerance_grade_from_dict_params():
    rules = [
        {"scope_feature": "hole", "params_json": {"投影法": "第一角", "公差等级": "IT8"}},
    ]
    assert _extract_tolerance_grade(rules) == "IT8"


def test_extract_tolerance_grade_from_json_string_params():
    rules = [
        {"params_json": '{"公差等级": "IT7"}'},
    ]
    assert _extract_tolerance_grade(rules) == "IT7"


def test_extract_tolerance_grade_normalizes_bare_number():
    rules = [{"params_json": {"公差等级": "9"}}]
    assert _extract_tolerance_grade(rules) == "IT9"


def test_extract_tolerance_grade_english_key_fallback():
    rules = [{"params_json": {"tolerance_grade": "it6"}}]
    assert _extract_tolerance_grade(rules) == "IT6"


def test_extract_tolerance_grade_returns_empty_when_missing():
    assert _extract_tolerance_grade([]) == ""
    assert _extract_tolerance_grade([{"params_json": {"投影法": "第一角"}}]) == ""
    assert _extract_tolerance_grade([{"foo": "bar"}]) == ""


def test_extract_tolerance_grade_first_match_wins():
    rules = [
        {"params_json": {"投影法": "第一角"}},
        {"params_json": {"公差等级": "IT10"}},
        {"params_json": {"公差等级": "IT5"}},
    ]
    assert _extract_tolerance_grade(rules) == "IT10"


def test_start_background_refresh_is_idempotent(monkeypatch):
    import service.knowledge_cache as kc

    # 避免真实网络请求: 让 refresh 直接返回，不触发云平台
    monkeypatch.setattr(
        kc.KnowledgeCache, "refresh", lambda self, force=False: {"refreshed": False}
    )
    # 用极短 interval 但线程内首次刷新后即 sleep，测试只验证不重复起线程
    kc.start_background_refresh(interval_seconds=3600)
    t1 = kc._prefetch_thread
    kc.start_background_refresh(interval_seconds=3600)
    t2 = kc._prefetch_thread
    assert t1 is t2, "重复调用不应创建第二个预取线程"
    assert t1 is not None and t1.daemon is True, "预取线程必须是守护线程"