"""Verify the numerical behavior of portfolio performance metrics."""
import pandas as pd
import pytest

from trading.metrics import (
    total_return,
    annualized_return,
    annualized_volatility,
    sharpe_ratio,
    maximum_drawdown,
    calculate_metrics,
)


def test_total_return():

    equity = pd.Series(
        [100, 110, 120]
    )

    result = total_return(equity)

    assert result == pytest.approx(0.20)


def test_maximum_drawdown():

    equity = pd.Series(
        [
            100,
            120,
            90,
            100,
        ]
    )

    result = maximum_drawdown(equity)

    assert result == pytest.approx(-0.25)


def test_annualized_volatility():

    returns = pd.Series(
        [0.01, -0.01, 0.02, -0.02]
    )

    result = annualized_volatility(
        returns
    )

    assert result > 0


def test_sharpe_ratio():

    returns = pd.Series(
        [0.01] * 100
    )

    result = sharpe_ratio(
        returns
    )

    # Constant positive returns have zero
    # volatility, so the implementation returns 0.
    assert result == 0


def test_calculate_metrics():

    equity = pd.Series(
        [
            100,
            105,
            110,
            108,
            115,
        ]
    )

    metrics = calculate_metrics(
        equity
    )

    assert "total_return" in metrics
    assert "cagr" in metrics
    assert "volatility" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown" in metrics


def test_crypto_annualization():
    equity = pd.Series([100, 102, 101, 105, 104])
    equity_metrics = calculate_metrics(equity, periods_per_year=252)
    crypto_metrics = calculate_metrics(equity, periods_per_year=365)
    assert crypto_metrics["total_return"] == equity_metrics["total_return"]
    assert crypto_metrics["volatility"] / equity_metrics["volatility"] == pytest.approx((365 / 252) ** 0.5)
