from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import MarketRankingSnapshot
from app.services import us_market
from app.services import us_signal_universe as universe


UTC = timezone.utc


def _quote(
    code: str,
    market_cap: int,
    *,
    volume: int = 1_000_000,
    regular_market_time: int = 1788912000,
) -> dict[str, object]:
    return {
        "symbol": code,
        "longName": f"{code} Corporation Common Stock",
        "quoteType": "EQUITY",
        "exchange": "NMS",
        "currency": "USD",
        "marketCap": market_cap,
        "regularMarketPrice": 100,
        "regularMarketVolume": 1_500_000,
        "regularMarketChangePercent": 1.25,
        "fiftyDayAverageChangePercent": 0.08,
        "twoHundredDayAverageChangePercent": 0.20,
        "trailingPE": 24.5,
        "priceToBook": 7.5,
        "averageDailyVolume3Month": volume,
        # Default: 2026-09-08 20:00 America/New_York (completed session date).
        "regularMarketTime": regular_market_time,
    }


def _candidates(count: int) -> list[dict[str, object]]:
    return [
        {
            "code": f"A{index:03d}",
            "name": f"Issuer {index} Common Stock",
            "sector": "Technology",
            "industry": "Software",
            "screen_exchange": "NASDAQ",
            "screen_market_cap": 1_000_000 - index,
            "screen_as_of": "2026-09-08",
        }
        for index in range(count)
    ]


def _cik_map(candidates: list[dict[str, object]]) -> dict[str, str]:
    return {
        str(item["code"]): f"{index + 1:010d}"
        for index, item in enumerate(candidates)
    }


def _valid_payload(
    as_of: str = "2026-09-08",
    *,
    code_prefix: str = "T",
) -> dict[str, object]:
    items = [
        {
            "market_cap_rank": rank,
            "code": f"{code_prefix}{rank:03d}",
            "name": f"Issuer {rank}",
            "market": "NASDAQ",
            "exchange": "NMS",
            "market_cap": str(2_000_000_000 - rank),
            "issuer_key": f"cik:{rank:010d}",
            "cik": f"{rank:010d}",
            "currency": "USD",
            "sector": "Technology",
            "screen_as_of": as_of,
            "quote_date": as_of,
        }
        for rank in range(1, 101)
    ]
    return {
        "status": "ready",
        "data_state": "ready",
        "universe_version": universe.US_SIGNAL_UNIVERSE_VERSION,
        "universe_as_of": as_of,
        "universe_count": 100,
        "source_candidate_count": 101,
        "validated_quote_count": 101,
        "checksum": universe._snapshot_checksum(items),
        "generated_at": f"{as_of}T21:00:00+00:00",
        "new_entries_allowed": True,
        "items": items,
    }


def _add_snapshot(
    db,
    payload: dict[str, object],
    *,
    captured_at: datetime,
    snapshot_id: str | None = None,
) -> MarketRankingSnapshot:
    row = MarketRankingSnapshot(
        snapshot_id=snapshot_id
        or f"{universe.US_SIGNAL_UNIVERSE_VERSION}:{payload['universe_as_of']}",
        category=universe.US_SIGNAL_UNIVERSE_CATEGORY,
        payload=universe._serialize_payload(payload),
        captured_at=captured_at,
        expires_at=captured_at + timedelta(days=400),
    )
    db.add(row)
    db.commit()
    return row


def test_cross_exchange_duplicate_ticker_is_rejected(monkeypatch):
    duplicate = {
        "symbol": "DUPE",
        "name": "Duplicate Corporation Common Stock",
        "marketCap": "$10B",
        "sector": "Technology",
        "industry": "Software",
        "country": "United States",
        "_screen_as_of": datetime(2026, 9, 8).date(),
    }
    monkeypatch.setattr(
        universe,
        "_fetch_exchange_screen",
        lambda _exchange, **_kwargs: [duplicate],
    )

    with pytest.raises(ValueError, match="duplicate ticker identities"):
        universe._screen_candidates(refresh=True)


@pytest.fixture
def sqlite_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[MarketRankingSnapshot.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    with factory() as db:
        yield db
    engine.dispose()


def test_us_signal_universe_is_exact_top100_and_deduplicates_share_classes(monkeypatch):
    candidates = _candidates(101)
    candidates.extend(
        [
            {**candidates[0], "code": "GOOG", "name": "Alphabet Class C"},
            {**candidates[0], "code": "GOOGL", "name": "Alphabet Class A"},
        ]
    )
    quotes = {
        item["code"]: _quote(str(item["code"]), 2_000_000_000 - index * 1_000_000)
        for index, item in enumerate(candidates)
    }
    quotes["GOOG"] = _quote("GOOG", 3_000_000_000, volume=2_000_000)
    quotes["GOOGL"] = _quote("GOOGL", 3_000_000_000, volume=3_000_000)
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    cik_by_code = _cik_map(candidates)
    cik_by_code.update({"GOOG": "0001652044", "GOOGL": "0001652044"})
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: cik_by_code)

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "ready"
    assert payload["universe_count"] == 100
    assert [item["market_cap_rank"] for item in payload["items"]] == list(range(1, 101))
    assert len({item["issuer_key"] for item in payload["items"]}) == 100
    assert "GOOGL" in {item["code"] for item in payload["items"]}
    assert "GOOG" not in {item["code"] for item in payload["items"]}
    first = payload["items"][0]
    assert first["legacy_regular_market_change_percent"] == Decimal("1.25")
    assert first["legacy_regular_market_volume"] == 1_500_000
    assert first["legacy_fifty_day_average_change_percent"] == Decimal("0.08")
    assert first["legacy_two_hundred_day_average_change_percent"] == Decimal("0.20")
    assert first["legacy_trailing_pe"] == Decimal("24.5")
    assert first["legacy_price_to_book"] == Decimal("7.5")


def test_us_signal_universe_fails_closed_when_fewer_than_100_validate(monkeypatch):
    candidates = _candidates(99)
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(
        us_market,
        "fetch_us_quote_batch",
        lambda symbols, **_kwargs: {
            item["code"]: _quote(str(item["code"]), 2_000_000_000 - index)
            for index, item in enumerate(candidates)
        },
    )
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["universe_count"] == 0
    assert payload["new_entries_allowed"] is False


def test_exactly_100_screen_issuers_cannot_claim_a_proven_top100_boundary(monkeypatch):
    candidates = _candidates(100)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(
        us_market,
        "fetch_us_quote_batch",
        lambda symbols, **_kwargs: quotes,
    )
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["universe_count"] == 0
    assert payload["new_entries_allowed"] is False


def test_us_signal_universe_security_name_filter_rejects_non_common_equity():
    allowed = {"symbol": "TSM", "name": "Taiwan Semiconductor ADR", "marketCap": "$1.2T"}
    assert universe._screen_row_allowed(allowed) is True
    for name in (
        "Example 5.25% Preferred Stock",
        "Example Acquisition Corp Unit",
        "Example Warrants",
        "Example Notes due 2030",
        "Example ETF",
    ):
        assert universe._screen_row_allowed(
            {"symbol": "BAD", "name": name, "marketCap": "$10B"}
        ) is False


def test_exchange_screen_paginates_table_rows_and_preserves_as_of(monkeypatch):
    calls: list[tuple[int, object]] = []

    class Response:
        def __init__(self, offset: int):
            self.offset = offset

        def raise_for_status(self):
            return None

        def json(self):
            symbol = "AAA" if self.offset == 0 else "BBB"
            return {
                "data": {
                    "table": {
                        "rows": [
                            {
                                "symbol": symbol,
                                "name": f"{symbol} Common Stock",
                                "marketCap": "$10B",
                            }
                        ]
                    },
                    "totalrecords": 2,
                    "asof": "Last price as of Sep 8, 2026",
                }
            }

    class DetailResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "rows": [
                        {"symbol": "AAA", "sector": "Technology"},
                        {"symbol": "BBB", "sector": "Health Care"},
                    ]
                }
            }

    def fake_get(_url, *, params, **_kwargs):
        calls.append((params["offset"], params.get("download")))
        if params.get("download") == "true":
            return DetailResponse()
        return Response(params["offset"])

    monkeypatch.setattr(universe.requests, "get", fake_get)

    rows = universe._fetch_exchange_screen("nasdaq", refresh=True)

    assert calls == [(0, None), (1, None), (0, "true")]
    assert [item["symbol"] for item in rows] == ["AAA", "BBB"]
    assert [item["sector"] for item in rows] == ["Technology", "Health Care"]
    assert {item["_screen_as_of"].isoformat() for item in rows} == {"2026-09-08"}


def test_exchange_screen_allows_detail_to_omit_proven_excluded_rank_instrument(
    monkeypatch,
):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "table": {
                        "rows": [
                            {
                                "symbol": "AAA",
                                "name": "AAA Common Stock",
                                "marketCap": "$10B",
                            },
                            {
                                "symbol": "AAAW",
                                "name": "AAA Corp. Warrant",
                                "marketCap": "NA",
                            },
                        ]
                    },
                    "totalrecords": 2,
                    "asof": "Last price as of Sep 8, 2026",
                }
            }

    class DetailResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "rows": [
                        {
                            "symbol": "AAA",
                            "name": "AAA Common Stock",
                            "marketCap": "$10B",
                            "sector": "Technology",
                        }
                    ]
                }
            }

    monkeypatch.setattr(
        universe.requests,
        "get",
        lambda _url, *, params, **_kwargs: (
            DetailResponse() if params.get("download") == "true" else Response()
        ),
    )

    rows = universe._fetch_exchange_screen("nasdaq", refresh=True)

    assert [item["symbol"] for item in rows] == ["AAA"]


@pytest.mark.parametrize(
    "invalidity",
    ["missing_total", "changed_date", "classification_set"],
)
def test_exchange_screen_rejects_incomplete_or_date_misaligned_pages(
    monkeypatch,
    invalidity,
):
    class Response:
        def __init__(self, offset: int):
            self.offset = offset

        def raise_for_status(self):
            return None

        def json(self):
            data = {
                "table": {
                    "rows": [
                        {
                            "symbol": f"A{self.offset}",
                            "name": f"Issuer {self.offset} Common Stock",
                            "marketCap": "$10B",
                        }
                    ]
                },
                "totalrecords": 2,
                "asof": (
                    "Last price as of Sep 7, 2026"
                    if invalidity == "changed_date" and self.offset == 1
                    else "Last price as of Sep 8, 2026"
                ),
            }
            if invalidity == "missing_total":
                data.pop("totalrecords")
            return {"data": data}

    monkeypatch.setattr(
        universe.requests,
        "get",
        lambda _url, *, params, **_kwargs: Response(params["offset"]),
    )

    with pytest.raises(ValueError):
        universe._fetch_exchange_screen("nasdaq", refresh=True)


@pytest.mark.parametrize("failure", ["missing", "stale", "non_usd"])
def test_top_cap_quote_failure_does_not_promote_issuer_101(monkeypatch, failure):
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(
            str(item["code"]),
            2_000_000_000 - index,
        )
        for index, item in enumerate(candidates)
    }
    if failure == "missing":
        quotes.pop("A000")
    elif failure == "stale":
        quotes["A000"] = _quote(
            "A000",
            2_000_000_000,
            regular_market_time=1788825600,
        )
    else:
        quotes["A000"]["currency"] = "CAD"
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["universe_count"] == 0
    assert payload["new_entries_allowed"] is False
    assert "A100" in quotes  # A complete #101 quote existed but was not promoted.


def test_top_cap_missing_class_allows_valid_alternate_class(monkeypatch):
    candidates = _candidates(101)
    alternate = {
        **candidates[0],
        "code": "A000.B",
        "name": "Issuer 0 Class B",
        "screen_market_cap": 100,
    }
    candidates.append(alternate)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
        if item["code"] != "A000"
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    cik_by_code = _cik_map(candidates)
    cik_by_code.update({"A000": "0000000001", "A000.B": "0000000001"})
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: cik_by_code)

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "ready"
    assert payload["universe_count"] == 100
    assert "A000.B" in {item["code"] for item in payload["items"]}
    assert "A000" not in {item["code"] for item in payload["items"]}
    alternate_member = next(item for item in payload["items"] if item["code"] == "A000.B")
    assert alternate_member["market_cap"] == 1_000_000


def test_nasdaq_screen_is_the_only_market_cap_ranking_source(monkeypatch):
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    quotes["A100"] = _quote("A100", 99_000_000_000)
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "ready"
    assert [item["code"] for item in payload["items"]] == [
        f"A{index:03d}" for index in range(100)
    ]
    assert "A100" not in {item["code"] for item in payload["items"]}
    assert [item["market_cap"] for item in payload["items"]] == sorted(
        [item["market_cap"] for item in payload["items"]],
        reverse=True,
    )


@pytest.mark.parametrize("failure", ["unavailable", "boundary_missing"])
def test_sec_cik_failure_at_top100_boundary_fails_closed(monkeypatch, failure):
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    if failure == "unavailable":
        monkeypatch.setattr(
            us_market,
            "_sec_ticker_map",
            lambda: (_ for _ in ()).throw(RuntimeError("SEC unavailable")),
        )
    else:
        cik_by_code = _cik_map(candidates)
        cik_by_code.pop("A050")
        monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: cik_by_code)

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["universe_count"] == 0
    assert payload["new_entries_allowed"] is False


@pytest.mark.parametrize("failure", ["stale", "mixed_exchange_dates"])
def test_screener_as_of_must_match_quotes_and_completed_session(monkeypatch, failure):
    candidates = _candidates(101)
    if failure == "stale":
        for item in candidates:
            item["screen_as_of"] = "2026-09-07"
    else:
        candidates[-1]["screen_as_of"] = "2026-09-07"
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(
        us_market,
        "fetch_us_quote_batch",
        lambda symbols, **_kwargs: quotes,
    )
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["new_entries_allowed"] is False


def test_forming_regular_session_never_publishes_current_day_snapshot(monkeypatch):
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        # 2026-09-08 14:00 America/New_York, the same date as the quotes.
        now=datetime(2026, 9, 8, 18, 0, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["data_state"] == "unavailable"
    assert payload["new_entries_allowed"] is False


def test_completed_session_waits_for_provider_publication_grace(monkeypatch):
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        now=datetime(2026, 9, 8, 20, 14, 59, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["new_entries_allowed"] is False
    assert "publication grace" in payload["source_error"]


@pytest.mark.parametrize(
    "case",
    [
        "version",
        "count",
        "ranks",
        "duplicate_code",
        "duplicate_issuer",
        "checksum",
        "date",
        "quote_date",
        "snapshot_id",
        "new_entries_allowed",
        "source_candidate_count",
        "validated_quote_count",
        "currency",
        "cik",
    ],
)
def test_persisted_snapshot_validation_is_strict(case):
    payload = _valid_payload()
    snapshot_id = f"{universe.US_SIGNAL_UNIVERSE_VERSION}:2026-09-08"
    if case == "version":
        payload["universe_version"] = "legacy-version"
    elif case == "count":
        payload["universe_count"] = 99
    elif case == "ranks":
        payload["items"][0]["market_cap_rank"] = 2
        payload["checksum"] = universe._snapshot_checksum(payload["items"])
    elif case == "duplicate_code":
        payload["items"][1]["code"] = payload["items"][0]["code"]
        payload["checksum"] = universe._snapshot_checksum(payload["items"])
    elif case == "duplicate_issuer":
        payload["items"][1]["issuer_key"] = payload["items"][0]["issuer_key"]
        payload["checksum"] = universe._snapshot_checksum(payload["items"])
    elif case == "checksum":
        payload["checksum"] = "0" * 64
    elif case == "date":
        payload["universe_as_of"] = "2026-09-08T00:00:00"
    elif case == "quote_date":
        payload["items"][0]["quote_date"] = "2026-09-07"
    elif case == "snapshot_id":
        snapshot_id = f"{universe.US_SIGNAL_UNIVERSE_VERSION}:2026-09-07"
    elif case == "new_entries_allowed":
        payload["new_entries_allowed"] = False
    elif case == "source_candidate_count":
        payload["source_candidate_count"] = 100
    elif case == "validated_quote_count":
        payload["validated_quote_count"] = 99
    elif case == "currency":
        payload["items"][0]["currency"] = "CAD"
        payload["checksum"] = universe._snapshot_checksum(payload["items"])
    elif case == "cik":
        payload["items"][0]["cik"] = "not-a-cik"
        payload["items"][0]["issuer_key"] = "cik:not-a-cik"
        payload["checksum"] = universe._snapshot_checksum(payload["items"])

    assert universe._snapshot_payload_is_valid(
        payload,
        snapshot_id=snapshot_id,
    ) is False


def test_snapshot_checksum_covers_sector_and_rank_caps_are_non_increasing():
    payload = _valid_payload()
    snapshot_id = f"{universe.US_SIGNAL_UNIVERSE_VERSION}:2026-09-08"
    original_checksum = payload["checksum"]

    payload["items"][0]["sector"] = "Energy"

    assert universe._snapshot_checksum(payload["items"]) != original_checksum
    assert universe._snapshot_payload_is_valid(payload, snapshot_id=snapshot_id) is False

    payload = _valid_payload()
    payload["items"][1]["market_cap"] = str(
        int(payload["items"][0]["market_cap"]) + 1
    )
    payload["checksum"] = universe._snapshot_checksum(payload["items"])

    assert universe._snapshot_payload_is_valid(payload, snapshot_id=snapshot_id) is False


def test_source_failure_uses_valid_stale_snapshot_and_blocks_entries(
    monkeypatch,
    sqlite_db,
):
    # 2026-09-07 is Labor Day; the previous official XNYS session is 09-04.
    previous = _valid_payload("2026-09-04", code_prefix="V")
    _add_snapshot(
        sqlite_db,
        previous,
        captured_at=datetime(2026, 9, 9, 1, 0),
    )
    monkeypatch.setattr(
        universe,
        "_screen_candidates",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("screen unavailable")),
    )

    payload = universe.build_us_signal_universe(
        db=sqlite_db,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "degraded"
    assert payload["data_state"] == "stale"
    assert payload["universe_as_of"] == "2026-09-04"
    assert payload["universe_count"] == 100
    assert payload["checksum"] == previous["checksum"]
    assert payload["new_entries_allowed"] is False


def test_exact_completed_daily_snapshot_is_reused_without_remote_calls(
    monkeypatch,
    sqlite_db,
):
    completed = _valid_payload()
    row = _add_snapshot(
        sqlite_db,
        completed,
        captured_at=datetime(2026, 9, 9, 1, 0),
    )
    original_payload = row.payload
    monkeypatch.setattr(
        universe,
        "_screen_candidates",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("same-session snapshot must avoid a remote refresh")
        ),
    )
    monkeypatch.setattr(
        us_market,
        "fetch_us_quote_batch",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("same-session snapshot must avoid quote refresh")
        ),
    )
    monkeypatch.setattr(
        us_market,
        "_sec_ticker_map",
        lambda: (_ for _ in ()).throw(
            AssertionError("same-session snapshot must avoid SEC refresh")
        ),
    )

    payload = universe.build_us_signal_universe(
        db=sqlite_db,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "ready"
    assert payload["data_state"] == "ready"
    assert payload["universe_as_of"] == "2026-09-08"
    assert payload["checksum"] == completed["checksum"]
    assert payload["new_entries_allowed"] is True
    sqlite_db.refresh(row)
    assert row.payload == original_payload


def test_malformed_exact_daily_snapshot_is_never_overwritten(
    monkeypatch,
    sqlite_db,
):
    malformed = _valid_payload()
    malformed.pop("source_candidate_count")
    row = _add_snapshot(
        sqlite_db,
        malformed,
        captured_at=datetime(2026, 9, 9, 1, 0),
    )
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    source_calls: list[str] = []

    def screen_candidates(**_kwargs):
        source_calls.append("screen")
        return candidates

    monkeypatch.setattr(universe, "_screen_candidates", screen_candidates)
    monkeypatch.setattr(
        us_market,
        "fetch_us_quote_batch",
        lambda symbols, **_kwargs: quotes,
    )
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))

    payload = universe.build_us_signal_universe(
        db=sqlite_db,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert source_calls == ["screen"]
    assert payload["status"] == "unavailable"
    assert payload["new_entries_allowed"] is False
    assert "invalid and immutable" in payload["source_error"]
    sqlite_db.refresh(row)
    assert universe._decode_valid_snapshot(row) is None
    assert "source_candidate_count" not in json.loads(row.payload)


def test_stale_fallback_skips_latest_malformed_snapshot(monkeypatch, sqlite_db):
    previous = _valid_payload("2026-09-04", code_prefix="V")
    _add_snapshot(
        sqlite_db,
        previous,
        captured_at=datetime(2026, 9, 8, 1, 0),
    )
    sqlite_db.add(
        MarketRankingSnapshot(
            snapshot_id=f"{universe.US_SIGNAL_UNIVERSE_VERSION}:2026-09-08",
            category=universe.US_SIGNAL_UNIVERSE_CATEGORY,
            payload="{not-json",
            captured_at=datetime(2026, 9, 9, 1, 0),
            expires_at=datetime(2027, 9, 9, 1, 0),
        )
    )
    sqlite_db.commit()
    monkeypatch.setattr(
        universe,
        "_screen_candidates",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("screen unavailable")),
    )

    payload = universe.build_us_signal_universe(
        db=sqlite_db,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert payload["status"] == "degraded"
    assert payload["universe_as_of"] == "2026-09-04"
    assert payload["checksum"] == previous["checksum"]
    assert payload["new_entries_allowed"] is False


@pytest.mark.parametrize("invalidity", ["checksum", "ranks"])
def test_latest_invalid_checksum_or_ranks_is_skipped(sqlite_db, invalidity):
    previous = _valid_payload("2026-09-04", code_prefix="V")
    _add_snapshot(
        sqlite_db,
        previous,
        captured_at=datetime(2026, 9, 8, 1, 0),
    )
    invalid = _valid_payload("2026-09-08", code_prefix="X")
    if invalidity == "checksum":
        invalid["checksum"] = "f" * 64
    else:
        invalid["items"][0]["market_cap_rank"] = 2
        invalid["checksum"] = universe._snapshot_checksum(invalid["items"])
    _add_snapshot(
        sqlite_db,
        invalid,
        captured_at=datetime(2026, 9, 9, 1, 0),
    )

    loaded = universe.load_latest_us_signal_universe_snapshot(sqlite_db)

    assert loaded is not None
    assert loaded["universe_as_of"] == "2026-09-04"
    assert loaded["checksum"] == previous["checksum"]


def test_commit_failure_rolls_back_before_valid_stale_fallback(
    monkeypatch,
    sqlite_db,
):
    previous = _valid_payload("2026-09-04", code_prefix="V")
    _add_snapshot(
        sqlite_db,
        previous,
        captured_at=datetime(2026, 9, 8, 1, 0),
    )
    candidates = _candidates(101)
    quotes = {
        str(item["code"]): _quote(str(item["code"]), 2_000_000_000 - index)
        for index, item in enumerate(candidates)
    }
    monkeypatch.setattr(universe, "_screen_candidates", lambda **_kwargs: candidates)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", lambda symbols, **_kwargs: quotes)
    monkeypatch.setattr(us_market, "_sec_ticker_map", lambda: _cik_map(candidates))
    rollback_events: list[str] = []
    real_rollback = sqlite_db.rollback

    def record_rollback():
        rollback_events.append("rollback")
        return real_rollback()

    monkeypatch.setattr(sqlite_db, "rollback", record_rollback)
    monkeypatch.setattr(
        sqlite_db,
        "commit",
        lambda: (_ for _ in ()).throw(RuntimeError("commit exploded")),
    )

    payload = universe.build_us_signal_universe(
        db=sqlite_db,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
    )

    assert rollback_events
    assert payload["status"] == "degraded"
    assert payload["universe_as_of"] == "2026-09-04"
    assert payload["new_entries_allowed"] is False
    rows = list(sqlite_db.scalars(select(MarketRankingSnapshot)))
    assert [row.snapshot_id for row in rows] == [
        f"{universe.US_SIGNAL_UNIVERSE_VERSION}:2026-09-04"
    ]


def test_complete_daily_snapshot_is_not_rewritten(sqlite_db):
    first = _valid_payload()
    row = _add_snapshot(
        sqlite_db,
        first,
        captured_at=datetime(2026, 9, 9, 1, 0),
    )
    original_payload = row.payload
    original_captured_at = row.captured_at
    repeated = deepcopy(first)
    repeated["generated_at"] = "2026-09-09T02:00:00+00:00"

    persisted = universe._persist_snapshot(sqlite_db, repeated)
    sqlite_db.refresh(row)

    assert persisted["generated_at"] == first["generated_at"]
    assert row.payload == original_payload
    assert row.captured_at == original_captured_at
