# KR/US hybrid forward release — 2026-10-13

## Intent and baseline

- Operator approved both production surfaces, no additional staging approval wait.
- Source branch: `codex/hybrid-kr-us-20261013`, based on `32fa5fe` (rc14 documentation), production code `67e503d7d6616f37865b5caa01a406aca66131b5`.
- Recoverable previous exact image: `ghcr.io/newlifeansh/kr-stock-analyst@sha256:5f123fc0137d2735271fa1358c3d160de77dc06b851d1553902fb0d8f0fb87cf` (all four production services).
- Candidate dashboard versions: KR `20261013v574`, US `20261013us146`.
- KR strategy stays `position-lifecycle-v8.1`; US forward strategy is `position-lifecycle-us-v3-hybrid1`. The v2 completed-day replay remains a separately versioned, regression-tested close-setup/baseline generator.

## Actual behavior, not broker orders

KR retains its verified regular-session intraday execution model. US now has an independent 30-second collector loop reading completed-close Top100 setups and fresh completed regular-session 1-minute bars. It does not run the expensive full daily replay on every tick or request.

US entries require a valid previous completed session's candidate, raw-price/ATR conversion from traded notional, an opening gap within the smaller of 5% and 1.5 ATR, and two consecutive completed closes between the reference close and that envelope. Both confirmation minutes must follow setup arming; a mid-session restart does not manufacture historical entries.

Observed subsequent minute-close returns trigger an original-position 50% sale at +3%, all remaining exposure at +5%, or an initial -4% stop. After the first sale, a return to entry price closes the remainder. A jump over both profit targets closes all at the actually observed price. Daily EMA20 deterioration can trigger an observed-price exit in the following regular session. Returns are gross before fees, taxes, spread, slippage and FX; a gap loss is not capped at -4%. Minute-close confirmation can miss an intraminute touch; no tick-perfect or guaranteed-price claim is made.

Exchange calendars enforce holidays, DST and early closes. Source identity, USD currency, finite positive OHLCV, strict minute ordering, completion and maximum 90-second age from minute end are mandatory. Delayed feeds, missing/invalid latest minutes and contemporaneous splits block new confirmations. Stored events retain exact input minutes for audit.

The durable ledger uses checksum validation and compare-and-swap publication. Repeated minutes, restarted workers and same-session re-entry cannot duplicate an event. Corruption raises an error; it never silently initializes a new ledger.

The last v2 publication and performance are frozen separately. Old v2 model holdings are **not** treated as personal brokerage holdings or carried into the new forward ledger; the new ledger starts flat. No old signal is rebroadcast. Existing subscriptions and opt-outs are unchanged. Confirmed events expire for push after 180 seconds and market/watchlist delivery share one dedupe key.

Public feed, detail, recommendation, MCP and alerts read the same forward state. UI returns use the model's observed regular minute, not an independently selected extended-hours quote. Collector/daily setup readiness and price freshness remain distinct; stale entry evidence cannot hide the durable record of an existing position.

## Validation and operational findings

- Final local serial run: 1,677 deterministic tests passed; 151/151 QA gate cases passed, no P0 failure/missing evidence. Evidence: `artifacts/qa-hybrid-20261013/pytest.xml` and `gate.json`. A preceding concurrent test run had one shared-database history-fixture failure; the isolated regression and subsequent full serial suite both passed. No product rule or assertion was relaxed to clear it.
- Deterministic suite and machine-readable QA gate run before production build; `SIG-US-HYBRID-001` covers forward execution, persistence, freshness, split/gap handling, notifications and public contracts. v2 fixtures remain intact.
- October 13 KR read-only snapshot: 7 individually blocked codes. 357870/360200/381170 have only 37 complete warm-up rows (minimum 125); no invented backfill or relaxed threshold. 010060/039030/278470/310970 have complete frozen warm-up but missing opening-minute volume anchors, so cross-source verification of current regular-session evidence fails. Read-only diagnostic run `38399491717` preserved these reasons. Other 143 names are not blocked by this condition; no relaxation of the evidence requirement was made.
- Rollout verification must record tested source SHA, immutable image digest, all four service identities, KR/US asset parity, current critical-data readiness and read-only live QA. Actual US regular-session observations must be checked after today's opening; pre-market unit tests are not that evidence.

## Deployment record

Pending execution of the tested-main immutable-image workflow. Do not infer deployment completion from this document or a successful local test.
