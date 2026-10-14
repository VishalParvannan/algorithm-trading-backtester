"""Bounded sensitivity grids and chronological training-only selection."""
import numpy as np
from .catalog import STRATEGIES, build_strategy
from .research import engine


def candidates(config):
    parameters = STRATEGIES[config.get('strategy','ma')][3]
    if not parameters:
        return None, [config]
    name = config.get('sensitivity_parameter') or parameters[0]['name']
    definition = next((p for p in parameters if p['name']==name), None)
    if definition is None:
        raise ValueError('Choose a sensitivity parameter belonging to this strategy.')
    center=float(config.get(name,definition['default']))
    values=sorted(set(max(definition['min'],min(definition['max'],round(center*factor/definition['step'])*definition['step'])) for factor in (.5,.75,1,1.25,1.5)))
    result=[]
    for value in values:
        candidate={**config,name:value}
        try:
            build_strategy(candidate)
            result.append(candidate)
        except ValueError:
            continue
    if not result:
        raise ValueError('No valid parameter candidates. Check the strategy settings.')
    return name,result


def robustness(config,data,cancel_check=None):
    name,grid=candidates(config)
    count=int(config.get('walk_folds',3))
    if not 2<=count<=5 or len(data)//2<3 or len(data)-len(data)//2<count*3:
        raise ValueError('Walk-forward testing requires 2–5 folds and at least three bars per training/test period.')
    sensitivity=[]
    # Full-sample sensitivity is exploratory; it never supplies the fold winner.
    for candidate in grid:
        run=engine(candidate,build_strategy(candidate),data.Close,cancel_check).run(data)
        sensitivity.append(dict(value=candidate.get(name) if name else None,metrics=run.metrics))
    initial=len(data)//2
    boundaries=np.linspace(initial,len(data),count+1,dtype=int)
    folds=[]
    for number,(start,stop) in enumerate(zip(boundaries[:-1],boundaries[1:]),1):
        train=data.iloc[:start];test=data.iloc[start:stop]
        scores=[]
        for candidate in grid:
            fit=engine(candidate,build_strategy(candidate),train.Close,cancel_check).run(train)
            scores.append(fit.metrics['total_return'])
        chosen=grid[int(np.argmax(scores))]
        # Only training scores select parameters; future test returns are excluded.
        underlying=build_strategy(chosen)
        history=data.iloc[:stop]
        # Indicators can use prior history, but the account runs only on test dates.
        class WarmedStrategy:
            def generate_signals(self, portion):
                return underlying.generate_signals(history).reindex(portion.index)
        run=engine(chosen,WarmedStrategy(),test.Close,cancel_check).run(test)
        folds.append(dict(fold=number,train_start=str(train.index[0].date()),train_end=str(train.index[-1].date()),
                          test_start=str(test.index[0].date()),test_end=str(test.index[-1].date()),
                          selected_value=chosen.get(name) if name else None,training_return=max(scores),metrics=run.metrics,bars=len(test)))
    return dict(parameter=name,sensitivity=sensitivity,folds=folds,
                method='Expanding training window; parameter selected by training net return only. Independent cash per test fold; training history warms indicators; first test bar remains cash before delayed fills. Sensitivity uses the full sample and is exploratory, not unseen performance.')
