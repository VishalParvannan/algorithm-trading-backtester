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
from .corporate_actions import fetch_actions, apply_actions, ActionReviewRequired
from .candles import INTERVALS,add_quote


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
        config.setdefault('paper_interval','1m')
        if not isinstance(config['paper_interval'],str) or config['paper_interval'] not in INTERVALS:raise ValueError('Choose 1-minute, 5-minute, or daily paper candles.')
        capital=float(config.get('capital',10000));commission=float(config.get('commission',.1));slippage=float(config.get('slippage',.05));allocation=float(config.get('allocation',100))
        if not all(math.isfinite(v) for v in (capital,commission,slippage,allocation)) or capital<=0 or not 0<=commission<=10 or not 0<=slippage<=10 or not 0<allocation<=100:
            raise ValueError('Use positive paper capital, costs between 0–10%, and allocation between 0–100%.')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if len([r for r in db.execute('SELECT payload FROM paper_sessions WHERE owner=?',(owner,)) if json.loads(r[0])['active']])>=3:
                raise ValueError('Stop an active session before starting another (maximum three).')
            identifier=uuid.uuid4().hex
            payload=dict(id=identifier,config=config,active=True,created=datetime.now(timezone.utc).isoformat(),cash=capital,shares=0,last_target=0,pending_target=0,observations=[],trades=[],equity=capital,next_poll=0,error=None,currency=None,
                         method='Signals use completed fixed-duration UTC candles reconstructed from sampled quotes. Warm-up starts empty. Split adjustments and ex-date dividend credits apply to Yahoo accounts. No real orders or liquidity model.',corporate_actions=[])
            payload['warmup_observations']=max((getattr(strategy,name,0) for name in ('fast','slow','lookback','period','entry_period')),default=0)+getattr(strategy,'signal_period',0)+1
            payload['sample_interval']={'market':60,'coinbase':10,'demo':5}[config['source']]
            payload.update(candle_model=1,candles=[],current_candle=None)
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

    def tick(self,identifier,loader=None,action_loader=None):
        # Keep a per-session atomic transition even when polling and stop overlap.
        # Claim before network access so multiple server processes do not poll twice.
        now=time.time()
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()
            if row is None:return
            state=json.loads(row[0])
            if not state['active'] or state['next_poll']>now:return
            if state.get('candle_model')!=1:
                state.update(active=False,error='Legacy quote-observation session paused. Start a new session to use fixed-duration candles; holdings and trade history are preserved.')
                db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),identifier))
                return
            state['next_poll']=now+60
            db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),identifier))
        try:
            quote=(loader or get_quote)(state['config'])
            price=float(quote['price']);timestamp=pd.Timestamp(quote['timestamp'])
            if timestamp.tzinfo is None:timestamp=timestamp.tz_localize('UTC')
            else:timestamp=timestamp.tz_convert('UTC')
            if not math.isfinite(price) or price<=0:raise ValueError('Invalid paper quote.')
            events=(action_loader or fetch_actions)(state['config'],state['created']) if state['config']['source']=='market' else []
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                latest=json.loads(db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()[0])
                if not latest['active']:return
                state=latest;state['next_poll']=time.time()+max(5,int(quote.get('interval') or 60))
                # Existing saved sessions also adopt the current action-policy label.
                state['method']='Signals use completed '+state['config']['paper_interval']+' UTC candles built from sampled quotes, not official exchange OHLC. Empty intervals are not filled. The first quote after a closed candle may fill its signal. Yahoo splits and ex-date dividend credits apply. No real orders or liquidity model.'
                if state['currency'] and quote.get('currency')!=state['currency']:
                    raise ValueError('Quote currency changed; stop this session and create a new account.')
                state['currency']=quote.get('currency')
                if state['observations'] and timestamp<=pd.Timestamp(state['observations'][-1]['timestamp']):
                    state['error']='Waiting for a fresh quote; duplicate timestamps do not generate orders.'
                else:
                    # Apply events before any new order; ledger and fill commit together.
                    apply_actions(state,events,timestamp)
                    config=state['config']
                    closed=add_quote(state,price,timestamp)
                    if closed:
                        data=pd.DataFrame(state['candles']).set_index('start')
                        data.index=pd.to_datetime(data.index)
                        signal=build_strategy(config).generate_signals(data)['signal'].iloc[-1]
                        state['pending_target']=float(signal)*float(config.get('allocation',100))/100 if pd.notna(signal) else 0
                    portfolio=Portfolio(float(config.get('capital',10000)),float(config.get('commission',.1))/100,float(config.get('slippage',.05))/100,config.get('share_mode','fractional')=='fractional')
                    portfolio.cash=state['cash'];portfolio.shares=state['shares'];portfolio.last_target=state['last_target']
                    portfolio.execute_target_position(state['pending_target'],price,timestamp.isoformat())
                    # This quote is outside the completed signal candle: no current-candle look-ahead.
                    state['trades'].extend(portfolio.trades)
                    state.update(cash=portfolio.cash,shares=portfolio.shares,last_target=portfolio.last_target,equity=portfolio.value(price),error=None)
                    state['observations'].append(dict(timestamp=timestamp.isoformat(),price=price))
                    state['observations']=state['observations'][-20000:]
                db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state,allow_nan=False),identifier))
        except Exception as exc:
            with self.store.connect() as db:
                row=db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()
                current=json.loads(row[0]);current['error']=str(exc) if isinstance(exc,ValueError) else 'Quote polling failed. Check the feed and connection; retrying in one minute.'
                if isinstance(exc,ActionReviewRequired):current['active']=False
                db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(current),identifier))

    def tick_due(self):
        with self.store.connect() as db:
            identifiers=[row[0] for row in db.execute('SELECT id FROM paper_sessions')]
        for identifier in identifiers:self.tick(identifier)
