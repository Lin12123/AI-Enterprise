# SOLIDWORKS VBA Runner

`AI_Enterprise_Runner.bas` is the fixed runtime macro for this Enterprise.

Usage:

1. Run the Python CLI and confirm generation of `workspace/jobs/current_job.ini`.
2. Open SOLIDWORKS manually.
3. Open the VBA macro editor.
4. Import `macros/AI_Enterprise_Runner.bas`.
5. Run `main`.
6. Check outputs in:
   - `workspace/outputs/parts`
   - `workspace/outputs/exports`
   - `workspace/outputs/previews`
   - `workspace/logs/run_log.txt`

Safety notes:

- The macro reads only `workspace/jobs/current_job.ini`.
- The macro writes generated model outputs only under `workspace/outputs`.
- The macro writes logs to `workspace/logs`.
- Existing output files are not overwritten; `_v001`, `_v002`, `_v003` style names are used.
- All dimensions are read as mm and converted to meters before SOLIDWORKS API calls.
- Some face or edge selections may need replacement with recorded macro snippets on your SOLIDWORKS version.
