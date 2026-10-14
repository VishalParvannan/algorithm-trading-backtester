"""Read-only quotes; polling and snapshots are explicitly distinguished."""
import math
from datetime import datetime, timezone
from urllib.parse import urlencode
import os

import yfinance as yf

from .assets import valid_symbol
from .sources import request_json, csv_data, normalize_daily


def get_quote(config):
    source = config.get('source')
    symbol = str(config.get('ticker', '')).strip().upper()
    if not valid_symbol(symbol):
        raise ValueError('Enter an asset symbol, such as AAPL or BTC-USD.')
    result = dict(symbol=symbol, currency='USD', bid=None, ask=None, change=None)
    if source == 'coinbase':
        if not symbol.endswith('-USD'):
            raise ValueError('Use a Coinbase USD pair such as BTC-USD.')
        quote=request_json(f'https://api.exchange.coinbase.com/products/{symbol}/ticker','Coinbase')
        result.update(price=float(quote['price']),timestamp=quote['time'],mode='Coinbase · polled quote',interval=10)
    elif source == 'market':
        ticker = yf.Ticker(symbol)
        bars = ticker.history(period='5d', interval='1m', auto_adjust=True, timeout=15)
        bars = bars.dropna(subset=['Close']) if 'Close' in bars else bars.iloc[0:0]
        if bars.empty:
            raise ValueError('Yahoo returned no recent prices for this symbol.')
        latest = bars.iloc[-1]
        result.update(price=float(latest.Close), timestamp=latest.name.isoformat(), mode='Yahoo · polled quote · may be delayed', interval=60)
        # Currency varies by exchange; never assume a non-US stock is USD.
        result['currency'] = ticker.fast_info['currency'] or 'USD'
    elif source == 'alpha':
        key = str(config.get('api_key','')).strip() or os.environ.get('ALPHA_VANTAGE_API_KEY','').strip()
        if not key:
            raise ValueError('Enter your Alpha Vantage API key in Strategy setup.')
        payload = request_json('https://www.alphavantage.co/query?' + urlencode(dict(function='GLOBAL_QUOTE',symbol=symbol,apikey=key)), 'Alpha Vantage')
        quote = payload.get('Global Quote', {})
        if not quote.get('05. price'):
            raise ValueError('Alpha Vantage returned no quote. Check the symbol, API key, and rate limit.')
        result.update(price=float(quote['05. price']), timestamp=quote.get('07. latest trading day'),
                      change=float(quote.get('10. change percent','0').rstrip('%')), mode='Alpha Vantage · daily quote',interval=3600,currency=None)
    elif source == 'csv':
        data = csv_data(config.get('csv_text'))
        data = normalize_daily(data, '1900-01-01','2100-01-01')
        if data.empty:
            raise ValueError('The uploaded CSV has no prices.')
        result.update(price=float(data.Close.iloc[-1]), timestamp=data.index[-1].isoformat(),mode='CSV · latest uploaded bar · historical snapshot', interval=None, currency=None)
    elif source == 'demo':
        result.update(price=100 + 2*math.sin(datetime.now(timezone.utc).timestamp()/30), timestamp=datetime.now(timezone.utc).isoformat(),mode='Demo · simulated prices',interval=5)
    else:
        raise ValueError('Choose a supported quote source.')
    if not math.isfinite(result['price']) or result['price'] <= 0:
        raise ValueError('Provider returned an invalid quote.')
    return result
