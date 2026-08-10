# AI-SolidWorks 企业版：工程师常用零件建模操作分类与 API 打通需求文档

## 1. 文档目标

本阶段目标是将当前项目从“少量固定特征自动建模”升级为“工程师常用零件建模能力库”。

系统最终应支持用户通过自然语言描述零件需求，由 AI 生成受控的 FeaturePlan，再经过 Policy Engine 校验，最后由 SolidWorks API Executor 自动完成零件建模。

核心链路为：

用户自然语言
→ 结构化 FeaturePlan
→ Schema Validator
→ Policy Engine
→ Feature Registry
→ SolidWorks API Executor
→ SolidWorks 自动建模
→ 保存、导出、预览、日志

重要原则：

1. AI 不能直接生成并执行 SolidWorks API 代码。
2. AI 只能生成 FeaturePlan。
3. 所有 FeaturePlan 必须经过白名单校验。
4. API Executor 只能执行 implemented 状态的能力。
5. scaffolded/planned 能力不能执行。
6. 所有建模文件默认保存到 workspace/outputs。
7. 不允许覆盖原始模型文件。
8. 不允许用户通过自然语言传入任意保存路径。
9. 所有尺寸统一以 mm 表达，进入 SolidWorks API 前统一转换为 m。
10. 每个 API 能力必须有 schema、policy、executor、test、docs。

---

# 2. 工程师新建零件时的常用操作总览

工程师新建零件时，常用操作可以分为以下大类：

1. 新建与模板设置
2. 基准与参考几何
3. 草图绘制
4. 草图约束与尺寸
5. 基础实体特征
6. 切除类特征
7. 孔类特征
8. 边缘处理特征
9. 阵列与镜像
10. 形体修改特征
11. 多实体与布尔操作
12. 材料、属性与外观
13. 特征编辑与参数修改
14. 模型校验
15. 文件保存、导出与预览
16. 标准零件模板与企业特征库

---

# 3. 第一类：新建与模板设置

## 3.1 常用工程师操作

1. 新建零件。
2. 选择零件模板。
3. 设置单位为 mm。
4. 设置材料。
5. 设置零件名称、图号、版本、作者等属性。
6. 保存为新文件。
7. 基于企业模板创建零件。

## 3.2 建议 FeaturePlan operation

* create_new_part
* set_unit_system
* set_material
* set_custom_property
* save_part
* export_part

## 3.3 参数示例

```json
{
  "op": "create_new_part",
  "params": {
    "template": "enterprise_part_mm",
    "part_name": "motor_mount_base"
  }
}
```

## 3.4 注意事项

1. 模板必须是 .prtdot 文件。
2. 模板路径不能由用户自然语言直接指定。
3. 模板必须来自企业模板白名单。
4. 默认单位应使用 mm。
5. 新建文件不能覆盖已有文件。
6. 文件名需要自动加版本号。
7. API 新建失败时，应提示“默认零件模板无效”，不要直接归因于模型失败。
8. 不允许打开用户任意路径下的未知文件。

## 3.5 优先级

P0，必须优先实现。

---

# 4. 第二类：基准与参考几何

## 4.1 常用工程师操作

1. 选择 Top Plane、Front Plane、Right Plane。
2. 新建偏移基准面。
3. 新建角度基准面。
4. 新建通过点/线/面的基准面。
5. 新建基准轴。
6. 新建参考点。
7. 使用已有面作为草图平面。
8. 使用圆柱面轴线作为参考轴。

## 4.2 建议 FeaturePlan operation

* select_plane
* create_offset_plane
* create_angle_plane
* create_mid_plane
* create_axis
* create_point
* select_face_as_sketch_plane
* select_axis_from_cylinder

## 4.3 参数示例

```json
{
  "op": "create_offset_plane",
  "params": {
    "base_plane": "Top",
    "offset": 25
  }
}
```

## 4.4 注意事项

1. 所有基准必须可命名。
2. 不允许使用模糊选择，例如“选那个面”。
3. 需要建立稳定的选择器 selector，例如 top_face、bottom_face、front_face、largest_face。
4. 如果面选择不唯一，必须拒绝执行并要求用户补充条件。
5. 后续特征必须能引用前面创建的基准面、基准轴和草图。

## 4.5 优先级

P1，基础特征稳定后实现。

---

# 5. 第三类：草图绘制

## 5.1 常用工程师操作

1. 创建 2D 草图。
2. 创建 3D 草图。
3. 绘制中心矩形。
4. 绘制角点矩形。
5. 绘制圆。
6. 绘制圆弧。
7. 绘制直线。
8. 绘制中心线。
9. 绘制槽。
10. 绘制多边形。
11. 绘制样条曲线。
12. 创建点。
13. 使用偏移实体。
14. 转换实体引用。
15. 修剪草图实体。
16. 镜像草图实体。
17. 线性阵列草图实体。
18. 圆周阵列草图实体。

## 5.2 建议 FeaturePlan operation

* create_sketch
* sketch_center_rectangle
* sketch_corner_rectangle
* sketch_circle
* sketch_arc
* sketch_line
* sketch_centerline
* sketch_slot
* sketch_polygon
* sketch_spline
* sketch_point
* sketch_offset_entities
* sketch_convert_entities
* sketch_trim
* sketch_mirror
* sketch_linear_pattern
* sketch_circular_pattern

## 5.3 参数示例

```json
{
  "op": "sketch_center_rectangle",
  "params": {
    "sketch": "sketch_base",
    "center": [0, 0],
    "length": 120,
    "width": 80
  }
}
```

```json
{
  "op": "sketch_circle",
  "params": {
    "sketch": "sketch_hole",
    "center": [0, 0],
    "diameter": 10
  }
}
```

## 5.4 注意事项

1. 草图必须绑定到明确平面或明确面。
2. 草图轮廓必须闭合，才能用于拉伸或切除。
3. 所有草图实体建议命名，方便后续引用。
4. 草图尺寸应参数化，不要只画几何不加尺寸。
5. 草图中不能出现自交轮廓。
6. 复杂草图建议先拆解为多个简单 operation。
7. 圆、矩形、槽是 P0/P1 优先能力。
8. 样条曲线和复杂轮廓属于后续能力，不作为第一批。

## 5.5 优先级

P0：矩形、圆、线、中心线
P1：槽、圆弧、多边形、偏移、转换实体
P2：样条、复杂修剪、草图阵列

---

# 6. 第四类：草图约束与尺寸

## 6.1 常用工程师操作

1. 添加水平约束。
2. 添加垂直约束。
3. 添加重合约束。
4. 添加同心约束。
5. 添加相等约束。
6. 添加平行约束。
7. 添加垂直关系。
8. 添加对称约束。
9. 添加固定约束。
10. 添加尺寸。
11. 修改尺寸。
12. 将尺寸命名为可控参数。

## 6.2 建议 FeaturePlan operation

* add_dimension
* add_named_dimension
* modify_dimension
* add_relation_horizontal
* add_relation_vertical
* add_relation_coincident
* add_relation_concentric
* add_relation_equal
* add_relation_parallel
* add_relation_perpendicular
* add_relation_symmetric
* fully_define_sketch

## 6.3 参数示例

```json
{
  "op": "add_named_dimension",
  "params": {
    "target": "base_length_dimension",
    "name": "D_base_length",
    "value": 120
  }
}
```

## 6.4 注意事项

1. 尺寸名称要稳定，便于后续 ModifyPlan 修改。
2. 建议企业版优先建立命名尺寸体系，例如 D_base_length、D_base_width、D_hole_diameter。
3. 不能允许 AI 任意修改所有尺寸，必须经过可修改参数白名单。
4. 草图应尽量完全定义，避免后续特征失败。
5. 如果尺寸冲突，应拒绝执行并返回冲突信息。

## 6.5 优先级

P1，尤其是命名尺寸和修改尺寸能力。

---

# 7. 第五类：基础实体特征

## 7.1 常用工程师操作

1. 拉伸凸台/基体。
2. 中面拉伸。
3. 薄壁拉伸。
4. 旋转凸台。
5. 扫描凸台。
6. 放样凸台。
7. 边界凸台。
8. 创建圆柱体。
9. 创建长方体。
10. 创建法兰盘基础体。
11. 创建轴类基础体。
12. 创建支架类基础体。

## 7.2 建议 FeaturePlan operation

* extrude_boss
* extrude_midplane_boss
* extrude_thin_boss
* revolve_boss
* sweep_boss
* loft_boss
* boundary_boss
* create_box
* create_cylinder
* create_flange_base
* create_shaft_base
* create_bracket_base

## 7.3 参数示例

```json
{
  "op": "extrude_boss",
  "params": {
    "sketch": "sketch_base",
    "depth": 12,
    "direction": "one_side"
  }
}
```

```json
{
  "op": "revolve_boss",
  "params": {
    "profile_sketch": "shaft_profile",
    "axis": "center_axis",
    "angle": 360
  }
}
```

## 7.4 注意事项

1. 拉伸需要闭合草图。
2. 旋转需要明确旋转轴。
3. 扫描需要 profile 和 path。
4. 放样需要多个截面草图。
5. 薄壁特征需要壁厚校验。
6. depth 不能为负数。
7. 拉伸方向必须明确。
8. 多实体操作需要明确 merge_result 是否合并实体。
9. 复杂特征应拆解为“草图准备 + 实体特征”两步。

## 7.5 优先级

P0：extrude_boss、create_box、create_cylinder
P1：revolve_boss、extrude_thin_boss
P2：sweep_boss、loft_boss、boundary_boss

---

# 8. 第六类：切除类特征

## 8.1 常用工程师操作

1. 拉伸切除。
2. 贯穿切除。
3. 指定深度切除。
4. 双向切除。
5. 旋转切除。
6. 扫描切除。
7. 放样切除。
8. 矩形口袋。
9. 圆形凹槽。
10. 台阶切除。
11. 开槽。
12. 减重孔。
13. 异形轮廓切除。

## 8.2 建议 FeaturePlan operation

* extrude_cut
* through_all_cut
* blind_cut
* bidirectional_cut
* revolve_cut
* sweep_cut
* loft_cut
* cut_rectangle_pocket
* cut_circular_pocket
* cut_step
* cut_slot
* cut_lightening_holes
* cut_profile

## 8.3 参数示例

```json
{
  "op": "through_all_cut",
  "params": {
    "sketch": "sketch_center_hole",
    "direction": "normal"
  }
}
```

```json
{
  "op": "cut_rectangle_pocket",
  "params": {
    "plane": "top_face",
    "center": [0, 0],
    "length": 40,
    "width": 20,
    "depth": 5
  }
}
```

## 8.4 注意事项

1. 切除轮廓必须在已有实体上。
2. 贯穿切除方向必须明确。
3. 盲孔/盲槽深度不能超过实体厚度，除非允许贯穿。
4. 口袋切除需要保留最小壁厚。
5. 开槽需要校验槽宽、槽长、端部半径。
6. 异形切除建议先在 dry_run 中检查草图闭合性。
7. 切除失败时要返回具体是草图失败、选择面失败还是特征失败。

## 8.5 优先级

P0：extrude_cut、through_all_cut、blind_cut
P1：slot、pocket、step cut
P2：revolve_cut、sweep_cut、loft_cut

---

# 9. 第七类：孔类特征

## 9.1 常用工程师操作

1. 简单通孔。
2. 盲孔。
3. 沉孔。
4. 沉头孔。
5. 螺纹孔。
6. 锥孔。
7. 孔向导孔。
8. 四角孔。
9. 圆周孔阵列。
10. 线性孔阵列。
11. 法兰螺栓孔。
12. 定位销孔。
13. 长圆孔。
14. 腰型孔。
15. 中心孔。
16. 安装孔。
17. M 系列标准孔。

## 9.2 建议 FeaturePlan operation

* create_simple_hole
* create_through_hole
* create_blind_hole
* create_counterbore_hole
* create_countersink_hole
* create_tapped_hole
* create_dowel_pin_hole
* create_corner_hole_pattern
* create_circular_hole_pattern
* create_linear_hole_pattern
* create_bolt_circle_holes
* create_slot_hole
* create_center_hole

## 9.3 参数示例

```json
{
  "op": "create_through_hole",
  "params": {
    "plane": "top_face",
    "center": [0, 0],
    "diameter": 10
  }
}
```

```json
{
  "op": "create_bolt_circle_holes",
  "params": {
    "plane": "top_face",
    "center": [0, 0],
    "bolt_circle_diameter": 60,
    "hole_diameter": 6.6,
    "count": 6,
    "start_angle": 0
  }
}
```

## 9.4 注意事项

1. 孔径必须小于所在实体宽度/厚度的合理比例。
2. 孔中心不能超出实体边界。
3. 孔边距必须满足最小边距规则。
4. 通孔、盲孔、沉孔、沉头孔、螺纹孔必须区分清楚。
5. M6 通孔不等于直径 6 mm，企业库应定义标准间隙孔径。
6. 螺纹孔应区分建模螺纹和注释螺纹。
7. 孔向导相关能力建议作为 P2，先实现简单孔和标准孔库。
8. 孔阵列应优先复用 pattern 能力，而不是重复创建多个单孔。
9. 所有标准孔应进入企业特征库。

## 9.5 优先级

P0：简单通孔、盲孔、中心孔、四角孔
P1：沉孔、沉头孔、圆周孔阵列、线性孔阵列、标准 M 系列孔
P2：孔向导、螺纹孔、复杂标准孔

---

# 10. 第八类：边缘处理特征

## 10.1 常用工程师操作

1. 添加圆角。
2. 添加倒角。
3. 等半径圆角。
4. 变半径圆角。
5. 面圆角。
6. 完整圆角。
7. 指定边圆角。
8. 外轮廓圆角。
9. 内角圆角。
10. 单距离倒角。
11. 距离-角度倒角。
12. 双距离倒角。

## 10.2 建议 FeaturePlan operation

* add_fillet
* add_constant_radius_fillet
* add_variable_radius_fillet
* add_face_fillet
* add_full_round_fillet
* add_chamfer
* add_distance_chamfer
* add_distance_angle_chamfer
* add_two_distance_chamfer

## 10.3 参数示例

```json
{
  "op": "add_fillet",
  "params": {
    "target": "outer_edges",
    "radius": 3
  }
}
```

```json
{
  "op": "add_chamfer",
  "params": {
    "target": "outer_edges",
    "distance": 2,
    "angle": 45
  }
}
```

## 10.4 注意事项

1. target 必须来自受控选择器。
2. 不允许模糊选择“所有边”，应区分 outer_edges、top_edges、bottom_edges、selected_edges。
3. 圆角半径不能大于局部壁厚或特征尺寸。
4. 倒角距离不能大于相邻边可用长度。
5. 如果边选择数量为 0，应拒绝执行。
6. 如果边选择数量过多，应提示用户确认。
7. 圆角/倒角建议放在特征树后段执行。
8. 对复杂模型，圆角失败概率较高，应有失败回滚或跳过策略。

## 10.5 优先级

P0：constant radius fillet
P1：chamfer
P2：variable radius fillet、face fillet、full round fillet

---

# 11. 第九类：阵列与镜像

## 11.1 常用工程师操作

1. 线性阵列特征。
2. 圆周阵列特征。
3. 草图阵列。
4. 孔阵列。
5. 镜像特征。
6. 镜像实体。
7. 表驱动阵列。
8. 曲线驱动阵列。
9. 填充阵列。

## 11.2 建议 FeaturePlan operation

* create_linear_pattern
* create_circular_pattern
* create_sketch_linear_pattern
* create_sketch_circular_pattern
* create_hole_pattern
* mirror_feature
* mirror_body
* create_table_pattern
* create_curve_driven_pattern
* create_fill_pattern

## 11.3 参数示例

```json
{
  "op": "create_linear_pattern",
  "params": {
    "seed_feature": "hole_001",
    "direction": "x",
    "count": 4,
    "spacing": 20
  }
}
```

```json
{
  "op": "create_circular_pattern",
  "params": {
    "seed_feature": "hole_001",
    "axis": "center_axis",
    "count": 6,
    "angle": 360
  }
}
```

## 11.4 注意事项

1. seed_feature 必须存在。
2. 阵列方向必须明确。
3. 阵列数量必须有限制，防止过大数量导致卡死。
4. 阵列间距不能导致特征超出实体边界。
5. 圆周阵列必须有明确轴。
6. 镜像必须有明确镜像面。
7. 特征阵列优先于重复创建多个相同特征。
8. 孔阵列应作为工程常用模板优先实现。

## 11.5 优先级

P1：linear pattern、circular pattern、mirror feature
P2：table pattern、curve-driven pattern、fill pattern

---

# 12. 第十类：形体修改特征

## 12.1 常用工程师操作

1. 抽壳。
2. 筋板。
3. 拔模。
4. 包覆。
5. 缩放。
6. 移动面。
7. 删除面。
8. 替换面。
9. 分割线。
10. 分割实体。
11. 加厚曲面。
12. 相交。
13. 压印。
14. 圆顶。
15. 自由形。

## 12.2 建议 FeaturePlan operation

* add_shell
* add_rib
* add_draft
* wrap_feature
* scale_body
* move_face
* delete_face
* replace_face
* split_line
* split_body
* thicken_surface
* intersect_bodies
* indent_feature
* add_dome
* freeform_feature

## 12.3 参数示例

```json
{
  "op": "add_shell",
  "params": {
    "thickness": 2,
    "remove_faces": ["top_face"]
  }
}
```

```json
{
  "op": "add_rib",
  "params": {
    "sketch": "rib_profile",
    "thickness": 3,
    "direction": "normal_to_sketch"
  }
}
```

## 12.4 注意事项

1. 抽壳需要明确删除哪些面。
2. 抽壳厚度不能超过局部最小尺寸。
3. 筋板需要草图线或轮廓。
4. 拔模需要拔模面、中性面和角度。
5. move_face/delete_face 可能破坏模型，应默认需要人工确认。
6. 高风险形体修改建议先作为 planned，不要过早 implemented。
7. 工程常用优先级：shell、rib、draft。

## 12.5 优先级

P1：shell、rib、draft
P2：move face、delete face、split body
P3：freeform、dome、wrap

---

# 13. 第十一类：多实体与布尔操作

## 13.1 常用工程师操作

1. 创建多实体零件。
2. 合并实体。
3. 相减实体。
4. 相交实体。
5. 保存实体。
6. 分割实体。
7. 移动/复制实体。
8. 组合实体。
9. 派生零件。
10. 插入零件。

## 13.2 建议 FeaturePlan operation

* create_multibody_part
* combine_bodies_add
* combine_bodies_subtract
* combine_bodies_common
* split_body
* save_bodies
* move_copy_body
* insert_part
* derive_part

## 13.3 参数示例

```json
{
  "op": "combine_bodies_add",
  "params": {
    "target_bodies": ["body_001", "body_002"]
  }
}
```

## 13.4 注意事项

1. 多实体命名必须稳定。
2. 布尔运算前必须确认实体存在。
3. 相减操作风险较高，应先 dry_run 并展示影响。
4. save_bodies 涉及文件输出，应限制到 workspace/outputs。
5. 多实体能力对复杂零件很重要，但不应早于基础特征。

## 13.5 优先级

P2。

---

# 14. 第十二类：材料、属性与外观

## 14.1 常用工程师操作

1. 设置材料。
2. 设置密度。
3. 设置颜色。
4. 设置透明度。
5. 设置零件编号。
6. 设置描述。
7. 设置设计者。
8. 设置项目号。
9. 设置版本号。
10. 设置重量属性。
11. 计算质量、体积、重心。

## 14.2 建议 FeaturePlan operation

* set_material
* set_appearance
* set_custom_property
* set_part_number
* set_revision
* calculate_mass_properties
* validate_mass_properties

## 14.3 参数示例

```json
{
  "op": "set_material",
  "params": {
    "material": "Aluminum_6061"
  }
}
```

## 14.4 注意事项

1. 材料必须来自企业材料库。
2. 不允许用户输入任意材料路径。
3. 颜色和外观不应影响几何建模。
4. 质量属性计算可作为模型校验的一部分。
5. 企业属性字段应统一命名。

## 14.5 优先级

P1。

---

# 15. 第十三类：特征编辑与参数修改

## 15.1 常用工程师操作

1. 修改特征尺寸。
2. 修改草图尺寸。
3. 修改孔径。
4. 修改拉伸深度。
5. 修改圆角半径。
6. 修改倒角距离。
7. 抑制特征。
8. 解除抑制特征。
9. 删除特征。
10. 重命名特征。
11. 调整特征顺序。
12. 重建模型。
13. 另存为新版本。

## 15.2 建议 FeaturePlan operation

* modify_named_dimension
* modify_feature_parameter
* suppress_feature
* unsuppress_feature
* delete_feature
* rename_feature
* rebuild_model
* save_as_new_version

## 15.3 参数示例

```json
{
  "op": "modify_named_dimension",
  "params": {
    "dimension_name": "D_base_length",
    "value": 150
  }
}
```

## 15.4 注意事项

1. 修改已有模型时必须基于副本，不能直接修改原文件。
2. 只有命名尺寸和白名单特征允许修改。
3. 删除特征属于高风险操作，默认需要人工确认。
4. 修改后必须重建模型。
5. 修改前后应生成变更报告。
6. 需要记录 old_value 和 new_value。
7. 修改失败时要恢复到修改前状态。

## 15.5 优先级

P1，尤其是 modify_named_dimension。

---

# 16. 第十四类：模型校验

## 16.1 常用工程师操作

1. 检查重建是否成功。
2. 检查是否存在悬空草图。
3. 检查是否存在失败特征。
4. 检查实体数量。
5. 检查孔是否越界。
6. 检查壁厚。
7. 检查最小边距。
8. 检查干涉。
9. 检查质量属性。
10. 检查外形尺寸。
11. 截图预览。
12. 与 FeaturePlan 对比。

## 16.2 建议 FeaturePlan operation

* rebuild_model
* validate_rebuild
* validate_feature_tree
* validate_body_count
* validate_geometry_bounds
* validate_hole_positions
* validate_min_wall_thickness
* calculate_mass_properties
* capture_preview
* generate_execution_report

## 16.3 注意事项

1. 每次建模完成后必须 rebuild。
2. 如果 rebuild 失败，输出不应标记为成功。
3. 需要记录失败的 operation id。
4. 校验结果需要写入日志。
5. 关键模型建议输出 PNG 预览。
6. 工程发布前必须人工确认。

## 16.4 优先级

P0/P1，必须尽早建立。

---

# 17. 第十五类：文件保存、导出与预览

## 17.1 常用工程师操作

1. 保存 SLDPRT。
2. 导出 STEP。
3. 导出 STL。
4. 导出 Parasolid。
5. 导出 IGES。
6. 截图 PNG。
7. 生成缩略图。
8. 生成建模日志。
9. 生成执行报告。
10. 自动版本号。
11. 不覆盖已有文件。

## 17.2 建议 FeaturePlan operation

* save_sldprt
* export_step
* export_stl
* export_parasolid
* export_iges
* capture_png
* generate_thumbnail
* generate_log
* generate_report
* allocate_versioned_filename

## 17.3 参数示例

```json
{
  "outputs": {
    "save_sldprt": true,
    "export_step": true,
    "capture_png": true
  }
}
```

## 17.4 注意事项

1. 输出路径只能由系统生成。
2. 不允许用户指定 output_dir。
3. 文件名必须自动加版本号。
4. 输出失败不应影响原文件。
5. 每次输出必须记录 job_id。
6. 工程文件、导出文件和预览图应分目录保存。
7. 导出格式应在白名单内。

## 17.5 优先级

P0。

---

# 18. 第十六类：企业标准零件模板

## 18.1 常用工程师建模对象

企业常见零件可以抽象为模板：

1. 安装板。
2. 法兰盘。
3. 轴。
4. 套筒。
5. 支架。
6. L 型支架。
7. U 型支架。
8. 连接板。
9. 盖板。
10. 箱体。
11. 底座。
12. 垫块。
13. 筋板支撑件。
14. 传感器安装座。
15. 电机安装座。
16. 夹具定位块。
17. 简单钣金折弯件。
18. 圆盘类零件。
19. 铰链座。
20. 连接法兰。

## 18.2 建议 TemplatePlan operation

* create_mounting_plate
* create_flange
* create_shaft
* create_sleeve
* create_bracket_l
* create_bracket_u
* create_cover_plate
* create_enclosure_base
* create_motor_mount
* create_sensor_mount
* create_spacer_block
* create_jig_locator

## 18.3 注意事项

1. 模板不是固定零件，而是参数化零件族。
2. 模板内部仍应拆解成 FeaturePlan operations。
3. 企业模板应包含默认尺寸范围。
4. 模板应包含标准孔型、边距、材料、圆角规则。
5. 模板可以显著提升自然语言建模成功率。
6. 模板优先级高于自由组合建模。

## 18.4 优先级

P1/P2。

---

# 19. 推荐 API 打通优先级

## P0：必须最先打通

1. create_new_part
2. create_sketch
3. sketch_center_rectangle
4. sketch_circle
5. extrude_boss
6. extrude_cut
7. create_through_hole
8. add_fillet
9. save_sldprt
10. export_step
11. capture_png
12. rebuild_model
13. validate_rebuild

目标：复现 MVP 五个特征，并能稳定输出文件。

---

## P1：常用工程零件能力

1. add_chamfer
2. create_blind_hole
3. create_counterbore_hole
4. create_countersink_hole
5. cut_slot
6. cut_rectangle_pocket
7. create_linear_pattern
8. create_circular_pattern
9. mirror_feature
10. set_material
11. set_custom_property
12. modify_named_dimension
13. create_offset_plane
14. create_axis

目标：支持安装板、法兰盘、简单支架、底座、盖板等常用零件。

---

## P2：复杂零件能力

1. revolve_boss
2. revolve_cut
3. sweep_boss
4. sweep_cut
5. loft_boss
6. loft_cut
7. add_shell
8. add_rib
9. add_draft
10. split_body
11. combine_bodies
12. move_face
13. delete_face

目标：支持轴类、壳体类、带筋结构、复杂机械件。

---

## P3：高级能力

1. boundary feature
2. advanced fillet
3. variable radius fillet
4. freeform
5. wrap
6. dome
7. table pattern
8. curve-driven pattern
9. surface modeling
10. sheet metal

目标：支持高级曲面、钣金、复杂造型件。

---

# 20. Feature Registry 能力状态规范

每个能力必须记录状态：

1. implemented：已实现、已测试、可执行。
2. scaffolded：已有骨架，但不能执行。
3. planned：计划支持，尚未编码。
4. unsupported：明确暂不支持。

Registry 字段建议：

```json
{
  "op": "extrude_boss",
  "status": "implemented",
  "category": "base_feature",
  "params_schema": {},
  "executor": "solidworks_api.features.extrude.extrude_boss",
  "docs": "docs/api_cookbook/extrusion.md",
  "limitations": [],
  "risk_level": "low",
  "requires_confirmation": false
}
```

注意：

1. Executor 只能执行 implemented。
2. scaffolded/planned/unsupported 必须拒绝。
3. README 能力矩阵必须与 Registry 一致。
4. 不允许文档夸大能力。

---

# 21. FeaturePlan 设计要求

FeaturePlan 必须支持 operation list。

标准结构：

```json
{
  "version": "2.0",
  "document_type": "part",
  "unit": "mm",
  "part_name": "example_part",
  "operations": [
    {
      "id": "op_001",
      "op": "create_new_part",
      "params": {
        "template": "enterprise_part_mm"
      }
    },
    {
      "id": "op_002",
      "op": "create_sketch",
      "params": {
        "name": "sketch_base",
        "plane": "Top"
      }
    },
    {
      "id": "op_003",
      "op": "sketch_center_rectangle",
      "params": {
        "sketch": "sketch_base",
        "center": [0, 0],
        "length": 120,
        "width": 80
      }
    },
    {
      "id": "op_004",
      "op": "extrude_boss",
      "params": {
        "sketch": "sketch_base",
        "depth": 12
      }
    }
  ],
  "outputs": {
    "save_sldprt": true,
    "export_step": true,
    "capture_png": true
  }
}
```

约束：

1. operation 必须有 id。
2. op 必须来自 Registry。
3. params 必须符合 schema。
4. 禁止出现 output_dir、path、file_path、save_path、script、macro、command、python_code、vba_code、powershell。
5. unit 只能是 mm。
6. document_type 本阶段只能是 part。
7. 每个 operation 执行结果都必须记录。

---

# 22. 自然语言到 FeaturePlan 的解析要求

系统需要支持以下输入风格：

## 22.1 标准工程语言

“新建一个 120×80×12mm 的安装板，四角 M6 通孔，孔距边 15mm，中间有直径 30mm、高 25mm 的凸台，凸台中心开 10mm 通孔，外边倒 R3 圆角。”

## 22.2 口语化语言

“帮我做一个电机安装底板，大概长 120 宽 80 厚 12，四个角打 M6 孔，中间做个圆台，中心再打个孔，边缘圆一下。”

## 22.3 模板化语言

“按电机安装板模板生成，长 120，宽 80，厚 12，孔为 M6，中心凸台直径 30，高 25。”

## 22.4 修改型语言

“把上次那个安装板长度改成 150，孔距边改成 20，圆角改成 R5，另存新版本。”

解析注意：

1. 自然语言不完整时，允许使用模板默认值，但必须在计划中标注 inferred/default。
2. 高风险缺省不能自动推断，例如材料、螺纹规格、装配定位。
3. 单位缺失时默认 mm，但要记录。
4. 解析结果必须展示给用户确认。
5. 不允许自然语言直接决定文件路径。

---

# 23. Policy Engine 通用规则

Policy Engine 必须检查：

1. op 是否在 Registry。
2. op 是否为 implemented。
3. params 是否符合 schema。
4. 是否包含危险字段。
5. 尺寸是否为正数。
6. 尺寸是否在合理范围内。
7. 孔是否越界。
8. 孔边距是否满足规则。
9. 圆角/倒角是否过大。
10. 阵列数量是否超限。
11. 草图是否可闭合。
12. 输出是否安全。
13. 是否需要人工确认。
14. 是否会覆盖文件。
15. 是否修改原始文件。

危险字段包括：

* output_dir
* path
* file_path
* save_path
* script
* macro
* command
* python_code
* vba_code
* powershell
* shell
* subprocess
* delete
* remove
* overwrite

---

# 24. API Executor 实现要求

每个 operation 的实现必须包含：

1. 参数校验。
2. 单位转换。
3. SolidWorks 选择器。
4. API 调用。
5. 错误捕获。
6. OperationResult。
7. 日志。
8. dry_run 支持。
9. 单元测试。
10. 文档说明。

OperationResult 结构建议：

```json
{
  "op_id": "op_004",
  "op": "extrude_boss",
  "success": true,
  "message": "拉伸凸台创建成功",
  "created_feature_name": "Boss-Extrude1",
  "error": null
}
```

---

# 25. 文档与测试要求

每新增一个能力，必须同步新增：

1. Registry 注册。
2. 参数 schema。
3. Policy 测试。
4. Executor 实现。
5. dry_run 测试。
6. README 能力矩阵。
7. docs/api_cookbook 文档。
8. 示例 FeaturePlan。
9. 示例自然语言输入。
10. 限制说明。

每个能力的文档必须包含：

1. 功能说明。
2. 自然语言示例。
3. FeaturePlan 示例。
4. 参数说明。
5. 注意事项。
6. 当前限制。
7. 测试方式。

---

# 26. 给 Codex 的执行要求

请 Codex 按以下节奏逐步实现，不要一次性打通所有能力。

## 第一阶段：补齐 P0 能力

目标：

1. create_new_part
2. create_sketch
3. sketch_center_rectangle
4. sketch_circle
5. extrude_boss
6. extrude_cut
7. create_through_hole
8. add_fillet
9. save_sldprt
10. export_step
11. capture_png
12. rebuild_model
13. validate_rebuild

要求：

* 保持 legacy_vba 不被破坏。
* API Executor 真实执行前需要用户确认。
* dry_run 测试必须通过。
* README 能力矩阵必须更新。

## 第二阶段：补齐 P1 能力

目标：

1. add_chamfer
2. create_blind_hole
3. create_counterbore_hole
4. create_countersink_hole
5. cut_slot
6. cut_rectangle_pocket
7. create_linear_pattern
8. create_circular_pattern
9. mirror_feature
10. set_material
11. set_custom_property
12. modify_named_dimension
13. create_offset_plane
14. create_axis

## 第三阶段：补齐 P2 能力

目标：

1. revolve_boss
2. revolve_cut
3. sweep_boss
4. sweep_cut
5. loft_boss
6. loft_cut
7. add_shell
8. add_rib
9. add_draft
10. split_body
11. combine_bodies
12. move_face
13. delete_face

## 第四阶段：建立企业模板库

目标：

1. mounting_plate_template
2. flange_template
3. shaft_template
4. bracket_template
5. enclosure_template
6. motor_mount_template
7. sensor_mount_template

每个模板都应由 FeaturePlan operations 组成，不允许直接写死 API 过程。

---

# 27. 最终验收标准

本阶段完成后，系统应满足：

1. 用户能用自然语言创建常用简单零件。
2. 系统能生成 FeaturePlan v2。
3. FeaturePlan 能通过 Policy Engine 校验。
4. API Executor 能执行 implemented 能力。
5. 未实现能力会被明确拒绝。
6. README 能力矩阵真实可信。
7. 所有输出保存到 workspace/outputs。
8. 不覆盖原始文件。
9. 每次执行有日志。
10. 每个 operation 有成功/失败结果。
11. 支持 dry_run。
12. 支持逐步扩展新特征。
13. 支持未来扩展到装配体、工程图和已有模型修改。
