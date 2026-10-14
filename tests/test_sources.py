from datetime import date
from urllib.parse import parse_qs, urlparse

import pandas as pd
import pytest

from trading import sources


def test_csv_sorts_and_filters():
    data = sources.load_source("csv", "CUSTOM", date(2025, 1, 2), date(2025, 1, 3), {"csv_text": "date,close\n2025-01-04,104\n2025-01-03,103\n2025-01-02,102"})
    assert list(data.Close) == [102, 103]


@pytest.mark.parametrize("text", ["Date,Close\ninvalid,100", "Date,Close\n2025-01-02,0", "Date,Close\n2025-01-02,nan", "Date,Close\n2025-01-02,100\n2025-01-02,101", "Date,Open\n2025-01-02,100", "Close\n100"])
def test_invalid_csv(text):
    with pytest.raises(ValueError):
        sources.load_source("csv", "CUSTOM", date(2025, 1, 1), date(2025, 1, 5), {"csv_text": text})


def test_coinbase_pagination_and_schema(monkeypatch):
    calls = []
    def request(url, provider):
        query = parse_qs(urlparse(url).query)
        start, end = pd.Timestamp(query["start"][0]), pd.Timestamp(query["end"][0])
        assert (end - start).days <= 299
        assert query["granularity"] == ["86400"]
        calls.append(url)
        # Include shared boundary candles to check deduplication.
        return [[int(day.timestamp()), 99, 105, 100, 103, 50] for day in pd.date_range(start, end, freq="D")][::-1]
    monkeypatch.setattr(sources, "request_json", request)
    data = sources.load_source("coinbase", "BTC-USD", date(2023, 1, 1), date(2024, 1, 1), {})
    assert len(calls) == 2
    assert len(data) == 366
    assert data.index.is_monotonic_increasing
    assert not data.index.has_duplicates
    assert data.Close.iloc[0] == 103
    assert data.Open.iloc[0] == 100


def test_alpha_mapping_and_key(monkeypatch):
    def request(url, provider):
        query = parse_qs(urlparse(url).query)
        assert query["apikey"] == ["test-key"]
        assert query["outputsize"] == ["compact"]
        return {"Time Series (Daily)": {"2025-01-02": {"1. open": "100", "2. high": "104", "3. low": "99", "4. close": "103", "5. volume": "1000"}}}
    monkeypatch.setattr(sources, "request_json", request)
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-key")
    data = sources.load_source("alpha", "IBM", date(2025, 1, 1), date(2025, 1, 5), {})
    assert data.Close.iloc[0] == 103
    assert data.Volume.iloc[0] == 1000


def test_alpha_reports_access_error_without_key(monkeypatch):
    monkeypatch.setattr(sources, "request_json", lambda *args: {"Information": "premium test-secret"})
    with pytest.raises(ValueError, match="premium") as error:
        sources.alpha_data("IBM", {"api_key": "test-secret", "outputsize": "full"})
    assert "test-secret" not in str(error.value)


def test_yahoo_inclusive_end(monkeypatch):
    def download(ticker, start, end):
        assert end == "2025-01-04"
        return pd.DataFrame({"Close": [100, 102]}, index=pd.to_datetime(["2025-01-02", "2025-01-03"]))
    monkeypatch.setattr(sources, "download_data", download)
    data = sources.load_source("market", "SPY", date(2025, 1, 2), date(2025, 1, 3), {})
    assert len(data) == 2


def test_ohlc_allows_only_precision_noise():
    data = pd.DataFrame({'Open':[100.00000001], 'High':[100], 'Low':[99], 'Close':[99-1e-9]},index=pd.to_datetime(['2025-01-02']))
    result = sources.normalize_daily(data, '2025-01-01', '2025-01-03')
    assert result.Open.iloc[0] == data.Open.iloc[0]
    data.loc[data.index[0], 'Close'] = 98
    with pytest.raises(ValueError, match='First invalid bar: 2025-01-02') as error:
        sources.normalize_daily(data, '2025-01-01', '2025-01-03')
    assert 'Close=98' in str(error.value)
    assert 'adjusted Close' in str(error.value)
