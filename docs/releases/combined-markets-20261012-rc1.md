# Combined KR/US candidate — 2026-10-12 rc1

- Release branch: `release/combined-markets-20261012-rc1`.
- Pending-work checkpoint: `63d6616` (all 37 previously uncommitted files).
- Integrated upstream: `a1391a67a92c1bf795b63821d776bc0e80930aea` (financial-series fixes and subsequent verified data/QA corrections).
- Observed production versions before this release: KR `20261010v561` / US `20261009us132`.
- Candidate client versions: KR `20261012v569` / US `20261012us141`.
- Strategy versions and execution rules are not newly tuned in this candidate. The pending work and upstream fixes are preserved.

## Included changes

- Compact 7/15/30-day completed-trade averages, count, win rate, sample warning and as-of date.
- KR summaries retain cost-adjusted model-return semantics; US summaries explicitly use gross model price returns, excluding costs, tax and FX. These are not account returns.
- US aggregation uses all verified replay events before display limits. Future, partial, invalid and duplicate exits are excluded. US summary refresh is additive and never enables the KR entry guard.
- KR performance snapshot key advances from v35 to v36 so old 30/90-only summaries cannot masquerade as current 7/15/30-day data.
- Previously pending community alert opt-in, deadline/retry/deep-link behavior, recommendation exit exclusion, news classification, AI-response UI and mobile layout changes.
- Automatic community alerts have QA ID `SIG-PUSH-COMMUNITY-002`; the existing operator-authorized one-off broadcast retains `SIG-PUSH-COMMUNITY-001`. Automatic opt-in is not bypassed by operator-only dispatch support.
- Preserve financial-series, US entry-basis, intraday evidence, data refresh and holiday fixes from the upstream candidate.

## Evidence and promotion

Full pytest/JUnit and machine QA gate are recorded under `artifacts/qa-combined-markets/` locally and in the release workflow. The stage workflow records the immutable OCI digest and source SHA, deploys that digest to both preproduction surfaces, and retains parity, live and browser evidence.

For this request, the explicitly supplied staging/approval policy remains governing even though the integrated historical repository policy describes optional staging: no production promotion until the operator reviews and approves this exact staged candidate. Do not push to main to bypass that requirement.
