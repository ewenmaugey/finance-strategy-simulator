"""Twelve Data market-data provider."""

from __future__ import annotations

import math
import os
from collections.abc import Iterable
from datetime import date
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
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and greater than zero")
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

            if not isinstance(payload, dict):
                raise TwelveDataError(f"Unexpected response from Twelve Data for {symbol}")
            if payload.get("status") == "error" or "values" not in payload:
                message = payload.get("message", "unexpected response")
                raise TwelveDataError(f"Twelve Data error for {symbol}: {message}")
            if not isinstance(payload["values"], list):
                raise TwelveDataError(f"Invalid daily-bar data for {symbol}")

            bars: list[DailyBar] = []
            try:
                for row in payload["values"]:
                    if not isinstance(row, dict):
                        raise ValueError("daily-bar row must be an object")
                    session_date = date.fromisoformat(row["datetime"][:10])
                    if not start_date <= session_date <= end_date:
                        continue
                    prices = {
                        field: float(row[field])
                        for field in ("open", "high", "low", "close")
                    }
                    volume_value = float(row["volume"])
                    if not math.isfinite(volume_value) or not volume_value.is_integer():
                        raise ValueError("volume must be a finite integer")
                    if volume_value < 0:
                        raise ValueError("volume cannot be negative")
                    if any(not math.isfinite(value) for value in prices.values()):
                        raise ValueError("prices must be finite")
                    bars.append(
                        DailyBar(
                            symbol=symbol,
                            session_date=session_date,
                            **prices,
                            volume=int(volume_value),
                        )
                    )
                bars.sort(key=lambda bar: bar.session_date)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise TwelveDataError(f"Invalid daily-bar data for {symbol}") from exc
            if len({bar.session_date for bar in bars}) != len(bars):
                raise TwelveDataError(f"Duplicate daily-bar dates for {symbol}")
            results[symbol] = bars
        return results
