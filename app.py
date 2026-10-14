"""Local dashboard for the existing backtesting engine. Run: python app.py."""
import json
import math
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import pandas as pd

from src.backtester import Backtester
from src.catalog import SOURCES, STRATEGIES, build_strategy, catalog
from src.sources import load_source, normalize_daily
from src.analysis import completed_trades
from src.research import compare, holdout, engine
from src.storage import ExperimentStore
from src.data_quality import audit
from src.robustness import robustness

ROOT = Path(__file__).parent / "web"


def run_backtest(config, data=None, include_data=False, cancel_check=None):
    start, end = date.fromisoformat(config["start"]), date.fromisoformat(config["end"])
    if start >= end or (end - start).days > 7305:
        raise ValueError("Choose a date range between 1 day and 20 years.")
    capital = float(config.get("capital", 10000))
    commission, slippage = float(config.get("commission", 0.1)), float(config.get("slippage", 0.05))
    if not all(math.isfinite(v) for v in (capital, commission, slippage)) or capital <= 0 or not 0 <= commission <= 10 or not 0 <= slippage <= 10:
        raise ValueError("Enter positive capital and costs between 0% and 10%.")
    ticker = str(config.get("ticker", "SPY")).strip().upper()
    if not ticker or len(ticker) > 16 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=" for c in ticker):
        raise ValueError("Enter a valid ticker symbol.")
    strategy = build_strategy(config)
    source = config.get("source", "demo")
    demo = source == "demo"
    if source not in {s["id"] for s in SOURCES}:
        raise ValueError("Choose a supported data source.")
    if data is None:
        data = load_source(source, ticker, start, end, config)
    else:
        try:
            data = normalize_daily(data, start, end)
        except ValueError as exc:
            raise ValueError(f'{source} · {ticker} · saved data · {start} to {end}\n{exc}\nCorrect the original data and create a new experiment.') from None
    if len(data) < 3:
        raise ValueError(f"{source} · {ticker} · {start} to {end}: Only {len(data)} valid bars are available. Choose a longer range or another source; at least three bars are required.")
    periods_per_year = int(config.get("periods_per_year", 365 if source == "coinbase" else 252))
    if periods_per_year not in {252, 365}:
        raise ValueError("Choose a 252-day or 365-day trading calendar.")
    if config.get("share_mode", "fractional") not in {"fractional", "whole"}:
        raise ValueError("Choose fractional or whole shares.")
    config = {**config, "periods_per_year": periods_per_year}
    quality, quality_warnings = audit(data, source, ticker, config)
    try:
        result = engine(config, strategy, data.Close, cancel_check).run(data)
    except ValueError as exc:
        raise ValueError(f'{source} · {ticker} · {start} to {end}\n{exc}') from None
    closed, trade_summary = completed_trades(result.trade_history)
    def number(value):
        return float(value) if math.isfinite(float(value)) else None
    trades = [{"date": str(t.timestamp.date()), "side": "Buy" if t.quantity > 0 else "Sell", "price": number(t.price), "quantity": number(abs(t.quantity)), "commission": number(t.commission), "slippage": number(t.slippage_cost)} for t in result.trade_history.itertuples()]
    warnings = []
    warmup = max((getattr(strategy, name, 0) for name in ("slow", "lookback", "period", "entry_period")), default=0)
    warmup += getattr(strategy, "signal_period", 0)
    if len(data) <= warmup:
        warnings.append("The selected period is shorter than the strategy warm-up. Try a longer range or smaller windows.")
    if source == "alpha":
        warnings.append("Alpha Vantage prices are not adjusted for splits or dividends. Compact history includes only the latest 100 bars.")
    if (data.index[0].date() - start).days > 7 or (end - data.index[-1].date()).days > 7:
        warnings.append("Available data covers only part of the requested period; results use the dates shown above.")
    missing = quality['missing_calendar_bars']
    warnings.extend(quality_warnings)
    warnings.append(f"Signals use completed bars and execute at the next available bar's {config.get('execution_price','Close').lower()}. Slippage and commission apply to every fill; positions are valued at close. No liquidity or partial-fill model is applied.")
    output = {"ticker": ticker, "demo": demo, "source": source, "source_name": next(s["name"] for s in SOURCES if s["id"] == source), "strategy": config.get("strategy", "ma"), "strategy_name": STRATEGIES[config.get("strategy", "ma")][1], "periods_per_year": periods_per_year, "warnings": warnings, "capital": capital, "metrics": {k: number(v) for k, v in result.metrics.items()}, "dates": [str(d.date()) for d in data.index], "equity": list(map(number, result.equity_curve)), "benchmark": list(map(number, data.Close / data.Close.iloc[0] * capital)), "drawdown": list(map(number, (result.equity_curve / result.equity_curve.cummax() - 1) * 100)), "trades": trades, "completed_trades": closed, "trade_summary": trade_summary, "assumptions": {"execution_price": config.get("execution_price", "Close"), "share_mode": config.get("share_mode", "fractional"), "allocation_percent": float(config.get("allocation", 100)), "commission_percent": commission, "slippage_percent": slippage, "signals_delayed": True, "chart_benchmark": "Cost-free price growth from the first bar; comparison-table buy & hold uses the selected fill model and costs."}, "data_quality": {"bars": len(data), "missing_calendar_bars": missing}}
    output['data_quality'] = quality
    output['engine_version'] = '3'
    output['robustness'] = robustness(config,data,cancel_check) if config.get('robustness') else None
    output['assumptions'].update(price_basis=quality['price_basis'],market_calendar=quality['calendar'],dividend_cash_added=False,cagr_basis='Elapsed calendar time',execution_timing='Completed-bar signals; next available bar fill; close mark-to-market')
    output["comparison"] = compare(config, data, cancel_check) if config.get("compare_strategies") else []
    output["holdout"] = holdout(config, data, cancel_check) if config.get("holdout") else None
    # Strict JSON remains valid for zero-volatility comparison/holdout periods.
    def clean(value):
        if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list): return [clean(v) for v in value]
        if isinstance(value, float) and not math.isfinite(value): return None
        return value
    output = clean(output)
    return (output, data) if include_data else output


class Handler(BaseHTTPRequestHandler):
    def store(self):
        return ExperimentStore()

    def json_response(self, result, status=200):
        body = json.dumps(result, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/experiments":
            return self.json_response(self.store().list("local"))
        if path == "/api/draft":
            return self.json_response(self.store().draft("local"))
        if path.startswith("/api/experiments/"):
            try:
                return self.json_response(self.store().get("local", path.rsplit("/", 1)[-1]))
            except KeyError:
                return self.json_response({"error": "Experiment not found."}, 404)
        if urlparse(self.path).path == "/api/catalog":
            body = json.dumps(catalog()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        routes = {"/": "index.html", "/style.css": "style.css", "/app.js": "app.js", "/live.js": "live.js", "/research-ui.js": "research-ui.js", "/navigation.js": "navigation.js"}
        name = routes.get(urlparse(self.path).path)
        if name is None:
            self.send_error(404)
            return
        body = (ROOT / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", {"index.html": "text/html", "style.css": "text/css", "app.js": "text/javascript", "live.js": "text/javascript", "research-ui.js": "text/javascript", "navigation.js": "text/javascript"}[name] + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path not in {"/api/backtest", "/api/draft", "/api/replay"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 4_100_000:
                raise ValueError("Invalid request size.")
            config = json.loads(self.rfile.read(length))
            if not isinstance(config, dict):
                raise ValueError("Request must be an object.")
            if self.path == "/api/draft":
                self.store().save_draft("local", config)
                return self.json_response({"saved": True})
            if self.path == "/api/replay":
                from io import StringIO
                record = self.store().get("local", config["id"])
                data = pd.read_csv(StringIO(self.store().dataset("local", config["id"])), index_col=0, parse_dates=True)
                result = run_backtest(record["config"], data=data)
            else:
                result, data = run_backtest(config, include_data=True)
                if not result["demo"]:
                    result = self.store().save("local", config, result, data)
            status = 200
        except Exception as exc:
            result, status = {"error": str(exc)}, 400
        body = json.dumps(result, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("Backtest Lab is ready at http://localhost:8000 — Ctrl+C to stop.")
    import uvicorn
    uvicorn.run("server:application", host="127.0.0.1", port=8000)
