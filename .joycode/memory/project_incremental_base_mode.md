---
name: 增量模式 assume_existing_base
description: 在当前已打开 SW 零件上继续开槽、放宽 base solid 校验的全链路
type: project
---

方案A（用户选定）：支持在当前已打开 SW 零件上继续开槽/开孔，无需重建底板，放宽 cut_slot 等 solid-body 依赖算子对 base solid 校验。用 metadata 字段最小侵入贯穿 generate→validate→execute。

链路：`PlanMetadata.assume_existing_base:bool`(featureplan.py from_dict/to_dict)；operation_planner `plan_operations` base raise 加守卫 `if not assume_existing_base: raise "requires a completed base solid"`；http_service `_apply_incremental_base_flag(plan, active_document)`——payload 带 active_document(has_solid_body/part_name/body_count>0) 且计划无 base 算子(_BASE_SOLID_OPS={create_base_plate,extrude_boss}) 时写 metadata.assume_existing_base=True，在 `_handle_generate_plan` plan 生成后调用。测试：test_api_executor_planning.py 的 test_cut_slot_without_base_allowed_in_incremental_mode / ..._still_blocked_without_incremental_flag。

安全：仅有标志且计划无 base 算子才放宽，无标志缺 base 仍 raise。待落地：插件端实际传 active_document；executor 执行仍需 SW 当前零件确有实体，须 Windows 端到端验证。