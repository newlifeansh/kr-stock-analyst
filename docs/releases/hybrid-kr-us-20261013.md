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

Initial exact-image rollout: source `610b1f900b4190f99a4b1a63939b68ba38b316fa`, image `sha256:cbfbec8e78e19ae95ed0e60410b00c4bae501e325d0b36382358e3d59a2a0d4b`, production workflow `38401471764`. All four identities, both asset parity checks and critical-data readiness passed. US forward ledger initialized at `2026-10-13T13:08:42.250144+00:00`, with 100 completed-close setups and one eligible candidate, GILD. Push is configured; the diagnostic read sends no notifications.

Read-only live QA exposed an API aggregate defect: `entry_pending_count` retained the daily baseline's 0 while the forward ledger had one pending candidate. The correction recalculates pending/open counts from the forward ledger (including empty/preparing and closed-position states). The public methodology also retains the daily technical input explanation while explicitly distinguishing raw observed minute prices. Trading rules, ledger version and historical records are unchanged. Final local tests: 1,681 passed; QA mapping regression: 149 passed; gate: 151 passed. Intermediate missing/malformed parameterized-test mapping evidence is retained and corrected with all four exact JUnit case names; no missing case was waived.

Initial authenticated US production E2E: 5/5 passed, both mobile themes, workflow `38402841078`. The earlier local E2E lacked the invite credential; remote QA used existing protected authentication without changing it. KR E2E and corrected-image production verification remain pending; completion is not inferred from initial rollout success. Domestic initial live: 48 passed, 10 skipped, one non-P0 calendar request timeout. US initial live P0 contract failures remain in the original report until the corrected image is rechecked.

## Final deployed source and current evidence

- Production source: `6e267e97509ca2e75bdc1e67ab414042215a9c79` on `main`; final workflow `38406215696` succeeded.
- Exact image: `ghcr.io/newlifeansh/kr-stock-analyst@sha256:9920938678852416ada078cae271aab06da3aa25a45bc5af82f4006449ef8e3d`. Read-only identity run `38407117588` confirmed this digest on all four KR/US web/collector services. The earlier rollback digest above remains recoverable.
- Both production source/asset parity checks passed; both critical-data readiness checks passed. The last source change explicitly requests split events on minute transport and excludes only still-forming seconds-stamped Yahoo quote tails before applying strict finished-minute checks. Local final suite: 1,683 passed; gate 151/151; remote deterministic gate passed as well.
- Initial real opening responses contained a zero-volume seconds-stamped tail and were correctly blocked by the original stricter parser. The corrected parser was checked against the actual source response and a preserved deterministic fixture; no timestamp is rounded or invented and malformed finished minutes still fail.
- At `2026-10-13T13:41:25Z` (22:41 KST), production reported GILD `quote_state=fresh`, observed minute `13:40:00Z`, close approximately `$149.2868`, and fresh coverage `1/1`. The model remained `entry_pending` because entry conditions were not met. This proves current regular-minute collection, not an actual filled trade or delivered transition alert.
- The original ledger initialization `2026-10-13T13:08:42.250144+00:00` survived all redeployments. The collector has 100 completed-close setups, one eligible candidate, and no forward position/event at the recorded check. Existing subscriptions/opt-outs were preserved; configured US push polls every 60 seconds, and delivery remains conditional on a newly confirmed event.
- Final US live: 13 passed, no failures. Final-image KR remote live encountered a metadata request timeout with dependent missing-evidence failures; the complete original report is retained. A subsequent read-only KR run on the same deployed image passed 49 checks, skipped 10 session-inapplicable checks, and failed none (`artifacts/qa-hybrid-20261013/final-kr-live-retry.json`).
- Final-image US mobile E2E: 5/5 passed (`38406455221`). KR initial E2E: 19 passed, 7 failed, 2 skipped; explicit seven-case retry passed six, leaving `SIG-UI-025` blocked at the US login gate from a KR-authenticated context. Run `38408000860` authenticated that isolated cross-market fixture using the existing US gateway credential and passed the remaining case in both mobile themes. Original failures and explicitly scoped retry evidence are retained; this is cumulative evidence, not a claim that the first full suite passed.
- The provider intermittently returns a null latest completed row. Those polls deliberately show `awaiting_fresh_regular_quote` and cannot create a confirmation. The successful real-minute evidence does not establish continuous tick-level availability; no data-quality threshold was relaxed to force a signal.
- KR October 14 readiness is pre-open readiness based on the verified October 13 data, not a claim that October 14 live observations have already occurred. The seven individually excluded KR codes described above remain excluded until their evidence is sufficient.
