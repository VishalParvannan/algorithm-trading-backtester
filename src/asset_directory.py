"""Persistent directories; a failed refresh never replaces a successful snapshot."""
import csv
import io
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from urllib.request import Request, urlopen

from .storage import DEFAULT_PATH


def download(url):
    with urlopen(Request(url, headers={'User-Agent': 'QuantLab/1.0'}), timeout=15) as response:
        data = response.read(8_000_001)
    if len(data) > 8_000_000:
        raise ValueError('Directory exceeds the size limit.')
    return data.decode('utf-8-sig')


def parse_equities(text, other=False):
    rows = csv.DictReader(io.StringIO(text), delimiter='|')
    required = {'Security Name', 'Test Issue', 'ETF', 'ACT Symbol' if other else 'Symbol'}
    if not required.issubset(rows.fieldnames or []):
        raise ValueError('Unexpected equity directory format.')
    result = []
    for row in rows:
        symbol = row.get('ACT Symbol' if other else 'Symbol', '')
        # Class-share dots map to Yahoo dashes. Complex preferred/warrant symbols
        # are excluded until their provider-specific mappings are available.
        if row.get('Test Issue') != 'N' or not re.fullmatch(r'[A-Z]+(?:[.][A-Z])?', symbol):
            continue
        result.append(dict(symbol=symbol.replace('.', '-'), name=row['Security Name'],
                           type='ETF' if row['ETF'] == 'Y' else 'Stock',
                           exchange=row.get('Exchange', 'NASDAQ'), currency='USD'))
    if not result:
        raise ValueError('Empty equity directory.')
    return result


def fetch_equities():
    base = 'https://www.nasdaqtrader.com/dynamic/SymDir/'
    return parse_equities(download(base + 'nasdaqlisted.txt')) + parse_equities(download(base + 'otherlisted.txt'), True)


def fetch_crypto():
    products = json.loads(download('https://api.exchange.coinbase.com/products'))
    if not isinstance(products, list):
        raise ValueError('Unexpected crypto directory format.')
    return [dict(symbol=p['id'], name=p.get('display_name') or p['base_currency'], type='Crypto', exchange='Coinbase', currency='USD')
            for p in products if p.get('quote_currency') == 'USD' and p.get('status') == 'online'
            and not p.get('trading_disabled') and re.fullmatch(r'[A-Z0-9]+-USD', p.get('id', ''))]


class AssetDirectory:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get('QUANTLAB_DB_PATH', DEFAULT_PATH))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS asset_directory (
                    provider TEXT NOT NULL, symbol TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(provider, symbol));
                CREATE TABLE IF NOT EXISTS asset_refresh (
                    provider TEXT PRIMARY KEY, success REAL, attempted REAL, error TEXT);
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def refresh(self, provider, loader, now=None, force=False):
        now = time.time() if now is None else now
        # Claim the refresh transactionally, including across app processes.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record = db.execute('SELECT success, attempted FROM asset_refresh WHERE provider=?', (provider,)).fetchone()
            if not force and record and ((record[0] is not None and now-record[0] < 86400) or (record[1] is not None and now-record[1] < 3600)):
                return False
            db.execute('INSERT INTO asset_refresh(provider,attempted) VALUES (?,?) ON CONFLICT(provider) DO UPDATE SET attempted=excluded.attempted', (provider,now))
        try:
            assets = loader()
            if not assets:
                raise ValueError('Empty directory.')
            rows = [(provider, a['symbol'], json.dumps(a)) for a in assets]
            with self.connect() as db:
                db.execute('DELETE FROM asset_directory WHERE provider=?', (provider,))
                db.executemany('INSERT OR REPLACE INTO asset_directory VALUES (?,?,?)', rows)
                db.execute('UPDATE asset_refresh SET success=?,error=NULL WHERE provider=?', (now,provider))
            return True
        except Exception:
            with self.connect() as db:
                db.execute('UPDATE asset_refresh SET error=? WHERE provider=?', ('Refresh unavailable; keeping the last successful directory.',provider))
            return False

    def refresh_due(self):
        self.refresh('equities', fetch_equities)
        self.refresh('crypto', fetch_crypto)

    def search(self, source, query):
        if source in {'csv', 'demo'}:
            return []
        providers = ['crypto'] if source == 'coinbase' else ['equities'] if source == 'alpha' else ['equities', 'crypto']
        # Escape LIKE wildcards so user input is always literal.
        query = query.upper().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        with self.connect() as db:
            rows = db.execute(f'''SELECT payload FROM asset_directory
                WHERE provider IN ({','.join('?' for _ in providers)})
                AND (symbol LIKE ? ESCAPE '\\' OR upper(json_extract(payload,'$.name')) LIKE ? ESCAPE '\\')
                ORDER BY symbol = ? DESC, symbol LIKE ? ESCAPE '\\' DESC, symbol LIMIT 30''',
                (*providers, '%'+query+'%', '%'+query+'%', query, query+'%')).fetchall()
        return [json.loads(row[0]) for row in rows]

    def status(self):
        with self.connect() as db:
            return [dict(provider=p, last_success=s, last_attempt=a, warning=e,
                         count=db.execute('SELECT count(*) FROM asset_directory WHERE provider=?',(p,)).fetchone()[0])
                    for p,s,a,e in db.execute('SELECT provider,success,attempted,error FROM asset_refresh').fetchall()]
