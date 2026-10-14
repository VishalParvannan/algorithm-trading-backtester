"""
End-to-end tests for the Backtester engine.

These tests use synthetic price data (no network access) to verify that the
engine orchestrates strategy -> portfolio -> metrics correctly and that the
look-ahead guard shifts signals as expected.
"""

import numpy as np
import pandas as pd
import pytest

from src.backtester import Backtester, BacktestResult
from src.strategy import (
    MovingAverageStrategy,
    MomentumStrategy,
    RSIStrategy,
)


def make_data(n: int = 300, seed: int = 42) -> pd.DataFrame:
    """Generate a synthetic trending price series."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(
        start="2020-01-01",
        periods=n,
        freq="B",
    )
    close = 100.0 * np.cumprod(1 + rng.normal(0.0005, 0.015, size=n))
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1000.0,
        },
        index=dates,
    )


@pytest.mark.parametrize(
    "strategy",
    [
        MovingAverageStrategy(fast=10, slow=30),
        MomentumStrategy(lookback=20),
        RSIStrategy(period=14),
    ],
)
def test_backtest_runs_and_returns_result(strategy, data):
    result = Backtester(strategy=strategy).run(data)

    assert isinstance(result, BacktestResult)
    assert len(result.equity_curve) == len(data)
    assert result.equity_curve.index.equals(data.index)
    assert result.initial_capital == 10_000
    assert result.strategy_name == strategy.__class__.__name__
    assert isinstance(result.metrics, dict)
    assert "total_return" in result.metrics
    assert "sharpe_ratio" in result.metrics
    assert "max_drawdown" in result.metrics
    assert result.n_trades == len(result.trade_history)


def test_initial_capital_preserved(data):
    result = Backtester(
        strategy=MovingAverageStrategy(fast=10, slow=30),
        initial_capital=5_000,
    ).run(data)

    assert result.initial_capital == 5_000
    assert result.equity_curve.iloc[0] == pytest.approx(5_000)


def test_zero_signal_means_no_trades(data):
    """A strategy that never fires should produce zero trades and flat equity."""
    class FlatStrategy(MovingAverageStrategy):
        def generate_signals(self, data):
            signals = super().generate_signals(data)
            signals["signal"] = 0
            return signals

    result = Backtester(strategy=FlatStrategy(fast=10, slow=30)).run(data)

    assert result.n_trades == 0
    assert result.equity_curve.iloc[0] == pytest.approx(result.equity_curve.iloc[-1])


def test_benchmark_alignment(data):
    benchmark = pd.Series(
        data["Close"].values,
        index=data.index,
        name="Close",
    )

    result = Backtester(
        strategy=MovingAverageStrategy(fast=10, slow=30),
        benchmark=benchmark,
    ).run(data)

    assert result.benchmark is not None
    assert "benchmark_return" in result.metrics
    assert len(result.benchmark) == len(data)


def test_benchmark_dataframe(data):
    benchmark_df = pd.DataFrame(
        {"Close": data["Close"].values},
        index=data.index,
    )

    result = Backtester(
        strategy=MovingAverageStrategy(fast=10, slow=30),
        benchmark=benchmark_df,
    ).run(data)

    assert result.benchmark is not None
    assert "benchmark_return" in result.metrics


def test_shift_signals_prevents_lookahead(data):
    """With shift_signals=True the first bar should never trade."""
    result = Backtester(
        strategy=MovingAverageStrategy(fast=10, slow=30),
        shift_signals=True,
    ).run(data)

    # The first bar has no prior signal, so no trade can execute on day 1.
    assert result.trade_history.empty or (
        result.trade_history["timestamp"].min() > data.index[0]
    )


def test_invalid_data_raises(data):
    empty = pd.DataFrame()
    with pytest.raises(ValueError):
        Backtester(strategy=MovingAverageStrategy(fast=10, slow=30)).run(empty)


def test_duplicate_index_raises(data):
    dup = data.iloc[[0, 0, 1, 2]].copy()
    with pytest.raises(ValueError):
        Backtester(strategy=MovingAverageStrategy(fast=10, slow=30)).run(dup)


def test_missing_close_raises(data):
    bad = data.drop(columns=["Close"])
    with pytest.raises(ValueError):
        Backtester(strategy=MovingAverageStrategy(fast=10, slow=30)).run(bad)


def test_print_report_returns_string(data):
    result = Backtester(
        strategy=MovingAverageStrategy(fast=10, slow=30),
    ).run(data)

    report = result.print_report()
    assert isinstance(report, str)
    assert "Strategy:" in report
    assert "Total return:" in report


def test_profit_factor(data):
    result = Backtester(
        strategy=MovingAverageStrategy(fast=10, slow=30),
    ).run(data)

    pf = result.profit_factor()
    if result.n_trades > 0:
        assert pf is not None
        assert np.isfinite(pf) or np.isinf(pf)


@pytest.fixture
def data():
    return make_data()