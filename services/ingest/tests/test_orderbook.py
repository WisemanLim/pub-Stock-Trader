"""F1.2 호가창 API 시험."""
from unittest.mock import patch

MOCK_PRICE = {
    "ticker": "005930",
    "price": 73500.0,
    "change": 0.021,
    "change_pct": 0.021,
    "volume": 1_200_000,
    "timestamp": "2024-01-08T00:00:00",
    "source": "FinanceDataReader",
}


def test_orderbook_ok(client):
    with patch("app.services.orderbook._fdr.get_price", return_value=MOCK_PRICE):
        r = client.get("/orderbook/005930")
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "005930"
    assert len(data["ask_levels"]) == 10
    assert len(data["bid_levels"]) == 10
    assert data["spread"] > 0
    assert data["mid_price"] > 0
    assert data["source"] == "simulated"


def test_orderbook_20_levels(client):
    with patch("app.services.orderbook._fdr.get_price", return_value=MOCK_PRICE):
        r = client.get("/orderbook/005930?levels=20")
    assert r.status_code == 200
    assert len(r.json()["ask_levels"]) == 20


def test_orderbook_ask_prices_ascending(client):
    with patch("app.services.orderbook._fdr.get_price", return_value=MOCK_PRICE):
        r = client.get("/orderbook/005930")
    asks = [l["price"] for l in r.json()["ask_levels"]]
    assert asks == sorted(asks)


def test_orderbook_bid_prices_descending(client):
    with patch("app.services.orderbook._fdr.get_price", return_value=MOCK_PRICE):
        r = client.get("/orderbook/005930")
    bids = [l["price"] for l in r.json()["bid_levels"]]
    assert bids == sorted(bids, reverse=True)


def test_orderbook_not_found(client):
    with patch(
        "app.services.orderbook._fdr.get_price",
        side_effect=ValueError("No data for ticker: INVALID"),
    ):
        r = client.get("/orderbook/INVALID")
    assert r.status_code == 404
