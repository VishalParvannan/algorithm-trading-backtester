"""
Debug script to check position calculations.
"""
import pandas as pd
import numpy as np

from src.data import download_data
from src.strategy import MovingAverageStrategy
from src.backtester import Backtester

def make_test_data():
    """Create synthetic test data"""
    dates = pd.date_range(start="2020-01-01", periods=50, freq="D")
    # Create a simple trending price series
    prices = 100 + np.cumsum(np.random.normal(0.1, 0.5, size=50))

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
    strategy = MovingAverageStrategy(fast=5, slow=15)  # Use faster MA for more signals
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
    print(signals[['Close', 'signal']].head(10))

    print("\n=== Built Positions ===")
    positions = backtester._build_positions(signals, data)
    print(positions.head(10))

    print("\n=== Position Changes ===")
    position_changes = positions.diff()
    print(position_changes[position_changes != 0].head(10))

    print(f"\nNumber of position changes: {(position_changes != 0).sum()}")