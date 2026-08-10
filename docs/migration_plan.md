# AI-SW Enterprise Migration Plan

This project starts from the verified AI-SW-Enterprise baseline and keeps the Enterprise compatibility layer intact during enterprise development.

## Current Enterprise Compatibility Layer

- `app`: natural language parsing, validation, and job writing.
- `macros`: fixed SolidWorks VBA runner assets retained for compatibility.
- `schemas`: CADPlan Lite schema.
- `tests`: Enterprise regression tests.

## Target Enterprise Direction

Natural language -> CADPlan or FeaturePlan -> Feature Registry -> Policy Engine -> fixed SolidWorks API Executor -> SolidWorks API.

## Current Status

- implemented: legacy CADPlan Lite -> fixed VBA Runner compatibility path.
- scaffolded: FeaturePlan v2, Feature Registry, Policy Engine, and SolidWorks API Executor boundary.
- implemented: confirmed API execution path for current mounting-plate operations, guarded by Policy Engine and explicit user confirmation.
- planned: broader official SolidWorks feature mappings and additional document types.

## Near-Term Priorities

- Define CADPlan and DrawingPlan schema boundaries.
- Build Policy Engine validation rules before executor work.
- Specify the executor interface before binding to SolidWorks.
- Preserve Enterprise tests and add enterprise tests alongside them.
- Keep outputs restricted to controlled project workspace paths.
- Keep legacy VBA assets available until the API Executor reaches parity.
