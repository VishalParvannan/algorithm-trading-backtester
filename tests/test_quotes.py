"""Verify quote adapters, currency labels, and historical versus simulated data."""
from unittest.mock import Mock
import pandas as pd
import pytest
from trading import quotes


def test_yahoo_quote_uses_bar_timestamp_and_currency(monkeypatch):
    ticker=Mock()
    ticker.history.return_value=pd.DataFrame({'Close':[123.45]},index=pd.to_datetime(['2025-01-02T15:30:00Z']))
    ticker.fast_info={'currency':'CAD'}
    monkeypatch.setattr(quotes.yf,'Ticker',lambda symbol:ticker)
    result=quotes.get_quote(dict(source='market',ticker='AAPL'))
    assert result['price']==123.45
    assert result['currency']=='CAD'
    assert result['timestamp'].startswith('2025-01-02')
    assert result['interval']==60
    assert ticker.history.call_args.kwargs['auto_adjust'] is False
    assert 'delayed' in result['mode']


def test_alpha_key_and_daily_quote(monkeypatch):
    monkeypatch.delenv('ALPHA_VANTAGE_API_KEY',raising=False)
    with pytest.raises(ValueError,match='API key'):
        quotes.get_quote(dict(source='alpha',ticker='IBM'))
    monkeypatch.setattr(quotes,'request_json',lambda *args:{'Global Quote':{'05. price':'100','07. latest trading day':'2025-01-02','10. change percent':'1.5%'}})
    result=quotes.get_quote(dict(source='alpha',ticker='IBM',api_key='secret'))
    assert result['change']==1.5
    assert result['interval']==3600
    assert 'daily' in result['mode']
    assert 'secret' not in str(result)


def test_csv_snapshot_is_last_chronological_bar():
    result=quotes.get_quote(dict(source='csv',ticker='CUSTOM',csv_text='Date,Close\n2025-01-03,105\n2025-01-02,100'))
    assert result['price']==105
    assert result['interval'] is None
    assert 'snapshot' in result['mode']


def test_demo_is_explicitly_simulated():
    result=quotes.get_quote(dict(source='demo',ticker='AAPL'))
    assert result['price']>0
    assert 'simulated' in result['mode']
