# Railway runtime cost controls

The September 21–October 21 bill primarily reflects continuously running resources. Stopping services affects future compute usage; existing charges and retained-volume charges remain.

## Staging

Both scheduled live QA and manual E2E pin the current web/collector image, start the selected database and application pair, and always stop applications before their database. Cleanup runs in a separate job so a QA job timeout cannot skip its teardown. A failed or unverified application shutdown preserves the database. `railway down` removes a deployment, preserving its service, variables, source image and volume; region=0 is not used as a stop operation.

US staging uses `Postgres-zJWq` (`4dea68bb-0b54-43b1-b791-aaed0b7fb118`). Its web, collector and personal MCP all referenced that private hostname in the baseline audit. The old `Postgres` and personal MCP are included in `US_STAGING_RAILWAY_EXTRA_STOP_SERVICES` and stay stopped outside explicit diagnostics. Ordinary dashboard QA resumes only web, collector and the shared database. To diagnose the personal MCP, start its shared DB and explicitly resume its retained deployment; run `stop-staging` with surface `us` afterwards. Do not delete the old database volume as part of cost controls.

The release workflow also prepares US staging before a candidate deployment and shuts both staging surfaces down after QA. `observe_session` retains only domestic staging when explicitly requested. The shared `domestic-staging-runtime` concurrency lock covers both surfaces and prevents a scheduled QA job stopping another workflow's staging session.

## Bulk collection

`MAINTENANCE_SUBPROCESS_ENABLED=true` is applied to production and staging collectors by the deployment workflows. Universe refresh, research backfill, DART financials, full-universe fundamentals, company snapshots and logos execute as disposable subprocesses inside the existing collector container. There is no additional always-on Railway service. Existing due intervals and result/error/retry bookkeeping remain intact; flow, price and priority Top100 fundamentals retain their existing lanes.

Only one bulk subprocess runs at a time. Each uses the parent's validated settings via stdin and owns its database session. Provider output is suppressed; only a bounded result is returned. Process exit releases temporary batch memory. The default 1,800-second deadline kills and reaps the process group, and Linux workers exit if their parent dies. The parent collector and the separate freshness lane remain running. This reduces retained batch memory, not the instantaneous peak while a batch is running.

Logs under `uvicorn.error.maintenance` identify job start, successful exit and failures without settings or provider output. Briefing runtime status includes process mode and completion/failure counters. For rollback, disable `MAINTENANCE_SUBPROCESS_ENABLED` on collectors and redeploy the same image; the inline implementation remains available.

## Ollama and production

All production app roles use `STOCK_AI_PROVIDER=rules`; deterministic calculations and rule-based analysis remain active. After exact-image deployment, source/asset parity, critical-data readiness and UI verification pass, the main workflow checks both domestic app roles are running that digest with the rules provider and that no project service still selects Ollama. Only then does it stop the configured Ollama deployment. Its service and volume remain recoverable.

Previous production image before this change:

`ghcr.io/newlifeansh/kr-stock-analyst@sha256:d95504389c9b6134856cb6e1416c10cfc748112e5439d57e123a8b10a964d1a6`

Runtime topology artifacts contain only allowlisted operational settings and connection hostnames. Never export credentials or full environment dumps to a report.
