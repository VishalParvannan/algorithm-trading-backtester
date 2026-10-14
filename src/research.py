"""Compare strategies and evaluate a chronological holdout on one snapshot."""
from .catalog import STRATEGIES, build_strategy
from .backtester import Backtester


def engine(config, strategy, benchmark, cancel_check=None):
    return Backtester(strategy=strategy, initial_capital=float(config.get("capital", 10000)), commission=float(config.get("commission", 0.1))/100, slippage=float(config.get("slippage", 0.05))/100, benchmark=benchmark, periods_per_year=int(config.get("periods_per_year", 252)), execution_price=config.get("execution_price", "Close"), fractional_shares=config.get("share_mode", "fractional") == "fractional", allocation=float(config.get("allocation", 100))/100, cancel_check=cancel_check)


def compare(config, data, cancel_check=None):
    selected = config.get("compare_strategies", [])
    if not isinstance(selected, list) or len(selected) > 8 or any(key not in STRATEGIES for key in selected):
        raise ValueError("Choose up to eight supported strategies for comparison.")
    rows = []
    parameter_names = {p["name"] for entry in STRATEGIES.values() for p in entry[3]}
    for key in dict.fromkeys([config.get("strategy", "ma"), "buyhold", *selected]):
        run_config = {k: v for k, v in config.items() if k not in parameter_names}
        if key == config.get("strategy", "ma"):
            run_config.update({k: v for k, v in config.items() if k in parameter_names})
        run_config["strategy"] = key
        result = engine(run_config, build_strategy(run_config), data.Close, cancel_check).run(data)
        rows.append(dict(strategy=key, name=STRATEGIES[key][1], metrics=result.metrics, final_value=float(result.equity_curve.iloc[-1]), n_executions=result.n_trades, parameters={p["name"]: run_config.get(p["name"], p["default"]) for p in STRATEGIES[key][3]}))
    return rows


def holdout(config, data, cancel_check=None):
    fraction = float(config.get("train_percent", 70)) / 100
    if not 0.5 <= fraction <= 0.9:
        raise ValueError("Training portion must be between 50% and 90%.")
    split = int(len(data) * fraction)
    if split < 3 or len(data) - split < 3:
        raise ValueError("Holdout testing needs at least three bars in each period.")
    rows = []
    for label, portion in [("Training", data.iloc[:split]), ("Unseen test", data.iloc[split:])]:
        result = engine(config, build_strategy(config), portion.Close, cancel_check).run(portion)
        rows.append(dict(name=label, start=str(portion.index[0].date()), end=str(portion.index[-1].date()), bars=len(portion), metrics=result.metrics, final_value=float(result.equity_curve.iloc[-1])))
    return dict(method="Chronological holdout; fixed parameters, independent cash starts and indicator warm-up. No automatic optimization.", periods=rows)
