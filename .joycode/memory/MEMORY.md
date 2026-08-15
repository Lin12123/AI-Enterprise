- [开发环境约定](project_dev_environment.md) — AI-Enterprise 项目在 Windows 上的统一 IDE 与运行环境约定（C# 插件 + Python 服务）

- [离线 LLM 约束](project_offline_llm_constraint.md) — AI-Enterprise 客户为内网离线环境,LLM 只能用标准库直连本地 Ollama,禁止安装 openai/httpx 等第三方包

- [SW slot/pocket 选面策略](feedback_sw_slot_face_selection.md) — SolidWorks 2019 上 slot/pocket 切除的草图基准面选择必须坐标优先、特征顶面兜底，否则 InsertSketch 进不了草图

- [云平台与知识库需求决策](project_cloud_platform_kb.md) — AI-Enterprise 进阶出图的云平台+本地知识库架构已拍板的关键决策

- [本地模型 FeaturePlan 确定性修复链](project_local_plan_salvage.md) — generate_plan 对本地模型输出的确定性 salvage 链与坐标系根因

- [通槽 through slot 语义约定](project_through_slot_semantics.md) — AI-Enterprise 项目对通槽的既定几何语义，处理 slot 深度/跨度时勿弄反

- [增量模式 assume_existing_base](project_incremental_base_mode.md) — 在当前已打开 SW 零件上继续开槽、放宽 base solid 校验的全链路

- [3D转2D企业标准出图链路](project_drawing_enterprise_standard.md) — AI-Enterprise 点击3D转2D的全链路:尺寸+公差+图幅+技术要求+长宽高兜底关键约定

- [出图早绑定迭代与 v033 卡点转移](project_drawing_early_bind_v029.md) — AI-Enterprise 3D转2D出图 draw早绑定 v029→v033 根因链；v032放弃draw整体早绑定改用_sw_invoke；v033卡点从建/读视图转到标尺寸
