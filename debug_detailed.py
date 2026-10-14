"""
Detailed debug script to trace signals, positions, trades, and equity.
"""
import pandas as pd
import numpy as np

from src.data import download_data
from src.strategy import MovingAverageStrategy
from src.backtester import Backtester

def make_test_data():
    """Create synthetic test data with known pattern"""
    dates = pd.date_range(start="2020-01-01", periods=20, freq="D")
    # Create a price series that will trigger clear signals
    prices = [100, 101, 102, 103, 104, 103, 102, 101, 100, 99,
              98, 99, 100, 101, 102, 103, 104, 105, 106, 107]

    data = pd.DataFrame({
        "Open": prices,
        "High": [p * 1.005 for p in prices],
        "Low": [p * 0.995 for p in prices],
        "Close": prices,
        "Volume": [1000] * len(prices)
    }, index=dates)

    return data

if __name__ == "__main__":
    # Create test data
    data = make_test_data()
    ticker = "TEST"

    print(f"Using synthetic data for {ticker} with {len(data)} days\n")
    print("Data:")
    print(data)
    print()

    # Use the same data for benchmark (buy-and-hold)
    benchmark_data = data.copy()

    # Initialize strategy and backtester
    strategy = MovingAverageStrategy(fast=5, slow=10)  # Will trigger signals based on crossovers
    backtester = Backtester(
        strategy=strategy,
        initial_capital=10_000,
        commission=0.001,
        slippage=0.0005,
        benchmark=benchmark_data["Close"],
        shift_signals=True,
    )

    # Let's manually check what the strategy and positions look like
    print("=== Strategy Signals ===")
    signals = strategy.generate_signals(data)
    print(signals[['Close', 'signal']])
    print()

    print("=== Built Positions ===")
    positions = backtester._build_positions(signals, data)
    print(positions)
    print()

    print("=== Position Changes (daily) ===")
    position_changes = positions.diff()
    print(position_changes)
    print()

    # Run the backtest
    print("Running backtest...")
    result = backtester.run(data)

    # Display results
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    print(result.print_report())

    print(f"\nNumber of trades: {len(result.trade_history)}")
    print("Trade history:")
    print(result.trade_history[['timestamp', 'price', 'quantity']].to_string())

    print(f"\nEquity curve:")
    for idx, (date, value) in enumerate(result.equity_curve.items()):
        print(f"{date}: {value:.2f}")