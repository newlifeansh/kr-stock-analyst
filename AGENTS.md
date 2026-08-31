# QA maintenance policy

- Every product behavior change or new feature must add or update the corresponding machine-readable QA case in `app/qa/data_signal_cases.json`.
- Keep each case traceable with a stable QA ID, priority, preconditions, inputs, procedure, expected result, failure criteria, and automation mode.
- Regenerate `docs/qa/data-signal-qa-matrix.md` with `analyst qa render-catalog` after catalog changes.
- Add or update deterministic tests for changed data integrations, signal rules, API contracts, and UI behavior. Preserve regression fixtures for older signal strategy versions.
- Before handoff, run the relevant `gate`, `live`, and `e2e` QA modes in proportion to the change. Do not clear a P0 failure without recorded evidence.
