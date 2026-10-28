"""Twelve Data market-data provider."""

from __future__ import annotations

import os
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import requests

from sp500_strategy_simulator.models import DailyBar


class TwelveDataError(RuntimeError):
    """Raised when Twelve Data cannot provide valid daily bars."""


class TwelveDataProvider:
    """Fetch daily OHLCV bars from Twelve Data's time-series endpoint."""

    endpoint = "https://api.twelvedata.com/time_series"

    def __init__(self, api_key: str | None = None, *, timeout: float = 30.0) -> None:
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY")
        if not self.api_key:
            raise ValueError("Provide api_key or set TWELVE_DATA_API_KEY")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        self.timeout = timeout

    def fetch_daily_bars(
        self,
        symbols: Iterable[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, list[DailyBar]]:
        """Fetch and return bars keyed by requested symbol, oldest first.

        Requests are made one symbol at a time to keep provider limits and error
        handling explicit. The API key is sent as a query parameter and is never
        included in raised error messages.
        """
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        requested = list(dict.fromkeys(symbol.strip() for symbol in symbols))
        if any(not symbol for symbol in requested):
            raise ValueError("symbols cannot contain empty values")

        results: dict[str, list[DailyBar]] = {}
        for symbol in requested:
            try:
                response = requests.get(
                    self.endpoint,
                    params={
                        "symbol": symbol,
                        "interval": "1day",
                        "start_date": start_date.isoformat(),
                        "end_date": end_date.isoformat(),
                        "order": "ASC",
                        "outputsize": 5000,
                        "apikey": self.api_key,
                    },
                    timeout=self.timeout,
                )
                response.raise_for_status()
                payload: Any = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise TwelveDataError(f"Failed to fetch daily bars for {symbol}") from exc

            if not isinstance(payload, dict) or "values" not in payload:
                message = payload.get("message", "unexpected response") if isinstance(payload, dict) else "unexpected response"
                raise TwelveDataError(f"Twelve Data error for {symbol}: {message}")

            try:
                bars = [
                    DailyBar(
                        symbol=symbol,
                        session_date=date.fromisoformat(row["datetime"][:10]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(float(row["volume"])),
                    )
                    for row in payload["values"]
                    if start_date <= date.fromisoformat(row["datetime"][:10]) <= end_date
                ]
                bars.sort(key=lambda bar: bar.session_date)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise TwelveDataError(f"Invalid daily-bar data for {symbol}") from exc
            if len({bar.session_date for bar in bars}) != len(bars):
                raise TwelveDataError(f"Duplicate daily-bar dates for {symbol}")
            results[symbol] = bars
        return results
