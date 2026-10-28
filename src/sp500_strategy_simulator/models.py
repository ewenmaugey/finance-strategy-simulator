"""Core domain models shared by data providers and the backtest engine."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class DailyBar:
    """One asset's daily OHLCV data, with prices in one consistent currency."""

    symbol: str
    session_date: date
    open: float
    high: float
    low: float
    close: float
    volume: int

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty")
        for field_name in ("open", "high", "low", "close"):
            value = getattr(self, field_name)
            if value <= 0:
                raise ValueError(f"{field_name} must be greater than zero")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be at least as large as open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be no greater than open, close, and high")
        if self.volume < 0:
            raise ValueError("volume cannot be negative")


@dataclass(frozen=True, slots=True)
class Trade:
    """A simulated execution at a specific session and market price."""

    symbol: str
    session_date: date
    side: str
    price: float
    quantity: float
    commission: float

    def __post_init__(self) -> None:
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be 'BUY' or 'SELL'")
        if self.price <= 0:
            raise ValueError("price must be greater than zero")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        if self.commission < 0:
            raise ValueError("commission cannot be negative")
