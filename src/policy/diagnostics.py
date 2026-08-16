"""FeaturePlan 的软性诊断规则（规则合规与几何质量诊断清单）。

与 `policy_engine` 的区别：
- policy_engine 输出的是**硬性合规违规(violation)**，会阻断执行；
- 本模块输出的是**软性诊断(diagnostic)**：可能是警告或建议，不阻断执行，
  但需要在 UI 上呈现给用户，让用户选择"定位/一键修/忽略"。

每一条诊断项包含：
- level:    "warning" / "suggestion"（严重程度）
- title:    简短标题(会在 UI 卡片顶部显示)
- feature:  受影响的特征标识(如 "切除-拉伸 1"、"外形边缘(12 条)"，帮助用户定位)
- body:     详细正文(说明当前值、判定条件、影响)
- reference: 依据(标准号/内部规范条款)
- fix_hint:  "一键修"的建议动作(可选)
- code:     稳定的规则代码(如 "GEOM_MIN_WALL")，便于插件端做去重/映射

未来接入真实规则时，只需在 `diagnose_plan()` 里增加检查逻辑并 append DiagnosticItem。
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Mapping


@dataclass
class DiagnosticItem:
    level: str          # "warning" | "suggestion"
    code: str
    title: str
    feature: str
    body: str
    reference: str
    fix_hint: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def diagnose_plan(plan: Mapping[str, Any] | None) -> list[DiagnosticItem]:
    """对 FeaturePlan 进行软性诊断，返回若干 DiagnosticItem。

    当前实现返回**示例数据**，用于 UI 联调与产品演示；
    后续可根据 plan 的 operations/params 补齐真实几何/工艺规则。
    """
    items: list[DiagnosticItem] = []

    # 示例 1: 警告——中心孔边缘与角孔边距紧凑
    items.append(DiagnosticItem(
        level="warning",
        code="GEOM_HOLE_EDGE_TIGHT",
        title="角孔边距紧凑",
        feature="特征：切除-拉伸 1",
        body=(
            "角孔最小壁厚约 14.0 mm，符合铝合金切削壁厚 >3.0mm 安全要求。"
        ),
        reference="Q/HW 2026.2 最小壁厚系数 4.2.1",
        fix_hint="",
    ))

    # 示例 2: 建议——外形边缘增加倒角
    items.append(DiagnosticItem(
        level="suggestion",
        code="GEOM_SHARP_EDGE",
        title="建议对四周锐边增加 0.5×45° 倒角",
        feature="外形边缘(12 条)",
        body=(
            "为提升组装配效率与工人手部防划伤，建议对上下底面边缘增加微型倒角。"
        ),
        reference="Q/HW 3011.5 倒角习惯",
        fix_hint="chamfer_all_outer_edges@0.5x45",
    ))

    return items


def diagnose_to_response(plan: Mapping[str, Any] | None) -> dict:
    """把诊断结果打包成 HTTP 响应用的 dict。"""
    items = diagnose_plan(plan)
    warnings = sum(1 for it in items if it.level == "warning")
    suggestions = sum(1 for it in items if it.level == "suggestion")
    return {
        "ok": True,
        "warning_count": warnings,
        "suggestion_count": suggestions,
        "items": [it.to_dict() for it in items],
    }