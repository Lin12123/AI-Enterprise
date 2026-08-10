"""Chinese UI copy for AI-SW Workbench."""

from __future__ import annotations


WINDOW_TITLE = "AI-SW Workbench - AI SolidWorks 本地工作台"

BUTTONS = {
    "generate_plan": "生成计划",
    "send": "发送",
    "regenerate": "重新生成",
    "validate": "校验",
    "dry_run": "预执行（Dry Run）",
    "real_run": "真实执行",
    "cancel": "取消任务",
    "export_log": "导出日志",
    "open_output_folder": "打开输出文件夹",
    "copy_path": "复制路径",
    "view_log": "查看日志",
    "clear_input": "清空输入",
    "use_defaults": "使用默认值",
    "manual_fill": "手动补充",
    "back": "返回上一步",
}

NAVIGATION = {
    "new_task": "新建任务",
    "task_history": "任务历史",
    "settings": "设置",
}

LABELS = {
    "provider_mode": "解析模式",
    "executor_mode": "驱动模式",
    "openai": "OpenAI",
    "local": "Local AI",
    "rule_based": "Rule Based",
    "api_executor": "API",
    "legacy_vba": "VBA",
}

SECTIONS = {
    "natural_language": "自然语言需求",
    "design_intent": "设计意图",
    "parameters": "参数确认",
    "operations": "建模步骤",
    "featureplan_json": "FeaturePlan JSON",
    "validation_result": "校验结果",
    "execution_control": "执行控制",
    "execution_log": "执行日志",
    "feedback": "执行状态反馈",
    "outputs": "输出结果",
    "job_status": "当前任务状态",
    "executor_mode": "驱动模式",
    "validation": "校验状态",
    "dry_run": "预执行状态",
    "real_run": "真实执行确认",
}

JOB_STATUS_ZH = {
    "created": "已创建",
    "planning": "正在生成计划",
    "need_user_input": "需要用户补充信息",
    "planned": "已生成计划",
    "planned_modified": "计划已修改，需重新校验",
    "validating": "正在校验",
    "validation_failed": "校验失败",
    "validation_passed": "校验通过",
    "dry_running": "正在预执行",
    "dry_run_passed": "预执行通过",
    "dry_run_failed": "预执行失败",
    "awaiting_real_run_approval": "等待真实执行确认",
    "running": "正在执行",
    "succeeded": "执行成功",
    "failed": "执行失败",
    "cancelled": "已取消",
}

MESSAGES = {
    "not_run": "未运行",
    "not_confirmed": "未确认",
    "passed": "通过",
    "failed": "失败",
    "rejected": "已拒绝",
    "need_generate_plan": "请先输入需求并生成计划。",
    "plan_generation_failed": "生成计划失败",
    "real_run_rejected": "真实执行被拒绝",
    "background_failed": "后台任务失败",
    "background_running": "正在处理，请稍候。",
    "featureplan_ready": "已生成 FeaturePlan，请继续校验或预执行。",
    "input_placeholder": "输入建模需求，例如：创建一个 120×80×12mm 的安装板，四角 M6 通孔，中间有凸台。",
    "real_run_confirmation": "预执行已通过。点击确认执行后，系统才会继续真实 SolidWorks API 执行。",
    "welcome": "描述你要建模的零件。我会按 FeaturePlan → 校验 → 预执行 → 确认执行的流程推进。",
    "need_confirmation": "当前节点需要用户确认。",
}


def tr_button(key: str) -> str:
    return BUTTONS[key]



def tr_status(status: str) -> str:
    return JOB_STATUS_ZH.get(str(status), str(status))
