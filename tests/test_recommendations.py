from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import DailyPrice, StockMaster
from app.schemas import MarketRecommendationOut
from app.services import recommendations
from app.services.recommendations import _action, _decision_reason, build_recommendations, universe_cache


def test_high_recommendation_score_produces_an_actionable_but_measured_decision():
    action = _action(Decimal("82.12"), Decimal("80"))

    assert action == "분할 접근"
    assert "추격 대신 나눠 접근" in _decision_reason(
        action,
        Decimal("82.12"),
        Decimal("80"),
        Decimal("30.55"),
    )


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _confirmed_entry_signal(code: str) -> dict[str, object]:
    as_of = datetime(2026, 8, 20, 15, 40, tzinfo=recommendations.KST)
    return {
        "code": code,
        "data_state": "ready",
        "data_message": "ready",
        "as_of": as_of,
        "price_through": date(2026, 8, 20),
        "strategy_version": "confirmed-entry-test",
        "signal_source": "local",
        "entry_score_threshold": Decimal("62"),
        "display_return_rate": None,
        "display_return_kind": None,
        "current": {
            "action": "entry_pending",
            "label": "매수 조건 확정",
            "score": Decimal("78.5"),
            "price": 81_000,
            "as_of": as_of,
            "live_observation": False,
            "position_open": False,
            "model_exposure_percent": Decimal("0"),
            "lifecycle": {
                "state": "entry_pending",
                "label": "매수 조건 확정",
                "stage_index": 2,
                "stages": ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"],
                "latest_transition": None,
            },
            "entry_date": None,
            "entry_price": None,
            "target_sell_price": None,
            "partial_exit_date": None,
            "partial_exit_price": None,
            "profit_stage": 0,
            "pending_profit_stage": None,
            "profit_steps_total": 3,
            "entry_setup": "trend_continuation",
            "entry_confirmation": {
                "allowed": True,
                "state": "approved",
                "required_supports": 1,
                "supportive_count": 2,
                "reason": "독립 우호 근거 2/1개와 최신성 확인 완료",
            },
            "partial_exit_reference": None,
            "locked_profit_reference": None,
            "stop_reference": None,
            "levels": [
                {
                    "key": "entry",
                    "label": "진입 확인선",
                    "price": 80_500,
                    "condition": "장 마감 기준 가격·거래 규모 조건 충족",
                }
            ],
            "unrealized_return": None,
            "reasons": ["가격 조건과 독립 근거 확인"],
            "next_confirmation": "다음 거래일 시가의 갭 범위를 확인",
        },
    }


def _entered_today_signal(code: str) -> dict[str, object]:
    signal = _confirmed_entry_signal(code)
    as_of = datetime(2026, 9, 1, 9, 20, tzinfo=recommendations.KST)
    current = signal["current"]
    current.update(
        {
            "action": "entered",
            "label": "전략상 진입 완료",
            "score": Decimal("75.37"),
            "price": 82_000,
            "as_of": as_of,
            "position_open": True,
            "model_exposure_percent": Decimal("100"),
            "entry_date": date(2026, 9, 1),
            "entry_price": 80_700,
            "lifecycle": {
                "state": "entered",
                "label": "전략상 진입 완료",
                "stage_index": 3,
                "stages": ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"],
                "latest_transition": {
                    "label": "전략상 진입",
                    "side": "buy",
                    "signal_at": "2026-08-31T15:40:00+09:00",
                    "signal_date": "2026-08-31",
                    "transition_date": "2026-09-01",
                    "price": 80_700,
                    "entry_price": 80_700,
                },
            },
            "levels": [
                {"key": "partial_exit", "label": "1차 수익확정", "price": 86_000},
                {"key": "full_exit", "label": "초기 위험선", "price": 76_000},
            ],
            "next_confirmation": "초기 위험선과 첫 수익확정 기준을 매일 확인",
        }
    )
    signal.update(
        {
            "as_of": as_of,
            "price_through": date(2026, 8, 31),
            "display_return_rate": Decimal("1.61"),
            "display_return_kind": "open_position",
        }
    )
    return signal


def _install_confirmed_entry_signals(monkeypatch, codes: list[str]) -> None:
    payloads = {code: _confirmed_entry_signal(code) for code in codes}
    snapshot = {
        "status": "ready",
        "items": [
            {
                "code": code,
                "action": "entry_pending",
                "signal_at": "2026-08-20T15:40:00+09:00",
                "current": payload["current"],
            }
            for code, payload in payloads.items()
        ],
        "preliminary_history": [],
    }
    monkeypatch.setattr(
        recommendations,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        recommendations,
        "load_quant_signal_payload",
        lambda _db, code, **_kwargs: payloads[str(code)],
    )
    monkeypatch.setattr(
        recommendations,
        "load_reference_quant_signal_payload",
        lambda _db, code, **_kwargs: payloads[str(code)],
    )


def _seed_prices(
    db: Session,
    code: str,
    name: str,
    latest_close: int,
    volume: int,
    *,
    sector=None,
    industry=None,
):
    db.add(
        StockMaster(
            code=code,
            name=name,
            market="KOSPI",
            sector=sector,
            industry=industry,
        )
    )
    start = date(2026, 3, 2)
    for offset in range(70):
        close = latest_close - (69 - offset) * 10
        db.add(
            DailyPrice(
                code=code,
                trade_date=start + timedelta(days=offset),
                open=close - 5,
                high=close + 20,
                low=close - 20,
                close=close,
                volume=volume,
                trading_value=None,
                market_cap=None,
                listed_shares=None,
            )
        )


def test_recommendations_fall_back_to_close_times_volume_without_market_cap(monkeypatch):
    _install_confirmed_entry_signals(monkeypatch, ["005930", "000660"])
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        _seed_prices(db, "000660", "SK하이닉스", 280000, 700_000)
        db.commit()

        payload = build_recommendations(
            db,
            limit=2,
            candidate_limit=10,
            refresh_live=True,
            ensure_signal_history=False,
        )

        assert payload["universe_count"] == 2
        assert payload["candidate_count"] == 2
        assert len(payload["items"]) == 2
        assert payload["selection_rule"] == "confirmed_entry_pending_or_entered_today"
        assert payload["qualified_count"] == 2
        assert all(item["trading_value"] for item in payload["items"])
        assert all(item["buy_condition_met"] is True for item in payload["items"])
        assert all(item["action"] == "신규 매수 대기" for item in payload["items"])
        assert all(item["ai_trade_signal"] for item in payload["items"])
        assert all(item["ai_trade_signal"]["entry_score_threshold"] == Decimal("62.00") for item in payload["items"])


def test_recommendations_keep_verified_candidates_when_live_enrichment_is_unavailable(monkeypatch):
    _install_confirmed_entry_signals(monkeypatch, ["005930"])
    monkeypatch.setattr(recommendations, "_uses_runtime_database", lambda _db: True)
    monkeypatch.setattr(recommendations, "_score_candidate", lambda *_args, **_kwargs: None)

    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        db.commit()

        payload = build_recommendations(
            db,
            limit=1,
            candidate_limit=10,
            refresh_live=True,
            ensure_signal_history=False,
        )

        assert payload["candidate_count"] == 1
        assert [item["code"] for item in payload["items"]] == ["005930"]
        assert payload["items"][0]["buy_condition_met"] is True
        assert any("1차 후보" in risk for risk in payload["items"][0]["risks"])


def test_recommendations_exclude_watch_holding_and_live_preliminary_states(monkeypatch):
    codes = ["100001", "100002", "100003", "100004", "100005"]
    confirmed = _confirmed_entry_signal(codes[0])

    def current_for(action: str, *, position_open: bool = False, live: bool = False):
        current = dict(confirmed["current"])
        current.update(
            {
                "action": action,
                "position_open": position_open,
                "live_observation": live,
            }
        )
        return current

    unconfirmed_pending = current_for("entry_pending")
    unconfirmed_pending["entry_confirmation"] = {
        "allowed": False,
        "state": "insufficient_support",
        "required_supports": 1,
        "supportive_count": 0,
    }
    snapshot = {
        "status": "ready",
        "items": [
            {"code": codes[0], "action": "entry_pending", "current": current_for("entry_pending")},
            {"code": codes[1], "action": "entry_watch", "current": current_for("entry_watch")},
            {"code": codes[2], "action": "holding", "current": current_for("holding", position_open=True)},
            {"code": codes[3], "action": "entry_pending", "current": current_for("entry_pending", live=True)},
            {"code": codes[4], "action": "entry_pending", "current": unconfirmed_pending},
        ],
        "preliminary_history": [],
    }
    monkeypatch.setattr(
        recommendations,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        recommendations,
        "load_quant_signal_payload",
        lambda *_args, **_kwargs: confirmed,
    )

    with _session() as db:
        for index, code in enumerate(codes):
            _seed_prices(db, code, f"조건종목{index}", 20_000 + index * 100, 500_000)
        db.commit()
        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=4,
            candidate_limit=10,
            refresh_live=False,
            ensure_signal_history=False,
        )

    assert payload["candidate_count"] == 1
    assert payload["qualified_count"] == 1
    assert [item["code"] for item in payload["items"]] == [codes[0]]
    assert payload["items"][0]["action"] == "신규 매수 대기"
    assert payload["items"][0]["buy_condition_met"] is True


def test_recommendations_keep_confirmed_entry_visible_on_its_execution_day(monkeypatch):
    entered = _entered_today_signal("100001")
    old_holding = _entered_today_signal("100002")
    old_holding["current"]["action"] = "holding"
    old_holding["current"]["entry_date"] = date(2026, 8, 31)
    old_holding["current"]["lifecycle"]["latest_transition"]["transition_date"] = "2026-08-31"
    payloads = {"100001": entered, "100002": old_holding}
    snapshot = {
        "status": "ready",
        "items": [
            {
                "code": code,
                "signal_at": "2026-08-31T15:40:00+09:00",
                "signal_date": "2026-08-31",
                "current": payload["current"],
            }
            for code, payload in payloads.items()
        ],
        "preliminary_history": [],
    }
    monkeypatch.setattr(
        recommendations,
        "_now_kst",
        lambda: datetime(2026, 9, 1, 9, 21, tzinfo=recommendations.KST),
    )
    monkeypatch.setattr(
        recommendations,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: snapshot,
    )
    monkeypatch.setattr(
        recommendations,
        "load_quant_signal_payload",
        lambda _db, code, **_kwargs: payloads[str(code)],
    )

    with _session() as db:
        _seed_prices(db, "100001", "오늘진입", 81_000, 500_000)
        _seed_prices(db, "100002", "과거보유", 82_000, 500_000)
        db.commit()
        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=2,
            candidate_limit=10,
            refresh_live=False,
            ensure_signal_history=False,
        )

    assert payload["candidate_count"] == 1
    assert payload["qualified_count"] == 1
    assert payload["pending_count"] == 0
    assert payload["entered_today_count"] == 1
    assert [item["code"] for item in payload["items"]] == ["100001"]
    item = payload["items"][0]
    assert item["recommendation_state"] == "entered_today"
    assert item["recommendation_label"] == "보유 유지"
    assert item["action"] == "보유 유지"
    assert "추가 매수보다 보유 기준" in item["decision_reason"]
    assert item["recommendation_entry_date"] == date(2026, 9, 1)
    assert item["strategy_entry_price"] == 80_700
    assert item["condition_price"] == item["price"]
    assert item["ai_trade_signal"]["current"]["position_open"] is True


def test_recommendations_only_expand_to_small_diversity_pool(monkeypatch):
    codes = [f"{100000 + idx:06d}" for idx in range(8)]
    _install_confirmed_entry_signals(monkeypatch, codes)
    with _session() as db:
        for idx in range(8):
            code = codes[idx]
            _seed_prices(db, code, f"종목{idx}", 10000 + idx * 500, 300_000 + idx * 50_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=2,
            candidate_limit=2,
            refresh_live=False,
            ensure_signal_history=False,
        )

        assert payload["candidate_count"] == 4
        assert len(payload["items"]) == 2


def test_fast_recommendations_only_score_observed_components_and_never_render_none_percent(monkeypatch):
    _install_confirmed_entry_signals(monkeypatch, ["005930"])
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=1,
            candidate_limit=10,
            refresh_live=False,
            ensure_signal_history=False,
        )
        item = payload["items"][0]

        assert set(item["component_scores"]) == {"price_momentum", "trading_value"}
        assert all("None%" not in reason for reason in item["reasons"])
        assert item["action"] == "신규 매수 대기"
        assert "매수" not in item["score_action"]
        assert item["ai_trade_signal"]["data_state"] == "ready"
        assert item["ai_trade_signal"]["current"]["levels"][0]["key"] == "entry"


def test_recommendations_backfill_signal_history_before_calculating_ai_stage(monkeypatch):
    _install_confirmed_entry_signals(monkeypatch, ["005930"])
    calls = []

    def ensure_history(
        _db,
        code,
        min_rows,
        lookback_days,
        *,
        require_recent_complete_ohlc,
    ):
        calls.append((code, min_rows, lookback_days, require_recent_complete_ohlc))
        return min_rows

    monkeypatch.setattr(recommendations, "ensure_stock_price_history", ensure_history)
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        db.commit()

        universe_cache.clear()
        build_recommendations(db, limit=1, candidate_limit=10, refresh_live=False)

    assert calls == [
        ("005930", recommendations.MIN_BACKTEST_HISTORY_ROWS, 600, True)
    ]


def test_recommendations_link_confirmed_entry_contract_and_released_preliminary(monkeypatch):
    signal_as_of = datetime(2026, 8, 20, 13, 8, tzinfo=recommendations.KST)
    signal_payload = _confirmed_entry_signal("005930")
    signal_payload["as_of"] = signal_as_of
    signal_payload["current"]["as_of"] = signal_as_of
    preliminary_snapshot = {
        "status": "ready",
        "items": [
            {
                "code": "005930",
                "action": "entry_pending",
                "signal_at": "2026-08-20T15:40:00+09:00",
                "current": signal_payload["current"],
            }
        ],
        "preliminary_history": [
            {
                "code": "005930",
                "side": "buy",
                "signal_date": "2026-08-20",
                "first_seen_at": "2026-08-20T09:35:00+09:00",
                "last_seen_at": "2026-08-20T10:05:00+09:00",
                "active": False,
                "price": 79_500,
                "score": "72.1",
                "reason": "장중 조건 해제",
            }
        ]
    }
    monkeypatch.setattr(recommendations, "load_quant_signal_payload", lambda *_args, **_kwargs: signal_payload)
    monkeypatch.setattr(recommendations, "load_reference_quant_signal_payload", lambda *_args, **_kwargs: signal_payload)
    monkeypatch.setattr(
        recommendations,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: preliminary_snapshot,
    )

    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80_000, 1_000_000)
        db.commit()
        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=1,
            candidate_limit=10,
            refresh_live=False,
            ensure_signal_history=False,
        )

    item = payload["items"][0]
    compact = item["ai_trade_signal"]
    assert item["recommended_at"] == payload["as_of"]
    assert item["recommendation_state"] == "entry_confirmed"
    assert item["buy_condition_met"] is True
    assert item["condition_price"] == item["price"]
    assert compact["current"]["lifecycle"]["state"] == "entry_pending"
    assert compact["current"]["position_open"] is False
    assert compact["current"]["entry_confirmation"]["allowed"] is True
    assert compact["current"]["levels"][0]["price"] == 80_500
    assert compact["display_return_rate"] is None
    assert compact["latest_preliminary"]["active"] is False
    assert compact["latest_preliminary"]["last_seen_at"] == "2026-08-20T10:05:00+09:00"
    validated = MarketRecommendationOut.model_validate(payload)
    assert validated.selection_rule == "confirmed_entry_pending_or_entered_today"
    assert validated.items[0].buy_condition_met is True
    assert validated.items[0].condition_price == validated.items[0].price
    assert validated.items[0].ai_trade_signal.current.lifecycle.state == "entry_pending"
    assert validated.items[0].ai_trade_signal.current.levels[0].price == 80_500


def test_recommendations_diversify_same_family_names_on_first_pass(monkeypatch):
    _install_confirmed_entry_signals(
        monkeypatch,
        ["005930", "032830", "000660", "035420"],
    )
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 2_000_000)
        _seed_prices(db, "032830", "삼성생명", 120000, 1_600_000)
        _seed_prices(db, "000660", "SK하이닉스", 280000, 900_000)
        _seed_prices(db, "035420", "NAVER", 230000, 850_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=3,
            candidate_limit=3,
            refresh_live=False,
            ensure_signal_history=False,
        )
        names = [str(item["name"]) for item in payload["items"]]

        assert len(payload["items"]) == 3
        assert sum(name.startswith("삼성") for name in names) == 1


def test_recommendations_limit_same_investment_sector_when_alternatives_exist(monkeypatch):
    codes = [f"10{index:04d}" for index in range(3)]
    codes.extend(f"20{index:04d}" for index in range(2))
    codes.append("300000")
    _install_confirmed_entry_signals(monkeypatch, codes)
    with _session() as db:
        for index in range(3):
            _seed_prices(
                db,
                f"10{index:04d}",
                f"칩기업{index}",
                20_000 + index * 100,
                1_000_000 - index * 10_000,
                sector="전기·전자",
                industry="반도체와반도체장비",
            )
        for index in range(2):
            _seed_prices(
                db,
                f"20{index:04d}",
                f"금융기업{index}",
                18_000 + index * 100,
                900_000 - index * 10_000,
                sector="금융",
                industry="은행",
            )
        _seed_prices(
            db,
            "300000",
            "소비기업",
            16_000,
            800_000,
            sector="음식료·담배",
            industry="식품",
        )
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=5,
            candidate_limit=6,
            refresh_live=False,
            ensure_signal_history=False,
        )

        sectors = [item["investment_sector"] for item in payload["items"]]
        assert len(sectors) == 5
        assert sectors.count("semiconductor") <= 2
        assert sectors.count("financials") <= 2
        assert "consumer" in sectors
