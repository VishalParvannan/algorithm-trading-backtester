"""Verify personal accounts, session cookies, ownership boundaries, and legacy import."""
import hashlib
import time
import pytest
from fastapi.testclient import TestClient
from backend import server
from trading.accounts import Accounts
from trading.storage import ExperimentStore


@pytest.fixture
def clients(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'accounts.sqlite'))
    monkeypatch.delenv('QUANTLAB_AUTH_MODE',raising=False)
    monkeypatch.delenv('QUANTLAB_PUBLIC',raising=False)
    monkeypatch.setattr(server.AssetDirectory,'refresh_due',lambda self:None)
    monkeypatch.setattr(server.PaperTrading,'tick_due',lambda self:None)
    with TestClient(server.application) as a,TestClient(server.application) as b:
        yield a,b


def register(client,name):
    response=client.post('/api/auth/register',json={'username':name,'password':'A-good-test-password'})
    assert response.status_code==200,response.text
    return response


def test_signup_login_logout_and_password_hashes(clients):
    a,b=clients
    assert a.get('/',follow_redirects=False).status_code==303
    assert a.get('/api/paper').status_code==401
    response=register(a,'Alice');assert response.json()['username']=='alice'
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    html=a.get('/').text
    assert 'account-context' in html and '/account-session.js' in html
    with Accounts().store.connect() as db:
        row=db.execute('SELECT password_hash FROM users').fetchone()
        assert row[0]!='A-good-test-password'
        assert db.execute('SELECT token_hash FROM user_sessions').fetchone()[0]!=a.cookies.get('backtest_session')
    assert a.post('/api/auth/logout',json={}).status_code==200
    assert a.get('/api/auth/me').status_code==401
    assert a.post('/api/auth/login',json={'username':'ALICE','password':'wrong'}).status_code==400
    assert a.post('/api/auth/login',json={'username':'ALICE','password':'A-good-test-password'}).status_code==200
    assert b.get('/api/auth/me').status_code==401


def test_users_cannot_read_or_change_each_others_data(clients):
    a,b=clients;alice=register(a,'alice').json();register(b,'bob')
    a.post('/api/draft',json={'fields':{'ticker':'AAPL'},'parameters':{}})
    assert b.get('/api/draft').json() is None
    config=dict(source='csv',ticker='AAPL',strategy='buyhold',start='2025-01-01',end='2025-01-06',csv_text='Date,Close\n2025-01-02,100\n2025-01-03,110\n2025-01-06,105')
    identifier=a.post('/api/backtest',json=config).json()['experiment_id']
    assert b.get('/api/experiments').json()==[]
    assert b.get('/api/experiments/'+identifier).status_code==404
    assert b.post('/api/replay',json={'id':identifier}).status_code==404
    paper=a.post('/api/paper',json={'source':'demo','ticker':'AAPL','strategy':'buyhold'}).json()['id']
    assert b.get('/api/paper').json()==[]
    assert b.post(f'/api/paper/{paper}/stop').status_code==404
    # Simulates an old tab retaining Alice's ID after the browser switches to Bob.
    assert b.post('/api/draft',headers={'X-Backtest-Account':alice['id']},json={'fields':{'ticker':'LEAK'}}).status_code==409
    assert b.get('/api/draft').json() is None


def test_expiry_and_explicit_local_import(clients):
    a,b=clients
    ExperimentStore().save_draft('local',{'fields':{'ticker':'SPY'},'parameters':{}})
    register(a,'alice');register(b,'bob')
    assert b.post('/api/auth/import-local',json={}).status_code==400
    assert a.post('/api/auth/import-local',json={}).status_code==200
    assert a.get('/api/draft').json()['fields']['ticker']=='SPY'
    assert b.get('/api/draft').json() is None
    token=hashlib.sha256(a.cookies.get('backtest_session').encode()).hexdigest()
    with Accounts().store.connect() as db:db.execute('UPDATE user_sessions SET expires=? WHERE token_hash=?',(time.time()-1,token))
    assert a.get('/api/auth/me').status_code==401


def test_registration_validation_and_throttling(clients):
    a,b=clients;register(a,'alice')
    assert b.post('/api/auth/register',json={'username':'alice','password':'another-valid-password'}).status_code==400
    assert b.post('/api/auth/register',json={'username':'bob','password':'short'}).status_code==400
    for _ in range(8):assert b.post('/api/auth/login',json={'username':'alice','password':'incorrect'}).status_code==400
    assert 'Too many' in b.post('/api/auth/login',json={'username':'alice','password':'incorrect'}).text


def test_hosted_signup_requires_invitation_and_uses_secure_cookie(clients,monkeypatch):
    a,b=clients
    monkeypatch.setenv('QUANTLAB_PUBLIC','1')
    monkeypatch.setenv('QUANTLAB_PASSWORD','private-invitation-test-code')
    payload=dict(username='hosted',password='a-personal-password')
    assert a.post('/api/auth/register',json=payload).status_code==400
    response=a.post('https://testserver/api/auth/register',json={**payload,'invitation':'private-invitation-test-code'})
    assert response.status_code==200
    assert 'Secure' in response.headers['set-cookie']
    assert a.get('https://testserver/api/auth/me').json()['username']=='hosted'
