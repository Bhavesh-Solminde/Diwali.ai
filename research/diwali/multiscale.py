"""Diwali0.3: bounded long-context experiment from causal one-second sources."""
import argparse
import json
from pathlib import Path
import random
import time

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .model import WIDTH, CANDLE_SIZE, BOOK_SIZE
from .probability import labels, ProbabilityModel, probabilities, infer, metrics, calibrate
from .train import Data
from ..market_data.validate_archive import save, file_hash

BLOCK_WIDTH = 24
LONG_WIDTH = 84*BLOCK_WIDTH
SHORT_WIDTH = WIDTH+1
NAMES = ([f'book_mean_{i}' for i in range(7)]+[f'book_std_{i}' for i in range(7)] +
         ['log_buy_btc','log_sell_btc','log_buy_usdt','log_sell_usdt','signed_flow',
          'vwap_vs_reference_bp','book_coverage','trade_coverage','has_execution','available_fraction'])


def prefix_sources(book, trades, directory):
    """Only observed valid seconds contribute. Summaries never read beyond cutoff."""
    n = len(book)
    if n != len(trades):raise ValueError('Mismatched source grids')
    path = directory/'prefix.npy'
    prefix = np.lib.format.open_memmap(path, mode='w+', dtype=np.float64, shape=(n+1,20))
    prefix[0] = 0
    for start in range(0,n,100000):
        end = min(n,start+100000); b = book[start:end]; t = trades[start:end]
        expected = book[0]['time_ns']+np.arange(start,end,dtype=np.int64)*10**9
        if not np.array_equal(b['time_ns'],expected) or not np.array_equal(t['time_ns'],expected):
            raise ValueError('Nonconsecutive source seconds')
        bx = b['x'][:,80:].astype(np.float64); tx = t['x'][:,:4].astype(np.float64)
        bv = (b['valid']==1)&(b['receipt_ns']<=expected)&(b['event_ns']<=expected)&np.isfinite(bx).all(1)
        tv = (t['valid']==1)&(t['receipt_ns']<expected+10**9)&(t['event_ns']<expected+10**9)&np.isfinite(tx).all(1)&(tx>=0).all(1)
        bx = np.where(bv[:,None],bx,0); tx = np.where(tv[:,None],tx,0)
        values = np.column_stack([bx,bx**2,tx,bv,tv])
        prefix[start+1:end+1] = np.cumsum(values,axis=0)+prefix[start]
    prefix.flush()
    return prefix


def context(prefix, end, reference):
    """60 minute and 24 hour bins, oldest first, all ending <= snapshot."""
    if not 0<=end<len(prefix) or not reference>0:raise ValueError('Invalid cutoff/reference')
    outputs = []
    for count, step in [(60,60),(24,3600)]:
        ends = end-np.arange(count-1,-1,-1)*step; starts = ends-step
        a = np.clip(starts,0,end); z = np.clip(ends,0,end)
        sums = prefix[z]-prefix[a]; bc = sums[:,18]; tc = sums[:,19]
        mean = sums[:,:7]/np.maximum(bc[:,None],1)
        std = np.sqrt(np.maximum(0,sums[:,7:14]/np.maximum(bc[:,None],1)-mean**2))
        # Thin/invalid historical blocks are marked, not fabricated as good observations.
        book_ok = bc/step>=.9; trade_ok = tc/step>=.99
        mean[~book_ok]=0; std[~book_ok]=0
        qty = np.maximum(0,sums[:,14:18]); qty[~trade_ok]=0
        total = qty[:,:2].sum(1)
        flow = (qty[:,0]-qty[:,1])/np.maximum(total,1e-12)
        vwap = np.divide(qty[:,2:4].sum(1),total,out=np.full(count,reference,dtype=np.float64),where=total>0)
        out = np.column_stack([mean,std,np.log1p(qty),flow,(vwap/reference-1)*10000,
                               bc/step,tc/step,total>0,(z-a)/step])
        outputs.append(out)
    return np.concatenate(outputs).astype(np.float32)


class MultiModel(nn.Module):
    def __init__(self, mode):
        super().__init__(); self.mode=mode
        self.short=ProbabilityModel('sequence',SHORT_WIDTH)
        self.short.head=nn.Identity()
        self.minute=nn.GRU(BLOCK_WIDTH,16,batch_first=True)
        self.hour=nn.GRU(BLOCK_WIDTH,16,batch_first=True)
        self.head=nn.Linear(65,6)

    def forward(self,x):
        e=self.short.encoder; s=x[:,:SHORT_WIDTH]; raw=s[:,:-1]
        c=raw[:,:CANDLE_SIZE].reshape(-1,1440,8).transpose(1,2)
        _,ch=e.candle_gru(F.gelu(e.conv(c)).transpose(1,2))
        b=raw[:,CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1,60,87)
        t=raw[:,CANDLE_SIZE+BOOK_SIZE:].reshape(-1,60,5)
        _,fh=e.flow_gru(F.gelu(e.project(torch.cat([b,t],dim=2))))
        short=e.body(torch.cat([ch[-1],fh[-1]],dim=1))
        long=x[:,SHORT_WIDTH:].reshape(-1,84,BLOCK_WIDTH)
        if self.mode=='short_control':long=torch.zeros_like(long)
        _,m=self.minute(long[:,:60]); _,h=self.hour(long[:,60:])
        return self.head(torch.cat([short,s[:,-1:],m[-1],h[-1]],dim=1)).reshape(-1,2,3)


def directional(y,p):
    result={}
    for cutoff in [.5,.6,.7,.8,.9]:
        mask=(p.argmax(1)!=1)&(p.max(1)>=cutoff)
        result[str(cutoff)]={'n':int(mask.sum()),'coverage':float(mask.mean()),
            'accuracy':float((p.argmax(1)[mask]==y[mask]).mean()) if mask.any() else None}
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('data/models/diwali0.3'))
    a=parser.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
    began=time.time();torch.set_num_threads(4);device='mps' if torch.backends.mps.is_available() else 'cpu'
    protocol={'model':'diwali0.3','source_resolution':'existing one-second features; not raw-event sequence',
        'task':'same primary +/-2bp next-full-minute and secondary colour labels as diwali0.2',
        'context':'original 1440 candles +60 seconds; additional 60 minute bins +24 hour bins ending exactly at cutoff',
        'block_feature_names':NAMES,'historical_quality':'book >=90% valid seconds, trades >=99%; suppress unreliable content, preserve coverage and availability; no interpolation',
        'same_cohort':'exact saved diwali0.2 origins, labels and references, checked against frozen parent',
        'fit_dates':'Oct1-18 2026','development_dates':'Oct19-21','calibration_dates':'Oct22-23',
        'benchmark_dates':'Oct24-31 already inspected; not fresh confirmation',
        'models':['short_control','multiscale'],'seeds':[17,29,43],
        'selection':'mean primary development log loss; seed17 fixed; both comparisons reported even if long loses',
        'max_epochs':20,'patience':4,'lr':.0003,'weight_decay':.0001,'batch':128,
        'loss':'primary cross entropy +0.25 secondary cross entropy; gradient clip5',
        'calibration':'separate scalar temperature per model/head, calibration only, same bounded grid as0.2',
        'normalization':'fit-only short inputs unchanged; long summaries and displacement fit-only',
        'limitations':['No events finer than one second restored; no verified cancel/refill amounts.',
         'October source starts Oct1: earlier book/trades unavailable, explicitly masked.',
         'Invalid old seconds masked; coverage is provider-observation quality, not market liquidity.',
         'Historical candle availability assumed; receipt clocks unverified; no live/trading evidence.'],
        'source_sha256':file_hash(Path(__file__)),
        'parent_run_report_sha256':file_hash(Path('data/models/diwali0.2/report.json'))}
    save(out/'run-protocol.json',protocol)
    def status(stage,**kw):save(out/'status.json',{'model':'diwali0.3','stage':stage,'seconds':time.time()-began,**kw})
    status('Checking source integrity and building causal history')
    data=Data(Path('data/btc-perp/aligned-button-pilot-202610-v1'),out/'unused-cache')
    parent=Path('data/models/diwali0.2');prep=json.loads((parent/'preprocessing.json').read_text())
    if prep['dataset_fingerprint']!=data.manifest['fingerprint']:raise ValueError('Parent dataset changed')
    for kind,source in [('book',Path(data.manifest['book_source'])),('trades',Path(data.manifest['trade_source']))]:
        audit=source.parent/('book-extraction.json' if kind=='book' else 'trades-extraction.json')
        meta=json.loads(audit.read_text())
        if file_hash(source)!=meta['sha256']:raise ValueError('Changed raw feature bytes')
    prefix=prefix_sources(data.book,data.trades,out)
    parts={};mean=std=None
    for name in ['fit','development','calibration','locked_test']:
        status('Preparing multiscale windows',partition=name)
        # Outcome labels already exposed in0.2. No new test-based model selection.
        old=np.load(parent/f'{name}-predictions.npz');idx=old['indices'];refs=old['reference'];y=old['labels']
        base=np.load(data.root/f'{name}-phase15-grace1000-indices.npy');targets=np.load(data.root/f'{name}-phase15-grace1000-targets.npy')
        for p in [data.root/f'{name}-phase15-grace1000-indices.npy',data.root/f'{name}-phase15-grace1000-targets.npy']:
            if file_hash(p)!=data.manifest['artifact_sha256'][p.name]:raise ValueError('Changed partition')
        ids=np.searchsorted(base[:,0],idx[:,0])
        if not np.array_equal(base[ids],idx):raise ValueError('Changed origins')
        if not np.array_equal(labels(targets[ids,3],refs),y[:,0]):raise ValueError('Changed labels')
        short=np.asarray(np.load(parent/f'cache/{name}-x.npy',mmap_mode='r')[ids])
        # Recompute source input on every origin rather than silently trust old caches.
        for i,row in enumerate(idx):
            if not np.array_equal(short[i],data.feature(row)):raise ValueError('Changed cached model input')
        oldanchor=data.raw[idx[:,2]-1,3];delta=((refs/oldanchor-1)*10000-prep['delta_mean'])/prep['delta_std']
        long=np.array([context(prefix,int(row[4]),ref) for row,ref in zip(idx,refs)])
        if name=='fit':
            mean=long.mean(axis=(0,1));std=np.maximum(long.std(axis=(0,1)),.01)
            save(out/'preprocessing.json',{'long_mean':mean.tolist(),'long_std':std.tolist(),
                 'delta_mean':prep['delta_mean'],'delta_std':prep['delta_std'],
                 'short_scaler_sha256':file_hash(data.aligned/'scalers.json'),'fit_only':True,
                 'dataset_fingerprint':data.manifest['fingerprint']})
        coverage={'book_mean':float(long[:,:,20].mean()),'trade_mean':float(long[:,:,21].mean()),
                  'available_mean':float(long[:,:,23].mean()),'examples':len(idx)}
        save(out/f'{name}-coverage.json',coverage)
        full=np.column_stack([short,delta,((long-mean)/std).reshape(len(long),-1)]).astype(np.float32)
        np.save(out/f'{name}-features.npy',full)
        parts[name]=(full,y,idx,refs)
    del prefix
    runs=[];history=[]
    for mode in protocol['models']:
        for seed in protocol['seeds']:
            np.random.seed(seed);random.seed(seed);torch.manual_seed(seed)
            model=MultiModel(mode).to(device);opt=torch.optim.AdamW(model.parameters(),lr=protocol['lr'],weight_decay=protocol['weight_decay'])
            fx,fy,_,_=parts['fit'];vx,vy,_,_=parts['development'];best=float('inf');wait=0;selected=0;state=None
            for epoch in range(1,21):
                model.train();order=np.random.permutation(len(fx));total=0
                for start in range(0,len(order),128):
                    ids=order[start:start+128];x=torch.tensor(fx[ids],device=device);y=torch.tensor(fy[ids],device=device)
                    opt.zero_grad(set_to_none=True);z=model(x)
                    loss=F.cross_entropy(z[:,0],y[:,0])+.25*F.cross_entropy(z[:,1],y[:,1])
                    if not torch.isfinite(loss):raise ValueError('Nonfinite loss')
                    loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5);opt.step();total+=float(loss.detach().cpu())*len(ids)
                v=infer(model,vx,device);score=metrics(vy[:,0],probabilities(v[:,0]))['log_loss']
                item={'mode':mode,'seed':seed,'epoch':epoch,'development_log_loss':score,'training_joint_loss':total/len(fx)}
                history.append(item);print(json.dumps(item),flush=True);status('Training',**item)
                if score<best:
                    best=score;selected=epoch;wait=0;state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
                else:wait+=1
                if wait>=4:break
            torch.save({'mode':mode,'seed':seed,'epoch':selected,'state_dict':state},out/f'{mode}-{seed}.pt')
            runs.append({'mode':mode,'seed':seed,'epoch':selected,'development_log_loss':best,'parameters':sum(p.numel() for p in model.parameters())})
            del model,opt
            if device=='mps':torch.mps.empty_cache()
    means={mode:float(np.mean([r['development_log_loss'] for r in runs if r['mode']==mode])) for mode in protocol['models']}
    winner=min(means,key=means.get);save(out/'selection.json',{'mode':winner,'seed':17,'development_three_seed_means':means,'frozen_before_calibration':True})
    report={'model':'diwali0.3','selected_mode':winner,'runs':runs,'history':history,'protocol':protocol,
            'models':{},'recent_live_accuracy':None,'device':device}
    for mode in protocol['models']:
        status('Calibrating and comparing',mode=mode)
        saved=torch.load(out/f'{mode}-17.pt',weights_only=True,map_location='cpu');model=MultiModel(mode).to(device);model.load_state_dict(saved['state_dict'])
        cx,cy,_,_=parts['calibration'];cl=infer(model,cx,device)
        temps=[calibrate(cl[:,h],cy[:,h]) for h in range(2)]
        details={'temperatures':temps,'checkpoint_sha256':file_hash(out/f'{mode}-17.pt'),'partitions':{}}
        for name,(x,y,idx,refs) in parts.items():
            z=infer(model,x,device);p=probabilities(z[:,0],temps[0]);cp=probabilities(z[:,1],temps[1])
            prior=(np.bincount(parts['fit'][1][:,0],minlength=3)+1)/(len(parts['fit'][1])+3)
            old=np.load(parent/f'{name}-predictions.npz')['probabilities']
            days=np.array([time.strftime('%Y-%m-%d',time.gmtime(t/1000)) for t in idx[:,1]])
            details['partitions'][name]={'primary':metrics(y[:,0],p),'directional':directional(y[:,0],p),
                'candle_colour':metrics(y[:,1],cp),'diwali0.2':metrics(y[:,0],old),
                'fit_frequency':metrics(y[:,0],np.broadcast_to(prior,p.shape)),
                'by_day':{d:{'model':metrics(y[days==d,0],p[days==d]),'diwali0.2':metrics(y[days==d,0],old[days==d])} for d in sorted(set(days))}}
            np.savez(out/f'{mode}-{name}-predictions.npz',probabilities=p,colour_probabilities=cp,labels=y,indices=idx,reference=refs)
        report['models'][mode]=details
    report['wall_seconds']=time.time()-began
    # Paired daily losses; days are dependent/small, so descriptive, no significance claim.
    bench='locked_test';short=np.load(out/f'short_control-{bench}-predictions.npz');long=np.load(out/f'multiscale-{bench}-predictions.npz');y=short['labels'][:,0]
    difference=-np.log(long['probabilities'][np.arange(len(y)),y])+np.log(short['probabilities'][np.arange(len(y)),y])
    days=short['indices'][:,1]//86400000
    report['paired_long_minus_short_log_loss_by_day']={str(int(d)):float(difference[days==d].mean()) for d in np.unique(days)}
    save(out/'report.json',report);status('Complete',selected_mode=winner)
    print('COMPLETE',winner,means,flush=True)


if __name__=='__main__':main()
