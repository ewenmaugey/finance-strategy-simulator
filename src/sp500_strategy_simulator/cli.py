"""Command-line interface for running a close-to-open strategy backtest."""

from __future__ import annotations

import argparse
import csv
from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path

from sp500_strategy_simulator.config import StrategyConfig
from sp500_strategy_simulator.data_provider import TwelveDataError, TwelveDataProvider
from sp500_strategy_simulator.performance import build_equity_curve, calculate_metrics
from sp500_strategy_simulator.simulation import simulate


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sp500-backtest",
        description="Run a daily close-to-next-open momentum backtest.",
    )
    parser.add_argument("--symbols", required=True, help="Comma-separated ticker symbols")
    parser.add_argument("--start", required=True, type=_parse_date, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, type=_parse_date, help="End date (YYYY-MM-DD)")
    parser.add_argument("--capital", type=float, default=10_000.0, help="Initial capital (default: 10000)")
    parser.add_argument("--assets", type=int, default=5, help="Number of assets to hold (default: 5)")
    parser.add_argument("--lookback", type=int, default=252, help="Momentum lookback in trading observations")
    parser.add_argument("--skip", type=int, default=21, help="Recent observations excluded from momentum")
    parser.add_argument("--commission", type=float, default=0.001, help="Commission rate per trade (default: 0.001)")
    parser.add_argument("--output-csv", type=Path, help="Optional path for the daily equity curve CSV")
    return parser


def _write_equity_curve(path: Path, curve: Sequence, initial_capital: float) -> None:
    """Write dated equity values and daily returns as a UTF-8 CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(("date", "portfolio_value", "daily_return"))
        previous = initial_capital
        for point in curve:
            daily_return = point.value / previous - 1.0
            writer.writerow((point.session_date.isoformat(), f"{point.value:.10f}", f"{daily_return:.10f}"))
            previous = point.value


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    symbols = list(dict.fromkeys(symbol.strip().upper() for symbol in args.symbols.split(",")))
    if not symbols or any(not symbol for symbol in symbols):
        parser.error("--symbols must contain non-empty ticker symbols")
    try:
        config = StrategyConfig(
            initial_capital=args.capital,
            n_assets=args.assets,
            momentum_lookback_days=args.lookback,
            momentum_skip_days=args.skip,
            commission_rate=args.commission,
            start_date=args.start,
            end_date=args.end,
        )
    except ValueError as exc:
        parser.error(str(exc))

    try:
        provider = TwelveDataProvider()
        # Calendar buffer provides enough trading observations for momentum warm-up.
        fetch_start = args.start - timedelta(days=max(args.lookback * 2, 30))
        bars = provider.fetch_daily_bars(symbols, fetch_start, args.end)
        trades = simulate(bars, config)
        full_curve = build_equity_curve(bars, trades, config.initial_capital)
        curve = [point for point in full_curve if args.start <= point.session_date <= args.end]
        metrics = calculate_metrics(curve, config.initial_capital)
    except (TwelveDataError, ValueError) as exc:
        parser.exit(2, f"Backtest failed: {exc}\n")

    if not curve:
        parser.exit(1, "No market data available for the requested period.\n")
    if args.output_csv:
        try:
            _write_equity_curve(args.output_csv, curve, config.initial_capital)
        except OSError as exc:
            parser.exit(2, f"Could not write CSV output: {exc}\n")
    print(f"Period: {curve[0].session_date} to {curve[-1].session_date}")
    print(f"Symbols requested: {len(symbols)} | Trades: {len(trades)}")
    print(f"Initial capital: {config.initial_capital:,.2f}")
    print(f"Final portfolio value: {curve[-1].value:,.2f}")
    print(f"Total return: {metrics.total_return:.2%}")
    print(f"Annualized return: {metrics.annualized_return:.2%}")
    print(f"Annualized volatility: {metrics.annualized_volatility:.2%}")
    print(f"Sharpe ratio: {metrics.sharpe_ratio:.3f}")
    print(f"Maximum drawdown: {metrics.max_drawdown:.2%}")
    if args.output_csv:
        print(f"Equity curve CSV: {args.output_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
