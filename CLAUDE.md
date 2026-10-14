# QuantBacktest - Algorithmic Trading Backtesting Engine

A modular Python-based algorithmic trading backtesting engine built with pandas and NumPy. The project simulates systematic trading strategies using historical market data while accounting for transaction costs, slippage, and look-ahead bias.

## Project Structure

```
quant-backtester/
│
├── data/                     # Data storage (SQLite for asset search, downloaded market data)
├── src/                      # Source code
│   ├── __init__.py           # Package initializer
│   ├── analysis.py           # Trade analysis utilities
│   ├── asset_directory.py    # Asset search and symbol directory management
│   ├── assets.py             # Asset metadata handling
│   ├── backtester.py         # Core backtesting engine and result container
│   ├── catalog.py            # Strategy and asset catalog
│   ├── data.py               # Market data download and loading utilities
│   ├── execution.py          # Trade execution engine (slippage, commission modeling)
│   ├── metrics.py            # Performance metrics calculation
│   ├── portfolio.py          # Portfolio tracking and position management
│   ├── research.py           # Background research job queue
│   ├── sources.py            # Data source integrations
│   ├── storage.py            # Persistent storage (SQLite) for experiments
│   └── strategy.py           # Strategy base class and implementations
│
├── tests/                    # Unit tests
│   ├── test_strategy.py      # Strategy tests
│   ├── test_portfolio.py     # Portfolio tests
│   ├── test_metrics.py       # Metrics tests
│   ├── test_backtester.py    # Backtester tests
│   └── ...                   # Other test files
│
├── examples/                 # Usage examples
│   └── moving_average.py     # Example backtest script
│
├── notebooks/                # Jupyter notebooks for analysis
│   └── strategy_analysis.ipynb
│
├── web/                      # Web dashboard components
├── app.py                    # Main dashboard application
├── server.py                 # Web server for the dashboard
├── debug_*.py                # Debug scripts
├── DEPLOYMENT.md             # Deployment instructions
├── README.md                 # Project overview and usage guide
├── requirements.txt          # Python dependencies
└── .gitignore                # Git ignore rules
```

## Core Components

### 1. Strategy System (`src/strategy.py`)
- **Base Strategy Class**: Abstract base class defining the `generate_signals()` interface
- **Implemented Strategies**:
  - `MovingAverageStrategy`: Long-only moving average crossover
  - `MomentumStrategy`: Hold when lookback return is positive
  - `RSIStrategy`: Buy when RSI < oversold, exit when RSI > overbought
  - `EMACrossoverStrategy`: Exponential moving average crossover
  - `MACDStrategy`: MACD line vs signal line
  - `BollingerBandsStrategy`: Buy below lower band, exit at middle band
  - `DonchianBreakoutStrategy`: Close-based breakout with shorter exit channel
  - `BuyAndHoldStrategy`: Always invested strategy

All strategies are long-only and use signals from the preceding bar to avoid look-ahead bias.

### 2. Backtester Engine (`src/backtester.py`)
- **Backtester Class**: Orchestrates the full backtest loop:
  1. Strategy signal generation
  2. Portfolio execution with slippage/commission
  3. Equity curve calculation
  4. Performance metrics computation
- **BacktestResult Dataclass**: Immutable container for results including:
  - Equity curve (daily portfolio value)
  - Trade history (executed trades with costs)
  - Performance metrics (CAGR, Sharpe ratio, max drawdown, etc.)
  - Visualization capabilities

### 3. Portfolio Management (`src/portfolio.py`)
- Tracks cash, shares, and executed trades
- Implements persistent signal handling (no rebalancing on unchanged signals)
- Models transaction costs:
  - Commission: Percentage of trade value
  - Slippage: Price movement against trade direction
- Supports fractional shares trading

### 4. Execution Engine (`src/execution.py`)
- Models realistic trade execution:
  - BUY orders: Execution price increased by slippage
  - SELL orders: Execution price decreased by slippage
  - Commission: Applied to execution value
  - Slippage cost: Difference between ideal and execution value

### 5. Metrics Calculation (`src/metrics.py`)
- Calculates key performance indicators:
  - Total return: `(final_value / initial_value) - 1`
  - CAGR: Compound annual growth rate
  - Annualized volatility: Standard deviation of returns × √(periods_per_year)
  - Sharpe ratio: (excess returns mean / excess returns std) × √(periods_per_year)
  - Maximum drawdown: Largest peak-to-trough decline
  - Benchmark comparison: Buy-and-hold performance

### 6. Data Handling (`src/data.py`)
- Downloads historical OHLCV data from Yahoo Finance via yfinance
- Loads data from CSV files
- Validates and cleans data (required columns, no missing values, sorted chronologically)

## Key Features

1. **Look-Ahead Bias Prevention**: Signals are shifted by one bar by default to ensure trades execute on next-bar open/close prices
2. **Realistic Cost Modeling**: Transaction costs (commission) and slippage are applied to all trades
3. **Flexible Position Sizing**: Supports both fractional and whole shares, with configurable allocation
4. **Benchmark Comparison**: Compare strategy performance against buy-and-hold or custom bench
5. **Interactive Dashboard**: Web-based interface for strategy configuration, backtesting, and result visualization
6. **Research Workspace**: Save experiments, compare strategies, run background jobs
7. **Multiple Data Sources**: Yahoo Finance, Coinbase, Alpha Vantage, CSV upload
8. **Comprehensive Testing**: Unit tests for all major components

## Usage Examples

### Programmatic Usage (see `examples/moving_average.py`)
```python
from src.data import download_data
from src.strategy import MovingAverageStrategy
from src.backtester import Backtester

# Download data
data = download_data("SPY", "2015-01-01", "2024-12-31")

# Initialize strategy and backtester
strategy = MovingAverageStrategy(fast=20, slow=50)
backtester = Backtester(
    strategy=strategy,
    initial_capital=10_000,
    commission=0.001,   # 0.1% per trade
    slippage=0.0005,    # 0.05% per trade
    benchmark=data["Close"],  # buy-and-hold benchmark
    shift_signals=True, # avoid look-ahead bias
)

# Run backtest
result = backtester.run(data)

# View results
print(result.print_result())

# Plot equity curve
result.plot(title="SPY 20/50 MA Crossover")
```

### Dashboard Usage
1. Install dependencies: `pip install -r requirements.txt`
2. Launch dashboard: `.venv\Scripts\python.exe app.py` (Windows) or `python app.py` (Unix)
3. Open http://localhost:8000 in browser
4. Configure strategy, data source, and date range
5. Run backtest and analyze results

## Design Principles

1. **Modularity**: Each component has a single responsibility and clear interface
2. **Immutability**: BacktestResult is immutable to ensure reproducible results
3. **Defensive Programming**: Input validation and error handling throughout
4. **Look-Ahead Bias Prevention**: Built-in signal shifting and validation
5. **Realistic Modeling**: Transaction costs and slippage modeled realistically
6. **Extensibility**: Easy to add new strategies by inheriting from Strategy base class

## Dependencies

See `requirements.txt` for full list, but key dependencies include:
- pandas: Data manipulation and analysis
- numpy: Numerical computations
- matplotlib: Plotting and visualization
- yfinance: Yahoo Finance data download
- Flask: Web dashboard framework
- SQLAlchemy: Database ORM for persistent storage

## Testing

Run tests with:
```bash
python -m pytest tests/
```

Test coverage includes:
- Strategy signal generation correctness
- Portfolio state management
- Execution engine slippage/commission modeling
- Metrics calculation accuracy
- Backtester orchestration
- Data loading and validation

## Deployment

See `DEPLOYMENT.md` for:
- Private hosting instructions
- Persistence configuration
- Authentication setup
- Queue limits for research jobs
- Distinction between monitoring and broker-connected paper trading