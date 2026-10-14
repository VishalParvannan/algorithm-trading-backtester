import json
import pandas as pd
import pytest
from trading.robustness import robustness
from trading.paper import PaperTrading
from trading.saved_comparison import compare_saved
from backend.backtest_service import run_backtest
from trading.storage import ExperimentStore


@pytest.fixture(autouse=True)
def database(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'features.sqlite'))


def test_walk_forward_chooses_from_training_only():
    data=pd.DataFrame({'Close':[100+(i%7)*3+i/3 for i in range(80)]},index=pd.bdate_range('2025-01-01',periods=80))
    config=dict(strategy='momentum',lookback=4,walk_folds=3,commission=.1,slippage=.1)
    original=robustness(config,data)
    changed=data.copy();changed.iloc[40:,0]=10000
    other=robustness(config,changed)
    assert original['folds'][0]['selected_value']==other['folds'][0]['selected_value']
    assert original['folds'][0]['training_return']==other['folds'][0]['training_return']
    assert len(original['sensitivity'])>=3
    for fold in original['folds']:
        assert fold['train_end']<fold['test_start']<=fold['test_end']


def test_robustness_rejects_short_folds():
    data=pd.DataFrame({'Close':range(100,112)},index=pd.bdate_range('2025-01-01',periods=12))
    with pytest.raises(ValueError,match='three bars'):
        robustness(dict(strategy='buyhold'),data)


def save_run(commission,prices):
    config=dict(source='csv',ticker='AAPL',strategy='buyhold',start='2025-01-01',end='2025-01-06',commission=commission,slippage=0,capital=1000,market_calendar='us',csv_text='Date,Close\n2025-01-02,'+str(prices[0])+'\n2025-01-03,'+str(prices[1])+'\n2025-01-06,'+str(prices[2]))
    result,data=run_backtest(config,include_data=True)
    return ExperimentStore().save('alice',config,result,data)['experiment_id']


def test_saved_comparison_flags_differences_and_reruns_one_snapshot():
    ids=[save_run(.1,[100,101,110]),save_run(2,[200,210,205])]
    report=compare_saved('alice',ids)
    assert 'commission' in report['mismatches'] and 'price snapshot' in report['mismatches']
    report=compare_saved('alice',ids,True)
    assert report['rows'][0]['result']['equity']==report['rows'][1]['result']['equity']
    with pytest.raises(KeyError):compare_saved('bob',ids)


def make_due(session):
    with ExperimentStore().connect() as db:
        row=db.execute('SELECT payload FROM paper_sessions WHERE id=?',(session,)).fetchone()
        state=json.loads(row[0]);state['next_poll']=0
        db.execute('UPDATE paper_sessions SET payload=? WHERE id=?',(json.dumps(state),session))


def test_paper_fills_next_quote_with_costs_and_survives_reopen():
    paper=PaperTrading();session=paper.start('alice',dict(source='demo',ticker='AAPL',strategy='buyhold',capital=1000,commission=1,slippage=1,api_key='secret'))
    identifier=session['id']
    assert 'secret' not in str(session)
    def quote(price,time):return lambda config:dict(price=price,timestamp=time,currency='USD',interval=5)
    paper.tick(identifier,quote(100,'2025-01-01T00:00:00Z'))
    assert paper.list('alice')[0]['trades']==[]
    make_due(identifier)
    paper.tick(identifier,quote(110,'2025-01-01T00:01:00Z'))
    state=PaperTrading().list('alice')[0]
    assert len(state['trades'])==1
    assert state['trades'][0]['price']==pytest.approx(111.1)
    assert state['shares']==pytest.approx(1000/(110*1.01*1.01))
    assert state['cash']>=0
    make_due(identifier)
    paper.tick(identifier,quote(110,'2025-01-01T00:01:00Z'))
    assert len(paper.list('alice')[0]['observations'])==2
    assert len(paper.list('alice')[0]['trades'])==1
    with pytest.raises(KeyError):paper.stop('bob',identifier)
    assert paper.list('bob')==[]
    paper.stop('alice',identifier);make_due(identifier)
    paper.tick(identifier,lambda config:pytest.fail('Stopped session must not poll'))
    assert paper.list('alice')[0]['active'] is False


def test_paper_quote_failure_keeps_portfolio_and_retries():
    paper=PaperTrading();session=paper.start('alice',dict(source='market',ticker='AAPL',strategy='momentum',lookback=2))
    def offline(config):raise ValueError('Feed offline')
    paper.tick(session['id'],offline)
    state=paper.list('alice')[0]
    assert state['error']=='Feed offline'
    assert state['cash']==10000 and state['trades']==[] and state['active']
    with pytest.raises(ValueError,match='not incoming feeds'):
        paper.start('alice',dict(source='csv',ticker='AAPL',strategy='buyhold'))
