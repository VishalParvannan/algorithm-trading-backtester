"""Verify protected API routes, saved results, research jobs, and cancellation."""
import time
from threading import Event
from concurrent.futures import CancelledError

import pytest
from fastapi.testclient import TestClient

from backend import server


@pytest.fixture
def client(monkeypatch,tmp_path):
    monkeypatch.setenv('QUANTLAB_AUTH_MODE','legacy')
    monkeypatch.setattr(server.AssetDirectory, 'refresh_due', lambda self: None)
    monkeypatch.setattr(server.PaperTrading, 'tick_due', lambda self: None)
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'database.sqlite'))
    monkeypatch.delenv('QUANTLAB_PASSWORD',raising=False)
    monkeypatch.delenv('QUANTLAB_PUBLIC',raising=False)
    with TestClient(server.application) as client:
        yield client


def test_directory_search_and_status(client):
    directory = server.AssetDirectory()
    directory.refresh('equities',lambda:[dict(symbol='UNIQUE',name='Example directory company',type='Stock')])
    response = client.post('/api/assets/search',json={'source':'market','query':'Example directory'})
    assert response.status_code == 200
    assert response.json()['assets'][0]['symbol'] == 'UNIQUE'
    status=client.get('/api/assets/status').json()
    assert status[0]['count'] == 1
    assert status[0]['last_success']


def test_saved_comparison_and_paper_endpoints(client):
    first=client.post('/api/backtest',json=config()).json()['experiment_id']
    second=client.post('/api/backtest',json={**config(),'commission':2}).json()['experiment_id']
    response=client.post('/api/experiments/compare',json={'ids':[first,second],'harmonize':True})
    assert response.status_code==200,response.text
    assert response.json()['harmonized']
    assert response.json()['rows'][0]['result']['equity']==response.json()['rows'][1]['result']['equity']
    assert client.post('/api/experiments/compare',json={'ids':[[first],second]}).status_code==400
    response=client.post('/api/paper',json={'source':'demo','ticker':'AAPL','strategy':'buyhold','capital':1000})
    assert response.status_code==200,response.text
    identifier=response.json()['id']
    assert client.get('/api/paper').json()[0]['active']
    assert client.post(f'/api/paper/{identifier}/stop').json()['active'] is False
    assert client.get('/research-ui.js').status_code==200
    assert client.get('/navigation.js').status_code==200


def config():
    return dict(start='2025-01-01',end='2025-01-06',source='csv',strategy='buyhold',csv_text='Date,Close\n2025-01-02,100\n2025-01-03,101\n2025-01-06,104')


def test_private_access(client,monkeypatch):
    monkeypatch.setenv('QUANTLAB_PASSWORD','strong-test-password')
    monkeypatch.setenv('QUANTLAB_USERNAME','alice')
    assert client.get('/api/catalog').status_code == 401
    assert client.get('/').status_code == 401
    assert client.get('/api/catalog',auth=('alice','wrong')).status_code == 401
    assert client.get('/api/catalog',auth=('alice','strong-test-password')).status_code == 200
    assert client.get('/health').status_code == 200


def test_draft_and_saved_runs(client):
    assert client.post('/api/draft',json={'fields':{'ticker':'AAPL','api_key':'secret'},'parameters':{}}).status_code == 200
    assert client.get('/api/draft').json()['fields'] == {'ticker':'AAPL'}
    response=client.post('/api/backtest',json=config())
    assert response.status_code == 200,response.text
    identifier=response.json()['experiment_id']
    assert len(client.get('/api/experiments').json()) == 1
    assert client.get('/api/experiments/'+identifier).status_code == 200
    replay=client.post('/api/replay',json={'id':identifier})
    assert replay.status_code == 200
    assert replay.json()['equity'] == response.json()['equity']


def test_job_complete_and_validation(client):
    response=client.post('/api/jobs',json=config())
    assert response.status_code == 202
    identifier=response.json()['id']
    for _ in range(100):
        job=client.get('/api/jobs/'+identifier).json()
        if job['state'] not in {'queued','running'}:break
        time.sleep(0.01)
    assert job['state'] == 'complete',job
    assert 'experiment_id' in job['result']
    invalid=client.post('/api/backtest',json={**config(),'capital':-1})
    assert invalid.status_code == 400
    assert 'error' in invalid.json()


def test_public_startup_requires_password(monkeypatch):
    monkeypatch.setenv('QUANTLAB_PUBLIC','1')
    monkeypatch.delenv('QUANTLAB_PASSWORD',raising=False)
    with pytest.raises(RuntimeError,match='QUANTLAB_PASSWORD'):
        with TestClient(server.application):pass


def test_cancelled_job_is_not_saved(client,monkeypatch):
    entered,released=Event(),Event()
    def execute(payload,user,cancel_check=None):
        entered.set()
        released.wait(timeout=3)
        if cancel_check and cancel_check():raise CancelledError()
        raise AssertionError('Expected cancellation')
    monkeypatch.setattr(server,'execute',execute)
    response=client.post('/api/jobs',json=config())
    identifier=response.json()['id']
    assert entered.wait(timeout=2)
    assert client.post('/api/jobs/'+identifier+'/cancel').json()['state']=='cancelled'
    released.set()
    assert client.get('/api/jobs/'+identifier).json()['state']=='cancelled'
    assert client.get('/api/experiments').json()==[]


def test_private_job_ownership(client,monkeypatch):
    monkeypatch.setenv('QUANTLAB_PASSWORD','strong-test-password')
    monkeypatch.setenv('QUANTLAB_USERNAME','alice')
    identifier=client.post('/api/jobs',json=config(),auth=('alice','strong-test-password')).json()['id']
    # The configured single-account identity may change, but saved ownership may not.
    monkeypatch.setenv('QUANTLAB_USERNAME','bob')
    assert client.get('/api/jobs/'+identifier,auth=('bob','strong-test-password')).status_code==404


def test_real_request_body_limit(client):
    response=client.post('/api/draft',content=b'x'*4_100_001,headers={'Content-Type':'application/json'})
    assert response.status_code==413
