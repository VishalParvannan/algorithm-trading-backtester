# Backtest Lab

A Python web app for testing trading strategies, comparing historical results,
and running simulated paper portfolios. Built with FastAPI, pandas, NumPy,
SQLite, and a browser interface.

## Setup and launch

Install Python 3.12 or later. From the project folder in a Windows terminal:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Skip creating `.venv` if it already exists. No frontend build is required.
Node.js is optional and used for browser regression checks.

Open the project folder in **Windows File Explorer** and double-click
**Backtest Lab.cmd**. It restarts verified servers belonging to this project,
waits for startup, and opens http://127.0.0.1:8000 in your default browser.
Leave its window running; you can minimize it. Press **Ctrl+C** there to stop.
Saving code automatically reloads the local server.

For a desktop shortcut, right-click the launcher and choose **Show more
options > Send to > Desktop (create shortcut)**. Keep the actual file inside
the project folder.

Alternatively, use VS Code's terminal:

```powershell
.\restart.cmd
```

If another app occupies port 8000, use `.\restart.cmd -Port 8002` and open
http://127.0.0.1:8002. Unrelated processes are never stopped. Run
`.\restart.cmd -CheckOnly` to inspect process checks without changing anything.

On other platforms, create a virtual environment, install the requirements,
and run `python -m backend.backtest_service` from the project root.

## Workspace pages

| Page | Purpose |
| --- | --- |
| Backtest | Configure sources, assets, strategies, dates, capital, and execution; view metrics and portfolio performance |
| Research | Compare strategies and run sensitivity, holdout, and walk-forward tests |
| Saved runs | Open, replay, and compare saved experiments |
| Trade history | Review historical executions and completed trades |
| Market monitor | Watch streaming, polled, historical, or simulated prices |
| Paper trading | Manage separate simulated portfolios using incoming quotes |

Navigation preserves inputs, results, and running feeds. Mobile screens use
horizontal navigation. The app remembers the last page and supports browser
Back/Forward navigation.

### Your first backtest

1. Open **Backtest**, select a data source, and search by asset name or symbol.
2. Select a strategy and dates long enough for its indicators to warm up.
3. Set capital, allocation, costs, and whole or fractional shares.
4. Choose next-bar Close or Open fills. Open fills need an `Open` column.
5. Click **Run backtest**, then inspect the chart and data-quality notes.
6. Open **Trade history** to review executions and completed trades.

Results start empty. Synthetic backtests do not populate historical trade
history or saved experiments.

## Data and strategies

| Source | Examples | Requirements |
| --- | --- | --- |
| Yahoo Finance | `AAPL`, `SPY`, `BTC-USD` | Internet; adjusted daily OHLCV |
| Coinbase | `BTC-USD`, `ETH-USD` | Internet; daily USD crypto candles |
| Alpha Vantage | `IBM`, `MSFT` | API key; raw daily OHLCV |
| CSV upload | Your asset symbol | Up to 2 MB; daily `Date,Close` columns |
| Sample data | Any display symbol | Synthetic prices; no network |

CSV can also contain `Open,High,Low,Volume`. Use one row per day and positive,
finite prices. Historical backtests format monetary values as USD. Uploaded
CSV contents may be saved in drafts and experiment snapshots.

Alpha Vantage compact history contains its latest 100 bars; full access
depends on the provider's plan. Enter a key in the app or set
`ALPHA_VANTAGE_API_KEY`. Keys are not saved with drafts or results. Backtest
date ranges include the end date.

Available strategies: moving average crossover, EMA crossover, momentum,
RSI mean reversion, MACD, Bollinger Bands, Donchian breakout, and buy & hold.
All are long-only. Historical windows count available daily bars. Donchian
uses closing-price channels, allowing Close-only CSVs.

### Asset directory

Search uses US securities from Nasdaq Trader and active USD pairs from
Coinbase, stored in SQLite. Built-in names remain available, and unmatched
Yahoo searches can return additional assets. Suggestions adapt to the source.

The server checks at startup and hourly. Successful directories refresh after
24 hours; failed downloads preserve the last successful copy and retry after
an hour. `/api/assets/status` reports counts and refresh status. The directory
does not cover every worldwide or historically delisted asset.

## Research

Configure the asset, dates, strategy, and costs on **Backtest**. Open **Research**,
choose analyses, and click **Run selected analyses**.

- **Strategy comparison:** same prices and costs; your strategy uses your
  parameters, and other strategies use their defaults.
- **Parameter sensitivity:** varies one chosen setting around its current
  value, holding other settings fixed. Strategies without adjustable settings
  show that explicitly. Full-period sensitivity is exploratory, not unseen performance.
- **Chronological holdout:** fixed parameters, independent training/test
  accounts, and independent indicator warm-up.
- **Walk-forward:** two to five expanding training windows. A candidate is
  chosen by training net return and evaluated on later dates. Each test fold
  starts with independent cash and indicators warmed by prior history; its
  first bar remains cash before delayed fills.

### Saved experiments

Non-synthetic runs save their settings, results, engine version, and exact
price snapshots with fingerprints. Replay uses stored prices with the current
engine rather than downloading again. Opening a saved run returns to Backtest.

Select two to five saved runs to compare them. Differences in data and
assumptions are highlighted. The shared-snapshot option reruns strategies
using the first selected run's prices, dates, capital, costs, allocation,
calendar, and fill model. It requires the same asset and preserves originals.

## Market monitor and paper trading

| Source | Market monitor |
| --- | --- |
| Coinbase | Browser WebSocket stream for USD crypto |
| Yahoo | Recent quotes polled every minute; may be delayed |
| Alpha Vantage | Default daily quotes checked hourly; key required |
| CSV | Latest chronological uploaded price |
| Sample data | Simulated quotes every five seconds |

Connections start on request. Monitoring does not execute orders or alter
historical backtest results.

**Paper trading** starts a separate simulated account using the Backtest
asset, strategy, capital, allocation, costs, and share sizing. Yahoo, Coinbase,
and demo are supported; Alpha Vantage daily quotes and CSVs are snapshots.

Indicators count collected quote observations, not daily backtest candles.
Warm-up begins empty, and the page shows the observation count and sampling
interval. A signal fills on the next fresh quote, with fees and slippage.
Duplicate timestamps do not generate orders.

Sessions, positions, observations, and trades persist in SQLite. Active
sessions continue when the browser closes and resume after server restart.
No quotes are collected during downtime. Stop freezes the account without
liquidating positions. Maximum three active sessions per user.

Yahoo paper accounts apply splits to holdings and stored indicator prices, and
credit dividends to eligible holdings using an ex-date cash model. A persistent
action ledger prevents duplicate adjustments after restarts. Newly bought shares
on the ex-date do not receive that dividend. Action-feed failures hold new
orders; late or revised events that would affect previous trades pause the
session for review. Reverse splits retain fractional entitlements; broker
cash-in-lieu, payment dates, taxes, and special distributions are not modeled.
Paper trading has no brokerage integration or liquidity/partial-fill model.
No real orders are submitted.

## Storage and simulation assumptions

The default database is `data/quantlab.sqlite`; override with
`QUANTLAB_DB_PATH`. Drafts also save in browser local storage and sync to
SQLite. Use a consistent browser address: `localhost` and `127.0.0.1` have
separate browser storage. API keys are excluded. `.env` files are not loaded
automatically.

- Data errors identify the provider, asset, requested range, offending date,
  and corrective action. Incomplete rows are not silently dropped.
- Daily dates preserve the exchange's local session date. Choose automatic,
  US equity sessions, 24/7, or weekdays with an unverified holiday calendar.
  US holidays are distinguished from missing bars. Missing prices are never invented.
- Yahoo adjusts all OHLC prices for splits and dividends. Dividend cash is
  not added twice. Adjusted-price fills and whole-share quantities are research
  approximations, not raw historical broker executions.
- Alpha Vantage remains raw; CSV adjustments are user supplied. Large price
  moves prompt a split/data check.
- Completed-bar signals fill at the next available Open or Close with costs.
  Portfolios are valued at Close; unchanged targets hold without daily rebalancing.
- Completed trades use FIFO matching and both commissions. Slippage is
  counted once through execution prices. Open positions are excluded from win rate.
- CAGR uses elapsed calendar time. Volatility and Sharpe use the selected
  annualization factor and can be distorted by missing observations.

## Project structure

```text
algorithm-trading-backtester/
  backend/             Web API and backtest orchestration
  trading/             Strategies, simulation, data, research, and storage
  web/                 HTML, CSS, and browser JavaScript
  scripts/             Startup and maintenance utilities
  tests/               Python and browser regression checks
  examples/            Runnable trading-library examples
  docs/                Deployment instructions
  data/                Databases and generated outputs (ignored by Git)
  Backtest Lab.cmd     Double-click launcher
  restart.cmd          Terminal restart launcher
  requirements.txt     Python dependencies
  render.yaml          Hosting configuration
  Dockerfile           Container build
```

The former `src/` package is now `trading/`. Imports use, for example,
`from trading.backtester import Backtester`. The web app is
`backend.server:application`.

Run the moving-average example from the project root:

```powershell
.\.venv\Scripts\python.exe examples\moving_average.py
```

Generated example charts are saved under `data/plots/`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
Get-ChildItem tests\*.cjs | ForEach-Object {
    node $_.FullName
    if ($LASTEXITCODE -ne 0) { throw "Browser check failed: $($_.Name)" }
}
```

Python tests use controlled data; Node.js regression checks run without a
browser dependency. Windows launcher checks are skipped on other platforms.
GitHub Actions runs both suites on pushes and pull requests.

## Hosting

See [the deployment guide](docs/DEPLOYMENT.md) for Render setup,
authentication, persistent storage, and Docker deployment.

Production uses `python -m scripts.serve`, the host's `PORT`, one worker,
and no development reload. The Render configuration serves the frontend and
backend together with a persistent SQLite disk and generated single-account
login password. It requires paid hosting.

The configuration does not publish the app automatically: connect a repository
and hosting account first. Keep secrets and local databases outside Git.
Completed data survives redeploys on the persistent disk; unfinished research
jobs reset, and paper polling pauses during downtime.
