---
name: 出图早绑定迭代与自绘转向 v039
description: >-
  AI-Enterprise
  3D转2D出图早绑定链;能力探测+QueryInterface取裸IDispatch;选边坐标用GetPolyLines7真实边中点
type: project
---

drawing.py 出图链:
- 建视图 late-bind 成功; InsertModelAnnotations3 白名单外、显示尺寸真0、宏死路→只能自绘(SelectByID2 选边+AddH/VDimension2)。
- 早绑定: v036 能力探测 _find_iface_cls_by_methods 选 cls.__dict__ 含 require_methods 的类(IModelDoc/IModelDocExtension); v037 _construct_iface 用 base.QueryInterface(iface_cls.CLSID,pythoncom.IID_IDispatch) 取裸IDispatch 再 cls(oleobj)。
- Extension 须从原始 draw_model.Extension 拿(IModelDoc 接口不暴露.Extension); 判断早绑定成功查 ext_early._oleobj_ 有 InvokeTypes(包装对象本身没有)否则误判回退(v038修复2)。
- v038后早绑定 SelectByID2 调通但返回 False 未命中: 坐标用 GetOutline 外框角/边缘, 视图外框比真实几何大有留白落不到真实边。
- v039: 新增 _view_edge_midpoints 用 IView.GetPolyLines7 拿真实投影线段端点(图纸坐标米)取水平/竖直边中点供 SelectByID2; _add_h/v_dim 优先真实边中点, 回退 outline 边缘。

How to apply: 早绑定=能力探测+QueryInterface裸IDispatch; Extension从原始draw_model拿+判断查_oleobj_.InvokeTypes; 选边用GetPolyLines7真实边中点; 建视图勿早绑定; 勿试InsertModelAnnotations3/宏。v039待真机验证 picked=True+自绘>0。