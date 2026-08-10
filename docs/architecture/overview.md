# Architecture Overview

AI-SW Enterprise evolves the verified Enterprise into a safer enterprise CAD automation architecture.

## Implemented Legacy Chain

Natural language -> CADPlan Lite -> validator.py -> job.ini -> fixed VBA Runner -> SolidWorks automatic modeling.

## Scaffolded API Chain

FeaturePlan v2 -> Feature Registry -> Policy Engine -> fixed SolidWorks API Executor -> SolidWorks API.

The API chain supports dry-run planning without connecting to SOLIDWORKS. Confirmed real execution is limited to implemented mounting-plate operations and connects only to an already-open SOLIDWORKS instance.

## Module Boundaries

- `cad_dsl`: FeaturePlan v2 schema, typed plan definitions, and Feature Registry.
- `policy`: validation, allowlists, geometry limits, path controls, and execution policy.
- `LocalAgent`: local orchestration that never executes LLM-generated code.
- `solidworks_api`: fixed executor interface for future SolidWorks API operations.

## Capability Labels

- implemented: working legacy compatibility behavior.
- scaffolded: code and docs exist, but the operation is not executable.
- planned: documented future capability with no executor support yet.
