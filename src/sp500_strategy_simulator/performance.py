"""Portfolio valuation and summary performance metrics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from math import sqrt

from sp500_strategy_simulator.models import DailyBar, Trade


@dataclass(frozen=True, slots=True)
class PortfolioValue:
    """Portfolio value marked to market at a session close."""

    session_date: date
    value: float


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    """Common summary statistics for a portfolio value series."""

    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    max_drawdown: float


def build_equity_curve(
    bars_by_symbol: Mapping[str, Sequence[DailyBar]],
    trades: Sequence[Trade],
    initial_capital: float,
) -> list[PortfolioValue]:
    """Mark portfolio to market at each date with available close prices.

    Trade commissions are deducted on their execution dates. Positions are
    tracked from BUY/SELL trades; a holding with no close on a session retains
    its last known close, rather than being silently valued at zero.
    """
    if initial_capital <= 0:
        raise ValueError("initial_capital must be greater than zero")
    prices: dict[str, dict[date, float]] = {}
    for symbol, bars in bars_by_symbol.items():
        prices[symbol] = {}
        for bar in bars:
            if bar.symbol != symbol:
                raise ValueError("mapping keys must match each bar's symbol")
            if bar.session_date in prices[symbol]:
                raise ValueError(f"duplicate session date for {symbol}: {bar.session_date}")
            prices[symbol][bar.session_date] = bar.close

    by_date: dict[date, list[Trade]] = {}
    dates = set()
    for trade in trades:
        if trade.symbol not in prices:
            raise ValueError(f"trade symbol {trade.symbol} has no market data")
        by_date.setdefault(trade.session_date, []).append(trade)
        dates.add(trade.session_date)
    dates.update(day for rows in prices.values() for day in rows)
    if not dates:
        return []

    cash = initial_capital
    holdings: dict[str, float] = {}
    last_close: dict[str, float] = {}
    curve: list[PortfolioValue] = []
    for day in sorted(dates):
        for symbol, rows in prices.items():
            if day in rows:
                last_close[symbol] = rows[day]
        for trade in by_date.get(day, []):
            notional = trade.price * trade.quantity
            if trade.side == "BUY":
                if cash + 1e-9 < notional + trade.commission:
                    raise ValueError("buy trade exceeds available cash")
                cash -= notional + trade.commission
                holdings[trade.symbol] = holdings.get(trade.symbol, 0.0) + trade.quantity
            elif trade.side == "SELL":
                held = holdings.get(trade.symbol, 0.0)
                if trade.quantity > held + 1e-9:
                    raise ValueError("sell trade exceeds held quantity")
                cash += notional - trade.commission
                remaining = held - trade.quantity
                if remaining <= 1e-9:
                    holdings.pop(trade.symbol, None)
                else:
                    holdings[trade.symbol] = remaining
            else:
                raise ValueError(f"unsupported trade side: {trade.side}")
        market_value = sum(
            quantity * last_close[symbol]
            for symbol, quantity in holdings.items()
            if symbol in last_close
        )
        curve.append(PortfolioValue(day, cash + market_value))
    return curve


def calculate_metrics(
    curve: Sequence[PortfolioValue],
    initial_capital: float,
    *,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> PerformanceMetrics:
    """Calculate returns, annualized volatility, Sharpe ratio and drawdown.

    ``initial_capital`` is the portfolio value immediately before the first
    observation. For a curve clipped to an evaluation window, pass the value at
    the preceding session as the anchor. Returns and risk-free rate are
    per-period arithmetic rates. Annualization uses the supplied number of
    periods per year. The return curve spans ``len(curve) - 1`` elapsed periods
    from the anchor; Sharpe is zero when returns have no volatility.
    """
    if initial_capital <= 0:
        raise ValueError("initial_capital must be greater than zero")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be greater than zero")
    if not curve:
        return PerformanceMetrics(0.0, 0.0, 0.0, 0.0, 0.0)
    values = [point.value for point in curve]
    if any(value <= 0 for value in values):
        raise ValueError("portfolio values must be greater than zero")
    total_return = values[-1] / initial_capital - 1.0
    elapsed_periods = max(len(values) - 1, 1)
    annualized_return = (
        (values[-1] / initial_capital) ** (periods_per_year / elapsed_periods) - 1.0
    )
    returns = [
        current / previous - 1.0
        for previous, current in zip([initial_capital, *values[:-1]], values)
    ]
    if len(returns) > 1:
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        volatility = sqrt(variance) * sqrt(periods_per_year)
    else:
        mean_return = returns[0]
        volatility = 0.0
    sharpe = (
        (mean_return - risk_free_rate) * periods_per_year / volatility
        if volatility > 0
        else 0.0
    )
    peak = initial_capital
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        max_drawdown = min(max_drawdown, value / peak - 1.0)
    return PerformanceMetrics(
        total_return,
        annualized_return,
        volatility,
        sharpe,
        max_drawdown,
    )
