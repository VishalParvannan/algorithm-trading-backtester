"""
Example backtest run using the moving average crossover strategy.

This script demonstrates how to:
1. Download historical data for a ticker
2. Instantiate a MovingAverageStrategy
3. Run a full backtest with the Backtester engine
4. Print performance metrics and optionally plot the equity curve
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import matplotlib.pyplot as plt

from src.data import download_data
from src.strategy import MovingAverageStrategy
from src.backtester import Backtester

if __name__ == "__main__":
    # Configuration
    TICKER = "SPY"
    START_DATE = "2015-01-01"
    END_DATE = "2024-12-31"
    INITIAL_CAPITAL = 10_000
    FAST_MA = 20
    SLOW_MA = 50
    PLOT_RESULTS = True

    print(f"Downloading {TICKER} data from {START_DATE} to {END_DATE}...")
    data = download_data(TICKER, START_DATE, END_DATE)
    print(f"Downloaded {len(data)} trading days of data.\n")

    # Download benchmark data (buy-and-hold SPY)
    print(f"Downloading benchmark data for {TICKER}...")
    benchmark_data = download_data(TICKER, START_DATE, END_DATE)
    print(f"Downloaded {len(benchmark_data)} trading days of benchmark data.\n")

    # Initialize strategy and backtester
    strategy = MovingAverageStrategy(fast=FAST_MA, slow=SLOW_MA)
    backtester = Backtester(
        strategy=strategy,
        initial_capital=INITIAL_CAPITAL,
        commission=0.001,   # 0.1% per trade
        slippage=0.0005,    # 0.05% per trade
        benchmark=benchmark_data["Close"],  # buy-and-hold SPY as benchmark
        shift_signals=True, # shift signals to avoid look-ahead bias
    )

    # Run the backtest
    print("Running backtest...")
    result = backtester.run(data)

    # Display results
    print("\n" + "="*50)
    print("BACKTEST RESULTS")
    print("="*50)
    print(result.print_report())

    # Plot if requested
    if PLOT_RESULTS:
        print("\nGenerating plots...")
        result.plot(
            title=f"{TICKER} {FAST_MA}/{SLOW_MA} MA Crossover Strategy",
            save_path=f"examples/{TICKER}_ma_backtest.png"
        )

    # Optional: save results for further analysis
    # result.equity_curve.to_csv(f"examples/{TICKER}_equity_curve.csv")
    # result.trade_history.to_csv(f"examples/{TICKER}_trades.csv", index=False)