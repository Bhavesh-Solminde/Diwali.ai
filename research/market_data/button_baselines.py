"""Fixed aligned button baselines. Scores FIT and DEVELOPMENT only; no test labels."""
import argparse
import json
from pathlib import Path
import numpy as np
from .build_pilot import feature_dtype,WARMUP
from .trade_alignment import transform
from .review_pilot import metrics,utc
from .validate_archive import save,file_hash


def predict(raw,indices,book,trades,majority):
    ci=indices[:,2];prev=raw[ci-1];prior=raw[ci-2];anchor=prev[:,3]
    move=(anchor/prior[:,3]-1)*10000;magnitude=np.abs(move)
    b=book[indices[:,4]-1]['x'];flow=[];recent=[]
    for row,a in zip(indices,anchor):
        values=trades[row[3]:row[4]]['x'][:,:4].astype(np.float64)
        aligned=transform(values,a)  # Same common transform used by the live adapter.
        # Recover linear qty for the imbalance; no message/execution counts.
        qty=np.expm1(aligned[:,:2]).sum(axis=0);flow.append(np.sign(qty[0]-qty[1]))
        nonempty=np.flatnonzero(values[:,:2].sum(axis=1)>0)
        recent.append(aligned[nonempty[-1],4] if len(nonempty) else 0.)
    signals={'persistence':np.zeros(len(ci)),'momentum':move,'reversal':-move,
        'fit_majority':np.full(len(ci),majority)*magnitude,
        'book_imbalance':np.sign(b[:,83])*magnitude,'trade_flow':np.asarray(flow)*magnitude,
        'recent_vwap_persistence':np.asarray(recent)}
    up=(prev[:,1]-np.maximum(prev[:,0],prev[:,3]))/anchor*10000
    down=(np.minimum(prev[:,0],prev[:,3])-prev[:,2])/anchor*10000
    result={name:np.column_stack((np.zeros(len(ci)),np.maximum(0,s)+up,np.minimum(0,s)-down,s)) for name,s in signals.items()}
    # Recent observed VWAP anchors both next open and close; historical wicks set range.
    s=np.asarray(recent);result['recent_vwap_persistence']=np.column_stack((s,s+up,s-down,s))
    return result


def run(aligned,config,output):
    output.mkdir(parents=True,exist_ok=True)
    contract=json.loads((aligned/'alignment-contract.json').read_text());dataset=Path(contract['parent_dataset'])
    m=json.loads((dataset/'dataset-manifest.json').read_text());protocol=json.loads(config.read_text())
    if m['fingerprint']!=contract['parent_dataset_fingerprint']:raise ValueError('Dataset fingerprint changed')
    if file_hash(aligned/'scalers.json')!=contract['scaler_sha256']:raise ValueError('Aligned scaler changed')
    protocol_hash=file_hash(config)
    existing=output/'frozen-protocol.json'
    if existing.exists() and json.loads(existing.read_text())['sha256']!=protocol_hash:
        raise ValueError('Changed protocol requires a NEW experiment output directory')
    save(output/'frozen-protocol.json',{'sha256':protocol_hash,'protocol':protocol,
        'aligned_contract_sha256':file_hash(aligned/'alignment-contract.json'),
        'frozen_before_scoring':True})
    raw=np.load(dataset/'candle-raw.npy')
    book=np.memmap(m['book_source'],mode='r',dtype=feature_dtype('book'))
    trades=np.memmap(m['trade_source'],mode='r',dtype=feature_dtype('trades'))
    loaded={}
    for part in ('fit','development'):
        ip=dataset/f'{part}-phase15-grace1000-indices.npy';tp=dataset/f'{part}-phase15-grace1000-targets.npy'
        if file_hash(ip)!=m['artifact_sha256'][ip.name] or file_hash(tp)!=m['artifact_sha256'][tp.name]:raise ValueError('Changed inputs/labels')
        idx=np.load(ip);target=np.load(tp)
        if not np.array_equal(target,raw[(idx[:,1]-WARMUP)//60000]):raise ValueError('Target alignment mismatch')
        actual=(target[:,:4]/raw[idx[:,2]-1,3,None]-1)*10000
        loaded[part]=(idx,actual)
    fit_sign=np.sign(loaded['fit'][1][:,3]);majority=max((-1,0,1),key=lambda s:int(np.sum(fit_sign==s)))
    scores={}
    for part,(idx,actual) in loaded.items():
        predictions=predict(raw,idx,book,trades,majority)
        if set(predictions)!=set(protocol['baselines']):raise ValueError('Baseline rules differ from frozen protocol')
        days=np.array([utc(t)[:10] for t in idx[:,1]])
        scores[part]={name:{'overall':metrics(p,actual),'by_day':{d:metrics(p[days==d],actual[days==d]) for d in sorted(set(days))}} for name,p in predictions.items()}
    result={'state':'development_baselines_complete','protocol_sha256':protocol_hash,
        'aligned_contract_sha256':file_hash(aligned/'alignment-contract.json'),
        'fit_majority_direction':int(majority),'scores':scores,'test_targets_scored':False,
        'calibration_targets_scored':False,'neural_training_started':False,
        'direction_reference':'close versus final input candle close; down/flat/up exact classes',
        'baseline_formula':'previous move magnitude and wick excursions; recent_vwap anchors open/close at last nonempty complete receipt-second VWAP',
        'limitations':['Historical candle availability remains assumed.',
            'Three development days give limited day-to-day uncertainty; neighboring samples are dependent.',
            'These rules are not calibrated win probabilities or profitability estimates.']}
    save(output/'baseline-results.json',result)
    print(json.dumps({k:{'close_mae_bp':v['overall']['ohlc_mae_bp'][3],
        'mean_ohlc_mae_bp':float(np.mean(v['overall']['ohlc_mae_bp'])),
        'direction_accuracy':v['overall']['close_direction_accuracy']} for k,v in scores['development'].items()},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('aligned','config','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.aligned,a.config,a.output)
