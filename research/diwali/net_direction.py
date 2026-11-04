"""Net displacement at the final forecast close; distinct from candle colour."""
import numpy as np
from .probability import metrics


def net_probabilities(price_probabilities):
    p=np.asarray(price_probabilities)
    if p.shape[-1]!=26 or not np.isfinite(p).all() or (p<0).any() or not np.allclose(p.sum(-1),1,atol=1e-6):raise ValueError('Expected normalized26-bin probabilities')
    # Bin12 is (-.5,0]; bin13 starts strictly above zero.
    return np.stack([p[...,:13].sum(-1),p[...,13:].sum(-1)],axis=-1)


def direction_summary(p):
    p=net_probabilities(p)
    if p.shape!=(15,2):raise ValueError('Expected15 forecasts')
    return {'up':float(p[-1,1]),'down_or_unchanged':float(p[-1,0]),
        'favoured_side':'up' if p[-1,1]>p[-1,0] else 'down_or_unchanged' if p[-1,0]>p[-1,1] else 'tie',
        'event':'15th forecast candle closes above the frozen input reference versus at or below it',
        'horizon':15,'exact_unchanged_separately_estimated':False,'scope':'Net endpoint displacement, not majority of green candles, monotone path or profit probability.'}


def net_metrics(labels,p):
    y=(np.asarray(labels)>12).astype(np.int64);p=net_probabilities(p);chosen=p.argmax(1);truth=np.eye(2)[y]
    return {'examples':len(y),'up_frequency':float(y.mean()),'accuracy':float((chosen==y).mean()),
        'binary_log_loss':float(-np.log(np.maximum(p[np.arange(len(y)),y],1e-15)).mean()),
        'brier_up':float(((p[:,1]-y)**2).mean()),'mean_up_probability':float(p[:,1].mean()),
        'confusion_actual_rows_predicted_columns':[[int(((y==i)&(chosen==j)).sum()) for j in range(2)] for i in range(2)],
        'confidence_groups':[{'minimum':v,'n':int((p.max(1)>=v).sum()),'accuracy':float((chosen[p.max(1)>=v]==y[p.max(1)>=v]).mean()) if (p.max(1)>=v).any() else None} for v in [.5,.6,.7,.8,.9]],
        'up_calibration':[{'lower':float(lo),'n':int(keep.sum()),'mean_claim':float(p[keep,1].mean()),'observed_up':float(y[keep].mean())} for lo in np.arange(0,1,.1) if (keep:=((p[:,1]>=lo)&(p[:,1]<(lo+.1) if lo<.9 else p[:,1]<=1))).any()],
        'labels':['down_or_unchanged','up'],'event':'Final forecast close versus frozen reference; equality in down_or_unchanged.'}
