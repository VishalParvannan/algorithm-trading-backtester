"""
Backtester engine and result container.

This module orchestrates the full backtest loop: strategy signals ->
portfolio execution -> equity curve -> performance metrics.
"""

from dataclasses import dataclass, field
from concurrent.futures import CancelledError
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from .metrics import (
    calculate_metrics,
    format_metrics,
)
from .portfolio import Portfolio
from .strategy import Strategy


@dataclass
class BacktestResult:
    """
    Immutable summary of a completed backtest.
    """

    equity_curve: pd.Series
    """Daily portfolio value indexed by date."""
    returns: pd.Series
    """Daily percentage returns of the equity curve."""
    trade_history: pd.DataFrame
    """All executed trades with price, quantity, commission and slippage."""
    metrics: dict
    """Performance metrics (total return, CAGR, Sharpe, max drawdown...)."""
    initial_capital: float
    """Capital deployed at the start of the backtest."""
    commission: float
    """Per-trade commission as a fraction of trade value."""
    slippage: float
    """Per-trade slippage as a fraction of trade value."""
    strategy_name: str
    """Readable strategy identifier."""
    n_trades: int = field(init=False)
    """Number of executed trades (derived)."""
    benchmark: Optional[pd.Series] = None
    """Benchmark value curve, if a benchmark was supplied."""

    def __post_init__(self) -> None:
        if not isinstance(self.trade_history, pd.DataFrame):
            self.trade_history = pd.DataFrame(self.trade_history)
        self.n_trades = len(self.trade_history)

    def total_return(self) -> float:
        return self.metrics["total_return"]

    def cagr(self) -> float:
        return self.metrics["cagr"]

    def volatility(self) -> float:
        return self.metrics["volatility"]

    def sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        return self.metrics["sharpe_ratio"]

    def max_drawdown(self) -> float:
        return self.metrics["max_drawdown"]

    def profit_factor(self):
        from .analysis import completed_trades
        _, summary = completed_trades(self.trade_history)
        if summary.get('profit_factor_no_losses'):
            return float('inf')
        return summary.get('profit_factor')

    def print_report(self) -> str:
        """Return a formatted text summary of the results."""
        factor = self.profit_factor()
        lines = [
            f"Strategy:     {self.strategy_name}",
            f"Backtest period: {self.equity_curve.index[0].date()} -> {self.equity_curve.index[-1].date()}",
            f"Initial capital: ${self.initial_capital:,.2f}",
            f"Final value:     ${self.equity_curve.iloc[-1]:,.2f}",
            f"Total return:    {self.total_return():+.2%}",
            f"CAGR:            {self.cagr():+.2%}",
            f"Volatility:      {self.volatility():.2%}",
            f"Sharpe ratio:    {self.sharpe_ratio():.2f}",
            f"Max drawdown:    {self.max_drawdown():+.2%}",
            f"Trades executed: {self.n_trades}",
            f"Profit factor:   {factor:.2f}" if factor is not None else "Profit factor:   N/A (no closed trades)",
        ]
        if self.benchmark is not None and "benchmark_return" in self.metrics:
            lines.append(
                f"Benchmark return: {self.metrics['benchmark_return']:+.2%}"
            )
        return "\n".join(lines)

    def plot(
        self,
        figsize: tuple[int, int] = (14, 10),
        save_path: Optional[str] = None,
        title: Optional[str] = None,
        show_trades: bool = True,
        show_benchmark: bool = True,
        style: str = "default",
    ) -> None:
        """
        Plot the equity curve (with benchmark if provided) and the drawdown.

        Enhanced visualization with professional styling, trade markers, and metrics display.

        Parameters
        ----------
        figsize : tuple[int, int], default (14, 10)
            Figure size in inches (width, height)
        save_path : str, optional
            Path to save the figure. If None, displays interactively
        title : str, optional
            Custom title for the plot
        show_trades : bool, default True
            Whether to show trade entry/exit markers on equity curve
        show_benchmark : bool, default True
            Whether to show benchmark comparison (if available)
        style : str, default "default"
            Plot style (currently only "default" supported)
        """
        # Set up professional style
        plt.style.use('default')  # Use matplotlib defaults as base

        # Define professional color palette (colorblind-friendly)
        colors = {
            'strategy': '#2E86AB',      # Professional blue
            'benchmark': '#F24236',     # Professional red
            'drawdown': '#F6C56C',      # Warm yellow
            'buy_marker': '#00C853',    # Green for buys
            'sell_marker': '#ff4444',   # Red for sells
            'grid': '#E0E0E0',          # Light gray for grid
            'text': '#212121',          # Dark gray for text
            'background': '#FAFAFA'     # Off-white background
        }

        # Create figure with improved layout
        fig = plt.figure(figsize=figsize, facecolor=colors['background'])
        gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 0.5], hspace=0.4)
        ax1 = fig.add_subplot(gs[0])  # Equity curve
        ax2 = fig.add_subplot(gs[1], sharex=ax1)  # Drawdown
        ax3 = fig.add_subplot(gs[2])  # Metrics text box

        # Set main title
        fig.suptitle(
            title or f"{self.strategy_name} - Backtest Result",
            fontsize=18,
            fontweight='bold',
            color=colors['text'],
            y=0.95
        )

        # Equity curve
        ax1.plot(
            self.equity_curve.index,
            self.equity_curve.values,
            label="Strategy",
            color=colors['strategy'],
            linewidth=2.5,
        )

        if show_benchmark and self.benchmark is not None:
            ax1.plot(
                self.benchmark.index,
                self.benchmark.values * self.initial_capital,
                label="Benchmark",
                color=colors['benchmark'],
                linewidth=2.5,
                linestyle="--",
                alpha=0.8
            )

        # Add trade markers if requested and trade history exists
        if show_trades and hasattr(self, 'trade_history') and not self.trade_history.empty:
            buy_trades = self.trade_history[self.trade_history['quantity'] > 0]
            sell_trades = self.trade_history[self.trade_history['quantity'] < 0]
            if 'timestamp' in self.trade_history:
                buy_trades = buy_trades.set_index('timestamp')
                sell_trades = sell_trades.set_index('timestamp')

            # Buy markers (green triangles pointing up)
            if not buy_trades.empty:
                # Find indices that exist in both trade history and equity curve
                valid_buy_indices = buy_trades.index.intersection(self.equity_curve.index)
                if not valid_buy_indices.empty:
                    ax1.scatter(
                        valid_buy_indices,
                        [self.equity_curve.loc[idx] for idx in valid_buy_indices],
                        marker='^',
                        color=colors['buy_marker'],
                        s=100,
                        label='Buy',
                        alpha=0.8,
                        edgecolors='white',
                        linewidth=1
                    )

            # Sell markers (red triangles pointing down)
            if not sell_trades.empty:
                # Find indices that exist in both trade history and equity curve
                valid_sell_indices = sell_trades.index.intersection(self.equity_curve.index)
                if not valid_sell_indices.empty:
                    ax1.scatter(
                        valid_sell_indices,
                        [self.equity_curve.loc[idx] for idx in valid_sell_indices],
                        marker='v',
                        color=colors['sell_marker'],
                        s=100,
                        label='Sell',
                        alpha=0.8,
                        edgecolors='white',
                        linewidth=1
                    )

        ax1.set_ylabel("Portfolio Value ($)", fontsize=12, fontweight='bold', color=colors['text'])
        ax1.set_title("Equity Curve", fontsize=14, fontweight='bold', pad=20, color=colors['text'])
        ax1.legend(loc='upper left', frameon=True, fancybox=True, shadow=True, fontsize=10)
        ax1.grid(True, color=colors['grid'], alpha=0.6, linestyle='-', linewidth=0.5)
        ax1.set_facecolor('white')

        # Format y-axis for currency
        ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

        # Drawdown
        running_max = self.equity_curve.cummax()
        drawdown = (self.equity_curve / running_max - 1) * 100
        ax2.fill_between(
            drawdown.index,
            0,
            drawdown.values,
            color=colors['drawdown'],
            alpha=0.7,
        )
        ax2.set_ylabel("Drawdown (%)", fontsize=12, fontweight='bold', color=colors['text'])
        ax2.set_title("Drawdown", fontsize=14, fontweight='bold', pad=20, color=colors['text'])
        ax2.grid(True, color=colors['grid'], alpha=0.6, linestyle='-', linewidth=0.5)
        ax2.set_facecolor('white')
        ax2.axhline(0, color=colors['text'], linewidth=1, alpha=0.8)

        # Format y-axis for percentages
        ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x:.1f}%'))

        # Add metrics text box
        ax3.axis('off')
        if hasattr(self, 'metrics') and self.metrics:
            metrics_text = (
                f"Total Return: {self.metrics.get('total_return', 0):+.2%}    "
                f"CAGR: {self.metrics.get('cagr', 0):+.2%}    "
                f"Sharpe: {self.metrics.get('sharpe_ratio', 0):.2f}    "
                f"Max DD: {self.metrics.get('max_drawdown', 0):+.2%}"
            )
            ax3.text(
                0.5, 0.5, metrics_text,
                transform=ax3.transAxes,
                fontsize=11,
                ha='center',
                va='center',
                bbox=dict(
                    boxstyle='round,pad=0.5',
                    facecolor=colors['background'],
                    edgecolor=colors['grid'],
                    alpha=0.8
                )
            )

        # Improve date formatting on x-axis
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right', fontsize=9)

        # Adjust layout - manual adjustment for gridspec compatibility
        fig.subplots_adjust(left=0.1, bottom=0.1, right=0.95, top=0.9, hspace=0.4)

        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight', facecolor=fig.get_facecolor())

        plt.show()


class Backtester:
    """
    Orchestrates a backtest end to end.
    """

    def __init__(
        self,
        strategy: Strategy,
        initial_capital: float = 10_000,
        commission: float = 0.001,
        slippage: float = 0.0005,
        benchmark: Optional[pd.Series | pd.DataFrame | None] = None,
        shift_signals: bool = True,
        periods_per_year: int = 252,
        execution_price: str = "Close",
        fractional_shares: bool = True,
        allocation: float = 1.0,
        cancel_check=None,
    ):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.shift_signals = shift_signals
        if periods_per_year <= 0:
            raise ValueError("Periods per year must be positive.")
        self.periods_per_year = periods_per_year
        if execution_price not in {"Open", "Close"}:
            raise ValueError("Execution price must be Open or Close.")
        if execution_price == "Open" and not shift_signals:
            raise ValueError("Next-open execution requires delayed signals.")
        if not np.isfinite(allocation) or not 0 < allocation <= 1:
            raise ValueError("Allocation must be between 0 and 1.")
        self.execution_price = execution_price
        self.fractional_shares = fractional_shares
        self.allocation = allocation
        self.cancel_check = cancel_check

        if benchmark is None:
            self.benchmark: Optional[pd.Series] = None
        elif isinstance(benchmark, pd.DataFrame):
            self.benchmark = benchmark["Close"].copy()
        else:
            self.benchmark = benchmark.copy()

    @staticmethod
    def _validate_data(data: pd.DataFrame) -> None:
        """Sanity-check the input market data."""
        if data.empty:
            raise ValueError("Input data is empty.")
        if data.index.has_duplicates:
            raise ValueError("Data index contains duplicate dates.")
        if not pd.api.types.is_datetime64_any_dtype(data.index):
            raise ValueError("Data index must be datetime-like.")
        if not data.index.is_monotonic_increasing:
            raise ValueError("Data index must be sorted ascending.")
        if "Close" not in data.columns:
            raise ValueError("Data must contain a 'Close' column.")

    @staticmethod
    def _validate_signals(signals: pd.DataFrame) -> pd.DataFrame:
        """Ensure the strategy produced a usable 0/1 signal column."""
        if "signal" not in signals.columns:
            raise ValueError(
                "Strategy must return a DataFrame with a 'signal' column."
            )

        unique_signals = set(signals["signal"].dropna().unique())
        if not unique_signals.issubset({0, 1}):
            raise ValueError(
                f"Signal column must contain only 0 or 1, got: {unique_signals}"
            )
        return signals

    def _align_benchmark(self, data: pd.DataFrame) -> Optional[pd.Series]:
        """
        Align benchmark price series with the strategy data dates and
        convert to a compounded growth curve starting at 1.0.
        """
        if self.benchmark is None:
            return None

        bench = self.benchmark.copy()
        if isinstance(bench.index, pd.MultiIndex):
            bench.index = bench.index.droplevel(-1)

        common = data.index.intersection(bench.index)
        if len(common) == 0:
            raise ValueError(
                "No overlapping dates between strategy data and benchmark."
            )

        bench = bench.loc[common].dropna().reindex(common)
        if bench.isna().any():
            bench = bench.ffill().bfill().fillna(1.0)

        curve = bench / bench.iloc[0]
        curve = curve.reindex(common)
        curve = curve.ffill().bfill().fillna(1.0)
        curve.index = common
        return curve

    def _build_positions(
        self, signals: pd.DataFrame, data: pd.DataFrame
    ) -> pd.Series:
        """
        Turn the strategy's signal column into long-only target positions
        (0 = cash, 1 = fully invested), shifted to remove look-ahead.
        """
        positions = signals["signal"].reindex(data.index).fillna(0).round(0)

        if self.shift_signals:
            positions = positions.shift(1)

        # Treat any remaining NaN / out-of-range as zero (no position).
        positions = positions.fillna(0).clip(lower=0, upper=1).astype(int)
        return positions

    def run(self, data: pd.DataFrame) -> BacktestResult:
        """
        Run the backtest and return a BacktestResult.

        Parameters
        ----------
        data : pd.DataFrame
            Historical OHLCV market data, indexed by datetime. The `Close`
            column is required; signals are produced by the strategy.

        Returns
        -------
        BacktestResult
            Immutable results including equity curve, trades and metrics.
        """
        self._validate_data(data)
        if self.execution_price not in data:
            raise ValueError("Next-open fills require an Open column. Use Yahoo, Coinbase, Alpha Vantage, or an OHLC CSV.")
        signals = self.strategy.generate_signals(data)
        signals = self._validate_signals(signals)

        positions = self._build_positions(signals, data)

        benchmark_curve = self._align_benchmark(data)
        benchmark = (
            benchmark_curve.reindex(data.index)
            .ffill()
            .bfill()
            .fillna(1.0)
            if benchmark_curve is not None
            else None
        )

        portfolio = Portfolio(
            initial_capital=self.initial_capital,
            commission=self.commission,
            slippage=self.slippage,
            fractional_shares=self.fractional_shares,
        )

        equity_curve = []
        for date in data.index:
            if self.cancel_check and self.cancel_check():
                raise CancelledError("Backtest cancelled.")
            row = data.loc[date]
            target = positions.loc[date]

            # Defensive: only trade on clear 0/1 positions.
            if target not in (0, 1):
                continue

            portfolio.execute_target_position(
                target_position=target * self.allocation,
                price=float(row[self.execution_price]),
                timestamp=date,
            )
            equity_curve.append(
                portfolio.value(float(row["Close"]))
            )

        equity_curve = pd.Series(
            equity_curve,
            index=data.index,
            name="equity",
        )
        returns = equity_curve.pct_change().dropna()

        metrics = calculate_metrics(equity_curve, benchmark_curve, self.periods_per_year)

        return BacktestResult(
            equity_curve=equity_curve,
            returns=returns,
            trade_history=portfolio.get_trade_history(),
            metrics=metrics,
            benchmark=benchmark,
            initial_capital=self.initial_capital,
            commission=self.commission,
            slippage=self.slippage,
            strategy_name=f"{self.strategy.__class__.__name__}",
        )
