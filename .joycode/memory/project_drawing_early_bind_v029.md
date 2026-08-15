---
name: 出图早绑定迭代与自绘转向 v034
description: >-
  AI-Enterprise 3D转2D出图 late-bind 迭代链 v029→v034；InsertModelAnnotations3
  白名单外无解，战略转自绘兜底
type: project
---

记录 v029→v034 迭代链（drawing.py）：
- late-bind 下 SW 无参方法(GetSheetNames/GetViews/GetOutline/GetFirstDisplayDimension5)被误当属性返 tuple/str。
- v031 IDrawingDoc(obj)早绑定崩 Create3rdAngleViews2(回退)。
- v032 放弃 draw 整体早绑定 + _sw_invoke → Create3rdAngleViews2 返 True + 读到 3 视图。
- v033 真机诊断铁证：InsertModelAnnotations3 抛 AttributeError:<unknown>.方法名(文档层+3视图全挂)——白名单外，模型驱动尺寸彻底无解；早绑定能解但崩建视图。计数改 _sw_invoke 证实显示尺寸真 0(非误判)。RunCommand(1668)返 True 但仍 0。宏 no_dump_macro_not_started 死路。
- v034 战略转向：放弃模型驱动尺寸，全力修自绘兜底。新增 _sw_call(obj,name,*args) 带参 late-bind 安全调用返(ok,result)，属性化不可调用即判失败。修 SelectByID2 callout=None 编组 VT_NULL 被拒(arg8)→多候选 pythoncom.Empty/Missing/None；ActivateView str 坑、AddH/VDimension2 全改 _sw_call。19 passed。

Why: SW2019 客户机内网，late-bind 是唯一稳定路径；模型驱动尺寸无解，只能自绘外形长宽高。
How to apply: _new_drawing_doc 不早绑定；无参走 _sw_invoke，带参走 _sw_call；勿再试 InsertModelAnnotations3/宏；v034 待真机验证自绘是否真出尺寸(看 select_edge/draw_self 日志)。