from __future__ import annotations

import asyncio
import html as html_lib
import json
import math
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Literal
from urllib.parse import urljoin, urlparse
from uuid import uuid4
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import httpx

from app.qa.catalog import load_qa_catalog

KST = ZoneInfo("Asia/Seoul")
QaMode = Literal["gate", "live", "e2e"]
QaStatus = Literal["pass", "warn", "fail", "skip"]
DEFAULT_STAGING_BASE_URLS = {
    "dashboard": "https://domestic-market-web-staging-staging.up.railway.app",
    "us": "https://us-market-web-staging.up.railway.app",
    "us-gateway": "https://domestic-market-web-staging-staging.up.railway.app",
}
SECRET_KEY_RE = re.compile(
    r"(authorization|token|secret|password|api[_-]?key|app[_-]?key|app[_-]?secret|approval[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?i)(bearer\s+)[^\s,;]+|((?:api|app|secret|token)[_-]?key=)[^&\s]+"
)
QUOTE_STREAM_META_RE = re.compile(
    r"""<meta\b
    (?=[^>]*\bname\s*=\s*["']secret-note-quote-stream-url["'])
    (?=[^>]*\bcontent\s*=\s*["']([^"']+)["'])
    [^>]*>""",
    re.IGNORECASE | re.VERBOSE,
)

# Gate evidence is intentionally traceable at the pytest testcase level. New
# cases must be added here with every deterministic test that is required to
# clear the corresponding QA case. Existing catalog entries keep the legacy
# suite-level evidence contract until they are migrated incrementally.
PYTEST_QA_CASE_TESTS: dict[str, tuple[str, ...]] = {
    "SIG-UI-025": (
        "tests.test_data_signal_qa."
        "test_live_intraday_transient_unavailable_recovers_with_bounded_retry",
        "tests.test_data_signal_qa."
        "test_live_intraday_persistent_unavailable_remains_p0",
        "tests.test_data_signal_qa."
        "test_live_intraday_malformed_empty_response_is_not_retried",
    ),
    "DATA-COM-005": (
        "tests.test_data_signal_qa."
        "test_domestic_live_skips_us_snapshot_when_collector_disabled",
        "tests.test_release_parity."
        "test_deployment_workflow_promotes_one_immutable_image_after_staging",
        "tests.test_release_parity."
        "test_staging_targets_and_qa_evidence_are_separate_for_both_products",
        "tests.test_release_parity."
        "test_scheduled_qa_never_reuses_the_preview_proxy",
    ),
    "DATA-COM-006": (
        "tests.test_us_public_gateway."
        "test_canonical_us_gateway_routes_shell_assets_api_and_isolates_cookies",
        "tests.test_us_public_gateway."
        "test_us_gateway_unavailable_or_wrong_market_shell_never_falls_back",
        "tests.test_us_public_gateway."
        "test_us_gateway_requires_distinct_https_origin_and_does_not_route_domestic",
        "tests.test_us_public_gateway."
        "test_us_cutover_freezes_only_us_writes",
        "tests.test_us_public_gateway."
        "test_public_us_bridge_rewrites_fetch_and_websocket_without_changing_us_staging",
        "tests.test_us_public_gateway."
        "test_public_us_bridge_routes_only_same_origin_fetches",
        "tests.test_release_parity."
        "test_us_canonical_route_activation_requires_exact_production_candidate",
        "tests.test_us_data_cutover."
        "test_us_cutover_copies_only_missing_us_namespaced_state_idempotently",
        "tests.test_us_data_cutover."
        "test_us_cutover_blocks_conflicts_and_private_subscription_state",
        "tests.test_data_signal_qa."
        "test_us_gateway_live_requires_dedicated_shell_assets_and_api",
        "tests.test_data_signal_qa."
        "test_us_gateway_e2e_normalizes_news_api_path_without_hiding_bypass",
    ),
    "DATA-COM-007": (
        "tests.test_us_public_gateway."
        "test_us_cutover_freezes_only_us_writes",
        "tests.test_us_data_cutover."
        "test_us_cutover_copies_only_missing_us_namespaced_state_idempotently",
        "tests.test_us_data_cutover."
        "test_us_cutover_blocks_conflicts_and_private_subscription_state",
        "tests.test_release_parity."
        "test_us_canonical_route_activation_requires_exact_production_candidate",
    ),
    "DATA-US-NEWS-001": (
        "tests.test_us_market."
        "test_us_market_trends_uses_real_recent_articles_and_rejects_synthetic_freshness",
        "tests.test_us_market."
        "test_us_market_trends_fails_closed_when_all_live_sources_fail",
        "tests.test_app."
        "test_us_market_trends_refresh_exposes_only_linked_live_articles",
        "tests.test_app."
        "test_us_and_dashboard_paths_serve_independently_versioned_products",
        "tests.test_staging_dark_theme."
        "test_staging_theme_has_touch_and_spacing_contract_for_tds_ia",
    ),
    "DATA-US-NEWS-TABS-001": (
        "tests.test_us_market."
        "test_us_news_filters_unrelated_naver_headlines_for_the_selected_stock",
        "tests.test_us_market."
        "test_naver_news_search_skips_full_unrelated_page_and_uses_next_query",
        "tests.test_us_market."
        "test_wmb_naver_news_rejects_short_ticker_collisions_stale_and_duplicates",
        "tests.test_us_market."
        "test_wmb_yahoo_news_accepts_trusted_related_ticker_for_short_symbol",
        "tests.test_us_market."
        "test_naver_world_news_uses_verified_yahoo_exchange_code_only",
        "tests.test_us_market."
        "test_parse_yahoo_news_payload_keeps_ticker_related_overseas_fields",
        "tests.test_app."
        "test_us_stock_news_has_separate_domestic_and_yahoo_overseas_tabs",
    ),
    "REC-US-INDEPENDENT-001": (
        "tests.test_us_market."
        "test_us_recommendations_rank_top100_independently_of_trade_signal_action",
        "tests.test_us_market."
        "test_us_recommendation_missing_valuation_reweights_only_observed_components",
        "tests.test_public_signal."
        "test_us_independent_recommendation_keeps_public_score_separate_from_signal",
        "tests.test_app."
        "test_us_market_recommendations_endpoint_exposes_independent_score_and_hides_signal_score",
        "tests.test_app."
        "test_us_and_dashboard_paths_serve_independently_versioned_products",
        "tests.test_staging_dark_theme."
        "test_staging_us_recommendation_detail_separates_public_score_and_signal_evidence",
    ),
    "SIG-CONTRACT-007": (
        "tests.test_web_push."
        "test_us_market_ai_signal_candidates_emit_ready_close_entry_pending",
        "tests.test_web_push."
        "test_us_market_ai_signal_candidates_fail_closed_outside_fresh_window",
        "tests.test_web_push."
        "test_us_market_ai_signal_candidates_require_canonical_ready_snapshot",
        "tests.test_web_push."
        "test_us_signal_notification_history_uses_new_york_event_date",
        "tests.test_web_push."
        "test_us_market_ai_signal_uses_independent_baseline",
        "tests.test_web_push."
        "test_run_once_dispatches_new_us_signal_after_independent_baseline",
        "tests.test_app."
        "test_market_signal_feed_includes_delivered_preliminary_history",
        "tests.test_app."
        "test_push_config_includes_briefing_and_domestic_market_signal_alerts",
    ),
    "SIG-UI-030": (
        "tests.test_domestic_market_scope."
        "test_domestic_market_is_the_default_product_boundary",
        "tests.test_domestic_market_scope."
        "test_domestic_home_never_requests_us_market_feeds",
        "tests.test_domestic_market_scope."
        "test_domestic_runtime_does_not_schedule_us_market_snapshots",
        "tests.test_web_push."
        "test_run_once_skips_us_signal_pipeline_for_domestic_product",
        "tests.test_app."
        "test_domestic_surface_disables_unified_runtime_and_preserves_dormant_us_implementation",
        "tests.test_app."
        "test_push_config_includes_briefing_and_domestic_market_signal_alerts",
    ),
    "SIG-UI-031": (
        "tests.test_domestic_market_scope."
        "test_us_spinout_shell_is_separate_from_the_domestic_product",
        "tests.test_app."
        "test_us_and_dashboard_paths_serve_independently_versioned_products",
        "tests.test_app."
        "test_legacy_nasdaq_routes_redirect_to_canonical_us_paths_with_query_preserved",
        "tests.test_app."
        "test_us_stock_path_serves_shell_without_shadowing_us_api_routes",
        "tests.test_app."
        "test_us_refresh_and_version_are_isolated_from_the_domestic_product_cache",
        "tests.test_app."
        "test_us_service_worker_owns_only_the_us_scope_and_caches_versioned_us_assets",
        "tests.test_app."
        "test_us_ai_signal_back_returns_home_without_relying_on_browser_history",
        "tests.test_market_index_live_endpoint."
        "test_us_entry_uses_the_us_only_shell_and_global_market_snapshot",
    ),
    "SIG-UI-022": (
        "tests.test_public_signal."
        "test_quant_projection_exposes_only_three_public_reasons_and_keeps_input_immutable",
        "tests.test_public_signal."
        "test_market_projection_redacts_live_and_preliminary_history_reasons",
        "tests.test_public_signal."
        "test_recommendation_projection_removes_component_and_nested_reason_details",
        "tests.test_public_signal."
        "test_us_candidate_projection_hides_shadow_diagnostics_and_numeric_evidence",
        "tests.test_public_signal."
        "test_us_recommendation_projection_hides_nested_internal_evidence",
        "tests.test_public_signal."
        "test_us_non_ready_market_and_recommendation_projections_are_no_signal",
        "tests.test_public_signal."
        "test_us_ready_snapshot_with_incomplete_public_reasons_fails_closed",
        "tests.test_app."
        "test_us_market_recommendations_endpoint_exposes_independent_score_and_hides_signal_score",
        "tests.test_home_ai_response."
        "test_us_public_ui_never_renders_private_scores_or_synthesized_trade_levels",
    ),
    "DATA-US-UNIVERSE-001": (
        "tests.test_us_signal_universe."
        "test_us_signal_universe_is_exact_top100_and_deduplicates_share_classes",
        "tests.test_us_signal_universe."
        "test_us_signal_universe_fails_closed_when_fewer_than_100_validate",
        "tests.test_us_signal_universe."
        "test_exactly_100_screen_issuers_cannot_claim_a_proven_top100_boundary",
        "tests.test_us_signal_universe."
        "test_us_signal_universe_security_name_filter_rejects_non_common_equity",
        "tests.test_us_signal_universe."
        "test_exchange_screen_paginates_table_rows_and_preserves_as_of",
        "tests.test_us_signal_universe."
        "test_exchange_screen_allows_detail_to_omit_proven_excluded_rank_instrument",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_incomplete_or_date_misaligned_pages[missing_total]",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_incomplete_or_date_misaligned_pages[changed_date]",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_incomplete_or_date_misaligned_pages[classification_set]",
        "tests.test_us_signal_universe."
        "test_top_cap_quote_failure_does_not_promote_issuer_101[missing]",
        "tests.test_us_signal_universe."
        "test_top_cap_quote_failure_does_not_promote_issuer_101[stale]",
        "tests.test_us_signal_universe."
        "test_top_cap_quote_failure_does_not_promote_issuer_101[non_usd]",
        "tests.test_us_signal_universe."
        "test_cross_exchange_duplicate_ticker_is_rejected",
        "tests.test_us_signal_universe."
        "test_nasdaq_screen_is_the_only_market_cap_ranking_source",
        "tests.test_us_signal_universe."
        "test_sec_cik_failure_at_top100_boundary_fails_closed[unavailable]",
        "tests.test_us_signal_universe."
        "test_sec_cik_failure_at_top100_boundary_fails_closed[boundary_missing]",
        "tests.test_us_signal_universe."
        "test_screener_as_of_must_match_quotes_and_completed_session[stale]",
        "tests.test_us_signal_universe."
        "test_screener_as_of_must_match_quotes_and_completed_session[mixed_exchange_dates]",
        "tests.test_us_signal_universe."
        "test_forming_regular_session_never_publishes_current_day_snapshot",
        "tests.test_us_signal_universe."
        "test_source_failure_uses_valid_stale_snapshot_and_blocks_entries",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[checksum]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[new_entries_allowed]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[source_candidate_count]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[validated_quote_count]",
        "tests.test_us_signal_universe."
        "test_snapshot_checksum_covers_sector_and_rank_caps_are_non_increasing",
        "tests.test_us_market."
        "test_sec_request_identity_contains_configured_contact",
        "tests.test_us_signal_universe."
        "test_commit_failure_rolls_back_before_valid_stale_fallback",
        "tests.test_us_signal_universe."
        "test_exact_completed_daily_snapshot_is_reused_without_remote_calls",
        "tests.test_us_signal_universe."
        "test_malformed_exact_daily_snapshot_is_never_overwritten",
        "tests.test_us_signal_universe."
        "test_completed_session_waits_for_provider_publication_grace",
        "tests.test_us_signal_universe."
        "test_source_digests_are_canonical_over_normalized_observations",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_invalid_classification_contract[date_mismatch]",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_invalid_classification_contract[invalid_date]",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_invalid_classification_contract[missing_field]",
        "tests.test_us_signal_universe."
        "test_exchange_screen_rejects_invalid_classification_contract[duplicate_ticker]",
        "tests.test_us_signal_universe."
        "test_exchange_screen_audits_unreported_date_and_blank_classification",
        "tests.test_us_signal_universe."
        "test_snapshot_records_deterministic_boundary_tie_and_source_evidence",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[audit_checksum]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[source_digest]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[audit_trust_model]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[classification_digest]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[classification_date]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[exchange_counts]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[boundary_rank_101]",
        "tests.test_us_signal_universe."
        "test_persisted_snapshot_validation_is_strict[tie_evidence]",
        "tests.test_us_signal_universe."
        "test_complete_daily_snapshot_rejects_audit_only_rewrite",
    ),
    "DATA-US-SIGNAL-INPUT-001": (
        "tests.test_us_market."
        "test_chart_price_rows_use_adjusted_ohlc_but_raw_dollar_notional",
        "tests.test_us_market."
        "test_signal_chart_rows_fail_closed_without_adjusted_complete_ohlcv",
        "tests.test_us_market."
        "test_signal_chart_rows_accept_bounded_yahoo_open_range_drift[416.010009765625-424.45001220703125-416.0199890136719-418.010009765625]",
        "tests.test_us_market."
        "test_signal_chart_rows_accept_bounded_yahoo_open_range_drift[119.62999725341797-121.2249984741211-119.75-120.93000030517578]",
        "tests.test_us_market."
        "test_signal_chart_rows_accept_bounded_yahoo_open_range_drift[107.08999633789062-109.41999816894531-107.20500183105469-108.58999633789062]",
        "tests.test_us_market."
        "test_signal_chart_rows_accept_bounded_yahoo_open_range_drift[254.27999877929688-258.45001220703125-254.64500427246094-257.489990234375]",
        "tests.test_us_market."
        "test_signal_daily_close_repairs_only_null_fields_from_completed_regular_intraday",
        "tests.test_us_market."
        "test_signal_daily_row_repairs_fully_null_completed_day_before_forming_row",
        "tests.test_us_market."
        "test_signal_daily_row_repair_rejects_intraday_session_gap",
        "tests.test_us_market."
        "test_signal_daily_close_repair_stays_closed_before_publication_grace",
        "tests.test_us_market."
        "test_signal_daily_close_repair_requires_intraday_through_official_close",
        "tests.test_us_market."
        "test_signal_daily_close_repair_rejects_mismatched_intraday_metadata[symbol-MSFT]",
        "tests.test_us_market."
        "test_signal_daily_close_repair_rejects_mismatched_intraday_metadata[currency-KRW]",
        "tests.test_us_market."
        "test_signal_daily_close_repair_rejects_partial_close_pair",
        "tests.test_us_market."
        "test_signal_chart_range_invokes_completed_daily_close_repair",
        "tests.test_us_market."
        "test_signal_chart_range_rejects_non_usd_or_mismatched_instrument[meta0-AAPL]",
        "tests.test_us_market."
        "test_signal_chart_range_rejects_non_usd_or_mismatched_instrument[meta1-AAPL]",
        "tests.test_us_market."
        "test_signal_chart_range_rejects_non_usd_or_mismatched_instrument[meta2-AAPL]",
        "tests.test_us_market."
        "test_sector_snapshot_pairs_last_valid_close_with_its_new_york_date",
        "tests.test_us_market."
        "test_signal_chart_rows_reject_invalid_adjusted_ohlc_geometry[100.0-99.0-90.0-100.0-50.0]",
        "tests.test_us_market."
        "test_signal_chart_rows_reject_invalid_adjusted_ohlc_geometry[100.0-110.0-101.0-100.0-50.0]",
        "tests.test_us_market."
        "test_signal_chart_rows_reject_invalid_adjusted_ohlc_geometry[0.0-110.0-90.0-100.0-50.0]",
        "tests.test_us_market."
        "test_signal_chart_rows_reject_invalid_adjusted_ohlc_geometry[100.0-110.0-90.0-100.0-0.0]",
        "tests.test_us_position_lifecycle."
        "test_us_price_bars_drop_forming_and_explicitly_unadjusted_rows",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_publication_history_loader_bypasses_any_preclose_chart_cache",
        "tests.test_us_market_calendar."
        "test_us_calendar_rejects_holiday_and_weekend",
        "tests.test_us_market_calendar."
        "test_us_market_display_session_stays_closed_on_xnys_holiday",
        "tests.test_us_market_calendar."
        "test_latest_completed_session_changes_at_early_close",
        "tests.test_us_market_calendar."
        "test_us_market_display_session_switches_to_afterhours_at_early_close",
        "tests.test_us_market_calendar."
        "test_signal_publication_waits_for_post_close_provider_grace",
        "tests.test_us_position_lifecycle_runtime."
        "test_canonical_snapshot_waits_for_provider_grace_after_official_close",
        "tests.test_app."
        "test_us_market_regular_session_request_never_enqueues_publication",
        "tests.test_home_ai_response."
        "test_dashboard_us_market_session_payload_overrides_fixed_clock_phase",
        "tests.test_home_ai_response."
        "test_nasdaq_us_market_session_sources_override_clock_and_drive_live_labels",
        "tests.test_home_ai_response."
        "test_dashboard_us_intraday_cache_policy_uses_safe_server_session_source",
    ),
    "DATA-US-EVIDENCE-001": (
        "tests.test_us_position_lifecycle."
        "test_us_entry_requires_market_relative_strength_and_dollar_volume_evidence",
        "tests.test_us_position_lifecycle."
        "test_us_entry_is_not_pending_when_evidence_dates_are_misaligned",
        "tests.test_us_position_lifecycle."
        "test_us_entry_fails_closed_when_a_recent_session_is_missing_mid_series",
        "tests.test_us_position_lifecycle."
        "test_common_non_session_date_cannot_pass_alignment",
        "tests.test_us_market_calendar."
        "test_recent_session_vector_uses_only_consecutive_official_xnys_sessions",
        "tests.test_us_position_lifecycle."
        "test_us_entry_requires_stock_strength_relative_to_its_sector",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_sector_etf_mapping_uses_only_reviewed_cik_taxonomy",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_sector_etf_taxonomy_is_versioned_complete_data_and_unknown_fails_closed",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_one_missing_member_history_blocks_every_new_entry",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_one_unreviewed_issuer_sector_blocks_every_new_entry",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_one_mid_series_session_gap_blocks_every_new_entry",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_contiguous_short_listing_history_blocks_only_that_member",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_gapped_short_history_still_blocks_all_new_entries",
        "tests.test_us_market."
        "test_us_liquidity_proxy_uses_explicit_dollar_volume_names",
        "tests.test_public_signal."
        "test_us_candidate_projection_hides_shadow_diagnostics_and_numeric_evidence",
        "tests.test_public_signal."
        "test_us_recommendation_projection_hides_nested_internal_evidence",
        "tests.test_public_signal."
        "test_us_ai_analysis_projection_labels_dollar_volume_proxy_without_investor_flow",
    ),
    "SIG-US-VERSION-001": (
        "tests.test_us_position_lifecycle."
        "test_us_feed_replays_top100_model_lifecycle_without_orders",
        "tests.test_us_position_lifecycle_runtime."
        "test_canonical_snapshot_keeps_model_holdings_when_raw_candidates_are_pending",
        "tests.test_us_market."
        "test_us_recommendations_use_the_same_rc1_snapshot_as_the_signal_feed",
        "tests.test_us_position_lifecycle_runtime."
        "test_canonical_snapshot_round_trip_and_stale_state_blocks_entries",
    ),
    "SIG-US-LIFECYCLE-001": (
        "tests.test_quant_signals."
        "test_shared_lifecycle_indicator_core_matches_v742_domestic_golden_vector",
        "tests.test_us_position_lifecycle."
        "test_us_entry_requires_market_relative_strength_and_dollar_volume_evidence",
        "tests.test_us_position_lifecycle."
        "test_us_model_replay_confirms_only_the_next_open_inside_gap",
        "tests.test_quant_signals."
        "test_v742_reentry_has_no_fixed_delay_but_requires_new_breakout_or_ema20_retest",
        "tests.test_us_position_lifecycle_runtime."
        "test_incomplete_refresh_never_overwrites_last_good",
        "tests.test_us_position_lifecycle_runtime."
        "test_older_worker_cannot_overwrite_newer_canonical_snapshot",
        "tests.test_us_position_lifecycle."
        "test_us_entry_fails_closed_when_a_recent_session_is_missing_mid_series",
    ),
    "SIG-US-CHASE-001": (
        "tests.test_us_position_lifecycle."
        "test_us_chase_guard_blocks_high_score_entry_independently",
        "tests.test_us_position_lifecycle."
        "test_us_chase_guard_boundaries_and_three_bar_lookback_are_exact",
        "tests.test_us_position_lifecycle."
        "test_us_next_open_gap_guard_uses_atr_and_percent_cap",
    ),
    "SIG-US-REENTRY-001": (
        "tests.test_us_position_lifecycle."
        "test_us_reentry_has_no_fixed_wait_but_requires_new_price_event",
        "tests.test_us_position_lifecycle."
        "test_us_reentry_allows_ema20_retest_recovery_without_fixed_wait",
        "tests.test_us_position_lifecycle."
        "test_us_model_reentry_keeps_prior_exit_out_of_current_position",
        "tests.test_us_position_lifecycle."
        "test_us_feed_replays_top100_model_lifecycle_without_orders",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[stateful_lifecycle_replay_enabled-False]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[reentry_runtime_enabled-False]",
    ),
    "SIG-US-SHADOW-001": (
        "tests.test_us_position_lifecycle."
        "test_legacy_us_momentum_baseline_reproduces_rounded_entry_boundary",
        "tests.test_us_position_lifecycle."
        "test_legacy_us_momentum_baseline_uses_point_in_time_quote_valuation",
        "tests.test_us_position_lifecycle."
        "test_legacy_us_momentum_baseline_preserves_rounding_and_quote_volume_semantics",
        "tests.test_us_position_lifecycle."
        "test_us_feed_replays_top100_model_lifecycle_without_orders",
        "tests.test_us_market."
        "test_us_recommendations_use_the_same_rc1_snapshot_as_the_signal_feed",
        "tests.test_us_position_lifecycle_runtime."
        "test_failed_refresh_keeps_last_good_snapshot_and_blocks_returned_entries",
    ),
    "SIG-US-CONTRACT-001": (
        "tests.test_data_signal_qa."
        "test_us_live_accepts_confirmed_model_holdings_and_exits",
        "tests.test_data_signal_qa."
        "test_us_live_rejects_inconsistent_model_exposure",
        "tests.test_us_position_lifecycle."
        "test_us_feed_replays_top100_model_lifecycle_without_orders",
        "tests.test_us_position_lifecycle."
        "test_us_model_reentry_keeps_prior_exit_out_of_current_position",
        "tests.test_us_market_calendar."
        "test_us_calendar_memoizes_official_session_and_replay_vectors",
        "tests.test_us_position_lifecycle_runtime."
        "test_canonical_snapshot_keeps_model_holdings_when_raw_candidates_are_pending",
        "tests.test_us_position_lifecycle_runtime."
        "test_canonical_snapshot_separates_lifecycle_no_signal_from_rejections",
        "tests.test_us_position_lifecycle_runtime."
        "test_open_model_reentry_does_not_project_historical_exit_as_current_exit",
        "tests.test_data_signal_qa."
        "test_live_us_contract_accepts_confirmed_model_lifecycle_items",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_sector_etf_mapping_uses_only_reviewed_cik_taxonomy",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_sector_etf_taxonomy_is_versioned_complete_data_and_unknown_fails_closed",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_one_missing_member_history_blocks_every_new_entry",
        "tests.test_us_position_lifecycle_fail_closed."
        "test_one_unreviewed_issuer_sector_blocks_every_new_entry",
        "tests.test_us_position_lifecycle_runtime."
        "test_future_dated_snapshot_is_blocked_and_refresh_is_due",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[top_level_coverage-99]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[nested_coverage-99]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[status-degraded]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[execution_enabled-True]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[entry_pending_count-999]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[preliminary_count-999]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[policy-False]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[coverage_percent-99.0]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[sector_classification_error_count-1]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[coverage_sector_classification_error_count-1]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[stateful_lifecycle_replay_enabled-False]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[reentry_runtime_enabled-False]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_currency-KRW]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_rank-101]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_position-true]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_exposure-100]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_status-confirmed]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_action-holding]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_events-nonempty]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[temporal_metadata-future]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_sector_etf-cik-mismatch]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_public_reasons-missing]",
        "tests.test_us_position_lifecycle_runtime."
        "test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum[item_public_reason_available-false]",
        "tests.test_us_position_lifecycle_runtime."
        "test_snapshot_identity_must_match_strategy_date_and_checksum",
        "tests.test_us_signal_universe."
        "test_snapshot_checksum_covers_sector_and_rank_caps_are_non_increasing",
        "tests.test_us_market."
        "test_us_recommendations_use_the_same_rc1_snapshot_as_the_signal_feed",
        "tests.test_us_market."
        "test_us_quant_signals_expose_only_usd_preliminary_candidates",
        "tests.test_public_signal."
        "test_us_candidate_projection_hides_shadow_diagnostics_and_numeric_evidence",
        "tests.test_public_signal."
        "test_us_recommendation_projection_hides_nested_internal_evidence",
        "tests.test_public_signal."
        "test_us_non_ready_market_and_recommendation_projections_are_no_signal",
        "tests.test_public_signal."
        "test_us_ready_snapshot_with_incomplete_public_reasons_fails_closed",
        "tests.test_app."
        "test_us_market_recommendations_endpoint_exposes_independent_score_and_hides_signal_score",
        "tests.test_app."
        "test_us_market_cold_request_is_read_only_and_collector_owned",
        "tests.test_app."
        "test_us_market_refresh_query_remains_read_only",
        "tests.test_app."
        "test_us_market_regular_session_request_never_enqueues_publication",
        "tests.test_app."
        "test_us_collector_backfills_legacy_member_evidence_during_regular_session",
        "tests.test_us_position_lifecycle."
        "test_us_history_loader_retries_only_transient_failures_with_lower_concurrency",
        "tests.test_us_position_lifecycle."
        "test_us_feed_retries_a_symbol_missing_the_completed_session",
        "tests.test_us_position_lifecycle_runtime."
        "test_legacy_snapshot_requires_one_time_public_member_evidence_upgrade",
        "tests.test_app."
        "test_us_market_refresh_queue_is_process_single_flight",
        "tests.test_app."
        "test_us_stock_ai_analysis_endpoint_labels_dollar_volume_proxy",
        "tests.test_app."
        "test_us_stock_ai_analysis_fails_closed_without_canonical_candidate[preparing]",
        "tests.test_app."
        "test_us_stock_ai_analysis_fails_closed_without_canonical_candidate[outside_top100]",
        "tests.test_app."
        "test_us_stock_ai_analysis_keeps_top100_member_ready_without_signal[share_class_alias]",
        "tests.test_app."
        "test_us_stock_ai_analysis_keeps_top100_member_ready_without_signal[exact_symbol]",
        "tests.test_home_ai_response."
        "test_us_ai_signal_composition_preserves_identity_and_fails_closed",
        "tests.test_home_ai_response."
        "test_us_ai_analysis_display_preserves_canonical_fields_and_fails_closed",
        "tests.test_home_ai_response."
        "test_us_stock_signal_evidence_preserves_proxy_labels_and_completed_date",
        "tests.test_home_ai_response."
        "test_us_stock_signal_outside_top100_is_not_mislabelled_as_missing_data",
        "tests.test_home_ai_response."
        "test_us_recommendation_detail_requires_matching_ready_snapshot_identity",
        "tests.test_home_ai_response."
        "test_nasdaq_ai_renderer_and_recommendation_history_keep_canonical_snapshot",
        "tests.test_home_ai_response."
        "test_us_public_ui_never_renders_private_scores_or_synthesized_trade_levels",
    ),
    "SIG-US-MIGRATION-001": (
        "tests.test_app."
        "test_us_market_regular_session_request_never_enqueues_publication",
        "tests.test_app."
        "test_us_market_cold_request_is_read_only_and_collector_owned",
        "tests.test_app."
        "test_us_collector_backfills_legacy_member_evidence_during_regular_session",
        "tests.test_us_position_lifecycle_runtime."
        "test_legacy_snapshot_requires_one_time_public_member_evidence_upgrade",
        "tests.test_us_position_lifecycle."
        "test_us_history_loader_retries_only_transient_failures_with_lower_concurrency",
        "tests.test_us_position_lifecycle."
        "test_us_feed_retries_a_symbol_missing_the_completed_session",
        "tests.test_us_position_lifecycle."
        "test_us_member_public_evidence_recovers_three_completed_session_reasons",
        "tests.test_us_position_lifecycle."
        "test_us_member_public_evidence_rejects_a_completed_session_gap",
        "tests.test_app."
        "test_us_stock_ai_analysis_repairs_legacy_member_evidence_without_full_scan",
    ),
}


@dataclass
class QaCheckResult:
    id: str
    priority: str
    status: QaStatus
    duration_ms: int
    evidence: dict[str, Any]
    message: str


class QaFailure(AssertionError):
    def __init__(self, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


class QaWarning(RuntimeError):
    def __init__(self, message: str, evidence: dict[str, Any] | None = None):
        super().__init__(message)
        self.evidence = evidence or {}


def redact(value: Any) -> Any:
    """Return a JSON-safe value with credentials and prepared URLs removed."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY_RE.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [redact(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return SECRET_VALUE_RE.sub(
            lambda match: f"{match.group(1) or match.group(2)}[REDACTED]", value
        )
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _forbidden_key_paths(
    value: Any,
    forbidden: set[str],
    *,
    path: str = "$",
) -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if str(key) in forbidden:
                paths.append(child_path)
            paths.extend(_forbidden_key_paths(item, forbidden, path=child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(
                _forbidden_key_paths(item, forbidden, path=f"{path}[{index}]")
            )
    return paths


class ResultCollector:
    def __init__(self, catalog: dict[str, Any]):
        self._cases = {case["id"]: case for case in catalog["cases"]}
        self.results: list[QaCheckResult] = []

    def add(
        self,
        case_id: str,
        status: QaStatus,
        message: str,
        *,
        evidence: dict[str, Any] | None = None,
        duration_ms: int = 0,
    ) -> None:
        case = self._cases.get(case_id)
        if case is None:
            raise KeyError(f"Unknown QA case: {case_id}")
        candidate = QaCheckResult(
            id=case_id,
            priority=case["priority"],
            status=status,
            duration_ms=max(0, int(duration_ms)),
            evidence=redact(evidence or {}),
            message=str(redact(message)),
        )
        existing = next((item for item in self.results if item.id == case_id), None)
        if existing is None:
            self.results.append(candidate)
            return
        severity = {"pass": 0, "skip": 1, "warn": 2, "fail": 3}
        existing.status = max(
            (existing.status, candidate.status), key=severity.__getitem__
        )
        existing.duration_ms += candidate.duration_ms
        existing.evidence = {
            "probes": [
                *(existing.evidence.get("probes") or [existing.evidence]),
                candidate.evidence,
            ]
        }
        if candidate.message not in existing.message:
            existing.message = f"{existing.message} / {candidate.message}"

    def check(
        self,
        case_id: str,
        callback: Callable[[], dict[str, Any] | None],
        *,
        pass_message: str,
    ) -> None:
        started = monotonic()
        try:
            evidence = callback() or {}
        except QaWarning as exc:
            self.add(
                case_id,
                "warn",
                str(exc),
                evidence=exc.evidence,
                duration_ms=round((monotonic() - started) * 1000),
            )
        except (QaFailure, AssertionError) as exc:
            self.add(
                case_id,
                "fail",
                str(exc),
                evidence=getattr(exc, "evidence", {}),
                duration_ms=round((monotonic() - started) * 1000),
            )
        except Exception as exc:  # noqa: BLE001 - QA must convert every exception into evidence.
            self.add(
                case_id,
                "fail",
                f"{type(exc).__name__}: {exc}",
                duration_ms=round((monotonic() - started) * 1000),
            )
        else:
            self.add(
                case_id,
                "pass",
                pass_message,
                evidence=evidence,
                duration_ms=round((monotonic() - started) * 1000),
            )


def _assert(condition: Any, message: str, **evidence: Any) -> None:
    if not condition:
        raise QaFailure(message, evidence)


def _environment_name(base_url: str) -> str:
    host = (urlparse(base_url).hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "testserver"}:
        return "local"
    if "staging" in host:
        return "staging"
    return "remote"


def _same_origin_quote_stream_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{parsed.netloc}/ws/quotes"


def _resolve_public_quote_stream_url(
    base_url: str, timeout: float
) -> tuple[str, str]:
    """Resolve the exact quote stream a dashboard browser will connect to."""
    fallback_url = _same_origin_quote_stream_url(base_url)
    dashboard_url = urljoin(f"{base_url.rstrip('/')}/", "dashboard/005930")
    try:
        response = httpx.get(
            dashboard_url,
            follow_redirects=True,
            timeout=timeout,
            headers={"Accept": "text/html"},
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return fallback_url, "same_origin"

    match = QUOTE_STREAM_META_RE.search(response.text)
    if match is None:
        return fallback_url, "same_origin"
    candidate = html_lib.unescape(match.group(1)).strip()
    parsed = urlparse(candidate)
    if parsed.scheme not in {"ws", "wss"} or not parsed.netloc:
        return fallback_url, "same_origin"
    return candidate, "dashboard_meta"


def _market_state(*payloads: Any) -> str | None:
    keys = (
        "market_state",
        "market_status",
        "market_session",
        "market_session_label",
        "session",
        "status_label",
    )
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for child_key in ("quote", "current", "market", "session"):
            child = payload.get(child_key)
            if isinstance(child, dict):
                found = _market_state(child)
                if found:
                    return found
    return None


def _stream_timestamp(value: Any, field: str) -> datetime:
    raw = str(value or "").strip()
    _assert(bool(raw), f"WebSocket {field} 시각이 없습니다.", field=field)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise QaFailure(
            f"WebSocket {field} 시각을 해석할 수 없습니다.",
            {"field": field, "value": raw},
        ) from None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _validate_signal_revision_frame(
    frame: dict[str, Any], *, require_initial: bool | None = None
) -> dict[str, Any]:
    _assert(frame.get("type") == "signal_revision", "signal_revision 프레임이 아닙니다.")
    revision = frame.get("revision")
    _assert(
        isinstance(revision, int) and not isinstance(revision, bool) and revision >= 0,
        "signal_revision revision이 음이 아닌 정수가 아닙니다.",
        revision=revision,
    )
    changed_codes = frame.get("changed_codes")
    _assert(
        isinstance(changed_codes, list)
        and all(re.fullmatch(r"\d{6}", str(code or "")) for code in changed_codes),
        "signal_revision changed_codes가 6자리 종목코드 배열이 아닙니다.",
        changed_codes=changed_codes,
    )
    if require_initial is not None:
        _assert(
            frame.get("initial") is require_initial,
            "signal_revision initial 표시가 연결 상태와 다릅니다.",
            initial=frame.get("initial"),
            expected=require_initial,
        )
    as_of = _stream_timestamp(frame.get("as_of"), "signal_revision.as_of")
    return {
        "revision": revision,
        "as_of": as_of.isoformat(),
        "changed_codes": [str(code) for code in changed_codes],
        "initial": frame.get("initial") is True,
    }


def _validate_public_quote_frame(
    frame: dict[str, Any], *, expected_code: str
) -> dict[str, Any]:
    _assert(frame.get("type") == "quote", "quote 프레임이 아닙니다.")
    _assert(
        str(frame.get("code") or "") == expected_code,
        "quote 종목코드가 구독 종목과 다릅니다.",
        expected_code=expected_code,
        code=frame.get("code"),
    )
    quote = frame.get("quote")
    _assert(isinstance(quote, dict), "quote 본문이 객체가 아닙니다.")
    price = quote.get("price")
    _assert(
        isinstance(price, (int, float))
        and not isinstance(price, bool)
        and float(price) > 0,
        "quote 현재가가 양수가 아닙니다.",
        price=price,
    )
    sequence = frame.get("sequence")
    _assert(
        isinstance(sequence, int)
        and not isinstance(sequence, bool)
        and sequence >= 1,
        "quote sequence가 양의 정수가 아닙니다.",
        sequence=sequence,
    )
    observed_at = _stream_timestamp(frame.get("observed_at"), "quote.observed_at")
    published_at = _stream_timestamp(frame.get("published_at"), "quote.published_at")
    _assert(
        observed_at <= published_at,
        "quote published_at이 observed_at보다 빠릅니다.",
        observed_at=observed_at,
        published_at=published_at,
    )
    return {
        "code": expected_code,
        "price": price,
        "sequence": sequence,
        "observed_at": observed_at.isoformat(),
        "published_at": published_at.isoformat(),
        "source": frame.get("source"),
    }


def _validate_quote_status_frame(frame: dict[str, Any]) -> dict[str, Any]:
    _assert(frame.get("type") == "status", "status 프레임이 아닙니다.")
    _assert(
        re.fullmatch(r"\d{6}", str(frame.get("code") or "")) is not None,
        "status 종목코드가 없거나 잘못됐습니다.",
        code=frame.get("code"),
    )
    status = str(frame.get("status") or "").strip().lower()
    _assert(
        status in {"connected", "fallback", "recovered"},
        "status 상태가 connected·fallback·recovered 계약과 다릅니다.",
        status=status,
    )
    _assert(bool(str(frame.get("source") or "").strip()), "status 출처가 비었습니다.")
    message = str(frame.get("message") or "").strip()
    _assert(
        "appkey" not in message.lower()
        and re.search(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            message,
            re.IGNORECASE,
        )
        is None,
        "status 메시지에 KIS 인증정보 또는 원문 appkey 오류가 노출됐습니다.",
        status_message=message,
    )
    return {
        "code": str(frame.get("code")),
        "status": status,
        "source": str(frame.get("source")),
        "has_message": bool(message),
    }


class ReadOnlyApi:
    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/") + "/"
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            headers={
                "Accept": "application/json",
                "User-Agent": "analyst-data-signal-qa/1.0",
            },
        )

    def close(self) -> None:
        self.client.close()

    def get(self, path: str, **params: Any) -> tuple[Any, dict[str, Any]]:
        started = monotonic()
        response = self.client.get(
            urljoin(self.base_url, path.lstrip("/")), params=params or None
        )
        latency_ms = round((monotonic() - started) * 1000)
        meta = {
            "path": path,
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
            "us_market_route": response.headers.get("x-us-market-route"),
        }
        if response.status_code >= 400:
            raise QaFailure(f"GET {path} returned HTTP {response.status_code}", meta)
        try:
            payload = response.json()
        except ValueError as exc:
            raise QaFailure(f"GET {path} did not return JSON", meta) from exc
        return payload, meta

    def get_text(self, path: str, **params: Any) -> tuple[str, dict[str, Any]]:
        started = monotonic()
        response = self.client.get(
            urljoin(self.base_url, path.lstrip("/")), params=params or None
        )
        meta = {
            "path": path,
            "http_status": response.status_code,
            "latency_ms": round((monotonic() - started) * 1000),
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
            "us_market_route": response.headers.get("x-us-market-route"),
        }
        if response.status_code >= 400:
            raise QaFailure(f"GET {path} returned HTTP {response.status_code}", meta)
        return response.text, meta

    def post_json(
        self, path: str, payload: dict[str, Any]
    ) -> tuple[int, Any, dict[str, Any]]:
        started = monotonic()
        response = self.client.post(
            urljoin(self.base_url, path.lstrip("/")), json=payload
        )
        meta = {
            "path": path,
            "http_status": response.status_code,
            "latency_ms": round((monotonic() - started) * 1000),
            "content_type": response.headers.get("content-type"),
            "cache_control": response.headers.get("cache-control"),
        }
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = None
        return response.status_code, response_payload, meta


def _pytest_evidence(pytest_junit: Path | str | None) -> dict[str, Any] | None:
    if pytest_junit is None:
        return None
    path = Path(pytest_junit)
    if not path.is_file():
        raise QaFailure("pytest JUnit 증거 파일이 없습니다.", {"pytest_junit": path})
    root = ElementTree.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {
        key: sum(int(float(suite.attrib.get(key, "0"))) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    totals["path"] = str(path)
    testcase_statuses: dict[str, str] = {}
    severity = {"pass": 0, "skip": 1, "failure": 2, "error": 3}
    for testcase in root.iter():
        if str(testcase.tag).rsplit("}", 1)[-1] != "testcase":
            continue
        classname = str(testcase.attrib.get("classname") or "").strip()
        name = str(testcase.attrib.get("name") or "").strip()
        if not classname or not name:
            continue
        status = "pass"
        for child in testcase:
            child_tag = str(child.tag).rsplit("}", 1)[-1]
            if child_tag in {"failure", "error", "skipped"}:
                candidate = "skip" if child_tag == "skipped" else child_tag
                if severity[candidate] > severity[status]:
                    status = candidate
        testcase_id = f"{classname}.{name}"
        previous = testcase_statuses.get(testcase_id)
        if previous is None or severity[status] > severity[previous]:
            testcase_statuses[testcase_id] = status
    totals["recorded_testcases"] = len(testcase_statuses)
    totals["_testcase_statuses"] = testcase_statuses
    return totals


def _pytest_summary(pytest_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if pytest_result is None:
        return None
    return {
        key: value
        for key, value in pytest_result.items()
        if not str(key).startswith("_")
    }


def _mapped_pytest_evidence(
    case_id: str,
    pytest_result: dict[str, Any] | None,
) -> tuple[QaStatus, str, dict[str, Any]]:
    expected = list(PYTEST_QA_CASE_TESTS[case_id])
    evidence: dict[str, Any] = {
        "delegated_to": "pytest",
        "required_testcases": expected,
        "pytest": _pytest_summary(pytest_result),
    }
    if pytest_result is None:
        return (
            "skip",
            "pytest JUnit 증거가 없어 필수 테스트를 확인하지 못했습니다.",
            evidence,
        )
    if pytest_result.get("error"):
        return "fail", "pytest JUnit 증거를 읽지 못했습니다.", evidence

    statuses = pytest_result.get("_testcase_statuses") or {}
    observed = {test_id: statuses.get(test_id) for test_id in expected}
    missing = [test_id for test_id, status in observed.items() if status is None]
    not_passed = {
        test_id: status
        for test_id, status in observed.items()
        if status is not None and status != "pass"
    }
    evidence["observed_testcases"] = observed
    if missing or not_passed:
        evidence["missing_testcases"] = missing
        evidence["not_passed_testcases"] = not_passed
        return (
            "fail",
            "QA 항목에 필요한 pytest 테스트 증적이 누락되었거나 통과하지 않았습니다.",
            evidence,
        )
    return (
        "pass",
        "QA 항목에 연결된 pytest 테스트가 모두 통과했습니다.",
        evidence,
    )


def _gate_checks(
    collector: ResultCollector,
    catalog: dict[str, Any],
    *,
    pytest_junit: Path | str | None,
) -> None:
    from app.services import quant_signals as qs
    from app.services.us_position_lifecycle import (
        US_BASELINE_STRATEGY_VERSION,
        US_CHASE_POLICY,
        US_LIFECYCLE_REPLAY_VERSION,
        US_ROLLOUT_MODE,
        US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
        US_REENTRY_RUNTIME_ENABLED,
        US_STRATEGY_VERSION,
    )
    from app.services.us_signal_universe import (
        US_SIGNAL_UNIVERSE_LIMIT,
        US_SIGNAL_UNIVERSE_VERSION,
    )

    def catalog_contract() -> dict[str, Any]:
        ids = [case["id"] for case in catalog["cases"]]
        _assert(len(ids) >= 50, "QA 카탈로그 항목이 예상보다 적습니다.", count=len(ids))
        _assert(len(ids) == len(set(ids)), "QA ID가 중복되었습니다.")
        return {"catalog_version": catalog["catalog_version"], "case_count": len(ids)}

    collector.check(
        "DATA-COM-003",
        catalog_contract,
        pass_message="단일 QA 카탈로그의 필수 필드와 고유 ID를 확인했습니다.",
    )

    def redaction_contract() -> dict[str, Any]:
        sample = redact(
            {
                "authorization": "Bearer super-secret",
                "nested": {"api_key": "abc", "url": "https://x.test/?token_key=abc"},
            }
        )
        encoded = json.dumps(sample, ensure_ascii=False)
        _assert(
            "super-secret" not in encoded and "abc" not in encoded,
            "비밀값 마스킹에 실패했습니다.",
        )
        return sample

    collector.check(
        "DATA-COM-001",
        redaction_contract,
        pass_message="보고서의 인증정보 마스킹 계약을 확인했습니다.",
    )

    def strategy_contract() -> dict[str, Any]:
        _assert(
            qs.STRATEGY_VERSION == catalog["strategy_version"],
            "전략 버전이 QA 카탈로그와 다릅니다.",
        )
        return {"strategy_version": qs.STRATEGY_VERSION}

    collector.check(
        "SIG-VERSION-002",
        strategy_contract,
        pass_message="전략 버전과 QA 카탈로그 버전이 일치합니다.",
    )

    def us_strategy_contract() -> dict[str, Any]:
        _assert(
            US_STRATEGY_VERSION == catalog.get("us_strategy_version"),
            "미국 후보 전략 버전이 QA 카탈로그와 다릅니다.",
        )
        _assert(
            US_SIGNAL_UNIVERSE_LIMIT == 100
            and US_SIGNAL_UNIVERSE_VERSION == "us-market-cap-top100-v3",
            "미국 시그널 유니버스 정책이 Top 100 v3와 다릅니다.",
        )
        _assert(
            US_ROLLOUT_MODE == "model_replay"
            and US_LIFECYCLE_REPLAY_VERSION == "us-next-open-model-replay-v1"
            and US_STATEFUL_LIFECYCLE_REPLAY_ENABLED is True
            and US_REENTRY_RUNTIME_ENABLED is True
            and US_BASELINE_STRATEGY_VERSION == "us-momentum-watch-v1",
            "미국 v2 모델 replay 비교 계약이 다릅니다.",
        )
        _assert(
            US_CHASE_POLICY.max_extension_atr == 1.5
            and US_CHASE_POLICY.max_extension_percent == 0.07
            and US_CHASE_POLICY.momentum5_max == 0.10,
            "미국 추격매수 차단 정책이 고정값과 다릅니다.",
        )
        return {
            "strategy_version": US_STRATEGY_VERSION,
            "baseline_strategy_version": US_BASELINE_STRATEGY_VERSION,
            "rollout_mode": US_ROLLOUT_MODE,
            "universe_version": US_SIGNAL_UNIVERSE_VERSION,
            "universe_limit": US_SIGNAL_UNIVERSE_LIMIT,
        }

    collector.check(
        "SIG-US-VERSION-001",
        us_strategy_contract,
        pass_message="미국 v2·baseline·Top 100 모델 replay 버전 계약을 확인했습니다.",
    )

    def input_contract() -> dict[str, Any]:
        _assert(qs.MIN_HISTORY_ROWS == 125, "최소 완전 일봉 계약이 변경되었습니다.")
        return {"minimum_complete_daily_bars": qs.MIN_HISTORY_ROWS}

    collector.check(
        "SIG-INPUT-001",
        input_contract,
        pass_message="최소 125개 완전 일봉 입력 계약을 확인했습니다.",
    )

    bar = qs.PriceBar(date(2026, 9, 4), 100, 103, 99, 102, 2_000_000, 10_000_000_000)
    common = {
        "atr_percent": 0.04,
        "ema20_extension_atr": 2.0,
        "average_trading_value": 6_000_000_000.0,
        "ema10": 101.0,
        "ema20": 100.0,
        "ema60": 99.0,
        "ema10_slope": 0.01,
        "ema20_slope": 0.01,
        "momentum5": 0.03,
        "momentum20": 0.02,
        "volume_ratio": 1.2,
        "high_distance": -0.02,
    }

    def entry_boundaries() -> dict[str, Any]:
        # Keep this fixture above the separate early-turn participation gate,
        # so it isolates the v7.4 established-trend score boundary.
        below = {**common, "score": qs.ENTRY_SCORE - 0.01, "volume_ratio": 1.0}
        exact = {**common, "score": qs.ENTRY_SCORE, "volume_ratio": 1.0}
        _assert(
            qs._entry_setup_kind(bar, below) is None,
            "64점 직전 기존 추세가 진입했습니다.",
        )
        _assert(
            qs._entry_setup_kind(bar, exact) == "trend_continuation",
            "64점 동일값 진입이 거절됐습니다.",
        )
        return {"threshold": qs.ENTRY_SCORE, "below": qs.ENTRY_SCORE - 0.01}

    collector.check(
        "SIG-ENTRY-001",
        entry_boundaries,
        pass_message="v7.4 기존 추세 64점 경계값을 확인했습니다.",
    )

    def early_boundaries() -> dict[str, Any]:
        early_bar = qs.PriceBar(
            date(2026, 9, 4), 99, 103, 98, 101.5, 2_000_000, 10_000_000_000
        )
        early = {
            **common,
            "score": qs.EARLY_ENTRY_SCORE,
            "ema10": 101.0,
            "ema20": 100.0,
            "ema60": 100.4,
            "ema20_slope": -0.001,
            "momentum20": 0.0,
        }
        _assert(
            qs._entry_setup_kind(early_bar, early) == "early_turn",
            "64점 조기 전환이 거절됐습니다.",
        )
        _assert(
            qs._entry_setup_kind(
                early_bar, {**early, "score": qs.EARLY_ENTRY_SCORE - 0.01}
            )
            is None,
            "64점 직전 조기 전환이 진입했습니다.",
        )
        return {"threshold": qs.EARLY_ENTRY_SCORE}

    collector.check(
        "SIG-ENTRY-002",
        early_boundaries,
        pass_message="v7.4 조기 전환 64점 경계값을 확인했습니다.",
    )

    def quality_guards() -> dict[str, Any]:
        _assert(
            qs._entry_quality_allowed(bar, {**common, "score": 70}),
            "정상 공통 품질 조건이 거절됐습니다.",
        )
        for field, value in (
            ("atr_percent", qs.MAX_ENTRY_ATR_PERCENT + 0.0001),
            ("ema20_extension_atr", qs.MAX_ENTRY_EXTENSION_ATR + 0.001),
            ("average_trading_value", qs.MIN_AVERAGE_TRADING_VALUE - 1),
            ("momentum5", -0.0001),
            ("volume_ratio", 0.79),
        ):
            _assert(
                not qs._entry_quality_allowed(
                    bar, {**common, "score": 70, field: value}
                ),
                f"{field} 품질 제한이 작동하지 않습니다.",
            )
        return {
            "atr_max": qs.MAX_ENTRY_ATR_PERCENT,
            "ema20_extension_atr_max": qs.MAX_ENTRY_EXTENSION_ATR,
            "average_trading_value_min": qs.MIN_AVERAGE_TRADING_VALUE,
            "pre_entry_score": qs.PRE_ENTRY_SCORE,
        }

    collector.check(
        "SIG-ENTRY-003",
        quality_guards,
        pass_message="v7.4 예비 포착 및 변동성·이격·모멘텀·참여·거래대금 품질 가드를 확인했습니다.",
    )

    def chase_entry_guards() -> dict[str, Any]:
        guard_bar = qs.PriceBar(
            qs.CHASE_GUARD_EFFECTIVE_DATE,
            105.0,
            108.0,
            103.0,
            106.99,
            2_000_000,
            10_000_000_000,
        )
        guard = {
            **common,
            "score": 100.0,
            "ema10": 103.0,
            "ema20": 100.0,
            "ema60": 99.0,
            "momentum5": qs.CHASE_MOMENTUM_5_MAX,
            "momentum20": 0.08,
            "ema20_extension_atr": qs.CHASE_MAX_ENTRY_EXTENSION_ATR - 0.01,
        }
        _assert(qs._entry_signal(guard_bar, guard), "추격매수 정상 경계 아래 진입이 거절됐습니다.")
        _assert(
            not qs._entry_signal(
                guard_bar,
                {**guard, "ema20_extension_atr": qs.CHASE_MAX_ENTRY_EXTENSION_ATR},
            ),
            "1.5ATR 이상 추격매수가 100점으로 승인됐습니다.",
        )
        percent_bar = qs.PriceBar(
            guard_bar.trade_date,
            guard_bar.open,
            108.0,
            guard_bar.low,
            107.0,
            guard_bar.volume,
            guard_bar.trading_value,
        )
        _assert(
            not qs._entry_signal(percent_bar, guard),
            "20일선 7% 이상 추격매수가 100점으로 승인됐습니다.",
        )
        spike = {**guard, "momentum5": qs.CHASE_MOMENTUM_5_MAX + 0.0001}
        _assert(
            not qs._entry_signal(
                guard_bar,
                guard,
                recent_indicators=[spike, guard, guard],
            ),
            "5일 10% 초과 급등의 2거래일 대기가 누락됐습니다.",
        )

        historical_bar = qs.PriceBar(
            date(2026, 9, 3),
            132_000.0,
            138_000.0,
            131_000.0,
            136_900.0,
            1_000_000,
            100_000_000_000,
        )
        historical_meritz = {
            **guard,
            "ema10": 130_000.0,
            "ema20": 122_135.8004,
            "ema60": 117_671.5272,
            "momentum5": 0.1504,
            "momentum20": 0.1370,
            "ema20_extension_atr": 2.3916,
        }
        _assert(
            qs._entry_signal(historical_bar, historical_meritz),
            "2026-09-03 메리츠 기존 신호가 소급 변경됐습니다.",
        )

        reentry_bars = [
            qs.PriceBar(
                date(2026, 9, 8) + timedelta(days=index),
                102.0,
                103.0,
                101.5,
                102.0,
                2_000_000,
                10_000_000_000,
            )
            for index in range(2)
        ]
        reentry_indicators = [
            {
                **guard,
                "ema20": 99.0,
                "ema20_extension_atr": 1.0,
                "momentum5": 0.03,
                "prior_high": 103.0,
            }
            for _bar in reentry_bars
        ]
        current_index = 1
        _assert(
            qs._reentry_cooldown_remaining(
                {"last_exit_index": 0},
                reentry_bars,
            ) == 0,
            "고정 재진입 유예가 적용일 이후에도 남아 있습니다.",
        )
        _assert(
            not qs._reentry_entry_allowed(
                reentry_bars,
                reentry_indicators,
                current_index,
                0,
            ),
            "전량 매도 다음 날 기존 진입 조건이 새 가격 사건 없이 승계됐습니다.",
        )
        last_bar = reentry_bars[current_index]
        reentry_bars[current_index] = qs.PriceBar(
            last_bar.trade_date,
            last_bar.open,
            last_bar.high,
            100.5,
            last_bar.close,
            last_bar.volume,
            last_bar.trading_value,
        )
        _assert(
            qs._reentry_entry_allowed(
                reentry_bars,
                reentry_indicators,
                current_index,
                0,
            ),
            "전량 매도 다음 날 20일선 눌림·회복 재진입이 거절됐습니다.",
        )
        return {
            "effective_date": qs.CHASE_GUARD_EFFECTIVE_DATE.isoformat(),
            "ema20_extension_atr_veto": qs.CHASE_MAX_ENTRY_EXTENSION_ATR,
            "ema20_extension_percent_veto": qs.CHASE_MAX_ENTRY_EXTENSION_PERCENT,
            "momentum5_veto": qs.CHASE_MOMENTUM_5_MAX,
            "momentum_lookback_bars": qs.CHASE_MOMENTUM_LOOKBACK_BARS,
            "historical_meritz_preserved": True,
            "fixed_reentry_cooldown_bars": 0,
            "legacy_reentry_cooldown_bars": qs.LEGACY_REENTRY_COOLDOWN_BARS,
            "reentry_rule_effective_date": qs.REENTRY_COOLDOWN_REMOVAL_EFFECTIVE_DATE.isoformat(),
            "fresh_reentry_required": True,
        }

    collector.check(
        "SIG-ENTRY-007",
        chase_entry_guards,
        pass_message="v7.4.2 추격매수 veto·고정 유예 없는 이벤트 재진입·메리츠 이력 보존을 확인했습니다.",
    )

    def versioned_entry_filters() -> dict[str, Any]:
        candidate_bar = qs.PriceBar(
            date(2026, 9, 4),
            100,
            103,
            99,
            102,
            2_000_000,
            10_000_000_000,
        )
        candidate_indicator = {
            **common,
            "score": 70.0,
            "momentum5": 0.007,
            "volume_ratio": 1.05,
            "atr_percent": 0.035,
            "ema20_extension_atr": 1.5,
        }
        comparison = qs.compare_entry_filter_candidates(
            candidate_bar,
            candidate_indicator,
        )
        _assert(
            qs.ENTRY_FILTER_VERSION == qs.ENTRY_FILTER_H1_VERSION,
            "활성 진입필터가 H1이 아닙니다.",
        )
        _assert(
            qs._entry_signal(candidate_bar, candidate_indicator),
            "기본 진입 경로가 H1을 통과하지 못했습니다.",
        )
        _assert(
            comparison[qs.ENTRY_FILTER_H1_VERSION]["allowed"] is True,
            "H1 경계 후보가 거절됐습니다.",
        )
        _assert(
            comparison[qs.ENTRY_FILTER_H2_VERSION]["allowed"] is False,
            "H2 shadow가 약한 모멘텀 후보를 허용했습니다.",
        )
        _assert(
            comparison[qs.ENTRY_FILTER_H3_VERSION]["allowed"] is True,
            "H3의 정상 ATR·이격 후보가 거절됐습니다.",
        )
        return {
            "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
            "active_filter": qs.ENTRY_FILTER_VERSION,
            "shadow_filters": list(qs.ENTRY_FILTER_SHADOW_VERSIONS),
            "comparison": comparison,
        }

    collector.check(
        "SIG-ENTRY-005",
        versioned_entry_filters,
        pass_message="v7.5-rc4 H1 활성 필터와 H2·H3 백엔드 shadow 비교 계약을 확인했습니다.",
    )

    def shadow_refresh_contract() -> dict[str, Any]:
        from app import main as main_module
        from app.services import entry_filter_backtest as shadow

        expected_filters = (
            qs.ENTRY_FILTER_BASELINE_VERSION,
            qs.ENTRY_FILTER_H1_VERSION,
            qs.ENTRY_FILTER_H2_VERSION,
            qs.ENTRY_FILTER_H3_VERSION,
        )
        _assert(
            shadow.FILTER_VERSIONS == expected_filters,
            "shadow 백테스트 필터 구성이 누락됐습니다.",
        )
        _assert(
            shadow.ENTRY_FILTER_SHADOW_CACHE_KEY.endswith(
                qs.CANDIDATE_STRATEGY_VERSION
            ),
            "shadow 백테스트 저장 키가 후보 버전에 고정되지 않았습니다.",
        )
        _assert(
            hasattr(main_module, "_run_entry_filter_shadow_backtest_loop"),
            "collector shadow 백테스트 루프가 연결되지 않았습니다.",
        )
        return {
            "refresh_interval_seconds": 300,
            "snapshot_key": shadow.ENTRY_FILTER_SHADOW_CACHE_KEY,
            "filters": list(expected_filters),
            "automatic_runner": "app.main._run_entry_filter_shadow_backtest_loop",
        }

    collector.check(
        "SIG-ENTRY-006",
        shadow_refresh_contract,
        pass_message="H1·H2·H3 일괄 shadow 백테스트 자동 갱신 루프와 분리 저장 계약을 확인했습니다.",
    )

    def execution_gap() -> dict[str, Any]:
        pending = {"signal_price": 100.0, "atr": 2.0}
        _assert(
            qs._entry_execution_allowed(103.0, pending),
            "1.5ATR 동일값 체결이 거절됐습니다.",
        )
        _assert(
            not qs._entry_execution_allowed(103.01, pending),
            "1.5ATR 초과 갭이 체결됐습니다.",
        )
        return {
            "atr_multiple": qs.MAX_ENTRY_GAP_ATR,
            "absolute_percent_max": qs.MAX_ENTRY_GAP_PERCENT,
        }

    collector.check(
        "SIG-EXECUTION-002",
        execution_gap,
        pass_message="진입 갭 1.5ATR·5% 제한 경계값을 확인했습니다.",
    )

    def cost_contract() -> dict[str, Any]:
        for raw in (-1.0, 0.003, 1.0):
            cost = qs._execution_cost({"volume_ratio": 1.0, "atr_percent": raw})
            _assert(
                qs.MIN_EXECUTION_COST_PER_SIDE
                <= cost
                <= qs.MAX_EXECUTION_COST_PER_SIDE,
                "체결비용 범위를 벗어났습니다.",
                cost=cost,
            )
        return {
            "minimum": qs.MIN_EXECUTION_COST_PER_SIDE,
            "maximum": qs.MAX_EXECUTION_COST_PER_SIDE,
        }

    collector.check(
        "SIG-EXECUTION-003",
        cost_contract,
        pass_message="편도 체결비용 0.125~0.50% 제한을 확인했습니다.",
    )

    def ladder_contract() -> dict[str, Any]:
        legacy = qs._profit_ladder_steps(date(2026, 8, 23))
        preservation = qs._profit_ladder_steps(date(2026, 8, 24))
        tactical = qs._profit_ladder_steps(date(2026, 8, 25))
        current = qs._profit_ladder_steps(date(2026, 9, 4))
        _assert(
            legacy == qs.LEGACY_PROFIT_LADDER_STEPS,
            "2026-08-24 이전 규칙이 바뀌었습니다.",
        )
        _assert(
            preservation == qs.PROFIT_PRESERVATION_LADDER_STEPS,
            "v7.1 규칙이 바뀌었습니다.",
        )
        _assert(tactical == qs.TACTICAL_PROFIT_LADDER_STEPS, "v7.3 수익확정 규칙이 바뀌었습니다.")
        _assert(
            current == qs.PROFIT_LADDER_STEPS
            and round(sum(step[1] for step in current), 8) == 1.0,
            "v7.4 +3%/+5% 전체 확정 계약이 깨졌습니다.",
        )
        stable_position = {"entry_price": 100.0, "initial_risk": 2.0}
        resolved = qs._resolved_profit_ladder_steps(stable_position, date(2026, 9, 4))
        _assert(resolved[0][0] == 1.5 and resolved[1][0] == 2.5, "고정 목표가의 R 변환이 바뀌었습니다.")
        return {
            "legacy": legacy,
            "v7_1": preservation,
            "v7_3": tactical,
            "v7_4": current,
            "runner": qs.MIN_RUNNER_FRACTION,
        }

    collector.check(
        "SIG-EXIT-001",
        ladder_contract,
        pass_message="역사적 사다리와 v7.4 +3%/+5% 수익확정을 확인했습니다.",
    )
    collector.check(
        "SIG-VERSION-001",
        ladder_contract,
        pass_message="결정일별 과거·현행 전략 규칙 보존을 확인했습니다.",
    )

    def lifecycle_contract() -> dict[str, Any]:
        _assert(qs.LEGACY_REENTRY_COOLDOWN_BARS == 10, "과거 재진입 유예 이력이 변경되었습니다.")
        current_bars = [
            qs.PriceBar(date(2026, 9, 8), 100, 101, 99, 100, 1_000_000, 10_000_000_000),
            qs.PriceBar(date(2026, 9, 9), 100, 101, 99, 100, 1_000_000, 10_000_000_000),
        ]
        _assert(
            qs._reentry_cooldown_remaining({"last_exit_index": 0}, current_bars) == 0,
            "현행 전략에 고정 재진입 유예가 남아 있습니다.",
        )
        _assert(qs.EXIT_SCORE == 42.0, "일반 이탈 점수가 변경되었습니다.")
        return {
            "fixed_cooldown_bars": 0,
            "legacy_cooldown_bars": qs.LEGACY_REENTRY_COOLDOWN_BARS,
            "effective_date": qs.REENTRY_COOLDOWN_REMOVAL_EFFECTIVE_DATE.isoformat(),
            "fresh_reentry_required": True,
            "exit_score": qs.EXIT_SCORE,
        }

    collector.check(
        "SIG-LIFECYCLE-002",
        lifecycle_contract,
        pass_message="현행 고정 유예 제거·이벤트 기반 재진입과 과거 10거래일 규칙 보존을 확인했습니다.",
    )
    collector.check(
        "SIG-EXIT-004",
        lifecycle_contract,
        pass_message="일반 추세 이탈 점수 계약을 확인했습니다.",
    )

    def pending_contract() -> dict[str, Any]:
        payload = {
            "action": "entry_pending",
            "is_current_holding": False,
            "entry_price": 100,
            "target_sell_price": 120,
            "return_rate": 0.2,
            "current": {
                "action": "entry_pending",
                "position_open": False,
                "entry_price": 100,
                "target_sell_price": 120,
                "unrealized_return": 0.2,
            },
        }
        sanitized = qs.sanitize_pending_entry_signal_payload(payload)
        _assert(
            all(
                sanitized.get(key) is None
                for key in ("entry_price", "target_sell_price", "return_rate")
            ),
            "예비 신호에 거래정보가 남았습니다.",
        )
        _assert(
            sanitized["current"]["entry_price"] is None,
            "예비 신호 current에 매수가가 남았습니다.",
        )
        return {"cleared_fields": ["entry_price", "target_sell_price", "return_rate"]}

    collector.check(
        "SIG-CONTRACT-001",
        pending_contract,
        pass_message="예비 신호의 매수가·목표가·수익률 비노출 계약을 확인했습니다.",
    )

    # Remaining gate-only cases are executed in pytest fixtures. Explicitly
    # mapped cases require their named testcase records; suite totals alone
    # cannot clear them. Unmapped legacy cases retain suite-level evidence
    # while their traceability mappings are migrated incrementally.
    try:
        pytest_result = _pytest_evidence(pytest_junit)
    except QaFailure as exc:
        pytest_result = {"error": str(exc), **exc.evidence}
    pytest_ok = bool(
        pytest_result
        and not pytest_result.get("error")
        and int(pytest_result.get("tests") or 0) > 0
        and int(pytest_result.get("failures") or 0) == 0
        and int(pytest_result.get("errors") or 0) == 0
    )
    executed = {item.id for item in collector.results}
    for case in catalog["cases"]:
        case_id = case["id"]
        if "gate" not in case["modes"]:
            continue
        if case_id in PYTEST_QA_CASE_TESTS:
            status, message, evidence = _mapped_pytest_evidence(
                case_id,
                pytest_result,
            )
            collector.add(
                case_id,
                status,
                message,
                evidence={"automation": case["automation"], **evidence},
            )
            continue
        if case_id in executed:
            continue
        collector.add(
            case_id,
            "pass" if pytest_ok else "fail" if pytest_result else "skip",
            (
                "pytest JUnit 증거에서 고정 픽스처·계약 테스트 통과를 확인했습니다."
                if pytest_ok
                else "pytest 실행이 실패했습니다."
                if pytest_result
                else "pytest JUnit 증거가 없어 고정 픽스처·계약 테스트를 확인하지 못했습니다."
            ),
            evidence={
                "automation": case["automation"],
                "delegated_to": "pytest",
                "pytest": _pytest_summary(pytest_result),
            },
        )


def _dataset_state(
    payload: dict[str, Any],
    name: str,
    *,
    allow_caution: bool = False,
    allow_not_applicable: bool = False,
) -> dict[str, Any]:
    dataset = (payload.get("datasets") or {}).get(name)
    _assert(isinstance(dataset, dict), f"{name} 데이터셋 상태가 없습니다.")
    state = str(dataset.get("state") or "unavailable")
    evidence = {
        "dataset": name,
        "state": state,
        "source": dataset.get("source") or (dataset.get("api") or {}).get("source"),
        "target_date": dataset.get("target_date") or dataset.get("signal_date"),
        "latest_date": dataset.get("latest_date"),
        "coverage_rate": dataset.get("coverage_rate"),
        "last_success_at": dataset.get("last_success_at")
        or (dataset.get("api") or {}).get("last_success_at"),
    }
    if state == "ready" or (allow_not_applicable and state == "not_applicable"):
        return evidence
    if allow_caution and state == "caution":
        raise QaWarning(f"{name} 커버리지가 caution입니다.", evidence)
    raise QaFailure(f"{name} 상태가 {state}입니다.", evidence)


def _valid_us_public_lifecycle_item(item: Any) -> bool:
    """Validate the public model state, not an assumed all-preliminary feed."""
    if not isinstance(item, dict):
        return False
    current = item.get("current")
    if not isinstance(current, dict):
        return False
    action = current.get("action")
    preliminary = action in {"entry_watch", "entry_pending", "full_exit_pending"}
    position_open = action in {"entered", "holding", "full_exit_pending"}
    if action not in {
        "entry_watch", "entry_pending", "entered", "holding",
        "full_exit_pending", "exited", "no_signal",
    }:
        return False
    try:
        rank = int(item.get("market_cap_rank"))
        exposure = Decimal(str(current.get("model_exposure_percent")))
    except (TypeError, ValueError, InvalidOperation):
        return False
    return bool(
        item.get("currency") == "USD"
        and 1 <= rank <= 100
        and (action == "no_signal" or (
            item.get("status") == ("preliminary" if preliminary else "confirmed")
            and item.get("is_preliminary") is preliminary
        ))
        and current.get("position_open") is position_open
        and exposure == (Decimal(100) if position_open else Decimal(0))
    )


def _live_checks(
    collector: ResultCollector,
    catalog: dict[str, Any],
    *,
    base_url: str,
    timeout: float,
    direct_kis: bool,
) -> tuple[str | None, dict[str, Any]]:
    api = ReadOnlyApi(base_url, timeout)
    context: dict[str, Any] = {}
    try:

        def health_contract() -> dict[str, Any]:
            health, meta = api.get("/health")
            ready, ready_meta = api.get("/readyz")
            _assert(
                health.get("status") == "ok", "health 상태가 ok가 아닙니다.", **meta
            )
            _assert(
                ready.get("status") == "ok" and ready.get("database_ok") is True,
                "readyz 또는 DB가 준비되지 않았습니다.",
                **ready_meta,
            )
            _assert(
                health.get("strategy_version") == catalog["strategy_version"],
                "health 전략 버전이 다릅니다.",
                strategy_version=health.get("strategy_version"),
            )
            context["health"] = health
            return {
                "health": meta,
                "readyz": ready_meta,
                "strategy_version": health.get("strategy_version"),
            }

        collector.check(
            "DATA-COM-002",
            health_contract,
            pass_message="헬스·준비 상태와 HTTP 타임아웃 계약을 확인했습니다.",
        )

        def domestic_product_boundary_contract() -> dict[str, Any]:
            dashboard, dashboard_meta = api.get_text(
                "/dashboard",
                view="home",
                market_scope="us",
                market="NASDAQ",
            )
            source, source_meta = api.get_text("/dashboard-app-v170.js")
            indices, indices_meta = api.get("/market/indices", limit=30)
            codes = {
                str(item.get("code") or "")
                for item in (indices.get("items") or [])
                if isinstance(item, dict)
            }
            _assert(
                '<html lang="ko" data-market-universe="kr">' in dashboard
                and '<meta name="secret-note-market-universe" content="kr" />'
                in dashboard,
                "스테이징 대시보드가 국내증시 단일 제품으로 표시되지 않습니다.",
                **dashboard_meta,
            )
            _assert(
                'const US_MARKET_ENABLED = PRODUCT_MARKET_UNIVERSE !== "kr";'
                in source
                and 'const requestedMarketScopeValue = IS_US_ONLY_PRODUCT'
                in source
                and 'PRODUCT_MARKET_UNIVERSE === "kr"\n    ? "kr"' in source
                and 'if (!US_MARKET_ENABLED) return null;' in source,
                "스테이징 클라이언트의 미국 시장 격리 가드가 누락됐습니다.",
                **source_meta,
            )
            _assert(
                {"KOSPI", "KOSDAQ"}.issubset(codes)
                and codes.issubset({"KOSPI", "KOSDAQ"}),
                "국내 시장 지수 API에 KOSPI·KOSDAQ 외 자산이 섹였습니다.",
                codes=sorted(codes),
                **indices_meta,
            )
            return {
                "dashboard": dashboard_meta,
                "source": source_meta,
                "indices": indices_meta,
                "market_universe": "kr",
                "market_codes": sorted(codes),
                "us_runtime_guard": True,
            }

        collector.check(
            "SIG-UI-030",
            domestic_product_boundary_contract,
            pass_message="스테이징의 국내증시 단일 제품 경계와 지수 계약을 확인했습니다.",
        )

        def canonical_us_gateway_contract() -> dict[str, Any]:
            us_shell, shell_meta = api.get_text("/us", view="home")
            version, version_meta = api.get("/us-version")
            bridge, bridge_meta = api.get_text("/us-gateway/assets/us-public-bridge.js")
            _assert(
                shell_meta.get("us_market_route") == "dedicated-service"
                and version_meta.get("us_market_route") == "dedicated-service"
                and bridge_meta.get("us_market_route") == "dedicated-service",
                "공식 /us 요청이 미국 독립 서비스 관문을 통과하지 않았습니다.",
                shell=shell_meta, version=version_meta, bridge=bridge_meta,
            )
            _assert(
                '<meta name="secret-note-market-universe" content="us"' in us_shell
                and '/us-gateway/dashboard-app-v170.js' in us_shell
                and '/us-gateway/assets/dashboard/styles.css' in us_shell
                and '/us-gateway/assets/us-public-bridge.js' in us_shell,
                "미국 셸이 독립 서비스 자산을 사용하지 않습니다.",
                shell=shell_meta,
            )
            _assert(
                bool(version.get("version"))
                and 'window.__US_PUBLIC_GATEWAY__ = prefix;' in bridge,
                "미국 독립 버전 또는 데이터 요청 관문이 없습니다.",
                version=version_meta, bridge=bridge_meta,
            )
            return {"shell": shell_meta, "version": version_meta, "bridge": bridge_meta}

        if (context.get("health") or {}).get("us_market_enabled") is False:
            collector.check(
                "DATA-COM-006",
                canonical_us_gateway_contract,
                pass_message="공식 /us 주소의 독립 미국 셸·버전·자산 관문을 확인했습니다.",
            )
        else:
            collector.add(
                "DATA-COM-006",
                "skip",
                "기존 미국 수집 런타임에서는 아직 공식 /us 관문을 활성화하지 않았습니다.",
                evidence={"us_market_enabled": True},
            )

        def us_market_payloads() -> dict[str, Any]:
            cached = context.get("us_market_contract")
            if isinstance(cached, dict):
                return cached
            feed, feed_meta = api.get(
                "/us/market/quant-signals", limit=50, recent_days=30
            )
            recommendations, recommendation_meta = api.get(
                "/us/market/recommendations", limit=20, candidate_limit=100
            )
            _assert(isinstance(feed, dict), "미국 시그널 응답이 객체가 아닙니다.")
            _assert(
                isinstance(recommendations, dict),
                "미국 추천 응답이 객체가 아닙니다.",
            )
            expected_version = str(catalog.get("us_strategy_version") or "")
            _assert(
                feed.get("strategy_version") == expected_version
                and recommendations.get("strategy_version") == expected_version,
                "미국 시그널·추천 전략 버전이 RC1과 다릅니다.",
                feed_version=feed.get("strategy_version"),
                recommendation_version=recommendations.get("strategy_version"),
                expected_version=expected_version,
            )
            _assert(
                feed.get("rollout_mode") == "model_replay"
                and feed.get("execution_enabled") is False
                and feed.get("stateful_lifecycle_replay_enabled") is True
                and feed.get("reentry_runtime_enabled") is True
                and feed.get("lifecycle_replay_version") == "us-next-open-model-replay-v1"
                and feed.get("stateful_lifecycle_replay_complete") is True,
                "미국 전략 생명주기 모델 replay 계약이 깨졌습니다.",
            )
            items = feed.get("items") or []
            _assert(isinstance(items, list), "미국 시그널 items가 배열이 아닙니다.")
            public_candidate_ready = bool(
                feed.get("status") == "ready"
                and feed.get("data_state") == "ready"
                and feed.get("new_entries_allowed") is True
            )
            invalid_items: list[str] = []
            entry_pending_count = 0
            confirmed_position_count = 0
            for item in items:
                if not isinstance(item, dict):
                    invalid_items.append("non_object")
                    continue
                current_signal = item.get("current") or {}
                if current_signal.get("action") == "entry_pending":
                    entry_pending_count += 1
                action = str(current_signal.get("action") or "")
                position_open = action in {"entered", "holding", "full_exit_pending"}
                if position_open:
                    confirmed_position_count += 1
                if not _valid_us_public_lifecycle_item(item):
                    invalid_items.append(str(item.get("code") or "unknown"))
            _assert(
                not invalid_items,
                "미국 공개 모델 생명주기의 USD·Top100·상태 계약이 깨졌습니다.",
                invalid_items=invalid_items,
            )
            _assert(
                confirmed_position_count <= int(feed.get("confirmed_count") or 0) <= 100,
                "미국 모델 확정 수가 공개 페이지의 열린 포지션 수보다 작거나 Top100을 넘습니다.",
                confirmed_count=feed.get("confirmed_count"),
                confirmed_position_count=confirmed_position_count,
            )
            recommendation_items = recommendations.get("items") or []
            _assert(
                isinstance(recommendation_items, list),
                "미국 추천 items가 배열이 아닙니다.",
            )
            recommendation_entry_pending_count = sum(
                1
                for item in recommendation_items
                if isinstance(item, dict)
                and (
                    str(item.get("action") or "") == "entry_pending"
                    or (
                        isinstance(item.get("ai_trade_signal"), dict)
                        and isinstance(item["ai_trade_signal"].get("current"), dict)
                        and item["ai_trade_signal"]["current"].get("action")
                        == "entry_pending"
                    )
                )
            )
            universe_state = str(feed.get("universe_data_state") or "unavailable")
            universe_count = int(feed.get("universe_count") or 0)
            evaluated_count = int(feed.get("evaluated_count") or 0)
            data_coverage_count = int(feed.get("data_coverage_count") or 0)
            signal_eligible_raw = feed.get("signal_eligible_count")
            insufficient_history_raw = feed.get("insufficient_history_count")
            _assert(
                type(signal_eligible_raw) is int
                and type(insufficient_history_raw) is int
                and signal_eligible_raw >= 0
                and insufficient_history_raw >= 0,
                "미국 신호 적격·신규 상장 이력 수가 정수 계약이 아닙니다.",
                signal_eligible_count=signal_eligible_raw,
                insufficient_history_count=insufficient_history_raw,
            )
            signal_eligible_count = int(signal_eligible_raw)
            insufficient_history_count = int(insufficient_history_raw)
            coverage = feed.get("coverage") or {}
            _assert(isinstance(coverage, dict), "미국 커버리가 객체가 아닙니다.")
            coverage_complete = bool(
                universe_state == "ready"
                and universe_count == 100
                and evaluated_count == 100
                and data_coverage_count == 100
                and signal_eligible_count + insufficient_history_count == 100
                and coverage.get("signal_eligible_count")
                == signal_eligible_count
                and coverage.get("insufficient_history_count")
                == insufficient_history_count
                and coverage.get("complete") is True
                and int(coverage.get("history_error_count") or 0) == 0
                and int(coverage.get("sector_classification_error_count") or 0)
                == 0
            )
            feed_state = str(feed.get("data_state") or feed.get("status") or "unavailable")
            recommendation_state = str(
                recommendations.get("data_state")
                or recommendations.get("status")
                or "unavailable"
            )
            operational_ready = bool(
                feed.get("status") == "ready"
                and feed_state == "ready"
                and recommendations.get("status") == "ready"
                and recommendation_state == "ready"
            )
            entry_ready = bool(operational_ready and coverage_complete)
            try:
                from app.services.us_market_calendar import (
                    latest_completed_us_market_session,
                )

                expected_universe_as_of = (
                    latest_completed_us_market_session().session_date.isoformat()
                )
            except Exception as exc:
                raise QaFailure(
                    "XNYS 마지막 완료 세션을 확인할 수 없습니다.",
                    {"error_type": type(exc).__name__},
                ) from exc
            stock_analysis: dict[str, Any] | None = None
            stock_analysis_meta: dict[str, Any] | None = None
            if entry_ready:
                stock_analysis, stock_analysis_meta = api.get(
                    "/us/stocks/NVDA/ai-analysis"
                )
                stock_reasons = stock_analysis.get("public_reasons") or []
                _assert(
                    stock_analysis.get("status") == "ready"
                    and stock_analysis.get("data_state") == "ready"
                    and stock_analysis.get("snapshot_id") == feed.get("snapshot_id")
                    and stock_analysis.get("snapshot_checksum")
                    == feed.get("snapshot_checksum")
                    and stock_analysis.get("is_current_universe_member") is True
                    and stock_analysis.get("public_evidence_status") == "ready"
                    and stock_analysis.get("data_covered") == 3
                    and [
                        reason.get("key")
                        for reason in stock_reasons
                        if isinstance(reason, dict)
                    ]
                    == ["trend_20d", "trend_60d", "flow"]
                    and [
                        reason.get("label")
                        for reason in stock_reasons
                        if isinstance(reason, dict)
                    ]
                    == ["20일 가격", "60일 가격", "거래대금 참여도"]
                    and all(
                        reason.get("available") is True
                        for reason in stock_reasons
                        if isinstance(reason, dict)
                    )
                    and str(stock_analysis.get("as_of") or "")[:10]
                    == str(feed.get("universe_as_of") or "")[:10]
                    and str(stock_analysis.get("evidence_session_date") or "")
                    == str(feed.get("universe_as_of") or "")[:10],
                    "미국 Top100 종목 분석이 비후보 완료 세션 공개근거를 유지하지 못했습니다.",
                    analysis=stock_analysis_meta,
                    action=(stock_analysis.get("current") or {}).get("action"),
                    labels=[
                        reason.get("label")
                        for reason in stock_reasons
                        if isinstance(reason, dict)
                    ],
                    availability=[
                        reason.get("available")
                        for reason in stock_reasons
                        if isinstance(reason, dict)
                    ],
                    analysis_as_of=stock_analysis.get("as_of"),
                    universe_as_of=feed.get("universe_as_of"),
                )
            _assert(
                feed_state == recommendation_state
                and feed.get("status") == recommendations.get("status"),
                "미국 추천과 시그널의 상태가 다릅니다.",
                feed_status=feed.get("status"),
                recommendation_status=recommendations.get("status"),
                feed_state=feed_state,
                recommendation_state=recommendation_state,
            )
            _assert(
                feed.get("new_entries_allowed") is entry_ready
                and recommendations.get("new_entries_allowed") is entry_ready,
                "미국 신규 진입 허용 상태가 ready·100/100/100 커버리와 다릅니다.",
                entry_ready=entry_ready,
                feed_new_entries_allowed=feed.get("new_entries_allowed"),
                recommendation_new_entries_allowed=recommendations.get(
                    "new_entries_allowed"
                ),
                universe_count=universe_count,
                evaluated_count=evaluated_count,
                data_coverage_count=data_coverage_count,
                signal_eligible_count=signal_eligible_count,
                insufficient_history_count=insufficient_history_count,
                coverage_complete=coverage.get("complete"),
            )
            if entry_ready:
                _assert(
                    feed.get("universe_as_of")
                    and feed.get("universe_checksum")
                    and feed.get("snapshot_id")
                    and feed.get("snapshot_checksum"),
                    "미국 ready Top 100 canonical 스냅샷 identity가 누락됐습니다.",
                    universe_as_of=feed.get("universe_as_of"),
                    snapshot_id=feed.get("snapshot_id"),
                )
                _assert(
                    str(feed.get("universe_as_of") or "")[:10]
                    == expected_universe_as_of,
                    "미국 ready 스냅샷이 XNYS 마지막 완료 세션일과 다릅니다.",
                    universe_as_of=feed.get("universe_as_of"),
                    expected_universe_as_of=expected_universe_as_of,
                )
            else:
                non_ready_actions = [
                    str((item.get("current") or {}).get("action") or "")
                    for item in items
                    if isinstance(item, dict)
                ]
                non_ready_recommendation_actions = [
                    str(
                        item.get("action")
                        or (
                            ((item.get("ai_trade_signal") or {}).get("current") or {}).get(
                                "action"
                            )
                            if isinstance(item.get("ai_trade_signal"), dict)
                            else ""
                        )
                        or ""
                    )
                    for item in recommendation_items
                    if isinstance(item, dict)
                ]
                _assert(
                    entry_pending_count == 0
                    and int(feed.get("entry_pending_count") or 0) == 0
                    and recommendation_entry_pending_count == 0,
                    "미국 non-ready·불완전 커버리에서 신규 매수대기가 생성됐습니다.",
                    universe_state=universe_state,
                    feed_state=feed_state,
                    coverage_complete=coverage_complete,
                    entry_pending_count=entry_pending_count,
                    feed_entry_pending_count=feed.get("entry_pending_count"),
                    recommendation_entry_pending_count=recommendation_entry_pending_count,
                )
                _assert(
                    not ({"entry_watch", "entry_pending"} & set(non_ready_actions))
                    and not (
                        {"entry_watch", "entry_pending"}
                        & set(non_ready_recommendation_actions)
                    ),
                    "미국 non-ready·불완전 스냅샷이 관망/no_signal로 닫히지 않았습니다.",
                    feed_actions=non_ready_actions,
                    recommendation_actions=non_ready_recommendation_actions,
                )
            _assert(
                recommendations.get("universe_as_of") == feed.get("universe_as_of")
                and int(recommendations.get("universe_count") or 0) == universe_count
                and int(recommendations.get("evaluated_count") or 0)
                == evaluated_count
                and int(recommendations.get("data_coverage_count") or 0)
                == data_coverage_count
                and recommendations.get("signal_eligible_count")
                == signal_eligible_count
                and recommendations.get("insufficient_history_count")
                == insufficient_history_count
                and recommendations.get("snapshot_id") == feed.get("snapshot_id")
                and recommendations.get("snapshot_checksum")
                == feed.get("snapshot_checksum"),
                "미국 추천과 시그널이 다른 canonical 스냅샷을 사용합니다.",
                feed_snapshot_id=feed.get("snapshot_id"),
                recommendation_snapshot_id=recommendations.get("snapshot_id"),
                feed_snapshot_checksum=feed.get("snapshot_checksum"),
                recommendation_snapshot_checksum=recommendations.get(
                    "snapshot_checksum"
                ),
            )
            _assert(
                recommendations.get("baseline_strategy_version")
                == feed.get("baseline_strategy_version")
                and recommendations.get("sector_classification_version")
                == feed.get("sector_classification_version")
                and recommendations.get("stateful_lifecycle_replay_enabled")
                is True
                and recommendations.get("reentry_runtime_enabled") is True
                and recommendations.get("lifecycle_replay_version")
                == "us-next-open-model-replay-v1",
                "미국 추천과 시그널의 baseline·섹터분류·runtime 계약이 다릅니다.",
            )
            invalid_recommendations: list[str] = []
            if entry_ready:
                _assert(
                    recommendations.get("recommendation_model_version")
                    == "us-independent-recommendation-v1"
                    and recommendations.get("recommendation_selection_rule")
                    == "recommendation_score_ranked_independent_of_trade_signal",
                    "미국 추천이 독립 점수 모델·선정 규칙을 공개하지 않았습니다.",
                    model_version=recommendations.get(
                        "recommendation_model_version"
                    ),
                    selection_rule=recommendations.get(
                        "recommendation_selection_rule"
                    ),
                )
                _assert(
                    bool(recommendation_items),
                    "ready 미국 Top100 스냅샷에서 독립 추천 후보가 비었습니다.",
                )
                for item in recommendation_items:
                    if not isinstance(item, dict):
                        invalid_recommendations.append("non_object")
                        continue
                    score = item.get("recommendation_score")
                    signal = item.get("ai_trade_signal") or {}
                    if (
                        not isinstance(score, (int, float))
                        or not 0 <= float(score) <= 100
                        or item.get("recommendation_model_version")
                        != "us-independent-recommendation-v1"
                        or item.get("action") != "추천 후보"
                        or not isinstance(signal, dict)
                        or "score" in signal
                    ):
                        invalid_recommendations.append(
                            str(item.get("code") or "unknown")
                        )
                _assert(
                    not invalid_recommendations,
                    "미국 독립 추천 점수와 nested 시그널 분리 계약이 깨졌습니다.",
                    invalid_codes=invalid_recommendations,
                )
            public_case = next(
                (case for case in catalog["cases"] if case.get("id") == "SIG-UI-022"),
                {},
            )
            forbidden_fields = set(
                public_case.get("inputs", {}).get("forbidden_public_fields") or []
            )
            forbidden_paths = _forbidden_key_paths(
                {
                    "feed": feed,
                    "recommendations": recommendations,
                    "stock_analysis": stock_analysis,
                },
                forbidden_fields,
            )
            _assert(
                not forbidden_paths,
                "미국 공개 응답에 내부 점수·필터 키가 남았습니다.",
                forbidden_paths=forbidden_paths,
            )
            invalid_public_reasons: list[str] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                reasons = item.get("public_reasons")
                valid_keys = isinstance(reasons, list) and [
                    reason.get("key") for reason in reasons if isinstance(reason, dict)
                ] == ["trend_20d", "trend_60d", "flow"]
                availability_valid = bool(
                    valid_keys
                    and (
                        all(reason.get("available") is True for reason in reasons)
                        if entry_ready
                        else all(
                            reason.get("available") is False
                            and str(reason.get("state") or "").lower() == "unavailable"
                            for reason in reasons
                        )
                    )
                )
                if not availability_valid:
                    invalid_public_reasons.append(str(item.get("code") or "unknown"))
            _assert(
                not invalid_public_reasons,
                "미국 공개 근거가 ready 여부에 맞는 20일·60일·거래대금 세 근거가 아닙니다.",
                invalid_codes=invalid_public_reasons,
            )
            result = {
                "feed": feed_meta,
                "recommendations": recommendation_meta,
                "strategy_version": expected_version,
                "universe_state": universe_state,
                "data_state": feed_state,
                "universe_count": universe_count,
                "evaluated_count": evaluated_count,
                "data_coverage_count": data_coverage_count,
                "signal_eligible_count": signal_eligible_count,
                "insufficient_history_count": insufficient_history_count,
                "sector_classification_error_count": int(
                    feed.get("sector_classification_error_count") or 0
                ),
                "coverage_complete": coverage_complete,
                "universe_as_of": feed.get("universe_as_of"),
                "expected_universe_as_of": expected_universe_as_of,
                "universe_checksum": feed.get("universe_checksum"),
                "snapshot_id": feed.get("snapshot_id"),
                "snapshot_checksum": feed.get("snapshot_checksum"),
                "preliminary_count": feed.get("preliminary_count"),
                "confirmed_count": feed.get("confirmed_count"),
                "visible_item_count": len(items),
                "entry_pending_count": entry_pending_count,
                "recommendation_entry_pending_count": recommendation_entry_pending_count,
                "recommendation_model_version": recommendations.get(
                    "recommendation_model_version"
                ),
                "recommendation_count": len(recommendation_items),
                "forbidden_public_paths": forbidden_paths,
                "methodology": feed.get("methodology"),
                "stock_analysis": stock_analysis_meta,
                "stock_public_evidence_status": (
                    stock_analysis.get("public_evidence_status")
                    if isinstance(stock_analysis, dict)
                    else None
                ),
                "stock_evidence_session_date": (
                    stock_analysis.get("evidence_session_date")
                    if isinstance(stock_analysis, dict)
                    else None
                ),
            }
            context["us_market_contract"] = result
            return result

        def us_version_contract() -> dict[str, Any]:
            health = context.get("health") or {}
            _assert(
                health.get("us_strategy_version") == catalog.get("us_strategy_version"),
                "health 미국 전략 버전이 RC1과 다릅니다.",
                health_version=health.get("us_strategy_version"),
            )
            return us_market_payloads()

        def us_universe_contract() -> dict[str, Any]:
            evidence = us_market_payloads()
            if evidence["universe_state"] != "ready":
                raise QaWarning(
                    "미국 Top 100 원천은 일시적으로 준비되지 않았지만 신규 진입은 차단됐습니다.",
                    evidence,
                )
            return evidence

        def us_evidence_contract() -> dict[str, Any]:
            evidence = us_market_payloads()
            methodology = " ".join(str(item) for item in evidence.get("methodology") or [])
            _assert(
                all(token in methodology for token in ("수정 OHLC", "SPY·QQQ", "거래대금")),
                "미국 수정주가·시장·거래대금 근거 설명이 누락됐습니다.",
            )
            if evidence["data_state"] != "ready" or not evidence["coverage_complete"]:
                raise QaWarning(
                    "미국 근거 원천은 일시적으로 준비되지 않았지만 매수 승격은 차단됐습니다.",
                    evidence,
                )
            return evidence

        if (context.get("health") or {}).get("us_market_enabled") is False:
            for case_id in (
                "SIG-US-VERSION-001", "DATA-US-UNIVERSE-001",
                "DATA-US-SIGNAL-INPUT-001", "DATA-US-EVIDENCE-001",
                "SIG-US-CONTRACT-001", "REC-US-INDEPENDENT-001", "SIG-UI-022",
            ):
                collector.add(
                    case_id, "skip",
                    "국내 전용 런타임의 미국 수집은 비활성화되어 미국 스테이징에서 별도 검증합니다.",
                    evidence={"surface": "dashboard", "us_market_enabled": False},
                )
        else:
            for case_id, check, message in (
                ("SIG-US-VERSION-001", us_version_contract, "health·미국 시그널·추천의 RC1 버전을 확인했습니다."),
                ("DATA-US-UNIVERSE-001", us_universe_contract, "미국 완료 세션 시총 Top 100 스냅샷을 확인했습니다."),
                ("DATA-US-SIGNAL-INPUT-001", us_evidence_contract, "미국 수정 일봉·완료 세션 입력 계약을 확인했습니다."),
                ("DATA-US-EVIDENCE-001", us_evidence_contract, "미국 시장·상대강도·달러 거래대금 근거 계약을 확인했습니다."),
                ("SIG-US-CONTRACT-001", us_market_payloads, "미국 Top100 모델 시그널·추천 공개 계약을 확인했습니다."),
                ("REC-US-INDEPENDENT-001", us_market_payloads, "미국 Top100 독립 추천 점수와 시그널 분리 계약을 확인했습니다."),
                ("SIG-UI-022", us_market_payloads, "미국 공개 근거 3개·내부 수치 비노출·non-ready 관망 계약을 확인했습니다."),
            ):
                collector.check(case_id, check, pass_message=message)

        def staging_page_summary_contract() -> dict[str, Any]:
            summary_case = next(
                (case for case in catalog["cases"] if case.get("id") == "SIG-UI-017"),
                {},
            )
            expected_prompt_version = str(
                summary_case.get("inputs", {}).get("prompt_version") or ""
            )
            dashboard, dashboard_meta = api.get_text("/dashboard", view="home")
            is_staging = (
                '<meta name="secret-note-environment" content="staging" />'
                in dashboard
            )
            request_payload = {
                "page_type": "recommendation_detail",
                "facts": {
                    "code": "005930",
                    "name": "삼성전자",
                    "buy_condition_met": True,
                    "recommendation_state": "entry_confirmed",
                    "customer_state": "new-buy-wait",
                    "customer_state_label": "신규 매수 대기",
                    "customer_state_note": "아직 매수 전",
                    "additional_buy_label": "보유 전",
                    "signal_action": "entry_pending",
                    "position_open": False,
                    "sources": [
                        {
                            "id": "buy-condition",
                            "label": "추천 기준 확인",
                            "value": "신규 매수 대기",
                        }
                    ],
                },
                "fallback": {
                    "headline": "삼성전자, 신규 매수를 기다리는 단계예요",
                    "summary": "추천 기준은 통과했지만 아직 매수 전이에요.",
                    "reason": "추천 점수와 가격 조건, 서로 다른 확인 자료가 기준을 통과했어요.",
                    "action_title": "지금은 새로 살 가격이 기준 안인지 확인할 때예요",
                    "next_check": "다음 거래가 시작될 때 가격이 매수 기준 안인지 확인해요.",
                    "evidence_refs": ["buy-condition"],
                },
            }
            status_code, payload, response_meta = api.post_json(
                "/ai/page-summary",
                request_payload,
            )
            _assert(
                status_code == 200,
                "쉬운 설명 API가 정상 응답하지 않았습니다.",
                http_status=status_code,
                latency_ms=response_meta["latency_ms"],
            )
            _assert(
                isinstance(payload, dict),
                "스테이징 쉬운 설명 API가 JSON 객체를 반환하지 않았습니다.",
                **response_meta,
            )
            required_copy = {
                "headline",
                "summary",
                "reason",
                "action_title",
                "next_check",
                "evidence_refs",
            }
            _assert(
                required_copy.issubset(payload)
                and all(str(payload.get(key) or "").strip() for key in required_copy - {"evidence_refs"})
                and isinstance(payload.get("evidence_refs"), list)
                and payload.get("generation_mode") in {"openai", "rules"}
                and expected_prompt_version
                and payload.get("prompt_version") == expected_prompt_version,
                "쉬운 설명 응답 스키마가 잘못됐습니다.",
                response_fields=sorted(payload),
                generation_mode=payload.get("generation_mode"),
                prompt_version=payload.get("prompt_version"),
                expected_prompt_version=expected_prompt_version,
            )
            return {
                "environment_meta": "staging" if is_staging else "production",
                "http_status": status_code,
                "latency_ms": response_meta["latency_ms"],
                "dashboard_http_status": dashboard_meta["http_status"],
                "generation_mode": payload.get("generation_mode"),
                "model_name": payload.get("model_name"),
                "prompt_version": payload.get("prompt_version"),
                "expected_prompt_version": expected_prompt_version,
                "cache_hit": payload.get("cache_hit"),
                "token_usage": {
                    "input": payload.get("input_tokens"),
                    "output": payload.get("output_tokens"),
                    "total": payload.get("total_tokens"),
                },
                "estimated_cost_usd": payload.get("estimated_cost_usd"),
            }

        collector.check(
            "SIG-UI-017",
            staging_page_summary_contract,
            pass_message="쉬운 설명 응답과 안전 폴백 계약을 확인했습니다.",
        )

        def staging_briefing_summary_contract() -> dict[str, Any]:
            briefing_case = next(
                (case for case in catalog["cases"] if case.get("id") == "SIG-UI-018"),
                {},
            )
            expected_prompt_version = str(
                briefing_case.get("inputs", {}).get("prompt_version") or ""
            )
            dashboard, dashboard_meta = api.get_text("/dashboard", view="news")
            is_staging = (
                '<meta name="secret-note-environment" content="staging" />'
                in dashboard
            )
            request_payload = {
                "page_type": "briefing_edition",
                "facts": {
                    "edition": "midday",
                    "edition_key": "qa-live:midday",
                    "edition_label": "점심판",
                    "publication_date": datetime.now(KST).date().isoformat(),
                    "selected_news_count": 1,
                    "opportunity_count": 1,
                    "caution_count": 0,
                    "sources": [
                        {
                            "id": "briefing-market-live-1",
                            "label": "시장 흐름",
                            "value": "공개 시장 소식을 확인했어요.",
                            "evidence": "장중 흐름을 확인할 공개 자료예요.",
                        }
                    ],
                },
                "fallback": {
                    "headline": "오전 핵심을 새로 정리했어요",
                    "summary": "공개 시장 소식을 짧게 확인해요.",
                    "reason": "장중 흐름을 확인할 공개 자료예요.",
                    "action_title": "이번 점심판에서 먼저 볼 내용",
                    "next_check": "원문과 최신 시세를 함께 확인하세요.",
                    "evidence_refs": ["briefing-market-live-1"],
                },
            }
            status_code, payload, response_meta = api.post_json(
                "/ai/page-summary",
                request_payload,
            )
            _assert(
                status_code == 200 and isinstance(payload, dict),
                "브리핑 GPT 문구 정리 API가 정상 응답하지 않았습니다.",
                http_status=status_code,
                latency_ms=response_meta["latency_ms"],
            )
            required_copy = {
                "headline",
                "summary",
                "reason",
                "action_title",
                "next_check",
                "evidence_refs",
            }
            _assert(
                required_copy.issubset(payload)
                and payload.get("generation_mode") in {"openai", "rules"}
                and payload.get("prompt_version") == expected_prompt_version
                and set(payload.get("evidence_refs") or {})
                <= {"briefing-market-live-1"},
                "브리핑 구조화 요약 계약이 잘못됐습니다.",
                response_fields=sorted(payload),
                generation_mode=payload.get("generation_mode"),
                prompt_version=payload.get("prompt_version"),
                evidence_refs=payload.get("evidence_refs"),
            )
            return {
                "environment_meta": "staging" if is_staging else "production",
                "http_status": status_code,
                "latency_ms": response_meta["latency_ms"],
                "dashboard_http_status": dashboard_meta["http_status"],
                "generation_mode": payload.get("generation_mode"),
                "model_name": payload.get("model_name"),
                "prompt_version": payload.get("prompt_version"),
                "cache_hit": payload.get("cache_hit"),
                "token_usage": {
                    "input": payload.get("input_tokens"),
                    "output": payload.get("output_tokens"),
                    "total": payload.get("total_tokens"),
                },
                "estimated_cost_usd": payload.get("estimated_cost_usd"),
            }

        collector.check(
            "SIG-UI-018",
            staging_briefing_summary_contract,
            pass_message="세 브리핑의 구조화 문구 정리와 안전 폴백 계약을 확인했습니다.",
        )

        def integrations_contract() -> dict[str, Any]:
            payload, meta = api.get("/meta/integrations")
            _assert(
                isinstance(payload, list) and payload,
                "연동 메타데이터가 비어 있습니다.",
                **meta,
            )
            secret_fields: list[str] = []
            for index, item in enumerate(payload):
                if not isinstance(item, dict):
                    continue
                for key, value in item.items():
                    # ``required_settings: [KIS_APP_SECRET]`` documents a
                    # variable name and is safe. Only secret-shaped response
                    # fields containing an actual value are forbidden.
                    if SECRET_KEY_RE.search(str(key)) and value not in (
                        None,
                        "",
                        False,
                        [],
                        {},
                    ):
                        secret_fields.append(f"{index}:{key}")
            _assert(
                not secret_fields,
                "연동 메타데이터에 인증정보 값이 노출됐습니다.",
                secret_fields=secret_fields,
            )
            context["integrations"] = payload
            return {
                **meta,
                "integrations": [
                    {"name": item.get("name"), "configured": item.get("configured")}
                    for item in payload
                ],
            }

        collector.check(
            "DATA-COM-001",
            integrations_contract,
            pass_message="연동 상태에 인증정보가 노출되지 않았습니다.",
        )

        def quality_contract() -> dict[str, Any]:
            payload, meta = api.get(
                "/meta/signal-data-quality", probe="true", sample_code="005930"
            )
            _assert(
                isinstance(payload, dict), "데이터 품질 응답이 객체가 아닙니다.", **meta
            )
            # Preserve the response for the layer-specific checks even when
            # this top-level version contract itself fails.
            context["quality"] = payload
            _assert(
                payload.get("strategy_version") == catalog["strategy_version"],
                "데이터 품질 전략 버전이 다릅니다.",
                strategy_version=payload.get("strategy_version"),
            )
            _assert(payload.get("as_of"), "데이터 품질 기준 시각이 없습니다.")
            return {
                **meta,
                "status": payload.get("status"),
                "as_of": payload.get("as_of"),
                "strategy_version": payload.get("strategy_version"),
            }

        collector.check(
            "DATA-COM-004",
            quality_contract,
            pass_message="기준 시각·전략 버전·품질 상태 응답을 확인했습니다.",
        )
        quality = context.get("quality") or {}

        core_map = (
            ("DATA-KRX-NAVER-002", "price", False, False),
            ("DATA-KRX-NAVER-005", "investor_flow", False, False),
            ("DATA-GLOBAL-001", "market_index", False, False),
            ("DATA-FUND-RESEARCH-001", "fundamentals", True, False),
            ("DATA-FUND-RESEARCH-002", "research", False, False),
            ("DATA-DART-002", "disclosure", False, False),
            ("SIG-EVIDENCE-003", "entry_evidence_snapshot", False, True),
        )
        for case_id, name, allow_caution, allow_na in core_map:
            collector.check(
                case_id,
                lambda name=name, allow_caution=allow_caution, allow_na=allow_na: (
                    _dataset_state(
                        quality,
                        name,
                        allow_caution=allow_caution,
                        allow_not_applicable=allow_na,
                    )
                ),
                pass_message=f"{name} 저장 데이터의 최신성과 커버리지를 확인했습니다.",
            )

        def coherence_contract() -> dict[str, Any]:
            coherence = quality.get("coherence") or {}
            evidence = {
                "state": coherence.get("state"),
                "signal_window_orphans": coherence.get(
                    "signal_window_orphan_stock_codes"
                ),
                "future_dated_rows": coherence.get("future_dated_rows"),
                "malformed_fundamentals": coherence.get(
                    "malformed_fundamental_snapshots"
                ),
                "flow_normalization": coherence.get("flow_normalization"),
            }
            _assert(
                coherence.get("state") == "ready",
                "저장 데이터 시점·매핑 정합성이 깨졌습니다.",
                **evidence,
            )
            return evidence

        collector.check(
            "SIG-INPUT-002",
            coherence_contract,
            pass_message="미래 데이터·미매핑·파싱 정합성을 확인했습니다.",
        )

        def source_probes() -> dict[str, Any]:
            probe = quality.get("api_probe") or {}
            items = probe.get("items") if isinstance(probe, dict) else None
            _assert(
                isinstance(items, list) and items, "외부 원천 probe 결과가 없습니다."
            )
            states = {
                str(item.get("key")): str(item.get("state"))
                for item in items
                if isinstance(item, dict)
            }
            failed = [key for key, state in states.items() if state != "ready"]
            if failed:
                raise QaWarning(
                    "일부 외부 원천 직접 probe가 실패했지만 저장 데이터 상태를 별도로 판정했습니다.",
                    {"states": states, "failed": failed},
                )
            return {"states": states}

        collector.check(
            "DATA-GLOBAL-003",
            source_probes,
            pass_message="외부 원천 읽기 전용 probe 응답 형식을 확인했습니다.",
        )

        def market_feed_contract() -> dict[str, Any]:
            payload, meta = api.get(
                "/market/quant-signals", universe_limit=100, limit=100, recent_days=30
            )
            _assert(
                isinstance(payload, dict), "시장 시그널 응답이 객체가 아닙니다.", **meta
            )
            _assert(
                payload.get("strategy_version") == catalog["strategy_version"],
                "시장 시그널 전략 버전이 다릅니다.",
                strategy_version=payload.get("strategy_version"),
            )
            status = str(payload.get("status") or "")
            _assert(
                status not in {"preparing", "unavailable", "error"},
                f"시장 시그널 상태가 {status}입니다.",
                **meta,
            )
            signal_revision = payload.get("signal_revision")
            _assert(
                isinstance(signal_revision, int)
                and not isinstance(signal_revision, bool)
                and signal_revision >= 0,
                "시장 시그널 signal_revision이 음이 아닌 정수가 아닙니다.",
                signal_revision=signal_revision,
            )
            signal_revision_as_of = _stream_timestamp(
                payload.get("signal_revision_as_of"),
                "market-signals.signal_revision_as_of",
            )
            _assert(
                payload.get("signal_revision_scope") == "canonical_market_feed",
                "시장 시그널 리비전 scope가 canonical market feed가 아닙니다.",
                signal_revision_scope=payload.get("signal_revision_scope"),
            )
            items = payload.get("items") or []
            _assert(isinstance(items, list), "시장 시그널 items가 배열이 아닙니다.")
            keys = [
                (item.get("code"), item.get("signal_date"), item.get("action"))
                for item in items
                if isinstance(item, dict)
            ]
            _assert(
                len(keys) == len(set(keys)),
                "동일 종목·날짜·상태 시그널이 중복됐습니다.",
            )
            pending_leaks = []
            for item in items:
                if not isinstance(item, dict) or item.get("action") not in {
                    "entry_watch",
                    "entry_pending",
                }:
                    continue
                for key in ("entry_price", "target_sell_price", "return_rate"):
                    if item.get(key) is not None:
                        pending_leaks.append(f"{item.get('code')}:{key}")
            _assert(
                not pending_leaks,
                "예비 시그널에 거래정보가 노출됐습니다.",
                leaks=pending_leaks,
            )
            context["market_signals"] = payload
            return {
                **meta,
                "status": status,
                "count": len(items),
                "as_of": payload.get("as_of"),
                "snapshot_state": payload.get("snapshot_state"),
                "signal_revision": signal_revision,
                "signal_revision_as_of": signal_revision_as_of.isoformat(),
                "signal_revision_scope": payload.get("signal_revision_scope"),
            }

        collector.check(
            "SIG-VERSION-002",
            market_feed_contract,
            pass_message="시장 시그널 버전·상태·중복·예비정보 계약을 확인했습니다.",
        )
        if context.get("market_signals"):
            collector.check(
                "SIG-LIFECYCLE-003",
                market_feed_contract,
                pass_message="동일 날짜 중복 시그널이 없음을 확인했습니다.",
            )
            collector.check(
                "SIG-CONTRACT-001",
                market_feed_contract,
                pass_message="예비 시그널 거래정보 비노출을 확인했습니다.",
            )

            def recommendation_eligibility_contract() -> dict[str, Any]:
                recommendations, meta = api.get(
                    "/market/recommendations",
                    limit=20,
                    candidate_limit=100,
                )
                _assert(
                    isinstance(recommendations, dict),
                    "종목 추천 응답이 객체가 아닙니다.",
                    **meta,
                )
                _assert(
                    recommendations.get("selection_rule")
                    == "recommendation_score_ranked_independent_of_trade_signal",
                    "종목 추천이 추천 점수와 AI 시그널을 분리하지 않았습니다.",
                    selection_rule=recommendations.get("selection_rule"),
                )
                items = recommendations.get("items") or []
                _assert(isinstance(items, list), "종목 추천 items가 배열이 아닙니다.")
                recommendation_date = str(recommendations.get("as_of") or "")[:10]
                invalid: list[dict[str, Any]] = []
                state_counts = {"entry_confirmed": 0, "entered_today": 0, "holding": 0}
                signal_actions: set[str] = set()
                for item in items:
                    if not isinstance(item, dict):
                        invalid.append({"item": "not_object"})
                        continue
                    signal = item.get("ai_trade_signal")
                    current = (
                        signal.get("current")
                        if isinstance(signal, dict)
                        and isinstance(signal.get("current"), dict)
                        else {}
                    )
                    state = str(item.get("recommendation_state") or "")
                    signal_action = str(current.get("action") or "")
                    if signal_action:
                        signal_actions.add(signal_action)
                    lifecycle = current.get("lifecycle")
                    transition = (
                        lifecycle.get("latest_transition")
                        if isinstance(lifecycle, dict)
                        and isinstance(lifecycle.get("latest_transition"), dict)
                        else {}
                    )
                    confirmation = current.get("entry_confirmation")
                    pending_valid = bool(
                        state == "entry_confirmed"
                        and current.get("action") == "entry_pending"
                        and current.get("position_open") is False
                    )
                    entered_today_valid = bool(
                        state == "entered_today"
                        and current.get("action") in {"entered", "holding"}
                        and current.get("position_open") is True
                        and str(current.get("entry_date") or "")[:10] == recommendation_date
                        and str(transition.get("transition_date") or "")[:10]
                        == recommendation_date
                        and str(transition.get("side") or "").lower() == "buy"
                        # The public recommendation projection deliberately
                        # redacts the internal entry-confirmation evidence.
                        # Eligibility was already derived before projection;
                        # verify that derived contract and the redaction here.
                        and confirmation is None
                        and item.get("strategy_entry_price") == current.get("entry_price")
                    )
                    holding_valid = bool(
                        state == "holding"
                        and current.get("action") in {"entered", "holding"}
                        and current.get("position_open") is True
                        and bool(str(current.get("entry_date") or "")[:10])
                        and bool(str(transition.get("transition_date") or "")[:10])
                        and str(transition.get("side") or "").lower() == "buy"
                        and confirmation is None
                        and item.get("strategy_entry_price") == current.get("entry_price")
                    )
                    score_selected_valid = state == "score_selected"
                    recommendation_score_is_independent = bool(
                        item.get("action")
                        and item.get("action") == item.get("score_action")
                        and item.get("recommendation_label") == "추천 후보"
                    )
                    if (
                        item.get("buy_condition_met") is not True
                        or not recommendation_score_is_independent
                        or not (
                            score_selected_valid
                            or pending_valid
                            or entered_today_valid
                            or holding_valid
                        )
                    ):
                        invalid.append(
                            {
                                "code": item.get("code"),
                                "action": item.get("action"),
                                "score_action": item.get("score_action"),
                                "recommendation_state": item.get("recommendation_state"),
                                "recommendation_label": item.get("recommendation_label"),
                                "buy_condition_met": item.get("buy_condition_met"),
                                "signal_action": current.get("action"),
                                "position_open": current.get("position_open"),
                                "live_observation": current.get("live_observation"),
                                "entry_date": current.get("entry_date"),
                                "entry_confirmation_redacted": confirmation is None,
                                "strategy_entry_price": item.get("strategy_entry_price"),
                                "current_entry_price": current.get("entry_price"),
                                "transition": transition,
                            }
                        )
                    elif state in state_counts:
                        state_counts[state] += 1
                _assert(
                    not invalid,
                    "추천 점수 순위가 AI 시그널 행동으로 덮였거나 현재 AI 상태가 일관되지 않습니다.",
                    invalid=invalid,
                )
                expected_ranks = list(range(1, len(items) + 1))
                ranks = [item.get("rank") for item in items if isinstance(item, dict)]
                _assert(
                    ranks == expected_ranks,
                    "추천 점수 후보의 순위가 연속적이지 않습니다.",
                    ranks=ranks,
                )
                qualified_count = int(recommendations.get("qualified_count") or 0)
                candidate_count = int(recommendations.get("candidate_count") or 0)
                _assert(
                    candidate_count >= qualified_count >= len(items),
                    "추천 후보·점수 계산·반환 건수의 관계가 올바르지 않습니다.",
                    candidate_count=candidate_count,
                    qualified_count=qualified_count,
                    returned_count=len(items),
                )
                _assert(
                    len(items) == min(20, qualified_count),
                    "AI 시그널 상태 때문에 점수 추천 후보가 누락됐습니다.",
                    expected_returned=min(20, qualified_count),
                    returned_count=len(items),
                )
                _assert(
                    int(recommendations.get("pending_count") or 0)
                    == state_counts["entry_confirmed"],
                    "추천 응답의 진입 대기 상태 수가 반환 항목과 다릅니다.",
                    pending_count=recommendations.get("pending_count"),
                    returned_pending=state_counts["entry_confirmed"],
                )
                _assert(
                    int(recommendations.get("entered_today_count") or 0)
                    == state_counts["entered_today"],
                    "추천 응답의 오늘 진입 상태 수가 반환 항목과 다릅니다.",
                    entered_today_count=recommendations.get("entered_today_count"),
                    returned_entered_today=state_counts["entered_today"],
                )
                _assert(
                    int(recommendations.get("holding_count") or 0)
                    == state_counts["holding"],
                    "추천 응답의 현재 보유 상태 수가 반환 항목과 다릅니다.",
                    holding_count=recommendations.get("holding_count"),
                    returned_holding=state_counts["holding"],
                )
                return {
                    **meta,
                    "selection_rule": recommendations.get("selection_rule"),
                    "candidate_count": candidate_count,
                    "qualified_count": qualified_count,
                    "pending_count": recommendations.get("pending_count"),
                    "entered_today_count": recommendations.get("entered_today_count"),
                    "holding_count": recommendations.get("holding_count"),
                    "returned_count": len(items),
                    "signal_actions": sorted(signal_actions),
                    "codes": [item.get("code") for item in items if isinstance(item, dict)],
                }

            collector.check(
                "SIG-CONTRACT-002",
                recommendation_eligibility_contract,
                pass_message="추천 점수 순위와 현재 AI 시그널이 독립적으로 유지됨을 확인했습니다.",
            )

            def signal_surface_contract() -> dict[str, Any]:
                payload = context["market_signals"]
                preliminary_mismatches: list[dict[str, Any]] = []
                return_mismatches: list[dict[str, Any]] = []
                checked_preliminary = 0
                checked_open_positions = 0
                checked_closed_trades = 0
                for item in payload.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    current = item.get("current") if isinstance(item.get("current"), dict) else {}
                    action = str(current.get("action") or item.get("action") or "")
                    preliminary = bool(
                        item.get("is_preliminary")
                        or item.get("status") == "preliminary"
                        or action
                        in {
                            "entry_watch",
                            "entry_pending",
                            "partial_exit_pending",
                            "full_exit_pending",
                        }
                    )
                    if preliminary:
                        checked_preliminary += 1
                        signal_date = str(item.get("signal_date") or "")[:10]
                        signal_at_date = str(item.get("signal_at") or "")[:10]
                        if (
                            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", signal_date)
                            or signal_at_date != signal_date
                        ):
                            preliminary_mismatches.append(
                                {
                                    "code": item.get("code"),
                                    "action": action,
                                    "signal_date": item.get("signal_date"),
                                    "signal_at": item.get("signal_at"),
                                    "current_as_of": current.get("as_of"),
                                    "live_observation": current.get("live_observation"),
                                }
                            )

                    holding = bool(
                        item.get("is_current_holding")
                        or current.get("position_open") is True
                    )
                    return_kind = str(item.get("display_return_kind") or "")
                    display_return = item.get("display_return_rate")
                    if holding:
                        checked_open_positions += 1
                        holding_context = (
                            item.get("holding_context")
                            if isinstance(item.get("holding_context"), dict)
                            else {}
                        )
                        return_basis = (
                            holding_context.get("return_basis")
                            if isinstance(holding_context.get("return_basis"), dict)
                            else current.get("return_basis")
                            if isinstance(current.get("return_basis"), dict)
                            else {}
                        )
                        basis_fields_ok = all(
                            _finite_number(return_basis.get(key)) is not None
                            for key in ("price", "return_rate", "return_rate_per_price")
                        )
                        if (
                            return_kind != "open_position"
                            or _finite_number(display_return) is None
                            or not basis_fields_ok
                        ):
                            return_mismatches.append(
                                {
                                    "code": item.get("code"),
                                    "state": "open_position",
                                    "display_return_kind": item.get("display_return_kind"),
                                    "display_return_rate": display_return,
                                    "return_basis": return_basis,
                                }
                            )
                    elif return_kind == "closed_trade":
                        checked_closed_trades += 1
                        recorded_return = item.get("return_rate")
                        display_number = _finite_number(display_return)
                        recorded_number = _finite_number(recorded_return)
                        same_return = display_number is not None and (
                            recorded_return is None
                            or (
                                recorded_number is not None
                                and abs(display_number - recorded_number) < 1e-9
                            )
                        )
                        if item.get("live_return_rate") is not None or not same_return:
                            return_mismatches.append(
                                {
                                    "code": item.get("code"),
                                    "state": "closed_trade",
                                    "display_return_rate": display_return,
                                    "return_rate": recorded_return,
                                    "live_return_rate": item.get("live_return_rate"),
                                }
                            )
                _assert(
                    not preliminary_mismatches,
                    "예비 시그널의 장 기준일과 발생 시각이 어긋났습니다.",
                    mismatches=preliminary_mismatches,
                )
                _assert(
                    not return_mismatches,
                    "열린 포지션 실시간 수익률 또는 완료 매매 고정 수익률 계약이 어긋났습니다.",
                    mismatches=return_mismatches,
                )
                return {
                    "checked_preliminary_signals": checked_preliminary,
                    "checked_open_positions": checked_open_positions,
                    "checked_closed_trades": checked_closed_trades,
                    "preliminary_mismatches": preliminary_mismatches,
                    "return_mismatches": return_mismatches,
                }

            collector.check(
                "SIG-CONTRACT-003",
                signal_surface_contract,
                pass_message="예비 장 기준일·열린 포지션 수익률·완료 매매 고정 손익 계약을 확인했습니다.",
            )

            def recent_signal_window_contract() -> dict[str, Any]:
                payload = context["market_signals"]
                reference_raw = str(payload.get("as_of") or "")
                try:
                    reference_date = datetime.fromisoformat(
                        reference_raw.replace("Z", "+00:00")
                    ).astimezone(KST).date()
                except ValueError:
                    raise QaFailure(
                        "시장 시그널 기준 시각을 해석할 수 없습니다.",
                        {"as_of": reference_raw},
                    ) from None
                recent_days = int(payload.get("recent_days") or 30)
                cutoff = reference_date - timedelta(days=recent_days)
                stale: list[dict[str, Any]] = []
                future: list[dict[str, Any]] = []
                checked = 0
                holding_exceptions = 0
                for item in payload.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    current = item.get("current") or {}
                    holding = bool(
                        item.get("is_current_holding")
                        or (isinstance(current, dict) and current.get("position_open"))
                    )
                    preliminary = bool(
                        item.get("is_preliminary")
                        or item.get("status") == "preliminary"
                        or item.get("action") in {"entry_watch", "entry_pending"}
                    )
                    raw_date = (
                        item.get("signal_date")
                        if preliminary
                        else item.get("execution_date") or item.get("signal_date")
                    )
                    if not raw_date:
                        continue
                    try:
                        candidate = date.fromisoformat(str(raw_date)[:10])
                    except ValueError:
                        raise QaFailure(
                            "시장 시그널 날짜를 해석할 수 없습니다.",
                            {"code": item.get("code"), "date": raw_date},
                        ) from None
                    checked += 1
                    if candidate > reference_date:
                        future.append({"code": item.get("code"), "date": str(raw_date)})
                    elif candidate < cutoff:
                        if holding:
                            holding_exceptions += 1
                        else:
                            stale.append({"code": item.get("code"), "date": str(raw_date)})
                _assert(
                    not future,
                    "미래 날짜 시장 시그널이 노출됐습니다.",
                    future=future,
                    reference_date=reference_date,
                )
                _assert(
                    not stale,
                    "최근 30일 범위를 벗어난 비보유 시그널이 노출됐습니다.",
                    stale=stale,
                    cutoff=cutoff,
                )
                return {
                    "recent_days": recent_days,
                    "reference_date": reference_date,
                    "cutoff": cutoff,
                    "checked": checked,
                    "holding_exceptions": holding_exceptions,
                }

            collector.check(
                "SIG-CONTRACT-004",
                recent_signal_window_contract,
                pass_message="최근 30일 시그널 경계와 장기 보유 예외를 확인했습니다.",
            )

        def representative_contract() -> dict[str, Any]:
            stock, stock_meta = api.get("/stocks/005930")
            dashboard, dashboard_meta = api.get(
                "/stocks/005930/dashboard",
                include_profile="false",
                include_live="false",
            )
            quote, quote_meta = api.get("/stocks/005930/quote")
            intraday, intraday_meta = api.get("/stocks/005930/intraday")
            signal, signal_meta = api.get("/stocks/005930/quant-signals")
            _assert(
                stock.get("code") == "005930", "대표 종목 코드가 일치하지 않습니다."
            )
            _assert(
                isinstance(dashboard, dict)
                and isinstance(quote, dict)
                and isinstance(signal, dict),
                "대표 종목 API 형식이 잘못됐습니다.",
            )
            points = intraday.get("points") if isinstance(intraday, dict) else intraday
            _assert(isinstance(points, list), "분봉 points가 배열이 아닙니다.")
            _assert(
                signal.get("strategy_version") == catalog["strategy_version"],
                "상세 시그널 버전이 다릅니다.",
            )
            context["quote"] = quote
            context["signal"] = signal
            return {
                "stock": {
                    "code": stock.get("code"),
                    "name": stock.get("name"),
                    "market": stock.get("market"),
                },
                "dashboard_http": dashboard_meta["http_status"],
                "quote_http": quote_meta["http_status"],
                "intraday_points": len(points),
                "signal_action": (signal.get("current") or {}).get("action")
                or signal.get("action"),
                "signal_as_of": signal.get("as_of"),
                "latency_ms": {
                    "stock": stock_meta["latency_ms"],
                    "dashboard": dashboard_meta["latency_ms"],
                    "quote": quote_meta["latency_ms"],
                    "intraday": intraday_meta["latency_ms"],
                    "signal": signal_meta["latency_ms"],
                },
            }

        collector.check(
            "DATA-KIS-002",
            representative_contract,
            pass_message="대표 종목 현재가·분봉·신호 API 계약을 확인했습니다.",
        )
        if context.get("signal"):
            collector.check(
                "SIG-INPUT-003",
                representative_contract,
                pass_message="대표 종목의 저장 일봉·실시간 시세 격리 계약을 확인했습니다.",
            )

        endpoint_cases = (
            ("DATA-KIS-003", "/market/indices", {"limit": 5}),
            (
                "DATA-KRX-NAVER-004",
                "/market/rankings",
                {"category": "market_cap", "limit": 15},
            ),
            (
                "DATA-FUND-RESEARCH-003",
                "/research-reports",
                {"stock_code": "005930", "limit": 5},
            ),
            ("DATA-DART-003", "/disclosures", {"stock_code": "005930", "limit": 5}),
            ("DATA-GLOBAL-002", "/market/global-assets", {"limit": 5}),
            ("DATA-CALENDAR-CONTENT-001", "/market/trends", {"days": 7}),
            ("DATA-CALENDAR-CONTENT-002", "/news-items", {"limit": 5}),
            ("DATA-CALENDAR-CONTENT-004", "/market/calendar", {"days": 14}),
            ("DATA-CALENDAR-CONTENT-005", "/briefings/morning-money", {}),
            ("DATA-ETF-001", "/stocks/069500/etf-profile", {}),
            (
                "DATA-FUND-ANALYSIS-001",
                "/stocks/005930/sector-operating-margins",
                {"limit": 5},
            ),
            ("DATA-FUND-ANALYSIS-002", "/stocks/000660/sga-analysis", {}),
        )
        for case_id, path, params in endpoint_cases:

            def endpoint_contract(
                path: str = path, params: dict[str, Any] = params
            ) -> dict[str, Any]:
                payload, meta = api.get(path, **params)
                _assert(payload is not None, f"{path} 응답이 비어 있습니다.", **meta)
                size = (
                    len(payload)
                    if isinstance(payload, list)
                    else len(payload.get("items") or [])
                    if isinstance(payload, dict)
                    else None
                )
                return {**meta, "item_count": size}

            collector.check(
                case_id,
                endpoint_contract,
                pass_message=f"{path} 읽기 전용 연동 계약을 확인했습니다.",
            )

        def us_contract() -> dict[str, Any]:
            payload, meta = api.get("/us/stocks/AAPL/dashboard")
            _assert(
                isinstance(payload, dict),
                "미국 대표 종목 API 형식이 잘못됐습니다.",
                **meta,
            )
            return {
                **meta,
                "symbol": payload.get("symbol") or payload.get("code"),
                "as_of": payload.get("as_of"),
            }

        collector.check(
            "DATA-GLOBAL-002",
            us_contract,
            pass_message="미국 대표 종목 데이터 계약을 확인했습니다.",
        )

        def watch_market_map_data_contract() -> dict[str, Any]:
            domestic, domestic_meta = api.get(
                "/stocks/005930/dashboard",
                include_profile="false",
                include_live="false",
            )
            overseas, overseas_meta = api.get("/us/stocks/NVDA/dashboard")
            domestic_intraday, domestic_intraday_meta = api.get(
                "/stocks/005930/intraday",
                limit="390",
            )
            domestic_intraday_attempts = 1
            initial_domestic_intraday_source = domestic_intraday.get("source")
            # A just-deployed web instance can briefly return a structured
            # KIS unavailable response before its closed-session chart is
            # fetched. Retry only that source condition; persistent absence
            # remains a P0 failure with the attempt count in evidence.
            while (
                domestic_intraday.get("source") == "unavailable"
                and not domestic_intraday.get("points")
                and domestic_intraday_attempts < 31
            ):
                sleep(10)
                domestic_intraday, domestic_intraday_meta = api.get(
                    "/stocks/005930/intraday", limit="390"
                )
                domestic_intraday_attempts += 1
            overseas_intraday, overseas_intraday_meta = api.get(
                "/us/stocks/NVDA/intraday",
                range="1d",
                interval="1m",
            )

            def positive_number(value: Any) -> float | None:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    return None
                return number if number > 0 else None

            domestic_cap = positive_number(
                (domestic.get("quote") or {}).get("market_cap")
                or domestic.get("market_cap")
            )
            overseas_cap = positive_number(
                (overseas.get("quote") or {}).get("market_cap")
                or overseas.get("market_cap")
            )
            _assert(
                domestic_cap is not None,
                "관심종목 버블맵에 필요한 국내 시가총액이 없습니다.",
                **domestic_meta,
            )
            _assert(
                overseas_cap is not None,
                "관심종목 버블맵에 필요한 미국 시가총액이 없습니다.",
                **overseas_meta,
            )
            for label, payload, meta in (
                ("국내", domestic_intraday, domestic_intraday_meta),
                ("미국", overseas_intraday, overseas_intraday_meta),
            ):
                points = payload.get("points")
                _assert(
                    isinstance(points, list) and bool(points),
                    f"관심종목 시간 스크러빙에 필요한 {label} 분봉이 없습니다.",
                    source=payload.get("source"),
                    attempts=domestic_intraday_attempts if label == "국내" else 1,
                    initial_source=(
                        initial_domestic_intraday_source if label == "국내" else payload.get("source")
                    ),
                    **meta,
                )
                sample = points[-1]
                _assert(
                    bool(sample.get("trade_time")) and positive_number(sample.get("price")) is not None,
                    f"{label} 분봉의 시각·가격 계약이 불완전합니다.",
                    sample=sample,
                    **meta,
                )
            _assert(
                positive_number(overseas_intraday.get("reference_price")) is not None,
                "미국 관심종목 분봉의 전일 기준가가 없습니다.",
                **overseas_intraday_meta,
            )
            return {
                "domestic": {
                    **domestic_meta,
                    "code": domestic.get("code") or "005930",
                    "market_scope": "kr",
                    "market_cap_krw": domestic_cap,
                },
                "overseas": {
                    **overseas_meta,
                    "code": overseas.get("symbol") or overseas.get("code") or "NVDA",
                    "market_scope": "us",
                    "market_cap_usd": overseas_cap,
                },
                "intraday": {
                    "domestic": {
                        **domestic_intraday_meta,
                        "points": len(domestic_intraday.get("points") or []),
                        "trade_date": domestic_intraday.get("trade_date"),
                        "attempts": domestic_intraday_attempts,
                        "initial_source": initial_domestic_intraday_source,
                    },
                    "overseas": {
                        **overseas_intraday_meta,
                        "points": len(overseas_intraday.get("points") or []),
                        "trade_date": overseas_intraday.get("trade_date"),
                        "reference_price": overseas_intraday.get("reference_price"),
                    },
                },
            }

        collector.check(
            "SIG-UI-025",
            watch_market_map_data_contract,
            pass_message="관심종목 버블맵의 국내·미국 분리 시총·분봉 스크러빙 입력을 확인했습니다.",
        )

        def domestic_community_latest_contract() -> dict[str, Any]:
            payload, meta = api.get(
                "/stocks/005930/community-feed",
                limit=5,
                mode="latest",
            )
            providers = payload.get("providers") if isinstance(payload, dict) else None
            _assert(
                isinstance(providers, list),
                "국내 커뮤니티 공급자 응답이 배열이 아닙니다.",
                **meta,
            )
            provider = next(
                (
                    item
                    for item in providers
                    if isinstance(item, dict) and item.get("key") == "naver_board"
                ),
                None,
            )
            items = provider.get("items") if isinstance(provider, dict) else None
            _assert(
                isinstance(items, list) and items,
                "삼성전자 최신 커뮤니티 글이 비어 있습니다.",
                provider_configured=(
                    provider.get("configured") if isinstance(provider, dict) else None
                ),
                provider_message=(
                    provider.get("message") if isinstance(provider, dict) else None
                ),
                **meta,
            )
            first = items[0] if isinstance(items[0], dict) else {}
            _assert(
                bool(first.get("post_id"))
                and bool(first.get("title"))
                and bool(first.get("author_name"))
                and str(first.get("url") or "").startswith(
                    "https://m.stock.naver.com/domestic/stock/005930/discussion/"
                ),
                "국내 커뮤니티 최신글 필드 또는 원문 링크가 잘못됐습니다.",
                post_id=first.get("post_id"),
                has_title=bool(first.get("title")),
                has_author=bool(first.get("author_name")),
                url=first.get("url"),
                **meta,
            )
            us_payload, us_meta = api.get(
                "/us/stocks/WMB/community-feed",
                limit=5,
                mode="latest",
            )
            us_providers = (
                us_payload.get("providers") if isinstance(us_payload, dict) else None
            )
            us_provider = next(
                (
                    item
                    for item in us_providers or []
                    if isinstance(item, dict) and item.get("key") == "naver_board"
                ),
                None,
            )
            us_items = (
                us_provider.get("items") if isinstance(us_provider, dict) else None
            )
            _assert(
                isinstance(us_items, list) and us_items,
                "WMB 미국 커뮤니티 글이 bare ticker 폴백 뒤에도 비어 있습니다.",
                provider_configured=(
                    us_provider.get("configured")
                    if isinstance(us_provider, dict)
                    else None
                ),
                provider_message=(
                    us_provider.get("message")
                    if isinstance(us_provider, dict)
                    else None
                ),
                **us_meta,
            )
            us_first = us_items[0] if isinstance(us_items[0], dict) else {}
            _assert(
                bool(us_first.get("post_id"))
                and bool(us_first.get("title"))
                and bool(us_first.get("author_name"))
                and str(us_first.get("url") or "").startswith(
                    "https://m.stock.naver.com/worldstock/stock/WMB/discussion/"
                ),
                "WMB 커뮤니티 최신글 필드 또는 bare ticker 원문 링크가 잘못됐습니다.",
                post_id=us_first.get("post_id"),
                has_title=bool(us_first.get("title")),
                has_author=bool(us_first.get("author_name")),
                url=us_first.get("url"),
                **us_meta,
            )
            return {
                **meta,
                "provider": provider.get("source"),
                "provider_configured": provider.get("configured"),
                "item_count": len(items),
                "first_post_id": first.get("post_id"),
                "first_post_url": first.get("url"),
                "domestic": {
                    **meta,
                    "provider": provider.get("source"),
                    "provider_configured": provider.get("configured"),
                    "item_count": len(items),
                    "first_post_id": first.get("post_id"),
                    "first_post_url": first.get("url"),
                },
                "us": {
                    **us_meta,
                    "provider": us_provider.get("source"),
                    "provider_configured": us_provider.get("configured"),
                    "item_count": len(us_items),
                    "first_post_id": us_first.get("post_id"),
                    "first_post_url": us_first.get("url"),
                },
            }

        collector.check(
            "SIG-UI-026",
            domestic_community_latest_contract,
            pass_message="삼성전자·WMB 최신 커뮤니티 글과 모바일 원문 링크를 확인했습니다.",
        )

        def realtime_status_contract() -> dict[str, Any]:
            payload, meta = api.get("/realtime/status")
            channels = payload.get("public_quote_channels") or {}
            unique_codes = int(channels.get("unique_codes") or 0)
            kis_realtime_codes = int(channels.get("kis_realtime_codes") or 0)
            fallback_codes = int(channels.get("fallback_codes") or 0)
            session_codes = int(channels.get("kis_session_codes") or 0)
            _assert(
                int(channels.get("max_codes_per_client") or 0) > 0,
                "실시간 구독 제한값이 없습니다.",
                **meta,
            )
            _assert(
                0 <= kis_realtime_codes <= 40,
                "KIS 실시간 종목 수가 40개 안전 상한을 벗어났습니다.",
                kis_realtime_codes=kis_realtime_codes,
            )
            _assert(
                fallback_codes >= 0
                and kis_realtime_codes + fallback_codes == unique_codes,
                "실시간·REST 폴백 종목 수가 전체 구독 종목 수와 다릅니다.",
                unique_codes=unique_codes,
                kis_realtime_codes=kis_realtime_codes,
                fallback_codes=fallback_codes,
            )
            _assert(
                session_codes >= kis_realtime_codes
                and isinstance(channels.get("idle_grace_active"), bool)
                and int(channels.get("idle_grace_seconds") or 0) > 0
                and int(channels.get("contention_backoff_seconds") or 0) > 0,
                "KIS 단일 세션 idle grace 상태 계약이 잘못됐습니다.",
                session_codes=session_codes,
                idle_grace_active=channels.get("idle_grace_active"),
                idle_grace_seconds=channels.get("idle_grace_seconds"),
                contention_backoff_seconds=channels.get(
                    "contention_backoff_seconds"
                ),
            )
            _assert(
                isinstance(channels.get("min_broadcast_interval_ms"), int)
                and not isinstance(channels.get("min_broadcast_interval_ms"), bool)
                and int(channels["min_broadcast_interval_ms"]) >= 0,
                "실시간 시세 방송 최소 간격이 잘못됐습니다.",
                min_broadcast_interval_ms=channels.get("min_broadcast_interval_ms"),
            )
            return {
                **meta,
                "public_quote_channels": channels,
                "connections": payload.get("connections"),
            }

        collector.check(
            "DATA-KIS-006",
            realtime_status_contract,
            pass_message="실시간 구독 제한과 REST 폴백 상태를 확인했습니다.",
        )

        _public_websocket_check(
            collector,
            base_url,
            timeout,
            expected_signal_revision=(context.get("market_signals") or {}).get(
                "signal_revision"
            ),
        )
        if direct_kis:
            _direct_kis_checks(collector)
        else:
            for case_id in ("DATA-KIS-001", "DATA-KIS-004", "DATA-KIS-007"):
                collector.add(
                    case_id,
                    "skip",
                    "--direct-kis 옵션이 없어 KIS 원천 직접 호출을 생략했습니다.",
                    evidence={"direct_kis": False},
                )
    finally:
        api.close()

    return _market_state(context.get("quote"), context.get("quality")), context


def _live_us_gateway_checks(
    collector: ResultCollector,
    *,
    base_url: str,
    timeout: float,
) -> None:
    api = ReadOnlyApi(base_url, timeout)
    try:
        def contract() -> dict[str, Any]:
            shell, shell_meta = api.get_text("/us", view="home")
            version, version_meta = api.get("/us-version")
            bridge, bridge_meta = api.get_text("/us-gateway/assets/us-public-bridge.js")
            signal, signal_meta = api.get("/us/market/quant-signals", limit=1)
            for meta in (shell_meta, version_meta, bridge_meta, signal_meta):
                _assert(
                    meta.get("us_market_route") == "dedicated-service",
                    "미국 공개 경로의 일부가 독립 서비스를 우회합니다.",
                    request=meta,
                )
            _assert(
                '<meta name="secret-note-market-universe" content="us"' in shell
                and '/us-gateway/dashboard-app-v170.js' in shell
                and '/us-gateway/assets/dashboard/styles.css' in shell
                and 'window.__US_PUBLIC_GATEWAY__ = prefix;' in bridge
                and bool(version.get("version"))
                and isinstance(signal, dict),
                "미국 공개 셸·자산·API 경계가 불완전합니다.",
                shell=shell_meta, version=version_meta, bridge=bridge_meta, signal=signal_meta,
            )
            return {"shell": shell_meta, "version": version_meta, "bridge": bridge_meta, "signal": signal_meta}

        collector.check(
            "DATA-COM-006",
            contract,
            pass_message="공식 /us 주소가 미국 전용 셸·자산·API로 전달됩니다.",
        )
    finally:
        api.close()


def _live_us_checks(
    collector: ResultCollector,
    catalog: dict[str, Any],
    *,
    base_url: str,
    timeout: float,
) -> tuple[str | None, dict[str, Any]]:
    api = ReadOnlyApi(base_url, timeout)
    context: dict[str, Any] = {}
    try:

        def health_contract() -> dict[str, Any]:
            health, health_meta = api.get("/health")
            ready, ready_meta = api.get("/readyz")
            _assert(
                health.get("status") == "ok"
                and ready.get("status") == "ok"
                and ready.get("database_ok") is True,
                "미국 서비스 health 또는 readyz가 준비되지 않았습니다.",
                health=health_meta,
                readyz=ready_meta,
            )
            _assert(
                health.get("us_market_enabled") is True
                and ready.get("us_market_enabled") is True,
                "미국 서비스의 US_MARKET_ENABLED가 true가 아닙니다.",
                health_enabled=health.get("us_market_enabled"),
                ready_enabled=ready.get("us_market_enabled"),
            )
            _assert(
                health.get("us_strategy_version")
                == catalog.get("us_strategy_version")
                and ready.get("us_strategy_version")
                == catalog.get("us_strategy_version"),
                "미국 서비스 전략 버전이 카탈로그와 다릅니다.",
                health_version=health.get("us_strategy_version"),
                ready_version=ready.get("us_strategy_version"),
            )
            _assert(
                bool(health.get("us_dashboard_version"))
                and health.get("us_dashboard_version")
                == ready.get("us_dashboard_version"),
                "미국 제품 빌드 버전이 health와 readyz에서 일치하지 않습니다.",
                health_version=health.get("us_dashboard_version"),
                ready_version=ready.get("us_dashboard_version"),
            )
            context["health"] = health
            return {
                "health": health_meta,
                "readyz": ready_meta,
                "us_market_enabled": True,
                "us_strategy_version": health.get("us_strategy_version"),
                "us_dashboard_version": health.get("us_dashboard_version"),
            }

        collector.check(
            "DATA-COM-002",
            health_contract,
            pass_message="미국 서비스 헬스·준비 상태와 기능 플래그를 확인했습니다.",
        )

        def us_product_boundary_contract() -> dict[str, Any]:
            shell, shell_meta = api.get_text("/us", view="home")
            domestic_shell, domestic_shell_meta = api.get_text("/dashboard", view="home")
            source, source_meta = api.get_text("/dashboard-app-v170.js")
            manifest, manifest_meta = api.get("/us.webmanifest")
            version, version_meta = api.get("/us-version")
            assets, assets_meta = api.get("/market/global-assets", limit=30)
            search, search_meta = api.get("/us/stocks/search", query="AAPL", limit=5)
            _assert(
                '<html lang="ko" data-market-universe="us">' in shell
                and '<meta name="secret-note-market-universe" content="us" />'
                in shell
                and "비밀노트 | 미국증시" in shell,
                "스테이징 /us가 미국증시 제품 계약을 제공하지 않습니다.",
                **shell_meta,
            )
            _assert(
                re.findall(r'\bid="([^"]+)"', shell)
                == re.findall(r'\bid="([^"]+)"', domestic_shell)
                and 'href="/assets/dashboard/styles.css?' in shell
                and 'src="/dashboard-app-v170.js?' in shell,
                "스테이징 /us가 /dashboard와 같은 화면 구조·공통 자산을 사용하지 않습니다.",
                us_shell=shell_meta,
                dashboard_shell=domestic_shell_meta,
            )
            _assert(
                'const IS_US_ONLY_PRODUCT = PRODUCT_MARKET_UNIVERSE === "us";'
                in source
                and 'const requestedMarketScopeValue = IS_US_ONLY_PRODUCT\n  ? "us"'
                in source
                and 'liveUrl("/market/global-assets?limit=30")' in source
                and 'const PRODUCT_VERSION_ENDPOINT = IS_US_ONLY_PRODUCT ? "/us-version"'
                in source
                and 'document.getElementById("home-ai-response")?.remove();'
                in source
                and 'if (IS_US_ONLY_PRODUCT || state.view !== "home")'
                in source
                and 'id="home-ai-response"' in domestic_shell,
                "공통 대시보드 런타임의 미국 전용 데이터·버전 경계가 고정되지 않았습니다.",
                **source_meta,
            )
            _assert(
                manifest.get("scope") == "/us"
                and manifest.get("start_url") == "/us?view=home"
                and manifest.get("name") == "비밀노트 미국증시",
                "미국 PWA manifest 경계가 잘못됐습니다.",
                manifest=manifest,
            )
            _assert(
                version.get("version")
                == (context.get("health") or {}).get("us_dashboard_version"),
                "미국 버전 endpoint와 health가 일치하지 않습니다.",
                version=version.get("version"),
                health_version=(context.get("health") or {}).get(
                    "us_dashboard_version"
                ),
            )
            codes = {
                str(item.get("code") or "")
                for item in assets.get("items") or []
                if isinstance(item, dict)
            }
            _assert(
                {"SP500", "NASDAQ", "SOX", "DOW"}.issubset(codes),
                "미국 홈 주요 지수 스냅샷이 완전하지 않습니다.",
                codes=sorted(codes),
                **assets_meta,
            )
            _assert(
                isinstance(search, list)
                and any(
                    str(item.get("code") or "").upper() == "AAPL"
                    for item in search
                    if isinstance(item, dict)
                ),
                "미국 종목 검색이 AAPL을 반환하지 않았습니다.",
                **search_meta,
            )
            return {
                "shell": shell_meta,
                "dashboard_shell": domestic_shell_meta,
                "source": source_meta,
                "manifest": manifest_meta,
                "version": version_meta,
                "global_assets": assets_meta,
                "market_codes": sorted(codes),
                "search": search_meta,
                "market_universe": "us",
            }

        collector.check(
            "SIG-UI-031",
            us_product_boundary_contract,
            pass_message="스테이징 /us의 대시보드 화면 동형성·미국 전용 데이터·검색 경계를 확인했습니다.",
        )

        def us_market_news_contract() -> dict[str, Any]:
            payload, payload_meta = api.get(
                "/us/market/trends", days=7, refresh="true"
            )
            _assert(isinstance(payload, dict), "미국 뉴스 응답이 객체가 아닙니다.")
            timeline = payload.get("timeline") or []
            _assert(
                payload.get("status") == "ready"
                and payload.get("data_state") == "live"
                and isinstance(timeline, list)
                and bool(timeline),
                "스테이징 미국 시장 뉴스가 live ready 상태가 아닙니다.",
                status=payload.get("status"),
                data_state=payload.get("data_state"),
                timeline_count=len(timeline) if isinstance(timeline, list) else None,
                **payload_meta,
            )
            current = datetime.now(timezone.utc)
            cutoff = current - timedelta(days=7, minutes=15)
            invalid: list[dict[str, Any]] = []
            seen_urls: set[str] = set()
            seen_titles: set[str] = set()
            for item in timeline:
                if not isinstance(item, dict):
                    invalid.append({"reason": "not_object"})
                    continue
                url = str(item.get("url") or "").strip()
                title = " ".join(str(item.get("title") or "").split()).strip()
                source_name = str(item.get("source") or "").strip()
                parsed_url = urlparse(url)
                try:
                    published_at = datetime.fromisoformat(
                        str(item.get("published_at") or "").replace("Z", "+00:00")
                    )
                    if published_at.tzinfo is None:
                        raise ValueError("timezone missing")
                    published_at = published_at.astimezone(timezone.utc)
                except ValueError:
                    published_at = None
                reasons = []
                if not title:
                    reasons.append("title")
                if not source_name or source_name in {"NASDAQ Brief", "Macro Brief"}:
                    reasons.append("source")
                if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                    reasons.append("url")
                if published_at is None or published_at < cutoff or published_at > current + timedelta(minutes=10):
                    reasons.append("published_at")
                title_key = re.sub(r"\W+", "", title.casefold())
                if url in seen_urls or title_key in seen_titles:
                    reasons.append("duplicate")
                seen_urls.add(url)
                seen_titles.add(title_key)
                if reasons:
                    invalid.append({"title": title[:120], "reasons": reasons})
            _assert(
                not invalid,
                "미국 시장 뉴스에 무효·중복·가짜 최신 기사가 포함됐습니다.",
                invalid=invalid[:10],
                **payload_meta,
            )
            source, source_meta = api.get_text("/dashboard-app-v170.js")
            ia, ia_meta = api.get_text("/assets/staging/toss-ia.js")
            css, css_meta = api.get_text("/assets/staging/toss-fidelity.css")
            _assert(
                'timeZone: "Asia/Seoul"' in source
                and "한국시간" in source
                and 'feedModes.dataset.feedColumns = stagingUsMarketContext ? "2" : "3"'
                in ia
                and '.staging-feed-modes[data-feed-columns="2"]' in css
                and "grid-template-columns: repeat(2, minmax(0, 1fr)) !important"
                in css
                and ".staging-feed-panels" in css
                and "min-height: 0 !important" in css,
                "미국 피드의 한국시간·2열 탭·여백 제거 계약이 배포되지 않았습니다.",
                source=source_meta,
                ia=ia_meta,
                css=css_meta,
            )
            return {
                "feed": payload_meta,
                "article_count": len(timeline),
                "oldest_allowed": cutoff.isoformat(),
                "forbidden_source_count": 0,
                "invalid_article_count": 0,
                "source": source_meta,
                "ia": ia_meta,
                "css": css_meta,
            }

        collector.check(
            "DATA-US-NEWS-001",
            us_market_news_contract,
            pass_message="스테이징 미국 시장 실제 뉴스·한국시간·2열 피드 계약을 확인했습니다.",
        )

        def us_stock_news_identity_contract() -> dict[str, Any]:
            payload, payload_meta = api.get(
                "/us/stocks/WMB/dashboard",
                refresh="true",
            )
            _assert(isinstance(payload, dict), "WMB dashboard 응답이 객체가 아닙니다.")
            sentiment = payload.get("sentiment") or {}
            domestic = sentiment.get("domestic_items") or []
            overseas = sentiment.get("overseas_items") or []
            _assert(
                isinstance(domestic, list) and isinstance(overseas, list),
                "WMB 종목뉴스 국내·해외 목록 계약이 없습니다.",
                **payload_meta,
            )
            current = datetime.now(timezone.utc)
            cutoff = current - timedelta(days=120, minutes=15)
            noise_signals = (
                "보이스3",
                "언오피셜보이",
                "윤병호",
                "hbm4",
                "웨이퍼",
                "모니터",
                "뷰소닉",
                "윌리엄스 타운",
            )

            def parsed_article_time(item: dict[str, Any]) -> datetime | None:
                try:
                    published = datetime.fromisoformat(
                        str(item.get("published_at") or "").replace("Z", "+00:00")
                    )
                except ValueError:
                    return None
                if published.tzinfo is None:
                    published = published.replace(tzinfo=KST)
                return published.astimezone(timezone.utc)

            invalid_domestic: list[dict[str, Any]] = []
            for item in domestic:
                if not isinstance(item, dict):
                    invalid_domestic.append({"reason": "not_object"})
                    continue
                title = " ".join(str(item.get("title") or "").split()).strip()
                lowered = title.casefold()
                published = parsed_article_time(item)
                reasons = []
                if not title or not re.search(r"[가-힣]", title):
                    reasons.append("korean_title")
                if not any(
                    identity in lowered
                    for identity in (
                        "williams companies",
                        "williams cos",
                        "윌리엄스컴퍼니즈",
                        "윌리엄스 컴퍼니즈",
                    )
                ):
                    reasons.append("company_identity")
                if any(signal in lowered for signal in noise_signals):
                    reasons.append("ticker_collision")
                if published is None or published < cutoff or published > current + timedelta(minutes=15):
                    reasons.append("published_at")
                url = urlparse(str(item.get("url") or ""))
                if url.scheme not in {"http", "https"} or not url.netloc:
                    reasons.append("url")
                if reasons:
                    invalid_domestic.append({"title": title[:120], "reasons": reasons})
            _assert(
                not invalid_domestic,
                "WMB 국내뉴스에 무관 약어·오래된 기사·무효 필드가 포함됐습니다.",
                invalid=invalid_domestic[:10],
                domestic_count=len(domestic),
                **payload_meta,
            )

            valid_overseas = []
            for item in overseas:
                if not isinstance(item, dict):
                    continue
                title = " ".join(str(item.get("title") or "").split()).strip()
                lowered = title.casefold()
                published = parsed_article_time(item)
                url = urlparse(str(item.get("url") or ""))
                if (
                    str(item.get("source") or "") == "Yahoo Finance"
                    and ("wmb" in lowered or "williams" in lowered)
                    and published is not None
                    and cutoff <= published <= current + timedelta(minutes=15)
                    and url.scheme in {"http", "https"}
                    and bool(url.netloc)
                ):
                    valid_overseas.append(item)
            _assert(
                bool(valid_overseas),
                "WMB Yahoo Finance 최신 해외뉴스를 확인하지 못했습니다.",
                overseas_count=len(overseas),
                **payload_meta,
            )
            source, source_meta = api.get_text("/dashboard-app-v170.js")
            _assert(
                "stockNewsTabTouched: false" in source
                and "collections.domestic.length === 0" in source
                and "collections.overseas.length > 0" in source
                and "state.stockNewsTabTouched = true" in source,
                "국내뉴스 0건일 때 해외뉴스 초기 선택 또는 사용자 탭 선택 보존 계약이 없습니다.",
                **source_meta,
            )
            return {
                **payload_meta,
                "domestic_count": len(domestic),
                "overseas_count": len(overseas),
                "valid_overseas_count": len(valid_overseas),
                "invalid_domestic_count": 0,
                "oldest_allowed": cutoff.isoformat(),
                "source": source_meta,
            }

        collector.check(
            "DATA-US-NEWS-TABS-001",
            us_stock_news_identity_contract,
            pass_message="WMB 국내 오염 차단·최신 Yahoo 해외뉴스·초기 탭 전환을 확인했습니다.",
        )

        def us_community_bare_symbol_contract() -> dict[str, Any]:
            payload, meta = api.get(
                "/us/stocks/WMB/community-feed",
                limit=5,
                mode="latest",
            )
            providers = payload.get("providers") if isinstance(payload, dict) else None
            provider = next(
                (
                    item
                    for item in providers or []
                    if isinstance(item, dict) and item.get("key") == "naver_board"
                ),
                None,
            )
            items = provider.get("items") if isinstance(provider, dict) else None
            _assert(
                isinstance(items, list) and items,
                "WMB 미국 커뮤니티 글이 bare ticker 폴백 뒤에도 비어 있습니다.",
                provider_configured=(
                    provider.get("configured")
                    if isinstance(provider, dict)
                    else None
                ),
                provider_message=(
                    provider.get("message") if isinstance(provider, dict) else None
                ),
                **meta,
            )
            first = items[0] if isinstance(items[0], dict) else {}
            _assert(
                bool(first.get("post_id"))
                and bool(first.get("title"))
                and bool(first.get("author_name"))
                and str(first.get("url") or "").startswith(
                    "https://m.stock.naver.com/worldstock/stock/WMB/discussion/"
                ),
                "WMB 커뮤니티 최신글 필드 또는 bare ticker 원문 링크가 잘못됐습니다.",
                post_id=first.get("post_id"),
                has_title=bool(first.get("title")),
                has_author=bool(first.get("author_name")),
                url=first.get("url"),
                **meta,
            )
            return {
                **meta,
                "provider": provider.get("source"),
                "provider_configured": provider.get("configured"),
                "item_count": len(items),
                "first_post_id": first.get("post_id"),
                "first_post_url": first.get("url"),
            }

        collector.check(
            "SIG-UI-026",
            us_community_bare_symbol_contract,
            pass_message="WMB bare ticker 커뮤니티 최신글과 원문 링크를 확인했습니다.",
        )

        def us_signal_contract() -> dict[str, Any]:
            cached = context.get("us_market_contract")
            if isinstance(cached, dict):
                return cached
            if context.get("us_market_contract_attempted"):
                raise AssertionError(
                    "미국 시그널 공통 계약이 이미 실패해 동일한 10분 재시도를 생략합니다."
                )
            context["us_market_contract_attempted"] = True
            feed, feed_meta = api.get(
                "/us/market/quant-signals", limit=50, recent_days=30
            )
            recommendations, recommendations_meta = api.get(
                "/us/market/recommendations", limit=20, candidate_limit=100
            )
            stock_analysis, stock_analysis_meta = api.get(
                "/us/stocks/NVDA/ai-analysis"
            )

            def member_evidence_ready() -> bool:
                reasons = stock_analysis.get("public_reasons") or []
                return bool(
                    stock_analysis.get("status") == "ready"
                    and stock_analysis.get("data_state") == "ready"
                    and stock_analysis.get("is_current_universe_member") is True
                    and stock_analysis.get("data_covered") == 3
                    and len(reasons) == 3
                    and all(
                        isinstance(reason, dict)
                        and reason.get("available") is True
                        for reason in reasons
                    )
                )

            evidence_deadline = monotonic() + 600
            while not member_evidence_ready() and monotonic() < evidence_deadline:
                sleep(10)
                feed, feed_meta = api.get(
                    "/us/market/quant-signals", limit=50, recent_days=30
                )
                recommendations, recommendations_meta = api.get(
                    "/us/market/recommendations", limit=20, candidate_limit=100
                )
                stock_analysis, stock_analysis_meta = api.get(
                    "/us/stocks/NVDA/ai-analysis"
                )
            _assert(isinstance(feed, dict), "미국 시그널 응답이 객체가 아닙니다.")
            _assert(
                isinstance(recommendations, dict),
                "미국 추천 응답이 객체가 아닙니다.",
            )
            expected_version = catalog.get("us_strategy_version")
            _assert(
                feed.get("strategy_version") == expected_version
                and recommendations.get("strategy_version") == expected_version,
                "미국 시그널·추천 전략 버전이 RC1과 다릅니다.",
                feed_version=feed.get("strategy_version"),
                recommendation_version=recommendations.get("strategy_version"),
                expected_version=expected_version,
            )
            _assert(
                feed.get("status") == "ready"
                and feed.get("data_state") == "ready"
                and recommendations.get("status") == "ready"
                and recommendations.get("data_state") == "ready",
                "미국 canonical Top100 스냅샷이 ready가 아닙니다.",
                feed_status=feed.get("status"),
                feed_state=feed.get("data_state"),
                recommendation_status=recommendations.get("status"),
                recommendation_state=recommendations.get("data_state"),
            )
            _assert(
                feed.get("rollout_mode") == "model_replay"
                and feed.get("execution_enabled") is False
                and feed.get("stateful_lifecycle_replay_enabled") is True
                and feed.get("reentry_runtime_enabled") is True
                and feed.get("lifecycle_replay_version") == "us-next-open-model-replay-v1"
                and feed.get("stateful_lifecycle_replay_complete") is True,
                "미국 전략 생명주기 모델 replay 계약이 깨졌습니다.",
            )
            universe_count = int(feed.get("universe_count") or 0)
            evaluated_count = int(feed.get("evaluated_count") or 0)
            data_coverage_count = int(feed.get("data_coverage_count") or 0)
            signal_eligible_count = feed.get("signal_eligible_count")
            insufficient_history_count = feed.get("insufficient_history_count")
            coverage = feed.get("coverage") or {}
            _assert(
                universe_count == 100
                and evaluated_count == 100
                and data_coverage_count == 100
                and type(signal_eligible_count) is int
                and type(insufficient_history_count) is int
                and signal_eligible_count + insufficient_history_count == 100
                and isinstance(coverage, dict)
                and coverage.get("complete") is True
                and int(coverage.get("history_error_count") or 0) == 0
                and int(coverage.get("sector_classification_error_count") or 0)
                == 0
                and int(feed.get("sector_classification_error_count") or 0) == 0,
                "미국 Top100 스냅샷의 100/100/100 커버리 계약이 깨졌습니다.",
                universe_count=universe_count,
                evaluated_count=evaluated_count,
                data_coverage_count=data_coverage_count,
                signal_eligible_count=signal_eligible_count,
                insufficient_history_count=insufficient_history_count,
                coverage=coverage,
            )
            _assert(
                feed.get("new_entries_allowed") is True
                and recommendations.get("new_entries_allowed") is True,
                "ready 미국 스냅샷의 신규 진입 허용 상태가 잘못됐습니다.",
                feed_new_entries_allowed=feed.get("new_entries_allowed"),
                recommendation_new_entries_allowed=recommendations.get(
                    "new_entries_allowed"
                ),
            )
            _assert(
                feed.get("snapshot_id")
                and feed.get("snapshot_id") == recommendations.get("snapshot_id")
                and feed.get("snapshot_checksum")
                == recommendations.get("snapshot_checksum"),
                "미국 시그널·추천 canonical identity가 다릅니다.",
                feed_snapshot_id=feed.get("snapshot_id"),
                recommendation_snapshot_id=recommendations.get("snapshot_id"),
            )
            _assert(
                recommendations.get("universe_as_of") == feed.get("universe_as_of")
                and int(recommendations.get("universe_count") or 0)
                == universe_count
                and int(recommendations.get("evaluated_count") or 0)
                == evaluated_count
                and int(recommendations.get("data_coverage_count") or 0)
                == data_coverage_count
                and recommendations.get("signal_eligible_count")
                == signal_eligible_count
                and recommendations.get("insufficient_history_count")
                == insufficient_history_count
                and recommendations.get("baseline_strategy_version")
                == feed.get("baseline_strategy_version")
                and recommendations.get("sector_classification_version")
                == feed.get("sector_classification_version")
                and recommendations.get("stateful_lifecycle_replay_enabled")
                is True
                and recommendations.get("reentry_runtime_enabled") is True
                and recommendations.get("lifecycle_replay_version")
                == "us-next-open-model-replay-v1",
                "미국 추천과 시그널이 다른 canonical 커버리·runtime 계약을 사용합니다.",
            )
            try:
                from app.services.us_market_calendar import (
                    latest_completed_us_market_session,
                )

                expected_universe_as_of = (
                    latest_completed_us_market_session().session_date.isoformat()
                )
            except Exception as exc:
                raise QaFailure(
                    "XNYS 마지막 완료 세션을 확인할 수 없습니다.",
                    {"error_type": type(exc).__name__},
                ) from exc
            _assert(
                str(feed.get("universe_as_of") or "")[:10]
                == expected_universe_as_of,
                "미국 ready 스냅샷이 XNYS 마지막 완료 세션일과 다릅니다.",
                universe_as_of=feed.get("universe_as_of"),
                expected_universe_as_of=expected_universe_as_of,
            )
            stock_reasons = stock_analysis.get("public_reasons") or []
            _assert(
                stock_analysis.get("status") == "ready"
                and stock_analysis.get("data_state") == "ready"
                and stock_analysis.get("snapshot_id") == feed.get("snapshot_id")
                and stock_analysis.get("snapshot_checksum")
                == feed.get("snapshot_checksum")
                and stock_analysis.get("is_current_universe_member") is True
                and stock_analysis.get("public_evidence_status") == "ready"
                and stock_analysis.get("data_covered") == 3
                and [
                    reason.get("key")
                    for reason in stock_reasons
                    if isinstance(reason, dict)
                ]
                == ["trend_20d", "trend_60d", "flow"]
                and [
                    reason.get("label")
                    for reason in stock_reasons
                    if isinstance(reason, dict)
                ]
                == ["20일 가격", "60일 가격", "거래대금 참여도"]
                and all(
                    reason.get("available") is True
                    for reason in stock_reasons
                    if isinstance(reason, dict)
                )
                and str(stock_analysis.get("as_of") or "")[:10]
                == str(feed.get("universe_as_of") or "")[:10]
                and str(stock_analysis.get("evidence_session_date") or "")
                == str(feed.get("universe_as_of") or "")[:10],
                "미국 Top100 종목 분석이 완료 세션 공개근거를 유지하지 못했습니다.",
                analysis=stock_analysis_meta,
                action=(stock_analysis.get("current") or {}).get("action"),
                labels=[
                    reason.get("label")
                    for reason in stock_reasons
                    if isinstance(reason, dict)
                ],
                availability=[
                    reason.get("available")
                    for reason in stock_reasons
                    if isinstance(reason, dict)
                ],
                analysis_as_of=stock_analysis.get("as_of"),
                universe_as_of=feed.get("universe_as_of"),
            )
            items = feed.get("items") or []
            _assert(isinstance(items, list), "미국 시그널 items가 배열이 아닙니다.")
            invalid_items: list[str] = []
            invalid_public_reasons: list[str] = []
            entry_pending_count = 0
            preliminary_item_count = 0
            confirmed_position_count = 0
            for item in items:
                if not isinstance(item, dict):
                    invalid_items.append("non_object")
                    continue
                current_signal = item.get("current") or {}
                action = str(current_signal.get("action") or "")
                if action == "entry_pending":
                    entry_pending_count += 1
                preliminary = action in {
                    "entry_watch",
                    "entry_pending",
                    "full_exit_pending",
                }
                position_open = action in {
                    "entered",
                    "holding",
                    "full_exit_pending",
                }
                if preliminary:
                    preliminary_item_count += 1
                if position_open:
                    confirmed_position_count += 1
                if not _valid_us_public_lifecycle_item(item):
                    invalid_items.append(str(item.get("code") or "unknown"))
                reasons = item.get("public_reasons")
                if not (
                    isinstance(reasons, list)
                    and [
                        reason.get("key")
                        for reason in reasons
                        if isinstance(reason, dict)
                    ]
                    == ["trend_20d", "trend_60d", "flow"]
                    and all(
                        reason.get("available") is True
                        for reason in reasons
                        if isinstance(reason, dict)
                    )
                ):
                    invalid_public_reasons.append(
                        str(item.get("code") or "unknown")
                    )
            _assert(
                not invalid_items,
                "미국 공개 모델 생명주기의 USD·Top100·상태 계약이 깨졌습니다.",
                invalid_items=invalid_items,
            )
            if feed.get("status") == "ready" and feed.get("data_state") == "ready":
                _assert(
                    int(feed.get("preliminary_count") or 0)
                    == preliminary_item_count
                    and int(feed.get("entry_pending_count") or 0)
                    >= entry_pending_count
                    and int(feed.get("confirmed_count") or 0)
                    == confirmed_position_count,
                    "미국 모델 생명주기 상태별 페이지/전체 집계가 화면 행과 다릅니다.",
                    preliminary_count=feed.get("preliminary_count"),
                    preliminary_item_count=preliminary_item_count,
                    entry_pending_count=feed.get("entry_pending_count"),
                    entry_pending_item_count=entry_pending_count,
                    confirmed_count=feed.get("confirmed_count"),
                    confirmed_position_count=confirmed_position_count,
                )
            _assert(
                not invalid_public_reasons,
                "미국 공개 근거가 20일·60일·거래대금 세 근거가 아닙니다.",
                invalid_codes=invalid_public_reasons,
            )
            recommendation_items = recommendations.get("items") or []
            _assert(
                isinstance(recommendation_items, list),
                "미국 추천 items가 배열이 아닙니다.",
            )
            recommendation_entry_pending_count = sum(
                1
                for item in recommendation_items
                if isinstance(item, dict)
                and (
                    str(item.get("action") or "") == "entry_pending"
                    or (
                        isinstance(item.get("ai_trade_signal"), dict)
                        and isinstance(item["ai_trade_signal"].get("current"), dict)
                        and item["ai_trade_signal"]["current"].get("action")
                        == "entry_pending"
                    )
                )
            )
            public_case = next(
                (
                    case
                    for case in catalog["cases"]
                    if case.get("id") == "SIG-UI-022"
                ),
                {},
            )
            forbidden_fields = set(
                public_case.get("inputs", {}).get("forbidden_public_fields") or []
            )
            forbidden_paths = _forbidden_key_paths(
                {
                    "feed": feed,
                    "recommendations": recommendations,
                    "stock_analysis": stock_analysis,
                },
                forbidden_fields,
            )
            _assert(
                not forbidden_paths,
                "미국 공개 응답에 내부 점수·필터 키가 남았습니다.",
                forbidden_paths=forbidden_paths,
            )
            invalid_recommendations: list[str] = []
            _assert(
                recommendations.get("recommendation_model_version")
                == "us-independent-recommendation-v1"
                and recommendations.get("recommendation_selection_rule")
                == "recommendation_score_ranked_independent_of_trade_signal",
                "미국 추천이 독립 점수 모델·선정 규칙을 공개하지 않았습니다.",
            )
            for item in recommendation_items:
                if not isinstance(item, dict):
                    invalid_recommendations.append("non_object")
                    continue
                score = item.get("recommendation_score")
                signal = item.get("ai_trade_signal") or {}
                if (
                    not isinstance(score, (int, float))
                    or not 0 <= float(score) <= 100
                    or item.get("recommendation_model_version")
                    != "us-independent-recommendation-v1"
                    or item.get("action") != "추천 후보"
                    or not isinstance(signal, dict)
                    or "score" in signal
                ):
                    invalid_recommendations.append(
                        str(item.get("code") or "unknown")
                    )
            _assert(
                not invalid_recommendations,
                "미국 독립 추천 점수와 nested 시그널 분리 계약이 깨졌습니다.",
                invalid_codes=invalid_recommendations,
            )
            methodology = " ".join(
                str(item) for item in feed.get("methodology") or []
            )
            _assert(
                all(token in methodology for token in ("수정 OHLC", "SPY·QQQ", "거래대금")),
                "미국 수정주가·시장·거래대금 근거 설명이 누락됐습니다.",
            )
            context["us_market"] = feed
            result = {
                "feed": feed_meta,
                "recommendations": recommendations_meta,
                "strategy_version": expected_version,
                "universe_count": universe_count,
                "evaluated_count": evaluated_count,
                "data_coverage_count": data_coverage_count,
                "signal_eligible_count": signal_eligible_count,
                "insufficient_history_count": insufficient_history_count,
                "coverage_complete": True,
                "universe_as_of": feed.get("universe_as_of"),
                "expected_universe_as_of": expected_universe_as_of,
                "snapshot_id": feed.get("snapshot_id"),
                "snapshot_checksum": feed.get("snapshot_checksum"),
                "data_state": feed.get("data_state"),
                "preliminary_count": feed.get("preliminary_count"),
                "confirmed_count": feed.get("confirmed_count"),
                "visible_item_count": len(items),
                "entry_pending_count": entry_pending_count,
                "recommendation_entry_pending_count": recommendation_entry_pending_count,
                "recommendation_model_version": recommendations.get(
                    "recommendation_model_version"
                ),
                "recommendation_count": len(recommendation_items),
                "forbidden_public_paths": forbidden_paths,
                "methodology": feed.get("methodology"),
                "stock_analysis": stock_analysis_meta,
                "stock_public_evidence_status": stock_analysis.get(
                    "public_evidence_status"
                ),
                "stock_evidence_session_date": stock_analysis.get(
                    "evidence_session_date"
                ),
            }
            context["us_market_contract"] = result
            return result

        collector.check(
            "SIG-US-VERSION-001",
            us_signal_contract,
            pass_message="미국 health·시그널·추천의 RC1 버전을 확인했습니다.",
        )
        collector.check(
            "DATA-US-UNIVERSE-001",
            us_signal_contract,
            pass_message="미국 완료 세션 Top100 스냅샷과 100/100/100 커버리를 확인했습니다.",
        )
        collector.check(
            "DATA-US-SIGNAL-INPUT-001",
            us_signal_contract,
            pass_message="미국 완료 세션 수정 일봉 입력 계약을 확인했습니다.",
        )
        collector.check(
            "DATA-US-EVIDENCE-001",
            us_signal_contract,
            pass_message="미국 시장·상대강도·달러 거래대금 근거 계약을 확인했습니다.",
        )
        collector.check(
            "SIG-US-CONTRACT-001",
            us_signal_contract,
            pass_message="미국 Top100 시그널·추천의 ready·canonical 공개 계약을 확인했습니다.",
        )
        collector.check(
            "SIG-US-MIGRATION-001",
            us_signal_contract,
            pass_message="레거시 미국 스냅샷이 NVDA 공개 근거 3개로 백필됐습니다.",
        )
        collector.check(
            "REC-US-INDEPENDENT-001",
            us_signal_contract,
            pass_message="미국 Top100 독립 추천 점수와 시그널 분리 계약을 확인했습니다.",
        )
        collector.check(
            "SIG-UI-022",
            us_signal_contract,
            pass_message="미국 공개 근거 3개와 내부 수치 비노출 계약을 확인했습니다.",
        )
    finally:
        api.close()

    return str((context.get("us_market") or {}).get("data_state") or "unknown"), context


def _public_websocket_check(
    collector: ResultCollector,
    base_url: str,
    timeout: float,
    *,
    expected_signal_revision: int | None = None,
) -> None:
    def current_http_signal_revision() -> int | None:
        """Read the revision immediately before comparing a live socket frame.

        The canonical feed can publish a new snapshot while the live QA suite
        is moving from its HTTP probes to the WebSocket probe.  A revision
        mismatch in that narrow window is a moving-target race, not evidence
        that the two transports disagree.  Re-read the HTTP revision once so
        the comparison is made against the same publication window.
        """
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(
                f"{base_url.rstrip('/')}/market/quant-signals",
                params={"universe_limit": 150, "limit": 0, "recent_days": 30},
            )
        response.raise_for_status()
        payload = response.json()
        revision = payload.get("signal_revision")
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 0
        ):
            return None
        return revision

    def websocket_contract() -> dict[str, Any]:
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise QaWarning(
                "websockets 동기 클라이언트가 없어 공개 실시간 채널을 생략했습니다."
            ) from exc
        ws_url, stream_resolution = _resolve_public_quote_stream_url(
            base_url, timeout
        )
        scheme = urlparse(ws_url).scheme

        def receive_required(
            socket: Any, required_types: set[str], *, maximum_frames: int = 12
        ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
            required = set(required_types)
            selected: dict[str, dict[str, Any]] = {}
            observed: list[dict[str, Any]] = []
            for _ in range(maximum_frames):
                frame = json.loads(socket.recv(timeout=timeout))
                _assert(isinstance(frame, dict), "WebSocket 프레임이 객체가 아닙니다.")
                observed.append(frame)
                frame_type = str(frame.get("type") or "")
                if frame_type == "status":
                    _validate_quote_status_frame(frame)
                elif frame_type == "error":
                    if frame.get("code") == "subscription_rate_limited":
                        _assert(
                            isinstance(frame.get("retry_after_ms"), int)
                            and int(frame["retry_after_ms"]) > 0,
                            "구독 속도 제한 error에 retry_after_ms가 없습니다.",
                            frame=frame,
                        )
                    raise QaFailure("WebSocket 구독 중 error 프레임을 받았습니다.", {"frame": frame})
                if frame_type in required and frame_type not in selected:
                    selected[frame_type] = frame
                    required.discard(frame_type)
                if not required:
                    return selected, observed
            raise QaFailure(
                "WebSocket 필수 프레임을 제한 개수 안에 받지 못했습니다.",
                {
                    "missing_types": sorted(required),
                    "observed_types": [frame.get("type") for frame in observed],
                },
            )

        with connect(ws_url, open_timeout=timeout, close_timeout=3) as socket:
            opening, opening_frames = receive_required(
                socket, {"ready", "signal_revision"}
            )
            ready = opening["ready"]
            revision = _validate_signal_revision_frame(
                opening["signal_revision"], require_initial=True
            )
            if expected_signal_revision is not None:
                if revision["revision"] != expected_signal_revision:
                    refreshed_http_revision = current_http_signal_revision()
                    _assert(
                        revision["revision"] == refreshed_http_revision,
                        "WebSocket 초기 신호 리비전이 HTTP 스냅샷과 다릅니다.",
                        websocket_revision=revision["revision"],
                        http_revision=expected_signal_revision,
                        refreshed_http_revision=refreshed_http_revision,
                    )
            _assert(ready.get("transport") == "multiplex", "WebSocket transport가 multiplex가 아닙니다.")
            _assert(
                int(ready.get("max_codes") or 0) > 0,
                "WebSocket ready에 종목 구독 상한이 없습니다.",
            )
            socket.send(json.dumps({"type": "set", "codes": ["005930"]}))
            subscribed_frames, quote_frames = receive_required(
                socket, {"subscribed", "quote"}
            )
            subscribed = subscribed_frames["subscribed"]
            _assert(
                subscribed.get("type") == "subscribed" and subscribed.get("count") == 1,
                "WebSocket 구독 ACK가 올바르지 않습니다.",
            )
            _assert(
                subscribed.get("codes") == ["005930"]
                and isinstance(subscribed.get("rejected_codes"), list)
                and not subscribed.get("rejected_codes"),
                "WebSocket 구독 ACK의 codes·rejected_codes가 올바르지 않습니다.",
                subscribed=subscribed,
            )
            quote = _validate_public_quote_frame(
                subscribed_frames["quote"], expected_code="005930"
            )
            socket.send(json.dumps({"type": "set", "codes": []}))
            unsubscribe_frames, unsubscribe_observed = receive_required(
                socket, {"subscribed"}
            )
            unsubscribed = unsubscribe_frames["subscribed"]
            _assert(
                unsubscribed.get("count") == 0
                and unsubscribed.get("codes") == []
                and isinstance(unsubscribed.get("rejected_codes"), list),
                "WebSocket 구독 해제가 반영되지 않았습니다.",
            )
        with connect(ws_url, open_timeout=timeout, close_timeout=3) as socket:
            reconnected_frames, reconnect_observed = receive_required(
                socket, {"ready", "signal_revision"}
            )
            reconnected = reconnected_frames["ready"]
            reconnected_revision = _validate_signal_revision_frame(
                reconnected_frames["signal_revision"], require_initial=True
            )
            _assert(
                reconnected.get("type") == "ready",
                "WebSocket 재연결 ready 프레임이 없습니다.",
            )
        return {
            "transport": scheme,
            "stream_url": ws_url,
            "stream_resolution": stream_resolution,
            "subscribe_count": 1,
            "unsubscribe_count": 0,
            "reconnected": True,
            "ready": {
                "transport": ready.get("transport"),
                "max_codes": ready.get("max_codes"),
            },
            "signal_revision": revision,
            "reconnected_signal_revision": reconnected_revision,
            "quote": quote,
            "observed_frame_types": [
                frame.get("type")
                for frame in [
                    *opening_frames,
                    *quote_frames,
                    *unsubscribe_observed,
                    *reconnect_observed,
                ]
            ],
        }

    started = monotonic()
    try:
        evidence = websocket_contract()
    except (QaFailure, QaWarning) as exc:
        collector.add(
            "DATA-KIS-005",
            "warn" if isinstance(exc, QaWarning) else "fail",
            str(exc),
            evidence=getattr(exc, "evidence", {}),
            duration_ms=round((monotonic() - started) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 - network volatility is evidence, not a crash.
        collector.add(
            "DATA-KIS-005",
            "warn",
            f"공개 WebSocket 실연동 확인 실패: {type(exc).__name__}",
            evidence={"exception_type": type(exc).__name__},
            duration_ms=round((monotonic() - started) * 1000),
        )
    else:
        collector.add(
            "DATA-KIS-005",
            "pass",
            "WebSocket ready·신호 리비전·구독 ACK·순서 메타 시세·해제·재연결을 확인했습니다.",
            evidence=evidence,
            duration_ms=round((monotonic() - started) * 1000),
        )


def _direct_kis_checks(collector: ResultCollector) -> None:
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import get_settings
    from app.services.kis_realtime import KisRealtimeQuoteProvider

    settings = get_settings()
    provider = KisRestBriefingProvider(settings)
    realtime = KisRealtimeQuoteProvider(settings)
    if not provider.is_configured():
        for case_id in ("DATA-KIS-001", "DATA-KIS-003", "DATA-KIS-004", "DATA-KIS-007"):
            collector.add(
                case_id,
                "warn",
                "KIS 인증정보가 없어 원천 직접 호출을 수행하지 못했습니다.",
                evidence={"configured": False},
            )
        return

    def oauth_contract() -> dict[str, Any]:
        token = provider._ensure_token()
        _assert(bool(token), "KIS OAuth 토큰이 비어 있습니다.")
        return {"configured": True, "token_received": True, "token_length": len(token)}

    collector.check(
        "DATA-KIS-001",
        oauth_contract,
        pass_message="KIS OAuth 토큰 발급과 메모리 캐시를 확인했습니다.",
    )

    def quote_and_venue() -> dict[str, Any]:
        krx = provider._request_current_price("005930", "J")
        _assert(krx.get("stck_prpr"), "KIS KRX 현재가가 없습니다.")
        integrated = provider._request_current_price("005930", "UN")
        return {
            "krx_price_present": True,
            "integrated_price_present": bool(integrated.get("stck_prpr")),
        }

    collector.check(
        "DATA-KIS-007",
        quote_and_venue,
        pass_message="KIS KRX·통합 시세 응답과 신호용 KRX 분리를 확인했습니다.",
    )

    def market_data_contract() -> dict[str, Any]:
        indices = provider.fetch_market_indices()
        intraday = provider.fetch_intraday_chart("005930", max_points=5)
        orderbook = provider._get(
            "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
            "FHKST01010200",
            {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930"},
        )
        _assert(
            len(indices) == 2, "KIS 지수 2종이 완성되지 않았습니다.", count=len(indices)
        )
        _assert(isinstance(intraday, list), "KIS 분봉 응답이 배열이 아닙니다.")
        _assert(
            bool(orderbook.get("output1") or orderbook.get("output")),
            "KIS 호가 응답이 비어 있습니다.",
        )
        return {
            "indices": [item.get("code") for item in indices],
            "intraday_points": len(intraday),
            "orderbook_present": True,
        }

    collector.check(
        "DATA-KIS-003",
        market_data_contract,
        pass_message="KIS 지수·분봉·호가 원천 응답을 확인했습니다.",
    )

    def ranking_contract() -> dict[str, Any]:
        gainers = provider._fetch_fluctuation("gainers", 3, "0", "300")
        losers = provider._fetch_fluctuation("losers", 3, "-300", "0")
        turnover = provider._fetch_turnover(3)
        _assert(
            all((item.change_rate or 0) >= 0 for item in gainers),
            "상승률 순위에 음수 종목이 섞였습니다.",
        )
        _assert(
            all((item.change_rate or 0) <= 0 for item in losers),
            "하락률 순위에 양수 종목이 섞였습니다.",
        )
        return {
            "gainers": len(gainers),
            "losers": len(losers),
            "turnover": len(turnover),
        }

    collector.check(
        "DATA-KIS-004",
        ranking_contract,
        pass_message="KIS 거래량·등락률 순위 방향성을 확인했습니다.",
    )

    if realtime.is_configured():

        def approval_contract() -> dict[str, Any]:
            approval = asyncio.run(realtime.approval_key())
            _assert(bool(approval), "KIS WebSocket approval key가 비어 있습니다.")
            return {
                "approval_received": True,
                "approval_length": len(approval),
                "configured_limit": settings.kis_realtime_max_codes,
            }

        collector.check(
            "DATA-KIS-005",
            approval_contract,
            pass_message="KIS WebSocket approval 발급을 확인했습니다.",
        )


def _summary(results: list[QaCheckResult], mode: QaMode) -> dict[str, Any]:
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("pass", "warn", "fail", "skip")
    }
    p0_failures = [
        result.id
        for result in results
        if result.priority == "P0" and result.status == "fail"
    ]
    p0_missing = [
        result.id
        for result in results
        if mode == "gate" and result.priority == "P0" and result.status == "skip"
    ]
    return {
        **counts,
        "total": len(results),
        "p0_failures": p0_failures,
        "p0_missing": p0_missing,
        "deployment_blocked": bool(p0_failures or p0_missing),
        "policy": "P0 failure or missing gate evidence blocks deployment; WARN records tolerated degradation",
        "mode": mode,
    }


def run_data_signal_qa(
    *,
    mode: QaMode,
    base_url: str | None = None,
    timeout: float = 20.0,
    artifact_dir: Path | str | None = None,
    direct_kis: bool = False,
    pytest_junit: Path | str | None = None,
    surface: str = "dashboard",
) -> dict[str, Any]:
    if mode not in {"gate", "live", "e2e"}:
        raise ValueError("mode must be gate, live, or e2e")
    if surface not in {"dashboard", "us", "us-gateway"}:
        raise ValueError("surface must be dashboard, us, or us-gateway")
    base_url = base_url or DEFAULT_STAGING_BASE_URLS[surface]
    catalog = load_qa_catalog()
    collector = ResultCollector(catalog)
    market_state: str | None = None
    if mode == "gate":
        _gate_checks(collector, catalog, pytest_junit=pytest_junit)
    elif mode == "live":
        if surface == "us-gateway":
            _live_us_gateway_checks(collector, base_url=base_url, timeout=timeout)
        elif surface == "us":
            market_state, _ = _live_us_checks(
                collector,
                catalog,
                base_url=base_url,
                timeout=timeout,
            )
        else:
            market_state, _ = _live_checks(
                collector,
                catalog,
                base_url=base_url,
                timeout=timeout,
                direct_kis=direct_kis,
            )
    else:
        from app.qa.e2e import run_e2e_checks

        e2e_results = run_e2e_checks(
            catalog=catalog,
            base_url=base_url,
            timeout=timeout,
            artifact_dir=artifact_dir,
            surface=surface,
        )
        for result in e2e_results:
            collector.add(**result)
        for result in e2e_results:
            evidence = result.get("evidence") or {}
            for theme in ("dark", "light"):
                api_stock = (evidence.get(theme) or {}).get("api_stock") or {}
                if api_stock.get("market_state"):
                    market_state = str(api_stock["market_state"])
                    break
            if market_state:
                break

    results = collector.results
    summary = _summary(results, mode)
    report = {
        "schema_version": "1.0",
        "run_id": f"qa-{datetime.now(KST).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}",
        "mode": mode,
        "surface": surface,
        "environment": _environment_name(base_url),
        "base_url": base_url.rstrip("/"),
        "as_of": datetime.now(KST).isoformat(),
        "market_state": market_state,
        "strategy_version": catalog["strategy_version"],
        "us_strategy_version": catalog.get("us_strategy_version"),
        "catalog_version": catalog["catalog_version"],
        "catalog_case_count": len(catalog["cases"]),
        "checks": [asdict(result) for result in results],
        "summary": summary,
        "deployment_blocked": summary["deployment_blocked"],
    }
    return redact(report)


def write_qa_report(report: dict[str, Any], output: Path | str) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(redact(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
