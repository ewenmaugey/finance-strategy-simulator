import pytest

from sp500_strategy_simulator.config import StrategyConfig


def test_default_config_represents_daily_close_to_next_open_strategy() -> None:
    config = StrategyConfig()

    assert config.n_assets == 5
    assert config.momentum_lookback_days == 252
    assert config.momentum_skip_days == 21
    assert config.initial_capital > 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"initial_capital": 0},
        {"n_assets": 0},
        {"momentum_lookback_days": 0},
        {"momentum_lookback_days": 10, "momentum_skip_days": 10},
        {"momentum_skip_days": -1},
        {"commission_rate": 1},
    ],
)
def test_invalid_config_is_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        StrategyConfig(**kwargs)
