"""Verified event inputs, explicit early-compression control and fit-only moments."""
import json
from pathlib import Path

import numpy as np
import torch

from ..market_data.validate_archive import file_hash
from .event_evaluation import eligible_origins

EDGES=np.array([-100,-60,-40,-30,-20,-12,-8,-5,-3,-2,-1,-.5,0,.5,1,2,3,5,8,12,20,30,40,60,100],np.float64)


def labels(returns):
    returns=np.asarray(returns,np.float64)
    if returns.shape[-1]!=15 or not np.isfinite(returns).all():
        raise ValueError('Invalid15-close targets')
    values=np.searchsorted(EDGES,returns,side='left')
    return np.where(returns>=2,np.maximum(values,16),values).astype(np.int64)


def one_second(events):
    """Explicit early-compression control, not claimed identical to the old feed.

    Keep per-second mean channels, last book state in the second, and event counts.
    Order and individual trade sizes within each second are discarded here only.
    """
    x=np.asarray(events,np.float32)
    if x.ndim!=2 or x.shape[1]!=103 or not len(x):raise ValueError('Invalid event matrix')
    sec=np.floor(x[:,84]).astype(int)
    if (sec<0).any() or (sec>=60).any():raise ValueError('Events outside60-second window')
    output=np.zeros((60,103),np.float32);n=np.bincount(sec,minlength=60)
    np.add.at(output,sec,x)
    output/=np.maximum(n,1)[:,None]
    # Each per-second state uses only that second's retained book transitions.
    # Empty intervals carry zero rather than an invented new observation.
    for s in np.unique(sec):
        rows=x[sec==s];books=rows[rows[:,80]>0]
        if len(books):output[s,:80]=books[-1,:80]
        output[s,80:82]=np.log1p(rows[:,80:82].sum(0))
    output[:,84]=np.arange(60)+.5
    return output


class Moments:
    def __init__(self,width):self.n=0;self.mean=np.zeros(width,np.float64);self.m2=np.zeros(width,np.float64)
    def add(self,rows):
        x=np.asarray(rows,np.float64).reshape(-1,len(self.mean))
        if not np.isfinite(x).all():raise ValueError('Nonfinite fit inputs')
        if not len(x):return
        n=len(x);mean=x.mean(0);m2=((x-mean)**2).sum(0);delta=mean-self.mean;total=self.n+n
        self.m2+=m2+delta**2*self.n*n/total;self.mean+=delta*n/total;self.n=total
    def record(self):
        if not self.n:raise ValueError('Empty fitted transform')
        sd=np.sqrt(self.m2/self.n);sd=np.where(sd<1e-6,1.,sd)
        return {'count':self.n,'mean':self.mean.tolist(),'std':sd.tolist()}


def normalize(x,record):
    return ((np.asarray(x,np.float32)-np.asarray(record['mean'],np.float32))/np.asarray(record['std'],np.float32)).astype(np.float32)


class EventData:
    def __init__(self,cohort,features,content_audit):
        self.root=Path(cohort);self.features=Path(features);croot=self.root/'candles'
        report=json.loads((self.root/'report.json').read_text());cr=json.loads((croot/'report.json').read_text());fr=json.loads((self.features/'report.json').read_text())
        if report['state']!='complete' or fr['state']!='complete':raise ValueError('Incomplete cohort')
        audit=json.loads(Path(content_audit).read_text())
        if not audit.get('content_gate_passed') or audit['cohort_sha256']!=file_hash(self.root/'report.json') or audit['maximum_close_difference']!=0:
            raise ValueError('Missing or mismatched independent content audit')
        if report['candle_report_sha256']!=file_hash(croot/'report.json') or fr['candle_report_sha256']!=file_hash(croot/'report.json'):raise ValueError('Mismatched candle cohort')
        for name,sha in cr['artifact_sha256'].items():
            if file_hash(croot/name)!=sha:raise ValueError('Changed candle or target contents')
        if file_hash(self.features/'inputs.json')!=fr['ledger_sha256']:raise ValueError('Changed feature ledger')
        rows=json.loads((self.features/'inputs.json').read_text());self.entries={r['input_row']:r for r in rows}
        for r in rows:
            if file_hash(self.features/r['file'])!=r['sha256']:raise ValueError('Changed event features')
        self.metadata=json.loads((croot/'input-metadata.json').read_text());targets=json.loads((croot/'targets.json').read_text())
        self.ids=np.array([r['input_row'] for r in targets],np.int64)
        if len(set(self.ids))!=len(self.ids) or any(i not in self.entries for i in self.ids):raise ValueError('Incomplete/duplicate feature origins')
        self.returns=np.asarray([r['returns_bp'] for r in targets],np.float64);self.y=labels(self.returns)
        self.cutoffs=np.array([self.metadata[i]['input_cutoff_ns'] for i in self.ids],np.int64)
        self.starts=np.array([r['target_start_ns'] for r in targets],np.int64)
        self.candles=np.load(croot/'input-candles.npy',mmap_mode='r');self.candle_masks=np.load(croot/'input-candle-masks.npy',mmap_mode='r')
        self.hashes={'cohort':file_hash(self.root/'report.json'),'features':file_hash(self.features/'report.json'),'content_audit':file_hash(Path(content_audit))}
    def partition(self,fold,name):
        keep,counts=eligible_origins(self.cutoffs,self.starts,fold,name)
        return np.flatnonzero(keep),counts
    def raw(self,j):
        i=int(self.ids[j]);entry=self.entries[i]
        with np.load(self.features/entry['file']) as value:
            event=value['events'];seed=value['seed'];groups=value['time_groups'];ref=float(value['reference_from_seed_bp'])
        return event,groups,np.array(self.candles[i]),np.array(self.candle_masks[i]),seed,np.array([ref],np.float32)
    def fit_transforms(self,fit,representation):
        if representation not in ['events','one_second']:raise ValueError('Unknown representation')
        stats={n:Moments(w) for n,w in [('event',103),('candle',8),('seed',80),('reference',1)]}
        for j in fit:
            e,g,c,m,s,r=self.raw(j)
            stats['event'].add(one_second(e) if representation=='one_second' else e)
            stats['candle'].add(c[m]);stats['seed'].add(s[None]);stats['reference'].add(r[None])
        return {'representation':representation,'fit_origins':len(fit),'fit_cutoff_min_ns':int(self.cutoffs[fit].min()),
                'fit_cutoff_max_ns':int(self.cutoffs[fit].max()),'moments':{n:s.record() for n,s in stats.items()},'source_hashes':self.hashes}
    def batch(self,indices,transforms,device):
        values=[];stats=transforms['moments']
        for j in indices:
            e,g,c,m,s,r=self.raw(j)
            if transforms['representation']=='one_second':e=one_second(e);g=np.arange(60,dtype=np.int64)
            e=normalize(e,stats['event']);c=normalize(c,stats['candle']);c[~m]=0
            values.append((e,g,c,m,normalize(s,stats['seed']),normalize(r,stats['reference'])))
        n=max(len(v[0]) for v in values);b=len(values)
        event=np.zeros((b,n,103),np.float32);mask=np.zeros((b,n),bool);groups=np.zeros((b,n),np.int64)
        for i,v in enumerate(values):
            event[i,:len(v[0])]=v[0];mask[i,:len(v[0])]=True;groups[i,:len(v[0])]=v[1]
        args=[event,mask,np.stack([v[2] for v in values]),np.stack([v[4] for v in values]),groups,np.stack([v[3] for v in values]),np.stack([v[5] for v in values])]
        return tuple(torch.as_tensor(v,device=device) for v in args),torch.tensor(self.y[indices],dtype=torch.long,device=device)
