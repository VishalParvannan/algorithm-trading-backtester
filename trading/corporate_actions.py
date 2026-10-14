"""Fetch Yahoo actions and apply audited, idempotent paper-account adjustments."""
import math
import pandas as pd
import yfinance as yf


class ActionReviewRequired(ValueError):
    """An account must pause rather than silently rewrite past executions."""


def fetch_actions(config, created):
    start=(pd.Timestamp(created)-pd.Timedelta(days=5)).date().isoformat()
    history=yf.Ticker(config['ticker']).history(start=start,interval='1d',auto_adjust=False,actions=True,timeout=15,raise_errors=True)
    if history.empty or not {'Dividends','Stock Splits'}.issubset(history.columns):
        raise ValueError('Corporate-action history is unavailable. Paper orders wait until Yahoo action checks succeed.')
    events=[]
    for timestamp,row in history.iterrows():
        for kind,column in [('split','Stock Splits'),('dividend','Dividends')]:
            value=float(row[column])
            if not math.isfinite(value) or value<0:raise ValueError('Yahoo returned an invalid corporate action.')
            if value:
                events.append(dict(id=f'{timestamp.date()}:{kind}',kind=kind,value=value,effective=timestamp.isoformat()))
    return events


def utc(value):
    timestamp=pd.Timestamp(value)
    return timestamp.tz_localize('UTC') if timestamp.tzinfo is None else timestamp.tz_convert('UTC')


def apply_actions(state,events,quote_time):
    ledger=state.setdefault('corporate_actions',[])
    applied={event['id']:event for event in ledger}
    for event in sorted(events,key=lambda e:(utc(e['effective']),0 if e['kind']=='split' else 1)):
        effective=utc(event['effective']);value=float(event['value'])
        if effective<=utc(state['created']) or effective>quote_time:continue
        if event['kind'] not in {'split','dividend'} or not math.isfinite(value) or value<=0:
            raise ValueError('Invalid corporate-action event; no adjustment applied.')
        if event['id'] in applied:
            if applied[event['id']]['value']!=value:
                raise ActionReviewRequired('A previously applied corporate action was revised. Session paused for review.')
            continue
        # Late information cannot safely fix orders already filled on a changed basis.
        if any(utc(t['timestamp'])>=effective for t in state['trades']):
            raise ActionReviewRequired(f"Late {event['kind']} reported for {effective.date()}. Session paused; review prior trades before starting a new account.")
        shares=state['shares'];credit=0
        if event['kind']=='split':
            state['shares']*=value
            # Keep indicator history continuous; trade records retain actual fill prices.
            for observation in state['observations']:
                if utc(observation['timestamp'])<effective:observation['price']/=value
        else:
            credit=shares*value;state['cash']+=credit
        record={**event,'shares_before':shares,'shares_after':state['shares'],'cash_credit':credit,
                'model':'Ex-date cash credit (payment date not modeled)' if event['kind']=='dividend' else 'Share adjustment; fractional reverse-split entitlements retained'}
        ledger.append(record);applied[event['id']]=record
