---
name: SW slot/pocket 选面策略
description: SolidWorks 2019 上 slot/pocket 切除的草图基准面选择必须坐标优先、特征顶面兜底，否则 InsertSketch 进不了草图
type: feedback
---

slot/pocket 切除选草图基准面时，必须**坐标选面优先、重读特征顶面兜底**，顺序为：
1. 按 slot/pocket 自身 center 坐标点选面(select_face_by_point_candidates)
2. 退 (0,0,z) 顶面(select_face_by_z)
3. 最后才退重读 base 特征取顶面(select_feature_top_face)

**Why:** SW2019 上「重读之前的 base COM 特征对象再 GetFaces」不稳定——base 经过多次孔/slot 切除后，原始顶面 face 对象会失效/被替换，Select4 选中的是过期面，InsertSketch 便进不了草图态，报 sketch_diag「无法获取活动草图对象」，最终 FeatureCut3 返回 None。成功的孔特征(cut_corner_holes / cut_center_hole)都明确注释优先用坐标选面。曾经把 select_feature_top_face 当首选，真机复跑仍失败，方向搞反了。

**How to apply:** 改 src/solidworks_api/features/cut.py 的 _try_select_slot_face_by_center 等选面逻辑时，坚持坐标优先；不要因为「孔用了 select_feature_top_face 兜底成功」就把它提为首选。