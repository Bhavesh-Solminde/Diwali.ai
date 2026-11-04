"""Exact timestamp bins for the early-compression control; frozen raw inputs unchanged."""
import hashlib
import io
import json
from functools import lru_cache

import numpy as np
import torch

from .event_data import EventData as OriginalData,one_second,normalize,Moments
from ..market_data.validate_archive import file_hash


def exact_one_second(events,elapsed_ns):
    times=np.asarray(elapsed_ns)
    if times.dtype.kind not in 'iu' or times.shape!=(len(events),):raise ValueError('Exact integer event times required')
    if ((times<0)|(times>=60*10**9)).any():raise ValueError('Exact event timestamp outside input window')
    x=np.array(events,np.float32,copy=True)
    # The old aggregator overwrites this channel with the second midpoint anyway.
    # Supply that exact bucket here instead of flooring a rounded float32 clock.
    x[:,84]=times//10**9+.5
    return one_second(x)


class ExactEventData(OriginalData):
    def __init__(self,cohort,features,content_audit):
        super().__init__(cohort,features,content_audit)
        root_report=json.loads((self.root/'report.json').read_text());wr=json.loads((self.root/'windows/report.json').read_text())
        if root_report['window_report_sha256']!=file_hash(self.root/'windows/report.json') or wr['ledger_sha256']!=file_hash(self.root/'windows/windows.json'):
            raise ValueError('Changed exact timestamp provenance')
        self.windows={r['input_row']:r for r in json.loads((self.root/'windows/windows.json').read_text())}
        for i in self.ids:
            if self.windows[int(i)]['input_cutoff_ns']!=self.metadata[int(i)]['input_cutoff_ns']:raise ValueError('Exact timestamp origin differs')
        self.hashes['exact_window_ledger']=wr['ledger_sha256']

    @lru_cache(maxsize=256)
    def exact_elapsed(self,j):
        i=int(self.ids[j]);r=self.windows[i];raw=(self.root/'windows'/r['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('Changed exact event indices')
        with np.load(io.BytesIO(raw)) as saved:
            indices=saved['events']
        elapsed=indices['available_ns']-r['window_start_ns']
        if len(elapsed)!=self.entries[i]['event_rows'] or ((elapsed<0)|(elapsed>=60*10**9)).any():raise ValueError('Invalid exact input times')
        return elapsed

    def fit_transforms(self,fit,representation):
        if representation!='one_second':return super().fit_transforms(fit,representation)
        stats={n:Moments(w) for n,w in [('event',103),('candle',8),('seed',80),('reference',1)]}
        for j in fit:
            e,g,c,m,s,r=self.raw(j)
            stats['event'].add(exact_one_second(e,self.exact_elapsed(int(j))))
            stats['candle'].add(c[m]);stats['seed'].add(s[None]);stats['reference'].add(r[None])
        return {'representation':representation,'timestamp_binning':'Exact integer availability nanoseconds, never float32 elapsed seconds',
                'fit_origins':len(fit),'fit_cutoff_min_ns':int(self.cutoffs[fit].min()),'fit_cutoff_max_ns':int(self.cutoffs[fit].max()),
                'moments':{n:s.record() for n,s in stats.items()},'source_hashes':self.hashes}

    def batch(self,indices,transforms,device):
        if transforms['representation']!='one_second':return super().batch(indices,transforms,device)
        values=[];stats=transforms['moments']
        for j in indices:
            e,g,c,m,s,r=self.raw(j);e=exact_one_second(e,self.exact_elapsed(int(j)))
            e=normalize(e,stats['event']);c=normalize(c,stats['candle']);c[~m]=0
            values.append((e,c,m,normalize(s,stats['seed']),normalize(r,stats['reference'])))
        b=len(values)
        args=[np.stack([v[0] for v in values]),np.ones((b,60),bool),np.stack([v[1] for v in values]),
              np.stack([v[3] for v in values]),np.tile(np.arange(60,dtype=np.int64),(b,1)),
              np.stack([v[2] for v in values]),np.stack([v[4] for v in values])]
        return tuple(torch.as_tensor(v,device=device) for v in args),torch.tensor(self.y[indices],dtype=torch.long,device=device)
