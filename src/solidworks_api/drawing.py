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

    # 2.1) 按零件包围盒最长边选择图幅(A4~A1)并设置到图纸；失败不阻断，沿用模板默认图幅
    paper_name = ""
    try:
        max_edge = _get_part_bounding_box_max_edge_mm(model)
        paper_code, paper_name = _choose_paper_size(max_edge)
        if not _apply_sheet_size(draw_model, paper_code):
            paper_name = ""  # 未成功设置就不在卡片里声称图幅
    except Exception:
        paper_name = ""

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
            # 一条模型尺寸都没画进图: 用包围盒总体尺寸兜底，保证图上有长宽高基本尺寸
            bbox_note = _insert_bbox_fallback_note(draw_model, model)
            if bbox_note:
                annotation_note = f"，模型尺寸未标记，已按包围盒兜底标注 {bbox_note}"
            else:
                annotation_note = "(未能导入模型尺寸且无法取得包围盒: 图纸暂无尺寸标注)"
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

    # 3.2) 技术要求完全沿用模板/图框自带的那份，程序不再写入任何技术要求文本框，
    #      避免与模板重复。企业模板已固化技术要求，出图无需额外补充。
    tech_note = "，技术要求沿用模板"

    # 图幅信息(2.1 设置成功时)
    paper_note = f"，图幅 {paper_name}" if paper_name else ""

    # 4) 保存工程图到 workspace/outputs/drawings
    try:
        out_path = _save_drawing(app, draw_model, model)
    except RuntimeError as exc:
        return _fail(f"保存工程图失败: {exc}")

    return {
        "ok": True,
        "status": "executed",
        "message": f"已生成三视图工程图: {out_path}{paper_note}{annotation_note}{tech_note}",
        "outputs": [out_path],
        # 供"上传云平台"使用: 本次出图关联的 3D 零件与 2D 工程图磁盘路径
        "part_path": part_path,
        "drawing_path": out_path,
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


# SolidWorks 图幅规格常量(swDwgPaperSizes_e)。国标图幅按最长边(mm)从大到小匹配。
# A0=841×1189, A1=594×841, A2=420×594, A3=297×420, A4=210×297。
# swDwgPapersUserDefined=12 用于自定义；这里优先用标准枚举。
_SW_PAPER_A4 = 8   # swDwgPaperA4size (横向)
_SW_PAPER_A3 = 6   # swDwgPaperA3size
_SW_PAPER_A2 = 4   # swDwgPaperA2size
_SW_PAPER_A1 = 2   # swDwgPaperA1size
_SW_PAPER_A0 = 0   # swDwgPaperA0size

# 图幅可容纳的零件最长边阈值(mm)。留出视图间距与标注余量，按较保守取值。
# 零件最长边 <= 阈值 即选用该图幅；超过 A1 上限一律用 A1(A0 慎用，多数厂不常备)。
_PAPER_BY_MAX_EDGE_MM = (
    (150.0, _SW_PAPER_A4, "A4"),
    (300.0, _SW_PAPER_A3, "A3"),
    (600.0, _SW_PAPER_A2, "A2"),
    (1200.0, _SW_PAPER_A1, "A1"),
)


def _valid_box6(box: object) -> tuple:
    """把任意来源的包围盒结果规整成 6 元组(米)。无效或退化盒返回 None。"""
    if box is None:
        return None
    try:
        xmin, ymin, zmin, xmax, ymax, zmax = (float(v) for v in box[:6])
    except Exception:
        return None
    if abs(xmax - xmin) + abs(ymax - ymin) + abs(zmax - zmin) <= 0.0:
        return None
    return (xmin, ymin, zmin, xmax, ymax, zmax)


def _read_part_box6(part_model: object) -> tuple:
    """多重兜底取零件包围盒 6 元组(xmin..zmax, 单位米)。全部失败返回 None。

    真机上 IModelDoc2 / ModelDocExtension 并无可靠的 GetBox；正确来源是
    IPartDoc.GetPartBox(True) 或遍历实体的 IBody2.GetBodyBox()。按可靠性依次尝试，
    并兼容离线单测里 Extension.GetBox(0) 的 mock 写法。
    """
    # 1) IPartDoc.GetPartBox(bUseUserView): 零件文档最直接的整体包围盒
    try:
        box = _valid_box6(part_model.GetPartBox(True))
        if box is not None:
            return box
    except Exception:
        pass
    # 2) 遍历实体 GetBodyBox 求并集(适配多实体与程序化建模)
    try:
        bodies = part_model.GetBodies2(0, True)
    except Exception:
        bodies = None
    if bodies:
        acc = [None, None, None, None, None, None]
        for body in bodies:
            try:
                bb = _valid_box6(body.GetBodyBox())
            except Exception:
                bb = None
            if bb is None:
                continue
            for i in range(3):
                acc[i] = bb[i] if acc[i] is None else min(acc[i], bb[i])
            for i in range(3, 6):
                acc[i] = bb[i] if acc[i] is None else max(acc[i], bb[i])
        if acc[0] is not None:
            return tuple(acc)
    # 3) 兼容旧接口/离线 mock: Extension.GetBox(0) 与 GetBox(0)
    try:
        box = _valid_box6(part_model.Extension.GetBox(0))
        if box is not None:
            return box
    except Exception:
        pass
    try:
        box = _valid_box6(part_model.GetBox(0))
        if box is not None:
            return box
    except Exception:
        pass
    return None


def _get_part_bounding_box_max_edge_mm(part_model: object) -> float:
    """取零件包围盒最长边(mm)，用于按零件大小选图幅。取不到返回 0(上层用 A3 兜底)。"""
    box = _read_part_box6(part_model)
    if box is None:
        return 0.0
    xmin, ymin, zmin, xmax, ymax, zmax = box
    dx = abs(xmax - xmin) * 1000.0
    dy = abs(ymax - ymin) * 1000.0
    dz = abs(zmax - zmin) * 1000.0
    return max(dx, dy, dz)


def _get_part_bbox_dims_mm(part_model: object) -> tuple:
    """取零件包围盒三向跨度(长/宽/高, mm)，从大到小排序返回 (L, W, H)。取不到返回 (0,0,0)。"""
    box = _read_part_box6(part_model)
    if box is None:
        return (0.0, 0.0, 0.0)
    xmin, ymin, zmin, xmax, ymax, zmax = box
    dims = sorted(
        [abs(xmax - xmin) * 1000.0, abs(ymax - ymin) * 1000.0, abs(zmax - zmin) * 1000.0],
        reverse=True,
    )
    return (round(dims[0], 2), round(dims[1], 2), round(dims[2], 2))


def _fmt_mm(v: float) -> str:
    """把 mm 数值格式化成简洁字符串(整数不带小数点)。"""
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _choose_paper_size(max_edge_mm: float) -> tuple:
    """按零件最长边选择图幅，返回 (swDwgPaperSizes_e 值, 图幅名如 'A3')。

    取不到尺寸(<=0)时用 A3 兜底(常见通用图幅)。超过 A1 上限用 A1。
    """
    if max_edge_mm <= 0:
        return _SW_PAPER_A3, "A3"
    for limit, code, name in _PAPER_BY_MAX_EDGE_MM:
        if max_edge_mm <= limit:
            return code, name
    return _SW_PAPER_A1, "A1"


def _apply_sheet_size(draw_model: object, paper_code: int) -> bool:
    """把工程图当前图纸设置为指定图幅规格。成功返回 True。

    优先 Sheet.SetSize(paperSize, templateIn, ...)；不同版本签名有差异，做多重兜底：
      1) draw_model.SetupSheet5 全参重设(带图幅枚举)；
      2) 取当前 Sheet 调 SetSize；
    任一成功即返回 True，全部失败返回 False(不阻断出图，沿用模板默认图幅)。
    """
    # 方式一: 直接对当前 Sheet 设图幅(标准枚举, width/height 传 0 由枚举决定)
    try:
        sheet = draw_model.GetCurrentSheet()
        if sheet is not None:
            try:
                sheet.SetSize(paper_code, 0.0, 0.0)
                return True
            except Exception:
                pass
    except Exception:
        pass
    return False


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


def _iter_rule_params(rules: list):
    """遍历规则，逐条产出可用的 params_json dict(字符串自动 json 解析)。"""
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
        if isinstance(params, dict):
            yield rule, params


# 未注尺寸公差三档默认值(mm)与适用场景，作为知识库未配置时的兜底文案。
_DEFAULT_GENERAL_TOL = [
    ("高精度", "±0.02mm", "精密配合、密封面、定位基准"),
    ("中精度", "±0.05mm", "常规装配、一般配合"),
    ("低精度", "±0.10mm", "非关键外形、自由尺寸"),
]

# 表面粗糙度默认取值规范(功能面→Ra)，知识库未配置时的兜底。
_DEFAULT_ROUGHNESS = [
    ("非接触自由面(默认)", "Ra12.5~25μm"),
    ("螺栓贴合端面/箱体外观非功能面", "Ra6.3μm"),
    ("普通轴孔间隙配合/安装定位面", "Ra3.2μm"),
    ("滑动配合面/轴承安装位/油封密封面", "Ra1.6μm"),
    ("精密轴颈/液压密封工作面", "Ra0.8μm"),
]


def _normalize_tiers(raw) -> list:
    """把 dict / list 形式的未注公差配置规整成 [(档位, 公差, 适用场景), ...]。"""
    out = []
    if isinstance(raw, dict):
        for lvl, v in raw.items():
            if isinstance(v, dict):
                out.append((str(lvl), str(v.get("tol") or v.get("公差") or ""),
                            str(v.get("scope") or v.get("适用") or "")))
            else:
                out.append((str(lvl), str(v), ""))
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                out.append((str(item.get("level") or item.get("档位") or ""),
                            str(item.get("tol") or item.get("公差") or ""),
                            str(item.get("scope") or item.get("适用") or "")))
    return [t for t in out if t[0] and t[1]]


def _extract_general_tolerance_tiers(rules: list) -> list:
    """从规则解析未注尺寸公差三档，解析不到返回企业标准默认三档。

    约定 params_json 键 "未注公差":
      {"高精度": {"tol":"±0.02mm","scope":"..."}, ...}
      或 [{"level":"高精度","tol":"±0.02mm","scope":"..."}, ...]
    """
    for _rule, params in _iter_rule_params(rules):
        raw = params.get("未注公差") or params.get("general_tolerance_tiers")
        tiers = _normalize_tiers(raw)
        if tiers:
            return tiers
    return list(_DEFAULT_GENERAL_TOL)


def _extract_roughness_spec(rules: list) -> list:
    """从规则解析表面粗糙度规范，解析不到返回企业标准默认规范。

    约定 params_json 键 "表面粗糙度": {"功能面": "Ra值", ...}
    或 [{"face":"...","ra":"Ra1.6μm"}, ...]
    """
    for _rule, params in _iter_rule_params(rules):
        raw = params.get("表面粗糙度") or params.get("roughness")
        out = []
        if isinstance(raw, dict):
            out = [(str(k), str(v)) for k, v in raw.items() if k and v]
        elif isinstance(raw, list):
            for item in raw:
                if isinstance(item, dict):
                    face = str(item.get("face") or item.get("功能面") or "")
                    ra = str(item.get("ra") or item.get("Ra") or "")
                    if face and ra:
                        out.append((face, ra))
        if out:
            return out
    return list(_DEFAULT_ROUGHNESS)


def _extract_extra_tech_notes(rules: list) -> list:
    """从规则解析额外技术要求条目(自由文本列表)。约定 params_json 键 "技术要求"
    为字符串列表或单条字符串。去重保序返回。
    """
    notes = []
    for _rule, params in _iter_rule_params(rules):
        items = params.get("技术要求") or params.get("tech_notes")
        if isinstance(items, list):
            notes.extend(str(x).strip() for x in items if str(x).strip())
        elif isinstance(items, str) and items.strip():
            notes.append(items.strip())
    seen = set()
    uniq = []
    for n in notes:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq


def _build_tech_requirements_text(rules: list) -> str:
    """按企业标准拼装【技术要求】文本框内容(编号条目)。

    固定包含: 未注尺寸公差三档、表面粗糙度规范、知识库补充条目，
    再补通用兜底项(未注圆角/去毛刺/表面处理/焊接)。返回多行字符串。
    """
    lines = ["技术要求"]
    idx = 1

    tiers = _extract_general_tolerance_tiers(rules)
    if tiers:
        tier_txt = "；".join(
            f"{lvl}{tol}({scope})" if scope else f"{lvl}{tol}"
            for lvl, tol, scope in tiers
        )
        lines.append(f"{idx}. 未注尺寸公差按公司统一精度标准分档管控：{tier_txt}。")
        idx += 1

    rough = _extract_roughness_spec(rules)
    if rough:
        rough_txt = "；".join(f"{face} {ra}" for face, ra in rough)
        lines.append(f"{idx}. 表面粗糙度未注处按功能面取值：{rough_txt}。")
        idx += 1

    for note in _extract_extra_tech_notes(rules):
        lines.append(f"{idx}. {note}")
        idx += 1

    defaults = [
        "未注圆角 R1，未注倒角 C1，锐边去毛刺。",
        "表面处理方式按图纸标题栏或工艺文件执行。",
        "焊接件焊缝按 GB/T 985 执行，焊后去除焊渣、飞溅。",
        "装配检验特殊要求见工艺文件。",
    ]
    for d in defaults:
        lines.append(f"{idx}. {d}")
        idx += 1
    return "\n".join(lines)


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
    # 保证程序化建模的"未标记"尺寸也能被导入。逐视图导入前必须先激活该视图，
    # 否则 InsertModelAnnotations3 会作用在错误的视图上导致一条也导不进来。
    try:
        view = draw_model.GetFirstView()
        # 首视图通常是图纸页，从其下一个视图开始
        view = view.GetNextView() if view is not None else None
        while view is not None:
            try:
                name = str(view.GetName2())
                if name:
                    draw_model.ActivateView(name)
            except Exception:
                pass
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


def _build_bbox_dims_text(part_model: object) -> str:
    """把零件总体尺寸拼成一条兜底标注文本(总长×总宽×总高)。取不到返回空串。

    程序化/AI 建模的零件尺寸常\"未标记\"，InsertModelAnnotations3 可能一条也导不进
    图纸。为满足\"图纸上必须有长宽高等基本尺寸\"的最低要求，用包围盒总体尺寸兜底：
    保证图上至少有长/宽/高三个基本尺寸数据。
    """
    l, w, h = _get_part_bbox_dims_mm(part_model)
    if l <= 0 and w <= 0 and h <= 0:
        return ""
    return (
        "总体尺寸(mm)\n"
        f"总长 L = {_fmt_mm(l)}\n"
        f"总宽 W = {_fmt_mm(w)}\n"
        f"总高 H = {_fmt_mm(h)}"
    )


def _insert_bbox_fallback_note(draw_model: object, part_model: object) -> str:
    """当模型尺寸未能导入时，在图纸上写入总体尺寸(长宽高)兜底注释。

    返回实际写入图纸的总体尺寸文本(单行, 供卡片回显)，未写入返回空串。
    坐标放在图纸右下 (0.18, 0.02) 米，避开左下角技术要求文本框。
    """
    text = _build_bbox_dims_text(part_model)
    if not text:
        return ""
    try:
        draw_model.ActivateSheet(draw_model.GetCurrentSheet().GetName())
    except Exception:
        pass
    note = None
    try:
        note = draw_model.InsertNote(text)
    except Exception:
        note = None
    if note is None:
        return ""
    try:
        ann = note.GetAnnotation()
        if ann is not None:
            ann.SetPosition(0.18, 0.02, 0.0)
    except Exception:
        pass
    l, w, h = _get_part_bbox_dims_mm(part_model)
    return f"总长{_fmt_mm(l)}×总宽{_fmt_mm(w)}×总高{_fmt_mm(h)}mm"


def _drawing_has_tech_requirements(draw_model: object) -> bool:
    """检测图纸(含模板/图框)是否已存在【技术要求】注释，存在返回 True。

    遍历所有视图(含图纸页视图)的 Note 注释，任一注释文本含"技术要求"即判定已有，
    避免在自带技术要求的企业模板上重复写入。任何异常都保守返回 False(不阻断写入)。
    """
    keys = ("技术要求", "技術要求", "TECHNICAL REQUIREMENT", "TECHNICAL REQUIREMENTS")

    def _text_hit(txt: object) -> bool:
        try:
            s = str(txt or "")
        except Exception:
            return False
        up = s.upper()
        return any(k in s or k in up for k in keys)

    try:
        view = draw_model.GetFirstView()
    except Exception:
        return False
    while view is not None:
        try:
            notes = view.GetNotes()
        except Exception:
            notes = None
        if notes:
            for note in notes:
                try:
                    if _text_hit(note.GetText()):
                        return True
                except Exception:
                    continue
        try:
            view = view.GetNextView()
        except Exception:
            break
    return False


def _insert_tech_requirements_note(draw_model: object, text: str) -> bool:
    """在工程图左下角(图框内)插入【技术要求】文本框注释。成功返回 True。

    优先激活图纸页视图后用 IModelDocExtension/ISketchManager 无关的 InsertNote；
    不同版本 InsertNote 签名有差异，做多重兜底：
      1) draw_model.InsertNote(text) 返回 Note 对象，再 SetTextFormat/定位；
      2) 失败则忽略(不阻断出图)。
    坐标单位为米(SolidWorks 内部)，放在图纸左下 (0.02, 0.02) 附近。
    """
    if not text:
        return False
    # 先确保当前激活的是图纸而非某个视图，注释才落在图纸空间
    try:
        draw_model.ActivateSheet(draw_model.GetCurrentSheet().GetName())
    except Exception:
        pass

    note = None
    try:
        note = draw_model.InsertNote(text)
    except Exception:
        note = None
    if note is None:
        return False

    # 定位到图纸左下角(米)。部分版本 note 有 GetAnnotation→SetPosition
    try:
        ann = note.GetAnnotation()
        if ann is not None:
            ann.SetPosition(0.02, 0.02, 0.0)
    except Exception:
        pass
    try:
        draw_model.EditRebuild3()
    except Exception:
        pass
    return True


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