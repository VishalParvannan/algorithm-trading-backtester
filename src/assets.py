"""Beginner-friendly asset metadata and optional provider search."""
import re

import yfinance as yf
from .asset_directory import AssetDirectory

ASSETS = [
    {"symbol": symbol, "name": name, "type": kind}
    for symbol, name, kind in [
        ("SPY", "SPDR S&P 500 ETF", "ETF"), ("QQQ", "Invesco Nasdaq-100 ETF", "ETF"),
        ("VTI", "Vanguard Total Stock Market ETF", "ETF"), ("VOO", "Vanguard S&P 500 ETF", "ETF"),
        ("IWM", "iShares Russell 2000 ETF", "ETF"), ("DIA", "SPDR Dow Jones Industrial Average ETF", "ETF"),
        ("GLD", "SPDR Gold Shares", "ETF"), ("TLT", "iShares 20+ Year Treasury Bond ETF", "ETF"),
        ("AAPL", "Apple", "Stock"), ("MSFT", "Microsoft", "Stock"),
        ("GOOGL", "Alphabet / Google", "Stock"), ("AMZN", "Amazon", "Stock"),
        ("NVDA", "NVIDIA", "Stock"), ("TSLA", "Tesla", "Stock"),
        ("META", "Meta / Facebook", "Stock"), ("NFLX", "Netflix", "Stock"),
        ("AMD", "Advanced Micro Devices", "Stock"), ("INTC", "Intel", "Stock"),
        ("CSCO", "Cisco Systems", "Stock"), ("IBM", "IBM", "Stock"),
        ("ORCL", "Oracle", "Stock"), ("ADBE", "Adobe", "Stock"),
        ("JPM", "JPMorgan Chase", "Stock"), ("BAC", "Bank of America", "Stock"),
        ("V", "Visa", "Stock"), ("MA", "Mastercard", "Stock"),
        ("WMT", "Walmart", "Stock"), ("COST", "Costco", "Stock"),
        ("KO", "Coca-Cola", "Stock"), ("PEP", "PepsiCo", "Stock"),
        ("JNJ", "Johnson & Johnson", "Stock"), ("PG", "Procter & Gamble", "Stock"),
        ("XOM", "Exxon Mobil", "Stock"), ("CVX", "Chevron", "Stock"),
        ("DIS", "Walt Disney", "Stock"), ("F", "Ford Motor", "Stock"),
        ("BTC-USD", "Bitcoin", "Crypto"), ("ETH-USD", "Ethereum", "Crypto"),
        ("SOL-USD", "Solana", "Crypto"), ("ADA-USD", "Cardano", "Crypto"),
        ("DOGE-USD", "Dogecoin", "Crypto"), ("LINK-USD", "Chainlink", "Crypto"),
        ("AVAX-USD", "Avalanche", "Crypto"), ("LTC-USD", "Litecoin", "Crypto"),
    ]
]


def valid_symbol(symbol):
    return bool(re.fullmatch(r"[A-Z0-9.\-^=]{1,16}", symbol))


def allowed_assets(source):
    if source == "coinbase": return [a for a in ASSETS if a["type"] == "Crypto"]
    if source == "alpha": return [a for a in ASSETS if a["type"] != "Crypto"]
    if source == "csv": return []
    return ASSETS


def search_assets(source, query):
    if source not in {"demo", "market", "coinbase", "alpha", "csv"}:
        raise ValueError("Choose a supported data source.")
    query = str(query).strip()[:80]
    directory = AssetDirectory()
    matches = directory.search(source, query)
    directory_match = bool(matches)
    for asset in allowed_assets(source):
        if query.lower() in (asset['symbol'] + ' ' + asset['name']).lower() and not any(a['symbol'] == asset['symbol'] for a in matches):
            matches.append(asset)
    warning = 'Using the saved asset directory; the latest refresh is unavailable.' if any(s['warning'] for s in directory.status() if s['provider'] in (['crypto'] if source == 'coinbase' else ['equities'] if source == 'alpha' else ['equities','crypto'])) else ''
    if source == "market" and len(query) >= 2 and not directory_match:
        try:
            quotes = yf.Search(query, max_results=12, news_count=0, timeout=8).quotes
            for quote in quotes:
                symbol = str(quote.get("symbol", "")).upper()
                if valid_symbol(symbol) and quote.get("quoteType") in {"EQUITY", "ETF", "CRYPTOCURRENCY", "INDEX"} and not any(a["symbol"] == symbol for a in matches):
                    matches.append(dict(symbol=symbol, name=quote.get("longname") or quote.get("shortname") or symbol, type={"EQUITY": "Stock", "ETF": "ETF", "CRYPTOCURRENCY": "Crypto", "INDEX": "Index"}[quote["quoteType"]]))
        except Exception:
            warning = "Online search is unavailable; showing saved and built-in matches."
    familiar = {a['symbol']: i for i, a in enumerate(ASSETS)}
    matches.sort(key=lambda a: (a["symbol"] != query.upper(), not a["symbol"].startswith(query.upper()), familiar.get(a['symbol'], len(ASSETS))))
    return {"assets": matches[:15], "warning": warning}
