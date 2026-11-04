"""Historical replay of exact close-state joint probabilities; never executes trades."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import time
import uuid

import numpy as np
import torch

from . import fan_serve as parent
from . import probability_serve as old
from .path import PathModel,forecast,path_events
from .fan import EDGES,direction
from .probability import probabilities,CLASSES
from ..market_data.validate_archive import file_hash


class Engine(parent.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());self.mode=self.full_report['selected_mode'];self.info=self.full_report['models'][self.mode]
        self.prep=json.loads((old.ROOT/'data/models/diwali0.5/preprocessing.json').read_text())
        self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.prep['dataset_fingerprint']!=self.data.manifest['fingerprint']:raise ValueError('Changed dataset')
        if file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed scaler')
        path=self.run/f'{self.mode}-17.pt'
        if file_hash(path)!=self.info['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        model=PathModel(self.mode);model.load_state_dict(torch.load(path,weights_only=True,map_location='cpu')['state_dict']);self.model=model.eval()
        z=np.load(self.run/f'{self.mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)]
        self.chains={};torch.set_num_threads(4)

    def predict(self,i):
        with self.lock:
            case=self.case(i);row=self.indices[i];start=time.perf_counter();ref=case['reference'];anchor=self.data.raw[int(row[2])-1,3]
            delta=((ref/anchor-1)*10000-self.prep['delta_mean'])/self.prep['delta_std'];x=np.concatenate([self.data.feature(row),[delta]])[None].astype(np.float32)
            a,t,m,c=forecast(self.model,x,self.info['temperatures'],'cpu');p=m[0];dp=direction(p);cp=probabilities(c[0],self.info['colour_temperature'])
            bounds=[None]+EDGES.tolist()+[None];fan=[]
            for h in range(15):
                ranges=[{'lower_bp':bounds[j],'upper_bp':bounds[j+1],
                    'lower_price':None if bounds[j] is None else ref*(1+bounds[j]/10000),
                    'upper_price':None if bounds[j+1] is None else ref*(1+bounds[j+1]/10000),'probability':float(v)} for j,v in enumerate(p[h])]
                fan.append({'horizon':h+1,'target_ms':case['target_ms']+h*60000,'close_ms':case['target_ms']+(h+1)*60000,'ranges':ranges,'probabilities':dict(zip(CLASSES,dp[h].tolist()))})
            token=uuid.uuid4().hex;self.requests[token]=(i,p);self.chains[token]=(a,t)
            if len(self.requests)>1000:
                key=next(iter(self.requests));self.requests.pop(key);self.chains.pop(key,None)
            return {'token':token,'fan':fan,'ranges':fan[0]['ranges'],'probabilities':fan[0]['probabilities'],
                'colour_probabilities':dict(zip(['red','flat','green'],cp.tolist())),'reference':ref,'lower_price':ref*.9998,'upper_price':ref*1.0002,'target_ms':case['target_ms'],
                'calculation_ms':(time.perf_counter()-start)*1000,'future_actuals_used':False,'model_calls':1,
                'scope':'joint26-bin first-order Markov distribution over15 closes; no intraminute path/touch or trade execution'}

    def query(self,token,lo,hi):
        with self.lock:
            if token not in self.chains:raise ValueError('Predict first')
            a,t=self.chains[token];s,v=path_events(a,t,lo,hi)
            return {'token':token,'lower_bin':lo,'upper_bin':hi,'all15_closes_inside':float(s[0]),'at_least_one_close_inside':float(v[0]),
                'future_actuals_used':False,'calculation':'exact forward summation of learned discrete Markov chain; no Monte Carlo','scope':'closing times only, not intraminute touch'}


def adapted(report,oldreport):
    r={'selected_mode':report['selected_mode'],'wall_seconds':report['wall_seconds'],'models':{}}
    for mode,info in report['models'].items():
        parts={}
        for name,part in info['partitions'].items():
            horizons={}
            for h,values in part['horizons'].items():
                base=oldreport['models'][oldreport['selected_mode']]['partitions'][name]['horizons'][h]
                horizons[h]={**values,'prior_range_baseline':base['prior_range_baseline'],'volatility_range_baseline':base['volatility_range_baseline']}
            parts[name]={**part,'horizons':horizons}
        r['models'][mode]={'partitions':parts}
    return r


def html(report,oldreport):
    r=adapted(report,oldreport);text=parent.html(r).replace('Diwali 0.5','Diwali 0.6')
    text=text.replace('All columns use the same frozen past inputs; they do not form a joint probability for an entire path.',
                      'All columns use the same frozen past inputs and are linked by a learned distribution over sequences of future close-price bands.')
    text=text.replace('These are marginal forecasts: an 80% band at each time does not mean an 80% chance of staying inside the whole fan.',
                      'Column probabilities alone do not give the chance of staying inside the whole fan. The joint-range query below calculates a15-close event explicitly.')
    info=report['models'][report['selected_mode']]['partitions']['locked_test']
    rows=[]
    for label,key in [('Diwali0.6 learned joint model','joint_log_loss'),('Diwali0.5 independent-column product','diwali0.5_independent_product_joint_log_loss'),('Transition-count baseline','count_markov_joint_log_loss'),('Volatility transition-count baseline','volatility_markov_joint_log_loss')]:
        rows.append(f"<tr><td>{label}</td><td>{info[key]:.5f}</td></tr>")
    section='<section><h2>Probability error for the whole sequence</h2><p>Joint log loss sums all15 conditional steps. Lower is better. This is different from the marginal range error below and is not a percent accuracy. Historical benchmark already inspected.</p><div style="overflow:auto"><table><thead><tr><th>Method</th><th>Whole-sequence error</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
    text=text.replace('<section><h2>Errors across all 15 future closes</h2>',section+'<section><h2>Errors across all 15 future closes</h2>')
    eventrows=[]
    for band,events in info['path_events'].items():
        for event,scores in events.items():
            m=scores['model'];b=scores['volatility_markov']
            eventrows.append(f"<tr><td>{band}, {'all 15 closes inside' if event=='stay' else 'at least one close inside'}</td><td>{100*m['mean_probability']:.2f}%</td><td>{100*m['observed_frequency']:.2f}%</td><td>{m['brier']:.5f}</td><td>{b['brier']:.5f}</td></tr>")
    table='<section><h2>Did range-event probabilities match outcomes?</h2><p>These are approximate symmetric price bands around the input reference, with the exact bin boundaries used by the range selector. Claims are averages over the inspected October examples. Lower Brier error is better. Overlapping examples are correlated; this is not fresh-market confirmation.</p><div style="overflow:auto"><table><thead><tr><th>Closing-time event</th><th>Mean claim</th><th>Observed frequency</th><th>Model error</th><th>Volatility-rule error</th></tr></thead><tbody>'+''.join(eventrows)+'</tbody></table></div></section>'
    text=text.replace('<section><h2>Were first-close confidence claims reliable?</h2>',table+'<section><h2>Were first-close confidence claims reliable?</h2>')
    text=text.replace('<p id="combined"></p>','<p id="combined"></p><h3>Joint15-close range query</h3><p>The same selected price bins apply to all15 closes, regardless of the closing time inspected above. This concerns candle closes only, not highs/lows or price touching the range during a minute.</p><p id="path-probabilities">Predict first.</p>')
    text=text.replace('clearRanges();clearFan();','clearRanges();clearFan();clearPath();')
    text=text.replace('combineRanges()}','combineRanges();queryPath()}')
    text=text.replace('markFanActuals(a)}','markFanActuals(a);queryPath()}')
    script='''<script>
let pathQueryVersion=0;
function clearPath(){++pathQueryVersion;document.getElementById('path-probabilities').textContent='Predict first.'}
async function queryPath(){if(!token||!priceRanges.length)return;const version=++pathQueryVersion,used=token,lo=Number(document.getElementById('lower-range').value),hi=Number(document.getElementById('upper-range').value);if(lo>hi){document.getElementById('path-probabilities').textContent='Choose a valid lower and upper range.';return}try{let r=await api('/api/path-range',{token:used,lower_bin:lo,upper_bin:hi});if(version!==pathQueryVersion||used!==token)return;let message='All15 closes inside: '+(100*r.all15_closes_inside).toFixed(2)+'%. At least one close inside: '+(100*r.at_least_one_close_inside).toFixed(2)+'%. Exact sum over the learned closing-price paths.';if(fanActuals){let inside=fanActuals.map(a=>a.range_index>=lo&&a.range_index<=hi);message+=' Revealed result: all inside '+(inside.every(Boolean)?'yes':'no')+'; at least one inside '+(inside.some(Boolean)?'yes':'no')+'.'}document.getElementById('path-probabilities').textContent=message}catch(e){fail(e)}}
for(let id of ['lower-range','upper-range'])document.getElementById(id).onchange=()=>{combineRanges();queryPath()};
</script>'''
    return (text+script).replace('Joint15-close','Joint range for 15 closes').replace('All15 closes','All 15 closes').replace('all15 closes','all 15 closes').replace('a15-close','a 15-close')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8746);parser.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.6');a=parser.parse_args();engine=Engine(a.run)
    def reports():return json.loads((a.run/'report.json').read_text()),json.loads((old.ROOT/'data/models/diwali0.5/report.json').read_text())
    class Handler(BaseHTTPRequestHandler):
        def respond(self,obj,status=200):
            b=json.dumps(obj,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            u=urlparse(self.path)
            try:
                if u.path=='/':
                    b=html(*reports()).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
                if u.path=='/api/report':
                    r,p=reports();v=parent.display_report(adapted(r,p),json.loads((old.ROOT/'data/models/diwali0.5/baseline-definitions.json').read_text()));v['architecture']='joint15-close Markov / '+r['selected_mode'];return self.respond(v)
                if u.path=='/api/full-report':return self.respond(reports()[0])
                if u.path=='/api/status':return self.respond(json.loads((a.run/'status.json').read_text()))
                if u.path=='/api/case':
                    with engine.lock:return self.respond(engine.case(int(parse_qs(u.query).get('id',['0'])[0])))
                self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def do_POST(self):
            try:
                n=int(self.headers.get('Content-Length',0))
                if not 0<n<4096:raise ValueError('Invalid request')
                body=json.loads(self.rfile.read(n))
                if self.path=='/api/predict':return self.respond(engine.predict(int(body['case_id'])))
                if self.path=='/api/path-range':return self.respond(engine.query(body['token'],int(body['lower_bin']),int(body['upper_bin'])))
                if self.path=='/api/reveal':
                    with engine.lock:return self.respond(engine.reveal(body['token']))
                self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def log_message(self,*args):pass
    print(f'Diwali0.6 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
