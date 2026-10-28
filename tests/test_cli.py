from datetime import date

import pytest

from sp500_strategy_simulator import cli
from sp500_strategy_simulator.models import DailyBar
from sp500_strategy_simulator.performance import PortfolioValue


def test_parser_parses_required_arguments_and_defaults() -> None:
    args = cli.build_parser().parse_args(
        ["--symbols", "aapl, msft", "--start", "2024-01-02", "--end", "2024-02-01"]
    )
    assert args.start == date(2024, 1, 2)
    assert args.end == date(2024, 2, 1)
    assert args.capital == 10_000.0
    assert args.lookback == 252


def test_main_runs_backtest_and_prints_metrics(monkeypatch, capsys) -> None:
    bars = {
        "AAPL": [
            DailyBar("AAPL", date(2024, 1, 2), 10, 10, 10, 10, 100),
            DailyBar("AAPL", date(2024, 1, 3), 11, 11, 11, 11, 100),
        ]
    }

    class FakeProvider:
        def __init__(self):
            pass

        def fetch_daily_bars(self, symbols, start_date, end_date):
            assert symbols == ["AAPL"]
            return bars

    monkeypatch.setattr(cli, "TwelveDataProvider", FakeProvider)
    monkeypatch.setattr(cli, "simulate", lambda data, config: [])
    monkeypatch.setattr(
        cli,
        "build_equity_curve",
        lambda data, trades, capital: [
            PortfolioValue(date(2024, 1, 2), capital),
            PortfolioValue(date(2024, 1, 3), capital),
        ],
    )
    monkeypatch.setattr(cli, "calculate_metrics", lambda curve, capital: type("Metrics", (), {
        "total_return": 0.0,
        "annualized_return": 0.0,
        "annualized_volatility": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
    })())

    assert cli.main(["--symbols", "aapl", "--start", "2024-01-02", "--end", "2024-01-03"]) == 0
    assert "Final portfolio value: 10,000.00" in capsys.readouterr().out


def test_invalid_date_uses_argparse_error() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--symbols", "AAPL", "--start", "not-a-date", "--end", "2024-01-03"])
    assert exc.value.code == 2
