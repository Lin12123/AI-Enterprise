---
name: 出图早绑定迭代与 v033 卡点转移
description: >-
  AI-Enterprise 3D转2D出图 draw早绑定 v029→v033
  根因链；v032放弃draw整体早绑定改用_sw_invoke；v033卡点从建/读视图转到标尺寸
type: project
---

`src/solidworks_api/drawing.py` 3D转2D出图。late-bind下 GetSheetNames/GetViews/
GetFirstView 被误当属性(返回tuple,再`()`调用报'tuple object is not callable'),读视图全0。

迭代链(真机验证):
- v030: EnsureModule(GUID {83A33D31-27C5-11CE-BFD4-00400513BB57} ver27=SW2019)成功,
  但CastTo(draw)报'can not automate the makepy process';回退late-bind时Create3rdAngleViews2仍返True。
- v031: 改 mod.IDrawingDoc(obj) 接口类构造→draw变早绑定→真机调Create3rdAngleViews2崩
  'NewDocument.InvokeTypes'(typelib27与真机IDL错位),反而搞崩原本可用的建视图(回退)。
- v032(当前):放弃对draw主对象整体早绑定。

How to apply:
1. _new_drawing_doc 不再 _ensure_early_bind(draw), draw保持late-bind保住建视图(函数保留不调用)。
2. 读视图改用helper _sw_invoke(obj,name): attr=getattr(obj,name);
   return attr() if callable(attr) else attr, 异常返None, 兼容方法/属性两种暴露。
3. 已替换: _count_sheet_views、_iter_model_views路径1/2/3。
4. 教训:别对整个draw早绑定(副作用大)。宏路径死路:macro_sec降级成功但dump不生成,放弃。
5. 真机日志有缓存,需stat/grep校验时间戳,以用户贴报错为准。