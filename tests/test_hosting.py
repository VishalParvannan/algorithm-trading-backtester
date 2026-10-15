"""Verify production port settings, private authentication, and persistent-storage requirements."""
import pytest
from scripts.serve import settings
from fastapi.testclient import TestClient
from backend import server


@pytest.fixture(autouse=True)
def legacy_auth(monkeypatch):
    monkeypatch.setenv('QUANTLAB_AUTH_MODE','legacy')


def test_production_port_and_single_process(monkeypatch):
    monkeypatch.setenv('PORT','10000')
    assert settings()==dict(host='0.0.0.0',port=10000,workers=1,reload=False)
    monkeypatch.setenv('PORT','not-a-port')
    with pytest.raises(ValueError,match='PORT'):settings()


def test_hosted_auth_protects_pages_and_paper_data(tmp_path,monkeypatch):
    monkeypatch.setenv('QUANTLAB_PUBLIC','1')
    monkeypatch.setenv('QUANTLAB_PASSWORD','hosting-test-password-strong')
    monkeypatch.setenv('QUANTLAB_USERNAME','researcher')
    monkeypatch.setenv('QUANTLAB_DB_PATH',str(tmp_path/'hosted.sqlite'))
    monkeypatch.setattr(server.AssetDirectory,'refresh_due',lambda self:None)
    monkeypatch.setattr(server.PaperTrading,'tick_due',lambda self:None)
    with TestClient(server.application) as client:
        assert client.get('/health').status_code==200
        for path in ('/','/api/paper','/api/experiments','/navigation.js'):
            assert client.get(path).status_code==401
            assert client.get(path,auth=('researcher','hosting-test-password-strong')).status_code==200
        assert client.post('/api/draft',json={},headers={'Origin':'https://unrelated.example'},auth=('researcher','hosting-test-password-strong')).status_code==403
        assert client.post('/api/draft',json={},headers={'Origin':'http://testserver'},auth=('researcher','hosting-test-password-strong')).status_code==200


def test_public_startup_requires_storage_path(monkeypatch):
    monkeypatch.setenv('QUANTLAB_PUBLIC','1')
    monkeypatch.setenv('QUANTLAB_PASSWORD','hosting-test-password-strong')
    monkeypatch.delenv('QUANTLAB_DB_PATH',raising=False)
    with pytest.raises(RuntimeError,match='persistent disk'):
        with TestClient(server.application):pass
