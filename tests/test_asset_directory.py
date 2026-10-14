import pytest

from trading.asset_directory import AssetDirectory, parse_equities


def test_refresh_persists_and_expires_daily(tmp_path):
    path = tmp_path / 'directory.sqlite'
    directory = AssetDirectory(path)
    asset = dict(symbol='AAPL', name='Apple', type='Stock')
    assert directory.refresh('equities', lambda: [asset], now=100000)
    reopened = AssetDirectory(path)
    assert reopened.search('market', 'apple') == [asset]
    assert not reopened.refresh('equities', lambda: pytest.fail('Not due'), now=100001)
    assert reopened.refresh('equities', lambda: [dict(symbol='MSFT',name='Microsoft',type='Stock')], now=186401)
    assert reopened.search('market', 'apple') == []
    assert reopened.search('market', 'Microsoft')[0]['symbol'] == 'MSFT'


def test_failed_or_empty_refresh_preserves_snapshot_and_throttles(tmp_path):
    directory = AssetDirectory(tmp_path / 'directory.sqlite')
    asset = dict(symbol='ETH-USD',name='Ethereum',type='Crypto')
    directory.refresh('crypto', lambda: [asset], now=100000)
    assert not directory.refresh('crypto', lambda: [], now=186401)
    assert directory.search('coinbase','ethereum') == [asset]
    assert directory.search('alpha','ethereum') == []
    assert directory.status()[0]['last_success'] == 100000
    assert directory.status()[0]['warning']
    assert not directory.refresh('crypto', lambda: pytest.fail('Retry too soon'), now=186402)
    def offline():
        raise OSError('offline')
    assert not directory.refresh('crypto', offline, now=190002)
    assert directory.search('coinbase','ethereum') == [asset]


def test_directory_parser_rejects_bad_downloads_and_test_securities():
    text = 'Symbol|Security Name|Test Issue|ETF\nAAPL|Apple|N|N\nTEST|Test|Y|N\nVOO|Vanguard|N|Y\nFile Creation Time: 1234||||\n'
    rows = parse_equities(text)
    assert [a['symbol'] for a in rows] == ['AAPL','VOO']
    assert rows[1]['type'] == 'ETF'
    with pytest.raises(ValueError):
        parse_equities('<html>Service unavailable</html>')


def test_search_literals_and_symbol_priority(tmp_path):
    directory = AssetDirectory(tmp_path / 'directory.sqlite')
    directory.refresh('equities',lambda:[dict(symbol='AA',name='Other'),dict(symbol='A',name='Company')],now=100000)
    assert directory.search('market','A')[0]['symbol']=='A'
    assert directory.search('market','%') == []
