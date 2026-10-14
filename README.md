# Backtest Lab

## Project folders

- `backend/`: FastAPI endpoints and dashboard backtest orchestration.
- `trading/`: strategies, simulation, data providers, analysis, research,
  paper trading, and SQLite persistence.
- `web/`: browser pages, navigation, styling, and interaction code.
- `scripts/`: desktop startup, production startup, and maintenance utilities.
- `tests/`: Python and browser regression checks.
- `examples/`: runnable examples of the trading library.
- `docs/`: deployment instructions.
- `data/`: local databases and downloaded data; excluded from Git.

The top level contains project configuration, this README, and the two
double-click/terminal launchers. Start with **Backtest Lab.cmd** or
`.\restart.cmd`; production uses `python -m scripts.serve`.

A modular Python-based algorithmic trading backtesting engine built
with pandas and NumPy.

The project simulates systematic trading strategies using historical
market data while accounting for transaction costs, slippage, and
look-ahead bias.

## Dashboard

On Windows, open the project folder in File Explorer and double-click
**Backtest Lab.cmd**. It restarts this project's server, waits until it is
ready, and opens the dashboard in your default browser. Leave its window
running (you can minimize it); press Ctrl+C there to stop. Startup errors
remain visible. To put it on your desktop, right-click the file and choose
**Show more options → Send to → Desktop (create shortcut)**. Keep the actual
launcher in the project folder so it can find the environment and scripts.

Launch the local Backtest Lab workspace from the project directory:

```powershell
.\restart.cmd
```

On Windows, this command stops verified servers belonging to this project's
`.venv` (including reload workers and older instances on other ports), then
starts one server on port 8000 with automatic reload. Leave its terminal open;
press Ctrl+C there to shut down. Unrelated or unverified processes are never
stopped. If another app occupies port 8000, the command stops without making
changes; use `.\restart.cmd -Port 8002` to choose another port.
Run `.\restart.cmd -CheckOnly` to inspect what would be stopped without
changing anything. The launcher applies PowerShell's execution-policy setting
only to its own invocation; it does not change your system policy.

Open http://localhost:8000 in your browser. The dashboard includes strategy
configuration, performance metrics, interactive equity and drawdown charts,
trade filtering, pagination, and CSV export. It starts with empty results and
trade history until you run a backtest. Select **Yahoo Finance** to run against
historical prices (requires internet access). Synthetic data remains available
for testing charts, but sample executions never populate trade history.
All backtests use the existing
Python engine and delay signals by one bar.

The sidebar opens separate Backtest, Research, Saved runs, Trade history,
Market monitor, and Paper trading views. Mobile screens use a horizontal
navigation bar. Switching views preserves inputs, results, and running feeds;
the app remembers the last view and supports browser Back/Forward navigation.
Opening a saved experiment returns to Backtest to show its results.

No additional dashboard dependencies are needed. On a fresh setup, install
the existing dependencies with `python -m pip install -r requirements.txt`.

Your configuration, parameters for each strategy, and uploaded CSV contents
are saved automatically in browser local storage as you edit. They are
restored after closing the browser or restarting the server, provided you
use the same browser and address (for example, `http://localhost:8000`).
Clearing site data or using a private browsing session can remove that state.
API keys are not saved. Re-enter your key or use the
server environment variable when needed. Results remain empty on reopen
until you run again or open a saved experiment. A notice appears if browser storage is unavailable.

### Research workspace

- Cash-aware position sizing reserves commission and slippage costs; an
  unchanged signal holds the position without daily rebalancing trades.
- Choose whole or fractional shares, allocation percentage, and next-bar
  Open or Close fills. Open fills require an Open column.
- Completed-trade analysis matches executions FIFO, includes commissions,
  and counts slippage once through the execution price. Win rate excludes
  positions that remain open. Profit factor is unavailable with no closed
  trades; a run with wins and no losses is labeled accordingly.
- Compare all strategies on one dataset snapshot. The selected strategy
  uses your parameters; the others use their documented defaults.
- Chronological holdout divides the range into independent training and
  test runs with fixed parameters. There is no automated fitting or
  parameter search, and indicators warm up independently in each period.
- Market-data runs are saved in SQLite with input settings, results, engine
  version, and a SHA-256 fingerprint of the exact prices. Open or replay
  them from Saved experiments. Synthetic runs are not saved.
- Drafts also sync to SQLite, allowing a fresh browser to restore inputs.
  API keys are excluded; more recently edited drafts take precedence.
- Research jobs run in a bounded background queue and can be cancelled.
- The optional market monitor supports every source with streaming, polling,
  historical snapshot, or simulated labels and is separate from strategy execution.

### Walk-forward testing, comparisons, and paper trading

- In Strategy setup, enable **Sensitivity + walk-forward**, choose the parameter
  to vary, and choose two to five folds. The sensitivity chart varies that
  parameter around your current setting with the other parameters held fixed.
  Walk-forward folds expand the training history and select the parameter using
  training net return only, then evaluate it on later dates. Each fold starts
  with independent cash; indicators use prior history, and delayed fills leave
  the first test bar in cash. Full-period sensitivity is exploratory and must
  not be mistaken for unseen test performance.
- **Compare saved runs** accepts two to five experiments and highlights differing
  data and assumptions. Enable the shared-snapshot checkbox to rerun the saved
  strategies on the first selected run's exact prices, dates, capital, costs,
  allocation, calendar, and fill model. This requires the same asset and does
  not overwrite the original saved results.
- **Paper trading** starts an independent simulated account from Strategy setup.
  Yahoo polls minute quotes; Coinbase polls public trade snapshots; demo uses
  simulated quotes. Indicators count collected quote observations, not daily
  backtest bars, and warm-up begins empty. A signal fills on the next fresh
  quote, including commission, slippage, allocation, and share rounding.
  Duplicate quote timestamps cannot generate orders. Sessions, observations,
  positions, and trades persist in SQLite; active sessions resume polling when
  the server restarts and continue when the browser closes. No data is collected
  while the server is closed. Stop preserves the portfolio and open positions
  without submitting a liquidation order. API keys are never stored.

Paper sessions support Yahoo, Coinbase, and demo. Alpha Vantage's default
daily quote and CSV files are snapshots, not incoming feeds. Paper trading has
no brokerage integration, liquidity/partial-fill model, or corporate-action
ledger; reset sessions around stock splits. The dashboard explains the quote
sampling interval and warm-up behavior. Maximum three active sessions per user.

### Data checks and simulation assumptions

Data errors identify the provider, symbol, requested range, offending session,
and corrective action. Invalid bars remain visible to validation instead of
being silently dropped; tiny numerical discrepancies are tolerated without
changing prices. Daily dates retain the exchange's local session date.

Market sessions can be automatic, US equities (NYSE holidays), 24/7, or
weekdays with an unverified holiday calendar. Automatic mode recognizes US
directory assets and USD crypto pairs; choose a calendar explicitly for CSV
or unsupported exchanges. Missing sessions are listed and never filled with
invented prices. A signal fills on the next available bar, which may be later
than the next scheduled session when data is incomplete.

Yahoo adjusts all OHLC columns for splits and dividends consistently. Reported
corporate-action event counts are retained, but dividend cash is not added a
second time. Adjusted-price fills and whole-share quantities are research
approximations, not a reconstruction of raw historical broker executions.
Alpha Vantage's daily data remains raw; CSV adjustments are supplied by the
user. Unusually large moves in either source prompt a split/data check.

Signals use completed bars, execute at the next available Open or Close as
selected, and mark portfolio value at Close. Commission and slippage apply
to each execution. There is no liquidity, partial-fill, or explicit dividend
payment ledger. CAGR uses elapsed calendar time; volatility and Sharpe still
use the chosen annualization factor and can be distorted by missing bars.

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for private hosting, persistence,
authentication, queue limits, and the distinction between monitoring and
broker-connected paper trading.

### Data sources

| Source | Symbol example | Setup |
| --- | --- | --- |
| Synthetic sample | Any display symbol | Reproducible generated prices; no network needed |
| Yahoo Finance | SPY, AAPL, BTC-USD | Adjusted daily prices; internet required |
| Coinbase | BTC-USD, ETH-USD | Daily USD crypto candles; no API key required |
| Alpha Vantage | IBM, MSFT | Enter an API key or set `ALPHA_VANTAGE_API_KEY` on the server |
| CSV upload | CUSTOM or your asset symbol | Upload a CSV with `Date,Close`; optional `Open,High,Low,Volume` |

All selected date ranges include the end date. CSV data must have one row per
day, valid dates, and positive finite prices. Files are limited to 2 MB and
are processed in memory without being saved to the project. Use USD prices
to match the dashboard's currency display. The CSV example download shows
the accepted format; choose short strategy windows when trying its few rows.

[Alpha Vantage daily data](https://www.alphavantage.co/documentation/#daily)
uses raw prices, so splits and dividends are not adjusted. Compact history
includes the latest 100 bars; full history requires a premium API key.
The dashboard suggests recent dates for compact history and reports the
actual available range. Keys are not stored by the app or returned in results.

[Coinbase candles](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)
are downloaded in date batches and can have missing days without trades.
The dashboard uses 365 bars per year for Coinbase. Choose the same calendar
for daily crypto CSVs or Yahoo crypto data; choose 252 for weekday equities.
These annualization assumptions affect CAGR, volatility, and Sharpe ratio.

### Strategies

All strategies are long-only and use signals from the preceding bar.
Windows are measured in available daily bars.

| Strategy | Entry / holding rule | Exit rule |
| --- | --- | --- |
| Simple moving average crossover | Fast average exceeds slow average | Fast average falls below or equals slow |
| EMA crossover | Fast exponential average exceeds slow | Fast average falls below or equals slow |
| Momentum | Lookback return is positive | Lookback return is zero or negative |
| RSI mean reversion | RSI falls below oversold | RSI rises above overbought |
| MACD | MACD exceeds its signal line | MACD falls below or equals its signal line |
| Bollinger Bands | Close falls below lower band | Close recovers to the middle band |
| Donchian breakout | Close exceeds the prior closing-price channel high | Close falls below the shorter closing-price channel low |
| Buy & hold | Invest on the first executable bar | Remain invested |

The Donchian variant uses closing prices rather than intraday highs and lows,
so it works with Close-only CSV files. Strategies remain in cash during
indicator warm-up. Increase your date range or shorten windows if the
dashboard reports insufficient warm-up data.

## Engine features

- Historical OHLCV data
- Modular trading strategy architecture
- Moving average crossover strategy
- Momentum strategy
- RSI strategy
- Portfolio simulation
- Transaction costs
- Slippage modeling
- Benchmark comparison
- Sharpe ratio
- CAGR
- Annualized volatility
- Maximum drawdown
- Trade history
- Unit tests

## Project Structure

```text
quant-backtester/
│
├── data/
│
├── trading/
│   ├── data.py
│   ├── strategy.py
│   ├── portfolio.py
│   ├── execution.py
│   ├── metrics.py
│   └── backtester.py
│
├── tests/
│   ├── test_strategy.py
│   ├── test_portfolio.py
│   └── test_metrics.py
│
├── examples/
│   └── moving_average.py
│
├── notebooks/
│
├── README.md
├── requirements.txt
└── .gitignore

Asset search uses a persistent SQLite directory in data/quantlab.sqlite (or QUANTLAB_DB_PATH). US stocks and ETFs are downloaded from Nasdaq Trader symbol directories; active USD crypto pairs come from Coinbase Exchange. No API key is required for these downloads. On startup and hourly while running, the server checks for directories older than 24 hours and refreshes them in the background. Failed downloads leave the previous successful snapshot intact and retry after an hour. Search remains available using saved data and built-in entries; Yahoo search supplements unmatched queries. /api/assets/status reports counts, last successful refresh, and refresh warnings. Directories cover current listings, not a worldwide or historical delisted universe; some complex security symbols are excluded pending provider mapping. Refreshing requires the application to be running.


The Live market monitor supports every backtest source with explicit freshness labels: Coinbase streams USD crypto prices, Yahoo polls recent minute bars every 60 seconds (quotes may be delayed), Alpha Vantage polls its default daily quote hourly using the API key entered in Strategy setup, CSV displays the latest chronological bar from the uploaded file, and demo mode generates simulated quotes every 5 seconds. Use asset symbols such as AAPL or BTC-USD. Connections start only when requested; changing the monitor source or symbol disconnects the old feed. These quotes never place orders or change backtest results.
