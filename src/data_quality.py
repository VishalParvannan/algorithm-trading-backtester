"""Session-aware data coverage and explicit price/execution assumptions."""
import pandas as pd
import exchange_calendars as calendars
from .assets import ASSETS
from .asset_directory import AssetDirectory


def audit(data, source, ticker, config):
    crypto = source == 'coinbase' or (source == 'market' and ticker.endswith('-USD'))
    choice = config.get('market_calendar', 'auto')
    if choice not in {'auto','us','continuous','weekdays'}:
        raise ValueError('Choose an automatic, US equity, continuous, or weekday market calendar.')
    known_us = any(a['symbol']==ticker and a['type'] != 'Crypto' for a in ASSETS)
    if not known_us and source in {'market','alpha'}:
        known_us = any(a['symbol']==ticker and a.get('exchange') != 'Coinbase' for a in AssetDirectory().search('alpha',ticker))
    mode = choice if choice != 'auto' else 'continuous' if crypto else 'us' if known_us and source in {'market','alpha'} else 'weekdays'
    first,last = data.index[0],data.index[-1]
    if mode == 'us':
        calendar=calendars.get_calendar('XNYS', start=first, end=last)
        expected=calendar.sessions_in_range(first,last).tz_localize(None)
        label='US equity sessions (NYSE holiday calendar)'
    else:
        expected=pd.date_range(first,last,freq='D' if mode=='continuous' else 'B')
        label='24/7 daily calendar' if mode=='continuous' else 'Weekdays (holiday calendar unverified)'
    absent=expected.difference(data.index)
    unexpected=data.index.difference(expected)
    basis={'market':'Yahoo OHLC adjusted consistently for splits and dividends; dividend cash is not added separately.',
           'alpha':'Raw Alpha Vantage OHLC; splits and dividends are not applied.',
           'coinbase':'Unadjusted crypto prices; no equity corporate actions.',
           'csv':'CSV adjustment basis is user supplied and unverified.',
           'demo':'Synthetic prices, not market history.'}[source]
    warnings=[]
    if len(absent):
        dates=', '.join(str(d.date()) for d in absent[:5])
        warnings.append(f'{len(absent)} expected bars are missing ({dates}). No prices are filled in; signals execute on the next available bar. Volatility and Sharpe estimates may be distorted by gaps.')
    if len(unexpected):
        warnings.append(f'{len(unexpected)} bars fall outside the selected market calendar. Verify the calendar and uploaded dates.')
    if mode=='weekdays':
        warnings.append('Exchange holiday calendar is unverified. Choose US equity sessions for US stocks; weekday gaps may be holidays.')
    if source in {'alpha','csv'} and data.Close.pct_change().abs().gt(.4).any():
        warnings.append('A daily price move exceeds 40%. Check for splits or data errors; raw prices are not automatically repaired.')
    warnings.append(basis)
    if source=='market':
        warnings.append('Adjusted-price fills are a research approximation. Share counts and whole-share rounding do not represent historical unadjusted broker executions.')
    return dict(bars=len(data),missing_calendar_bars=len(absent),missing_dates=[str(d.date()) for d in absent],
                unexpected_dates=[str(d.date()) for d in unexpected],calendar=label,price_basis=basis,
                dividend_events=int(data['Dividends'].fillna(0).ne(0).sum()) if 'Dividends' in data else None,
                split_events=int(data['Stock Splits'].fillna(0).ne(0).sum()) if 'Stock Splits' in data else None),warnings
