from datetime import date

import pytest

from sp500_strategy_simulator.models import DailyBar, Trade
from sp500_strategy_simulator.performance import (
    PortfolioValue,
    build_equity_curve,
    calculate_metrics,
)


def bar(day: int, close: float) -> DailyBar:
    return DailyBar("AAA", date(2024, 1, day), close, close, close, close, 100)


def test_equity_curve_accounts_for_trades_and_commission() -> None:
    bars = {"AAA": [bar(2, 110), bar(3, 120)]}
    trades = [
        Trade("AAA", date(2024, 1, 2), "BUY", 100, 1, 1),
        Trade("AAA", date(2024, 1, 3), "SELL", 115, 1, 1),
    ]

    curve = build_equity_curve(bars, trades, 1_000)

    assert [point.value for point in curve] == pytest.approx([1_009, 1_013])


def test_metrics_known_values_and_drawdown() -> None:
    curve = [
        PortfolioValue(date(2024, 1, 1), 100),
        PortfolioValue(date(2024, 1, 2), 110),
        PortfolioValue(date(2024, 1, 3), 99),
    ]

    metrics = calculate_metrics(curve, 100, periods_per_year=2)

    assert metrics.total_return == pytest.approx(-0.01)
    assert metrics.max_drawdown == pytest.approx(-0.1)
    assert metrics.annualized_volatility > 0


def test_metrics_use_evaluation_anchor_for_total_and_annualized_return() -> None:
    curve = [
        PortfolioValue(date(2024, 1, 2), 120),
        PortfolioValue(date(2024, 1, 3), 132),
    ]

    metrics = calculate_metrics(curve, 110, periods_per_year=2)

    assert metrics.total_return == pytest.approx(0.2)
    assert metrics.annualized_return == pytest.approx(0.44)


def test_empty_curve_has_zero_metrics() -> None:
    assert calculate_metrics([], 10_000) == calculate_metrics([], 10_000)


def test_invalid_metrics_input_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_metrics([PortfolioValue(date(2024, 1, 1), 0)], 100)
