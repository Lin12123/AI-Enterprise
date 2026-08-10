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
| `local` | Local Ollama semantic parsing | local Ollama service | Falls back to `rule_based` on connection, model, SDK, or JSON errors |

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
