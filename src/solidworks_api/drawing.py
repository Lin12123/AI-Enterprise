"""3D 零件 → 2D 工程图(三视图)出图。

由插件成果看板「3D转2D出图」按钮触发：把当前对话生成的活动 3D 零件
一键转成标准三视图工程图，保存到 workspace/outputs/drawings 下。

设计要点：
- 所有 SolidWorks COM 调用必须在专用 STA 工作线程内串行执行(见 sw_worker.py)，
  本模块只提供纯函数，由 http_service 在 worker 线程里调用。
- 工程图视图引用零件文件路径，因此出图前零件必须已保存到磁盘；若活动零件
  尚未保存(无 PathName)，先另存到 workspace/outputs/parts 再出图。
- 使用第三角视图布局 Create3rdAngleViews2(前/上/右 + 等轴测)，与国内常见
  机械制图习惯一致(第三角)；如客户需第一角可另行切换。
"""

from __future__ import annotations

from pathlib import Path


# SolidWorks 文档类型常量(swDocumentTypes_e)
_SW_DOC_PART = 1
_SW_DOC_DRAWING = 3

# InsertModelAnnotations3 的 option(swInsertAnnotation_e 位标志):
#   1 = swInsertDimensionsMarkedForDrawing   (仅"标记为工程图用途"的尺寸)
#   2 = swInsertDimensionsNotMarkedForDrawing (未标记的尺寸)
# 程序化/AI 建模生成的零件尺寸默认都"未标记"，只传 1 会一条也导不进来，
# 图纸上看不到任何尺寸。因此必须传 1|2=3 才能把全部模型尺寸导入工程图。
_SW_INSERT_ALL_DIMENSIONS = 3


def create_drawing_from_active_part(app: object, rules: list | None = None) -> dict:
    """把当前活动的 3D 零件转为三视图工程图并保存。

    参数:
        app: 已连接的 SolidWorks.Application COM对象(SolidWorksSession.app)。
        rules: 从企业云平台获取的标准/规范规则列表(每条含 scope_feature/clause/
               params_json)。用于依据企业标准生成尺寸标注与公差等级；为空时仅
               导入模型尺寸(不加公差)。
    返回:
        {"ok": bool, "status": str, "message": str, "outputs": [工程图路径, ...]}

    任何失败都以 ok=False + 可读中文 message 返回，绝不抛出未捕获异常导致
    工作线程崩溃。
    """
    try:
        model = _get_active_part(app)
    except RuntimeError as exc:
        return _fail(str(exc))

    # 1) 确保零件已保存到磁盘(工程图视图需引用零件文件路径)
    try:
        part_path = _ensure_part_saved(app, model)
    except RuntimeError as exc:
        return _fail(f"保存零件失败: {exc}")

    # 2) 新建工程图文档
    try:
        draw_model = _new_drawing_doc(app)
    except RuntimeError as exc:
        return _fail(f"新建工程图失败: {exc}")

    # 3) 生成标准三视图(前/上/右 + 等轴测)
    try:
        _insert_three_views(draw_model, part_path)
    except RuntimeError as exc:
        return _fail(f"插入三视图失败: {exc}")

    # 3.1) 依据企业标准/规范生成尺寸标注与公差(标注失败不阻断出图，只降级为无标注)
    annotation_note = ""
    try:
        ann = _apply_dimensions_and_tolerance(app, draw_model, rules or [])
        dim_count = ann.get("dim_count", 0)
        grade = ann.get("grade", "")
        tol_applied = ann.get("tol_applied", 0)
        if dim_count <= 0:
            # 一条尺寸都没画进图: 如实告知，不再谎报"已标注"
            annotation_note = "(未能导入模型尺寸: 零件尺寸可能未标记为工程图用途，图纸暂无尺寸标注)"
        elif grade and tol_applied > 0:
            annotation_note = (
                f"，已标注 {dim_count} 处尺寸并按企业标准对 {tol_applied} 处应用公差等级 {grade}"
            )
        elif grade:
            annotation_note = f"，已标注 {dim_count} 处尺寸(公差等级 {grade})"
        else:
            annotation_note = f"，已导入 {dim_count} 处模型尺寸标注"
    except Exception as exc:
        annotation_note = f"(尺寸/公差标注降级: {exc})"

    # 4) 保存工程图到 workspace/outputs/drawings
    try:
        out_path = _save_drawing(app, draw_model, model)
    except RuntimeError as exc:
        return _fail(f"保存工程图失败: {exc}")

    return {
        "ok": True,
        "status": "executed",
        "message": f"已生成三视图工程图: {out_path}{annotation_note}",
        "outputs": [out_path],
    }


def _fail(message: str) -> dict:
    return {"ok": False, "status": "error", "message": message, "outputs": []}


def _get_active_part(app: object) -> object:
    """取当前活动零件文档；非零件(装配/工程图/空)一律拒绝。"""
    from solidworks_api.com_types import get_doc_type

    try:
        model = app.ActiveDoc
    except Exception as exc:
        raise RuntimeError(f"无法获取活动文档: {exc}") from exc
    if model is None:
        raise RuntimeError("当前没有打开的文档，请先完成 3D 建模再出图。")
    doc_type = get_doc_type(model)
    if doc_type is None:
        raise RuntimeError("无法判断文档类型，请确认当前打开的是 3D 零件窗口。")
    if doc_type != _SW_DOC_PART:
        raise RuntimeError("当前活动文档不是 3D 零件，无法出图。请切换到本次生成的零件窗口。")
    return model


def _ensure_part_saved(app: object, model: object) -> str:
    """确保零件已保存并返回其磁盘路径；未保存则另存到 workspace/outputs/parts。"""
    from solidworks_api.com_types import byref_int, dispatch_none
    from solidworks_api.output_manager import next_versioned_path
    from app.config import PARTS_DIR, ensure_dirs

    try:
        existing = str(model.GetPathName() or "").strip()
    except Exception:
        existing = ""
    if existing:
        # 已保存过：确保最新改动落盘
        try:
            model.Save3(1, byref_int(), byref_int())
        except Exception:
            try:
                model.Save()
            except Exception:
                pass
        return existing

    ensure_dirs()
    try:
        title = str(model.GetTitle() or "").strip()
    except Exception:
        title = ""
    part_name = title or "ai_part"
    target = str(Path(next_versioned_path(PARTS_DIR, part_name, ".SLDPRT")))
    try:
        model.Extension.SaveAs(target, 0, 1, dispatch_none(), byref_int(), byref_int())
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    return target


def _read_default_drawing_template(app: object) -> str:
    """读取 SolidWorks 默认工程图模板路径。

    真机上 GetUserPreferenceStringValue 在不同 pywin32 dispatch 模式下可能被
    暴露为方法或属性；且有时按枚举值读回为空。这里做多重兼容：
    1) callable 判断后调用/取值；
    2) 兼容 swDefaultTemplateDrawing=3 常量；
    3) 任一读到非空即返回。
    """
    getter = getattr(app, "GetUserPreferenceStringValue", None)
    if getter is None:
        return ""
    for pref in (3,):  # swUserPreferenceStringValue_e.swDefaultTemplateDrawing = 3
        try:
            value = getter(pref) if callable(getter) else ""
        except Exception:
            value = ""
        value = str(value or "").strip()
        if value:
            return value
    return ""


def _guess_drawing_template() -> str:
    """当读不到默认模板时，扫描 SolidWorks 常见安装目录猜测工程图模板。

    覆盖 chinese-simplified(chinese-sim) 与 english 语言目录、ProgramData 模板目录，
    命中第一个存在的 .drwdot 即返回；全部不存在则返回空。
    """
    import glob

    patterns = [
        r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates\*.drwdot",
        r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates\*\*.drwdot",
        r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\lang\*\*.drwdot",
        r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\data\templates\*.drwdot",
    ]
    for pat in patterns:
        try:
            hits = sorted(glob.glob(pat))
        except Exception:
            hits = []
        for hit in hits:
            if Path(hit).is_file():
                return hit
    return ""


def _new_drawing_doc(app: object) -> object:
    """新建工程图文档。优先用默认工程图模板，取不到时扫描常见安装目录兜底。"""
    template = _read_default_drawing_template(app)
    if not template or not Path(template).is_file():
        guessed = _guess_drawing_template()
        if guessed:
            template = guessed
    if not template:
        raise RuntimeError(
            "未找到默认工程图模板(swDefaultTemplateDrawing)，且在常见安装目录未扫描到 .drwdot 模板。"
            "请在 SolidWorks 选项→默认模板中设置工程图模板后重试。"
        )
    try:
        # NewDocument(template, paperSize, width, height)；paperSize=12 约 A3 横向
        draw = app.NewDocument(template, 12, 0.0, 0.0)
    except Exception as exc:
        raise RuntimeError(f"以模板 {template} 新建工程图失败: {exc}") from exc
    if draw is None:
        raise RuntimeError(f"NewDocument 返回 None，工程图模板可能不可用: {template}")
    return draw


def _insert_three_views(draw_model: object, part_path: str) -> None:
    """在工程图上放置标准三视图(前/上/右)+ 等轴测。"""
    try:
        draw = draw_model  # IDrawingDoc 接口即工程图 model
        ok = draw.Create3rdAngleViews2(part_path)
    except Exception as exc:
        raise RuntimeError(f"Create3rdAngleViews2 异常: {exc}") from exc
    if not ok:
        raise RuntimeError("Create3rdAngleViews2 返回失败(可能零件路径无效或模板不含视图框)。")
    try:
        draw_model.ViewZoomtofit2()
    except Exception:
        pass


# ISO 286 基本公差数值(单位 mm)，按 IT 等级取一个通用尺寸段(>18~30mm)的近似值，
# 仅用于在没有逐尺寸精算时给工程图一个合理的默认对称公差。真机可按尺寸段细化。
_IT_GRADE_DEFAULT_TOL_MM = {
    "IT5": 0.009,
    "IT6": 0.013,
    "IT7": 0.021,
    "IT8": 0.033,
    "IT9": 0.052,
    "IT10": 0.084,
    "IT11": 0.130,
    "IT12": 0.210,
    "IT13": 0.330,
}


def _extract_tolerance_grade(rules:list) -> str:
    """从企业标准规则的 params_json 中解析公差等级(如 IT8)。

    规则字段约定: 每条 rule 含 params_json(可能是 dict 或 JSON 字符串)，
    其中中文键 "公差等级" 给出 IT 等级。取第一条命中的等级。
    找不到返回空字符串。
    """
    import json as _json

    for rule in rules or []:
        if not isinstance(rule, dict):
            continue
        params = rule.get("params_json")
        if isinstance(params, str):
            try:
                params = _json.loads(params)
            except Exception:
                continue
        if not isinstance(params, dict):
            continue
        grade = params.get("公差等级") or params.get("tolerance_grade")
        if grade:
            grade = str(grade).strip().upper()
            if grade and not grade.startswith("IT"):
                grade = "IT" + grade
            return grade
    return ""


def _count_display_dimensions(draw_model: object) -> int:
    """统计整张工程图当前已导入的显示尺寸总数(遍历所有视图)。

    用于判断 InsertModelAnnotations3 是否真的把尺寸画进了图纸——
    返回值非 None 并不代表真的导入了尺寸(可能 0 条)，必须用实际计数核实。
    """
    total = 0
    try:
        view = draw_model.GetFirstView()
    except Exception:
        return 0
    while view is not None:
        try:
            dim = view.GetFirstDisplayDimension5()
        except Exception:
            dim = None
        while dim is not None:
            total += 1
            try:
                dim = dim.GetNext5()
            except Exception:
                dim = None
        try:
            view = view.GetNextView()
        except Exception:
            break
    return total


def _apply_dimensions_and_tolerance(app: object, draw_model: object, rules: list) -> dict:
    """在工程图上导入模型尺寸并按企业标准应用默认公差。

    返回 {"dim_count": int, "grade": str, "tol_applied": int}:
      - dim_count:   实际导入到图纸的显示尺寸条数(0 表示一条都没画进去)
      - grade:       命中的企业标准公差等级(如 "IT8"), 未命中为空串
      - tol_applied: 实际设置了对称公差的尺寸条数
    该函数所有 COM 调用均在内部尽量兜底，异常上抛由主流程降级处理。
    """
    # 1) 导入模型尺寸到所有视图
    #    InsertModelAnnotations3(type, option, allViews, duplicateDimensions, sameEdges, ...)
    #    type=0(swDimension) 导入模型尺寸; option=3 = 标记+未标记全部导入(见常量说明)
    try:
        ext = draw_model.Extension
        ext.InsertModelAnnotations3(0, _SW_INSERT_ALL_DIMENSIONS, True, False, False, False)
    except Exception:
        pass

    # 无论文档层调用是否成功，都再逐视图补一次(某些版本文档层不生效)，
    # 保证程序化建模的"未标记"尺寸也能被导入。
    try:
        view = draw_model.GetFirstView()
        # 首视图通常是图纸页，从其下一个视图开始
        view = view.GetNextView() if view is not None else None
        while view is not None:
            try:
                view.InsertModelAnnotations3(0, _SW_INSERT_ALL_DIMENSIONS, False, False, False, False)
            except Exception:
                pass
            try:
                view = view.GetNextView()
            except Exception:
                break
    except Exception:
        pass

    try:
        draw_model.EditRebuild3()
    except Exception:
        pass

    # 用实际显示尺寸数核实是否真的画进了图纸(返回值非 None 不可靠)
    dim_count = _count_display_dimensions(draw_model)

    # 2) 依据企业标准的公差等级设置默认对称公差
    grade = _extract_tolerance_grade(rules)
    tol_applied = 0
    if not grade:
        return {"dim_count": dim_count, "grade": "", "tol_applied": 0}

    tol_value = _IT_GRADE_DEFAULT_TOL_MM.get(grade)
    if tol_value is None:
        # 未知等级: 只回等级不改公差数值
        return {"dim_count": dim_count, "grade": grade, "tol_applied": 0}

    # 遍历工程图各视图的显示尺寸，设置对称公差(swTolBILATERAL=3)
    try:
        view = draw_model.GetFirstView()
        while view is not None:
            try:
                dim = view.GetFirstDisplayDimension5()
            except Exception:
                dim = None
            while dim is not None:
                try:
                    disp = dim.GetDimension2(0)
                    if disp is not None:
                        # swTolBILATERAL=3; 单位 m，SolidWorks 尺寸内部为米
                        disp.SetToleranceType(3)
                        disp.SetToleranceValues(tol_value / 1000.0, -tol_value / 1000.0)
                        tol_applied += 1
                except Exception:
                    pass
                try:
                    dim = dim.GetNext5()
                except Exception:
                    dim = None
            view = view.GetNextView()
    except Exception:
        pass

    try:
        draw_model.EditRebuild3()
    except Exception:
        pass

    return {"dim_count": dim_count, "grade": grade, "tol_applied": tol_applied}


def _save_drawing(app: object, draw_model: object, part_model: object) -> str:
    """把工程图保存到 workspace/outputs/drawings，文件名沿用零件名。"""
    from solidworks_api.com_types import byref_int, dispatch_none
    from solidworks_api.output_manager import next_versioned_path
    from app.config import DRAWINGS_DIR, ensure_dirs

    ensure_dirs()
    try:
        title = str(part_model.GetTitle() or "").strip()
    except Exception:
        title = ""
    name = title or "ai_part"
    target = str(Path(next_versioned_path(DRAWINGS_DIR, name, ".SLDDRW")))
    try:
        draw_model.Extension.SaveAs(target, 0, 1, dispatch_none(), byref_int(), byref_int())
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc
    return target