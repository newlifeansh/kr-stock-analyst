# Post-rc6 staging cleanup correction

The rc6 product image remains unpromoted. Its US live/E2E passed (13/5); domestic E2E passed (26), but domestic live retains one P0 session-basis failure (48 pass / 1 fail / 10 skip). Gateway QA was skipped. See the local report under `artifacts/qa-combined-markets/rc6/REPORT.md`.

The final rc6 shutdown also failed: the collector did not remain stopped after the scale patch. The DB was correctly retained, not removed under an active collector. A single successful stop observation is therefore insufficient while a scale-triggered deployment can appear asynchronously.

`stop_application` now stops reappearing active deployments of the explicitly selected staging app at most three times, requires 30 seconds of continuous stopped state, and retains the DB on deadline/failure. This is a release-control-only change, not a strategy or user interface change. A regression reproduces an application reappearing after the first stop. DATA-COM-005 and the rendered matrix are updated.

- Deterministic tests after this fix: 1,563 passed (including 10 runtime tests).
- A `stop-staging` run will verify the cleanup against the existing rc6 services without a rebuild or production action.
- This source change supersedes rc6 as a promotable source. No fresh product image has been built from this cleanup commit. A future candidate must be rebuilt/staged after resolving the regular-vs-after-market data basis and receive exact-candidate approval.
