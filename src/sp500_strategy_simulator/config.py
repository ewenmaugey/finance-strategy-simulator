"""Validated configuration for the daily close-to-open strategy."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Parameters that define one reproducible backtest run.

    At each session close, select the highest-ranked eligible assets, buy them
    at that close, and sell those positions at the next session's open.
    """

    initial_capital: float = 10_000.0
    n_assets: int = 5
    momentum_lookback_days: int = 252
    momentum_skip_days: int = 21
    commission_rate: float = 0.001
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero")
        if self.n_assets <= 0:
            raise ValueError("n_assets must be greater than zero")
        if self.momentum_lookback_days <= 0:
            raise ValueError("momentum_lookback_days must be greater than zero")
        if not 0 <= self.momentum_skip_days < self.momentum_lookback_days:
            raise ValueError(
                "momentum_skip_days must be non-negative and smaller than "
                "momentum_lookback_days"
            )
        if not 0 <= self.commission_rate < 1:
            raise ValueError("commission_rate must be in [0, 1)")
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.start_date > self.end_date
        ):
            raise ValueError("start_date must be on or before end_date")
