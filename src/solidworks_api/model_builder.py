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


# 意图判断关键词：当活动文档已有零件时，用于区分"修改当前零件"还是"新增零件"。
# 修改类词汇 → 复用当前窗口；新增类词汇 → 另开新窗口。
_MODIFY_INTENT_KEYWORDS = (
    "修改", "改成", "改为", "调整", "在此基础", "在这基础", "在现有", "继续",
    "接着", "给它", "给这个", "把它", "把这个", "对当前", "对这个", "当前零件",
    "现有零件", "这个零件", "再加", "再开", "追加", "补充",
    "modify", "change", "edit", "adjust", "update", "add to", "current part",
    "this part", "existing part",
)
_NEW_INTENT_KEYWORDS = (
    "新建", "新增", "新的零件", "新零件", "另建", "另画", "另外画", "另外做",
    "再画一个", "再做一个", "重新画", "重新建", "换一个", "单独",
    "new part", "another part", "create a new", "separate part", "brand new",
)


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
    def build(self, sw_app: object, plan: FeaturePlan, use_active_doc: bool = False,
              prompt: str = "") -> tuple[str, ...]:
        # use_active_doc=True 时优先在当前活动文档里建模：
        #   - 当前活动文档是"空零件"(只有默认基准面/原点) → 直接复用；
        #   - 当前活动文档已有实际零件 → 根据用户自然语言(prompt)判断意图：
        #       * 修改类意图(修改/在此基础/继续...) → 复用当前文档，新特征叠加到现有零件；
        #       * 新增类意图(新建/再画一个...)或意图不明 → 新建窗口，避免破坏已有零件。
        # use_active_doc=False 时保持原有行为：始终新建零件文档。
        plan = plan_operations(plan)
        sw_model, needs_clear = self._pick_target_doc(sw_app, use_active_doc, prompt)
        if sw_model is not None and needs_clear:
            # 修改/重绘意图：在同一个 3D 模型文件里从零重绘完整零件，
            # 先清空旧特征，避免新特征叠加到旧零件上（越堆越多）。
            self._clear_all_features(sw_model)
        create_new_needed = sw_model is None
        state = {"base": {}, "boss": {}, "sketches": {}, "saved_outputs": [], "sw_app": sw_app}
        explicit_output = False
        for operation in plan.operations:
            try:
                if operation.op == "create_new_part":
                    # 若已经复用了当前空零件文档，跳过 create_new_part 避免多开窗口
                    if not create_new_needed and sw_model is not None:
                        continue
                    sw_model = self._create_new_part(sw_app)
                    create_new_needed = False
                    continue
                if sw_model is None:
                    sw_model = self._create_new_part(sw_app)
                    create_new_needed = False
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

        # 关键：程序化建模生成的尺寸默认都是「未标记出图」状态，
        # 工程图端 InsertModelAnnotations3 会一条也导不进来(即便传 option=3)。
        # 建完并 rebuild 之后统一把所有尺寸标记为「可出工程图」，
        # 让后续 3D→2D 出图能自动把孔距/孔径/长宽高等挂到视图上。
        self._mark_all_dimensions_for_drawing(sw_model)

        if explicit_output:
            return tuple(state["saved_outputs"])

        try:
            return self._save_outputs(sw_model, plan)
        except Exception as exc:
            raise RuntimeError(f"保存输出失败: {exc}") from exc

    def _pick_target_doc(self, sw_app: object, use_active_doc: bool,
                         prompt: str = "") -> tuple[object | None, bool]:
        """按需选择目标文档，返回 (目标文档, 是否需要先清空)：
        - use_active_doc=False → (None, False)，始终新建；
        - use_active_doc=True 且当前活动文档是"空零件" → (它, False)，直接复用；
        - use_active_doc=True 且当前活动文档已有零件 →
            * prompt 判定为"修改当前"意图 → (它, True)，复用当前文件但先清空
              旧特征后完整重绘（符合用户"在同一模型文件里清空重绘"的期望，
              而非把新特征叠加到旧零件上）；
            * prompt 判定为"新增零件"意图或意图不明 → (None, False)，新建窗口。
        （返回 None 时会在遇到首个建模 op 前调 _create_new_part）
        """
        if not use_active_doc:
            return None, False
        active_doc = getattr(sw_app, "ActiveDoc", None)
        if active_doc is None:
            return None, False
        if self._is_empty_part(active_doc):
            # 空零件，直接复用，无需清空
            return active_doc, False
        # 活动文档已有实际零件：按用户自然语言意图决定复用还是新建
        if self._classify_intent(prompt) == "modify":
            # 修改意图：复用当前文件，但先清空旧特征再完整重绘
            return active_doc, True
        # 新增意图 or 意图不明 → 新窗口，保护已有零件
        return None, False

    @staticmethod
    def _classify_intent(prompt: str) -> str:
        """根据用户自然语言判断意图：
        返回 "modify"(修改当前零件) 或 "new"(新增/新建零件)。
        规则：
        - 命中新增类关键词 → "new"（新增优先级更高，避免误判为修改）;
        - 命中修改类关键词 → "modify";
        - 都未命中 → "new"（安全默认：不叠加破坏已有零件，另开窗口）。
        """
        text = (prompt or "").lower()
        if not text.strip():
            return "new"
        if any(kw in text for kw in _NEW_INTENT_KEYWORDS):
            return "new"
        if any(kw in text for kw in _MODIFY_INTENT_KEYWORDS):
            return "modify"
        return "new"

    def _is_empty_part(self, sw_model: object) -> bool:
        """判断一个零件文档是否为"空"：只含默认基准面/原点，没有用户特征。"""
        # 1) 必须是零件类型(swDocPART=1)。装配/工程图/其它一律视为非空(不适合建模)
        from solidworks_api.com_types import get_doc_type

        doc_type = get_doc_type(sw_model)
        if doc_type is None:
            return False
        if doc_type != SW_DOC_PART:
            return False

        # 2) 遍历顶层 Feature，若发现非默认特征则视为非空
        default_names = {"Front Plane", "Top Plane", "Right Plane", "Origin",
                         "前视基准面", "上视基准面", "右视基准面", "原点"}
        try:
            feature = sw_model.FirstFeature()
        except Exception:
            return False
        while feature is not None:
            try:
                name = feature.Name
            except Exception:
                name = ""
            if name and name not in default_names:
                return False
            try:
                feature = feature.GetNextFeature()
            except Exception:
                break
        return True

    def _clear_all_features(self, sw_model: object) -> int:
        """清空零件文档里的所有用户特征，只保留默认基准面/原点。

        用于「修改/重绘」场景：用户希望在同一个 3D 模型文件里得到一个
        从零重绘的完整零件，而不是把新特征叠加到旧零件上。
        遍历顶层 Feature，把非默认特征逐个 Select 后调用 EditDelete 删除。
        返回删除的特征数量。
        """
        default_names = {"Front Plane", "Top Plane", "Right Plane", "Origin",
                         "前视基准面", "上视基准面", "右视基准面", "原点"}
        deleted = 0
        try:
            model_ext = getattr(sw_model, "Extension", None)
        except Exception:
            model_ext = None
        # 反复扫描直到没有可删除的用户特征为止（删除会改变链表结构，
        # 单次遍历+边删边走可能漏删，改为多轮全量扫描更稳）
        for _ in range(1000):
            target = None
            try:
                feature = sw_model.FirstFeature()
            except Exception:
                break
            while feature is not None:
                try:
                    name = feature.Name
                except Exception:
                    name = ""
                if name and name not in default_names:
                    target = feature
                    break
                try:
                    feature = feature.GetNextFeature()
                except Exception:
                    break
            if target is None:
                break
            try:
                sw_model.ClearSelection2(True)
            except Exception:
                pass
            try:
                selected = target.Select2(False, 0)
            except Exception:
                selected = False
            if not selected:
                # 无法选中，避免死循环
                break
            deleted_ok = False
            # 优先用 ModelDocExtension.DeleteSelection2（可携带子特征）
            if model_ext is not None:
                try:
                    deleted_ok = bool(model_ext.DeleteSelection2(0))
                except Exception:
                    deleted_ok = False
            if not deleted_ok:
                try:
                    deleted_ok = bool(sw_model.EditDelete())
                except Exception:
                    deleted_ok = False
            if not deleted_ok:
                # 删除失败，停止以免死循环
                break
            deleted += 1
        try:
            sw_model.ClearSelection2(True)
        except Exception:
            pass
        return deleted

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

    def _mark_all_dimensions_for_drawing(self, sw_model: object) -> None:
        """把零件里所有特征尺寸都标记为「可出工程图」。

        程序化 API 建模(AddDimension/HoleWizard/ExtrudeCut...)生成的尺寸,
        MarkedForDrawing 属性默认为 False。工程图端 InsertModelAnnotations3
        即使传 option=3(标记+未标记全导)，SolidWorks 2019 上仍常常一条都
        导不进来，导致三视图上没有任何标注。

        这里在建模全部完成、ForceRebuild3 之后统一调用
        ModelDocExtension.SelectAll + MarkAllDimensionsForDrawing(True)
        给所有尺寸盖上「可出图」章。任何异常都吞掉、不阻断保存流程
        (最坏情况就是回退到出图端的兜底)。
        """
        try:
            ext = getattr(sw_model, "Extension", None)
            if ext is None:
                return
            try:
                ext.SelectAll()
            except Exception:
                # 某些版本没有 Extension.SelectAll，退回文档级
                try:
                    sw_model.Extension.SelectAll()
                except Exception:
                    pass
            try:
                # MarkAllDimensionsForDrawing(mark: bool)
                # 会遍历文档里所有 DisplayDimension 把 MarkedForDrawing 置为 True
                ext.MarkAllDimensionsForDrawing(True)
            except Exception:
                pass
            try:
                sw_model.ClearSelection2(True)
            except Exception:
                pass
        except Exception:
            # 兜底：任何异常都静默，避免影响建模主流程
            pass

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
