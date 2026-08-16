---
name: 出图 v042 只出模板+标准三视图(停用全部尺寸标注)
description: 'AI-Enterprise 3D转2D出图;真机 late-bind 尺寸/注释全不通,v042 起只出企业模板+标准三视图,不做任何尺寸标注'
type: project
---

drawing.py 出图(真机 SW2019, late-bind COM)最终决策:
- 死路(勿再试, v035~v041.1 全验证失败): InsertModelAnnotations3 白名单外; SelectByID2 选边恒False; AddDimension 依赖选边; GetPolyLines7 out参数拿不到; RunCommand1668 True但0; VBA no_dump; IView 早绑定失败; 程序化零件 DisplayDimension 恒0。该机 late-bind 对 FirstFeature/GetCurrentSheet/SetPosition 大量方法报 -2147352573 找不到成员(gen_py/typelib), 连唯一可用的 InsertNote 也因 SetPosition 无法定位而三条注释堆叠重叠。
- v042 决策: 按用户要求, 工程图只保留企业模板 + 标准三视图, 彻底停用全部尺寸/注释标注。
  * _apply_dimensions_and_tolerance 开头直接 return {dim_count:0,grade:"",tol_applied:0}(短路, 不再调 InsertModelAnnotations3/选边自绘/视图旁注释/兜底)。
  * 主流程 3.1 段去掉 dim_count<=0 的 MarkAll 重试 + _insert_bbox_fallback_note 包围盒兜底, annotation_note 固定为"只出模板+标准三视图,未标注尺寸"。技术要求仍沿用模板。

How to apply: 出图=模板+三视图, 不要再加任何尺寸/注释标注代码; _insert_three_views 保留, 尺寸相关全部停用。