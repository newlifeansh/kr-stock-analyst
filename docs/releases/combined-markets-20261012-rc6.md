# Combined KR/US recovery candidate rc6

- Candidate: `20261012-kr572-us144-rc6`.
- Base: `7721f83` on `release/combined-markets-20261012-rc1`.
- Client versions remain KR `20261012v572`, US `20261012us144`; neither rc4 nor rc5 was promoted or built. Both were cancelled during gate before deployment.
- Inherits rc3–rc5 fixes, all original uncommitted work, and the strict user-supplied staging/approval policy.

## Operational correction

Actual rc4 shutdown left the old apps serving after scale=0. `stop_application` now explicitly stops the active application deployment if scaling leaves it running, then checks that the process is stopped before stopping the DB. Source image, service definitions and volumes are retained. An explicit stop failure retains the DB and fails QA. Two new deterministic regressions cover both outcomes; DATA-COM-005 is updated.

## Source-session finding (not yet a strategy change)

KIS announced KRX after-market trading from 16:00 to 20:00 effective 2026-09-14, with new realtime `MARKET_CLS_CODE` values 1 premarket, 2 regular, 3 after-market, 5 closing-price market. KRX venue J therefore does not identify a regular-only price series. This explains why J can legitimately return post-15:30 trades; it does not alone prove which returned daily fields include those trades. Current raw daily/minute OHLC mismatches remain recorded as failures, and no historical prices or seal validation have been altered.

- Official notice: https://apiportal.koreainvestment.com/community/10000000-0000-0011-0000-000000000001/post/26dfe350-eb72-48e5-8175-34eb27970f3e
- Public notice API: https://apiportal.koreainvestment.com/api/forums/10000000-0000-0011-0000-000000000001/posts/26dfe350-eb72-48e5-8175-34eb27970f3e
- Official tick fields: https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/ccnl_krx/ccnl_krx.py

Do not broaden the signal strategy to extended trading or rewrite historical daily prices without deciding and verifying the session basis. Required P0 evidence and exact-candidate approval remain outstanding. Record fresh source/digest and gate/live/E2E evidence from the rc6 staging run, not superseded candidates.
