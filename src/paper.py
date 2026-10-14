"""Persistent, server-driven simulated trading; no broker/order API exists."""
import json
import math
import time
import uuid
from datetime import datetime,timezone
import pandas as pd
from .storage import ExperimentStore
from .portfolio import Portfolio
from .catalog import build_strategy
from .quotes import get_quote
from .assets import valid_symbol


class PaperTrading:
    def __init__(self):
        self.store=ExperimentStore()
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS paper_sessions (id TEXT PRIMARY KEY,owner TEXT NOT NULL,payload TEXT NOT NULL)')

    def start(self,owner,config):
        config={k:v for k,v in config.items() if k not in {'api_key','csv_text'}}
        if config.get('source') not in {'market','coinbase','demo'}:
            raise ValueError('Paper trading supports Yahoo quotes, Coinbase quotes, or simulated demo quotes. Daily Alpha Vantage quotes and uploaded CSVs are not incoming feeds.')
        strategy=build_strategy(config)
        symbol=str(config.get('ticker','')).strip().upper()
        if not valid_symbol(symbol):raise ValueError('Choose a valid paper-trading symbol.')
        if config.get('share_mode','fractional') not in {'fractional','whole'}:raise ValueError('Choose fractional or whole shares.')
        config['ticker']=symbol
        capital=float(config.get('capital',10000));commission=float(config.get('commission',.1));slippage=float(config.get('slippage',.05));allocation=float(config.get('allocation',100))
        if not all(math.isfinite(v) for v in (capital,commission,slippage,allocation)) or capital<=0 or not 0<=commission<=10 or not 0<=slippage<=10 or not 0<allocation<=100:
            raise ValueError('Use positive paper capital, costs between 0–10%, and allocation between 0–100%.')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if len([r for r in db.execute('SELECT payload FROM paper_sessions WHERE owner=?',(owner,)) if json.loads(r[0])['active']])>=3:
                raise ValueError('Stop an active session before starting another (maximum three).')
            identifier=uuid.uuid4().hex
            payload=dict(id=identifier,config=config,active=True,created=datetime.now(timezone.utc).isoformat(),cash=capital,shares=0,last_target=0,pending_target=0,observations=[],trades=[],equity=capital,next_poll=0,error=None,currency=None,
                         method='Simulated orders on the next fresh sampled quote after a signal. Indicators use collected quote observations, not historical daily candles. Warm-up starts empty. No real orders, liquidity model, or corporate-action ledger; stop/reset around splits. Prices may be delayed.')
            payload['warmup_observations']=max((getattr(strategy,name,0) for name in ('fast','slow','lookback','period','entry_period')),default=0)+getattr(strategy,'signal_period',0)+1
            payload['sample_interval']={'market':60,'coinbase':10,'demo':5}[config['source']]
            db.execute('INSERT INTO paper_sessions VALUES (?,?,?)',(identifier,owner,json.dumps(payload)))
        return payload

    def list(self,owner):
        with self.store.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM paper_sessions WHERE owner=? ORDER BY rowid DESC LIMIT 20',(owner,))]

    def stop(self,owner,identifier):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM paper_sessions WHERE id=? AND owner=?',(identifier,owner)).fetchone()
            if row is None: raise KeyError('Paper session not found.')
            state=json.loads(row[0]);state['active']=False
            db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),identifier))
        return state

    def tick(self,identifier,loader=None):
        # Keep a per-session atomic transition even when polling and stop overlap.
        # Claim before network access so multiple server processes do not poll twice.
        now=time.time()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()
            if row is None:return
            state=json.loads(row[0])
            if not state['active'] or state['next_poll']>now:return
            state['next_poll']=now+60
            db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),identifier))
        try:
            quote=(loader or get_quote)(state['config'])
            price=float(quote['price']);timestamp=pd.Timestamp(quote['timestamp'])
            if timestamp.tzinfo is None:timestamp=timestamp.tz_localize('UTC')
            else:timestamp=timestamp.tz_convert('UTC')
            if not math.isfinite(price) or price<=0:raise ValueError('Invalid paper quote.')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                latest=json.loads(db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()[0])
                if not latest['active']:return
                state=latest;state['next_poll']=time.time()+max(5,int(quote.get('interval') or 60))
                if state['currency'] and quote.get('currency')!=state['currency']:
                    raise ValueError('Quote currency changed; stop this session and create a new account.')
                state['currency']=quote.get('currency')
                if state['observations'] and timestamp<=pd.Timestamp(state['observations'][-1]['timestamp']):
                    state['error']='Waiting for a fresh quote; duplicate timestamps do not generate orders.'
                else:
                    config=state['config']
                    portfolio=Portfolio(float(config.get('capital',10000)),float(config.get('commission',.1))/100,float(config.get('slippage',.05))/100,config.get('share_mode','fractional')=='fractional')
                    portfolio.cash=state['cash'];portfolio.shares=state['shares'];portfolio.last_target=state['last_target']
                    portfolio.execute_target_position(state['pending_target'],price,timestamp.isoformat())
                    state['trades'].extend(portfolio.trades)
                    state.update(cash=portfolio.cash,shares=portfolio.shares,last_target=portfolio.last_target,equity=portfolio.value(price),error=None)
                    state['observations'].append(dict(timestamp=timestamp.isoformat(),price=price))
                    state['observations']=state['observations'][-20000:]
                    data=pd.DataFrame({'Close':[o['price'] for o in state['observations']]},index=pd.to_datetime([o['timestamp'] for o in state['observations']]))
                    signal=build_strategy(config).generate_signals(data)['signal'].iloc[-1]
                    state['pending_target']=float(signal) * float(config.get('allocation',100))/100 if pd.notna(signal) else 0
                db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state,allow_nan=False),identifier))
        except Exception as exc:
            with self.store.connect() as db:
                row=db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()
                current=json.loads(row[0]);current['error']=str(exc) if isinstance(exc,ValueError) else 'Quote polling failed. Check the feed and connection; retrying in one minute.'
                db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(current),identifier))

    def tick_due(self):
        with self.store.connect() as db:
            identifiers=[row[0] for row in db.execute('SELECT id FROM paper_sessions')]
        for identifier in identifiers:self.tick(identifier)
