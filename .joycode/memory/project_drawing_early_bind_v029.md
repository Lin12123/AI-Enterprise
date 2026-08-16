---
name: 出图早绑定迭代与自绘转向 v038
description: >-
  AI-Enterprise
  3D转2D出图早绑定链；能力探测选类+QueryInterface取裸IDispatch；Extension须从原始draw_model拿
type: project
---

drawing.py 出图链要点：
- 建视图 late-bind+_sw_invoke 成功; InsertModelAnnotations3 白名单外无解、显示尺寸真0、宏死路→只能自绘。
- 自绘需先 Extension.SelectByID2 选边(arg8 callout)再 AddH/VDimension2。late-bind arg8 类型不匹配(-2147352571)→选不中。
- 早绑定演进: getattr(mod,name)(obj) 类名 NewDocument 无目标方法(v035); 能力探测 _find_iface_cls_by_methods 选 cls.__dict__ 含 require_methods 的类选对 IModelDoc, 但直接 cls(obj) 把 obj 包装对象当 _oleobj_ 无 InvokeTypes→报 NewDocument.InvokeTypes(v036)。
- v037 _construct_iface: base.QueryInterface(iface_cls.CLSID, pythoncom.IID_IDispatch)取裸IDispatch 再 cls(oleobj), 校验 _oleobj_ 有 InvokeTypes+hasattr。真机 IModelDoc 早绑定成功。但 select_edge 仍 picked=False, 因走 early_doc.Extension 而 IModelDoc 接口不暴露 .Extension→整块跳过仍 late-bind。
- v038 select_edge 从原始 draw_model.Extension 直接 _ensure_early_bind(require SelectByID2)探测。

How to apply: 早绑定=能力探测选类+QueryInterface取裸IDispatch; Extension 从原始 draw_model 拿; 建视图勿早绑定; 勿再试 InsertModelAnnotations3/宏。v038 待真机验证 picked=True+自绘>0。