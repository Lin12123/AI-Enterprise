---
name: 本地模型 FeaturePlan 确定性修复链
description: generate_plan 对本地模型输出的确定性 salvage 链与坐标系根因
type: project
---

本地模型 FeaturePlan 经确定性 salvage 链修复到 Policy 放行，避免 generate_plan 500。链在 app/providers/local_provider.py `_attempt_semantic_salvage`，顺序：normalize→convert_corner_to_center(须在 bind 之前)→normalize→bind→normalize→clamp 越界孔→normalize→policy。

确定性修正(纯几何/别名/兜底，合规)：角点→中心坐标系 `_convert_corner_to_center_coordinates`(严格判定：存在越界孔且全 center 减半板尺寸后落合法区间才整体平移)；越界孔 epsilon(0.01)+单轴钳制；算子名归一化 OP_NAME_ALIASES；create_center_boss 缺 height→base_thickness 兜底；cut_slot length<=width→提升 width×2；顶层单算子平铺 `_promote_top_level_single_operation`。

Why：客户内网离线只能代码层确定性修正，纯 prompt 教育本地模型不可靠。How：新缺陷优先 bind 层或 salvage 链加确定性修正；坐标类务必放 bind 之前；判定须严格可验证避免误改合法 plan；改动需 Windows 重启验证 SW 建模。根因：500 第四次真因是角点坐标系。Python 3.9 环境(ui_desktop 测试缺 StrEnum ImportError 属环境非代码)。---
name: 本地模型 FeaturePlan 确定性修复链
description: AI-Enterprise generate_plan 对 qwen2.5-coder 输出缺陷的确定性 salvage 修复链与角点坐标系根因
type: project
---

本地模型 qwen2.5-coder:7b 的 FeaturePlan 经确定性 salvage 链修复到 Policy 可放行，避免 generate_plan 500。链在 app/providers/local_provider.py `_attempt_semantic_salvage`。

**链顺序**：normalize → convert_corner_to_center（必须在 bind 之前，否则与 bind 内置 center 处理双重转换）→ normalize → bind → normalize → clamp 越界孔 → normalize → policy。

**已实现确定性修正**（纯几何/别名/兜底，非语义推断，合规）：
- 角点→中心坐标系转换 `_convert_corner_to_center_coordinates`：模型常以底板左下角为原点致孔越界；判定严格（存在越界孔且所有 center 减半板尺寸后全落合法区间才整体平移），覆盖圆孔+矩形算子。
- 越界孔 epsilon(0.01)+单轴钳制（仅非 explicit center）。
- 算子名归一化 OP_NAME_ALIASES：create_slot→cut_slot、create_pocket→cut_rectangle_pocket。
- create_center_boss 缺 height → base_thickness 兜底。
- cut_slot length<=width → 提升 length 到 width×2（受板方向半尺寸约束），满足 Policy 严格 length>width。

**Why**：客户内网离线只能纯 prompt 教育本地模型不可靠，须代码层确定性修正。

**How to apply**：新缺陷优先在bind 层或 salvage 链加确定性修正；坐标类务必放 bind 之前；判定须严格可验证避免误改合法 plan；改动需 Windows 重启验证 SW 建模。根因：500 第四次真因是角点坐标系（first_pass 算子名本正确，repair 循环才恶化）；修好 first_pass 绕开 repair 更有效。回归基线 140+27。