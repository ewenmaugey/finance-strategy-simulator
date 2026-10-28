"""Cross-sectional momentum ranking for close-to-open strategy decisions."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sp500_strategy_simulator.models import DailyBar


@dataclass(frozen=True, slots=True)
class MomentumScore:
    """A symbol's momentum score at a decision session."""

    symbol: str
    score: float


def rank_by_momentum(
    bars: Iterable[DailyBar],
    decision_date: date,
    lookback_days: int = 252,
    skip_days: int = 21,
) -> list[MomentumScore]:
    """Rank eligible symbols by trailing momentum, excluding recent sessions.

    ``lookback_days`` and ``skip_days`` count trading observations, not calendar
    days. For a decision on session t, the score is close[t - skip_days - 1] /
    close[t - lookback_days - 1] - 1. The decision-session close is therefore
    available to the strategy, but excluded from the signal by the skip window.
    A symbol is eligible only when both endpoint observations exist, its latest
    bar is exactly on ``decision_date``, and all its supplied bars are valid and
    unique by session date. Ties are broken by symbol for deterministic output.
    """
    if lookback_days <= 0:
        raise ValueError("lookback_days must be greater than zero")
    if not 0 <= skip_days < lookback_days:
        raise ValueError("skip_days must be non-negative and smaller than lookback_days")

    by_symbol: dict[str, list[DailyBar]] = {}
    for bar in bars:
        by_symbol.setdefault(bar.symbol, []).append(bar)

    ranked: list[MomentumScore] = []
    for symbol, symbol_bars in by_symbol.items():
        ordered = sorted(symbol_bars, key=lambda bar: bar.session_date)
        dates = [bar.session_date for bar in ordered]
        if len(dates) != len(set(dates)):
            raise ValueError(f"duplicate session dates for {symbol}")
        if not ordered or ordered[-1].session_date != decision_date:
            continue
        start_index = len(ordered) - lookback_days - 1
        end_index = len(ordered) - skip_days - 1
        if start_index < 0 or end_index < 0:
            continue
        start_close = ordered[start_index].close
        end_close = ordered[end_index].close
        ranked.append(MomentumScore(symbol, end_close / start_close - 1.0))

    return sorted(ranked, key=lambda item: (-item.score, item.symbol))
