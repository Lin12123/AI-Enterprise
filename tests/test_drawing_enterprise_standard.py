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
from solidworks_api.drawing import (  # noqa: E402
    _choose_paper_size,
    _fmt_mm,
    _get_part_bbox_dims_mm,
    _build_bbox_dims_text,
    _build_tech_requirements_text,
)


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


# --- 图幅选择(按包围盒最长边选 A4~A1) ---


def test_choose_paper_size_by_max_edge():
    # (最长边mm, 期望图幅名)
    cases = [
        (80, "A4"),    # <=150
        (150, "A4"),
        (200, "A3"),   # <=300
        (300, "A3"),
        (450, "A2"),   # <=600
        (600, "A2"),
        (900, "A1"),   # <=1200
        (1200, "A1"),
        (2000, "A1"),  # 超上限用 A1 兜底
    ]
    for edge, expect in cases:
        _, name = _choose_paper_size(edge)
        assert name == expect, f"最长边 {edge}mm 应选 {expect}，实际 {name}"


def test_choose_paper_size_zero_fallback_a3():
    # 取不到尺寸(<=0)用 A3 兜底
    _, name = _choose_paper_size(0)
    assert name == "A3"


# --- mm 数值格式化 ---


def test_fmt_mm_integer_no_decimal():
    assert _fmt_mm(100.0) == "100"
    assert _fmt_mm(100) == "100"


def test_fmt_mm_keeps_needed_decimals():
    assert _fmt_mm(12.5) == "12.5"
    assert _fmt_mm(12.30) == "12.3"


# --- 包围盒总体尺寸(长宽高兜底) ---


class _FakePartWithBox:
    """离线 mock: GetBox(0) 返回米制 6 元组 (xmin,ymin,zmin,xmax,ymax,zmax)。"""

    def __init__(self, box):
        self._box = box

    @property
    def Extension(self):
        return self

    def GetBox(self, _flag):
        return self._box


def test_get_part_bbox_dims_mm_sorted_desc():
    # x跨度0.1m=100mm, y跨度0.05m=50mm, z跨度0.2m=200mm → 排序后 (200,100,50)
    part = _FakePartWithBox((0.0, 0.0, 0.0, 0.1, 0.05, 0.2))
    l, w, h = _get_part_bbox_dims_mm(part)
    assert (l, w, h) == (200.0, 100.0, 50.0)


def test_get_part_bbox_dims_mm_bad_box_returns_zero():
    part = _FakePartWithBox(None)
    assert _get_part_bbox_dims_mm(part) == (0.0, 0.0, 0.0)


def test_build_bbox_dims_text_contains_lwh():
    part = _FakePartWithBox((0.0, 0.0, 0.0, 0.1, 0.05, 0.2))
    text = _build_bbox_dims_text(part)
    assert "总体尺寸" in text
    assert "总长 L = 200" in text
    assert "总宽 W = 100" in text
    assert "总高 H = 50" in text


def test_build_bbox_dims_text_empty_when_no_box():
    part = _FakePartWithBox(None)
    assert _build_bbox_dims_text(part) == ""


# --- 技术要求文本(未注公差三档 + 粗糙度 + 通用兜底) ---


def test_build_tech_requirements_text_defaults_when_empty_rules():
    text = _build_tech_requirements_text([])
    assert text.startswith("技术要求")
    # 无规则时至少要有通用工艺兜底(圆角/倒角/去毛刺)
    assert "去毛刺" in text
