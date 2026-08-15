---
name: 出图早绑定迭代与自绘转向 v037
description: AI-Enterprise 3D转2D出图迭代链 v029→v037；早绑定=能力探测选类+QueryInterface取裸IDispatch构造
type: project
---

drawing.py 迭代链：
- v032 建视图 late-bind+_sw_invoke 成功。
- v033 InsertModelAnnotations3 白名单外无解; 显示尺寸真0; RunCommand(1668)True但0; 宏死路。转自绘。
- v034 SelectByID2 arg8 callout late-bind 类型不匹配→自绘0。
- v035 getattr(mod,"IModelDoc2")(obj) 类名 NewDocument→InvokeTypes AttributeError。
- v036 能力探测 _find_iface_cls_by_methods 选 cls.__dict__ 含 require_methods 的类, 真机选对 IModelDoc。但 IModelDoc(obj) 把 obj(NewDocument包装对象)当_oleobj_存, 无InvokeTypes→调 AddHorizontalDimension2 仍报 NewDocument.InvokeTypes; hasattr True 是假阳性(方法在类上)。
- v037 _construct_iface: base=obj._oleobj_ or obj; oleobj=base.QueryInterface(iface_cls.CLSID, pythoncom.IID_IDispatch)取裸IDispatch; iface_cls(oleobj); 校验 _oleobj_ 有 InvokeTypes+hasattr 才返回。能力探测+名字候选都走它。

Why: pywin32 _oleobj_ 必须是裸 PyIDispatch(有InvokeTypes), 传早绑定包装对象会崩; 选对类不够, 构造时 _oleobj_ 才关键。
How to apply: 早绑定=能力探测选类+QueryInterface取裸IDispatch; 建视图勿早绑定; 勿再试 InsertModelAnnotations3/宏。v037 待真机验证 InvokeTypes=True 且自绘>0。