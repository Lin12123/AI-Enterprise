---
name: 出图长宽高落地转向 InsertNote v041.1
description: >-
  AI-Enterprise
  3D转2D出图;真机唯一可用落地=InsertNote;SetPosition不通改ActivateView分散;选边/Dimension全放弃
type: project
---

drawing.py 出图(真机 SW2019, late-bind COM):
- 死路(勿再试): SelectByID2 选边恒False; AddH/VDimension2 依赖选边; GetPolyLines7 out参数拿不到; InsertModelAnnotations3 白名单外; RunCommand1668 True但0; VBA no_dump; IView 早绑定失败。程序化零件 DisplayDimension 恒0。
- 该机 late-bind 对大量方法报 -2147352573 找不到成员(FirstFeature/GetCurrentSheet/SetPosition 全中, gen_py/typelib 问题), SetPosition 定位路彻底不通。

长宽高只用 InsertNote(真机唯一可用): _insert_note_at + _draw_bbox_notes_on_views。
- v040: dim_count=3 成功但 SetPosition 失败三条堆图纸中心。
- v041.1: 不靠 SetPosition 定位, 改①插入前 ActivateView 目标视图(真机可用)让注释落该视图中心附近天然分散 ②同视图多量合并成一条多行注释(长=L\n宽=W)避免同视图内叠。俯视图落长/宽, 右视图落高。

How to apply: 长宽高只用 InsertNote+ActivateView 分散落点, 勿依赖 SetPosition/选边/Dimension。落点仍压图形则试 IView.InsertNote(视图级注释)。dim_count=3 核心已达成。