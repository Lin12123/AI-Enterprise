---
name: 出图长宽高落地转向 InsertNote v041
description: >-
  AI-Enterprise
  3D转2D出图;真机唯一可用落地=InsertNote视图旁注释;SelectByID2/AddDimension/GetPolyLines7全走不通已放弃
type: project
---

drawing.py 出图(真机 SW2019, late-bind COM):
- 早绑定链: QueryInterface 取裸IDispatch; IModelDoc/IModelDocExtension 成功, IView 早绑定失败。
- 死路(勿再试): SelectByID2 选边恒False; AddH/VDimension2 依赖选边恒None; GetPolyLines7 out参数拿不到; InsertModelAnnotations3 白名单外; RunCommand1668 True但0; VBA宏 no_dump。程序化零件 DisplayDimension 恒0。

长宽高只用 InsertNote(真机唯一可用): _insert_note_at + _draw_bbox_notes_on_views, 三视图取 _view_outline+_get_part_bbox_dims_mm 的 L/W/H, 边缘外 margin≈10mm 写长/宽/高(俯视图底写长右写宽, 右视图右写高), 计入 dim_count。
- v040真机: dim_count=3 成功(图上确有3条), 但 SetPosition 报 -2147352573 找不到成员, 三条堆叠图纸中央未贴视图边。
- v041修: _insert_note_at 定位改 _sw_call 多路径重试: ①note.SetPosition ②ann.SetPosition2 ③ann.SetPosition, 任一成功即停, 全败位置默认。待真机验证。

How to apply: 长宽高只用 InsertNote, 勿走选边/Dimension API; SetPosition late-bind 不稳用 _sw_call 多路径重试。dim_count>0 核心已达成, 剩定位微调。