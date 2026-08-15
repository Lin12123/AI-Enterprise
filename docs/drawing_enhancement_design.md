# 进阶版 2D 工程图智能出图 — 分阶段设计方案（评审稿）

> 状态：待评审 | 目标读者：项目负责人 | 关联现状：`src/solidworks_api/drawing.py` 已实现基础三视图出图

## 1. 需求与目标

在现有「3D 转 2D 出图」（生成裸三视图）基础上，做**企业级智能工程图**：

> 基于当前生成的 3D 模型，AI 根据行业标准（GB/T 14689-2024 等）与企业级标准（Q/HW 系列）
> 自动**选模板、选标注参数、补工程规范**，输出规范化的 2D 工程图文件。

拆解为四项能力：
1. **选模板**：按零件尺寸/复杂度自动选图幅（A4/A3/A2）与图框、题栏模板。
2. **选标注参数**：自动标注尺寸；按标准决定公差等级、表面粗糙度、基准与形位公差。
3. **补工程规范**：填标题栏（名称/材料/比例/图号/单位/投影法），补技术要求文字块。
4. **输出文件**：保存 .SLDDRW，并可导出 PDF/DWG（企业交付常用）。

## 2. 现状与约束（来自当前代码与记忆）

| 项 | 现状/约束 |
| --- | --- |
| 出图链路 | `create_drawing_from_active_part(app)` 5 步纯函数：取零件→保存→新建工程图→三视图→保存 |
| 服务架构 | HTTP `/api/create_drawing` → STA 工作线程 `worker.submit(timeout=300)` |
| **STA 约束** | 所有 SW COM 调用必须在专用 STA 工作线程串行执行，本模块只提供纯函数 |
| **离线约束** | 客户内网离线，LLM 只能用标准库直连本地 Ollama，禁止 openai/httpx 等第三方包 |
| **COM 兼容坑** | pywin32 下方法可能暴露为属性，需 `callable()` 判断（见 `get_doc_type`） |
| 标准数据 | 目前仅在 `diagnostics.py` 以 reference 字符串出现，无结构化规范库 |
| 验证限制 | 本机无 SW/无 C#/无 pytest，仅 `python3 -m py_compile` 验证语法；改 Python 需重启 service |

## 3. 总体架构

```
成果卡「3D转2D出图(进阶)」
      │  POST /api/create_drawing { "mode": "enhanced", "options": {...} }
      ▼
http_service._handle_create_drawing  (STA worker.submit)
      ▼
drawing.create_drawing_from_active_part(app, mode, options)
      ├─ A. 元数据提取  metadata.extract_part_metadata(model)   ← 纯 COM 读
      ├─ B. 决策引擎    drawing_rules.decide(metadata, options) ← 纯 Python 规则(+可选 LLM)
      │        └─ 产出 DrawingSpec(图幅/视图/标注策略/标题栏/技术要求)
      ├─ C. 落地执行    annotate.apply(draw_model, spec)        ← 纯 COM 写
      └─ D. 导出        export.save_and_export(spec)           ← SLDDRW + PDF/DWG
```

设计原则：
- **决策与执行分离**：B 是可单测的纯 Python（无 COM）；A/C/D 是薄 COM 封装，全 try/except。
- **规则优先、LLM 可选**：默认用固化规则表；LLM 仅在开启时对"技术要求文字/标注取舍"做增强，失败自动回退规则。
- **绝不崩溃工作线程**：任一步失败返回可读中文 message，已完成步骤尽量保留。

## 4. 数据结构（草案）

```python
# 模型元数据(纯 COM 读，A 阶段产出)
PartMetadata = {
  "title": str, "path": str,
  "bbox_mm": {"dx","dy","dz"},         # 包围盒尺寸
  "material": str,                     # GetMaterialPropertyName
  "mass_g": float, "volume_mm3": float,
  "features": [{"type","name",...}],   # 遍历 FeatureManager
  "holes": [{"dia","depth","through"}],# 供孔标注/孔表
}

# 出图规格(B 阶段决策产出，可 JSON 序列化、可单测)
DrawingSpec = {
  "paper": {"size":"A3","fmt_template":"...drwdot"},
  "projection": "third_angle",         # GB 常用第一角，可配置
  "views": ["front","top","right","iso"],
  "dim_policy": {"auto_dim": True, "tol_grade":"IT12", "decimals":1},
  "surface_finish": {"default_ra":"Ra3.2"},
  "titleblock": {"name","material","scale","drawing_no","unit":"mm","proj":"第一角"},
  "tech_notes": ["1. 未注公差按 GB/T 1804-m", "2. 未注圆角 R0.5", ...],
  "standards": ["GB/T 14689-2024","Q/HW 2026.2"],
}
```

## 5. 分阶段实施计划

### 阶段 0 — 契约与骨架（不接 COM，可先评审/单测）
- 新增 `src/solidworks_api/drawing_spec.py`：定义 `PartMetadata`/`DrawingSpec` dataclass 与 JSON 序列化。
- 新增 `src/policy/drawing_rules.py`：`decide(metadata, options) -> DrawingSpec` 纯规则（图幅按 bbox 选 A4/A3/A2；tech_notes 按标准模板拼装）。
- 扩展 `/api/create_drawing` 入参 `mode`（`basic`/`enhanced`）与 `options`，`basic` 走现有逻辑不变。
- 单测：`tests/test_drawing_rules.py`（纯 Python，可本机跑 unittest）。
- **交付即可评审**，零 SW 依赖。

### 阶段 1 — 元数据提取（COM 读，最小风险）
- 新增 `src/solidworks_api/part_metadata.py`：`extract_part_metadata(model)`。
- COM 接口：`GetBox`/`Extension.GetMassProperties`/`GetMaterialPropertyName2`/遍历 `FirstFeature().GetNextFeature()`。
- 全部 `callable()` 兼容 + try/except，取不到给缺省值，绝不抛异常。
- 真机验证：出图流程先把 metadata 打进返回 message/日志，人工核对准确性。

### 阶段 2 — 智能选模板与标题栏
- `_new_drawing_doc` 支持按 `DrawingSpec.paper` 选图幅与图框模板（扫描 `.drwdot` 命名匹配 A3/A4）。
- 填标题栏：`draw_model` 找到 SheetFormat 的注释/属性，用 `CustomPropertyManager` 或 note 写入名称/材料/比例/图号/投影法。
- 兜底：无企业模板时用 SW 自带模板 + 程序化插入标题栏文字块。

### 阶段 3 — 自动尺寸标注 + 表面粗糙度
- 尺寸：视图上 `IView.InsertModelDimensions`/`Extension.InsertModelAnnotations3` 导入模型尺寸，再做重叠清理。
- 公差：按 `dim_policy.tol_grade` 对关键尺寸设未注公差说明（技术要求文字 + 选配逐尺寸公差）。
- 表面粗糙度：`InsertSurfaceFinishSymbol2` 或统一在技术要求中声明默认 Ra。
- 孔标注/孔表：对 `metadata.holes` 用 `InsertHoleCallout` / 孔表（可选，阶段 3.5）。

### 阶段 4 — 技术要求文字块（规则 + 可选 LLM）
- 默认规则：按 `standards` + `material` 生成中文技术要求条目（未注公差/圆角/去毛刺/热处理占位）。
- LLM 增强（可开关）：把 `PartMetadata` 摘要喂本地 Ollama（标准库直连），输出补充条目 JSON；解析失败回退规则。
- 复用现有本地 provider（`app/providers/local_provider.py`），不引第三方包。

### 阶段 5 — 导出与交付
- `save_and_export`：SLDDRW + `Extension.SaveAs` 导出 PDF；可选 DWG。
- 输出统一落 `workspace/outputs/drawings`，`outputs` 列表返回全部产物路径。
- 前端成果卡展示多产物链接（复用现有 message 渲染）。

## 6. 前端改动（C#）
- `ResultBoardPanel`/`AiSwTaskPaneControl`：出图按钮可加"基础/进阶"选择或直接默认进阶。
- `ServiceClient.CreateDrawingAsync` 支持传 `mode`/`options` JSON（当前是空体 `{}`）。
- 复用现有 `ExtractMessage`/多产物展示。

## 7. 风险与开放问题（需评审拍板）
1. **投影法**：GB 传统用**第一角**，现有代码用 `Create3rdAngleViews2`（第三角）。企业标准要哪个？
2. **企业模板来源**：是否有客户提供的 `.drwdot`（含标准图框/标题栏/图号规则）？没有则需程序化画标题栏，工作量与还原度差别很大。
3. **自动标注范围**：全尺寸标注常导致视图杂乱。是"全标+人工删"还是"只标关键尺寸(孔/总长宽高)"？
4. **公差/粗糙度智能程度**：按材料+特征查表决定，还是先统一"未注公差 GB/T 1804-m + 默认 Ra3.2"？
5. **LLM 参与度**：技术要求是否要 LLM 生成？离线 Ollama 模型能力/耗时是否可接受（出图已 300s 超时）。
6. **图号规则**：图号/版本/企业编码规则是否有既定格式？

## 8. 建议评审结论选项
- **最小可用（推荐先做）**：阶段 0+1+2+3(仅总体尺寸)+5(PDF)，技术要求走规则模板，不接 LLM。
- **完整企业级**：全部阶段 + LLM 技术要求 + 孔表 + 逐尺寸公差。

请就第 7 节的开放问题给出选择，我据此细化并进入阶段 0 编码。