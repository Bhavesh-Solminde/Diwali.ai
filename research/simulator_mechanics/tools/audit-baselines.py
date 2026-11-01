"""Post-hoc stronger-baseline audit of existing unique origins; no fitting."""
import argparse
import gzip
import json
from collections import Counter
from pathlib import Path
import numpy as np


def summary(rows, rule, majority=1):
    predictions=np.array([predict(r,rule,majority) for r in rows])
    truth=np.array([r['actual'] for r in rows])
    recalls={str(k):float(np.mean(predictions[truth==k]==k)) if np.any(truth==k) else None for k in (-1,0,1)}
    return dict(n=len(rows),accuracy=float(np.mean(predictions==truth)) if len(rows) else None,
                balanced_accuracy=float(np.mean([v for v in recalls.values() if v is not None])) if len(rows) else None,
                per_class_recall=recalls,predictions=dict(Counter(map(int,predictions))),
                coverage=1.0 if len(rows) else 0)


def predict(r, rule, majority=1):
    return {'up':1,'down':-1,'neutral':0,'pilot_majority':majority,'momentum':r['momentum'],
            'reversal':-r['momentum'],'book':r['book']}[rule]


def paired(rows, left='book', right='reversal', alpha=.05):
    parents=sorted({r['run_id'] for r in rows})
    values=np.array([np.mean([int(predict(r,left)==r['actual'])-int(predict(r,right)==r['actual'])
                             for r in rows if r['run_id']==p]) for p in parents])
    if not len(values): return dict(parents=0)
    rng=np.random.default_rng(617)
    means=values[rng.integers(0,len(values),(10000,len(values)))].mean(axis=1)
    return dict(parents=len(parents),parent_mean_delta=float(values.mean()),
                origin_weighted_delta=float(np.mean([int(predict(r,left)==r['actual'])-int(predict(r,right)==r['actual']) for r in rows])),
                parent_sd=float(values.std(ddof=1)) if len(values)>1 else None,
                alpha=alpha,bootstrap_ci=list(map(float,np.quantile(means,[alpha/2,1-alpha/2]))),
                parent_deltas={p:float(v) for p,v in zip(parents,values)})


def main(root,output):
    with gzip.open(root/'main-analysis/origins.jsonl.gz','rt') as f:
        allrows=[json.loads(line) for line in f]
    rows=[r for r in allrows if r['phase']=='main' and r['group']=='all' and r['book'] is not None]
    assert len({(r['run_id'],r['candle']) for r in rows})==len(rows)==10168
    pilot=[r for r in allrows if r['phase']=='pilot' and r['group']=='all' and r['book'] is not None]
    counts=Counter(r['actual'] for r in pilot)
    majority=max((-1,0,1),key=lambda k:(counts[k],k))
    stats=json.loads((root/'main-analysis/statistics.json').read_text())
    candidate=30*470
    invalid=sum(r['excluded_locked_or_absent_origins'] for r in stats['runs'] if r['phase']=='main')
    result=dict(comparison_status='post_hoc_reversal_suggested_after_outcome_review',
        origins=len(rows),parents=len({r['run_id'] for r in rows}),candidate_origins=candidate,
        locked_or_absent_exclusions=invalid,missing_10bp_depth_exclusions=candidate-invalid-len(rows),
        coverage_of_all_candidates=len(rows)/candidate,labels=dict(Counter(r['actual'] for r in rows)),
        pilot_majority=majority,pilot_label_counts=dict(counts),
        rules={rule:summary(rows,rule,majority) for rule in ('up','down','neutral','pilot_majority','momentum','reversal','book')},
        book_minus_reversal=paired(rows),pilot_book_minus_reversal=paired(pilot))
    expected={'up':49.5771,'down':48.9477,'momentum':42.8698,'reversal':54.3371,'book':56.7172}
    for rule,value in expected.items(): assert abs(result['rules'][rule]['accuracy']*100-value)<.00006
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists(): raise FileExistsError(output)
    output.write_text(json.dumps(result,indent=2))
    print(json.dumps({k:result[k] for k in ('origins','parents','coverage_of_all_candidates','missing_10bp_depth_exclusions','book_minus_reversal','pilot_book_minus_reversal')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();main(a.root,a.output)
