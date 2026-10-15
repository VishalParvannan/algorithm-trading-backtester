"""Build fixed UTC candles from sampled quotes without filling empty intervals."""
import pandas as pd

INTERVALS={'1m':'1min','5m':'5min','1d':'1D'}


def add_quote(state,price,timestamp):
    interval=state['config'].get('paper_interval','1m')
    start=timestamp.floor(INTERVALS[interval]);end=start+pd.Timedelta(INTERVALS[interval])
    current=state.get('current_candle');closed=False
    if current and start>pd.Timestamp(current['start']):
        # The new quote belongs to the next interval and cannot change the old close.
        if current['complete_from_start']:
            state['candles'].append(current)
            state['candles']=state['candles'][-20000:]
            closed=True
        state['current_candle']=None
    if not state.get('current_candle'):
        # Skip a first candle started midway through an interval.
        state['current_candle']=dict(start=start.isoformat(),end=end.isoformat(),Open=price,High=price,Low=price,Close=price,
                                    complete_from_start=bool(current) or timestamp==start)
    else:
        current=state['current_candle'];current['High']=max(current['High'],price);current['Low']=min(current['Low'],price);current['Close']=price
    return closed
