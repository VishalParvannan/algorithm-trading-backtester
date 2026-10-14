from datetime import date
from unittest.mock import patch
import numpy as np
import pandas as pd
import pytest

from trading.data_quality import audit
from trading.sources import normalize_daily, load_source
from trading.data import download_data
from trading.metrics import annualized_return
from backend.backtest_service import run_backtest


def test_us_holidays_are_not_missing_bars():
    data=pd.DataFrame({'Close':[100,101,102]},index=pd.to_datetime(['2025-07-03','2025-07-07','2025-07-08']))
    quality,_=audit(data,'csv','AAPL',{'market_calendar':'us'})
    assert quality['missing_calendar_bars']==0
    quality,_=audit(data.drop(pd.Timestamp('2025-07-07')),'csv','AAPL',{'market_calendar':'us'})
    assert quality['missing_dates']==['2025-07-07']


def test_crypto_includes_weekends():
    data=pd.DataFrame({'Close':[100,102]},index=pd.to_datetime(['2025-07-04','2025-07-06']))
    quality,_=audit(data,'coinbase','BTC-USD',{})
    assert quality['missing_dates']==['2025-07-05']


def test_exchange_local_dates_are_preserved():
    data=pd.DataFrame({'Close':[100]},index=pd.DatetimeIndex(['2025-01-06'],tz='Asia/Tokyo'))
    result=normalize_daily(data,'2025-01-06','2025-01-07')
    assert result.index[0]==pd.Timestamp('2025-01-06')


def test_invalid_price_error_identifies_source_symbol_date_and_action():
    with pytest.raises(ValueError) as error:
        load_source('csv','AAPL',date(2025,1,1),date(2025,1,5),{'csv_text':'Date,Close\n2025-01-02,nan'})
    message=str(error.value)
    for part in ('CSV upload','AAPL','2025-01-02','upload the file again'):
        assert part in message


def test_yahoo_does_not_hide_incomplete_rows_and_preserves_actions():
    data=pd.DataFrame({'Open':[100,np.nan], 'High':[101,102], 'Low':[99,99], 'Close':[100,101], 'Volume':[10,10], 'Dividends':[1,0],'Stock Splits':[0,2]},index=pd.date_range('2025-01-02',periods=2))
    with patch('trading.data.yf.download',return_value=data) as download:
        result=download_data('AAPL','2025-01-01','2025-01-04')
    assert download.call_args.kwargs['auto_adjust'] is True
    assert len(result)==2
    assert 'Dividends' in result and 'Stock Splits' in result
    with pytest.raises(ValueError,match='Open.*2025-01-03'):
        normalize_daily(result,'2025-01-01','2025-01-04')


def test_cagr_respects_elapsed_year_despite_missing_rows():
    equity=pd.Series([100,110],index=pd.to_datetime(['2024-01-01','2025-01-01']))
    assert annualized_return(equity)==pytest.approx(1.1**(365.25/366)-1)


def test_next_open_uses_previous_completed_signal_and_close_valuation():
    config=dict(source='csv',ticker='CUSTOM',strategy='buyhold',start='2025-01-02',end='2025-01-06',capital=1000,commission=0,slippage=0,execution_price='Open',market_calendar='us',csv_text='Date,Open,High,Low,Close\n2025-01-02,10,10,10,10\n2025-01-03,20,22,20,22\n2025-01-06,22,23,22,23')
    result=run_backtest(config)
    assert result['trades'][0]['date']=='2025-01-03'
    assert result['trades'][0]['price']==20
    assert result['equity'][1]==pytest.approx(1100)
    assert result['assumptions']['signals_delayed'] is True
