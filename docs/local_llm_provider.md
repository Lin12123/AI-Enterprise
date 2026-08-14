# Local LLM Provider

## Background

AI-SW-Enterprise is moving from a cloud-only OpenAI parsing path to a provider-based parser that can use local LLMs. This avoids blocking natural-language parsing when `OPENAI_API_KEY`, OpenAI quota, billing, or network access is unavailable.

## Purpose

The local provider uses a local Ollama model to convert natural language into controlled FeaturePlan v2 JSON. It does not directly control SolidWorks.

The execution chain remains:

```text
Natural language -> local provider -> FeaturePlan JSON -> Schema / Policy Engine -> fixed API Executor -> SolidWorks
```

## Requirements

Install and start Ollama before using local mode.

Download the default model:

```cmd
ollama pull qwen2.5-coder:7b
```

The default local OpenAI-compatible endpoint is:

```text
http://localhost:11434/v1
```

The local provider does not require `OPENAI_API_KEY` and does not read it.

## Offline / Air-Gapped Implementation (No Third-Party Packages)

The local provider talks to Ollama using **only the Python standard library** (`urllib.request`). It does **not** import `openai` or `httpx`, so it works in fully offline / air-gapped customer intranets where no extra Python package can be installed. Only Ollama itself needs to be installed on the local machine.

### How it works

- A built-in `OllamaClient` ([`local_provider.py`](../app/providers/local_provider.py)) posts JSON to Ollama's native chat endpoint `POST http://localhost:11434/api/chat`.
- It exposes an OpenAI-compatible surface — `client.chat.completions.create(**kwargs)` returning an object with `.choices[0].message.content` — so the parsing, JSON extraction, Policy validation, and repair-retry logic are unchanged.
- `AI_SW_LOCAL_LLM_BASE_URL` may keep the `/v1` suffix for backward compatibility; the client automatically normalizes `/v1` (or `/api`) to the native `/api/chat` path.

### Request mapping (OpenAI kwargs -> Ollama native)

| OpenAI-style kwarg | Ollama native field |
| --- | --- |
| `messages` | `messages` |
| `temperature` | `options.temperature` |
| `extra_body.num_predict` | `options.num_predict` |
| `extra_body.keep_alive` | top-level `keep_alive` |
| `response_format={"type":"json_object"}` | `format: "json"` |
| (fixed) | `stream: false` |
| `AI_SW_LOCAL_LLM_API_KEY` | `Authorization: Bearer <key>` header |

### Constraints

- `base_url` must point to `localhost` or `127.0.0.1`.
- Request timeout comes from `_request_timeout_seconds(stage)` and is passed directly to `urllib`.
- No `openai` / `httpx` install is required or performed anywhere in the local path.

### Output length (num_predict) — avoids truncated JSON

The model's max output tokens directly bound how large the returned FeaturePlan JSON can be. A complex part (7+ features, plus `metadata` provenance) can need 1500–2500+ tokens; if `num_predict` is too small the JSON is cut mid-object, `json.loads` fails with `LLM response was not valid FeaturePlan JSON`, and the request falls back to `rule_based` (which then rejects complex requests). Current defaults are sized for complex parts:

| Stage | Constant / Env | Default | Hard cap |
| --- | --- | --- | --- |
| First pass | `DEFAULT_FIRST_PASS_NUM_PREDICT` / `AI_SW_LOCAL_LLM_NUM_PREDICT_FIRST` | `2048` | `4096` |
| Repair | `DEFAULT_REPAIR_NUM_PREDICT` / `AI_SW_LOCAL_LLM_NUM_PREDICT_REPAIR` | `2048` | `4096` |

If a very large part still truncates, raise it at runtime without a rebuild:

```cmd
set AI_SW_LOCAL_LLM_NUM_PREDICT=3072
```

To confirm truncation, dump the raw model reply and inspect whether the JSON ends abruptly:

```cmd
set AI_SW_LOCAL_LLM_DEBUG_DIR=C:\temp\llm_debug
:: then inspect first_pass_raw.txt / first_pass_json.json in that folder
```

## Data Transformation Chain (Worked Example)

This traces one real request end-to-end so each hop's input and output is explicit. Example request (Chinese, as typed by the user):

> 画一个120mm*80mm*15mm的安装板，四角加直径为10的通孔四周边距10，安装板上加直径20的中心凸台，中心开直径20的通孔。沿着安装板上表面宽度方向分别在距离两边20mm处开2个宽度为8mm的通槽。再从上边面的长边中心，边距0mm处切割一个10mm*10mm*10mm的口袋，两侧各一个。安装板加圆角。

### Step 1 — Natural language -> chat messages

Input: the raw prompt string above.
Output: a two-message array built by [`parse_featureplan()`](../app/providers/local_provider.py) — a `system` message (the FeaturePlan parser rules from `_local_system_prompt`) plus the `user` message (the raw prompt).

```json
[
  {"role": "system", "content": "You are the AI-SolidWorks FeaturePlan parser. Output JSON only. ...(rules)"},
  {"role": "user",   "content": "画一个120mm*80mm*15mm的安装板，四角加直径为10的通孔..."}
]
```

### Step 2 — chat messages -> Ollama HTTP payload

Input: the messages plus tuning kwargs from `_chat_completion_kwargs()`.
Output: `OllamaClient._chat_create()` maps OpenAI-style kwargs to Ollama's native `POST /api/chat` body.

```json
{
  "model": "qwen2.5-coder:7b",
  "messages": [ /* system + user from Step 1 */ ],
  "stream": false,
  "options": { "temperature": 0, "num_predict": 2048 },
  "keep_alive": "10m",
  "format": "json"
}
```

### Step 3 — Ollama reply -> text content

Input: Ollama's raw HTTP JSON response.
Output: `OllamaClient` reads `data["message"]["content"]` and wraps it so the upper layers see an OpenAI-shaped object (`response.choices[0].message.content`).

```json
{ "model": "qwen2.5-coder:7b", "message": { "role": "assistant", "content": "{ \"version\": \"2.0\", ... }" }, "done": true }
```

`.content` (the string that matters) is a single FeaturePlan JSON object — no markdown, no code fences (enforced by the system prompt + `format: "json"`).

### Step 4 — text content -> FeaturePlan dict

Input: the `.content` string.
Output: `extract_json_object()` strips any stray fences, slices from the first `{` to the last `}`, and `json.loads` into a Python dict. Failure here (usually truncation) raises `LLM response was not valid FeaturePlan JSON`.

### Step 5 — FeaturePlan dict -> validated 9-step plan

Input: the parsed dict.
Output: `_validated_featureplan_from_response()` runs schema shape checks + Policy Engine. For this request it yields **9 operations**, in dependency order:

```json
{
  "version": "2.0", "unit": "mm", "document_type": "part", "part_name": "unnamed_part",
  "operations": [
    {"id": "create_base_plate",   "op": "create_base_plate",      "params": {"length": 120, "width": 80, "thickness": 15}},
    {"id": "create_center_boss",  "op": "create_center_boss",     "params": {"diameter": 20, "height": 5}},
    {"id": "cut_center_hole",     "op": "cut_center_hole",        "params": {"diameter": 20, "through_all": true}},
    {"id": "cut_corner_holes",    "op": "cut_corner_holes",       "params": {"diameter": 10, "edge_margin": 10}},
    {"id": "cut_slot_1",          "op": "cut_slot",               "params": {"width": 8, "direction":"y"}},
    {"id": "cut_slot_2",          "op": "cut_slot",               "params": {"width": 8, "direction": "y"}},
    {"id": "cut_rectangle_pocket_1","op": "cut_rectangle_pocket", "params": {"length": 10, "width": 10, "depth": 10}},
    {"id": "cut_rectangle_pocket_2","op": "cut_rectangle_pocket", "params": {"length": 10, "width": 10, "depth": 10}},
    {"id": "add_fillet",          "op": "add_fillet",             "params": {"radius": 2, "target": "outer_edges"}}
  ],
  "metadata": {"explicit_parameters": {"create_base_plate.params.length": 120}, "inferred_parameters": {}},
  "outputs": {}
}
```

### Step 6 — validated plan -> SolidWorks

Input: the validated FeaturePlan.
Output: after the explicit confirmation gate, the API Executor runs each operation as a `Feature.<op>` call against SolidWorks. The parser itself never touches SolidWorks.

> Note: parameter values above are illustrative of the shape/order; exact inferred values (boss height, fillet radius, slot span, pocket placement) are filled by the model and then bounded by the Policy Engine.

## CMD Configuration

```cmd
set AI_SW_LLM_PROVIDER=local
set AI_SW_LOCAL_LLM_BASE_URL=http://localhost:11434/v1
set AI_SW_LOCAL_LLM_MODEL=qwen2.5-coder:7b
set AI_SW_LOCAL_LLM_API_KEY=ollama
set AI_SW_EXECUTOR_MODE=api_executor
set AI_SW_API_DRY_RUN=1
python app\main.py "Create a 120x80x12 mm base plate"
```

## PowerShell Configuration

```powershell
$env:AI_SW_LLM_PROVIDER="local"
$env:AI_SW_LOCAL_LLM_BASE_URL="http://localhost:11434/v1"
$env:AI_SW_LOCAL_LLM_MODEL="qwen2.5-coder:7b"
$env:AI_SW_LOCAL_LLM_API_KEY="ollama"
$env:AI_SW_EXECUTOR_MODE="api_executor"
$env:AI_SW_API_DRY_RUN="1"
python app/main.py "Create a 120x80x12 mm base plate"
```

## Provider Modes

| Provider | Use Case | Key Requirement | Failure Behavior |
| --- | --- | --- | --- |
| `rule_based` | Default local parser and safety fallback | none | No LLM call |
| `openai` | Cloud OpenAI structured parsing | `OPENAI_API_KEY` | Falls back to `rule_based` on quota, billing, auth, timeout, network, or JSON errors |
| `local` | Local Ollama semantic parsing | local Ollama service (no `openai`/`httpx` package needed) | Falls back to `rule_based` on connection, model, or JSON errors |

## How To Confirm Local Mode

When local mode is selected, CLI output may show:

```text
LLM provider: local
Local LLM base_url: http://localhost:11434/v1
Local LLM model: qwen2.5-coder:7b
```

The local API key is never printed.

If Ollama is unavailable, CLI output shows:

```text
Local LLM unavailable, fallback to rule_based parser.
```

## Safety

- Local LLM output may only be FeaturePlan JSON.
- The local prompt forbids Python, VBA, PowerShell, Shell, cmd, scripts, macros, commands, and direct execution instructions.
- The local prompt forbids `output_dir`, `path`, `file_path`, `save_path`, `delete`, `remove`, `overwrite`, and `subprocess`.
- All FeaturePlans must still pass schema shape checks and Policy Engine validation.
- `dry_run` does not connect to SolidWorks.
- Real API execution still requires the existing explicit confirmation gate.

## Regression Boundaries

- `openai` provider remains available.
- `rule_based` provider remains available.
- `legacy_vba` remains available through `AI_SW_EXECUTOR_MODE=legacy_vba`.
- The old `current_job.ini` / `job.ini` compatibility path is not removed.
