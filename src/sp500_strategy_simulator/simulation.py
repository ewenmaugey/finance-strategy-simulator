"""Portfolio simulation for daily close-to-next-open momentum strategies."""

from collections.abc import Mapping, Sequence
from datetime import date

from sp500_strategy_simulator.config import StrategyConfig
from sp500_strategy_simulator.models import DailyBar, Trade
from sp500_strategy_simulator.ranking import rank_by_momentum


def simulate(
    bars_by_symbol: Mapping[str, Sequence[DailyBar]],
    config: StrategyConfig,
) -> list[Trade]:
    """Return trades for a daily close-to-next-open strategy.

    Each session, available cash is allocated equally across the top-ranked
    eligible assets at the close. Those positions are sold at the next session's
    open. Commissions (percentage or fixed per order) are charged on both sides;
    fractional shares are allowed.
    A missing next-session open skips that symbol's sale and makes it ineligible
    for the next purchase while held. The final session never opens new positions.
    """
    by_symbol = {symbol: tuple(bars) for symbol, bars in bars_by_symbol.items()}
    if any(bar.symbol != symbol for symbol, bars in by_symbol.items() for bar in bars):
        raise ValueError("mapping keys must match each bar's symbol")

    dates = sorted(
        {
            bar.session_date
            for bars in by_symbol.values()
            for bar in bars
            if (config.start_date is None or bar.session_date >= config.start_date)
            and (config.end_date is None or bar.session_date <= config.end_date)
        }
    )
    if len(dates) < 2:
        return []

    indexed: dict[str, dict[date, DailyBar]] = {}
    for symbol, bars in by_symbol.items():
        rows: dict[date, DailyBar] = {}
        for bar in bars:
            if bar.session_date in rows:
                raise ValueError(f"duplicate session date for {symbol}: {bar.session_date}")
            rows[bar.session_date] = bar
        indexed[symbol] = rows

    cash = config.initial_capital
    trades: list[Trade] = []
    held: dict[str, float] = {}

    for i, current_date in enumerate(dates):
        # Exit prior positions at the next session open. Missing bars are
        # conservatively marked unsold; do not silently invent an execution.
        sold_this_session = False
        for symbol, quantity in list(held.items()):
            bar = indexed[symbol].get(current_date)
            if bar is not None:
                proceeds = quantity * bar.open
                fee = proceeds * config.commission_rate + config.fixed_commission
                cash += proceeds - fee
                trades.append(Trade(symbol, current_date, "SELL", bar.open, quantity, fee))
                sold_this_session = True
                del held[symbol]

        # The final session does not open an unexitable position if no position was
        # unwound during this session.
        if i == len(dates) - 1 and not sold_this_session:
            continue

        # The ranking API consumes a flat iterable of bars and returns
        # MomentumScore objects. Include only observations up to this session.
        ranking_input = (
            bar
            for symbol, bars in by_symbol.items()
            if symbol in indexed and current_date in indexed[symbol]
            for bar in bars
            if bar.session_date <= current_date
        )
        ranked = rank_by_momentum(
            ranking_input,
            current_date,
            config.momentum_lookback_days,
            config.momentum_skip_days,
        )
        selected = [item.symbol for item in ranked if item.symbol not in held][: config.n_assets]
        if not selected:
            continue

        n_selected = len(selected)
        total_fixed_fees = n_selected * config.fixed_commission
        if cash <= total_fixed_fees:
            continue

        cash_available_for_positions = cash - total_fixed_fees
        gross_per_asset = cash_available_for_positions / (n_selected * (1 + config.commission_rate))

        for symbol in selected:
            bar = indexed[symbol][current_date]
            quantity = gross_per_asset / bar.close
            fee = gross_per_asset * config.commission_rate + config.fixed_commission
            cash -= gross_per_asset + fee
            held[symbol] = quantity
            trades.append(Trade(symbol, current_date, "BUY", bar.close, quantity, fee))

    return trades
