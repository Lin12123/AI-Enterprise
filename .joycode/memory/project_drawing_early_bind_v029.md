---
name: 出图长宽高落地转向 InsertNote v040
description: >-
  AI-Enterprise
  3D转2D出图;真机唯一可用落地=InsertNote视图旁注释;SelectByID2/AddDimension/GetPolyLines7全走不通已放弃
type: project
---

drawing.py 出图(真机 SW2019, late-bind COM)结论:
- 早绑定链(v036~v038): 能力探测选 cls.__dict__ 含目标方法的类 + QueryInterface(iface.CLSID, pythoncom.IID_IDispatch) 取裸IDispatch 再 cls(oleobj); 判成功查 ._oleobj_ 有 InvokeTypes。IModelDoc/IModelDocExtension 成功; IView 早绑定彻底失败。
- 死路(勿再试): ①SelectByID2 选边恒返回 False 未命中 EDGE ②AddH/VDimension2 依赖选边恒 None ③GetPolyLines7 有 out 参数, late/early 均拿不到 ④InsertModelAnnotations3 白名单外 ⑤RunCommand1668 True 但 0 ⑥VBA 宏 no_dump。程序化建模零件 DisplayDimension 恒 0。

v040 转向: 图上长宽高改用 InsertNote 文字注释落地(真机唯一可用: InsertNote 返回 note→note.GetAnnotation().SetPosition(x,y,0.0) 图纸坐标米; 技术要求/兜底注释已真机成功)。
- 新增 _insert_note_at + _draw_bbox_notes_on_views: 三视图(_classify_three_views)取 _view_outline, 用 _get_part_bbox_dims_mm 的 L/W/H, 第三角方位在视图边缘外(margin≈10mm)写"长/宽/高"; 俯视图底写长右写宽, 右视图右写高。计入 dim_count。接入 _apply_dimensions_and_tolerance 作主力。

How to apply: 长宽高只用 InsertNote+SetPosition, 勿走 SelectByID2/AddDimension/GetPolyLines7; _view_outline/InsertNote 真机可靠。v040 待真机复测 dim_count>0。