"""Model builder for fixed SOLIDWORKS API operations."""

from __future__ import annotations

from pathlib import Path

from cad_dsl.featureplan import FeaturePlan
from solidworks_api.features.base_plate import create_base_plate
from solidworks_api.features.boss import create_center_boss
from solidworks_api.features.chamfer import add_chamfer
from solidworks_api.features.cut import cut_rectangle_pocket, cut_slot, extrude_cut
from solidworks_api.features.extrude import extrude_boss
from solidworks_api.features.fillet import add_fillet
from solidworks_api.features.hole import (
    create_blind_hole,
    create_counterbore_hole,
    create_countersink_hole,
    create_through_hole,
    cut_center_hole,
    cut_corner_holes,
)
from solidworks_api.features.material_properties import set_custom_property, set_material
from solidworks_api.features.mirror import mirror_feature
from solidworks_api.features.modify import modify_named_dimension
from solidworks_api.features.pattern import create_circular_pattern, create_linear_pattern
from solidworks_api.features.reference_geometry import create_axis, create_offset_plane
from solidworks_api.operation_planner import plan_operations
from solidworks_api.output_manager import plan_output_paths
from solidworks_api.sketch_builder import create_sketch, sketch_center_rectangle, sketch_circle


# SOLIDWORKS swUserPreferenceStringValue_e.swDefaultTemplatePart.
# Kept as a literal to avoid requiring generated COM constants at runtime.
SW_DEFAULT_TEMPLATE_PART = 1
SW_DOC_PART = 1
SW_DWG_PAPER_NONE = 0


DISPATCH = {
    "create_sketch": create_sketch,
    "sketch_center_rectangle": sketch_center_rectangle,
    "sketch_circle": sketch_circle,
    "extrude_boss": extrude_boss,
    "extrude_cut": extrude_cut,
    "create_through_hole": create_through_hole,
    "create_blind_hole": create_blind_hole,
    "create_counterbore_hole": create_counterbore_hole,
    "create_countersink_hole": create_countersink_hole,
    "cut_rectangle_pocket": cut_rectangle_pocket,
    "cut_slot": cut_slot,
    "create_base_plate": create_base_plate,
    "cut_corner_holes": cut_corner_holes,
    "create_center_boss": create_center_boss,
    "cut_center_hole": cut_center_hole,
    "add_fillet": add_fillet,
    "add_chamfer": add_chamfer,
    "create_linear_pattern": create_linear_pattern,
    "create_circular_pattern": create_circular_pattern,
    "mirror_feature": mirror_feature,
    "set_material": set_material,
    "set_custom_property": set_custom_property,
    "modify_named_dimension": modify_named_dimension,
    "create_offset_plane": create_offset_plane,
    "create_axis": create_axis,
}


class ModelBuilder:
    def build(self, sw_app: object, plan: FeaturePlan, use_active_doc: bool = False) -> tuple[str, ...]:
        # use_active_doc=True 时在当前打开的活动文档里建模，不新建窗口；
        # 默认 False 保持原有行为：新建零件文档。
        plan = plan_operations(plan)
        sw_model = self._active_part(sw_app) if use_active_doc else None
        state = {"base": {}, "boss": {}, "sketches": {}, "saved_outputs": [], "sw_app": sw_app}
        explicit_output = False
        for operation in plan.operations:
            try:
                if operation.op == "create_new_part":
                    # 若指定在当前文档建模，则忽略 create_new_part，不再新开窗口
                    if use_active_doc:
                        if sw_model is None:
                            sw_model = self._active_part(sw_app)
                        continue
                    sw_model = self._create_new_part(sw_app)
                    continue
                if sw_model is None:
                    sw_model = self._active_part(sw_app) if use_active_doc else self._create_new_part(sw_app)
                if operation.op == "rebuild_model":
                    self._rebuild_model(sw_model)
                    continue
                if operation.op == "validate_rebuild":
                    self._validate_rebuild(sw_model)
                    continue
                if operation.op in {"save_sldprt", "export_step", "capture_png"}:
                    explicit_output = True
                    state["saved_outputs"].extend(self._save_output_operation(sw_model, plan, operation.op))
                    continue
            except Exception as exc:
                raise RuntimeError(f"执行 operation 失败: {operation.id}/{operation.op}: {exc}") from exc
            handler = DISPATCH.get(operation.op)
            if handler is None:
                raise RuntimeError(f"未实现的 API operation: {operation.op}")
            try:
                state["current_operation_id"] = operation.id
                handler(sw_model, dict(operation.params), state)
                state.pop("current_operation_id", None)
            except Exception as exc:
                state.pop("current_operation_id", None)
                raise RuntimeError(f"执行 operation 失败: {operation.id}/{operation.op}: {exc}") from exc

        if sw_model is None:
            sw_model = self._create_new_part(sw_app)

        try:
            sw_model.ForceRebuild3(False)
        except Exception as exc:
            raise RuntimeError(f"重建零件失败: {exc}") from exc

        if explicit_output:
            return tuple(state["saved_outputs"])

        try:
            return self._save_outputs(sw_model, plan)
        except Exception as exc:
            raise RuntimeError(f"保存输出失败: {exc}") from exc

    def _active_part(self, sw_app: object) -> object:
        """返回当前活动零件文档；无活动文档时报错，提示用户先打开一个零件。"""
        active_doc = getattr(sw_app, "ActiveDoc", None)
        if active_doc is None:
            raise RuntimeError(
                "已选择在当前文档建模，但 SolidWorks 没有活动文档。请先打开或新建一个零件后再执行。"
            )
        return active_doc

    def _create_new_part(self, sw_app: object) -> object:
        errors: list[str] = []

        try:
            template_path = self._default_part_template(sw_app)
            sw_model = sw_app.NewDocument(template_path, SW_DWG_PAPER_NONE, 0, 0)
            if sw_model is not None:
                return sw_model
            errors.append("NewDocument: returned None")
            active_doc = getattr(sw_app, "ActiveDoc", None)
            if active_doc is not None:
                return active_doc
            errors.append("ActiveDoc: returned None after NewDocument")
        except Exception as exc:
            errors.append(f"NewDocument(default part template): {exc}")

        raise RuntimeError(
            "无法通过 SolidWorks API 新建零件。已尝试 NewDocument(default part template)，"
            "并在 NewDocument 返回 None 时检查 ActiveDoc。请确认 SolidWorks 已完全启动，"
            "并且 SolidWorks 选项中配置了默认 Part 模板。详情: "
            + " | ".join(errors)
        )

    def _default_part_template(self, sw_app: object) -> str:
        errors: list[str] = []

        try:
            template_path = sw_app.GetUserPreferenceStringValue(SW_DEFAULT_TEMPLATE_PART)
            if isinstance(template_path, str) and template_path.strip():
                return template_path
            errors.append("GetUserPreferenceStringValue(swDefaultTemplatePart): returned empty")
        except Exception as exc:
            errors.append(f"GetUserPreferenceStringValue(swDefaultTemplatePart): {exc}")

        try:
            template_path = sw_app.GetDocumentTemplate(SW_DOC_PART, "", SW_DWG_PAPER_NONE, 0, 0)
            if isinstance(template_path, str) and template_path.strip():
                return template_path
            errors.append("GetDocumentTemplate(swDocPART): returned empty")
        except Exception as exc:
            errors.append(f"GetDocumentTemplate(swDocPART): {exc}")

        raise RuntimeError(
            "无法从 SolidWorks 读取默认 Part 模板路径。请在 SolidWorks 的 "
            "Tools > Options > System Options > Default Templates 中确认 Part 模板。"
            "详情: " + " | ".join(errors)
        )

    def _rebuild_model(self, sw_model: object) -> None:
        try:
            self._last_rebuild_result = sw_model.ForceRebuild3(False)
        except Exception as exc:
            raise RuntimeError(f"重建零件失败: {exc}") from exc

    def _validate_rebuild(self, sw_model: object) -> None:
        if not hasattr(self, "_last_rebuild_result"):
            self._rebuild_model(sw_model)

    def _save_output_operation(self, sw_model: object, plan: FeaturePlan, operation_type: str) -> tuple[str, ...]:
        output_flags = {
            "save_sldprt": operation_type == "save_sldprt",
            "export_step": operation_type == "export_step",
            "capture_png": operation_type == "capture_png",
        }
        output_plan = FeaturePlan(
            version=plan.version,
            unit=plan.unit,
            document_type=plan.document_type,
            part_name=plan.part_name,
            operations=(),
            outputs=output_flags,
            metadata=plan.metadata,
        )
        return self._save_outputs(sw_model, output_plan)

    def _save_outputs(self, sw_model: object, plan: FeaturePlan) -> tuple[str, ...]:
        from solidworks_api.com_types import byref_int, dispatch_none

        paths = plan_output_paths(plan.part_name, dict(plan.outputs))
        saved: list[str] = []
        export_data = dispatch_none()

        if "sldprt" in paths:
            target = str(Path(paths["sldprt"]))
            sw_model.Extension.SaveAs(target, 0, 1, export_data, byref_int(), byref_int())
            saved.append(target)
        if "step" in paths:
            target = str(Path(paths["step"]))
            sw_model.Extension.SaveAs(target, 0, 1, export_data, byref_int(), byref_int())
            saved.append(target)
        if "png" in paths:
            target = str(Path(paths["png"]))
            sw_model.ViewZoomtofit2()
            sw_model.SaveAs3(target, 0, 0)
            saved.append(target)
        return tuple(saved)
