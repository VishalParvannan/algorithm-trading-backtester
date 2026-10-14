from dataclasses import dataclass
import math


@dataclass
class ExecutionResult:
    """
    Represents the result of executing a trade.
    """

    price: float
    quantity: float
    commission: float
    slippage_cost: float
    total_cost: float


class ExecutionEngine:
    """
    Handles trade execution.

    This is a simplified execution model.

    Slippage:
        BUY  -> price increases
        SELL -> price decreases

    Commission:
        Percentage of trade value.
    """

    def __init__(
        self,
        commission: float = 0.001,
        slippage: float = 0.0005,
    ):
        if not math.isfinite(commission) or not 0 <= commission < 1:
            raise ValueError(
                "Commission cannot be negative."
            )

        if not math.isfinite(slippage) or not 0 <= slippage < 1:
            raise ValueError(
                "Slippage cannot be negative."
            )

        self.commission = commission
        self.slippage = slippage

    def execute(
        self,
        price: float,
        quantity: float,
    ) -> ExecutionResult:

        if not math.isfinite(price) or price <= 0 or not math.isfinite(quantity):
            raise ValueError("Execution requires a positive finite price and finite quantity.")

        if quantity == 0:
            return ExecutionResult(
                price=price,
                quantity=0,
                commission=0,
                slippage_cost=0,
                total_cost=0,
            )

        trade_value = abs(price * quantity)

        # Slippage moves the execution price against us.
        if quantity > 0:
            execution_price = price * (
                1 + self.slippage
            )
        else:
            execution_price = price * (
                1 - self.slippage
            )

        execution_value = abs(
            execution_price * quantity
        )

        commission_cost = (
            execution_value * self.commission
        )

        slippage_cost = (
            abs(execution_value - trade_value)
        )

        total_cost = (
            commission_cost +
            slippage_cost
        )

        return ExecutionResult(
            price=execution_price,
            quantity=quantity,
            commission=commission_cost,
            slippage_cost=slippage_cost,
            total_cost=total_cost,
        )
