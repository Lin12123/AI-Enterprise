---
name: 3D转2D企业标准出图链路
description: AI-Enterprise 点击3D转2D时从云平台取标准并驱动尺寸+公差标注的全链路与关键约定
type: project
---

3D转2D出图已升级为"企业级智能工程图"：三视图 + 导入模型尺寸 + 依企业标准公差。

**链路**：插件成果看板 DrawClicked → ServiceClient.CreateDrawingAsync(POST /api/create_drawing) → http_service._handle_create_drawing 从 KnowledgeCache 取 rules → create_drawing_from_active_part(app, rules=rules) → _insert_three_views 后调 _apply_dimensions_and_tolerance(InsertModelAnnotations3 导入尺寸 + 按公差等级设对称公差) → 保存 DRAWINGS_DIR。

**知识缓存**(service/knowledge_cache.py)：TTL=1800(30分钟)；start_background_refresh(interval_seconds=None) 守护线程,启动立即force刷新+每interval循环,幂等；_log 带 `[时间] [知识库]` 时间戳；云平台不可达沿用旧缓存(stale)不阻断；http_service.serve() 启动接入。

**公差等级解析**：rule.params_json(dict或JSON串) 中文键"公差等级"(如IT8)或英文 tolerance_grade；_extract_tolerance_grade 取首个命中,裸数字补IT前缀；_IT_GRADE_DEFAULT_TOL_MM 给默认对称公差(mm)。

**Why**：客户内网离线,标准由云平台统一下发,出图须符合企业制图规范(公差/投影法)。
**How to apply**：改出图/标准相关时,尺寸公差 COM 调用必须 except 兜底降级(不阻断出图);params_json 中文键名需与云平台 /api/knowledge/pull 契约对齐;真机 InsertModelAnnotations3/公差API 只能 Windows+SolidWorks 验证,离线单测只覆盖 _extract_tolerance_grade 与预取幂等。