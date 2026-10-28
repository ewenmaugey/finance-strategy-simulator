from datetime import date, timedelta

import pytest

from sp500_strategy_simulator.models import DailyBar
from sp500_strategy_simulator.ranking import rank_by_momentum


def bars_for(symbol: str, closes: list[float]) -> list[DailyBar]:
    start = date(2024, 1, 1)
    result = []
    for index, close in enumerate(closes):
        session = start + timedelta(days=index)
        result.append(
            DailyBar(
                symbol=symbol,
                session_date=session,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1,
            )
        )
    return result


def test_ranks_using_lookback_and_skip_endpoint_closes() -> None:
    decision = date(2024, 1, 5)
    bars = bars_for("AAA", [100, 110, 120, 130, 100])
    ranked = rank_by_momentum(bars, decision, lookback_days=4, skip_days=1)

    # Uses close[3] / close[0] - 1; close[4] is the decision close.
    assert [item.symbol for item in ranked] == ["AAA"]
    assert ranked[0].score == pytest.approx(0.3)


def test_omits_symbols_without_full_history_or_decision_bar() -> None:
    decision = date(2024, 1, 5)
    bars = bars_for("SHORT", [10, 11, 12, 13])
    bars += bars_for("STALE", [10, 11, 12, 13])
    ranked = rank_by_momentum(bars, decision, lookback_days=4, skip_days=1)

    assert ranked == []


def test_ties_are_broken_by_symbol_and_order_is_deterministic() -> None:
    decision = date(2024, 1, 4)
    bars = bars_for("ZZZ", [10, 11, 12, 13])
    bars += bars_for("AAA", [10, 11, 12, 13])

    ranked = rank_by_momentum(bars, decision, lookback_days=3, skip_days=0)

    assert [item.symbol for item in ranked] == ["AAA", "ZZZ"]


@pytest.mark.parametrize(
    ("lookback", "skip"),
    [(0, 0), (3, 3), (3, -1)],
)
def test_rejects_invalid_windows(lookback: int, skip: int) -> None:
    with pytest.raises(ValueError):
        rank_by_momentum([], date(2024, 1, 1), lookback, skip)


def test_rejects_duplicate_symbol_dates() -> None:
    duplicate = bars_for("AAA", [10, 11])
    duplicate.append(duplicate[-1])

    with pytest.raises(ValueError, match="duplicate session dates"):
        rank_by_momentum(duplicate, date(2024, 1, 2), lookback_days=1, skip_days=0)
