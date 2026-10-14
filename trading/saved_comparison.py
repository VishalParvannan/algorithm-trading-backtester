"""Compare stored results and optionally rerun on a shared price snapshot."""
from io import StringIO
import pandas as pd
from .storage import ExperimentStore


def compare_saved(owner, identifiers, harmonize=False):
    if not isinstance(identifiers,list) or not 2<=len(identifiers)<=5 or any(not isinstance(key,str) for key in identifiers) or len(set(identifiers))!=len(identifiers):
        raise ValueError('Choose two to five distinct saved experiments.')
    identifiers=list(dict.fromkeys(identifiers))
    database=ExperimentStore()
    records=[database.get(owner,key) for key in identifiers]
    first=records[0]
    keys=['ticker','source','start','end','capital','commission','slippage','execution_price','allocation','share_mode','periods_per_year','market_calendar']
    defaults=dict(capital=10000,commission=.1,slippage=.05,execution_price='Close',allocation=100,share_mode='fractional',periods_per_year=252,market_calendar='auto')
    mismatches=[key for key in keys if len({str(r['config'].get(key,defaults.get(key))) for r in records})>1]
    if len({r['dataset_hash'] for r in records})>1:
        mismatches.append('price snapshot')
    rows=[]
    if harmonize:
        if any(r['result']['ticker']!=first['result']['ticker'] for r in records):
            raise ValueError('A shared-snapshot comparison requires the same asset in every saved run.')
        data=pd.read_csv(StringIO(database.dataset(owner,identifiers[0])),index_col=0,parse_dates=True)
        from backend.backtest_service import run_backtest
        for key,record in zip(identifiers,records):
            config={**record['config'],**{k:first['config'].get(k,defaults.get(k)) for k in keys}}
            config.update(compare_strategies=[],holdout=False,robustness=False)
            result=run_backtest(config,data=data)
            rows.append(dict(id=key,result=result))
    else:
        rows=[dict(id=key,result=record['result']) for key,record in zip(identifiers,records)]
    return dict(rows=rows,mismatches=mismatches,harmonized=harmonize,
                method='Rerun on the first selected experiment’s exact prices, dates, capital, and execution assumptions.' if harmonize else 'Original saved results; differing settings and datasets are highlighted.')
