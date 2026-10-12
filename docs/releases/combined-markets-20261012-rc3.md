# Combined KR/US recovery candidate rc3

- Candidate: `20261012-kr571-us143-rc3`
- Base: rc2 source `3247e6016f984953c9a00b86237d2d25c5b41adb` on `release/combined-markets-20261012-rc1`.
- Production baseline observed: KR `20261010v561`, US `20261009us132`.
- Product versions: KR `20261012v571`, US `20261012us143`.
- No strategy thresholds, subscriber consent, order placement or existing strategy fixtures changed.

## Verified causes and corrections

1. Domestic staging DB was running but web and collector deployments remained CRASHED/stopped. Scaling to one did not restart them. Restarting the same existing image restored `/readyz`, then critical data refreshed. `up` now restarts stopped deployments without rebuilding and requires DB-backed readiness; `prepare` leaves new-image deployment independent of the old app. Shutdown waits for applications to stop before removing the DB deployment, retaining its volume.
2. US E2E rejected all recent Yahoo frames even during active sessions. It now verifies frame source, live flag, exchange session and actual timestamp age, while preserving strict completed-session reference tests. Missing, stale, future and falsely realtime prices still fail.
3. Community history E2E injected state while navigation started a real async history fetch that could erase it. The history HTTP response is now fixed before navigation and checked again after load completion; no real subscriber push is sent by this test.
4. XLY/IYT returned empty one-day premarket charts and prevented the all-ETF snapshot validator from publishing any refresh. A bounded five-day minute fallback preserves the actual last-trade timestamp/date and marks reference rows and mixed payloads explicitly; complete source failure is not replaced with invented prices.
5. Domestic completed daily-price correction used a current quote stamped with the requested date. It now queries the dated KRX daily API and requires the exact returned business date and daily close. Official source: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_itemchartprice/inquire_daily_itemchartprice.py

## Release requirements

The user-supplied policy for this task requires staging both surfaces, recording exact source/digest and QA, then explicit approval of that exact tested candidate before production. This takes precedence over the older repository main-auto-deploy text. Do not push main or promote rc2. Source/artifact and runtime QA evidence are recorded in the corresponding workflow artifact after this commit is built; changing source creates a new candidate.
