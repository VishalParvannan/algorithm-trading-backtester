"""Calculate return, annual growth, volatility, Sharpe ratio, and drawdown."""
import numpy as np
import pandas as pd


def total_return(
    equity_curve: pd.Series,
) -> float:
    """
    Calculate total portfolio return.
    """

    if len(equity_curve) < 2:
        return 0.0

    return (
        equity_curve.iloc[-1] /
        equity_curve.iloc[0]
        - 1
    )


def annualized_return(
    equity_curve: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate CAGR.
    """

    if len(equity_curve) < 2:
        return 0.0

    number_of_periods = len(equity_curve) - 1

    years = (
        number_of_periods /
        periods_per_year
    )
    # Missing observations must not shorten the apparent investment horizon.
    if isinstance(equity_curve.index, pd.DatetimeIndex):
        years = (equity_curve.index[-1] - equity_curve.index[0]).total_seconds() / (365.25 * 86400)

    if years <= 0:
        return 0.0

    return (
        equity_curve.iloc[-1] /
        equity_curve.iloc[0]
    ) ** (1 / years) - 1


def annualized_volatility(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate annualized volatility.
    """

    return (
        returns.std() *
        np.sqrt(periods_per_year)
    )


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate annualized Sharpe ratio.

    risk_free_rate is expressed annually.
    """

    if returns.std() < np.finfo(float).eps:
        return 0.0

    daily_risk_free = (
        (1 + risk_free_rate)
        ** (1 / periods_per_year)
        - 1
    )

    excess_returns = (
        returns - daily_risk_free
    )

    return (
        excess_returns.mean() /
        excess_returns.std()
    ) * np.sqrt(periods_per_year)


def maximum_drawdown(
    equity_curve: pd.Series,
) -> float:
    """
    Calculate maximum drawdown.
    """

    running_max = (
        equity_curve
        .cummax()
    )

    drawdown = (
        equity_curve /
        running_max
        - 1
    )

    return drawdown.min()


def calculate_metrics(
    equity_curve: pd.Series,
    benchmark: pd.Series | None = None,
    periods_per_year: int = 252,
) -> dict:
    """
    Calculate a collection of performance metrics.
    """

    returns = equity_curve.pct_change().dropna()

    metrics = {
        "total_return": total_return(
            equity_curve
        ),

        "cagr": annualized_return(
            equity_curve, periods_per_year
        ),

        "volatility": annualized_volatility(
            returns, periods_per_year
        ),

        "sharpe_ratio": sharpe_ratio(
            returns, periods_per_year=periods_per_year
        ),

        "max_drawdown": maximum_drawdown(
            equity_curve
        ),
    }

    if benchmark is not None:
        metrics["benchmark_return"] = (
            total_return(benchmark)
        )

    return metrics


def format_metrics(
    metrics: dict,
) -> str:
    """
    Convert metrics into a readable report.
    """

    lines = []

    lines.append("=" * 40)
    lines.append("       BACKTEST RESULTS")
    lines.append("=" * 40)

    if "total_return" in metrics:
        lines.append(
            f"Total Return:      "
            f"{metrics['total_return']:.2%}"
        )

    if "cagr" in metrics:
        lines.append(
            f"CAGR:              "
            f"{metrics['cagr']:.2%}"
        )

    if "volatility" in metrics:
        lines.append(
            f"Volatility:        "
            f"{metrics['volatility']:.2%}"
        )

    if "sharpe_ratio" in metrics:
        lines.append(
            f"Sharpe Ratio:      "
            f"{metrics['sharpe_ratio']:.2f}"
        )

    if "max_drawdown" in metrics:
        lines.append(
            f"Max Drawdown:      "
            f"{metrics['max_drawdown']:.2%}"
        )

    if "benchmark_return" in metrics:
        lines.append(
            f"Benchmark Return:  "
            f"{metrics['benchmark_return']:.2%}"
        )

    lines.append("=" * 40)

    return "\n".join(lines)
