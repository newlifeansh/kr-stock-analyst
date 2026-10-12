# Combined KR/US recovery candidate rc4

- Candidate: `20261012-kr572-us144-rc4`.
- Base: rc3 source `1309218cfd64be8629cdfd2f365b58315b9ab041` on `release/combined-markets-20261012-rc1`.
- Production baseline: KR `20261010v561`, US `20261009us132`; not promoted.
- Product versions: KR `20261012v572`, US `20261012us144`.
- Includes all rc3 recovery corrections and original uncommitted work preserved at `63d6616`.
- No signal strategy thresholds, price-series rewrites, order placement or subscriber broadcasts.

## New correction

The repaired community-history E2E exposed an actual cold-navigation bug: `initializeDashboard` loaded the stock directly, while only popstate navigation ran `syncViewFromLocation` and applied `tab=community&community_mode=popular`. Initial stock navigation now uses the same route synchronizer, still in parallel with identity initialization. Deterministic KR/US tests cover popular/latest community links and restoring the intended tab after stock hydration. QA case `SIG-PUSH-COMMUNITY-002` and its generated matrix are updated.

## Retained rc3 evidence and open blocker

- rc3 gate: 1,559 pytest passes, 147 QA passes.
- rc3 US: 13 live and 5 E2E passes, matching source/asset parity.
- rc3 domestic: 47 live passes, 2 P0 failures; 25 E2E passes, 1 P1 failure, 2 scope skips. Gateway QA did not run.
- The community P1 is addressed by this candidate; it requires fresh browser verification.
- One P0 was a `refreshing` signal feed during warmup; later API reads returned ready, but a new recorded QA run is required.
- `SIG-KR-INTRADAY-SEAL-001` is an unresolved upstream-data contradiction, not cleared: on 2026-10-12 Samsung 005930, both KIS current and dated regular-session minute series end at 15:30 with close 250,500 and low 249,500, while KIS dated daily J and legacy daily J return close 251,000 and low 249,000. Open/high agree. Stored daily data matches the latter. J/NX/UN requests were sent separately; J minute requests after regular close also return trades through 20:00. This does not prove all requested J data is KRX-only or establish which daily endpoint is correct for the regular-session strategy.
- Do not manufacture a closing bar, re-label an extended price as 15:30, silently rewrite historical daily series, loosen exact seal validation, or promote this candidate while required P0 evidence fails.
- Official KIS parameter reference: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_time_itemchartprice/inquire_time_itemchartprice.py

## Release boundary

Record the source SHA and immutable digest from this build. Stage both surfaces and collect fresh gate/live/E2E evidence. The direct user policy requires explicit approval of this exact tested candidate after reviewing us-market, then promotion of the same digest without rebuild. No main push or production deployment is authorized by staging alone. Market-basis changes or an exception require a separate informed decision; no automatic strategy promotion is included.
