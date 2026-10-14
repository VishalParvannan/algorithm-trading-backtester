"""Shared dashboard strategy definitions and validated construction."""
import math
from .assets import ASSETS

from .strategy import (
    BollingerBandsStrategy, BuyAndHoldStrategy, DonchianBreakoutStrategy,
    EMACrossoverStrategy, MACDStrategy, MomentumStrategy,
    MovingAverageStrategy, RSIStrategy,
)


def parameter(name, label, default, minimum=1, maximum=5000, step=1):
    return dict(name=name, label=label, default=default, min=minimum, max=maximum, step=step)


STRATEGIES = {
    "ma": (MovingAverageStrategy, "Moving average crossover", "Hold while the fast simple average is above the slow average.", [parameter("fast", "Fast window", 20), parameter("slow", "Slow window", 50)]),
    "ema": (EMACrossoverStrategy, "EMA crossover", "Follow trends with exponential averages that give recent prices more weight.", [parameter("fast", "Fast window", 12), parameter("slow", "Slow window", 26)]),
    "momentum": (MomentumStrategy, "Momentum", "Hold when the return over the lookback window is positive.", [parameter("lookback", "Lookback (bars)", 60)]),
    "rsi": (RSIStrategy, "RSI mean reversion", "Buy below the oversold level, hold, then exit above the overbought level.", [parameter("period", "RSI period", 14), parameter("oversold", "Oversold", 30, 1, 99, 0.1), parameter("overbought", "Overbought", 70, 1, 99, 0.1)]),
    "macd": (MACDStrategy, "MACD", "Hold while the MACD line is above its signal average.", [parameter("fast", "Fast EMA", 12), parameter("slow", "Slow EMA", 26), parameter("signal_period", "Signal period", 9)]),
    "bollinger": (BollingerBandsStrategy, "Bollinger Bands", "Buy below the lower band and exit when price recovers to the rolling mean.", [parameter("period", "Band period", 20, 2), parameter("std_dev", "Std. deviations", 2, 0.1, 10, 0.1)]),
    "donchian": (DonchianBreakoutStrategy, "Donchian breakout", "Buy above the prior closing-price channel; exit below the shorter low channel.", [parameter("entry_period", "Entry window", 20, 2), parameter("exit_period", "Exit window", 10)]),
    "buyhold": (BuyAndHoldStrategy, "Buy & hold", "Invest on the first executable bar and hold through the test period.", []),
}

SOURCES = [
    dict(id="demo", name="Sample market · synthetic data", note="Reproducible sample data for exploring strategies.", example="SPY"),
    dict(id="market", name="Yahoo Finance · equities & ETFs", note="Adjusted daily prices. Try SPY, AAPL, MSFT, or BTC-USD. Internet required.", example="SPY"),
    dict(id="coinbase", name="Coinbase · crypto", note="Daily crypto candles. Use a USD pair such as BTC-USD or ETH-USD. Internet required.", example="BTC-USD"),
    dict(id="alpha", name="Alpha Vantage · equities", note="Raw daily prices. API key required; full history requires a premium key. Compact returns the latest 100 bars.", example="IBM"),
    dict(id="csv", name="CSV upload · your own data", note="Upload daily data with Date and Close columns. Optional: Open, High, Low, Volume. No download needed.", example="CUSTOM"),
]


def catalog():
    return {"sources": SOURCES, "assets": ASSETS, "strategies": [dict(id=key, name=name, description=description, parameters=params) for key, (_, name, description, params) in STRATEGIES.items()]}


def build_strategy(config):
    key = config.get("strategy", "ma")
    if key not in STRATEGIES:
        raise ValueError("Choose a supported strategy.")
    cls, _, _, parameters = STRATEGIES[key]
    values = {}
    for spec in parameters:
        value = float(config.get(spec["name"], spec["default"]))
        if not math.isfinite(value) or not spec["min"] <= value <= spec["max"]:
            raise ValueError(f"{spec['label']} must be between {spec['min']} and {spec['max']}.")
        if spec["step"] == 1:
            if not value.is_integer():
                raise ValueError(f"{spec['label']} must be a whole number.")
            value = int(value)
        values[spec["name"]] = value
    return cls(**values)
