# LocalAgent

Coordinates local enterprise CAD automation without executing LLM-generated code.

Initial work:

- Accept only validated CADPlan or DrawingPlan inputs.
- Call Policy Engine before executor handoff.
- Keep all artifacts inside controlled workspace paths.
- Record auditable job metadata without exposing secrets.
