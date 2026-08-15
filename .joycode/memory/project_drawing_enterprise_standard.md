---
name: 3D转2D企业标准出图链路
description: 'AI-Enterprise 点击3D转2D的全链路:尺寸+公差+图幅+技术要求+长宽高兜底关键约定'
type: project
---

3D转2D=三视图+导入模型尺寸+企业标准公差+图幅+技术要求+长宽高兜底。

链路:插件→POST /api/create_drawing→从 KnowledgeCache 取 rules→create_drawing_from_active_part(app,rules)。云端口=8800,knowledge_cache DEFAULT_BASE_URL 须同为8800(env AI_SW_CLOUD_URL 覆盖),不一致报 WinError 10061。缓存TTL=1800守护幂等,不可达沿用旧缓存。

InsertModelAnnotations3 option 位标志:1=标记为工程图尺寸,2=未标记。程序化/AI建模零件默认全未标记,只传1一条都导不进但返回非None误判成功。必须传 1|2=3;用 _count_display_dimensions 遍历实际条数核实。返回{dim_count,grade,tol_applied}。

图幅:模板走SW默认.drwdot不切换,用 Sheet.SetSize 按包围盒最长边选(≤150 A4/≤300 A3/≤600 A2/≤1200 A1,超A1,取不到A3)。枚举 A4=8/A3=6/A2=4/A1=2/A0=0。

公差:params_json"公差等级"(IT8)/tolerance_grade,裸数字补IT。技术要求:_build_tech_requirements_text 读未注公差三档(默认±0.02/0.05/0.10)+粗糙度五级+技术要求列表,无配置默认兜底,InsertNote 左下(0.02,0.02)米。

长宽高兜底(最低要求):dim_count<=0 触发,_get_part_bbox_dims_mm 取 GetBox(0) 三向跨度(米×1000,从大到小 L/W/H),InsertNote 右下(0.18,0.02)米。兜底覆盖不了圆直径。COM 全 except 兜底;真机只能 Windows+SW 验证。