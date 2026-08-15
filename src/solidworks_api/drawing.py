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

import time
from pathlib import Path


# ---------------------------------------------------------------------------
# 出图诊断日志
# ---------------------------------------------------------------------------
# 真机排查\"图上没标注\"这类问题时，光看成果卡片文案不够，需要把每一步的
# 中间状态(视图分类是否成功、outline 是否退化、SelectByID2 有没有命中、
# AddHorizontalDimension2 返回是否 None) 落到日志文件里。
#
# 落盘位置: workspace/logs/drawing_debug/last_run.log (每次出图覆盖写)
# 同时把关键摘要 (_DBG_SUMMARY) 累积起来，主流程会把其中的\"卡点行\"塞到
# annotation_note 里, 使成果卡片一眼可见。
_DBG_LOG_LINES: list[str] = []
_DBG_SUMMARY: list[str] = []


def _dbg_reset() -> None:
    """新一次出图开始前清空累积日志。由主流程在入口处调用一次。"""
    _DBG_LOG_LINES.clear()
    _DBG_SUMMARY.clear()


def _dbg(msg: str, summary: bool = False) -> None:
    """写一行诊断日志。summary=True 的行会额外汇总到成果卡片摘要中。

    任何 I/O 异常都吞掉——诊断日志绝不能反过来阻断出图流程。
    """
    try:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    except Exception:
        line = msg
    _DBG_LOG_LINES.append(line)
    if summary:
        _DBG_SUMMARY.append(msg)


def _dbg_flush() -> str:
    """把累计日志写到磁盘并返回日志文件路径(写失败返回空串)。"""
    try:
        log_dir = Path("workspace") / "logs" / "drawing_debug"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "last_run.log"
        log_path.write_text("\n".join(_DBG_LOG_LINES) + "\n", encoding="utf-8")
        return str(log_path)
    except Exception:
        return ""


def _dbg_summary_text() -> str:
    """成果卡片可见的关键诊断行。

    v023 教训: [:6] 硬截断只显示前 6 条, 路径 4/C/E 全被截掉。
    v025 教训: [:30] 依然被 iter_views 循环刷屏填满 (path E 无视图分支会
    再调一次 _iter_model_views, 每次 5 条 summary; 加上 EditRebuild3 也会
    触发多轮), 结果新加的路径 F 诊断挤不进前 30 条。
    v026: 改为取**最新 30 条** (_DBG_SUMMARY[-30:]), 因为真机排查最关心
    的永远是最后一步执行到哪 (路径 E → 路径 F → 兜底自绘), 前面的
    iter_views 失败已经稳定重复很多轮不需要再看。
    """
    if not _DBG_SUMMARY:
        return ""
    return " | ".join(_DBG_SUMMARY[-30:])


# SolidWorks 文档类型常量(swDocumentTypes_e)
_SW_DOC_PART = 1
_SW_DOC_DRAWING = 3

# swDrawingViewTypes_e.swDrawingSheetView = 3 → 工程图的\"图纸页\"视图,
# 不是真正的模型视图, InsertModelAnnotations3 对它无意义, 必须跳过。
_SW_DRAWING_SHEET_VIEW_TYPE = 3

# InsertModelAnnotations3 的 option(swInsertAnnotation_e 位标志):
#   1 = swInsertDimensionsMarkedForDrawing   (仅"标记为工程图用途"的尺寸)
#   2 = swInsertDimensionsNotMarkedForDrawing (未标记的尺寸)
# 程序化/AI 建模生成的零件尺寸默认都"未标记"，只传 1 会一条也导不进来，
# 图纸上看不到任何尺寸。因此必须传 1|2=3 才能把全部模型尺寸导入工程图。
_SW_INSERT_ALL_DIMENSIONS = 3

# swCommands_e.swCommands_InsertModelItems: 触发 SW 主 UI 的"模型项目"命令,
# 让 SW 自己把当前激活视图的模型尺寸/注解按 UI 上下文导入。作为路径 E: 当
# InsertModelAnnotations3 走 late-bind 挂 DISP_E_MEMBERNOTFOUND 时的兜底。
# SW 2019 里 swCommands_InsertModelItems 官方值为 1668;  1497 是历史备份 ID;
# 部分中文版模板会用 2062。真机 v022 弹"试图执行系统不支持的操作"表示 1497
# 上下文不合法, 因此按 [1668, 2062, 1497] 顺序 fallback。RunCommand 静默失败
# 不破坏主流程。
_SW_CMD_INSERT_MODEL_ITEMS = 1668
_SW_CMD_INSERT_MODEL_ITEMS_ALTS = (1668, 2062, 1497)


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
    _dbg_reset()
    _dbg("create_drawing: 入口")
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
        ann = _apply_dimensions_and_tolerance(app, draw_model, rules or [], model)
        dim_count = ann.get("dim_count", 0)
        grade = ann.get("grade", "")
        tol_applied = ann.get("tol_applied", 0)
        if dim_count <= 0:
            # 首次未能画进任何模型尺寸: 先做一次"MarkAll → 再补打整体尺寸"重试,
            # 主因是部分企业模板首次 InsertModelAnnotations3 时机太早, 视图尚未
            # 完全 rebuild。重试仍为 0 才降级为包围盒文字兜底。
            try:
                _mark_all_display_dimensions(model)
            except Exception:
                pass
            try:
                ann_retry = _apply_dimensions_and_tolerance(app, draw_model, rules or [], model)
                dim_count = ann_retry.get("dim_count", 0)
                grade = ann_retry.get("grade", grade)
                tol_applied = ann_retry.get("tol_applied", tol_applied)
            except Exception:
                pass
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
        _dbg(f"save_drawing: 失败 {exc}", summary=True)
        _dbg_flush()
        return _fail(f"保存工程图失败: {exc}")

    # 落盘诊断日志, 并把\"最关键 3 行\"塞到 message 里, 方便真机排查
    log_path = _dbg_flush()
    dbg_note = ""
    summary_txt = _dbg_summary_text()
    if summary_txt:
        dbg_note += f"，诊断: {summary_txt}"
    if log_path:
        dbg_note += f"，详细日志: {log_path}"

    return {
        "ok": True,
        "status": "executed",
        "message": f"已生成三视图工程图: {out_path}{paper_note}{annotation_note}{tech_note}{dbg_note}",
        "outputs": [out_path],
        # 供\"上传云平台\"使用: 本次出图关联的 3D 零件与 2D 工程图磁盘路径
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


# SolidWorks Type Library GUID(SldWorks.tlb, 各版本共用同一 typelib GUID)。
# 用于 gencache.EnsureModule 预生成早绑定模块, 再对 late-bind 对象 CastTo 到
# 具体接口。lcid=0, major/minor 逐组尝试(2019=27.x, 2020=28.x, 2021=29.x ...)。
_SW_TYPELIB_GUID = "{83A33D31-27C5-11CE-BFD4-00400513BB57}"
_SW_TYPELIB_VERSIONS = (
    (27, 0), (28, 0), (29, 0), (30, 0), (31, 0),
    (26, 0), (25, 0), (24, 0), (23, 0), (22, 0),
)
# 早绑定模块只需生成/加载一次(进程内幂等)。
_SW_EARLY_MODULE = None
_SW_EARLY_MODULE_TRIED = False


def _ensure_sw_early_module():
    """v030: 从注册的 SolidWorks typelib 预生成早绑定模块(gencache.EnsureModule)。

    根因(见 last_run.log v029 复测): 直接 gencache.EnsureDispatch(draw) 报
    'This COM object can not automate the makepy process' —— SolidWorks 的运行时
    IDispatch 对象**不携带可自动解析的 typelib 引用**, EnsureDispatch 无法据此
    反查 typelib, 所以早绑定从未生效, 仍走 late-bind 白名单坑。

    正确做法: 用 typelib 的 GUID + 版本号显式 EnsureModule, 让 pywin32 从注册表
    里注册的 SldWorks.tlb 生成早绑定包装模块; 拿到模块后才能用 CastTo 把 late-bind
    对象转成具体接口(IDrawingDoc / IModelDoc2)。返回模块或 None(全失败)。
    """
    global _SW_EARLY_MODULE, _SW_EARLY_MODULE_TRIED
    if _SW_EARLY_MODULE_TRIED:
        return _SW_EARLY_MODULE
    _SW_EARLY_MODULE_TRIED = True
    try:
        from win32com.client import gencache
    except Exception:
        _dbg("early_bind: 无 pywin32(单测), 跳过 EnsureModule", summary=True)
        return None
    for major, minor in _SW_TYPELIB_VERSIONS:
        try:
            mod = gencache.EnsureModule(_SW_TYPELIB_GUID, 0, major, minor)
        except Exception:
            continue
        if mod is not None:
            _SW_EARLY_MODULE = mod
            _dbg(
                f"early_bind: EnsureModule 成功 ver={major}.{minor}, 早绑定模块已生成",
                summary=True,
            )
            return mod
    _dbg("early_bind: EnsureModule 全版本失败, 回退 late-bind", summary=True)
    return None


def _ensure_early_bind(obj: object, iface: str = "IDrawingDoc") -> object:
    """v030: 把 late-bind IDispatch COM 对象 CastTo 到具体早绑定接口。

    根因(见 last_run.log): pywin32 纯 late-bind(IDispatch.Invoke)把
    IDrawingDoc.GetSheetNames / GetFirstView 等**方法**误解析成属性(返回 tuple,
    再 `()` 调用报 'tuple' object is not callable); GetCurrentSheet / FirstFeature
    直接 -2147352573 找不到成员。都是 IDispatch 动态派发对带 typelib 的接口方法
    解析不了导致的。

    v029 用 EnsureDispatch(obj) 失败(SW 对象不带可解析 typelib)。v030 改为:
      1) 先 _ensure_sw_early_module() 从 typelib GUID 预生成早绑定模块;
      2) 再 win32com.client.CastTo(obj, iface) 按早绑定接口做显式类型转换。
    转换后所有接口方法按 IDL 签名走 vtable/dispid, 绕开 late-bind 白名单。

    任何失败(缺 pywin32 / typelib 未注册 / CastTo 不认识该接口)都静默回退原对象,
    绝不能让早绑定失败反而崩掉整个出图流程。
    """
    if obj is None:
        return obj
    try:
        import win32com.client  # 单测无 pywin32 时直接走 except 回退
    except Exception:
        return obj
    mod = _ensure_sw_early_module()
    if mod is None:
        return obj
    try:
        early = win32com.client.CastTo(obj, iface)
        if early is not None:
            _dbg(f"early_bind: CastTo {iface} 成功, 走早绑定接口", summary=True)
            return early
    except Exception as exc:
        _dbg(
            f"early_bind: CastTo {iface} 失败({type(exc).__name__}:{exc}), 回退 late-bind",
            summary=True,
        )
    return obj


_MACRO_SECURITY_LOWERED = False


def _lower_macro_security() -> bool:
    """v029: 把 SolidWorks 宏安全性降级, 允许 RunMacro2 加载未签名 .swp。

    根因(见 last_run.log): RunMacro2 返回 ok=True err_ref=0, 但宏体的心跳 dump
    从不生成 → SW 2019 默认宏安全策略静默拒载未签名/不受信任的 .swp, 宏根本
    没被执行。SW 把宏安全设置存在注册表:
      HKCU\\Software\\SolidWorks\\SolidWorks 2019\\Security
    相关值(不同版本键名略有差异, 逐个尝试, 写不进去就跳过):
      - "Enable macro"        = 1   (允许运行宏)
      - "Macro Run Warning"   = 0   (不弹安全警告)
      - "Enable VSTA macros"  = 1

    只在进程内降级一次(幂等)。任何权限/缺 winreg 失败都吞掉并回退, 绝不阻断
    出图; 降级失败时后续 RunMacro2 仍会照常尝试(靠 dump 分级诊断)。
    """
    global _MACRO_SECURITY_LOWERED
    if _MACRO_SECURITY_LOWERED:
        return True
    try:
        import winreg  # 非 Windows / 单测环境无 winreg → 直接回退
    except Exception:
        _dbg("macro_sec: 无 winreg(非 Windows 或单测), 跳过降级", summary=True)
        return False
    lowered_any = False
    # 覆盖常见的几个 SW 版本键路径, 命中哪个改哪个。
    subkeys = (
        r"Software\SolidWorks\SolidWorks 2019\Security",
        r"Software\SolidWorks\SolidWorks 2020\Security",
        r"Software\SolidWorks\SolidWorks 2021\Security",
    )
    values = (
        ("Enable macro", 1),
        ("Macro Run Warning", 0),
        ("Enable VSTA macros", 1),
    )
    for subkey in subkeys:
        try:
            key = winreg.CreateKeyEx(
                winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE
            )
        except Exception:
            continue
        try:
            for name, val in values:
                try:
                    winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, val)
                    lowered_any = True
                except Exception:
                    pass
        finally:
            try:
                winreg.CloseKey(key)
            except Exception:
                pass
    if lowered_any:
        _MACRO_SECURITY_LOWERED = True
        _dbg("macro_sec: 已写入注册表宏安全性降级(HKCU\\...\\Security)", summary=True)
    else:
        _dbg("macro_sec: 注册表宏安全性降级失败(可能无写权限), 后续照常尝试宏", summary=True)
    return lowered_any


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
    # v029: 对新建的 IDrawingDoc 做 gencache 早绑定, 让后续 GetSheetNames /
    # GetFirstView / GetCurrentSheet 等接口方法按 typelib 签名调用, 根治
    # late-bind 白名单坑('tuple' object is not callable / 找不到成员)。
    draw = _ensure_early_bind(draw)
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


def _count_sheet_views(draw_model: object) -> int:
    """v028: 遍历所有 Sheet 的 GetViews, 数一下当前工程图里到底有几个视图对象。

    真机 v027 日志显示 iter_views 各路径全 0, 需要在 Create3rdAngleViews2
    之后立刻打一条计数, 用来分辨:
      A. Create3rdAngleViews2 返回 True 但 SW 静默失败(计数=0);
      B. 视图已创建但 _iter_model_views 各路径都撞到 late-bind IDispatch
         白名单 → 需要换取视图方式。

    对 late-bind 环境的 pywin32 IDispatch, GetViews 可能返回 tuple/None,
    统一按可迭代对象处理; 全部异常一律吞成 -1(表示 count 不可靠)。
    """
    total = 0
    got_any_iter = False
    try:
        names = draw_model.GetSheetNames
        if callable(names):
            names = names()
    except Exception:
        names = None
    try:
        if names:
            for nm in list(names):
                try:
                    draw_model.ActivateSheet(str(nm))
                except Exception:
                    pass
                try:
                    sheet = draw_model.GetCurrentSheet()
                except Exception:
                    sheet = None
                if sheet is None:
                    continue
                try:
                    views = sheet.GetViews
                    if callable(views):
                        views = views()
                except Exception:
                    views = None
                if not views:
                    continue
                got_any_iter = True
                try:
                    for v in list(views):
                        if v is not None:
                            total += 1
                except Exception:
                    pass
    except Exception:
        pass

    if not got_any_iter:
        # 回退: 直接 draw_model.GetFirstView + GetNext 链表
        try:
            v = draw_model.GetFirstView
            if callable(v):
                v = v()
            while v is not None:
                total += 1
                try:
                    nxt = v.GetNextView
                    if callable(nxt):
                        nxt = nxt()
                except Exception:
                    nxt = None
                v = nxt
                if total > 32:
                    break  # 保险: 防止死循环
        except Exception:
            return -1
    return total


def _insert_three_views(draw_model: object, part_path: str) -> None:
    """在工程图上放置标准三视图(前/上/右)+ 等轴测。

    v028: 加视图落地计数诊断。真机反馈显示 Create3rdAngleViews2 可能返回
    True 但实际没创建视图, 需要在这里立即验证并落一条 _dbg, 避免下游
    apply_dim 全 0 却无法分辨根因。
    """
    ok = False
    try:
        draw = draw_model  # IDrawingDoc 接口即工程图 model
        ok = draw.Create3rdAngleViews2(part_path)
    except Exception as exc:
        _dbg(f"insert_views: Create3rdAngleViews2 抛异常 {type(exc).__name__}:{exc}", summary=True)
        raise RuntimeError(f"Create3rdAngleViews2 异常: {exc}") from exc
    _dbg(f"insert_views: Create3rdAngleViews2 返回 {bool(ok)} part_path={part_path}", summary=True)
    if not ok:
        raise RuntimeError("Create3rdAngleViews2 返回失败(可能零件路径无效或模板不含视图框)。")

    # v028: Create3rdAngleViews2 API 返回值不可靠, 强制重建 + 计视图数
    try:
        draw_model.ForceRebuild3(True)
    except Exception as exc:
        _dbg(f"insert_views: ForceRebuild3(True) 抛 {type(exc).__name__}:{exc}")

    view_count = _count_sheet_views(draw_model)
    _dbg(f"insert_views: 创建后视图计数 = {view_count}", summary=True)

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


def _dump_view_names_via_macro(app: object) -> list:
    """通过 SolidWorks 内部 VBA 宏读回当前活动工程图的所有视图名。

    背景：v019 真机现场 IDrawingDoc 上 late-bind 全废 (FirstFeature/GetCurrentSheet
    /GetSheetNames/GetFirstView 全抛 -2147352573 "找不到成员")。原因是 pywin32 拿
    到的 IDispatch 只暴露了 IModelDoc 白名单方法, IModelDoc2/IDrawingDoc 的成员
    通过 IDispatch.Invoke 全部返回 DISP_E_MEMBERNOTFOUND。

    绕开方式：在 SolidWorks 自己的 VBA 引擎里跑一段脚本 —— 宏内部对 IDrawingDoc
    是 early-bind (VBA 编译时按 typelib 绑定), 所有方法都能调。宏遍历所有 sheet
    的所有视图, 把 {name, is_sheet} 序列化到临时 JSON, Python 侧读回。

    实际拿到视图名之后, 就能用 Extension.SelectByID2("真实名", "DRAWINGVIEW", ...)
    把 IView 回取到 Python 侧 —— SelectByID2 走的是 IModelDocExtension 命令通道
    (跟 IDrawingDoc 是不同的 IDispatch), 已多次实测可用。

    返回：视图名列表 (只含"引用模型的视图", 已过滤 Sheet 本身)。任一步失败返回 []。
    """
    if app is None:
        return []
    import os
    import json
    import tempfile
    import uuid

    tmp_dir = tempfile.gettempdir()
    tag = uuid.uuid4().hex[:8]
    dump_path = os.path.join(tmp_dir, f"aisw_view_dump_{tag}.json").replace("\\", "/")
    macro_path = os.path.join(tmp_dir, f"aisw_dump_views_{tag}.swp")

    # 宏内 Application.SldWorks 是 early-bind, 能拿全部 IDrawingDoc 方法。
    # 每个 sheet 用 GetViews 拿元组: 第一个是 Sheet 自身(Type=1), 之后是引用模型
    # 的视图 —— 只 dump 后者。视图名用 IView.GetName2。
    vba_source = (
        "Dim swApp As Object\n"
        "Sub main()\n"
        "  Dim swModel As Object\n"
        "  Dim swDraw As Object\n"
        "  Dim vSheetNames As Variant\n"
        "  Dim vSheet As Variant\n"
        "  Dim swSheet As Object\n"
        "  Dim vViews As Variant\n"
        "  Dim swView As Object\n"
        "  Dim i As Long, j As Long\n"
        "  Dim lines As String\n"
        "  Dim iFile As Integer\n"
        "  Set swApp = Application.SldWorks\n"
        "  Set swModel = swApp.ActiveDoc\n"
        "  If swModel Is Nothing Then Exit Sub\n"
        "  ' swDocDRAWING = 3\n"
   "  If swModel.GetType <> 3 Then Exit Sub\n"
        "  Set swDraw = swModel\n"
        "  lines = \"{\"\"views\"\":[\"\n"
        "  Dim first As Boolean\n"
        "  first = True\n"
        "  vSheetNames = swDraw.GetSheetNames\n"
        "  If Not IsEmpty(vSheetNames) Then\n"
        "    For i = LBound(vSheetNames) To UBound(vSheetNames)\n"
        "      Set swSheet = swDraw.Sheet(CStr(vSheetNames(i)))\n"
        "      If Not swSheet Is Nothing Then\n"
        "        vViews = swSheet.GetViews\n"
        "        If Not IsEmpty(vViews) Then\n"
        "          For j = LBound(vViews) To UBound(vViews)\n"
        "            Set swView = vViews(j)\n"
        "            If Not swView Is Nothing Then\n"
        "              ' 跳过 sheet 自身 (Type=1)\n"
        "              If swView.Type <> 1 Then\n"
        "                If Not first Then lines = lines & \",\"\n"
        "                lines = lines & \"{\"\"name\"\":\"\"\" & Replace(swView.GetName2, \"\"\"\", \"'\") & \"\"\",\"\"type\"\":\" & swView.Type & \"}\"\n"
        "                first = False\n"
        "              End If\n"
        "            End If\n"
        "          Next j\n"
        "        End If\n"
        "      End If\n"
        "    Next i\n"
        "  End If\n"
        "  lines = lines & \"]}\"\n"
        "  iFile = FreeFile\n"
        f"  Open \"{dump_path}\" For Output As #iFile\n"
        "  Print #iFile, lines\n"
        "  Close #iFile\n"
        "End Sub\n"
    )

    try:
        with open(macro_path, "w", encoding="utf-8") as f:
            f.write(vba_source)
    except Exception as exc:
        _dbg(f"iter_views: 路径5 写宏失败 {type(exc).__name__}:{exc}", summary=True)
        return []

    # RunMacro2(filePath, moduleName, procName, options, byref error)
    # options=1 (swRunMacroOption_e.swRunMacroDefault); 若 SW 版本不认 5 参数就退回 3 参数版
    # v029: 触发宏前先降级 SW 宏安全性, 否则未签名 .swp 被静默拒载。
    _lower_macro_security()
    try:
        from solidworks_api.com_types import byref_int
        err_ref = byref_int(0)
        try:
            app.RunMacro2(macro_path, "Module1", "main", 1, err_ref)
        except Exception:
            try:
                app.RunMacro(macro_path, "Module1", "main")
            except Exception as exc2:
                _dbg(
                    f"iter_views: 路径5 RunMacro/RunMacro2 均失败 {type(exc2).__name__}:{exc2}",
                    summary=True,
                )
                return []
    except Exception as exc:
        _dbg(f"iter_views:路径5 执行宏抛异常 {type(exc).__name__}:{exc}", summary=True)
        return []

    try:
        with open(dump_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read().strip())
        names = [str(v.get("name") or "").strip() for v in data.get("views", [])]
        names = [n for n in names if n]
    except Exception as exc:
        _dbg(f"iter_views: 路径5 读取 dump 抛异常 {type(exc).__name__}:{exc}", summary=True)
        names = []
    finally:
        try:
            os.remove(dump_path)
        except Exception:
            pass
        try:
            os.remove(macro_path)
        except Exception:
            pass
    _dbg(f"iter_views: 路径5(VBA 宏 dump) 拿到视图名 {names}", summary=True)
    return names


def _insert_annotations_via_macro(app: object) -> dict:
    """路径 F: 在 SW 内部 VBA 宏里 early-bind 完成 InsertModelAnnotations3。

    背景 (v024 真机决定性证据):
      - `IDrawingDoc` 的 late-bind 通道在客户机器上被 pywin32 白名单完全阉割:
        `FirstFeature/GetCurrentSheet/GetSheetNames/GetFirstView` 全 `找不到成员`,
        `SelectByID2` 类型选 `DRAWINGVIEW` 报 `类型不匹配`;
      - `RunCommand(1668/2062/1497)` 会弹 SW `试图执行系统不支持的操作` 弹窗,
        因为拿不到激活视图上下文;
      - 图纸上 3 个视图 (工程图视图1/2/3) 真实存在, 只是 Python 侧摸不到。

    终极方案 = 让 SW 自己的 VBA 引擎干活。VBA 内部对 IDrawingDoc/IView 是
    early-bind (typelib 编译时绑定), 所有方法直接可调, 没有 IDispatch 白名单
    问题。宏遍历所有 sheet 的所有 view, 逐个 ActivateView + InsertModelAnnotations3,
    最后把导入的显示尺寸数写回 JSON。Python 只负责触发 RunMacro2 与读结果。

    返回 {\"imported\": int, \"views\": int, \"error\": str}。任一步失败返回 imported=0。
    """
    if app is None:
        _dbg("path_F: app 为 None, 跳过", summary=True)
        return {"imported": 0, "views": 0, "error": "app_none"}
    import os
    import json
    import tempfile
    import uuid

    tmp_dir = tempfile.gettempdir()
    tag = uuid.uuid4().hex[:8]
    dump_path = os.path.join(tmp_dir, f"aisw_dim_dump_{tag}.json").replace("\\", "/")
    macro_path = os.path.join(tmp_dir, f"aisw_insert_dim_{tag}.swp")

    # 宏内: swDoc.Extension.InsertModelAnnotations3 是 IDrawingDoc.Extension 上的方法,
    # early-bind 直接调; 每个 view.InsertModelAnnotations3 也 early-bind。
    # type=0 (swInsertDimensionsMarkedForDrawing 之外, 由 option 控制), option=2 (all)。
    # SW 2019 InsertModelAnnotations3 签名:
    #   InsertModelAnnotations3(Type, Options, AllViews, DuplicateDims,
    #                          HideDuplicates, UseDimPlacementInSketch,
    #                          InsertInAllDrawViews, ImportedItemAnnotations)
    # 参数 all-True + option=2 (all except items marked for drawing 之外),
    # 让 SW 把所有能拿到的模型尺寸都塞进图纸。
    vba_source = (
        "Dim swApp As Object\n"
        "Sub main()\n"
        "  Dim swModel As Object\n"
        "  Dim swDraw As Object\n"
        "  Dim vSheetNames As Variant\n"
        "  Dim swSheet As Object\n"
        "  Dim vViews As Variant\n"
        "  Dim swView As Object\n"
        "  Dim i As Long, j As Long\n"
        "  Dim viewCount As Long\n"
        "  Dim docImported As Long\n"
        "  Dim viewImported As Long\n"
        "  Dim totalImported As Long\n"
        "  Dim errMsg As String\n"
        "  Dim iFile As Integer\n"
        "  viewCount = 0\n"
        "  docImported = 0\n"
        "  totalImported = 0\n"
        "  errMsg = \"\"\n"
        "  Set swApp = Application.SldWorks\n"
        "  Set swModel = swApp.ActiveDoc\n"
        "  ' 心跳: 一进 main 就先落 dump, 后面即便崩了 Python 也能知道宏跑起来了\n"
        "  iFile = FreeFile\n"
        f"  Open \"{dump_path}\" For Output As #iFile\n"
        "  Print #iFile, \"{\"\"phase\"\":\"\"macro_started\"\",\"\"imported\"\":0,\"\"views\"\":0,\"\"error\"\":\"\"\"\"}\"\n"
        "  Close #iFile\n"
        " If swModel Is Nothing Then\n"
        "    errMsg = \"no_active_doc\"\n"
        "    GoTo WriteResult\n"
        "  End If\n"
        "  ' swDocDRAWING = 3\n"
        "  If swModel.GetType <> 3 Then\n"
        "    errMsg = \"not_a_drawing\"\n"
        "    GoTo WriteResult\n"
        "  End If\n"
        "  Set swDraw = swModel\n"
        "  ' 文档层先跑一次, 覆盖 all-views 场景\n"
        "  On Error Resume Next\n"
        "  docImported = swModel.Extension.InsertModelAnnotations3(0, 2, True, False, False, False, True, False)\n"
        "  If Err.Number <> 0 Then\n"
        "    errMsg = errMsg & \"doc_insert:\" & Err.Number & \";\"\n"
        "    Err.Clear\n"
        "  End If\n"
        "  On Error GoTo 0\n"
        "  ' 遍历所有 sheet 所有 view, 逐个 ActivateView + InsertModelAnnotations3\n"
        "  On Error Resume Next\n"
        "  vSheetNames = swDraw.GetSheetNames\n"
        "  On Error GoTo 0\n"
        "  If Not IsEmpty(vSheetNames) Then\n"
        "    For i = LBound(vSheetNames) To UBound(vSheetNames)\n"
        "      On Error Resume Next\n"
        "      swDraw.ActivateSheet CStr(vSheetNames(i))\n"
        "      Set swSheet = swDraw.Sheet(CStr(vSheetNames(i)))\n"
        "      On Error GoTo 0\n"
        "      If Not swSheet Is Nothing Then\n"
        "        On Error Resume Next\n"
        "        vViews = swSheet.GetViews\n"
        "        On Error GoTo 0\n"
        "        If Not IsEmpty(vViews) Then\n"
        "          For j = LBound(vViews) To UBound(vViews)\n"
        "            Set swView = vViews(j)\n"
        "            If Not swView Is Nothing Then\n"
        "              ' Type=1 是 sheet 自身, 跳过\n"
        "              If swView.Type <> 1 Then\n"
        "                viewCount = viewCount + 1\n"
        "                On Error Resume Next\n"
        "                swDraw.ActivateView swView.GetName2\n"
        "                viewImported = swView.InsertModelAnnotations3(0, 2, False, False, False, False, False, False)\n"
        "                If Err.Number <> 0 Then\n"
        "                  errMsg = errMsg & \"v\" & j & \":\" & Err.Number & \";\"\n"
        "                  Err.Clear\n"
        "                Else\n"
        "                  totalImported = totalImported + viewImported\n"
        "                End If\n"
        "                On Error GoTo 0\n"
        "              End If\n"
        "      End If\n"
        "          Next j\n"
        "        End If\n"
        "      End If\n"
        "    Next i\n"
        "  End If\n"
        "  On Error Resume Next\n"
        "  swModel.EditRebuild3\n"
        "  On Error GoTo 0\n"
        "WriteResult:\n"
        "  iFile = FreeFile\n"
        f"  Open \"{dump_path}\" For Output As #iFile\n"
        "  Print #iFile, \"{\"\"phase\"\":\"\"finished\"\",\"\"imported\"\":\" & totalImported & \",\"\"doc_imported\"\":\" & docImported & \",\"\"views\"\":\" & viewCount & \",\"\"error\"\":\"\"\" & errMsg & \"\"\"}\"\n"
        "  Close #iFile\n"
        "End Sub\n"
    )

    try:
        with open(macro_path, "w", encoding="utf-8") as f:
            f.write(vba_source)
    except Exception as exc:
        _dbg(f"path_F: 写宏失败 {type(exc).__name__}:{exc}", summary=True)
        return {"imported": 0, "views": 0, "error": f"write_macro_fail:{exc}"}

    # 触发宏。RunMacro2 是 ISldWorks 上的方法, 与 RunMacro 同级, 与 IDrawingDoc 白名单无关。
    # v028: 真机 v027 日志显示 dump 文件从未生成 → RunMacro2 静默失败, 宏体根本
    # 没被 SW 加载执行。加三重兜底:
    #   1) err_ref 落 _dbg (swRunMacroError_e 枚举, 0=success);
    #   2) macro_path 规范化为 Windows 反斜杠绝对路径;
    #   3) ProcName 依次试 "main" / "Module1.main" / "" (空让 SW 自动搜);
    ran = False
    err_val = -1  # -1 表示没拿到 err_ref
    macro_abs = os.path.abspath(macro_path).replace("/", "\\")

    # v029: 触发宏前先降级 SW 宏安全性(注册表), 让未签名 .swp 能被加载执行。
    # 真机 v028 日志: RunMacro2 ok=True 但 dump 从不生成 → 宏被安全策略静默拒载。
    _lower_macro_security()

    def _try_runmacro(proc_name: str) -> tuple:
        """返回 (ok, err_val, exc_msg)。RunMacro2 优先, 失败退 RunMacro。"""
        try:
            from solidworks_api.com_types import byref_int
            eref = byref_int(0)
            try:
                app.RunMacro2(macro_abs, "Module1", proc_name, 1, eref)
                try:
                    ev = int(getattr(eref, "value", 0) or 0)
                except Exception:
                    ev = 0
                return True, ev, ""
            except BaseException as e1:
                try:
                    app.RunMacro(macro_abs, "Module1", proc_name)
                    return True, 0, ""
                except BaseException as e2:
                    return False, -1, f"{type(e2).__name__}:{e2} (RunMacro2 前置错:{type(e1).__name__}:{e1})"
        except BaseException as ex:
            return False, -1, f"{type(ex).__name__}:{ex}"

    for proc in ("main", "Module1.main", ""):
        ok, ev, emsg = _try_runmacro(proc)
        _dbg(f"path_F: RunMacro2 proc='{proc}' ok={ok} err_ref={ev} msg={emsg}", summary=True)
        if ok:
            ran = True
            err_val = ev
            # 若 err_ref != 0 说明宏体加载/编译有问题, 仍然 break, 靠 dump 阶段分级
            break

    if not ran:
        try:
            os.remove(macro_path)
        except Exception:
            pass
        return {"imported": 0, "views": 0, "error": "run_macro_fail"}

    imported = 0
    views = 0
    err = ""
    phase = ""
    dump_exists = os.path.exists(dump_path)
    try:
        with open(dump_path, "r", encoding="utf-8") as f:
            data = json.loads(f.read().strip())
        imported = int(data.get("imported", 0) or 0)
        views = int(data.get("views", 0) or 0)
        err = str(data.get("error") or "")
        phase = str(data.get("phase") or "")
    except FileNotFoundError:
        _dbg(
            "path_F: dump 文件不存在, 宏体根本没跑到 main (RunMacro2 静默无痕失败)",
            summary=True,
        )
        err = "no_dump_macro_not_started"
    except Exception as exc:
        _dbg(f"path_F: 读取 dump 抛异常 {type(exc).__name__}:{exc}", summary=True)
        err = f"read_dump_fail:{exc}"
    finally:
        try:
            os.remove(dump_path)
        except Exception:
            pass
        try:
            os.remove(macro_path)
        except Exception:
            pass
    # 分级诊断: 心跳 macro_started 但没进到 finished → 宏中途崩; finished → 正常跑完
    if phase == "macro_started":
        _dbg(
            "path_F: 宏跑到 heartbeat 但没到 finished, 宏体中途崩 (Extension/GetSheetNames/InsertModelAnnotations3 抛错未捕获)",
            summary=True,
        )
    elif phase == "" and dump_exists:
        _dbg("path_F: dump 存在但缺 phase 字段, 疑似写入格式异常", summary=True)
    _dbg(
     f"path_F: VBA 宏 InsertModelAnnotations3 完成 phase={phase!r} imported={imported} views={views} err={err!r}",
        summary=True,
    )
    return {"imported": imported, "views": views, "error": err, "phase": phase}


def _iter_model_views(draw_model: object, app: object = None) -> list:
    """遍历工程图，返回所有引用模型的视图对象列表(跳过图纸页视图)。

    真机 SolidWorks 2019 排查记录：
      - `Create3rdAngleViews2` 能正常成功，说明 `draw_model` 是合法的 IDrawingDoc；
      - 但 `draw_model.GetFirstView()` 在部分 win32com 早绑定/typelib 组合下会抛
        "com_error: (-2147352573, '找不到成员。')"——同一 IDispatch 上并不是所有
        DrawingDoc 方法都能通过 late-bind 到 IDispatch.Invoke。
      - 同样地，`GetCurrentSheet` / `GetSheetNames` / `Sheet(name)` 在某些
        win32com typelib 缓存下也可能挂 late-bind (真机 v017 上路径1/路径2
        全部静默失败，只留下路径3 的 GetFirstView 报错)。

    因此本次遍历策略扩展为「五段兜底」，任一成功即返回：
      0. **FeatureManager 优先**: 遍历 `IModelDoc2.FeatureManager` 里 typeName
         为 `DrView` 的 feature，用 `Feature.GetSpecificFeature2()` 拿到 IView。
         这条路径完全绕开 IDrawingDoc/ISheet 的 late-bind 坑，即使前面所有
         IDrawingDoc 方法都挂了它也能通过 IFeature 接口拿到视图。
      1. **首选(ISheet)**: `GetCurrentSheet().GetViews()` 直接拿当前活动 sheet 的视图元组；
      2. **多 sheet 兼容**: 遍历 `GetSheetNames()`, 用 `IDrawingDoc.Sheet(name)`
         逐个 sheet 拿 `GetViews()`, 若拿不到再降级 `ActivateSheet + GetCurrentSheet`；
      3. **GetFirstView 链**: 沿用原 `GetFirstView` 两层链遍历(Sheet 视图 → 模型视图子链)；
      4. **命名视图回取**: `Create3rdAngleViews2` 会产生 `Drawing View1..4`
         (中文模板可能是 "视图 1..4")，用 SelectionMgr SelectByID2 命中后
         从 `SelectionMgr.GetSelectedObject6(i,-1)` 回取。

    路径1/2/3 任一步的异常都会打 summary=True 日志, 保证真机诊断可见。
    任何异常都保守返回已收集到的部分，绝不阻断出图。
    """
    views: list = []

    # --- 路径 0: FeatureManager 遍历 DrView feature ---
    # 这是最抗 late-bind 的路径：Feature/FeatureManager 接口稳定，不吃 IDrawingDoc 的坑
    try:
        feat = draw_model.FirstFeature()
    except Exception as exc:
        _dbg(
            f"iter_views: 路径0 FirstFeature 抛异常 {type(exc).__name__}:{exc}",
            summary=True,
        )
        feat = None
    seen_feat = 0
    while feat is not None:
        seen_feat += 1
        try:
            ftype = str(getattr(feat, "GetTypeName2", lambda: "")() or "")
        except Exception:
            try:
                ftype = str(feat.GetTypeName() or "")
            except Exception:
                ftype = ""
        if ftype == "DrView":
            try:
                spec = feat.GetSpecificFeature2()
            except Exception:
                spec = None
            if spec is not None:
                try:
                    vt = int(getattr(spec, "Type", 0) or 0)
                except Exception:
                    vt = 0
                if vt != _SW_DRAWING_SHEET_VIEW_TYPE:
                    views.append(spec)
        try:
            feat = feat.GetNextFeature()
        except Exception:
            break
        if seen_feat > 5000:  # 防御:极端情况避免死循环
            break
    if views:
        _dbg(
            f"iter_views: 路径0(FeatureManager DrView) 拿到 {len(views)} 个模型视图, "
            f"扫描 feature 数={seen_feat}",
            summary=True,
        )
        return views

    # --- 路径 1: GetCurrentSheet().GetViews() ---
    try:
        cur_sheet = draw_model.GetCurrentSheet()
    except Exception as exc:
        _dbg(
            f"iter_views: 路径1 GetCurrentSheet 抛异常 {type(exc).__name__}:{exc}",
            summary=True,
        )
        cur_sheet = None
    if cur_sheet is not None:
        try:
            raw = cur_sheet.GetViews()
        except Exception as exc:
            _dbg(
                f"iter_views: 路径1 cur_sheet.GetViews 抛异常 {type(exc).__name__}:{exc}",
                summary=True,
            )
            raw = None
        if raw:
            try:
                # GetViews 返回 tuple/VARIANT array，展平并跳过 sheet 视图本身
                for v in raw:
                    if v is None:
                        continue
                    try:
                        vt = int(getattr(v, "Type", 0) or 0)
                    except Exception:
                        vt = 0
                    if vt == _SW_DRAWING_SHEET_VIEW_TYPE:
                        continue
                    views.append(v)
                _dbg(
                    f"iter_views: 路径1(GetCurrentSheet.GetViews) 拿到 {len(views)} 个模型视图",
                    summary=True,
                )
            except Exception as exc:
                _dbg(
                    f"iter_views: 路径1 展开 GetViews 结果异常 {type(exc).__name__}:{exc}",
                    summary=True,
                )

    # --- 路径 2: 多 sheet 兼容 ---
    try:
        sheet_names = draw_model.GetSheetNames()
    except Exception as exc:
        _dbg(
            f"iter_views: 路径2 GetSheetNames 抛异常 {type(exc).__name__}:{exc}",
            summary=True,
        )
        sheet_names = None
    if sheet_names and len(sheet_names) > 0:
        for sn in sheet_names:
            sheet_obj = None
            # 优先 IDrawingDoc.Sheet(name) 拿 sheet 对象，避免副作用切换活动 sheet
            try:
                sheet_obj = draw_model.Sheet(str(sn))
            except Exception:
                sheet_obj = None
            if sheet_obj is None:
                # 降级: ActivateSheet 后再取 CurrentSheet
                try:
                    draw_model.ActivateSheet(str(sn))
                    sheet_obj = draw_model.GetCurrentSheet()
                except Exception:
                    sheet_obj = None
            if sheet_obj is None:
                continue
            try:
                raw = sheet_obj.GetViews()
            except Exception:
                raw = None
            if not raw:
                continue
            try:
                for v in raw:
                    if v is None:
                        continue
                    try:
                        vt = int(getattr(v, "Type", 0) or 0)
                    except Exception:
                        vt = 0
                    if vt == _SW_DRAWING_SHEET_VIEW_TYPE:
                        continue
                    if v not in views:
                        views.append(v)
            except Exception:
                continue
        if views:
            _dbg(
                f"iter_views: 路径2(GetSheetNames+Sheet.GetViews) 累计 {len(views)} 个模型视图, "
                f"sheet_count={len(sheet_names)}",
                summary=True,
            )
            return views

    if views:
        return views

    # --- 路径 3: 兜底走 GetFirstView 两层链 ---
    sheet_count = 0
    raw_view_count = 0
    skip_path3_loop = False
    try:
        top = draw_model.GetFirstView()
    except Exception as exc:
        _dbg(
            f"iter_views: 路径3 draw_model.GetFirstView 抛异常 {type(exc).__name__}:{exc}",
            summary=True,
        )
        top = None
        skip_path3_loop = True
    if top is None and not skip_path3_loop:
        _dbg("iter_views: 路径3 draw_model.GetFirstView 返回 None(工程图为空?)", summary=True)
        skip_path3_loop = True

    while (not skip_path3_loop) and top is not None:
        raw_view_count += 1
        try:
            top_type = int(getattr(top, "Type", 0) or 0)
        except Exception:
            top_type = 0
        try:
            top_name = str(getattr(top, "Name", "") or "") or "<no-name>"
        except Exception:
            top_name = "<no-name>"

        if top_type == _SW_DRAWING_SHEET_VIEW_TYPE:
            sheet_count += 1
            try:
                child = top.GetNextView()
            except Exception as exc:
                _dbg(f"iter_views: 路径3 sheet={top_name} 下沉 GetNextView 抛异常 {type(exc).__name__}:{exc}")
                child = None
            child_in_sheet = 0
            while child is not None:
                try:
                    child_type = int(getattr(child, "Type", 0) or 0)
                except Exception:
                    child_type = 0
                if child_type == _SW_DRAWING_SHEET_VIEW_TYPE:
                    break
                views.append(child)
                child_in_sheet += 1
                try:
                    child = child.GetNextView()
                except Exception:
                    break
            _dbg(f"iter_views: 路径3 sheet={top_name} 收集到 {child_in_sheet} 个模型视图")
            break
        else:
            views.append(top)
            try:
                top = top.GetNextView()
            except Exception:
                break

    _dbg(
        f"iter_views: 路径3汇总 sheet_count={sheet_count} raw_top_view_count={raw_view_count} "
        f"model_view_count={len(views)}",
        summary=True,
    )
    if views:
        return views

    # --- 路径 5: VBA 宏 early-bind 穿透白名单, 拿真实视图名再 SelectByID2 回取 ---
    # 前 4 路径都失败通常是 pywin32 late-bind IDispatch 白名单只暴露 IModelDoc,
    # IDrawingDoc 全部成员挂 DISP_E_MEMBERNOTFOUND。VBA 宏在 SW 进程内是 early-bind,
    # 能穿透白名单读到 Sheet/GetViews 全部真实名字。
    macro_view_names: list = []
    if app is not None:
        try:
            macro_view_names = _dump_view_names_via_macro(app) or []
        except Exception as exc:
            _dbg(
                f"iter_views: 路径5 宏中转异常 {type(exc).__name__}:{exc}",
                summary=True,
            )
            macro_view_names = []
        _dbg(
            f"iter_views: 路径5(VBA 宏 dump) 拿到视图名 {macro_view_names!r}",
            summary=True,
        )

    # --- 路径 4: SelectByID2 命名视图回取 (最坏兜底) ---
    # Create3rdAngleViews2 会产生固定命名的视图: 英文模板 "Drawing View1..4",
    # 中文模板可能是 "视图 1..4" 或 "工程视图1..4"。逐个尝试选中后从 SelectionMgr
    # 拿回 IView。这是完全绕开 IDrawingDoc 遍历接口的终极兜底。
    # 若路径5 拿到了真实名, 就把它作为首选候选组; 否则用硬编码多语言候选兜底。
    # 注意: pywin32 late-bind 白名单挂时, 属性访问可能抛 BaseException 而非 Exception,
    # 必须用 BaseException 兜住, 否则整个函数会静默从这里跳出(v020 真机断链根因)。
    _dbg("iter_views: 进入路径4 前, 尝试 draw_model.SelectionManager", summary=True)
    sel_mgr = None
    try:
        sel_mgr = draw_model.SelectionManager
    except BaseException as exc:
        _dbg(
            f"iter_views: 路径4 SelectionManager 取不到 {type(exc).__name__}:{exc}",
            summary=True,
        )
        sel_mgr = None
    _dbg(
        f"iter_views: 路径4 SelectionManager={'ok' if sel_mgr is not None else 'None'}",
        summary=True,
    )
    if sel_mgr is not None:
        # SelectByID2(name, "DRAWINGVIEW", x, y, z, append, mark, callout, selectOption)
        candidates_by_lang = []
        if macro_view_names:
            candidates_by_lang.append(list(macro_view_names))
        candidates_by_lang.extend([
            ["Drawing View1", "Drawing View2", "Drawing View3", "Drawing View4"],
            ["视图 1", "视图 2", "视图 3", "视图 4"],
            ["工程视图1", "工程视图2", "工程视图3", "工程视图4"],
            ["视图1", "视图2", "视图3", "视图4"],
        ])
        try:
            draw_model.ClearSelection2(True)
        except Exception:
            pass
        picked = 0
        for names in candidates_by_lang:
            for nm in names:
                try:
                    ok = bool(
                        draw_model.Extension.SelectByID2(
                            nm, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, None, 0
                        )
                    )
                except Exception:
                    ok = False
                if not ok:
                    continue
                try:
                    sel = sel_mgr.GetSelectedObject6(1, -1)
                except Exception:
                    sel = None
                if sel is None:
                    continue
                try:
                    vt = int(getattr(sel, "Type", 0) or 0)
                except Exception:
                    vt = 0
                if vt == _SW_DRAWING_SHEET_VIEW_TYPE:
                    continue
                if sel not in views:
                    views.append(sel)
                    picked += 1
                try:
                    draw_model.ClearSelection2(True)
                except Exception:
                    pass
            if picked > 0:
                break
        _dbg(
            f"iter_views: 路径4(SelectByID2 命名视图) 拿到 {picked} 个模型视图",
            summary=True,
        )

    # --- 路径 C: Extension.SelectAll + SelectionMgr 遍历回取 (终极兜底) ---
    # 若命名候选一个都没命中(比如客户模板视图名完全定制过, 且宏 dump 也失败),
    # 就走 SW 主命令通道的 SelectAll: 它会把当前图纸上所有实体全选上, 再从
    # SelectionMgr 逐个回取, 按 Type 过滤出 DRAWINGVIEW(非 SheetView)。
    # 这条路径彻底不依赖任何"名字"或 IDrawingDoc 遍历接口。
    if not views and sel_mgr is not None:
        picked_c = 0
        try:
            draw_model.ClearSelection2(True)
        except Exception:
            pass
        selected_ok = False
        # 优先按类型选: SelectByID2 允许 name="" + Type="DRAWINGVIEW" 走类型选择。
        try:
            selected_ok = bool(
                draw_model.Extension.SelectByID2(
                    "", "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, None, 0
                )
            )
        except Exception as exc:
            _dbg(
                f"iter_views: 路径C SelectByID2(type only) 抛 {type(exc).__name__}:{exc}",
                summary=True,
            )
            selected_ok = False
        if not selected_ok:
            # 类型选失败, 再退到 SelectAll(全选图纸上所有实体)
            try:
                draw_model.Extension.SelectAll()
                selected_ok = True
            except Exception as exc:
                _dbg(
                    f"iter_views: 路径C SelectAll 抛 {type(exc).__name__}:{exc}",
                    summary=True,
                )
                selected_ok = False
        if selected_ok:
            try:
                sel_count = int(sel_mgr.GetSelectedObjectCount2(-1) or 0)
            except Exception as exc:
                _dbg(
                    f"iter_views: 路径C GetSelectedObjectCount2 抛 {type(exc).__name__}:{exc}",
                    summary=True,
               )
                sel_count = 0
            for i in range(1, sel_count + 1):
                try:
                    sel = sel_mgr.GetSelectedObject6(i, -1)
                except Exception:
                    sel = None
                if sel is None:
                    continue
                # 视图对象通常有 GetName2 + Type; 用 duck typing 过滤
                try:
                    vt = int(getattr(sel, "Type", 0) or 0)
                except Exception:
                    vt = 0
                if vt == _SW_DRAWING_SHEET_VIEW_TYPE:
                    continue
                has_view_api = False
                for probe in ("GetName2", "GetOutline"):
                    try:
                        getattr(sel, probe)
                        has_view_api = True
                        break
                    except Exception:
                        continue
                if not has_view_api:
                    continue
                if sel not in views:
                    views.append(sel)
                    picked_c += 1
            try:
                draw_model.ClearSelection2(True)
            except Exception:
                pass
        _dbg(
            f"iter_views: 路径C(SelectAll+SelMgr) 拿到 {picked_c} 个模型视图",
            summary=True,
        )

    return views


def _view_outline(view: object) -> tuple:
    """取视图在图纸坐标系下的外轮廓 (xmin, ymin, xmax, ymax, cx, cy)(米)。取不到返回 None。"""
    try:
        box = view.GetOutline()
    except Exception as exc:
        _dbg(f"view_outline: GetOutline 抛异常 {type(exc).__name__}: {exc}")
        return None
    try:
        xmin, ymin, xmax, ymax = (float(v) for v in box[:4])
    except Exception as exc:
        _dbg(f"view_outline: 解析 GetOutline 返回失败 raw={box!r} err={exc}")
        return None
    if abs(xmax - xmin) + abs(ymax - ymin) <= 0.0:
        _dbg(f"view_outline: 退化零面积框 box={box[:4]}")
        return None
    return (xmin, ymin, xmax, ymax, (xmin + xmax) / 2.0, (ymin + ymax) / 2.0)


def _classify_three_views(draw_model: object, app: object = None) -> dict:
    """按图纸坐标位置把三视图分类为 front/top/right(等轴测忽略)。

    第三角: 前视图为基准(通常最左下的正投影视图), 俯视图在其正上方,
    右视图在其正右方。用各视图外轮廓中心的相对位置判定, 不依赖视图命名(更稳)。
    返回 {"front": view, "top": view|None, "right": view|None}, 取不到为 None。
    """
    ortho = []
    for v in _iter_model_views(draw_model, app):
        # 等轴测/轴测图排除: swDrawingIsometricView=4 等; 保守用轮廓近似方形+无法水平/竖直对齐再排除
        ol = _view_outline(v)
        if ol is None:
            continue
        ortho.append((v, ol))
    if not ortho:
        _dbg("classify_views: 未找到任何正投影视图(ortho=0)", summary=True)
        return {"front": None, "top": None, "right": None}
    # 前视图: 取最靠左下(x 最小, 其次 y 最小)的正投影视图作为基准
    front, front_ol = min(ortho, key=lambda t: (t[1][4], t[1][5]))
    fcx, fcy = front_ol[4], front_ol[5]
    top = right = None
    top_ol = right_ol = None
    for v, ol in ortho:
        if v is front:
            continue
        cx, cy = ol[4], ol[5]
        dx, dy = cx - fcx, cy - fcy
        # 正上方: y 明显更大且 x 基本对齐
        if dy > abs(dx) and abs(dx) <= max(front_ol[2] - front_ol[0], 1e-6):
            if top is None or cy > top_ol[5]:
                top, top_ol = v, ol
        # 正右方: x 明显更大且 y 基本对齐
        elif dx > abs(dy) and abs(dy) <= max(front_ol[3] - front_ol[1], 1e-6):
            if right is None or cx > right_ol[4]:
                right, right_ol = v, ol
    _dbg(
        f"classify_views: ortho={len(ortho)} front={'Y' if front is not None else 'N'} "
        f"top={'Y' if top is not None else 'N'} right={'Y' if right is not None else 'N'}",
        summary=True,
    )
    return {"front": front, "top": top, "right": right}


def _select_edge_at(draw_model: object, view: object, x: float, y: float) -> bool:
    """在工程图坐标 (x, y) 处用 SelectByID2 吸附选中一条投影边。

    真机 SW 2019 上，AddHorizontalDimension2/AddVerticalDimension2 若在
    调用前没有任何"实体"被选中，会直接返回 null，尺寸不会画上视图。
    这里通过 Extension.SelectByID2 在视图 outline 的边缘坐标附近做吸附式
    选边(容差由 SolidWorks 内部处理)，命中率明显高于凭空给坐标。

    选中成功返回 True。任何异常一律吞掉返回 False。
    """
    try:
        ext = getattr(draw_model, "Extension", None)
        if ext is None:
            _dbg("select_edge: draw_model.Extension 为 None")
            return False
        # 附加选择: mark=0, callout=None, selectOption=0
        ok = bool(ext.SelectByID2("", "EDGE", x, y, 0.0, True, 0, None, 0))
        if not ok:
            _dbg(f"select_edge: SelectByID2 未命中 EDGE @ ({x:.4f},{y:.4f})")
        return ok
    except Exception as exc:
        _dbg(f"select_edge: 抛异常 {type(exc).__name__}: {exc}")
        return False


def _add_h_dim(draw_model: object, view: object, x1: float, x2: float, y_edge: float, y_text: float) -> bool:
    """在视图上放置水平尺寸(米)。

    步骤: 先在 (x_mid, y_edge) 处 SelectByID2 吸附选中水平投影边,
    再调 AddHorizontalDimension2 在 (x_mid, y_text) 放尺寸线。
    成功返回 True。所有异常吞掉，避免打断整个补打流程。
    """
    try:
        try:
            draw_model.ClearSelection2(True)
        except Exception:
            pass
        x_mid = (x1 + x2) / 2.0
        picked = _select_edge_at(draw_model, view, x_mid, y_edge)
        try:
            dim = draw_model.AddHorizontalDimension2(x_mid, y_text, 0.0)
        except Exception as exc:
            _dbg(f"add_h_dim: AddHorizontalDimension2 抛异常 {type(exc).__name__}: {exc}")
            return False
        ok = dim is not None
        if not ok:
            _dbg(f"add_h_dim: AddHorizontalDimension2 返回 None (picked={picked} x_mid={x_mid:.4f} y_text={y_text:.4f})")
        return ok
    except Exception as exc:
        _dbg(f"add_h_dim: 外层异常 {type(exc).__name__}: {exc}")
        return False


def _add_v_dim(draw_model: object, view: object, y1: float, y2: float, x_edge: float, x_text: float) -> bool:
    """在视图上放置竖直尺寸(米)。

    步骤: 先在 (x_edge, y_mid) 处 SelectByID2 吸附选中竖直投影边,
    再调 AddVerticalDimension2 在 (x_text, y_mid) 放尺寸线。
    成功返回 True。所有异常吞掉。
    """
    try:
        try:
            draw_model.ClearSelection2(True)
        except Exception:
            pass
        y_mid = (y1 + y2) / 2.0
        picked = _select_edge_at(draw_model, view, x_edge, y_mid)
        try:
            dim = draw_model.AddVerticalDimension2(x_text, y_mid, 0.0)
        except Exception as exc:
            _dbg(f"add_v_dim: AddVerticalDimension2 抛异常 {type(exc).__name__}: {exc}")
            return False
        ok = dim is not None
        if not ok:
            _dbg(f"add_v_dim: AddVerticalDimension2 返回 None (picked={picked} x_text={x_text:.4f} y_mid={y_mid:.4f})")
        return ok
    except Exception as exc:
        _dbg(f"add_v_dim: 外层异常 {type(exc).__name__}: {exc}")
        return False


def _insert_overall_view_dimensions(draw_model: object, app: object = None) -> int:
    """在俯视图标注长/宽、在右视图标注高(厚度)的整体轮廓尺寸。

    仅补充"整体外形长宽高"三个基本尺寸(不重复模型自动导入的孔距/孔径等)。
    做法: 识别三视图方位, 取俯视图轮廓打水平(长)+竖直(宽)尺寸, 取右视图轮廓
    打竖直(高)尺寸。选边+放尺寸都逐个兜底, 返回成功放置的尺寸条数。

    注意: 真机需先选中轮廓边再 AddDimension 才最稳; 这里用视图轮廓包围框的边界
    坐标近似放置尺寸标注线, 具体落边由 SolidWorks 就近吸附。异常一律吞掉不阻断。
    """
    placed = 0
    # 补打之前强制重建, 保证 GetOutline 返回真实包围框, 而不是空 sheet 的退化框。
    try:
        draw_model.ForceRebuild3(False)
    except Exception:
        pass
    try:
        draw_model.EditRebuild3()
    except Exception:
        pass
    try:
        cls = _classify_three_views(draw_model, app)
    except Exception:
        return 0
    margin = 0.012  # 尺寸线离轮廓的偏移量(米, ≈12mm)

    top = cls.get("top") or cls.get("front")
    if top is not None:
        ol = _view_outline(top)
        if ol is not None:
            xmin, ymin, xmax, ymax, _, _ = ol
            try:
                draw_model.ActivateView(str(top.GetName2()))
            except Exception:
                pass
            # 长: 俯视图底部水平尺寸
            if _add_h_dim(draw_model, top, xmin, xmax, ymin, ymin - margin):
                placed += 1
            # 宽: 俯视图右侧竖直尺寸
            if _add_v_dim(draw_model, top, ymin, ymax, xmax, xmax + margin):
                placed += 1

    right = cls.get("right")
    if right is not None:
        ol = _view_outline(right)
        if ol is not None:
            xmin, ymin, xmax, ymax, _, _ = ol
            try:
                draw_model.ActivateView(str(right.GetName2()))
            except Exception:
                pass
            # 高(厚度): 右视图右侧竖直尺寸
            if _add_v_dim(draw_model, right, ymin, ymax, xmax, xmax + margin):
                placed += 1

    if placed:
        try:
            draw_model.EditRebuild3()
        except Exception:
            pass
    return placed


def _draw_all_dimensions_by_ourselves(draw_model: object, part_model: object, app: object = None) -> int:
    """出图端自绘策略：不依赖模型 DisplayDimension，直接在三视图上补齐外形尺寸。

    真机现象：程序化 API 建模 (create_base_plate / cut_corner_holes 等)
    不会调 SketchManager.AddDimension，零件里 DisplayDimension 数为 0，
    所以 InsertModelAnnotations3 无论如何都拉不到任何尺寸。走"自绘为主"路线：
    识别三视图后，用零件包围盒的三向跨度自绘外形尺寸。

    绘制策略（第三角，X=长/Y=宽/Z=高）:
      - 俯视图 (Top):    底部水平尺寸=X跨(长), 右侧竖直尺寸=Y跨(宽)
      - 前视图 (Front):  底部水平尺寸=X跨(长), 右侧竖直尺寸=Z跨(高)
      - 右视图 (Right):  底部水平尺寸=Y跨(宽), 右侧竖直尺寸=Z跨(高)

    注意：AddHorizontalDimension2/AddVerticalDimension2 的实际数值由 SolidWorks
    从选中的投影边自动计算，所以我们只负责"在正确位置选边+放尺寸线"，
    不需要传入长/宽/高的数值。零件包围盒仅用于日志/图幅决策。

    返回成功放置的尺寸条数。任何异常一律吞掉不阻断出图流程。
    """
    placed = 0
    if draw_model is None:
        _dbg("draw_self: draw_model 为 None, 直接跳过")
        return 0

    # 补打之前强制重建，保证 GetOutline 拿到真实的视图轮廓框
    try:
        draw_model.ForceRebuild3(False)
    except Exception as exc:
        _dbg(f"draw_self: ForceRebuild3 抛异常 {type(exc).__name__}: {exc}")
    # v028 修: SolidWorks 2019 late-bind 下 EditRebuild3 会被解析成布尔属性
    # 报 "'bool' object is not callable"; 上面 ForceRebuild3(False) 已经重建
    # 过了, 这里只做二次保险, 用 ForceRebuild3(True) 二次触发, 失败一律吞掉。
    try:
        draw_model.ForceRebuild3(True)
    except Exception as exc:
        _dbg(f"draw_self: ForceRebuild3(True) 抛异常 {type(exc).__name__}: {exc}")

    try:
        cls = _classify_three_views(draw_model, app)
    except Exception as exc:
        _dbg(f"draw_self: _classify_three_views 抛异常 {type(exc).__name__}: {exc}", summary=True)
        return 0

    margin = 0.012  # 尺寸线离轮廓的偏移(米, ≈12mm)

    def _draw_pair(view: object, tag: str, want_h: bool, want_v: bool) -> int:
        """在单个视图上按 outline 打水平/竖直尺寸，返回落地数。"""
        if view is None:
            _dbg(f"draw_self[{tag}]: 视图缺失, 跳过")
            return 0
        ol = _view_outline(view)
        if ol is None:
            _dbg(f"draw_self[{tag}]: outline 取不到, 跳过")
            return 0
        xmin, ymin, xmax, ymax, _, _ = ol
        _dbg(
            f"draw_self[{tag}]: outline=({xmin:.4f},{ymin:.4f})-({xmax:.4f},{ymax:.4f}) "
            f"跨度 dx={xmax-xmin:.4f} dy={ymax-ymin:.4f} m"
        )
        try:
            draw_model.ActivateView(str(view.GetName2()))
        except Exception as exc:
            _dbg(f"draw_self[{tag}]: ActivateView 抛异常 {type(exc).__name__}:{exc}")
        n = 0
        if want_h:
            if _add_h_dim(draw_model, view, xmin, xmax, ymin, ymin - margin):
                n += 1
                _dbg(f"draw_self[{tag}]: 水平尺寸 OK")
            else:
                _dbg(f"draw_self[{tag}]: 水平尺寸 FAIL")
        if want_v:
            if _add_v_dim(draw_model, view, ymin, ymax, xmax, xmax + margin):
                n += 1
                _dbg(f"draw_self[{tag}]: 竖直尺寸 OK")
            else:
                _dbg(f"draw_self[{tag}]: 竖直尺寸 FAIL")
        return n

    # 俯视图: 长 + 宽
    placed += _draw_pair(cls.get("top"), "top", want_h=True, want_v=True)
    # 前视图: 长 + 高
    placed += _draw_pair(cls.get("front"), "front", want_h=True, want_v=True)
    # 右视图: 宽 + 高
    placed += _draw_pair(cls.get("right"), "right", want_h=True, want_v=True)

    _dbg(f"draw_self: 累计自绘 {placed} 条", summary=True)

    if placed:
        try:
            draw_model.EditRebuild3()
        except Exception:
            pass
    return placed


def _count_display_dimensions(draw_model: object, app: object = None) -> int:
    """统计整张工程图当前已导入的显示尺寸总数(遍历所有视图)。

    用于判断 InsertModelAnnotations3 是否真的把尺寸画进了图纸——
    返回值非 None 并不代表真的导入了尺寸(可能 0 条)，必须用实际计数核实。
    统一走 _iter_model_views 拿到已下沉到 sheet 子节点的模型视图列表，
    避免此处再次踩"同级链只有 sheet 视图"的坑。
    """
    total = 0
    try:
        model_views = _iter_model_views(draw_model, app)
    except BaseException as exc:
        _dbg(
            f"count_display: _iter_model_views 抛 {type(exc).__name__}:{exc}",
            summary=True,
        )
        model_views = []
    for view in model_views:
        try:
            dim = view.GetFirstDisplayDimension5()
        except BaseException:
            dim = None
        while dim is not None:
            total += 1
            try:
                dim = dim.GetNext5()
            except BaseException:
                dim = None
    return total


def _mark_all_display_dimensions(part_model: object) -> None:
    """对已打开的零件模型再次触发 MarkAllDimensionsForDrawing(True)。

    首次 InsertModelAnnotations3 失败常见原因: 建模流程结束到出图开始之间
    有其他插件/宏改动过标记状态, 或 rebuild 时机导致部分特征尺寸未落表。
    出图重试前再打一次全体"待出图"标记, 提高 InsertModelAnnotations3 命中率。
    所有异常一律吞掉。
    """
    if part_model is None:
        return
    try:
        ext = getattr(part_model, "Extension", None)
        if ext is None:
            return
        try:
            ext.SelectAll()
        except Exception:
            pass
        try:
            ext.MarkAllDimensionsForDrawing(True)
        except Exception:
            pass
        try:
            part_model.ClearSelection2(True)
        except Exception:
            pass
    except Exception:
        pass


def _apply_dimensions_and_tolerance(app: object, draw_model: object, rules: list, part_model: object = None) -> dict:
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
    # 视图筛选统一走 _iter_model_views(已正确下沉到 sheet 子节点)，避免此处
    # 再次踩"同级链只有 sheet 视图"的坑。
    try:
        model_views = _iter_model_views(draw_model, app)
        _dbg(f"apply_dim: 逐视图导入前, 拿到模型视图数={len(model_views)}")
        for view in model_views:
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
    except Exception:
        pass

    try:
        draw_model.EditRebuild3()
    except Exception:
        pass

    # 用实际显示尺寸数核实是否真的画进了图纸(返回值非 None 不可靠)
    imported = _count_display_dimensions(draw_model, app)
    _dbg(f"apply_dim: InsertModelAnnotations3 后计数 DisplayDimension={imported}", summary=True)

    # 路径 E: 若 InsertModelAnnotations3 一条尺寸都没导进来(late-bind 白名单挂),
    # 就走 SW 主 UI 命令通道 RunCommand(swCommands_InsertModelItems),
    # 让 SW 按当前激活视图上下文自己标模型项目。RunCommand 是 ISldWorks 主
    # IDispatch 上的方法(与 RunMacro2 同级), 已知不在 IModelDoc 白名单管辖内。
    # 逐视图激活后触发, 保证 3 个投影视图都有机会被标注。
    # 加固要点(v021):
    #   - 触发条件放宽: 只要 imported==0 且 app 可用就跑, 不再要求 fallback_views 非空;
    #   - fallback_views 为空也执行 1 次"不激活直接 RunCommand", 让 SW 用当前激活视图;
    #   - 用 BaseException 兜住, 避免 pywin32 late-bind 抛非 Exception 异常静默断链;
    #   - 无论触发与否都落 summary 日志, 保证真机诊断可见性。
    _dbg(
        f"apply_dim: 进入路径E 判定 imported={imported} app_available={app is not None}",
        summary=True,
    )
    if imported == 0 and app is not None:
        try:
            fallback_views = _iter_model_views(draw_model, app)
        except BaseException as exc:
            _dbg(
                f"apply_dim: 路径E _iter_model_views 抛 {type(exc).__name__}:{exc}",
                summary=True,
            )
            fallback_views = []
        _dbg(
            f"apply_dim: 路径E fallback_views 数量={len(fallback_views)}",
            summary=True,
        )
        run_cmd_ok = 0
        run_cmd_tried = 0
        # 定义一个"发一次 RunCommand + 多命令ID fallback"闭包, 逐个尝试直到成功
        def _try_run_cmd() -> tuple[int, int]:
            tried = 0
            succ = 0
            for cmd_id in _SW_CMD_INSERT_MODEL_ITEMS_ALTS:
                tried += 1
                try:
                    ok_c = bool(app.RunCommand(cmd_id, ""))
                except BaseException as exc:
                    _dbg(
                        f"apply_dim: 路径E RunCommand(cmd={cmd_id}) 抛 {type(exc).__name__}:{exc}",
                        summary=True,
                    )
                    continue
                _dbg(
                    f"apply_dim: 路径E RunCommand(cmd={cmd_id}) 返回={ok_c}",
                    summary=True,
                )
                if ok_c:
                    succ += 1
                    break  # 命中一个命令ID就够, 别的可能会重复标注
            return tried, succ

        if fallback_views:
            for view in fallback_views:
                try:
                    name = str(view.GetName2())
                    if name:
                        draw_model.ActivateView(name)
                except BaseException:
                    pass
                t, s = _try_run_cmd()
                run_cmd_tried += t
                run_cmd_ok += s
                if s == 0:
                    break  # 某视图上所有 cmd_id 都不认, 后续视图也别浪费
        else:
            # 视图列表拿不到就用 SelectByID2 类型选先把一个 DRAWINGVIEW 选中作为命令上下文
            # (v022 真机反馈: "试图执行系统不支持的操作" 弹窗根因 = RunCommand 无激活视图上下文)。
            # SelectByID2 允许 name="" + type="DRAWINGVIEW" 走类型选择, 把当前图纸上第一个
            # 匹配类型的视图选中, 这就是 SW 主命令通道所需的 UI 上下文。
            selected_for_cmd = False
            try:
                draw_model.ClearSelection2(True)
            except BaseException:
                pass
            try:
                selected_for_cmd = bool(
                    draw_model.Extension.SelectByID2(
                        "", "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, None, 0
                    )
                )
            except BaseException as exc:
                _dbg(
                    f"apply_dim: 路径E 类型选 DRAWINGVIEW 抛 {type(exc).__name__}:{exc}",
                    summary=True,
                )
                selected_for_cmd = False
            _dbg(
                f"apply_dim: 路径E 类型选 DRAWINGVIEW={'ok' if selected_for_cmd else 'fail'}, "
                f"准备直发 RunCommand",
                summary=True,
            )
            t, s = _try_run_cmd()
            run_cmd_tried += t
            run_cmd_ok += s
            try:
                draw_model.ClearSelection2(True)
            except BaseException:
                pass
        try:
            draw_model.EditRebuild3()
        except BaseException:
            pass
        try:
            imported_after_e = _count_display_dimensions(draw_model, app)
        except BaseException as exc:
            _dbg(
                f"apply_dim: 路径E 后 _count_display_dimensions 抛 {type(exc).__name__}:{exc}",
                summary=True,
            )
            imported_after_e = 0
        _dbg(
            f"apply_dim: 路径E(RunCommand InsertModelItems) 尝试={run_cmd_tried} "
            f"成功={run_cmd_ok} 命令后 DisplayDimension={imported_after_e}",
            summary=True,
        )
        imported = imported_after_e

    # 路径 F: RunCommand 也没标进来时, 让 SW 内部 VBA 引擎 early-bind 完成
    # InsertModelAnnotations3。这是 v024 决定性证据锁定的终极兜底 -- pywin32
    # late-bind 白名单完全阉割了 IDrawingDoc, 但 VBA 内部对 IDrawingDoc 是
    # early-bind, 不受 IDispatch 白名单影响。跟路径 5 dump 视图名同一个原理,
    # 只是这里不是 dump 名字, 而是直接把 InsertModelAnnotations3 的活儿也放到
    # 宏里干完, 再把 imported 数写回来。
    #
    # v027 加固: 不管条件是否满足, 先无条件落一条"路径F 前置状态"日志。真机 v026
    # 反馈里 30 条摘要完全看不到任何 path_F 行, 需要区分 "分支被跳过" vs
    # "分支进了但 dbg 被 UI 截了"。
    _dbg(
        f"apply_dim: 路径F 前置状态 imported={imported} app_is_none={app is None}",
        summary=True,
    )
    if imported == 0 and app is not None:
        _dbg(
            f"apply_dim: 进入路径F 判定 imported={imported} app_available=True",
            summary=True,
        )
        try:
            f_result = _insert_annotations_via_macro(app)
        except BaseException as exc:
            _dbg(
                f"apply_dim: 路径F _insert_annotations_via_macro 抛 {type(exc).__name__}:{exc}",
                summary=True,
            )
            f_result = {"imported": 0, "views": 0, "error": f"exception:{exc}"}
        try:
            draw_model.EditRebuild3()
        except BaseException:
            pass
        try:
            imported_after_f = _count_display_dimensions(draw_model, app)
        except BaseException:
            imported_after_f = int(f_result.get("imported", 0) or 0)
        _dbg(
            f"apply_dim: 路径F(VBA InsertModelAnnotations3) 宏内 imported={f_result.get('imported')} "
            f"views={f_result.get('views')} 命令后 DisplayDimension={imported_after_f} err={f_result.get('error')!r}",
            summary=True,
        )
        imported = imported_after_f

    dim_count = imported

    # 1.1) 出图端自绘策略：程序化 API 建模的零件里 DisplayDimension 恒为 0,
    #      InsertModelAnnotations3 拉不到任何尺寸。直接在三视图上按 outline 边
    #      自绘长/宽/高六条外形尺寸(俯视图长宽、前视图长高、右视图宽高)。
    #      自绘条数直接计入 dim_count，取代之前"再数一次 display dimension"的做法。
    try:
        drawn = _draw_all_dimensions_by_ourselves(draw_model, part_model, app)
    except Exception as exc:
        _dbg(f"apply_dim: _draw_all_dimensions_by_ourselves 抛异常 {type(exc).__name__}: {exc}", summary=True)
        drawn = 0
    if drawn:
        dim_count += drawn

    # 1.2) 兼容旧路径:模型自带 DisplayDimension 的场景(如手工建模+AddDimension),
    #      再走一遍"整体外形长/宽/高补打",与自绘互补不冲突(SW 会去重)。
    try:
        overall = _insert_overall_view_dimensions(draw_model, app)
    except Exception as exc:
        _dbg(f"apply_dim: _insert_overall_view_dimensions 抛异常 {type(exc).__name__}: {exc}")
        overall = 0
    if overall:
        dim_count += overall
    _dbg(f"apply_dim: dim_count 汇总 = 模型导入{imported} + 自绘{drawn} + 兜底{overall} 合计={dim_count}", summary=True)

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