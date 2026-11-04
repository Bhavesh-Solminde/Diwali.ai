"""Shared exact marginal/joint evaluation of already selected close-state models."""
import time
from pathlib import Path

import numpy as np

from .path import forecast,chain_losses,path_events,event_metrics,BANDS
from .fan import direction,range_metrics
from .probability import probabilities,metrics
from .multiscale import directional
from ..market_data.validate_archive import save


def evaluate(model,info,parts,out,variant,parent05,parent06,status):
    base=__import__('json').loads((parent06/'baselines.json').read_text());initial=np.asarray(base['initial']);transitions=np.asarray(base['transitions']);cuts=np.asarray(base['cuts'])
    conditional=[(np.asarray(v['initial']),np.asarray(v['transitions'])) for v in base['conditional']]
    oldreport=__import__('json').loads((parent05/'report.json').read_text());mode05=oldreport['selected_mode'];partscores={}
    for name,part in parts.items():
        status('Exact marginal and joint evaluation',variant=variant,partition=name)
        x,y=part['x'],part['y'];preds=[];losses=[];base_losses=[];vol_losses=[];colours=[]
        events={k:{'stay':[],'visit':[]} for k in BANDS};baseevents={k:{'stay':[],'visit':[]} for k in BANDS};groups=np.searchsorted(cuts,part['volatility'],side='right')
        for start in range(0,len(x),64):
            sl=slice(start,start+64);a,t,p,c=forecast(model,x[sl],info['temperatures'],info['device']);preds.append(p.astype(np.float32));colours.append(probabilities(c,info['colour_temperature']));losses.append(chain_losses(a,t,y[sl]))
            bi=np.broadcast_to(initial,a.shape);bt=np.broadcast_to(transitions,t.shape);base_losses.append(chain_losses(bi,bt,y[sl]))
            ci=np.asarray([conditional[g][0] for g in groups[sl]]);tr=np.asarray([conditional[g][1] for g in groups[sl]]);vol_losses.append(chain_losses(ci,tr,y[sl]))
            for key,(lo,hi) in BANDS.items():
                for target,aa,tt in [(events,a,t),(baseevents,ci,tr)]:
                    s,v=path_events(aa,tt,lo,hi);target[key]['stay'].extend(s);target[key]['visit'].extend(v)
        p=np.concatenate(preds);joint=np.concatenate(losses);baseline=np.concatenate(base_losses);vol=np.concatenate(vol_losses);colour=np.concatenate(colours);dp=direction(p)
        old=np.load(parent05/f'{mode05}-{name}-predictions.npz');previous=np.load(parent06/f'markov-{name}-predictions.npz')
        np.testing.assert_array_equal(part['indices'],old['indices']);np.testing.assert_array_equal(part['indices'],previous['indices'])
        indloss=-np.log(np.maximum(np.take_along_axis(old['bin_probabilities'],y[:,:,None],2),1e-15)).sum(1)
        byh={str(h+1):{'ranges':range_metrics(y[:,h],p[:,h]),'primary':metrics(np.where(y[:,h]<10,0,np.where(y[:,h]>=16,2,1)),dp[:,h]),'directional':directional(np.where(y[:,h]<10,0,np.where(y[:,h]>=16,2,1)),dp[:,h])} for h in range(15)}
        er={}
        for key,(lo,hi) in BANDS.items():
            inside=(y>=lo)&(y<=hi);er[key]={kind:{'model':event_metrics(truth,events[key][kind]),'volatility_markov':event_metrics(truth,baseevents[key][kind])} for kind,truth in [('stay',inside.all(1)),('visit',inside.any(1))]}
        days=np.array([time.strftime('%Y-%m-%d',time.gmtime(v/1000)) for v in part['indices'][:,1]])
        marginal=float(np.mean([h['ranges']['bin_log_loss'] for h in byh.values()]));score={'examples':len(y),'joint_log_loss':float(joint.mean()),'joint_log_loss_per_step':float(joint.mean()/15),
            'mean15_marginal_bin_log_loss':marginal,'joint_plus_marginal_per_step':float(joint.mean()/15+marginal),
            'diwali0.5_independent_product_joint_log_loss':float(indloss.mean()),'count_markov_joint_log_loss':float(baseline.mean()),'volatility_markov_joint_log_loss':float(vol.mean()),
            'diwali0.6_joint_log_loss':float(previous['joint_losses'].mean()),'diwali0.6_mean15_marginal_bin_log_loss':float(-np.log(np.maximum(np.take_along_axis(previous['bin_probabilities'],y[:,:,None],2),1e-15)).mean()),
            'horizons':byh,'path_events':er,'h1_colour':metrics(part['colour'],colour),
            'by_day':{d:{'n':int((days==d).sum()),'joint_log_loss':float(joint[days==d].mean()),'diwali0.6_joint_log_loss':float(previous['joint_losses'][days==d].mean()),'volatility_markov_joint_log_loss':float(vol[days==d].mean())} for d in sorted(set(days))}}
        partscores[name]=score
        np.savez(out/f'{variant}-{name}-predictions.npz',bin_probabilities=p,probabilities=dp,joint_losses=joint,baseline_losses=baseline,volatility_losses=vol,diwali05_joint_losses=indloss,diwali06_joint_losses=previous['joint_losses'],indices=part['indices'],reference=part['reference'],bin_labels=y,colour_probabilities=colour,
                 **{f'{key}_{kind}':np.asarray(v[kind]) for key,v in events.items() for kind in ['stay','visit']})
    return partscores
