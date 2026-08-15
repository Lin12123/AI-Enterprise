"""Local Ollama provider using the OpenAI-compatible API."""

from __future__ import annotations

import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path

from app.openai_config import safe_exception_message
from app.providers.json_utils import extract_json_object
from cad_dsl.featureplan_prompt import build_featureplan_prompt_for_request
from cad_dsl.featureplan import FeaturePlan
from cad_dsl.semantic_binding import bind_featureplan_semantics
from policy.policy_engine import PolicyEngine
from solidworks_api.operation_planner import plan_operations


DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_API_KEY = "ollama"
DEFAULT_NUM_PREDICT = 768
DEFAULT_TIMEOUT_SECONDS = 45.0
DEFAULT_FIRST_PASS_NUM_PREDICT = 2048
DEFAULT_REPAIR_NUM_PREDICT = 2048
DEFAULT_FIRST_PASS_TIMEOUT_SECONDS = 180.0
DEFAULT_REPAIR_TIMEOUT_SECONDS = 120.0

FEATURE_COMPLETENESS_HINTS = {
    "cut_corner_holes": (
        "四角孔",
        "角孔",
        "螺栓孔",
        "螺丝孔",
        "角上通孔",
        "corner hole",
        "corner holes",
        "corner through hole",
        "corner through holes",
        "bolt hole",
        "bolt holes",
    ),
    "create_center_boss": (
        "中心凸台",
        "圆柱凸台",
        "凸起平台",
        "中间凸台",
        "boss",
        "raised boss",
        "platform",
    ),
    "cut_center_hole": (
        "中心孔",
        "凸台中心孔",
        "中心通孔",
        "中间孔",
        "center hole",
        "hole at center",
    ),
    "cut_slot": ("通槽", "槽", "长槽", "slot"),
    "cut_rectangle_pocket": ("口袋", "矩形口袋", "凹槽口袋", "pocket"),
    "add_fillet": ("圆角", "倒圆", "R角", "fillet", "r1", "r2", "r3", "r4", "r5"),
    "add_chamfer": ("倒角", "chamfer", "c1", "c2", "c3", "c4", "c5"),
}

def _debug_dump_local_provider_artifact(filename: str, content: str) -> None:
    debug_dir = os.environ.get("AI_SW_LOCAL_LLM_DEBUG_DIR", "").strip()
    if not debug_dir:
        return
    try:
        target_dir = Path(debug_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / filename).write_text(str(content), encoding="utf-8")
    except Exception:
        pass


def _debug_dump_local_provider_json(filename: str, payload) -> None:
    debug_dir = os.environ.get("AI_SW_LOCAL_LLM_DEBUG_DIR", "").strip()
    if not debug_dir:
        return
    try:
        target_dir = Path(debug_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


_CLAMP_SAFETY_MARGIN_MM = 0.5  # 与 policy_engine._EDGE_SAFETY_MARGIN_MM 保持一致的材料余量
# Policy 用 `abs(x)+radius >= half-margin` 严格判越界，边界值会被判死；钳制结果需再内缩
# 一个极小 epsilon，保证 abs(x)+radius < half-margin（严格小于），才能通过 Policy 校验。
_CLAMP_BOUNDARY_EPSILON_MM = 0.01


def _plan_base_size(data: dict) -> tuple[float, float] | None:
    """从 plan 中提取底板尺寸 (length, width)，与 policy_engine 的取值逻辑一致。"""
    operations = data.get("operations") if isinstance(data, dict) else None
    if not isinstance(operations, list):
        return None
    sketch_rectangles: dict[str, tuple[float, float]] = {}
    base_size: tuple[float, float] | None = None
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        op_name = str(operation.get("op", "")).strip()
        if op_name == "sketch_center_rectangle":
            sketch_name = str(params.get("name", params.get("sketch", ""))).strip()
            try:
                length = float(params.get("length", 0))
                width = float(params.get("width", 0))
            except (TypeError, ValueError):
                length = width = 0.0
            if sketch_name and length > 0 and width > 0:
                sketch_rectangles[sketch_name] = (length, width)
        if op_name == "create_base_plate":
            try:
                base_size = (float(params.get("length", 0)), float(params.get("width", 0)))
            except (TypeError, ValueError):
                base_size = None
        if op_name == "extrude_boss" and base_size is None:
            sketch_name = str(params.get("sketch", "")).strip()
            if sketch_name in sketch_rectangles:
                base_size = sketch_rectangles[sketch_name]
    if base_size and base_size[0] > 0 and base_size[1] > 0:
        return base_size
    return None


def _hole_center_ops() -> dict[str, str]:
    """需要检测/转换 center 坐标的圆孔算子 -> 直径参数名。"""
    return {
        "create_through_hole": "diameter",
        "create_blind_hole": "diameter",
        "create_counterbore_hole": "hole_diameter",
        "create_countersink_hole": "hole_diameter",
    }


def _convert_corner_to_center_coordinates(data: dict) -> dict:
    """确定性坐标系转换：识别"角点坐标系"并整体平移到"中心坐标系"。

    本地小模型常把孔 center 写成"距底板左下角"的角点坐标（如 120x80 板四角孔
    [10,10]/[110,70]），而 Policy 用"板中心为原点"的中心坐标系（合法区间约
    x∈[-half,half]）。这会导致 Policy 判越界并 500。

    这是纯几何坐标系换算而非语义推断，判定条件严格可验证：
    - 存在至少一个孔 center 在中心坐标系下越界；
    - 且所有孔 center 减去半板尺寸 (x-half_length, y-half_width) 后**全部**落入
      合法区间；
    - 且原始孔 center 至少有一个分量为正且明显偏离中心（避免误判已在中心系的 plan）。
    仅当整体自洽时才平移，否则保持原样交由钳制/Policy 处理。
    """
    if not isinstance(data, dict):
        return data
    base_size = _plan_base_size(data)
    if base_size is None:
        return data
    operations = data.get("operations")
    if not isinstance(operations, list):
        return data

    half_length = base_size[0] / 2
    half_width = base_size[1] / 2
    center_ops = _hole_center_ops()

    # 矩形算子（槽/型腔）也有 center，一并纳入坐标系判定：其"有效半尺寸"取 x/y 方向
    # 的半边长，保证矩形边框整体在界内。
    rect_ops = {"cut_slot", "cut_rectangle_pocket"}

    # 收集所有带 center 的特征。元素: (params, x, y, half_x, half_y)
    holes: list[tuple[dict, float, float, float, float]] = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", "")).strip()
        diameter_name = center_ops.get(op_name)
        is_rect = op_name in rect_ops
        if diameter_name is None and not is_rect:
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else None
        if not isinstance(params, dict):
            continue
        center = params.get("center")
        if not isinstance(center, (list, tuple)) or len(center) != 2:
            continue
        try:
            x = float(center[0])
            y = float(center[1])
            if is_rect:
                length = float(params.get("length", 0))
                width = float(params.get("width", 0))
                if length <= 0 or width <= 0:
                    continue
                half_x = length / 2
                half_y = width / 2
            else:
                diameter = float(params.get(diameter_name, 0))
                if diameter <= 0:
                    continue
                half_x = half_y = diameter / 2
        except (TypeError, ValueError):
            continue
        holes.append((params, x, y, half_x, half_y))

    if not holes:
        return data

    def _in_bounds(cx: float, cy: float, hx: float, hy: float) -> bool:
        return (
            abs(cx) + hx < half_length - _CLAMP_SAFETY_MARGIN_MM
            and abs(cy) + hy < half_width - _CLAMP_SAFETY_MARGIN_MM
        )

    any_out = any(not _in_bounds(x, y, hx, hy) for _p, x, y, hx, hy in holes)
    if not any_out:
        return data  # 已在合法中心坐标系，无需转换

    # 检查平移后是否全部自洽。
    all_shifted_ok = all(
        _in_bounds(x - half_length, y - half_width, hx, hy)
        for _p, x, y, hx, hy in holes
    )
    if not all_shifted_ok:
        return data  # 不是角点坐标系（平移后仍越界），交给钳制处理

    # 判定为角点坐标系，整体平移到中心坐标系。
    for params, x, y, _hx, _hy in holes:
        params["center"] = [round(x - half_length, 3), round(y - half_width, 3)]

    return data


def _clamp_inferred_out_of_bounds_holes(data: dict) -> dict:
    """确定性几何钳制：把 inferred（或缺 provenance）的越界孔 center 钳到合法区间内。

    这是纯几何修正而非语义推断，不违反离线约束：
    - 仅钳制 metadata.inferred_parameters 中登记或缺失 provenance 的 center；
    - metadata.explicit_parameters（用户明确给的）保持不动，交由用户确认；
    - 保留原坐标象限（sign(x)/sign(y)），四角孔不会全部挤到中心重叠。
    """
    if not isinstance(data, dict):
        return data
    base_size = _plan_base_size(data)
    if base_size is None:
        return data
    operations = data.get("operations")
    if not isinstance(operations, list):
        return data

    metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    explicit_paths = set(str(p) for p in metadata.get("explicit_parameters", []) if isinstance(metadata.get("explicit_parameters"), list))

    half_length = base_size[0] / 2
    half_width = base_size[1] / 2

    circular_ops = {
        "create_through_hole": "diameter",
        "create_blind_hole": "diameter",
        "create_counterbore_hole": "hole_diameter",
        "create_countersink_hole": "hole_diameter",
    }

    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", "")).strip()
        diameter_name = circular_ops.get(op_name)
        if diameter_name is None:
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else None
        if not isinstance(params, dict):
            continue
        center = params.get("center")
        if not isinstance(center, (list, tuple)) or len(center) != 2:
            continue
        try:
            x = float(center[0])
            y = float(center[1])
            diameter = float(params.get(diameter_name, 0))
        except (TypeError, ValueError):
            continue
        if diameter <= 0:
            continue

        operation_id = str(operation.get("id", "")).strip()
        center_path = f"{operation_id}.params.center" if operation_id else ""
        # 用户明确给出的坐标不钳制，保持走用户确认。
        if center_path and center_path in explicit_paths:
            continue

        radius = diameter / 2
        # Policy 用 `abs(x)+radius >= half-margin` 严格判越界，故钳制目标必须严格小于
        # 该边界，多减一个 epsilon，避免钳到边界值仍被 Policy 判死。
        x_limit = half_length - _CLAMP_SAFETY_MARGIN_MM - radius - _CLAMP_BOUNDARY_EPSILON_MM
        y_limit = half_width - _CLAMP_SAFETY_MARGIN_MM - radius - _CLAMP_BOUNDARY_EPSILON_MM
        if x_limit <= 0 or y_limit <= 0:
            # 孔太大，底板放不下，几何无解，交由 Policy 拒绝 / 用户确认。
            continue

        x_out = abs(x) + radius >= half_length - _CLAMP_SAFETY_MARGIN_MM
        y_out = abs(y) + radius >= half_width - _CLAMP_SAFETY_MARGIN_MM
        if not (x_out or y_out):
            continue

        # 仅钳越界的那一轴，未越界的坐标保持原值（避免把合法坐标一起挤动）。
        new_x = x
        new_y = y
        if x_out:
            new_x = 0.0 if x == 0 else (x_limit if x > 0 else -x_limit)
        if y_out:
            new_y = 0.0 if y == 0 else (y_limit if y > 0 else -y_limit)
        params["center"] = [round(new_x, 3), round(new_y, 3)]

        # 钳制后的坐标是确定性几何修正，标记为 inferred。
        if center_path:
            inferred = metadata.get("inferred_parameters")
            if not isinstance(inferred, list):
                inferred = []
            if center_path not in inferred:
                inferred.append(center_path)
            metadata["inferred_parameters"] = inferred
            data["metadata"] = metadata

    return data


def _attempt_semantic_salvage(prompt: str, rejected_data: dict) -> dict | None:
    if not isinstance(rejected_data, dict):
        return None
    salvaged = _normalize_featureplan_protocol(rejected_data)
    # 本地小模型常把孔 center 写成"距左下角"的角点坐标（如四角孔 [10,10]/[110,70]），
    # 而 Policy 用"板中心为原点"的中心坐标系。先在语义绑定前做确定性坐标系换算（非语义
    # 推断，合规），把整体自洽的角点坐标平移到中心坐标系，避免与 bind 的 center 处理冲突。
    salvaged = _convert_corner_to_center_coordinates(salvaged)
    salvaged = _normalize_featureplan_protocol(salvaged)
    salvaged = bind_featureplan_semantics(prompt, salvaged)
    salvaged = _normalize_featureplan_protocol(salvaged)
    # 纯 prompt 教育对本地小模型不可靠：即使消息给出精确合法区间，qwen2.5-coder 仍
    # 反复越界。此处对 inferred 越界孔 center 做确定性几何钳制（非语义推断，合规）。
    salvaged = _clamp_inferred_out_of_bounds_holes(salvaged)
    salvaged = _normalize_featureplan_protocol(salvaged)
    policy_errors = _policy_error_summary(salvaged, prompt)
    if not policy_errors:
        _debug_dump_local_provider_json("semantic_salvage_featureplan.json", salvaged)
        return salvaged
    _debug_dump_local_provider_artifact("semantic_salvage_error.txt", policy_errors)
    return None

class LocalProviderError(RuntimeError):
    """Raised when local Ollama cannot produce a FeaturePlan JSON object."""


class LocalProviderOutputError(LocalProviderError):
    """Raised when local Ollama returns invalid FeaturePlan after repair."""


class LocalProviderConfirmationRequired(LocalProviderOutputError):
    """Raised when an explicit user value exceeds safe model boundaries."""


def _local_system_prompt(prompt: str = "") -> str:
    shared_prompt = build_featureplan_prompt_for_request(prompt)
    lines = [
        "You are the AI-SolidWorks FeaturePlan parser.",
        "Convert user natural language into one FeaturePlan JSON object.",
        "Output JSON only.",
        "Do not output markdown.",
        "Do not output explanations.",
        "Do not output ```json.",
        "No code fences, paths, scripts, macros, or commands.",
        "The first character must be {.",
        "The last character must be }.",
        "Top-level fields: version='2.0', unit='mm', document_type='part', part_name, metadata, operations, outputs.",
        "outputs MUST be a JSON object, never a string, array, boolean, or null.",
        "outputs may contain only boolean save_sldprt, export_step, and capture_png. Use {} when no output flags are needed.",
        "Every operation must have id, op, params, and op must come from the implemented operation set described below.",
        "Use only the implemented operations described below. Do not output scaffolded, planned, unsupported, or unknown operations.",
        "Do not output output_dir, path, file_path, save_path, script, macro, command, python_code, vba_code, powershell, shell, subprocess, delete, remove, or overwrite.",
        "LLM only creates FeaturePlan data; it must not directly control SolidWorks.",
        "Use metadata.explicit_parameters for exact user-provided params and metadata.inferred_parameters for recommended/computed params.",
        "Metadata provenance paths must use exactly this format: <operation_id>.params.<parameter>.",
        "Do not output metadata paths like create_through_hole.params.center.x, create_through_hole.params.center.y, or operation-name-based pseudo ids.",
        "For center coordinates, params.center itself must be a JSON array [x, y], not an object with x/y fields.",
        "When converting edge distance into center coordinates, mark center as inferred unless the user gave that exact coordinate.",
        "Build a completed base solid before cuts, holes, fillets, chamfers, patterns, mirrors, or output operations.",
        "Every generated operation must be directly requested by the user or clearly required to express the requested modeling intent.",
        "Do not replace one requested feature class with another. A center hole request must stay a center-hole capability, not a corner-hole capability.",
        "Do not add corner-hole operations unless the user explicitly requests corner holes, four-corner holes, bolt holes, or screw holes at the corners.",
        "Interpret M6 clearance holes, M6 bolt holes, and M6 corner holes as diameter=6.6 mm unless the user explicitly gives another hole diameter.",
        "For cut_corner_holes, always output a numeric diameter. Never leave M6 as text and never omit diameter.",
        "For cut_slot, params.length is the slot span and params.width is the slot width. length must be strictly greater than width; if your draft reverses them, swap them before returning JSON.",
        "For cut_slot, use params.direction='x' when the slot span follows the base length/X direction, and params.direction='y' when the slot span follows the base width/Y direction.",
        "If the request says the slot runs along the plate width, across the width, vertically on the top view, or 濞屽灝顔旀惔锔芥煙閸?濞屾寧婢樼€硅姤鏌熼崥? use cut_slot direction='y'.",
        "If the request says the slot runs along the plate length, across the length, horizontally on the top view, or 濞屽潡鏆辨惔锔芥煙閸?濞屾寧婢橀梹鎸庢煙閸? use cut_slot direction='x'.",
        "For add_fillet, when the user requests a generic edge round/round-over and no narrower target is explicit, use params.target=outer_edges. Do not invent custom target names.",
        "Every add_fillet operation must include a numeric params.radius greater than 0. If the user gives an R value such as R2 or R3, use that number; otherwise recommend a conservative radius (R2 to R3, smaller than the base thickness) and mark it inferred. Never omit radius and never output it as a string.",
        "When the user requests a 闁碍蝎 / through-slot and does not explicitly give the slot span, infer the slot span from the base size along the requested direction so the slot traverses that axis.",
        "Do not set cut_slot through_all=true unless the user explicitly asks to cut through the plate thickness, through the base, 鐠愵垳鈹涚€瑰顥婇弶? 鐠愵垳鈹涙惔鏇熸緲, or 鐠愵垳鈹涢弶鍨袱.",
        "If a slot depth is required but the user did not specify it, recommend a conservative blind depth that stays within the base thickness and mark that depth as inferred.",
        "If four corner holes are requested without an explicit edge distance, recommend a safe symmetric edge_margin that keeps every hole fully inside the base and is greater than the hole radius.",
        "If the request describes an off-center hole, an edge-distance hole, or a hole that will be patterned, use create_through_hole or create_blind_hole with plane and center. Do not use cut_center_hole for those cases.",
        "For centered boss/base holes expressed with cut_center_hole, do not output plane or center. cut_center_hole may use only diameter plus optional depth/through_all/target.",
        "If a pattern references a hole seed, the seed operation itself must already be a reusable hole feature such as create_through_hole/create_blind_hole. Do not keep cut_center_hole and merely add plane/center fields to it.",
        "For a centered rectangle, center=[0,0], left edge x=-length/2, right edge x=length/2, lower/front y=-width/2, upper/back y=width/2.",
        "For a hole distance from left edge, x=-length/2+distance and y=0 if no y distance is given.",
        "Shared enterprise Feature Registry and Policy guidance:",
        shared_prompt,
    ]
    return "\n".join(lines)


@lru_cache(maxsize=1)
def _repair_system_prompt() -> str:
    return "\n".join(
        [
            "You repair one invalid FeaturePlan JSON object.",
            "Output JSON only. No markdown, explanations, code fences, paths, scripts, macros, or commands.",
            "Keep version='2.0', unit='mm', document_type='part'.",
            "The top-level outputs field MUST be a JSON object. It may contain only boolean save_sldprt, export_step, and capture_png; use {} when no output flags are needed.",
            "Use only implemented operations already available to the original parser.",
            "Do not add reference geometry unless the original request explicitly asks for reference geometry or the selected operation intrinsically requires it.",
            "create_linear_pattern uses direction=x/y/z directly and must not be repaired by inventing create_axis or create_offset_plane.",
            "create_circular_pattern may require an axis, but linear patterns do not.",
            "Do not add unrelated capabilities. Remove operations not requested or clearly implied.",
            "Fill only missing or invalid parameters required by the selected operations.",
            "For material repair, map user wording to the closest official SOLIDWORKS material name, such as 6061 Alloy or AISI 304.",
            "For set_material, use only params.material or params.material_id. Do not use params.material_spec.",
            "For custom properties, use only PartNumber, Description, Designer, ProjectNo, Revision, or MaterialSpec.",
        ]
    )


def _response_text(response) -> str:
    text = getattr(response, "output_text", None)
    if text:
        return text
    choices = getattr(response, "choices", None)
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if content:
            return content
    raise LocalProviderError("Local LLM response did not contain text")


class _OllamaMessage:
    """Mimics openai response message: exposes .content."""

    def __init__(self, content: str):
        self.content = content


class _OllamaChoice:
    """Mimics openai response choice: exposes .message.content."""

    def __init__(self, content: str):
        self.message = _OllamaMessage(content)


class _OllamaResponse:
    """Mimics openai ChatCompletion: exposes .choices[0].message.content."""

    def __init__(self, content: str):
        self.choices = [_OllamaChoice(content)]
        self.output_text = None


class _OllamaChatCompletions:
    def __init__(self, client: "OllamaClient"):
        self._client = client

    def create(self, **kwargs) -> _OllamaResponse:
        return self._client._chat_create(kwargs)


class _OllamaChat:
    def __init__(self, client: "OllamaClient"):
        self.completions = _OllamaChatCompletions(client)


class OllamaClient:
    """Minimal Ollama native-API client using only the Python standard library.

    Talks to Ollama's /api/chat endpoint over urllib so no third-party package
    (openai / httpx) is required. Exposes an openai-compatible surface:
    client.chat.completions.create(**kwargs) -> object with .choices[0].message.content
    """

    def __init__(self, base_url: str, api_key: str, timeout_seconds: float):
        # base_url may end with /v1 (OpenAI-compatible) or /api; normalize to native /api/chat.
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[: -len("/v1")]
        if root.endswith("/api"):
            root = root[: -len("/api")]
        self._chat_url = root + "/api/chat"
        self._api_key = api_key
        self._timeout = timeout_seconds
        self.chat = _OllamaChat(self)

    def _chat_create(self, kwargs: dict) -> _OllamaResponse:
        import urllib.request
        import urllib.error

        messages = kwargs.get("messages", [])
        model = kwargs.get("model")

        options: dict[str, object] = {}
        temperature = kwargs.get("temperature")
        if temperature is not None:
            options["temperature"] = temperature

        keep_alive = None
        extra_body = kwargs.get("extra_body") or {}
        if isinstance(extra_body, dict):
            if "num_predict" in extra_body:
                options["num_predict"] = extra_body["num_predict"]
            keep_alive = extra_body.get("keep_alive")

        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options
        if keep_alive:
            payload["keep_alive"] = keep_alive

        response_format = kwargs.get("response_format")
        if isinstance(response_format, dict) and response_format.get("type") == "json_object":
            payload["format"] = "json"

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        request = urllib.request.Request(self._chat_url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise LocalProviderError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise LocalProviderError(f"Ollama request failed: {exc.reason}") from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LocalProviderError("Ollama response was not valid JSON") from exc

        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not content:
            raise LocalProviderError("Ollama response did not contain message.content")
        return _OllamaResponse(content)


def _openai_client_class():
    # Return the standard-library Ollama client so no third-party package is needed.
    return OllamaClient


def _create_local_client(openai_client, base_url: str, api_key: str, stage: str = "first_pass"):
    timeout_seconds = _request_timeout_seconds(stage)
    return openai_client(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )


def _request_timeout_seconds(stage: str = "first_pass") -> float:
    stage_key = "AI_SW_LOCAL_LLM_TIMEOUT_SECONDS_FIRST" if stage == "first_pass" else "AI_SW_LOCAL_LLM_TIMEOUT_SECONDS_REPAIR"
    default_value = DEFAULT_FIRST_PASS_TIMEOUT_SECONDS if stage == "first_pass" else DEFAULT_REPAIR_TIMEOUT_SECONDS
    raw = os.environ.get(stage_key, os.environ.get("AI_SW_LOCAL_LLM_TIMEOUT_SECONDS", str(default_value))).strip()
    try:
        value = float(raw)
    except ValueError:
        value = default_value
    return max(5.0, min(value, 300.0))


def _repair_attempt_count() -> int:
    raw = os.environ.get("AI_SW_LOCAL_LLM_REPAIR_ATTEMPTS", "1").strip()
    try:
        attempts = int(raw)
    except ValueError:
        attempts = 1
    return max(0, min(attempts, 2))


def _requested_feature_complexity(prompt: str) -> int:
    prompt_text = str(prompt or "")
    lowered = prompt_text.lower()
    score = 0
    for hints in FEATURE_COMPLETENESS_HINTS.values():
        matched = any(hint in prompt_text for hint in hints if not hint.isascii()) or any(
            hint in lowered for hint in hints if hint.isascii()
        )
        if matched:
            score += 1
    return score


def _timing_enabled() -> bool:
    return os.environ.get("AI_SW_LOCAL_LLM_TIMING", "").strip() == "1"


def _print_timing(label: str, started_at: float) -> None:
    if _timing_enabled():
        print(f"Local LLM timing: {label}={time.perf_counter() - started_at:.3f}s")


def _chat_completion_kwargs(model: str, messages: list[dict[str, str]], stage: str = "first_pass") -> dict[str, object]:
    kwargs: dict[str, object] = {
        "model": model,
        "temperature": 0,
        "messages": messages,
    }
    extra_body: dict[str, object] = {}
    num_predict = _num_predict(stage)
    if num_predict > 0:
        extra_body["num_predict"] = num_predict
    keep_alive = os.environ.get("AI_SW_LOCAL_LLM_KEEP_ALIVE", "10m").strip()
    if keep_alive:
        extra_body["keep_alive"] = keep_alive
    if extra_body:
        kwargs["extra_body"] = extra_body
    if os.environ.get("AI_SW_LOCAL_LLM_JSON_MODE", "1").strip() == "1":
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _num_predict(stage: str = "first_pass") -> int:
    stage_key = "AI_SW_LOCAL_LLM_NUM_PREDICT_FIRST" if stage == "first_pass" else "AI_SW_LOCAL_LLM_NUM_PREDICT_REPAIR"
    default_value = DEFAULT_FIRST_PASS_NUM_PREDICT if stage == "first_pass" else DEFAULT_REPAIR_NUM_PREDICT
    raw = os.environ.get(stage_key, os.environ.get("AI_SW_LOCAL_LLM_NUM_PREDICT", str(default_value))).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default_value
    return max(0, min(value, 4096))


def _policy_violations(data: dict, prompt: str = ""):
    data = _normalize_featureplan_protocol(data)
    if prompt:
        data = bind_featureplan_semantics(prompt, data)
        data = _normalize_featureplan_protocol(data)
    return PolicyEngine().validate(data).violations


def _plan_operation_names(data: dict) -> set[str]:
    operations = data.get("operations") if isinstance(data, dict) else None
    names: set[str] = set()
    if not isinstance(operations, list):
        return names
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_name = str(operation.get("op", "")).strip()
        if op_name:
            names.add(op_name)
    return names


def _prompt_mentions(prompt: str, hints: tuple[str, ...]) -> bool:
    prompt_text = str(prompt or "")
    lowered = prompt_text.lower()
    return any(hint in prompt_text for hint in hints if not hint.isascii()) or any(
        hint in lowered for hint in hints if hint.isascii()
    )


def _semantic_completeness_issues(data: dict, prompt: str) -> list[str]:
    if not isinstance(data, dict) or not isinstance(prompt, str) or not prompt.strip():
        return []

    operation_names = _plan_operation_names(data)
    issues: list[str] = []
    lowered_prompt = prompt.lower()
    corner_hole_requested = _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["cut_corner_holes"]) or (
        ("四角" in prompt or "角上" in prompt or "corners" in lowered_prompt or "corner" in lowered_prompt)
        and ("通孔" in prompt or "孔" in prompt or "hole" in lowered_prompt)
    )

    if corner_hole_requested and "cut_corner_holes" not in operation_names:
        issues.append("missing requested cut_corner_holes operation")

    if _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["create_center_boss"]) and "create_center_boss" not in operation_names:
        issues.append("missing requested create_center_boss operation")

    if _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["cut_center_hole"]) and "cut_center_hole" not in operation_names:
        issues.append("missing requested cut_center_hole operation")

    if _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["cut_slot"]) and "cut_slot" not in operation_names:
        issues.append("missing requested cut_slot operation")

    if _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["cut_rectangle_pocket"]) and "cut_rectangle_pocket" not in operation_names:
        issues.append("missing requested cut_rectangle_pocket operation")

    wants_fillet = _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["add_fillet"])
    wants_chamfer = _prompt_mentions(prompt, FEATURE_COMPLETENESS_HINTS["add_chamfer"])
    if wants_fillet and "add_fillet" not in operation_names:
        issues.append("missing requested add_fillet operation")
    if wants_fillet and "add_chamfer" in operation_names and "add_fillet" not in operation_names:
        issues.append("user requested rounded edges, not chamfer; replace add_chamfer with add_fillet")
    if wants_chamfer and "add_chamfer" not in operation_names:
        issues.append("missing requested add_chamfer operation")

    operations = data.get("operations") if isinstance(data.get("operations"), list) else []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        if str(operation.get("op", "")).strip() != "cut_center_hole":
            continue
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        try:
            diameter = float(params.get("diameter", 0))
        except (TypeError, ValueError):
            diameter = 0.0
        if diameter <= 0:
            issues.append("cut_center_hole diameter is missing or invalid")

    return list(dict.fromkeys(issues))


def _policy_error_summary(data: dict, prompt: str = "") -> str:
    data = _normalize_featureplan_protocol(data)
    if prompt:
        data = bind_featureplan_semantics(prompt, data)
        data = _normalize_featureplan_protocol(data)
    policy_result = PolicyEngine().validate(data)
    if not policy_result.allowed:
        return "; ".join(f"{violation.code}: {violation.message}" for violation in policy_result.violations[:8])
    try:
        plan_operations(FeaturePlan.from_dict(data))
    except Exception as exc:
        return f"planning: {exc}"
    completeness_issues = _semantic_completeness_issues(data, prompt)
    if completeness_issues:
        return "semantic_completeness: " + "; ".join(completeness_issues)
    return ""


def _policy_repair_checklist(data: dict, prompt: str = "") -> str:
    data = _normalize_featureplan_protocol(data)
    if prompt:
        data = bind_featureplan_semantics(prompt, data)
        data = _normalize_featureplan_protocol(data)
    policy_result = PolicyEngine().validate(data)
    if policy_result.allowed:
        try:
            plan_operations(FeaturePlan.from_dict(data))
        except Exception:
            return "\n".join(
                [
                    "- Ensure the FeaturePlan creates a completed base solid before any cut, hole, chamfer, fillet, pattern, or mirror operation.",
                    "- For a rectangular block/plate, use create_new_part -> create_sketch -> sketch_center_rectangle -> extrude_boss before top-face cuts.",
                    "- For a simple mounting plate, create_base_plate may be used instead of the atomic sketch/extrude chain.",
                    "- For an off-center positioned hole, use create_through_hole with plane='top_face' and explicit center coordinates.",
                    "- Do not use cut_center_hole for holes that are not at the part center.",
                    "- Do not use cut_center_hole as the seed_feature for create_linear_pattern or create_circular_pattern. Pattern seeds must be explicit hole features such as create_through_hole/create_blind_hole with a valid center.",
                    "- If a pattern currently references cut_center_hole, change the hole operation type itself to create_through_hole or create_blind_hole, move plane/center there, and point seed_feature to that rewritten hole operation id.",
                    "- Do not try to repair this by adding center or plane parameters to cut_center_hole; those parameters are not allowlisted for cut_center_hole.",
                ]
            )
        return ""

    hints = []
    for violation in policy_result.violations:
        if violation.code == "unit":
            hints.append('Set the top-level field "unit" exactly to "mm". Do not leave it empty.')
        elif violation.code == "version":
            hints.append('Set the top-level field "version" exactly to "2.0".')
        elif violation.code == "document_type":
            hints.append('Set the top-level field "document_type" exactly to "part".')
        elif violation.code == "part_name":
            hints.append('Set "part_name" to a safe ASCII identifier using letters, digits, underscores, or hyphens.')
        elif violation.code == "operation_id":
            hints.append('Ensure every operation has a unique non-empty "id".')
        elif violation.code == "parameters":
            hints.append('Fix operation parameters according to the Feature Registry: add missing required params and remove non-allowlisted params.')
            if "diameter" in violation.message:
                hints.append("For cut_corner_holes and M6 corner bolt-hole intent, repair diameter to the numeric clearance-hole value 6.6 mm unless the user explicitly gave another diameter.")
                hints.append("Never leave M6 as text and never omit cut_corner_holes.params.diameter.")
            if "material" in violation.message or "material_spec" in violation.message:
                hints.append("For set_material, use only params.material or params.material_id. Never use params.material_spec.")
                hints.append("If the request names Aluminum_6061, 6061, or aluminum 6061, repair set_material.params.material to the official catalog material name 6061 Alloy, or use material_id=Aluminum_6061.")
            if "offset_x" in violation.message or "offset_y" in violation.message:
                hints.append("For cut_corner_holes, offset_x and offset_y must be positive distances. Never output negative signed coordinates for corner holes.")
                hints.append("If the user gives the same edge distance for all four corner holes, prefer cut_corner_holes edge_margin=<positive mm> instead of signed offset_x/offset_y.")
            if "center" in violation.message or "plane" in violation.message:
                hints.append("If the invalid operation is cut_center_hole, remove params.center and params.plane. cut_center_hole allows only diameter plus optional depth/through_all/target.")
                hints.append("For a centered hole in a boss, repair to cut_center_hole target=boss. For a centered hole in only the base, repair to cut_center_hole target=base.")
        elif violation.code == "metadata":
            hints.append(
                "Fix metadata provenance paths so every path is '<operation_id>.params.<parameter>' and references an existing operation id and parameter."
            )
            hints.append(
                "Do not output per-coordinate paths such as '<operation_id>.params.center.x' or '<operation_id>.params.center.y'. Use only '<operation_id>.params.center'."
            )
            hints.append(
                "Never use operation names such as create_new_part.params.part_name or create_through_hole.params.center in metadata; use actual operation ids like 1.params.part_name or 5.params.center."
            )
            hints.append(
                "If center coordinates were computed from an edge-distance request, put the center path in metadata.inferred_parameters, not metadata.explicit_parameters."
            )
            hints.append(
                "Do not repair invalid provenance by keeping unrelated geometry. Re-check the original user requirement and remove operations that are not requested or clearly implied."
            )
        elif violation.code == "geometry":
            hints.append('Fix numeric geometry values so dimensions are positive and feature relationships are physically valid.')
            if "seed_feature 瀵洜鏁ゆ禍?cut_center_hole" in violation.message or "seed_feature references cut_center_hole" in violation.message:
                hints.append(
                    "When a pattern or mirror currently references cut_center_hole, rewrite the hole operation itself to create_through_hole or create_blind_hole. "
                    "Move plane and center to that rewritten hole operation, remove target-only center-hole semantics, and point seed_feature to the rewritten hole operation id."
                )
                hints.append(
                    "Do not repair this case by adding center or plane parameters to cut_center_hole. cut_center_hole remains a centered-hole capability only."
                )
            if "offset_x" in violation.message or "offset_y" in violation.message:
                hints.append("For cut_corner_holes, offset_x and offset_y must be positive distances. Never output negative signed coordinates for corner holes.")
                hints.append("If the user gives the same edge distance for all four corner holes, prefer cut_corner_holes edge_margin=<positive mm> instead of signed offset_x/offset_y.")
            if "create_axis references" in violation.message:
                hints.append(
                    "Reference geometry must be explicit and controlled. Do not invent create_axis to satisfy a linear pattern."
                )
                hints.append(
                    "If the user asked for a linear pattern, remove create_axis and keep create_linear_pattern with params.direction set directly to x, y, or z."
                )
                hints.append(
                    "Only keep create_axis when the original request explicitly asks for a reference axis, or when a circular pattern truly requires a controlled axis."
                )
            if "plane" in violation.message:
                hints.append("Fix plane selectors exactly to the Policy Engine allowlist. For create_sketch use only Top, Front, Right, or top_face.")
                hints.append("For the initial rectangular base sketch, use create_sketch params.plane='Top'.")
                hints.append("For holes, slots, pockets, and cuts on the existing top surface, use params.plane='top_face'.")
                hints.append("Do not output Top Plane, top, upper_face, top plane, translated plane display names, or SolidWorks UI display names.")
            if "current base boundary" in violation.message or "edge-distance intent" in violation.message:
                hints.append(
                    "For a hole located by distance from a rectangular base edge, convert edge distance to the hole center coordinate: "
                    "left edge x=-length/2+distance, right edge x=length/2-distance, front/lower edge y=-width/2+distance, "
                    "back/upper edge y=width/2-distance."
                )
                hints.append("The hole center plus its radius must stay inside the base boundary.")
                hints.append(
                    "This Policy message already states the exact valid numeric range, for example 'x within [a, b] and y within [c, d]'. "
                    "You MUST rewrite params.center to a coordinate strictly inside that stated x and y range. Prefer a value near the middle of the range, "
                    "not at either endpoint, so the hole keeps clearance from the edge."
                )
                hints.append(
                    "The base center is the origin [0,0]. Positive x is toward the right/length+ edge, negative x toward the left; "
                    "positive y is toward the back/width+edge, negative y toward the front. For four corner holes on a length x width base, "
                    "use symmetric coordinates like [+X,+Y], [-X,+Y], [+X,-Y], [-X,-Y] where X and Y are both inside the stated valid range."
                )
                hints.append(
                    "If the invalid coordinate or size was inferred/recommended by the LLM, replace it with a safe recommendation and list the parameter path in metadata.inferred_parameters."
                )
                hints.append(
                    "If the invalid coordinate or size was explicitly specified by the user, do not change it; list it in metadata.explicit_parameters so execution can ask for user confirmation."
                )
                if "missing source provenance" in violation.message:
                    hints.append(
                        "The invalid coordinate is missing source provenance. If the user did not provide the exact coordinate, treat it as LLM-inferred: correct the coordinate and add the path to metadata.inferred_parameters."
                    )
        elif violation.code == "file_safety":
            hints.append('Remove dangerous/path/script fields from every level of the JSON.')
            hints.append(
                "For set_custom_property, never use dangerous words such as script, macro, command, shell, powershell, python, delete, remove, or overwrite as the key or value."
            )
            hints.append(
                "Use only enterprise custom property keys: PartNumber, Description, Designer, ProjectNo, Revision, MaterialSpec."
            )
            hints.append(
                "Map Chinese 闂嗘湹娆㈢紓鏍у娇/闂嗘湹娆㈤崣?閺傛瑥褰?or English part number/part no to key='PartNumber'; map Chinese 閹诲繗鍫?鐠囧瓨妲?or English description to key='Description'."
            )
        elif violation.code == "outputs":
            hints.append('Set outputs to a JSON object containing only safe boolean fields: save_sldprt, export_step, capture_png. Use {} when no flags are needed.')
        elif violation.code in {"registry", "capability"}:
            hints.append('Use only implemented operations from the Feature Registry.')
    return "\n".join(f"- {hint}" for hint in dict.fromkeys(hints))


def _normalize_featureplan_protocol(data: dict) -> dict:
    """Normalize safe top-level FeaturePlan protocol fields only.

    This is not semantic parsing and must not invent geometry. It only repairs
    empty/missing protocol constants that the local model often drops despite
    the prompt. Non-mm units such as inch are preserved so Policy can reject
    them instead of silently converting.
    """

    if not isinstance(data, dict):
        return data
    normalized = dict(data)
    operations = _normalize_protocol_operations(normalized.get("operations", []))
    operations = _normalize_top_level_operation_fields(normalized, operations)
    normalized["operations"] = operations

    if not str(normalized.get("version", "")).strip():
        normalized["version"] = "2.0"

    unit = str(normalized.get("unit", "")).strip()
    if not unit:
        normalized["unit"] = "mm"
    elif unit.lower() == "mm" or unit in {"毫米", "millimeter", "millimeters"}:
        normalized["unit"] = "mm"

    if not str(normalized.get("document_type", "")).strip():
        normalized["document_type"] = "part"

    part_name = _normalize_part_name(str(normalized.get("part_name", "")).strip())
    metadata = normalized.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    else:
        metadata = dict(metadata)
    if not part_name:
        part_name = _normalize_part_name(str(metadata.get("name", "")).strip()) or "unnamed_part"
    normalized["part_name"] = part_name
    metadata.setdefault("name", part_name)
    metadata["name"] = _normalize_part_name(str(metadata.get("name", "")).strip()) or part_name
    metadata.setdefault("description", "")
    metadata.setdefault("source", "local")
    metadata["inferred_parameters"] = _normalize_metadata_parameter_bucket(metadata.get("inferred_parameters"))
    metadata["explicit_parameters"] = _normalize_metadata_parameter_bucket(metadata.get("explicit_parameters"))
    _normalize_metadata_parameter_paths(metadata, operations)
    _autofill_missing_parameter_provenance(metadata, operations)
    normalized["metadata"] = metadata

    outputs = normalized.get("outputs")
    if "outputs" not in normalized or outputs is None or outputs == "" or outputs == []:
        normalized["outputs"] = {}
    elif isinstance(outputs, list):
        normalized["outputs"] = _normalize_outputs_array(outputs)

    return normalized



def _promote_top_level_single_operation(data: dict, operations: list[dict]) -> list[dict]:
    """Promote a top-level single-operation object into the operations array.

    本地模型对“只开一个/几个特征”的 prompt 偶尔把单个算子对象直接铺在顶层
    （形如 {"id": "slot_001", "op": "cut_slot", "params": {...}, "operations": []}），
    而不是放进 operations 数组，导致 operations 为空、Policy 报“至少需要一个 operation”而 500。
    这里做纯结构修复：当顶层带有字符串 op + dict params，且 operations 里尚无同名算子时，
    把顶层的 id/op/params/depends_on 收进 operations，并从顶层移除这些字段。不发明几何。
    """

    op_name = data.get("op")
    params = data.get("params")
    if not isinstance(op_name, str) or not op_name.strip():
        return operations
    if not isinstance(params, dict):
        return operations

    normalized_operations = list(operations)
    existing_ops = {
        str(operation.get("op", "")).strip()
        for operation in normalized_operations
        if isinstance(operation, dict)
    }
    if op_name.strip() in existing_ops:
        # operations 里已有同名算子，顶层字段视为冗余，直接移除避免污染。
        for key in ("id", "op", "params", "depends_on"):
            data.pop(key, None)
        return normalized_operations

    used_ids = {
        str(operation.get("id", "")).strip()
        for operation in normalized_operations
        if isinstance(operation, dict)
    }
    operation_id = str(data.get("id", "")).strip()
    if not operation_id or operation_id in used_ids:
        base_id = op_name.strip()
        suffix = 1
        operation_id = f"{base_id}_{suffix:03d}"
        while operation_id in used_ids:
            suffix += 1
            operation_id = f"{base_id}_{suffix:03d}"

    promoted = {"id": operation_id, "op": op_name.strip(), "params": dict(params)}
    depends_on = data.get("depends_on")
    if depends_on is not None:
        promoted["depends_on"] = list(depends_on) if isinstance(depends_on, list) else depends_on
    normalized_operations.append(promoted)

    for key in ("id", "op", "params", "depends_on"):
        data.pop(key, None)
    return normalized_operations


def _normalize_top_level_operation_fields(data: dict, operations: list[dict]) -> list[dict]:
    operations = _promote_top_level_single_operation(data, operations)
    operation_fields = (
        "rebuild_model",
        "validate_rebuild",
        "save_sldprt",
        "export_step",
        "capture_png",
    )
    existing_ops = {
        str(operation.get("op", "")).strip(): str(operation.get("id", "")).strip()
        for operation in operations
        if isinstance(operation, dict)
    }
    normalized_operations = list(operations)

    for field_name in operation_fields:
        if field_name not in data:
            continue
        raw_value = data.pop(field_name)
        if field_name in {"save_sldprt", "export_step", "capture_png"}:
            outputs = data.get("outputs")
            if not isinstance(outputs, dict):
                outputs = {}
            if isinstance(raw_value, bool):
                outputs[field_name] = raw_value
            elif raw_value not in (None, "", [], {}):
                outputs[field_name] = True
            data["outputs"] = outputs
            continue

        if field_name in existing_ops:
            continue
        if raw_value in (None, False, "", [], {}):
            continue
        operation_id = f"{field_name}_001"
        suffix = 1
        used_ids = {str(operation.get("id", "")).strip() for operation in normalized_operations if isinstance(operation, dict)}
        while operation_id in used_ids:
            suffix += 1
            operation_id = f"{field_name}_{suffix:03d}"
        normalized_operations.append({"id": operation_id, "op": field_name, "params": {}})

    return normalized_operations

def _normalize_protocol_operations(operations: object) -> list[dict]:
    if not isinstance(operations, list):
        return []
    normalized_operations: list[dict] = []
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        expanded_operations = _expand_operation_param_variants(operation)
        for expanded_operation in expanded_operations:
            normalized_operation = dict(expanded_operation)
            params = expanded_operation.get("params")
            if isinstance(params, dict):
                normalized_operation["params"] = _normalize_operation_params(
                    str(expanded_operation.get("op", "")).strip(),
                    params,
                )
            normalized_operations.append(normalized_operation)
    return normalized_operations


def _expand_operation_param_variants(operation: dict) -> list[dict]:
    params = operation.get("params")
    if not isinstance(params, list):
        return [operation]
    param_variants = [item for item in params if isinstance(item, dict)]
    if not param_variants or len(param_variants) != len(params):
        return [operation]

    base_operation = dict(operation)
    base_operation.pop("params", None)
    base_id = str(operation.get("id", "")).strip()
    base_depends_on = operation.get("depends_on")
    expanded: list[dict] = []
    for index, param_variant in enumerate(param_variants, start=1):
        expanded_id = f"{base_id}_{index:03d}" if base_id else f"op_{index:03d}"
        expanded_operation = {
            **base_operation,
            "id": expanded_id,
            "params": dict(param_variant),
        }
        if base_depends_on is not None:
            expanded_operation["depends_on"] = list(base_depends_on) if isinstance(base_depends_on, list) else base_depends_on
        expanded.append(expanded_operation)
    return expanded


def _normalize_metadata_parameter_bucket(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, dict):
        normalized: list[str] = []
        for key, bucket_value in value.items():
            key_text = str(key).strip()
            if not key_text:
                continue
            if isinstance(bucket_value, (int, float)):
                normalized.append(key_text)
                continue
            if bucket_value:
                normalized.append(key_text)
        return normalized
    return []


def _normalize_outputs_array(outputs: list[object]) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    for item in outputs:
        if not isinstance(item, dict):
            continue
        operation_id = str(item.get("operation_id", "")).strip().lower()
        description = str(item.get("description", "")).strip().lower()
        op_name = str(item.get("op", "")).strip().lower()
        text = f"{operation_id} {description} {op_name}"
        if "save_sldprt" in text or "sldprt" in text:
            normalized["save_sldprt"] = True
        elif "export_step" in text or " step" in f" {text} " or ".step" in text:
            normalized["export_step"] = True
        elif "capture_png" in text or "png" in text or "preview" in text or "screenshot" in text:
            normalized["capture_png"] = True
    return normalized


def _normalize_part_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_-]", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    return text[:80] or "unnamed_part"


def _normalize_operation_params(operation_type: str, params: dict) -> dict:
    normalized = dict(params)
    normalized_center = _normalize_center_value(normalized.get("center"))
    if normalized_center is not None:
        normalized["center"] = normalized_center
    if operation_type == "set_material":
        material_value = normalized.get("material")
        material_id_value = normalized.get("material_id")
        material_spec_value = normalized.get("material_spec")
        if material_spec_value and not material_value and not material_id_value:
            normalized["material"] = material_spec_value
        normalized.pop("material_spec", True)
    return normalized


def _normalize_center_value(center: object) -> list[object] | None:
    if isinstance(center, (list, tuple)) and len(center) == 2:
        return [center[0], center[1]]
    if isinstance(center, dict):
        keyed = {str(key).lower(): value for key, value in center.items()}
        if "x" in keyed and "y" in keyed:
            return [keyed["x"], keyed["y"]]
    return None


def _autofill_missing_parameter_provenance(metadata: dict, operations: object) -> None:
    if not isinstance(metadata, dict) or not isinstance(operations, list):
        return
    inferred = metadata.get("inferred_parameters")
    explicit = metadata.get("explicit_parameters")
    if not isinstance(inferred, list):
        inferred = []
    if not isinstance(explicit, list):
        explicit = []

    tracked = set(str(path) for path in inferred) | set(str(path) for path in explicit)
    auto_inferable_params = {
        "create_through_hole": {"plane", "center", "diameter"},
        "create_blind_hole": {"plane", "center", "diameter", "depth"},
        "cut_slot": {"plane", "center", "length", "width", "depth", "through_all", "direction"},
        "cut_rectangle_pocket": {"plane", "center", "length", "width", "depth"},
        "sketch_center_rectangle": {"center", "length", "width"},
        "sketch_circle": {"center", "diameter"},
        "cut_corner_holes": {"diameter", "edge_margin", "offset_x", "offset_y", "through_all"},
        "add_fillet": {"radius", "target"},
        "add_chamfer": {"distance", "angle", "target"},
    }
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        operation_type = str(operation.get("op", "")).strip()
        tracked_params = auto_inferable_params.get(operation_type)
        if not tracked_params:
            continue
        operation_id = str(operation.get("id", "")).strip()
        params = operation.get("params") if isinstance(operation.get("params"), dict) else {}
        if not operation_id:
            continue
        for parameter_name in tracked_params:
            if parameter_name not in params:
                continue
            parameter_value = params.get(parameter_name)
            if parameter_name == "center":
                if not (isinstance(parameter_value, (list, tuple)) and len(parameter_value) == 2):
                    continue
            elif parameter_value in (None, "", [], {}):
                continue
            path = f"{operation_id}.params.{parameter_name}"
            if path in tracked:
                continue
            inferred.append(path)
            tracked.add(path)

    metadata["inferred_parameters"] = list(dict.fromkeys(str(path) for path in inferred))
    metadata["explicit_parameters"] = list(dict.fromkeys(str(path) for path in explicit))


def _normalize_metadata_parameter_paths(metadata: dict, operations: object) -> None:
    if not isinstance(operations, list):
        return

    explicit_paths = metadata.get("explicit_parameters")
    inferred_paths = metadata.get("inferred_parameters")
    explicit_out: list[str] = []
    inferred_out: list[str] = []

    # Local 7B models frequently emit the provenance buckets as an
    # object/dict (``{"<op>.params.<param>": <value>}``) instead of the
    # canonical list of path strings. The path itself lives in the *key*, so
    # extract the keys and normalize them like a list. Without this, dict-shaped
    # metadata bypassed normalization entirely and the malformed op-name+id
    # joined paths (e.g. ``create_base_plate.001.params.plane``) reached the
    # Policy Engine unchanged, producing "invalid parameter path" 500s.
    if isinstance(explicit_paths, dict):
        explicit_paths = list(explicit_paths.keys())
    if isinstance(inferred_paths, dict):
        inferred_paths = list(inferred_paths.keys())

    if isinstance(explicit_paths, list):
        for path in explicit_paths:
            normalized_path, bucket = _normalize_metadata_parameter_path(str(path), operations, default_bucket="explicit")
            if not normalized_path:
                continue
            if bucket == "inferred":
                inferred_out.append(normalized_path)
            else:
                explicit_out.append(normalized_path)

    if isinstance(inferred_paths, list):
        for path in inferred_paths:
            normalized_path, _ = _normalize_metadata_parameter_path(str(path), operations, default_bucket="inferred")
            if normalized_path:
                inferred_out.append(normalized_path)

    metadata["explicit_parameters"] = list(dict.fromkeys(explicit_out))
    metadata["inferred_parameters"] = list(dict.fromkeys(inferred_out))


def _normalize_metadata_parameter_path(path: str, operations: list, default_bucket: str = "explicit") -> tuple[str, str]:
    parts = path.split(".")
    original_operation_ref = parts[0] if parts else ""
    center_component = False
    if len(parts) == 4 and parts[1] == "params" and parts[2] == "center" and parts[3] in {"x", "y"}:
        parts = [parts[0], parts[1], parts[2]]
        path = ".".join(parts)
        center_component = True
    # Local 7B models frequently emit malformed provenance paths where the
    # operation *name* and *id* are joined with a dot (e.g.
    # ``create_base_plate.001.params.plane``), producing a 4+ segment path the
    # Policy Engine rejects. Deterministically compress these back to the
    # canonical ``<operation_id>.params.<parameter>`` form when we can map the
    # pre-``params`` head to a real operation, and drop the rest instead of
    # letting them pass through as fatal metadata violations.
    if len(parts) != 3 or parts[1] != "params":
        if "params" not in parts:
            return "", default_bucket
        p_index = parts.index("params")
        parameter_name = ".".join(parts[p_index + 1 :]).strip()
        head = parts[:p_index]
        if not parameter_name or not head:
            return "", default_bucket
        resolved = ""
        for start in range(len(head)):
            candidate_ref = ".".join(head[start:]).strip()
            if not candidate_ref:
                continue
            resolved = _resolve_metadata_operation_ref(candidate_ref, parameter_name, operations)
            if resolved:
                break
        if not resolved:
            return "", default_bucket
        parts = [resolved,"params", parameter_name]
        path = ".".join(parts)

    operation_ref, _, parameter_name = parts
    resolved_operation_ref = _resolve_metadata_operation_ref(operation_ref, parameter_name, operations)
    if not resolved_operation_ref:
        return "", default_bucket

    # Drop provenance that references a parameter the resolved operation does
    # not actually carry (e.g. a bogus ``host`` on ``create_center_boss``).
    # Policy validation rejects such paths as fatal metadata violations.
    resolved_params: set[str] = set()
    for operation in operations:
        if isinstance(operation, dict) and str(operation.get("id", "")).strip() == resolved_operation_ref:
            op_params = operation.get("params")
            if isinstance(op_params, dict):
                resolved_params = set(op_params.keys())
            break
    if parameter_name not in resolved_params:
        return "", default_bucket

    bucket = default_bucket
    if parameter_name == "center" and (center_component or not _looks_like_operation_id(original_operation_ref)):
        bucket = "inferred"

    return f"{resolved_operation_ref}.params.{parameter_name}", bucket


def _looks_like_operation_id(value: str) -> bool:
    return value == str(value or "").strip() and "." not in value and bool(value) and value != "create_through_hole" and value != "create_sketch"


def _resolve_metadata_operation_ref(operation_ref: str, parameter_name: str, operations: list) -> str:
    operation_ids = {str(operation.get("id", "")).strip() for operation in operations if isinstance(operation, dict)}
    if operation_ref in operation_ids:
        return operation_ref

    matching_ids = []
    operation_ref_lower = operation_ref.lower()
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        params = operation.get("params")
        if not isinstance(params, dict) or parameter_name not in params:
            continue
        operation_id = str(operation.get("id", "")).strip()
        operation_type = str(operation.get("op", "")).strip()
        lowered_type = operation_type.lower()
        lowered_id = operation_id.lower()
        if operation_ref_lower == lowered_type or operation_ref_lower == lowered_id:
            matching_ids.append(operation_id)
            continue
        if operation_ref_lower.startswith(lowered_type + "_"):
            matching_ids.append(operation_id)
            continue
        if lowered_id and lowered_id.endswith(operation_ref_lower):
            matching_ids.append(operation_id)
    matching_ids = list(dict.fromkeys(matching_ids))
    if len(matching_ids) == 1:
        return matching_ids[0]
    return ""


def _validated_featureplan_from_response(response, prompt: str = "") -> dict:
    try:
        data = extract_json_object(_response_text(response))
    except Exception as exc:
        raise LocalProviderError(str(exc)) from exc

    data = _normalize_featureplan_protocol(data)
    data = bind_featureplan_semantics(prompt, data)
    data = _normalize_featureplan_protocol(data)
    policy_errors = _policy_error_summary(data, prompt)
    if policy_errors:
        if "Explicit user parameter" in policy_errors and "requires user confirmation" in policy_errors:
            raise LocalProviderConfirmationRequired(policy_errors)
        raise LocalProviderOutputError(policy_errors)
    return data



def _focused_rejected_data(rejected_data: dict) -> dict:
    if not isinstance(rejected_data, dict):
        return rejected_data
    operations = rejected_data.get("operations")
    if not isinstance(operations, list) or len(operations) <= 6:
        return rejected_data

    failing_ids = {violation.operation_id for violation in _policy_violations(rejected_data) if getattr(violation, "operation_id", "")}
    if not failing_ids:
        return rejected_data

    included_ids: set[str] = set()
    focused_operations: list[dict] = []
    highest_index = -1
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            continue
        operation_id = str(operation.get("id", "")).strip()
        if operation_id in failing_ids:
            highest_index = max(highest_index, index)
    if highest_index < 0:
        return rejected_data

    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            continue
        operation_id = str(operation.get("id", "")).strip()
        if index <= highest_index or operation_id in failing_ids:
            focused_operations.append(operation)
            included_ids.add(operation_id)

    metadata = rejected_data.get("metadata") if isinstance(rejected_data.get("metadata"), dict) else {}
    focused_metadata = dict(metadata)
    for field_name in ("explicit_parameters", "inferred_parameters"):
        paths = focused_metadata.get(field_name)
        if isinstance(paths, list):
            focused_metadata[field_name] = [
                path for path in paths if str(path).split(".", 1)[0] in included_ids
            ]

    return {
        **rejected_data,
        "operations": focused_operations,
        "metadata": focused_metadata,
    }
def _merged_repair_checklist(prompt: str, rejected_data: dict) -> str:
    raw_checklist = _policy_repair_checklist(rejected_data)
    semantic_checklist = _policy_repair_checklist(rejected_data, prompt)
    merged_lines: list[str] = []
    seen: set[str] = set()
    for checklist in (raw_checklist, semantic_checklist):
        for line in str(checklist).splitlines():
            normalized = line.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged_lines.append(normalized)
    return "\n".join(merged_lines)


def _repair_messages(prompt: str, rejected_data: dict, policy_errors: str) -> list[dict[str, str]]:
    repair_checklist = _merged_repair_checklist(prompt, rejected_data)
    semantic_repair_hints: list[str] = []
    policy_errors_text = str(policy_errors)
    if "missing requested cut_corner_holes operation" in policy_errors_text:
        semantic_repair_hints.append("The original request explicitly includes corner holes. Add exactly one cut_corner_holes operation instead of omitting the corner holes.")
        semantic_repair_hints.append("If the user gave a numeric corner-hole diameter, copy that numeric diameter into cut_corner_holes.params.diameter.")
    if "missing requested create_center_boss operation" in policy_errors_text:
        semantic_repair_hints.append("The original request explicitly includes a center boss or raised platform. Add one create_center_boss operation.")
    if "missing requested cut_center_hole operation" in policy_errors_text:
        semantic_repair_hints.append("The original request explicitly includes a centered hole. Add one cut_center_hole operation aligned to the requested host body.")
    if "missing requested cut_slot operation" in policy_errors_text:
        semantic_repair_hints.append("The original request explicitly includes slots. Add the missing cut_slot operations instead of omitting them.")
    if "missing requested cut_rectangle_pocket operation" in policy_errors_text:
        semantic_repair_hints.append("The original request explicitly includes a rectangular pocket. Add the missing cut_rectangle_pocket operations instead of omitting them.")
    if "missing requested add_fillet operation" in policy_errors_text:
        semantic_repair_hints.append("The original request explicitly includes rounded edges. Add add_fillet instead of omitting edge rounding.")
    if "add_fillet" in policy_errors_text and ("radius" in policy_errors_text or "半径" in policy_errors_text):
        semantic_repair_hints.append("Every add_fillet operation must include a numeric params.radius greater than 0. If radius is missing, empty, zero, or non-numeric, recommend a conservative fillet radius in mm from the base thickness and feature size (a safe default is R2 to R3, and the radius must be smaller than the base thickness), then add the exact <operation_id>.params.radius path to metadata.inferred_parameters.")
        semantic_repair_hints.append("Do not omit params.radius from add_fillet and do not output radius as a string; output a positive number such as 2 or 3.")
    if semantic_repair_hints:
        extra_lines = [f"- {hint}" for hint in semantic_repair_hints]
        repair_checklist = "\n".join([line for line in [repair_checklist, *extra_lines] if line])

    return [
        {"role": "system", "content": _repair_system_prompt()},
        {
            "role": "user",
            "content": "\n".join(
                [
                    "Repair the previous FeaturePlan JSON so it passes the project policy.",
                    "Use the original user requirement as the source of intent.",
                    "Semantic premise: the request is a SolidWorks mechanical modeling task for equipment parts, machine components, fixtures, bases, plates, or assemblies.",
                    "Use that SolidWorks mechanical-design context to understand intent and recommend reasonable missing parameters.",
                    "Fill only missing or invalid parameters required by the selected operations.",
                    "For missing numeric values, infer conservative engineering values from the described part function, dimensions, feature relationships, and supported Feature Registry capabilities.",
                    "Before changing individual parameters, compare every operation against the original user requirement. Remove any operation that is not requested or clearly implied by the user.",
                    "For a request that only asks for a rectangular part plus material/properties, do not add bosses, holes, fillets, chamfers, slots, pockets, patterns, mirrors, or reference geometry.",
                    "For a linear pattern request, keep create_linear_pattern with params.direction=x/y/z. Do not add create_axis or create_offset_plane unless the user explicitly asked for reference geometry.",
                    "For cut_corner_holes, use positive edge distances only: prefer edge_margin when the request gives the same margin to all four corners, or positive offset_x/offset_y when the request gives explicit rectangular offsets. Do not convert cut_corner_holes into signed center coordinates.",
                    "If the request says M6 corner holes, M6 bolt holes, or M6 clearance holes and no numeric diameter is present, set cut_corner_holes diameter=6.6 mm.",
                    "Do not output M6 as a string in cut_corner_holes.params.diameter; output the numeric value 6.6.",
                    "If corner-hole offsets become negative, repair them to positive edge-based distances, or switch to edge_margin when the same edge distance applies on both axes.",
                    "If the rejected plan contains create_axis but the original request did not ask for an axis or circular pattern, remove create_axis instead of trying to repair its references.",
                    "When repairing geometry, reason from the actual FeaturePlan dimensions already present: base length, base width, thickness, feature diameters, depths, pattern count, and spacing.",
                    "Determine the active coordinate system before choosing coordinates. For a centered rectangular base sketch, the base center is [0,0], left edge is x=-length/2, right edge is x=length/2, front/lower edge is y=-width/2, and back/upper edge is y=width/2.",
                    "Convert natural-language edge-distance constraints into center coordinates before policy validation. Example: a hole center 20mm from the left edge of a 120mm long centered base has x=-120/2+20=-40.",
                    "For a slot or pocket located distance d from the left or right edge of a centered rectangular base, compute the center x first: left edge x=-base_length/2+d, right edge x=base_length/2-d. For distance from the front/lower or back/upper edge, compute center y first: front/lower y=-base_width/2+d, back/upper y=base_width/2-d.",
                    "When the request says a slot runs along the width direction, the slot span follows the base width axis and the edge-distance usually determines the x coordinate. When the request says a slot runs along the length direction, the slot span follows the base length axis and the edge-distance usually determines the y coordinate.",
                    "If a cut_slot or cut_rectangle_pocket boundary error appears and the feature size itself can fit inside the base, repair the center coordinate first and record <operation_id>.params.center in metadata.inferred_parameters unless the user explicitly gave that exact center.",
                    "Check geometric reasonableness before returning JSON: a circular hole must satisfy abs(x)+diameter/2 <= length/2 and abs(y)+diameter/2 <= width/2.",
                    "For cut_slot, params.length is always the slot span and params.width is always the slot width. If your draft reversed them and length <= width, swap them before returning JSON.",
                    "Do not set cut_slot through_all=true unless the user explicitly asked to cut through the plate thickness or through the base. If the user only says ???? but does not specify slot depth, recommend a conservative blind depth within the base thickness and mark it inferred.",
                    "If four corner holes are requested without an explicit edge distance, recommend a safe symmetric edge_margin that is greater than the hole radius and keeps all holes fully inside the base.",
                    "If a top-face slot or rectangular pocket is located at the center of an outer edge, long edge, or short edge, move the feature center inward by half of the feature size on the perpendicular axis so the feature stays fully inside the base, unless the user explicitly requested an open-edge cut.",
                    "For a generic fillet request such as rounding the plate or adding R3 round corners, use add_fillet params.target=outer_edges unless the user explicitly requested top_edges or bottom_edges.",
                    "For slots and rectangular pockets, check abs(x)+feature_length/2 <= base_length/2 and abs(y)+feature_width/2 <= base_width/2 unless the user explicitly requests an overhanging/partial feature.",
                    "For two symmetric side slots with the same edge distance, if operation ids or descriptions indicate left/right sides, set left-slot center x=-base_length/2+distance and right-slot center x=base_length/2-distance. Use y=0 unless the user specified another y position.",
                    "If there are exactly two side-slot operations and the request says the slots are respectively distance d from the two side edges, but the operation ids do not literally contain left/right, assign the first slot to the left side and the second slot to the right side for center-coordinate repair.",
                    "For a pocket described only as being at the center position of the long-edge direction or length direction, set its center on that axis to 0 unless the user explicitly gives another coordinate. Keep the other axis inside the base boundary as well.",
                    "If the user's exact requested coordinate or size violates the boundary, do not silently change it; mark it explicit and let the caller ask for confirmation.",
                    "If the invalid coordinate or size was recommended by the model, replace it with a safer recommendation inside the boundary.",
                    "Keep all inferred lengths in mm.",
                    "For material repair, use only the official SOLIDWORKS material catalog exposed in the system prompt. Map user wording to the closest official SOLIDWORKS material name and put that official name in set_material.params.material, such as 6061 Alloy or AISI 304. material_id is accepted only for backward compatibility.",
                    "For set_material, use only params.material or params.material_id. Never use params.material_spec. MaterialSpec is only a custom-property key, not a set_material parameter.",
                    "For custom properties, use only PartNumber, Description, Designer, ProjectNo, Revision, or MaterialSpec as keys.",
                    "Map ?????????????/?????????????????part number/part no to PartNumber. Map ??????????????description to Description.",
                    "Never use script, macro, command, shell, powershell, python, delete, remove, or overwrite as custom property keys or values.",
                    "Do not add unrelated capabilities, operations, paths, scripts, or commands.",
                    "Do not add optional parameters unless they are required to express the user-requested modeling capability safely.",
                    "If a parameter is reported as missing source provenance and the user did not provide that exact parameter value, correct it as an inferred value and add the exact path to metadata.inferred_parameters.",
                    "If a hole is described by edge distance, the edge distance is explicit but the computed center coordinate is inferred.",
                    "If metadata provenance uses operation names instead of operation ids, replace operation names with actual operation ids. Example: create_through_hole.params.diameter must become 5.params.diameter if operation id 5 is the create_through_hole operation.",
                    "Do not put edge-distance-derived center coordinates in explicit_parameters; use inferred_parameters for the computed center coordinate.",
                    "For any hole or sketch center created with create_through_hole/create_blind_hole or sketch operations, params.center must be a JSON array [x, y]. Do not use objects like {\"x\": ..., \"y\": ...}.",
                    "Do not add params.center or params.plane to cut_center_hole. For centered boss/base holes, use cut_center_hole target=boss or target=base.",
                    "For metadata provenance, use only '<operation_id>.params.center' for a center coordinate. Never output '.center.x' or '.center.y'.",
                    "Return one corrected FeaturePlan JSON object only.",
                    f"Original user requirement: {prompt}",
                    f"Policy errors: {policy_errors}",
                    "Required fixes:",
                    repair_checklist,
                    "Rejected FeaturePlan JSON:",
                    json.dumps(rejected_data, ensure_ascii=False),
                ]
            ),
        },
    ]


def parse_featureplan(prompt: str) -> dict:
    base_url = os.environ.get("AI_SW_LOCAL_LLM_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    model = os.environ.get("AI_SW_LOCAL_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    api_key = os.environ.get("AI_SW_LOCAL_LLM_API_KEY", DEFAULT_API_KEY).strip() or DEFAULT_API_KEY

    if not base_url.startswith("http://localhost:") and not base_url.startswith("http://127.0.0.1:"):
        raise LocalProviderError("Local LLM base_url must point to localhost or 127.0.0.1")

    print("LLM provider: local")
    print(f"Local LLM base_url: {base_url}")
    print(f"Local LLM model: {model}")

    try:
        openai_client = _openai_client_class()
    except ImportError as exc:
        raise LocalProviderError("openai package is not installed") from exc

    try:
        client = _create_local_client(openai_client, base_url, api_key, stage="first_pass")
        started_at = time.perf_counter()
        response = client.chat.completions.create(
            **_chat_completion_kwargs(
                model,
                [
                    {"role": "system", "content": _local_system_prompt(prompt)},
                    {"role": "user", "content": prompt},
                ],
                stage="first_pass",
            )
        )
        _print_timing("first_pass", started_at)
        _debug_dump_local_provider_artifact("first_pass_raw.txt", _response_text(response))
        try:
            _debug_dump_local_provider_json("first_pass_json.json", extract_json_object(_response_text(response)))
        except Exception:
            pass
    except Exception as exc:
        raise LocalProviderError(f"Local LLM request failed: {safe_exception_message(exc)}") from exc

    try:
        return _validated_featureplan_from_response(response, prompt)
    except LocalProviderOutputError as first_error:
        if isinstance(first_error, LocalProviderConfirmationRequired):
            raise
        try:
            # Feed the repair model a *sanitized* rejected sample rather than the
            # raw LLM JSON. Otherwise malformed provenance paths (e.g. the
            # operation-name+id joined ``create_base_plate.001.params.plane``)
            # survive in the repair prompt and the local model simply copies them
            # back, producing the same "invalid parameter path" rejection after
            # every repair attempt.
            raw_rejected = extract_json_object(_response_text(response))
            try:
                sanitized_rejected = _normalize_featureplan_protocol(raw_rejected)
                sanitized_rejected = bind_featureplan_semantics(prompt, sanitized_rejected)
                sanitized_rejected = _normalize_featureplan_protocol(sanitized_rejected)
            except Exception:
                sanitized_rejected = raw_rejected
            rejected_data = _focused_rejected_data(sanitized_rejected)
            _debug_dump_local_provider_json("first_rejected_featureplan.json", rejected_data)
            print("Local LLM FeaturePlan rejected by Policy Engine; requesting local model repair.")
            repair_attempts = _repair_attempt_count()
            if _requested_feature_complexity(prompt) >= 4 and repair_attempts < 2:
                repair_attempts = 2
            if "semantic_completeness:" in str(first_error) and repair_attempts < 2:
                repair_attempts = 2
            last_error: LocalProviderOutputError = first_error
            if repair_attempts <= 0:
                raise LocalProviderOutputError(f"Local LLM FeaturePlan rejected without repair: {last_error}") from last_error

            repair_client = _create_local_client(openai_client, base_url, api_key, stage="repair")
            for attempt in range(repair_attempts):
                repair_started_at = time.perf_counter()
                repaired_response = repair_client.chat.completions.create(
                    **_chat_completion_kwargs(
                        model,
                        _repair_messages(prompt, rejected_data, str(last_error)),
                        stage="repair",
                    )
                )
                _print_timing(f"repair_{attempt + 1}", repair_started_at)
                _debug_dump_local_provider_artifact(f"repair_{attempt + 1}_raw.txt", _response_text(repaired_response))
                try:
                    _debug_dump_local_provider_json(f"repair_{attempt + 1}_json.json", extract_json_object(_response_text(repaired_response)))
                except Exception:
                    pass
                try:
                    return _validated_featureplan_from_response(repaired_response, prompt)
                except LocalProviderOutputError as repair_error:
                    if isinstance(repair_error, LocalProviderConfirmationRequired):
                        raise
                    last_error = repair_error
                    raw_repaired = extract_json_object(_response_text(repaired_response))
                    try:
                        sanitized_repaired = _normalize_featureplan_protocol(raw_repaired)
                        sanitized_repaired = bind_featureplan_semantics(prompt, sanitized_repaired)
                        sanitized_repaired = _normalize_featureplan_protocol(sanitized_repaired)
                    except Exception:
                        sanitized_repaired = raw_repaired
                    rejected_data = _focused_rejected_data(sanitized_repaired)
                    _debug_dump_local_provider_json(f"repair_{attempt + 1}_rejected_featureplan.json", rejected_data)
                    if attempt < repair_attempts - 1:
                        print("Local LLM repair still invalid; requesting one more local model repair.")
            last_error_text = str(last_error)
            salvage_triggers = (
                "cut_slot center is outside the current base boundary",
                "create_through_hole center is outside the current base boundary",
                "create_blind_hole center is outside the current base boundary",
                "missing source provenance",
                "plane must be exactly",
            )
            if any(trigger in last_error_text for trigger in salvage_triggers):
                salvaged = _attempt_semantic_salvage(prompt, rejected_data)
                if salvaged is not None:
                    return salvaged
            raise LocalProviderOutputError(f"Local LLM FeaturePlan rejected after repair: {last_error}") from last_error
        except LocalProviderError:
            raise
        except Exception as exc:
            raise LocalProviderError(f"Local LLM repair request failed: {safe_exception_message(exc)}") from exc





