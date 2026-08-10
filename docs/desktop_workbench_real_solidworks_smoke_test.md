# AI-SW Workbench Real SOLIDWORKS API Smoke Test

This is a manual smoke test for the Workbench real SOLIDWORKS API execution path. Do not run it as an automated test.

## Preconditions

- SOLIDWORKS is installed.
- SOLIDWORKS is started manually before real run.
- The default Part template is valid in SOLIDWORKS.
- `pywin32` is installed manually in the active Python environment.
- The project virtual environment is active.
- Do not run any VBA macro for this test.
- Do not use real customer CAD files.

## Manual Test Steps

1. Start SOLIDWORKS manually and leave it open.
2. From the project root, start AI-SW Workbench:

   ```powershell
   python -m ui_desktop.main
   ```

3. In the natural-language input box, enter:

   ```text
   画一个120×80×12mm的安装板，四角M6通孔，中间有直径30mm高度25mm的凸台，中心开10mm通孔，边缘R3圆角。
   ```

4. Select the intended provider, usually `local` or `rule_based` for offline testing.
5. Click `Generate Plan`.
6. Review the FeaturePlanCandidate:
   - base plate dimensions are 120 x 80 x 12 mm
   - four corner holes are present
   - center boss is diameter 30 mm and height 25 mm
   - center hole is 10 mm
   - fillet radius is 3 mm
   - only implemented operations are present
7. Click `Validate`.
8. Confirm validation passes and `blocking_errors` is empty.
9. Click `Dry Run`.
10. Confirm every operation is planned and no SOLIDWORKS connection is made during dry run.
11. In the confirmation box, type exactly:

    ```text
    YES_RUN_SOLIDWORKS_API
    ```

12. Click real execution.
13. In SOLIDWORKS, inspect the generated model:
    - rectangular base is correct
    - four M6 clearance holes exist
    - center boss is correct
    - center through hole exists
    - outer edges have R3 fillet
14. Rebuild the model in SOLIDWORKS and confirm no rebuild error.
15. Inspect the Workbench job directory under:

    ```text
    outputs/jobs/job_xxx/
    ```

16. Confirm these files exist:
    - `execution.log`
    - `outputs.json`
17. Confirm `outputs.json` records generated SLDPRT / STEP / PNG paths when those outputs are enabled.
18. Confirm no macro or VBA was run.

## Pass Criteria

- Real execution requires `YES_RUN_SOLIDWORKS_API`.
- Policy Engine validation is not bypassed.
- No scaffolded, planned, unsupported, or unknown operation is executed.
- Workbench records `execution.log` and `outputs.json`.
- Output paths remain controlled by the project.
- No macro or VBA is run.

## Failure Notes

If SOLIDWORKS connection fails, record the Workbench error from `execution.log`.
Do not retry by running a macro. Fix the SOLIDWORKS environment or API Executor path first.
