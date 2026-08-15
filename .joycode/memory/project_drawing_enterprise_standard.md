---
name: 3D转2D企业标准出图链路
description: 'AI-Enterprise 点击3D转2D的全链路:尺寸+公差+图幅+技术要求+长宽高兜底关键约定'
type: project
---

链路:插件→POST /api/create_drawing→KnowledgeCache 取 rules→create_drawing_from_active_part(app,rules)。云端口=8800,knowledge_cache DEFAULT_BASE_URL 须同为8800(env AI_SW_CLOUD_URL 覆盖)。缓存TTL=1800。

尺寸:InsertModelAnnotations3 option 1=标记/2=未标记,程序化建模全未标记须传3;返回不可靠用 _count_display_dimensions 核实;逐视图补导入前须 ActivateView(GetName2())。期望效果=俯视图标长宽+孔距孔径、侧视图标厚度(见用户参考图)。

整体轮廓尺寸补打:自动导入常只有孔距/孔径,整体长宽高不齐。_insert_overall_view_dimensions 用 _classify_three_views(靠各视图 GetOutline() 中心相对位置判 front/top/right,不靠命名)→俯视图 AddHorizontalDimension2 打长+AddVerticalDimension2 打宽,右视图 AddVerticalDimension2 打高。

图幅:Sheet.SetSize 按包围盒最长边(≤150 A4/≤300 A3/≤600 A2/≤1200 A1)。枚举 A4=8/A3=6/A2=4/A1=2/A0=0。

技术要求:彻底不写,完全沿用模板自带(用户明确要求)。_insert_tech_requirements_note/_drawing_has_tech_requirements 已成死代码;_build_tech_requirements_text 仅单测引用保留。

长宽高文字兜底:dim_count<=0 才触发。真机 IModelDoc2/Extension 无可靠 GetBox。_read_part_box6:①GetPartBox(True) ②GetBodies2(0,True)→GetBodyBox 并集 ③兼容旧 mock。所有 COM 改动只能 Windows+SW 真机验证。