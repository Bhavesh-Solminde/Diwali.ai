"""Discrete probability fan: 15 marginal close distributions, separate actual reveal."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import time
import uuid

import numpy as np
import torch

from . import probability_serve as old
from . import distribution_serve as endpoint
from .fan import FanModel,EDGES,direction,range_labels
from .probability import probabilities,CLASSES,labels
from ..market_data.build_pilot import WARMUP
from ..market_data.validate_archive import file_hash


class Engine(old.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());self.mode=self.full_report['selected_mode']
        self.info=self.full_report['models'][self.mode];self.prep=json.loads((self.run/'preprocessing.json').read_text())
        self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.prep['dataset_fingerprint']!=self.data.manifest['fingerprint']:raise ValueError('Changed dataset')
        if file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed scalers')
        path=self.run/f'{self.mode}-17.pt'
        if file_hash(path)!=self.info['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        saved=torch.load(path,weights_only=True,map_location='cpu');self.model=FanModel();self.model.load_state_dict(saved['state_dict']);self.model.eval()
        z=np.load(self.run/f'{self.mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)]
        torch.set_num_threads(4)

    def predict(self,i):
        with self.lock:
            case=self.case(i);row=self.indices[i];start=time.perf_counter();ref=case['reference'];anchor=self.data.raw[int(row[2])-1,3]
            delta=((ref/anchor-1)*10000-self.prep['delta_mean'])/self.prep['delta_std'];x=np.concatenate([self.data.feature(row),[delta]])[None].astype(np.float32)
            with torch.inference_mode():z,c=self.model(torch.from_numpy(x));z=z.numpy()[0];c=c.numpy()[0]
            p=np.array([probabilities(z[h],self.info['temperatures'][h]) for h in range(15)]);dp=direction(p);cp=probabilities(c,self.info['colour_temperature'])
            bounds=[None]+EDGES.tolist()+[None];fan=[]
            for h in range(15):
                ranges=[{'lower_bp':bounds[j],'upper_bp':bounds[j+1],
                    'lower_price':None if bounds[j] is None else ref*(1+bounds[j]/10000),
                    'upper_price':None if bounds[j+1] is None else ref*(1+bounds[j+1]/10000),
                    'probability':float(v)} for j,v in enumerate(p[h])]
                fan.append({'horizon':h+1,'target_ms':case['target_ms']+h*60000,'close_ms':case['target_ms']+(h+1)*60000,
                            'ranges':ranges,'probabilities':dict(zip(CLASSES,dp[h].tolist()))})
            token=uuid.uuid4().hex;self.requests[token]=(i,p)
            if len(self.requests)>1000:self.requests.pop(next(iter(self.requests)))
            return {'token':token,'fan':fan,'ranges':fan[0]['ranges'],'probabilities':fan[0]['probabilities'],
                    'colour_probabilities':dict(zip(['red','flat','green'],cp.tolist())),
                    'reference':ref,'lower_price':ref*.9998,'upper_price':ref*1.0002,'target_ms':case['target_ms'],
                    'calculation_ms':(time.perf_counter()-start)*1000,'future_actuals_used':False,'model_calls':1,
                    'scope':'15 separate marginal closing-time distributions, not a joint path distribution'}

    def reveal(self,token):
        if token not in self.requests:raise ValueError('Predict first')
        i,p=self.requests[token];case=self.case(i);actuals=[]
        for h in range(15):
            minute=case['target_ms']+h*60000;actual=self.data.raw[(minute-WARMUP)//60000,:4].copy();move=(actual[3]/case['reference']-1)*10000;b=int(range_labels(move));y=int(labels(actual[3],case['reference']))
            actuals.append({'horizon':h+1,'time':minute,'ohlc':actual.tolist(),'range_index':b,'move_bp':float(move),
                            'outcome':CLASSES[y],'assigned_probability':float(p[h,b])})
        return {**actuals[0],'actuals':actuals}


def adapted(report):
    models={}
    for mode,info in report['models'].items():
        parts={}
        for name,v in info['partitions'].items():
            h=v['horizons']['1'];parts[name]={'primary':h['primary']}
            for key,source in [('ranges','ranges'),('empirical_range_baseline','prior_range_baseline'),('volatility_range_baseline','volatility_range_baseline')]:
                d=dict(h[source]);d['ranked_probability_score_mean_17_thresholds']=d['ranked_probability_score_mean_25_thresholds'];parts[name][key]=d
        models[mode]={'partitions':parts}
    return {'selected_mode':report['selected_mode'],'models':models,'wall_seconds':report['wall_seconds']}


def display_report(report,baseline):
    r=adapted(report);prior=direction(np.asarray(baseline['prior'])[0]);parts={}
    for name,v in r['models'][r['selected_mode']]['partitions'].items():
        counts=np.asarray(v['primary']['class_counts']);parts[name]={'primary':v['primary'],'fit_frequency_baseline':{'log_loss':float(-(counts*np.log(prior)).sum()/counts.sum())}}
    return {'architecture':'15 direct closing-time distributions / '+report['selected_mode'],'wall_seconds':report['wall_seconds'],'partitions':parts}


def html(report):
    text=endpoint.html(adapted(report)).replace('Diwali 0.4','Diwali 0.5')
    text=text.replace('Where could the next candle close?','A probability fan across 15 candle closes')
    text=text.replace('18 learned price ranges describe the target closing price. Direction probabilities below are sums of those same ranges. Each forecast concerns one future closing time; no intervening path is implied.', '26 price ranges at each of 15 future closing times. The first-candle bars below come from column one. All columns use the same frozen past inputs; they do not form a joint probability for an entire path.')
    for a,b in [('all 18 ranges','all 26 ranges'),('18-range log loss','26-range log loss'),('18 price ranges','26 price ranges'),('18 ranges','26 ranges')]:text=text.replace(a,b)
    text=text.replace('<h2>Price-range probability errors</h2>','<h2>First-close price-range errors</h2>')
    text=text.replace('<h2>Direction from those ranges</h2>','<h2>First-close direction results</h2>')
    text=text.replace('<h2>Were high-confidence calls reliable?</h2>','<h2>Were first-close confidence claims reliable?</h2>')
    info=report['models'][report['selected_mode']]['partitions']['locked_test']
    rows=[]
    for h in range(1,16):
        scores=info['horizons'][str(h)]
        rows.append(f"<tr><td>{h}</td><td>{scores['ranges']['bin_log_loss']:.5f}</td><td>{scores['prior_range_baseline']['bin_log_loss']:.5f}</td><td>{scores['volatility_range_baseline']['bin_log_loss']:.5f}</td></tr>")
    summary='<section><h2>Errors across all 15 future closes</h2><p>Already-inspected October benchmark, same '+str(info['horizons']['1']['ranges']['examples'])+' origins at every horizon. Lower log loss is better; this is not a percentage accuracy.</p><div style="overflow:auto"><table><thead><tr><th>Future candle close</th><th>Model error</th><th>Past frequency</th><th>Past volatility</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
    text=text.replace('<section><h2>First-close price-range errors</h2>',summary+'<section><h2>First-close price-range errors</h2>')
    text=text.replace('Candle colour probabilities:', 'First-candle colour probabilities:')
    section='''<section><h2>Future closing-time probability grid</h2><p id="fan-note">Click Predict to forecast the 15 closes.</p><div style="overflow-x:auto"><div id="fan-grid" style="display:grid;grid-template-columns:135px repeat(15,48px);gap:2px;min-width:885px;font-size:12px"></div></div><p>Each column sums to 100%. Darker purple means more probability in that price bin. Rows are unequal-width price bands shown at equal heights; this is a probability table, not a linear-price chart. Open-ended tails are labelled. Forecasts between these closing times are not defined.</p><label>Inspect closing time <select id="horizon" aria-label="Forecast horizon"></select></label><p id="horizon-direction"></p><small>Click a cell to inspect its closing time. Dark dots appear only after Reveal and mark actual closes. These are marginal forecasts: an 80% band at each time does not mean an 80% chance of staying inside the whole fan.</small></section>'''
    text=text.replace('<section><h2>Closing-price range forecast</h2>',section+'<section><h2>Selected closing-time ranges</h2>')
    text=text.replace('renderRanges(p);', 'renderFan(p);')
    text=text.replace("$('bars').replaceChildren();clearRanges();", "$('bars').replaceChildren();clearRanges();clearFan();")
    text=text.replace('draw(a);markActualRange(a)', 'draw(a);markFanActuals(a)')
    text=text.replace("document.getElementById('lower-range').value=6;document.getElementById('upper-range').value=11", "document.getElementById('lower-range').value=10;document.getElementById('upper-range').value=15")
    script='''<script>
let fanPrediction=null,fanActuals=null;
function clearFan(){fanPrediction=null;fanActuals=null;document.getElementById('fan-grid').replaceChildren();document.getElementById('horizon').replaceChildren();document.getElementById('horizon-direction').textContent='';document.getElementById('fan-note').textContent='Click Predict to forecast the 15 closes.'}
function selectedHorizon(){if(!fanPrediction)return;let h=Number(document.getElementById('horizon').value),item=fanPrediction.fan[h];renderRanges({...fanPrediction,...item});document.getElementById('horizon-direction').textContent='This close: bearish '+(100*item.probabilities.bearish).toFixed(1)+'%, neutral '+(100*item.probabilities.neutral).toFixed(1)+'%, bullish '+(100*item.probabilities.bullish).toFixed(1)+'%.';if(fanActuals)markActualRange(fanActuals[h])}
function renderFan(result){clearFan();fanPrediction=result;const grid=document.getElementById('fan-grid');let label=document.createElement('div');label.textContent='Close price bin / UTC';grid.append(label);result.fan.forEach((item,h)=>{let div=document.createElement('div');div.textContent=new Date(item.close_ms).toISOString().slice(11,16);div.style.textAlign='center';grid.append(div);let option=document.createElement('option');option.value=h;option.textContent='Candle '+(h+1)+' · '+new Date(item.close_ms).toISOString().slice(11,19)+' UTC';document.getElementById('horizon').append(option)});for(let bin=25;bin>=0;bin--){let r=result.fan[0].ranges[bin],label=document.createElement('div');let bounds=r.lower_price===null?'≤ $'+r.upper_price.toFixed(2):r.upper_price===null?'> $'+r.lower_price.toFixed(2):'$'+r.lower_price.toFixed(2)+'–'+r.upper_price.toFixed(2);label.textContent=bounds;label.title=bounds;grid.append(label);result.fan.forEach((item,h)=>{let cell=document.createElement('button'),p=item.ranges[bin].probability;cell.type='button';cell.style.cssText='padding:0;border:0;border-radius:1px;height:22px;color:#1b1030;background:rgba(121,83,172,'+Math.min(1,p*5)+')';cell.title='Candle '+(h+1)+', '+bounds+': '+(100*p).toFixed(2)+'%';cell.setAttribute('aria-label',cell.title);cell.dataset.horizon=h;cell.dataset.bin=bin;cell.onclick=()=>{document.getElementById('horizon').value=h;selectedHorizon()};grid.append(cell)})}document.getElementById('fan-note').textContent='Forecast issued from input snapshot '+new Date(current.snapshot_ms).toISOString().replace('T',' ').slice(0,19)+' UTC. Purple cells show learned probabilities for the 15 future closes.';selectedHorizon()}
function markFanActuals(actual){fanActuals=actual.actuals;document.querySelectorAll('#fan-grid button').forEach(cell=>{let h=Number(cell.dataset.horizon),bin=Number(cell.dataset.bin);if(fanActuals[h].range_index===bin){cell.textContent='●';cell.style.outline='1px solid #fff';cell.title+=' · actual close $'+fanActuals[h].ohlc[3].toFixed(2)}});selectedHorizon()}
document.getElementById('horizon').onchange=selectedHorizon;
</script>'''
    return text+script


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8745);parser.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.5');a=parser.parse_args();engine=Engine(a.run)
    class Handler(BaseHTTPRequestHandler):
        def respond(self,obj,status=200):
            b=json.dumps(obj,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            u=urlparse(self.path)
            try:
                if u.path=='/':
                    b=html(json.loads((engine.run/'report.json').read_text())).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
                if u.path=='/api/report':return self.respond(display_report(json.loads((engine.run/'report.json').read_text()),json.loads((engine.run/'baseline-definitions.json').read_text())))
                if u.path=='/api/full-report':return self.respond(json.loads((engine.run/'report.json').read_text()))
                if u.path=='/api/status':return self.respond(json.loads((engine.run/'status.json').read_text()))
                if u.path=='/api/case':
                    with engine.lock:return self.respond(engine.case(int(parse_qs(u.query).get('id',['0'])[0])))
                return self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def do_POST(self):
            try:
                n=int(self.headers.get('Content-Length',0))
                if not 0<n<4096:raise ValueError('Invalid request')
                body=json.loads(self.rfile.read(n))
                if self.path=='/api/predict':return self.respond(engine.predict(int(body['case_id'])))
                if self.path=='/api/reveal':
                    with engine.lock:return self.respond(engine.reveal(body['token']))
                return self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def log_message(self,*args):pass
    print(f'Diwali0.5 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
