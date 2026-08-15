---
name: 出图v029早绑定与宏安全性降级
description: 'AI-Enterprise 3D转2D出图 v029:gencache早绑定绕开late-bind白名单 + 注册表降级SW宏安全性'
type: project
---

v028复测根因(last_run.log):Create3rdAngleViews2 返回True但 pywin32 late-bind IDispatch 白名单封死视图访问——GetSheetNames 误解析成属性返回tuple,()调用报'tuple' object is not callable;GetCurrentSheet/GetFirstView/FirstFeature 全 找不到成员;iter_views七段全0。RunMacro2 ok=True 但dump从不生成→SW2019静默拒载未签名.swp。

**Why:** 视图真创建了,失败在Python侧摸不到视图对象+宏被拒载,dim全0走包围盒兜底。

v029(方案C,src/solidworks_api/drawing.py):①_ensure_early_bind(obj)(L338)用 gencache.EnsureDispatch 转早绑定绕开白名单,在_new_drawing_doc的NewDocument后对draw调用(L457),缺依赖/权限全try回退late-bind。②_lower_macro_security()(L373)写注册表 HKCU\Software\SolidWorks\SolidWorks{2019/2020/2021}\Security(Enable macro=1/Macro Run Warning=0/Enable VSTA macros=1)幂等一次,在两处RunMacro2(路径5、路径F)前调用,无winreg/无权限静默回退。

**How to apply:** macOS drawing 19 passed(另5个Windows路径断言失败与本改动无关)。须Windows+SW2019真机复测确认是否根治。若仍失败终极兜底=纯_draw_all_dimensions_by_ourselves。