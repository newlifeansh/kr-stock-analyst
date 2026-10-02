# Intraday Top100 RC1

## Scope and isolated bases

- Domestic base: `2da0ebf` / `hotfix/domestic-fold-layout-20260925`.
- US base: `f794377` / `hotfix/us-calendar-prod125-20261001`.
- Existing uncommitted work in the original checkout is excluded.
- New signal version: `intraday-top100-v1-rc1`; no daily history rewriting.
- No broker order code. Confirmed means the signal decision is persisted, NOT a fill or a guaranteed return.
- Each independent deployment scans its own market's previous completed-session Top100, plus retained open positions.

## Frozen RC policy (not a proven performance improvement)

All Top100 names are scanned; membership is NOT limited to yesterday's buy signals.
Prior completed daily quality and evidence are inputs: KR score 64/US 65,
ATR at most KR 4.5%/US 5.5%, five-session momentum 0.5–10%, daily volume ratio
at least 1, average turnover KR KRW5bn/US USD50m. Existing evidence must be
fresh for the previous completed session. This is not a new same-day
institutional-flow model.

After at least 20 regular-session minutes, a completed five-minute candle
must reclaim/retest a rolling 20-minute volume-weighted typical price and
close above prior EMA20/60. This is explicitly NOT full-session VWAP.
Current price must remain above the rolling reference, within 1% of it,
within 3% of prior close and no more than 0.5% above the confirming close.
Missing minutes, future timestamps, invalid OHLC, stale quotes (>90s), or
missing context block new buys.

Exits use the newest observed price, not retrospective candle high/low:
+3% half, +5% remaining; initial ATR stop between 1–4%; after the first
partial the remaining protective reference is entry +0.4%. A gap beyond +5%
before the first partial generates one full exit, not two fictional fills.
The +0.4% cushion is a model allowance, NOT a brokerage fee guarantee.
No same-session re-entry in this RC. Prior strategy holdings are NOT silently
imported into this new ledger. Daily and intraday records remain distinguishable.

## Operations and limitations

`INTRADAY_SIGNAL_MODE=off|shadow|alerts` defaults to off. Staging uses shadow.
Shadow never sends push and has a separate state/event namespace from alerts.
Activating alerts therefore starts a fresh signal ledger, not a retroactive
import of shadow positions. Existing daily notification policy is unchanged.

Only collector processes run the monitor. The existing provider supplies
rate-limited REST minute observations with four concurrent requests; cycles
do not overlap. PostgreSQL advisory locking serializes replicas. The poll
pause defaults to 30s AFTER a cycle, so latency is cycle duration + poll delay,
not a promise of instantaneous/tick-level alerting. Quotes that age during
slow context preparation fail closed. Validate full Top100 latency in-session
before enabling alerts.

Korea: KIS KRX-only one-minute API. US: KIS overseas one-minute API, NYSE/Nasdaq
venue, New York timestamps and official session calendar including DST/early
closes. A subscription or entitlement returning delayed data is never
silently treated as real-time. API availability does not establish entitlement
or freshness for all symbols.

Append-only completed minutes and immutable signal events persist across
restart. The dashboard reports stale monitor status after three minutes.
Separate market endpoints and event pages:
- KR: `/market/intraday-signals`, `/intraday-alerts`
- US: `/us/market/intraday-signals`, `/us/intraday-alerts`

Push requires alerts mode, VAPID readiness, browser permission, and existing
market-signal opt-in; no new subscription is created by deployment. Only
recent events occurring after registration/preferences update are delivered.
Provider raw exceptions/credentials are not logged or returned.

## Validation / promotion gate

Run deterministic intraday, existing daily, provider, and web-push regressions;
render the machine-readable catalog with `analyst qa render-catalog`.
Run `scripts/qa_intraday_monitor.py --mode live|e2e` against each shadow
candidate. Closed-session checks establish wiring, NOT in-session readiness
or improved investment performance. Require a real full-universe regular
session cycle, latency/coverage, and an opted-in test device before claiming
operational push readiness.

Record each source SHA, parent production version, immutable image digest,
and QA evidence. Preserve market-specific production fixes. Deploy candidates
to us-market preproduction before any domestic production promotion; never
overwrite another active candidate without coordination. Production remains
unchanged until the operator approves the exact tested artifact.

Source API contracts:
- https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/domestic_stock/inquire_time_itemchartprice
- https://github.com/koreainvestment/open-trading-api/tree/main/examples_llm/overseas_stock/inquire_time_itemchartprice
