"""Twelve Data market-data provider."""

from __future__ import annotations

import math
import os
import time
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

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout: float = 30.0,
        rate_limit_delay: float = 8.0,
    ) -> None:
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY")
        if not self.api_key:
            raise ValueError("Provide api_key or set TWELVE_DATA_API_KEY")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and greater than zero")
        if not math.isfinite(rate_limit_delay) or rate_limit_delay < 0:
            raise ValueError("rate_limit_delay must be a non-negative finite number")
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay

    def fetch_daily_bars(
        self,
        symbols: Iterable[str],
        start_date: date,
        end_date: date,
    ) -> dict[str, list[DailyBar]]:
        """Fetch and return bars keyed by requested symbol, oldest first.

        Requests are made one symbol at a time to keep provider limits and error
        handling explicit. A rate limit pause is observed between queries.
        """
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        requested = list(dict.fromkeys(symbol.strip() for symbol in symbols))
        if any(not symbol for symbol in requested):
            raise ValueError("symbols cannot contain empty values")

        results: dict[str, list[DailyBar]] = {}
        total = len(requested)

        for index, symbol in enumerate(requested):
            # Pause between requests to respect Twelve Data's rate limit (8 req/min for free tier)
            if index > 0 and self.rate_limit_delay > 0:
                time.sleep(self.rate_limit_delay)

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
                if response.status_code == 429:
                    raise TwelveDataError(
                        f"Limite d'appels API atteinte (erreur 429) pour '{symbol}'. "
                        "Le plan gratuit de Twelve Data autorise un maximum de 8 requêtes par minute et 800 par jour. "
                        "Veuillez patienter 1 minute ou réduire le nombre de symboles."
                    )
                response.raise_for_status()
                payload: Any = response.json()
            except requests.RequestException as exc:
                raise TwelveDataError(f"Échec de la connexion à Twelve Data pour '{symbol}': {exc}") from exc
            except ValueError as exc:
                raise TwelveDataError(f"Réponse invalide de Twelve Data pour '{symbol}'") from exc

            if not isinstance(payload, dict):
                raise TwelveDataError(f"Réponse inattendue de Twelve Data pour '{symbol}'")

            # Handle Twelve Data API error messages (including quota/limit in JSON payload)
            if payload.get("status") == "error" or "values" not in payload:
                code = payload.get("code")
                message = payload.get("message", "réponse inattendue")
                if code == 429 or "limit" in message.lower():
                    raise TwelveDataError(
                        f"Limite d'appels API atteinte pour '{symbol}' : {message}. "
                        "Veuillez patienter 1 minute avant de relancer."
                    )
                raise TwelveDataError(f"Erreur Twelve Data pour '{symbol}': {message}")

            if not isinstance(payload["values"], list):
                raise TwelveDataError(f"Données de chandeliers quotidiennes invalides pour '{symbol}'")

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
                raise TwelveDataError(f"Données corrompues pour '{symbol}'") from exc
            if len({bar.session_date for bar in bars}) != len(bars):
                raise TwelveDataError(f"Dates en double détectées pour '{symbol}'")
            results[symbol] = bars

        return results
