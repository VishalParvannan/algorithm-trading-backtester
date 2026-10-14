"""Daily market-data adapters with a common validated schema."""
import json
import os
import re
from datetime import timedelta
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from .data import download_data

MAX_CSV_BYTES = 2_000_000


def request_json(url, provider):
    request = Request(url, headers={"User-Agent": "QuantLab/1.0", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=25) as response:
            return json.load(response)
    except HTTPError as exc:
        if exc.code == 429:
            raise ValueError(f"{provider} rate limit reached. Wait before trying again.") from None
        raise ValueError(f"{provider} request failed (HTTP {exc.code}). Check your symbol and access.") from None
    except (URLError, TimeoutError, OSError, ValueError):
        # Do not expose a provider URL which may contain an API key.
        raise ValueError(f"Could not read {provider} data. Check your internet connection and try again.") from None


def normalize_daily(data, start, end):
    """Reject invalid prices and duplicate bars, sort and filter inclusive dates."""
    data = data.copy()
    data.columns = [str(c).strip().title() for c in data.columns]
    if data.columns.has_duplicates or "Close" not in data:
        raise ValueError("Data must contain unique columns including Close.")
    index = pd.to_datetime(data.index, errors="coerce", utc=True)
    if index.isna().any():
        raise ValueError("Data contains an invalid date. Use YYYY-MM-DD dates.")
    # Daily bars are exchange session dates. Preserve their local date rather
    # than shifting a Tokyo/Australia midnight bar into the previous UTC day.
    if isinstance(data.index, pd.DatetimeIndex):
        data.index = data.index.tz_localize(None).normalize()
    else:
        data.index = pd.DatetimeIndex([pd.Timestamp(value).tz_localize(None).normalize() for value in data.index])
    if data.index.has_duplicates:
        day=data.index[data.index.duplicated()][0]
        raise ValueError(f"Data contains duplicate daily dates ({day:%Y-%m-%d}). Supply one row per day.")
    data = data.sort_index().loc[str(start):str(end)]
    for column in [c for c in ("Open", "High", "Low", "Close", "Volume") if c in data]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
        if not np.isfinite(data[column].to_numpy()).all():
            bad=~np.isfinite(data[column].to_numpy());day=data.index[bad][0]
            raise ValueError(f"{column} contains missing or non-numeric values on {day:%Y-%m-%d}. Supply a finite price; rows are not silently dropped.")
        if column != "Volume" and (data[column] <= 0).any():
            day=data.index[data[column] <= 0][0]
            raise ValueError(f"{column} prices must be positive. Invalid bar: {day:%Y-%m-%d}.")
        if column == "Volume" and (data[column] < 0).any():
            raise ValueError("Volume cannot be negative.")
    if "High" in data and "Low" in data and (data.High < data.Low).any():
        day=data.index[data.High < data.Low][0]
        raise ValueError(f"High prices cannot be below Low prices. Invalid bar: {day:%Y-%m-%d}.")
    if all(c in data for c in ("High", "Low")):
        prices = [c for c in ('Open','Close') if c in data]
        upper = data[prices].max(axis=1)
        lower = data[prices].min(axis=1)
        # Adjusted provider prices can differ at floating-point precision.
        above = (upper > data.High) & ~np.isclose(upper, data.High, rtol=1e-8, atol=1e-10)
        below = (lower < data.Low) & ~np.isclose(lower, data.Low, rtol=1e-8, atol=1e-10)
        invalid = above | below
        if invalid.any():
            day = data.index[invalid][0]
            bar = data.loc[day]
            raise ValueError(
                "Open and Close must lie within each bar's High and Low. "
                f"First invalid bar: {day:%Y-%m-%d} "
                '(' + ', '.join(f'{column}={bar[column]:.12g}' for column in ('Open','High','Low','Close') if column in data) + '). '
                "Use the same adjustment basis for all OHLC columns; do not mix adjusted Close with raw prices."
            )
    return data.sort_index().loc[str(start):str(end)]


def csv_data(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Select a CSV file before running the backtest.")
    if len(text.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("CSV files must be smaller than 2 MB.")
    try:
        data = pd.read_csv(StringIO(text.lstrip("\ufeff")))
    except (pd.errors.ParserError, pd.errors.EmptyDataError):
        raise ValueError("Could not parse the CSV. Use comma-separated Date and Close columns.") from None
    data.columns = [str(c).strip().title() for c in data.columns]
    date_column = next((c for c in ("Date", "Timestamp", "Datetime") if c in data), None)
    if date_column is None:
        raise ValueError("CSV must include a Date column (YYYY-MM-DD).")
    return data.set_index(date_column)


def coinbase_data(ticker, start, end):
    if not re.fullmatch(r"[A-Z0-9]+-USD", ticker):
        raise ValueError("Use a Coinbase USD pair such as BTC-USD or ETH-USD.")
    cursor, stop = start, end + timedelta(days=1)
    candles = {}
    while cursor < stop:
        # Coinbase permits at most 300 candles per request; leave a boundary margin.
        window_end = min(cursor + timedelta(days=299), stop)
        query = urlencode({"start": f"{cursor}T00:00:00Z", "end": f"{window_end}T00:00:00Z", "granularity": 86400})
        rows = request_json(f"https://api.exchange.coinbase.com/products/{ticker}/candles?{query}", "Coinbase")
        if not isinstance(rows, list) or any(not isinstance(row, list) or len(row) != 6 for row in rows):
            raise ValueError("Coinbase returned an unexpected response. Check the selected pair.")
        for row in rows:
            candles[row[0]] = row
        cursor = window_end
    data = pd.DataFrame(candles.values(), columns=["Time", "Low", "High", "Open", "Close", "Volume"])
    data.index = pd.to_datetime(data.pop("Time"), unit="s", utc=True)
    return data


def alpha_data(ticker, config):
    key = str(config.get("api_key", "")).strip() or os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        raise ValueError("Enter an Alpha Vantage API key or set ALPHA_VANTAGE_API_KEY.")
    outputsize = config.get("outputsize", "compact")
    if outputsize not in {"compact", "full"}:
        raise ValueError("Choose compact or full Alpha Vantage history.")
    query = urlencode({"function": "TIME_SERIES_DAILY", "symbol": ticker, "outputsize": outputsize, "apikey": key})
    payload = request_json(f"https://www.alphavantage.co/query?{query}", "Alpha Vantage")
    if not isinstance(payload, dict) or not isinstance(payload.get("Time Series (Daily)"), dict):
        if isinstance(payload, dict) and ("Note" in payload or "Information" in payload):
            raise ValueError("Alpha Vantage could not supply data. Your key may be rate-limited or full history may require a premium plan. Try compact history or another source.")
        raise ValueError("Alpha Vantage returned no daily prices. Check your symbol and API key.")
    data = pd.DataFrame.from_dict(payload["Time Series (Daily)"], orient="index")
    return data.rename(columns={"1. open": "Open", "2. high": "High", "3. low": "Low", "4. close": "Close", "5. volume": "Volume"})


def _load_source(source, ticker, start, end, config):
    if source == "demo":
        index = pd.bdate_range(start, end)
        prices = 100 * np.exp(np.cumsum(np.random.default_rng(42).normal(0.00045, 0.011, len(index))))
        data = pd.DataFrame({"Close": prices}, index=index)
    elif source == "market":
        data = download_data(ticker, str(start), str(end + timedelta(days=1)))
    elif source == "coinbase":
        data = coinbase_data(ticker, start, end)
    elif source == "alpha":
        data = alpha_data(ticker, config)
    elif source == "csv":
        data = csv_data(config.get("csv_text"))
    else:
        raise ValueError("Choose a supported data source.")
    return normalize_daily(data, start, end)


def load_source(source, ticker, start, end, config):
    provider={'market':'Yahoo Finance','alpha':'Alpha Vantage','coinbase':'Coinbase','csv':'CSV upload','demo':'Sample data'}.get(source,source)
    try:
        return _load_source(source,ticker,start,end,config)
    except ValueError as exc:
        action='Fix the indicated CSV row and upload the file again.' if source=='csv' else 'Retry the download or choose another provider. Invalid prices were not changed to make the backtest pass.'
        raise ValueError(f'{provider} · {ticker} · {start} to {end}\n{exc}\n{action}') from None
