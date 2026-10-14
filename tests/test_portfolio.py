"""Verify cash-aware position sizing, holding behavior, and trade records."""
import pandas as pd
import pytest

from trading.portfolio import Portfolio


def test_initial_portfolio():

    portfolio = Portfolio(
        initial_capital=10_000
    )

    assert portfolio.cash == 10_000
    assert portfolio.shares == 0


def test_buy_position():

    portfolio = Portfolio(
        initial_capital=10_000,
        commission=0,
        slippage=0,
    )

    portfolio.execute_target_position(
        target_position=1,
        price=100,
        timestamp=pd.Timestamp("2025-01-01"),
    )

    assert portfolio.shares == pytest.approx(100)
    assert portfolio.cash == pytest.approx(0)


def test_exit_position():

    portfolio = Portfolio(
        initial_capital=10_000,
        commission=0,
        slippage=0,
    )

    timestamp = pd.Timestamp("2025-01-01")

    portfolio.execute_target_position(
        target_position=1,
        price=100,
        timestamp=timestamp,
    )

    portfolio.execute_target_position(
        target_position=0,
        price=110,
        timestamp=timestamp,
    )

    assert portfolio.shares == pytest.approx(0)
    assert portfolio.cash == pytest.approx(11_000)


def test_commission_reduces_cash():

    portfolio = Portfolio(
        initial_capital=10_000,
        commission=0.01,
        slippage=0,
    )

    portfolio.execute_target_position(
        target_position=1,
        price=100,
        timestamp=pd.Timestamp("2025-01-01"),
    )

    assert portfolio.cash < 10_000


def test_trade_history():

    portfolio = Portfolio(
        initial_capital=10_000,
        commission=0,
        slippage=0,
    )

    portfolio.execute_target_position(
        target_position=1,
        price=100,
        timestamp=pd.Timestamp("2025-01-01"),
    )

    trades = portfolio.get_trade_history()

    assert len(trades) == 1

    assert "price" in trades.columns
    assert "quantity" in trades.columns
    assert "commission" in trades.columns