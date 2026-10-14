"""Check dashboard requests against the real engine without network access."""
import json
import re
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from app import Handler, run_backtest
from src.catalog import catalog


def test_all_options_remain_visible_without_catalog_endpoint():
    html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    definitions = catalog()
    for name, items in [("source", definitions["sources"]), ("strategy", definitions["strategies"])]:
        select = re.search(rf'<select name="{name}" id="{name}">(.*?)</select>', html, re.S)[1]
        assert re.findall(r'<option value="([^"]+)"', select) == [item["id"] for item in items]
    snapshot = re.search(r'<script id="dashboard-catalog" type="application/json">(.*?)</script>', html, re.S)[1]
    assert json.loads(snapshot) == definitions


@pytest.mark.parametrize("strategy", ["ma", "momentum", "rsi", "ema", "macd", "bollinger", "donchian", "buyhold"])
def test_sample_backtest(strategy):
    result = run_backtest({"start": "2022-01-01", "end": "2023-12-31", "strategy": strategy})
    assert result["demo"] is True
    assert len(result["dates"]) == len(result["equity"]) == len(result["benchmark"])
    assert result["benchmark"][0] == result["capital"]
    assert result["metrics"]["total_return"] == pytest.approx(result["equity"][-1] / result["equity"][0] - 1)
    assert all(t["side"] in {"Buy", "Sell"} for t in result["trades"])


def test_csv_dashboard():
    result = run_backtest({"start": "2025-01-01", "end": "2025-01-06", "source": "csv", "strategy": "buyhold", "csv_text": "Date,Close\n2025-01-02,100\n2025-01-03,101\n2025-01-06,104"})
    assert result["source"] == "csv"
    assert result["dates"] == ["2025-01-02", "2025-01-03", "2025-01-06"]
    assert result["demo"] is False
    assert result["trades"][0]["date"] == "2025-01-03"


@pytest.mark.parametrize("changes", [{"source": "unknown"}, {"strategy": "unknown"}, {"fast": 2.5}, {"strategy": "bollinger", "std_dev": "nan"}, {"strategy": "donchian", "entry_period": 5, "exit_period": 10}, {"periods_per_year": 0}])
def test_reject_invalid_extended_configuration(changes):
    with pytest.raises(ValueError):
        run_backtest({"start": "2022-01-01", "end": "2023-12-31", **changes})


@pytest.mark.parametrize("changes", [{"end": "2021-01-01"}, {"capital": -1}, {"commission": -1}, {"slippage": "nan"}, {"fast": 50, "slow": 20}, {"ticker": "<script>"}])
def test_invalid_configuration(changes):
    with pytest.raises(ValueError):
        run_backtest({"start": "2022-01-01", "end": "2023-12-31", **changes})


def test_dashboard_http():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for route, expected in [("/", b"Backtest Lab"), ("/app.js", b"/api/backtest"), ("/style.css", b"@media"), ("/navigation.js", b"data-nav-page")]:
            with urlopen(base + route, timeout=10) as response:
                assert response.status == 200
                assert expected in response.read()
        request = Request(base + "/api/backtest", data=json.dumps({"start": "2022-01-01", "end": "2023-01-01"}).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=10) as response:
            assert json.load(response)["demo"] is True
        with urlopen(base + "/api/catalog", timeout=10) as response:
            options = json.load(response)
            assert len(options["sources"]) == 5
            assert len(options["strategies"]) == 8
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
