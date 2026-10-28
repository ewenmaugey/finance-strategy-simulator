from datetime import date, timedelta

import pytest

from sp500_strategy_simulator.config import StrategyConfig
from sp500_strategy_simulator.models import DailyBar
from sp500_strategy_simulator.simulation import simulate


def make_bars(symbol: str, closes: list[float]) -> list[DailyBar]:
    start = date(2024, 1, 2)
    return [
        DailyBar(
            symbol=symbol,
            session_date=start + timedelta(days=i),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1_000,
        )
        for i, close in enumerate(closes)
    ]


def test_simulate_buys_at_close_and_sells_at_next_open() -> None:
    bars = {"AAA": make_bars("AAA", [10, 11, 12, 13])}
    config = StrategyConfig(
        initial_capital=1_000,
        n_assets=1,
        momentum_lookback_days=2,
        momentum_skip_days=0,
        commission_rate=0,
    )

    trades = simulate(bars, config)

    assert [(trade.side, trade.price) for trade in trades] == [
        ("BUY", 12),
        ("SELL", 13),
        ("BUY", 13),
    ]
    assert trades[0].quantity == pytest.approx(1_000 / 12)


def test_simulation_charges_commission_on_both_sides() -> None:
    bars = {"AAA": make_bars("AAA", [10, 11, 12, 13])}
    config = StrategyConfig(
        initial_capital=1_000,
        n_assets=1,
        momentum_lookback_days=2,
        momentum_skip_days=0,
        commission_rate=0.01,
    )

    trades = simulate(bars, config)

    assert trades[0].commission == pytest.approx(1_000 / 1.01 * 0.01)
    assert trades[1].side == "SELL"
    assert trades[1].commission == pytest.approx(trades[1].price * trades[1].quantity * 0.01)


def test_last_session_does_not_open_an_unexitable_position() -> None:
    bars = {"AAA": make_bars("AAA", [10, 11, 12])}
    config = StrategyConfig(n_assets=1, momentum_lookback_days=2, momentum_skip_days=0)

    trades = simulate(bars, config)

    assert all(trade.session_date < bars["AAA"][-1].session_date for trade in trades)


def test_duplicate_session_is_rejected() -> None:
    bars = make_bars("AAA", [10, 11, 12])
    with pytest.raises(ValueError, match="duplicate session date"):
        simulate({"AAA": [*bars, bars[-1]]}, StrategyConfig())
