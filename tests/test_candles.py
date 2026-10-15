"""Verify fixed intervals, closed-bar signals, gap handling, and restart state."""
import pandas as pd
import pytest
import json
from trading.candles import add_quote
from trading.paper import PaperTrading
from trading.storage import ExperimentStore


def make_due(identifier):
    with ExperimentStore().connect() as db:
        state=json.loads(db.execute('SELECT payload FROM paper_sessions WHERE id=?',(identifier,)).fetchone()[0])
        state['next_poll']=0
        db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),identifier))


def state(interval='1m'):
    return dict(config={'paper_interval':interval},candles=[],current_candle=None)


def test_same_minute_updates_ohlc_without_closing():
    s=state();assert not add_quote(s,100,pd.Timestamp('2025-01-01T00:00:00Z'))
    assert not add_quote(s,110,pd.Timestamp('2025-01-01T00:00:30Z'))
    assert s['current_candle']['Close']==110 and s['candles']==[]
    assert add_quote(s,999,pd.Timestamp('2025-01-01T00:01:00Z'))
    assert s['candles'][0]['Close']==110
    assert s['current_candle']['Open']==999


@pytest.mark.parametrize('interval,last,next_time',[('5m','00:04:59','00:05:00'),('1d','23:59:59','00:00:00')])
def test_five_minute_and_daily_boundaries(interval,last,next_time):
    s=state(interval);add_quote(s,100,pd.Timestamp('2025-01-01T00:00:00Z'))
    assert not add_quote(s,101,pd.Timestamp('2025-01-01T'+last+'Z'))
    day='2025-01-02' if interval=='1d' else '2025-01-01'
    assert add_quote(s,102,pd.Timestamp(day+'T'+next_time+'Z'))
    assert len(s['candles'])==1


def test_initial_partial_and_empty_intervals_are_not_invented():
    s=state();add_quote(s,100,pd.Timestamp('2025-01-01T00:00:30Z'))
    assert not add_quote(s,101,pd.Timestamp('2025-01-01T00:01:00Z'))
    assert add_quote(s,102,pd.Timestamp('2025-01-01T00:05:00Z'))
    assert len(s['candles'])==1


def test_paper_only_trades_after_interval_closes(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'candles.sqlite'))
    p=PaperTrading();identifier=p.start('alice',dict(source='demo',ticker='AAPL',strategy='buyhold',paper_interval='5m',commission=0,slippage=0))['id']
    def tick(price,timestamp):
        make_due(identifier);PaperTrading().tick(identifier,lambda c:dict(price=price,timestamp=timestamp,currency='USD',interval=5))
    tick(100,'2025-01-01T00:00:00Z');tick(200,'2025-01-01T00:04:00Z')
    assert p.list('alice')[0]['trades']==[]
    tick(150,'2025-01-01T00:05:00Z')
    s=p.list('alice')[0];assert len(s['trades'])==1
    assert s['trades'][0]['price']==150 and len(s['candles'])==1
    assert s['candles'][0]['Close']==200


def test_legacy_sessions_pause_without_changing_holdings(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'legacy.sqlite'))
    p=PaperTrading();s=p.start('alice',dict(source='demo',ticker='AAPL',strategy='buyhold'))
    s.pop('candle_model');s.update(shares=10,cash=50)
    with ExperimentStore().connect() as db:
        db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(s),s['id']))
    p.tick(s['id'],lambda config:pytest.fail('Legacy account must not poll or trade'))
    stored=p.list('alice')[0]
    assert stored['active'] is False and stored['shares']==10 and stored['cash']==50
    assert 'Legacy' in stored['error']


def test_split_updates_closed_and_forming_candles():
    from trading.corporate_actions import apply_actions
    s=state();s.update(created='2024-12-01T00:00:00Z',shares=10,cash=0,trades=[],observations=[])
    add_quote(s,100,pd.Timestamp('2025-01-01T00:00:00Z'))
    add_quote(s,110,pd.Timestamp('2025-01-01T00:01:00Z'))
    event=dict(id='split',kind='split',value=2,effective='2025-01-02T00:00:00Z')
    apply_actions(s,[event],pd.Timestamp('2025-01-02T01:00:00Z'))
    assert s['candles'][0]['Close']==50
    assert s['current_candle']['Close']==55
    assert s['shares']==20
