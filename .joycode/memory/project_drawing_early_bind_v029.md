---
name: 出图早绑定迭代与 v033 卡点转移
description: >-
  AI-Enterprise 3D转2D出图 draw早绑定 v029→v033
  根因链；v032放弃draw整体早绑定改用_sw_invoke；v033卡点从建/读视图转到标尺寸
type: project
---

`src/solidworks_api/drawing.py` 3D转2D出图。late-bind下 SW无参方法(GetSheetNames/
GetViews/GetOutline/GetFirstDisplayDimension5)被误当属性返tuple,`()`调用报
'tuple object is not callable',读值全挂。

迭代链(真机):
- v031: IDrawingDoc(obj)使draw早绑定→Create3rdAngleViews2崩InvokeTypes(回退)。
- v032: 放弃对draw整体早绑定,draw保持late-bind;新增helper _sw_invoke(obj,name):
  attr=getattr(obj,name); return attr() if callable(attr) else attr, 异常返None。
  真机成功: Create3rdAngleViews2返True + 读到3个视图。卡点转移到"标尺寸"。
- v033(卡点=DisplayDimension=0一条没标上):
  * tuple坑扩散到 _view_outline的GetOutline、_count_display_dimensions的
    GetFirstDisplayDimension5/GetNext5→全改_sw_invoke。计数tuple坑吞成0可能误判"没导入"触发兜底空转。
  * InsertModelAnnotations3(6参)无tuple坑但可能抛com_error,原try/except:pass吞掉→改落summary日志暴露异常。

How to apply:
1. _new_drawing_doc 不再 _ensure_early_bind(draw)(函数保留不调用)。
2. late-bind无参方法一律走 _sw_invoke。宏路径死路放弃。真机日志有缓存需校验时间戳。
3. 待真机验证: InsertModelAnnotations3是否真抛异常及计数改后是否>0。