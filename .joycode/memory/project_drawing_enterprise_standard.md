---
name: 3D转2D企业标准出图链路
description: AI-Enterprise 点击3D转2D时从云平台取标准并驱动尺寸+公差标注的全链路与关键约定
type: project
---

3D转2D出图为"企业级智能工程图"：三视图+导入模型尺寸+依企业标准公差。

**链路**：插件 DrawClicked → POST /api/create_drawing → _handle_create_drawing 从 KnowledgeCache 取 rules → create_drawing_from_active_part(app,rules) → _insert_three_views 后 _apply_dimensions_and_tolerance → 存 DRAWINGS_DIR。知识缓存 TTL=1800,守护线程幂等,云平台不可达沿用旧缓存不阻断。

**InsertModelAnnotations3 option 坑(关键)**：option 是位标志,1=仅"标记为工程图用途"尺寸,2=未标记。程序化/AI/宏建模零件尺寸默认全"未标记",只传1一条都导不进图(图空白),但返回非None会误判成功谎报"已标注"。必须传 1|2=3(_SW_INSERT_ALL_DIMENSIONS);成败用 _count_display_dimensions 遍历视图数实际尺寸条数核实。_apply_dimensions_and_tolerance 返回 {dim_count,grade,tol_applied} 供卡片如实展示。

**公差等级**：params_json 中文键"公差等级"(IT8)或 tolerance_grade;_extract_tolerance_grade 取首命中,裸数字补IT;_IT_GRADE_DEFAULT_TOL_MM 给默认对称公差(mm)。

**How to apply**：COM 必须 except 兜底不阻断;真机 API 只能 Windows+SW 验证。云平台后端约定端口=8800(cloud/backend uvicorn --port 8800),knowledge_cache DEFAULT_BASE_URL 必须同为 8800,可用环境变量 AI_SW_CLOUD_URL 覆盖;端口不一致会 WinError 10061"积极拒绝"。