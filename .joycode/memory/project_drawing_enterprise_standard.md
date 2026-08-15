---
name: 3D转2D企业标准出图链路
description: 'AI-Enterprise 点击3D转2D的全链路:尺寸+公差+图幅+技术要求+长宽高兜底关键约定'
type: project
---

3D转2D=三视图+导入模型尺寸+企业标准公差+图幅+技术要求+长宽高兜底。

链路:插件→POST /api/create_drawing→KnowledgeCache 取 rules→create_drawing_from_active_part(app,rules)。云端口=8800,knowledge_cache DEFAULT_BASE_URL 须同为8800(env AI_SW_CLOUD_URL 覆盖),不一致 WinError 10061。缓存TTL=1800,不可达沿用旧缓存。

尺寸:InsertModelAnnotations3 option 位标志 1=标记/2=未标记,程序化建模全未标记,必须传 1|2=3;返回非None不可靠,用 _count_display_dimensions 核实。逐视图补导入前须 draw_model.ActivateView(view.GetName2()),否则作用错视图导不进。

图幅:Sheet.SetSize 按包围盒最长边选(≤150 A4/≤300 A3/≤600 A2/≤1200 A1,取不到A3)。枚举 A4=8/A3=6/A2=4/A1=2/A0=0。

技术要求:模板常自带一处,出图前 _drawing_has_tech_requirements(遍历 view.GetNotes()→GetText() 含"技术要求"/"TECHNICAL REQUIREMENT")检测,已有则跳过写入避免两处。无自带才 InsertNote 左下(0.02,0.02)。

长宽高兜底:dim_count<=0 触发。根因:真机 IModelDoc2/Extension 均无可靠 GetBox,旧 ext.GetBox(0) 全抛异常→(0,0,0)兜底失败。正确 _read_part_box6:①IPartDoc.GetPartBox(True) ②GetBodies2(0,True)→IBody2.GetBodyBox() 求并集 ③兼容旧 mock GetBox(0),_valid_box6 过滤退化盒。三向跨度米×1000 从大到小 L/W/H,InsertNote 右下(0.18,0.02)。覆盖不了圆直径。真机只能 Windows+SW 验证。