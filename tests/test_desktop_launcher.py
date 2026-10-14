"""Verify browser opening waits for a healthy server and handles startup failure."""
import importlib.util
import io
from pathlib import Path


spec=importlib.util.spec_from_file_location('browser_helper',Path(__file__).resolve().parents[1]/'scripts/open-browser.py')
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def test_waits_through_startup_before_opening_browser(monkeypatch):
    attempts=[];opened=[]
    def request(address,timeout):
        attempts.append(address)
        if len(attempts)==1:raise OSError('starting')
        return io.StringIO('{"status":"ok","engine_version":"3"}')
    monkeypatch.setattr(helper,'urlopen',request)
    monkeypatch.setattr(helper.time,'sleep',lambda seconds:None)
    monkeypatch.setattr(helper.webbrowser,'open',lambda address:opened.append(address) or True)
    assert helper.launch(8001) is None
    assert len(attempts)==2
    assert opened==['http://127.0.0.1:8001']


def test_no_browser_is_opened_when_server_fails(monkeypatch):
    monkeypatch.setattr(helper,'wait_ready',lambda address:False)
    monkeypatch.setattr(helper.webbrowser,'open',lambda address:(_ for _ in ()).throw(AssertionError('Unexpected browser')))
    assert 'did not become ready' in helper.launch(8000)
