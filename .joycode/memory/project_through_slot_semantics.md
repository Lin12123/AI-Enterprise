---
name: 通槽 through slot 语义约定
description: AI-Enterprise 项目对通槽的既定几何语义，处理 slot 深度/跨度时勿弄反
type: project
---

项目对"通槽/through slot"的既定语义 = 沿板**跨度方向贯通**：length 覆盖整个板长/宽（由 src/cad_dsl/semantic_binding.py `_infer_slot_span_from_prompt` 处理）+ 深度方向按底板厚度兜底切除（`_infer_default_slot_depth`）。**绝不设 through_all=True**（through_all 是厚度方向贯穿，与本项目通槽语义不同）。

**Why**：曾错误地把"通槽"实现为强制 through_all=True，与两个既有测试冲突——test_semantic_binding_infers_full_slot_span_for_generic_through_slot_prompt（断言 length 全跨 + assertNotIn("through_all")）、test_semantic_binding_infers_default_slot_depth_when_missing（断言 depth 有兜底值 + assertNotIn("through_all")）。已撤销，恢复 cut_slot depth 分支 `if not through_all_is_true and not has_valid_depth` → 兜底 depth 并 pop through_all。

**How to apply**：处理 slot 缺失 depth/通槽 prompt 时走 length 全跨 + depth 厚度兜底，不要引入 through_all；改 slot 语义前先看这两个基准测试。