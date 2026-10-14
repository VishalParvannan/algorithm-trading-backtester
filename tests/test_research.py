"""Verify same-snapshot strategy comparisons and chronological holdout tests."""
from concurrent.futures import CancelledError

import pandas as pd
import pytest

from backend.backtest_service import run_backtest
from trading.analysis import completed_trades
from trading.backtester import Backtester
from trading.portfolio import Portfolio
from trading.strategy import BuyAndHoldStrategy
from trading.storage import ExperimentStore


def test_cash_covers_costs_and_hold_does_not_rebalance():
    portfolio = Portfolio(10000, commission=0.01, slippage=0.02)
    portfolio.execute_target_position(1, 100, pd.Timestamp('2025-01-01'))
    assert portfolio.cash >= 0
    assert portfolio.shares == pytest.approx(10000 / (100 * 1.02 * 1.01))
    for price in [105, 90, 110]:
        portfolio.execute_target_position(1, price, pd.Timestamp('2025-01-02'))
    assert len(portfolio.trades) == 1
    portfolio.execute_target_position(0, 110, pd.Timestamp('2025-01-03'))
    assert portfolio.shares == pytest.approx(0)
    assert portfolio.cash >= 0


def test_whole_shares_and_allocation():
    portfolio = Portfolio(1000, commission=0.01, fractional_shares=False)
    portfolio.execute_target_position(0.5, 110, pd.Timestamp('2025-01-01'))
    assert portfolio.shares == 4
    assert portfolio.cash > 500


def test_completed_trades_include_fees_without_double_slippage():
    trades = pd.DataFrame([
        dict(timestamp=pd.Timestamp('2025-01-01'), quantity=10, price=101, commission=10),
        dict(timestamp=pd.Timestamp('2025-01-03'), quantity=-4, price=109, commission=4),
        dict(timestamp=pd.Timestamp('2025-01-04'), quantity=-6, price=99, commission=6),
    ])
    closed, summary = completed_trades(trades)
    assert closed[0]['net_pnl'] == 24
    assert closed[1]['net_pnl'] == -24
    assert summary['realized_pnl'] == 0
    assert summary['win_rate'] == 0.5
    assert summary['profit_factor'] == 1
    assert summary['open_quantity'] == 0


def test_next_open_fill_and_close_valuation():
    data = pd.DataFrame({'Open':[100,120,110], 'Close':[110,130,125]}, index=pd.date_range('2025-01-01',periods=3))
    result = Backtester(BuyAndHoldStrategy(), commission=0, slippage=0, execution_price='Open').run(data)
    assert result.trade_history.iloc[0]['price'] == 120
    assert result.equity_curve.iloc[1] == pytest.approx(10000 / 120 * 130)
    assert result.profit_factor() is None
    assert 'N/A' in result.print_report()


def test_cancellation_before_execution():
    data = pd.DataFrame({'Close':[100,101,102]}, index=pd.date_range('2025-01-01',periods=3))
    with pytest.raises(CancelledError):
        Backtester(BuyAndHoldStrategy(), cancel_check=lambda:True).run(data)


def test_comparison_and_disjoint_holdout():
    result = run_backtest(dict(start='2022-01-01',end='2023-12-31',strategy='ma',fast=5,slow=20,compare_strategies=['ema','rsi'],holdout=True,train_percent=70))
    assert {row['strategy'] for row in result['comparison']} == {'ma','buyhold','ema','rsi'}
    periods=result['holdout']['periods']
    assert periods[0]['end'] < periods[1]['start']
    assert sum(p['bars'] for p in periods) == len(result['dates'])
    assert result['comparison'][0]['parameters'] == {'fast':5,'slow':20}
    assert next(r for r in result['comparison'] if r['strategy']=='ema')['parameters'] == {'fast':12,'slow':26}


def test_saved_snapshot_replays_without_provider_and_hides_keys(tmp_path):
    config=dict(start='2025-01-01',end='2025-01-10',source='csv',strategy='buyhold',api_key='secret',csv_text='Date,Close\n2025-01-02,100\n2025-01-03,105\n2025-01-06,102')
    result,data=run_backtest(config,include_data=True)
    store=ExperimentStore(tmp_path/'runs.sqlite')
    saved=store.save('alice',config,result,data)
    assert len(store.list('alice')) == 1
    assert store.list('bob') == []
    with pytest.raises(KeyError):store.get('bob',saved['experiment_id'])
    record=store.get('alice',saved['experiment_id'])
    assert 'api_key' not in record['config'] and 'csv_text' not in record['config']
    replay=run_backtest(record['config'],data=data)
    assert replay['equity'] == saved['equity']
    assert store.dataset('alice',saved['experiment_id']).startswith('Date,Close')
