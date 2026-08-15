---
name: 出图v031早绑定接口类直接构造
description: >-
  AI-Enterprise 3D转2D出图
  v031:EnsureModule成功但CastTo仍报makepy,改用早绑定模块接口包装类mod.IDrawingDoc(obj)直接构造绕开makepy反查
type: project
---

迭代根因链(last_run.log):
v029 gencache.EnsureDispatch(draw)报'can not automate the makepy process'(SW运行时对象不带可解析typelib);
v030 EnsureModule(GUID {83A33D31-27C5-11CE-BFD4-00400513BB57},ver27=SW2019)成功生成早绑定模块,
但win32com.client.CastTo(obj,"IDrawingDoc")仍报同一makepy错(CastTo内部还要对obj反查CLSID匹配接口类,SW对象拿不到CLSID)。
v031(drawing.py _ensure_early_bind):模块已生成后直接用接口包装类构造 mod.IDrawingDoc(obj)——
包装类只是包裹IDispatch的普通类,构造不走makepy反查。三重兜底:①接口类直接构造(候选名IDrawingDoc/DrawingDoc带不带I前缀都试)②Dispatch(obj)③CastTo,全失败回退late-bind。
_ensure_sw_early_module幂等,_SW_TYPELIB_VERSIONS逐版本试。macOS drawing 19 passed。须SW2019真机复测接口类构造后GetSheetNames()/GetFirstView()是否不再tuple崩/找不到成员、视图计数是否转正。
宏路径(RunMacro2 dump始终不生成)注册表降级无效已确认死路,后续须回.swb二进制宏或彻底走自绘。
若v031接口类构造仍失败=终极兜底纯_draw_all_dimensions_by_ourselves。