# Combined KR/US recovery candidate rc5

- Candidate: `20261012-kr572-us144-rc5`.
- Parent source: `94f6d6e` (rc4); product versions remain KR `20261012v572`, US `20261012us144`.
- rc4 was cancelled during its remote gate before any image build or deployment: the new parameterized test IDs did not match the machine-readable gate mapping. The assertions passed but their evidence was missing for the QA case. This candidate uses one stable mapped test that exercises all four KR/US popular/latest combinations. No QA failure is reclassified or ignored.
- Product changes and release boundaries are in `combined-markets-20261012-rc4.md`; all remain applicable. Production is not approved or changed.

## Cross-symbol source diagnostic

Read-only workflow `38259389351` confirms the daily/minute discrepancy is not unique to Samsung:

| Code / date | Dated minute evidence | KIS dated daily J |
| --- | --- | --- |
| 005930 / Oct 8 | 380 points ending 15:19, no closing auction; last 264,500, low 263,000 | close 262,000, low 262,000 |
| 000660 / Oct 12 | 381 points ending 15:30; close 1,605,000, low 1,605,000 | close 1,605,000, low 1,597,000 |
| 373220 / Oct 12 | 381 points ending 15:30; close 398,000, low 395,500 | close 396,500, low 391,500 |

These are raw response observations, not an assertion that every daily or minute series is correct. Incomplete Oct 8 data must not be substituted for a complete session. The current exact close-path validation remains fail-closed. No change to regular vs extended/NXT strategy scope or historical price rewrite is included. The temporary diagnostic SSH key was removed after the read-only probes.

Record this candidate's full source, immutable image digest and fresh QA results from its workflow. Required P0 failures and exact-candidate operator approval still block production promotion.
