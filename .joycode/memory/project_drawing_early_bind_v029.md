---
name: 出图早绑定迭代与自绘转向 v035
description: >-
  AI-Enterprise 3D转2D出图迭代链
  v029→v035；建视图用late-bind，自绘尺寸阶段局部早绑定IModelDoc2调SelectByID2
type: project
---

drawing.py 迭代链 v029→v035：
- v031 整体早绑定 draw 崩 Create3rdAngleViews2(回退)。
- v032 建视图用 late-bind + _sw_invoke → 建视图+读3视图成功。
- v033 InsertModelAnnotations3 抛 AttributeError:<unknown>.方法名(白名单外,模型驱动尺寸无解); 计数证实显示尺寸真0; RunCommand(1668)返True但仍0; 宏死路。战略转自绘兜底。
- v034 新增 _sw_call 带参 late-bind 安全调用; ActivateView str 坑修好(真机进视图编辑态)。但 SelectByID2 arg8(callout,ICallout*)无论传 None/pythoncom.Empty/Missing 都 late-bind 编组失败(类型不匹配)→自绘0条。
- v035 根治: 视图建完后用 _early_bound_doc 把 draw_model 早绑定成 IModelDoc2(复用v031 mod.接口包装类直接构造,不走makepy反查,进程内缓存)。早绑定按dispid调用允许省略尾部可选参数,正确编组callout。选边+AddH/VDimension2都走早绑定doc(同一文档共享选择集),late-bind仅兜底。此时不再调Create3rdAngleViews2,早绑定IModelDoc2安全。

Why: late-bind 建视图稳定,但选边/加尺寸的可选对象参数编组不了,须建完视图后局部早绑定。
How to apply: 建视图阶段勿早绑定;自绘尺寸阶段用_early_bound_doc;勿再试InsertModelAnnotations3/宏;v035待真机验证EnsureModule成功+SelectByID2命中。