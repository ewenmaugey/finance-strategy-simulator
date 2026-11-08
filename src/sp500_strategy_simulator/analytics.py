"""Statistical validation and quantitative analytics tools.

Provides:
- Monte Carlo simulation via daily return bootstrapping.
- Parameter sensitivity grid evaluations.
- Walk-Forward Analysis helpers.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import pandas as pd

from sp500_strategy_simulator.performance import PortfolioValue


@dataclass(frozen=True)
class MonteCarloResult:
    """Summary and percentile paths from a Monte Carlo simulation."""

    n_simulations: int
    median_final_value: float
    p5_final_value: float
    p25_final_value: float
    p75_final_value: float
    p95_final_value: float
    prob_negative_return: float
    median_max_drawdown: float
    p95_max_drawdown: float
    percentile_curves: dict[str, list[float]]  # 'p5', 'p25', 'p50', 'p75', 'p95'
    dates: list[str]
    simulated_trajectories: list[list[float]]

    @property
    def percentile_95(self) -> list[float]:
        return self.percentile_curves.get("p95", [])

    @property
    def percentile_50(self) -> list[float]:
        return self.percentile_curves.get("p50", [])

    @property
    def percentile_5(self) -> list[float]:
        return self.percentile_curves.get("p5", [])

    @property
    def worst_drawdown_p50(self) -> float:
        return self.median_max_drawdown


def _compute_max_drawdown_series(values: Sequence[float]) -> float:
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        elif peak > 0:
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd
    return max_dd


def run_monte_carlo(
    curve: Sequence[PortfolioValue],
    initial_capital: float,
    n_simulations: int = 500,
    seed: int = 42,
) -> MonteCarloResult | None:
    """Run a bootstrap Monte Carlo simulation on the daily returns of an equity curve."""
    if len(curve) < 5:
        return None

    # Calculate daily returns
    daily_returns: list[float] = []
    prev_val = curve[0].value
    for pt in curve[1:]:
        ret = (pt.value - prev_val) / prev_val if prev_val > 0 else 0.0
        daily_returns.append(ret)
        prev_val = pt.value

    if not daily_returns:
        return None

    rng = random.Random(seed)
    n_days = len(daily_returns)
    simulated_final_values: list[float] = []
    simulated_max_dds: list[float] = []
    all_trajectories: list[list[float]] = []

    for _ in range(n_simulations):
        sampled_returns = [rng.choice(daily_returns) for _ in range(n_days)]
        trajectory = [initial_capital]
        current_val = initial_capital
        for r in sampled_returns:
            current_val = max(0.0, current_val * (1.0 + r))
            trajectory.append(current_val)

        simulated_final_values.append(current_val)
        simulated_max_dds.append(_compute_max_drawdown_series(trajectory))
        all_trajectories.append(trajectory)

    simulated_final_values.sort()
    simulated_max_dds.sort()

    def get_percentile(sorted_list: list[float], pct: float) -> float:
        idx = int(len(sorted_list) * pct)
        return sorted_list[min(idx, len(sorted_list) - 1)]

    # Compute percentiles for each step to plot cone of probabilities
    p5_path: list[float] = []
    p25_path: list[float] = []
    p50_path: list[float] = []
    p75_path: list[float] = []
    p95_path: list[float] = []

    for day_idx in range(n_days + 1):
        vals_at_day = sorted(traj[day_idx] for traj in all_trajectories)
        p5_path.append(get_percentile(vals_at_day, 0.05))
        p25_path.append(get_percentile(vals_at_day, 0.25))
        p50_path.append(get_percentile(vals_at_day, 0.50))
        p75_path.append(get_percentile(vals_at_day, 0.75))
        p95_path.append(get_percentile(vals_at_day, 0.95))

    prob_neg = sum(1 for v in simulated_final_values if v < initial_capital) / n_simulations
    dates = [curve[0].session_date.isoformat()] + [pt.session_date.isoformat() for pt in curve[1:]]

    return MonteCarloResult(
        n_simulations=n_simulations,
        median_final_value=get_percentile(simulated_final_values, 0.50),
        p5_final_value=get_percentile(simulated_final_values, 0.05),
        p25_final_value=get_percentile(simulated_final_values, 0.25),
        p75_final_value=get_percentile(simulated_final_values, 0.75),
        p95_final_value=get_percentile(simulated_final_values, 0.95),
        prob_negative_return=prob_neg,
        median_max_drawdown=get_percentile(simulated_max_dds, 0.50),
        p95_max_drawdown=get_percentile(simulated_max_dds, 0.95),
        percentile_curves={
            "p5": p5_path,
            "p25": p25_path,
            "p50": p50_path,
            "p75": p75_path,
            "p95": p95_path,
        },
        dates=dates,
        simulated_trajectories=all_trajectories,
    )


def run_parameter_sensitivity(
    eval_fn: Callable[[float | int, float | int], float],
    param1_name: str,
    param1_values: Sequence[float | int],
    param2_name: str,
    param2_values: Sequence[float | int],
) -> pd.DataFrame:
    """Evaluate an objective metric over a 2D parameter grid.

    Returns a pandas DataFrame where index is param1 and columns are param2.
    """
    matrix: dict[str, list[float]] = {}
    row_labels = [f"{param1_name}={v}" for v in param1_values]

    for p2 in param2_values:
        col_name = f"{param2_name}={p2}"
        matrix[col_name] = []
        for p1 in param1_values:
            score = eval_fn(p1, p2)
            matrix[col_name].append(round(score, 2))

    return pd.DataFrame(matrix, index=row_labels)


def run_walk_forward_split(
    dates: Sequence[str],
    n_splits: int = 3,
    train_ratio: float = 0.7,
) -> list[tuple[list[str], list[str]]]:
    """Generate sequential train/test date slices for walk-forward evaluation."""
    if len(dates) < n_splits * 2:
        return []

    splits = []
    chunk_size = len(dates) // n_splits
    for i in range(n_splits):
        window = dates[: (i + 1) * chunk_size]
        split_point = int(len(window) * train_ratio)
        train_dates = list(window[:split_point])
        test_dates = list(window[split_point:])
        if train_dates and test_dates:
            splits.append((train_dates, test_dates))

    return splits
