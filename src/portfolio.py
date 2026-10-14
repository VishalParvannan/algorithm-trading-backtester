from dataclasses import dataclass
import math

import pandas as pd

from .execution import ExecutionEngine


@dataclass
class PortfolioState:
    """
    Current state of the portfolio.
    """

    cash: float
    shares: float


class Portfolio:
    """
    Tracks cash, positions, trades, and portfolio value.
    """

    def __init__(
        self,
        initial_capital: float = 10_000,
        commission: float = 0.001,
        slippage: float = 0.0005,
        fractional_shares: bool = True,
    ):
        if not math.isfinite(initial_capital) or initial_capital <= 0:
            raise ValueError(
                "Initial capital must be positive."
            )

        self.initial_capital = initial_capital

        self.cash = initial_capital
        self.shares = 0.0

        self.execution_engine = ExecutionEngine(
            commission=commission,
            slippage=slippage,
        )

        self.trades = []
        self.fractional_shares = fractional_shares
        self.last_target = 0.0

    def execute_target_position(
        self,
        target_position: float,
        price: float,
        timestamp,
    ):
        """
        Move the portfolio toward the target position.

        target_position:
            0 = no position
            1 = fully invested

        This implementation is long-only.
        """

        if not math.isfinite(price) or price <= 0 or not 0 <= target_position <= 1:
            raise ValueError("Price must be positive and target position between 0 and 1.")
        # A persistent signal means hold, not rebalance on every price change.
        if target_position == self.last_target:
            return
        self.last_target = target_position
        portfolio_value = (
            self.cash +
            self.shares * price
        )

        target_value = (
            portfolio_value *
            target_position
        )

        target_shares = (
            target_value / price
        )

        quantity = (
            target_shares -
            self.shares
        )

        if quantity > 0:
            unit_cost = price * (1 + self.execution_engine.slippage) * (1 + self.execution_engine.commission)
            quantity = min(quantity, max(0, self.cash) / unit_cost)
        else:
            quantity = max(quantity, -self.shares)
        if not self.fractional_shares:
            quantity = math.floor(quantity) if quantity > 0 else -math.floor(abs(quantity))

        # Avoid trading when the change is very small relative to portfolio value
        # Use a tolerance of $0.01 in trade value to avoid floating point issues
        trade_value = abs(price * quantity)
        if trade_value < 0.01:
            return

        result = self.execution_engine.execute(
            price=price,
            quantity=quantity,
        )

        self.cash -= (
            result.price * quantity
        )

        self.cash -= result.commission
        if abs(self.cash) < 1e-8:
            self.cash = 0.0

        self.shares += quantity

        self.trades.append(
            {
                "timestamp": timestamp,
                "price": result.price,
                "quantity": quantity,
                "commission": result.commission,
                "slippage_cost": result.slippage_cost,
            }
        )

    def value(self, price: float) -> float:
        """
        Calculate total portfolio value.
        """

        return (
            self.cash +
            self.shares * price
        )

    def get_state(self) -> PortfolioState:
        """
        Return the current portfolio state.
        """

        return PortfolioState(
            cash=self.cash,
            shares=self.shares,
        )

    def get_trade_history(self) -> pd.DataFrame:
        """
        Return all executed trades.
        """

        if not self.trades:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "price",
                    "quantity",
                    "commission",
                    "slippage_cost",
                ]
            )

        return pd.DataFrame(self.trades)
