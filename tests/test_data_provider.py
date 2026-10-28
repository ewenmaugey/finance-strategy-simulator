from datetime import date

import pytest
import requests

from sp500_strategy_simulator.data_provider import TwelveDataError, TwelveDataProvider


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError("bad status")

    def json(self):
        return self.payload


def test_fetch_daily_bars_maps_and_sorts_provider_rows(monkeypatch):
    calls = []

    def fake_get(url, *, params, timeout):
        calls.append((url, params, timeout))
        return FakeResponse({"values": [
            {"datetime": "2024-01-03", "open": "12", "high": "13", "low": "11", "close": "12.5", "volume": "100"},
            {"datetime": "2024-01-02", "open": "10", "high": "12", "low": "9", "close": "11", "volume": "90"},
        ]})

    monkeypatch.setattr(requests, "get", fake_get)
    provider = TwelveDataProvider("test-key")
    result = provider.fetch_daily_bars(["ABC", "ABC"], date(2024, 1, 1), date(2024, 1, 5))

    assert list(result) == ["ABC"]
    assert [bar.session_date for bar in result["ABC"]] == [date(2024, 1, 2), date(2024, 1, 3)]
    assert result["ABC"][0].close == 11
    assert calls[0][1]["apikey"] == "test-key"
    assert calls[0][2] == 30.0


def test_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    with pytest.raises(ValueError, match="TWELVE_DATA_API_KEY"):
        TwelveDataProvider()


def test_provider_rejects_api_error_without_exposing_key(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse({"status": "error", "message": "Invalid API key"}))
    provider = TwelveDataProvider("secret")
    with pytest.raises(TwelveDataError, match="Invalid API key") as exc:
        provider.fetch_daily_bars(["ABC"], date(2024, 1, 1), date(2024, 1, 2))
    assert "secret" not in str(exc.value)


def test_provider_rejects_invalid_date_range():
    provider = TwelveDataProvider("test-key")
    with pytest.raises(ValueError, match="on or before"):
        provider.fetch_daily_bars(["ABC"], date(2024, 1, 2), date(2024, 1, 1))


@pytest.mark.parametrize(
    "bad_row",
    [
        {"datetime": "2024-01-02", "open": "nan", "high": "13", "low": "11", "close": "12", "volume": "10"},
        {"datetime": "2024-01-02", "open": "10", "high": "13", "low": "11", "close": "inf", "volume": "10"},
        {"datetime": "2024-01-02", "open": "14", "high": "13", "low": "11", "close": "12", "volume": "10"},
        {"datetime": "2024-01-02", "open": "10", "high": "13", "low": "11", "close": "12", "volume": "1.5"},
        {"datetime": "2024-01-02", "open": "10", "high": "13", "low": "11", "close": "12", "volume": "-1"},
    ],
)
def test_provider_rejects_invalid_ohlcv_rows(monkeypatch, bad_row):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse({"values": [bad_row]}))
    provider = TwelveDataProvider("test-key")

    with pytest.raises(TwelveDataError, match="Invalid daily-bar data"):
        provider.fetch_daily_bars(["ABC"], date(2024, 1, 1), date(2024, 1, 5))


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0, -1])
def test_provider_rejects_non_positive_or_non_finite_timeout(timeout):
    with pytest.raises(ValueError, match="timeout"):
        TwelveDataProvider("test-key", timeout=timeout)


@pytest.mark.parametrize("values", [None, {}, "bad"])
def test_provider_rejects_invalid_values_container(monkeypatch, values):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse({"values": values}))
    provider = TwelveDataProvider("test-key")

    with pytest.raises(TwelveDataError, match="Invalid daily-bar data"):
        provider.fetch_daily_bars(["ABC"], date(2024, 1, 1), date(2024, 1, 5))
