"""Verify signal generation and parameter validation for trading strategies."""
import numpy as np
import pandas as pd
import pytest

from trading.strategy import (
    MovingAverageStrategy,
    MomentumStrategy,
    RSIStrategy,
    EMACrossoverStrategy,
    MACDStrategy,
    BollingerBandsStrategy,
    DonchianBreakoutStrategy,
    BuyAndHoldStrategy,
)


def create_test_data(
    prices: list[float],
) -> pd.DataFrame:

    dates = pd.date_range(
        start="2025-01-01",
        periods=len(prices),
        freq="D",
    )

    return pd.DataFrame(
        {
            "Open": prices,
            "High": [p + 1 for p in prices],
            "Low": [p - 1 for p in prices],
            "Close": prices,
            "Volume": [1000] * len(prices),
        },
        index=dates,
    )


def test_moving_average_strategy_creates_signal():

    prices = list(range(1, 101))

    data = create_test_data(prices)

    strategy = MovingAverageStrategy(
        fast=5,
        slow=20,
    )

    result = strategy.generate_signals(data)

    assert "fast_ma" in result.columns
    assert "slow_ma" in result.columns
    assert "signal" in result.columns


def test_moving_average_strategy_has_long_signal():

    prices = list(range(1, 101))

    data = create_test_data(prices)

    strategy = MovingAverageStrategy(
        fast=5,
        slow=20,
    )

    result = strategy.generate_signals(data)

    # In a strongly increasing market,
    # the fast MA should eventually be above
    # the slow MA.
    assert result["signal"].iloc[-1] == 1


def test_moving_average_invalid_parameters():

    with pytest.raises(ValueError):

        MovingAverageStrategy(
            fast=50,
            slow=20,
        )


def test_momentum_strategy():

    prices = list(range(1, 101))

    data = create_test_data(prices)

    strategy = MomentumStrategy(
        lookback=10,
    )

    result = strategy.generate_signals(data)

    assert "momentum" in result.columns
    assert "signal" in result.columns

    assert result["signal"].iloc[-1] == 1


def test_rsi_strategy_creates_rsi():

    prices = (
        list(range(100, 50, -1))
        + list(range(50, 100))
    )

    data = create_test_data(prices)

    strategy = RSIStrategy(
        period=14,
    )

    result = strategy.generate_signals(data)

    assert "rsi" in result.columns
    assert "signal" in result.columns


def test_rsi_values_are_reasonable():

    prices = (
        list(range(100, 50, -1))
        + list(range(50, 100))
    )

    data = create_test_data(prices)

    strategy = RSIStrategy()

    result = strategy.generate_signals(data)

    rsi = result["rsi"].dropna()

    assert (rsi >= 0).all()
    assert (rsi <= 100).all()


def test_rsi_exits_after_recovery():
    data = create_test_data(list(range(100, 50, -1)) + list(range(50, 101)))
    signals = RSIStrategy().generate_signals(data)
    assert signals.signal.iloc[40] == 1
    assert signals.signal.iloc[-1] == 0
    assert signals.loc[signals.rsi > 70, "signal"].eq(0).all()


@pytest.mark.parametrize("strategy", [EMACrossoverStrategy(3, 6), MACDStrategy(3, 6, 3), BollingerBandsStrategy(5, 1), DonchianBreakoutStrategy(5, 3), BuyAndHoldStrategy()])
def test_new_strategies_do_not_use_future_prices(strategy):
    data = create_test_data([100, 101, 99, 102, 103, 100, 98, 95, 100, 104, 106, 105, 99, 94, 101])
    prefix = strategy.generate_signals(data.iloc[:10]).signal
    full = strategy.generate_signals(data).signal
    pd.testing.assert_series_equal(prefix, full.iloc[:10])
    assert full.isin([0, 1]).all()


def test_breakout_enters_and_exits():
    signals = DonchianBreakoutStrategy(3, 2).generate_signals(create_test_data([100, 101, 102, 103, 104, 90]))
    assert list(signals.signal) == [0, 0, 0, 1, 1, 0]


def test_bollinger_recovery_exit():
    signals = BollingerBandsStrategy(4, 1).generate_signals(create_test_data([100, 100, 100, 100, 80, 85, 100]))
    assert signals.signal.iloc[4] == 1
    assert signals.signal.iloc[5] == 1
    assert signals.signal.iloc[6] == 0


@pytest.mark.parametrize("strategy", [EMACrossoverStrategy(3, 6), MACDStrategy(3, 6, 3)])
def test_ema_based_strategies_follow_trend(strategy):
    signals = strategy.generate_signals(create_test_data(list(range(100, 160)) + list(range(160, 100, -1))))
    assert signals.signal.iloc[40] == 1
    assert signals.signal.iloc[-1] == 0
