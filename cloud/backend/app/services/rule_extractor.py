"""规则抽取：把文档正文交给本地 LLM，理解成可供 3D 转 2D 出图调用的规则草稿。

流程
----
1. doc_extractor 抽出的正文文本 -> 构造 prompt
2. llm_client.chat_json 调本地 Ollama，要求输出 {"rules": [...]} 结构
3. 校验/清洗每条规则，字段对齐 standard_rule(scope_material/scope_feature/clause/params_json)
4. 每条 status 一律置 'draft'（LLM 有幻觉风险，必须人工确认后再发布）

失败(LLM 不可达/输出非法)时返回空列表，由上层降级为“仅存原文附件、待人工补录”。
"""
from __future__ import annotations

from typing import Any

from . import llm_client


_SYSTEM_PROMPT = (
    "你是机械制图标准解析助手。你的任务是把用户给出的“工程制图/出图标准”文档正文，"
    "理解并抽取成结构化的出图规则，供 3D 转 2D 自动出图程序调用。\n"
    "严格只输出 JSON，不要输出任何解释或 Markdown。\n"
    "输出格式：{\"rules\": [{\"scope_material\": 字符串或null, \"scope_feature\": 字符串或null, "
    "\"clause\": 规则的简短中文描述, \"params_json\": {键值对参数}}]}\n"
    "字段说明：\n"
    "- scope_material：该规则适用的材料(如 45钢/铝合金)，无法判断填 null。\n"
    "- scope_feature：该规则适用的特征或场景(如 孔/键槽/图纸幅面)，无法判断填 null。\n"
    "- clause：一句话描述这条规则要求了什么。\n"
    "- params_json：把可量化的要求整理成键值对，例如 {\"图幅\":\"A3\",\"比例\":\"1:2\","
    "\"投影法\":\"第一角\",\"公差等级\":\"IT8\"} 等；没有可量化参数时给空对象 {}。\n"
    "只抽取文档中明确出现的信息，不要编造。若文档没有可用规则，输出 {\"rules\": []}。"
)


def extract_rules_from_text(text: str) -> list[dict[str, Any]]:
    """把正文文本抽取成规则草稿列表(status='draft')。失败或无内容时返回 []。"""
    text = (text or "").strip()
    if not text:
        return []

    user_prompt = (
        "以下是标准文档正文，请抽取出图规则并按要求的 JSON 结构返回：\n\n" + text
    )
    try:
        result = llm_client.chat_json(_SYSTEM_PROMPT, user_prompt)
    except llm_client.LlmUnavailable:
        # LLM 不可达/输出非法：交由上层降级(仅存附件、人工补录)
        return []

    raw_rules = result.get("rules")
    if not isinstance(raw_rules, list):
        return []

    cleaned: list[dict[str, Any]] = []
    for item in raw_rules:
        rule = _normalize_rule(item)
        if rule is not None:
            cleaned.append(rule)
    return cleaned


def _normalize_rule(item: Any) -> dict[str, Any] | None:
    """校验并规范化单条规则；非法项(无 clause)丢弃，返回 None。"""
    if not isinstance(item, dict):
        return None

    clause = _clean_str(item.get("clause"))
    if not clause:
        # clause 是规则的核心描述，缺失则视为无效
        return None

    params = item.get("params_json")
    if not isinstance(params, dict):
        # 容错：模型偶尔把参数放成字符串/列表
        params = {"raw": params} if params not in (None, "", []) else {}

    return {
        "scope_material": _clean_str(item.get("scope_material")),
        "scope_feature": _clean_str(item.get("scope_feature")),
        "clause": clause,
        "params_json": params,
        "status": "draft",  # 抽取产物一律草稿，人工确认后再发布
    }


def _clean_str(value: Any) -> str | None:
    """把值规范成去空白字符串；空/占位(null/none/无)归一为 None。"""
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("null", "none", "n/a", "na", "无", "不适用"):
        return None
    return s