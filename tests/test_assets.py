from unittest.mock import patch
import pytest

from src.assets import search_assets
from src.asset_directory import AssetDirectory


@pytest.fixture(autouse=True)
def isolated_directory(tmp_path, monkeypatch):
    monkeypatch.setenv('QUANTLAB_DB_PATH', str(tmp_path / 'directory.sqlite'))


def test_names_and_source_filters():
    assert search_assets('demo', 'apple')['assets'][0]['symbol'] == 'AAPL'
    assert search_assets('coinbase', 'bitcoin')['assets'][0]['symbol'] == 'BTC-USD'
    assert search_assets('coinbase', 'apple')['assets'] == []
    assert search_assets('alpha', 'bitcoin')['assets'] == []


def test_online_matches_deduplicate_and_filter():
    with patch('src.assets.yf.Search') as search:
        search.return_value.quotes = [
            {'symbol': 'AAPL', 'quoteType': 'EQUITY', 'longname': 'Apple'},
            {'symbol': 'NEW', 'quoteType': 'EQUITY', 'longname': 'New company'},
            {'symbol': '<script>', 'quoteType': 'EQUITY'},
        ]
        results = search_assets('market', 'apple')['assets']
    assert [a['symbol'] for a in results] == ['AAPL', 'NEW']


def test_provider_failure_preserves_builtin_matches():
    with patch('src.assets.yf.Search', side_effect=RuntimeError('offline')):
        result = search_assets('market', 'apple')
    assert result['assets'][0]['symbol'] == 'AAPL'
    assert result['warning']


def test_cached_search_is_offline_and_keeps_familiar_funds_visible():
    directory = AssetDirectory()
    directory.refresh('equities', lambda: [dict(symbol=f'ASSET{i}',name='Example 500 fund',type='ETF') for i in range(30)])
    with patch('src.assets.yf.Search', side_effect=AssertionError('Cached search must not request Yahoo')) as online:
        result = search_assets('market','500')
    online.assert_not_called()
    assert result['assets'][0]['symbol'] == 'SPY'
    assert any(a['symbol'] == 'VOO' for a in result['assets'])
