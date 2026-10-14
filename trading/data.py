from pathlib import Path

import pandas as pd
import yfinance as yf


def download_data(
    ticker: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """
    Download historical OHLCV data from Yahoo Finance.

    Parameters
    ----------
    ticker : str
        Stock ticker, e.g. "SPY".
    start : str
        Start date in YYYY-MM-DD format.
    end : str
        End date in YYYY-MM-DD format.

    Returns
    -------
    pd.DataFrame
        Cleaned historical market data.
    """

    data = yf.download(
        ticker,
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        actions=True,
    )

    if data.empty:
        raise ValueError(f"No data found for ticker: {ticker}")

    # yfinance can sometimes return MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    data = data[required_columns + [c for c in ('Dividends', 'Stock Splits') if c in data]].copy()
    # Keep incomplete bars visible to validation rather than silently dropping them.
    data = data.sort_index()

    return data


def load_csv(filepath: str | Path) -> pd.DataFrame:
    """
    Load OHLCV data from a CSV file.
    """

    data = pd.read_csv(
        filepath,
        index_col=0,
        parse_dates=True,
    )

    required_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    missing = [
        column
        for column in required_columns
        if column not in data.columns
    ]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    data = data[required_columns].copy()
    data = data.dropna()
    data = data.sort_index()

    return data


def save_csv(
    data: pd.DataFrame,
    filepath: str | Path,
) -> None:
    """
    Save market data to a CSV file.
    """

    data.to_csv(filepath)
