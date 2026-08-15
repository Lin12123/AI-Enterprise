---
name: 出图v030早绑定EnsureModule+CastTo
description: >-
  AI-Enterprise 3D转2D出图 v030:用SW typelib
  GUID的EnsureModule+CastTo替代无效的EnsureDispatch(obj)绕开late-bind白名单
type: project
---

v029复测根因(last_run.log铁证): gencache.EnsureDispatch(draw)报
'This COM object can not automate the makepy process'——SW运行时IDispatch对象不带可解析typelib,
EnsureDispatch无法反查,早绑定从未生效仍走late-bind(GetSheetNames tuple崩/GetFirstView/GetCurrentSheet找不到成员/iter全0);
注册表macro_sec已写入成功但RunMacro2 dump仍不生成(降级注册表没解除未签名.swp拒载)。
v030(drawing.py):
①_ensure_sw_early_module()用SW typelib GUID {83A33D31-27C5-11CE-BFD4-00400513BB57}逐版本(27/28/29..major)
gencache.EnsureModule预生成早绑定模块,进程内幂等。
②_ensure_early_bind(obj,iface="IDrawingDoc")改为win32com.client.CastTo(obj,iface)显式接口转换,全失败静默回退late-bind。
_new_drawing_doc对draw调用后draw_model全程早绑定。macOS drawing 19 passed。须SW2019真机复测CastTo是否成功。
若CastTo仍失败=typelib未注册/接口名不符,终极兜底纯_draw_all_dimensions_by_ourselves。
宏路径(RunMacro2)仍未通,注册表降级无效,后续须回.swb二进制宏或放弃宏路径。