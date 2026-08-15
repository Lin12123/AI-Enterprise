---
name: 出图早绑定迭代与自绘转向 v036
description: AI-Enterprise 3D转2D出图迭代链 v029→v036；早绑定接口类改用能力探测而非名字getattr
type: project
---

drawing.py 迭代链 v029→v036：
- v031 整体早绑定 draw 崩 Create3rdAngleViews2(回退)。
- v032 建视图 late-bind+_sw_invoke → 建视图+读3视图成功。
- v033 InsertModelAnnotations3 白名单外 AttributeError(模型驱动尺寸无解); 显示尺寸真0; RunCommand(1668)True但0; 宏死路。转自绘。
- v034 _sw_call + ActivateView str 坑修好(进视图编辑态)。但 SelectByID2 arg8(callout)late-bind 传 None/Empty/Missing 都类型不匹配→自绘0。
- v035 局部早绑定 IModelDoc2。真机: EnsureModule成功ver=27.0, 但 getattr(mod,"IModelDoc2")(obj) 类名是 NewDocument(无 AddHorizontalDimension2)→InvokeTypes AttributeError。
- v036 根治: 不靠名字, 改能力探测——_find_iface_cls_by_methods 遍历 mod 选 cls.__dict__ 含 require_methods 的类(makepy 每个 dispid 方法在类字典生成同名函数)。_ensure_early_bind 加 require_methods, 命中打印真实类名+hasattr校验。_early_bound_doc 要求含 AddH/VDimension2。_select_edge_at 对 early_doc.Extension 再针对 SelectByID2 探测。

Why: makepy 里"接口属性名"与"真正含方法的类"不一致, 名字匹配不可靠, 只有类字典含方法名才精确命中。
How to apply: 早绑定按能力探测; 建视图勿早绑定; 勿再试 InsertModelAnnotations3/宏; v036 待真机验证类名非 NewDocument 且自绘>0。