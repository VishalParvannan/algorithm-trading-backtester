"""
Test script to verify the example logic works with synthetic data.
"""
import pandas as pd
import numpy as np

from src.data import download_data
from src.strategy import MovingAverageStrategy
from src.backtester import Backtester

def make_test_data():
    """Create synthetic test data"""
    dates = pd.date_range(start="2020-01-01", periods=100, freq="D")
    # Create a simple trending price series
    prices = 100 + np.cumsum(np.random.normal(0.1, 0.5, size=100))

    data = pd.DataFrame({
        "Open": prices,
        "High": prices * 1.01,
        "Low": prices * 0.99,
        "Close": prices,
        "Volume": 1000
    }, index=dates)

    return data

if __name__ == "__main__":
    # Create test data
    data = make_test_data()
    ticker = "TEST"

    print(f"Using synthetic data for {ticker} with {len(data)} days\n")

    # Use the same data for benchmark (buy-and-hold)
    benchmark_data = data.copy()

    # Initialize strategy and backtester
    strategy = MovingAverageStrategy(fast=10, slow=20)
    backtester = Backtester(
        strategy=strategy,
        initial_capital=10_000,
        commission=0.001,
        slippage=0.0005,
        benchmark=benchmark_data["Close"],
        shift_signals=True,
    )

    # Run the backtest
    print("Running backtest...")
    result = backtester.run(data)

    # Display results
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    print(result.print_report())

    # Verify profit factor calculation works
    pf = result.profit_factor()
    print(f"\nProfit factor from method: {pf}")

    # Manual verification of profit factor for insight
    if len(result.trade_history) > 0:
        print(f"\nNumber of trades: {len(result.trade_history)}")
        print("Trade history:")
        print(result.trade_history[['timestamp', 'price', 'quantity']].head())