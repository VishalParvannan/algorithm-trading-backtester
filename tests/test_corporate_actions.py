"""Verify share adjustments, dividend eligibility, persistence, and action deduplication."""
import json
import pandas as pd
import pytest
from trading.corporate_actions import apply_actions,ActionReviewRequired
from trading.paper import PaperTrading
from trading.storage import ExperimentStore


def account():
    return dict(created='2025-01-01T00:00:00Z',cash=0,shares=10,trades=[dict(timestamp='2025-01-02T15:00:00Z')],observations=[dict(timestamp='2025-01-02T15:00:00Z',price=100)])


def event(kind,value):
    return dict(id=f'2025-01-03:{kind}',kind=kind,value=value,effective='2025-01-03T00:00:00Z')


def test_split_preserves_marked_value_and_adjusts_indicators_once():
    state=account();events=[event('split',2)]
    apply_actions(state,events,pd.Timestamp('2025-01-03T15:00:00Z'))
    assert state['shares']==20 and state['observations'][0]['price']==50
    assert state['shares']*50==1000
    apply_actions(state,events,pd.Timestamp('2025-01-03T16:00:00Z'))
    assert state['shares']==20 and len(state['corporate_actions'])==1


def test_dividend_credit_and_same_day_split_order():
    state=account()
    apply_actions(state,[event('dividend',1),event('split',2)],pd.Timestamp('2025-01-03T15:00:00Z'))
    assert state['shares']==20 and state['cash']==20
    assert state['corporate_actions'][-1]['cash_credit']==20


def test_reverse_split_retains_fractional_entitlement():
    state=account();state['shares']=5
    apply_actions(state,[event('split',.1)],pd.Timestamp('2025-01-03T15:00:00Z'))
    assert state['shares']==.5 and state['observations'][0]['price']==1000


def test_session_started_on_ex_date_gets_no_old_dividend():
    state=account();state['created']='2025-01-03T12:00:00Z'
    apply_actions(state,[event('dividend',1)],pd.Timestamp('2025-01-03T15:00:00Z'))
    assert state['cash']==0 and state['corporate_actions']==[]


def test_revised_or_late_action_requires_review():
    state=account();apply_actions(state,[event('split',2)],pd.Timestamp('2025-01-03T15:00:00Z'))
    with pytest.raises(ActionReviewRequired,match='revised'):
        apply_actions(state,[event('split',3)],pd.Timestamp('2025-01-03T16:00:00Z'))
    state=account();state['trades'].append(dict(timestamp='2025-01-03T14:00:00Z'))
    with pytest.raises(ActionReviewRequired,match='Late'):
        apply_actions(state,[event('dividend',1)],pd.Timestamp('2025-01-03T16:00:00Z'))


def test_paper_commits_actions_before_fill_and_deduplicates_after_restart(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'paper.sqlite'))
    paper=PaperTrading();session=paper.start('alice',dict(source='market',ticker='AAPL',strategy='buyhold',capital=1000,commission=0,slippage=0))
    def replace(state):
        with ExperimentStore().connect() as db:db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),session['id']))
    session.update(account(),next_poll=0,last_target=1,pending_target=1)
    session['trades']=[];replace(session)
    actions=lambda config,created:[event('split',2),event('dividend',1)]
    quote=lambda config:dict(price=50,timestamp='2025-01-03T15:00:00Z',currency='USD',interval=60)
    paper.tick(session['id'],quote,actions)
    state=PaperTrading().list('alice')[0]
    assert state['shares']==20 and state['cash']==20 and state['equity']==1020
    assert state['trades']==[] and len(state['corporate_actions'])==2
    state['next_poll']=0;replace(state)
    PaperTrading().tick(session['id'],lambda c:dict(price=50,timestamp='2025-01-03T16:00:00Z',currency='USD',interval=60),actions)
    assert PaperTrading().list('alice')[0]['cash']==20


def test_failed_action_check_blocks_new_orders(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'paper.sqlite'))
    paper=PaperTrading();session=paper.start('alice',dict(source='market',ticker='AAPL',strategy='buyhold'))
    def offline(config,created):raise ValueError('Action feed unavailable')
    paper.tick(session['id'],lambda c:dict(price=100,timestamp='2025-01-03T15:00:00Z',currency='USD'),offline)
    state=paper.list('alice')[0]
    assert state['trades']==[] and state['observations']==[]
    assert state['error']=='Action feed unavailable'
