# QA maintenance policy

- Every product behavior change or new feature must add or update the corresponding machine-readable QA case in `app/qa/data_signal_cases.json`.
- Keep each case traceable with a stable QA ID, priority, preconditions, inputs, procedure, expected result, failure criteria, and automation mode.
- Regenerate `docs/qa/data-signal-qa-matrix.md` with `analyst qa render-catalog` after catalog changes.
- Add or update deterministic tests for changed data integrations, signal rules, API contracts, and UI behavior. Preserve regression fixtures for older signal strategy versions.
- Before handoff, run the relevant `gate`, `live`, and `e2e` QA modes in proportion to the change. Do not clear a P0 failure without recorded evidence.

# Release promotion policy

- Treat an approved merge to `main` as production release intent. Every `main` push must pass the deterministic pytest and QA gate before deployment starts.
- Build one immutable OCI image for the tested `main` commit, record its source SHA and digest, and deploy that exact digest to the US and domestic production web/collector services without rebuilding.
- Staging is optional and remains available for manual diagnosis or explicitly requested high-risk observation; it is not a prerequisite for the normal `main` production path.
- After deployment, verify both production surfaces against the checked-out source version and asset hashes and wait for current critical data. A parity or readiness failure is a failed release.
- Run read-only live QA after every deployment and retain its complete evidence. Operational/provider P0 findings remain visible as workflow warnings and follow-up evidence; they do not retroactively undo an exact-image deployment whose deterministic gate, parity, and critical-data readiness passed.
- Keep the previous known-good image digest recoverable for rollback. A source change creates a new candidate and must pass the gate again.
