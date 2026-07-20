from typing import Optional

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.integrations.toss import TossInvestClient, sync_toss_holdings, sync_toss_orders
from app.models import BrokerAccount, BrokerHolding, BrokerOrder


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: Optional[dict] = None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls: list[dict] = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "data": data,
                "headers": headers,
            }
        )
        return FakeResponse(
            200,
            {
                "access_token": "test-token",
                "token_type": "Bearer",
                "expires_in": 86400,
            },
        )

    def request(self, method, url, headers=None, params=None, json=None, timeout=None):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": headers,
                "params": params,
                "json": json,
            }
        )
        if url.endswith("/api/v1/holdings"):
            return FakeResponse(
                200,
                {
                    "result": {
                        "totalPurchaseAmount": {"krw": "6500000", "usd": None},
                        "marketValue": {
                            "amount": {"krw": "7200000", "usd": None},
                            "amountAfterCost": {"krw": "7050000", "usd": None},
                        },
                        "profitLoss": {
                            "amount": {"krw": "700000", "usd": None},
                            "amountAfterCost": {"krw": "550000", "usd": None},
                            "rate": "0.1077",
                            "rateAfterCost": "0.0846",
                        },
                        "dailyProfitLoss": {
                            "amount": {"krw": "100000", "usd": None},
                            "rate": "0.0141",
                        },
                        "items": [],
                    }
                },
            )
        raise AssertionError(f"Unexpected request to {url}")


class FakeTossClient:
    def get_accounts(self):
        return [
            {
                "accountNo": "12345678901",
                "accountSeq": 1,
                "accountType": "BROKERAGE",
            }
        ]

    def get_holdings(self, account_seq: int, symbol=None):
        assert account_seq == 1
        return {
            "totalPurchaseAmount": {"krw": "6500000", "usd": None},
            "marketValue": {
                "amount": {"krw": "7200000", "usd": None},
                "amountAfterCost": {"krw": "7050000", "usd": None},
            },
            "profitLoss": {
                "amount": {"krw": "700000", "usd": None},
                "amountAfterCost": {"krw": "550000", "usd": None},
                "rate": "0.1077",
                "rateAfterCost": "0.0846",
            },
            "dailyProfitLoss": {
                "amount": {"krw": "100000", "usd": None},
                "rate": "0.0141",
            },
            "items": [
                {
                    "symbol": "005930",
                    "name": "삼성전자",
                    "marketCountry": "KR",
                    "currency": "KRW",
                    "quantity": "100",
                    "lastPrice": "72000",
                    "averagePurchasePrice": "65000",
                    "marketValue": {
                        "purchaseAmount": "6500000",
                        "amount": "7200000",
                        "amountAfterCost": "7050000",
                    },
                    "profitLoss": {
                        "amount": "700000",
                        "amountAfterCost": "550000",
                        "rate": "0.1077",
                        "rateAfterCost": "0.0846",
                    },
                    "dailyProfitLoss": {"amount": "100000", "rate": "0.0141"},
                    "cost": {"commission": "14400", "tax": "135600"},
                }
            ],
        }

    def get_orders(self, account_seq: int, status="OPEN", cursor=None, limit=None):
        assert account_seq == 1
        assert status == "OPEN"
        return {
            "orders": [
                {
                    "orderId": "ord-1",
                    "symbol": "005930",
                    "side": "BUY",
                    "orderType": "LIMIT",
                    "timeInForce": "DAY",
                    "status": "PENDING",
                    "price": "70000",
                    "quantity": "10",
                    "orderAmount": None,
                    "currency": "KRW",
                    "orderedAt": "2026-06-17T09:30:00+09:00",
                    "canceledAt": None,
                    "execution": {
                        "filledQuantity": "0",
                        "averageFilledPrice": None,
                        "filledAmount": None,
                        "commission": None,
                        "tax": None,
                        "filledAt": None,
                        "settlementDate": None,
                    },
                }
            ],
            "nextCursor": None,
            "hasNext": False,
        }


def test_toss_client_uses_bearer_and_account_header():
    settings = Settings(
        toss_client_id="client-id",
        toss_client_secret="client-secret",
        toss_base_url="https://openapi.tossinvest.com",
    )
    session = FakeSession()
    client = TossInvestClient(settings=settings, session=session)

    client.get_holdings(1)

    assert session.calls[0]["url"].endswith("/oauth2/token")
    assert session.calls[1]["headers"]["Authorization"] == "Bearer test-token"
    assert session.calls[1]["headers"]["X-Tossinvest-Account"] == "1"


def test_sync_toss_holdings_persists_accounts_and_items():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        count = sync_toss_holdings(
            db,
            settings=Settings(),
            client=FakeTossClient(),
        )
        assert count == 1
        assert db.scalar(select(func.count()).select_from(BrokerAccount)) == 1
        assert db.scalar(select(func.count()).select_from(BrokerHolding)) == 1

        account = db.scalar(select(BrokerAccount))
        assert str(account.market_value_krw) == "7200000.00000000"
        holding = db.scalar(select(BrokerHolding))
        assert holding.symbol == "005930"
        assert str(holding.quantity) == "100.00000000"


def test_sync_toss_orders_persists_open_orders():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        count = sync_toss_orders(
            db,
            settings=Settings(),
            client=FakeTossClient(),
            status="OPEN",
        )
        assert count == 1
        assert db.scalar(select(func.count()).select_from(BrokerOrder)) == 1
        order = db.scalar(select(BrokerOrder))
        assert order.order_id == "ord-1"
        assert order.status == "PENDING"
