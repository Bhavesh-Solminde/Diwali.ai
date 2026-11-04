"""Checkpoint-backed one-endpoint price-range probabilities, no fake path cloud."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import time
import uuid

import numpy as np
import torch

from . import probability_serve as old
from .distribution import DistributionModel,EDGES,direction,range_labels
from .probability import probabilities,CLASSES
from ..market_data.validate_archive import file_hash


class Engine(old.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());mode=self.full_report['selected_mode']
        info=self.full_report['models'][mode];self.report={'temperatures':info['temperatures']}
        self.prep=json.loads((self.run/'preprocessing.json').read_text())
        self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.prep['dataset_fingerprint']!=self.data.manifest['fingerprint']:raise ValueError('Changed dataset')
        if file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed scalers')
        checkpoint=self.run/f'{mode}-17.pt'
        if file_hash(checkpoint)!=info['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        state=torch.load(checkpoint,weights_only=True,map_location='cpu')
        z=np.load(self.run/f'{mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)]
        self.model=DistributionModel();self.model.load_state_dict(state['state_dict']);self.model.eval();torch.set_num_threads(4)

    def predict(self,i):
        with self.lock:
            case=self.case(i);row=self.indices[i];start=time.perf_counter();ref=case['reference'];anchor=self.data.raw[int(row[2])-1,3]
            delta=((ref/anchor-1)*10000-self.prep['delta_mean'])/self.prep['delta_std']
            x=np.concatenate([self.data.feature(row),[delta]])[None].astype(np.float32)
            with torch.inference_mode():z=self.model(torch.from_numpy(x)).numpy()[0]
            p=probabilities(z[:18],self.report['temperatures'][0]);dp=direction(p);cp=probabilities(z[18:],self.report['temperatures'][1])
            token=uuid.uuid4().hex;self.requests[token]=(i,dp.tolist())
            if len(self.requests)>1000:self.requests.pop(next(iter(self.requests)))
            edges=[None]+EDGES.tolist()+[None]
            ranges=[{'lower_bp':edges[j],'upper_bp':edges[j+1],
                     'lower_price':None if edges[j] is None else ref*(1+edges[j]/10000),
                     'upper_price':None if edges[j+1] is None else ref*(1+edges[j+1]/10000),
                     'probability':float(v)} for j,v in enumerate(p)]
            return {'token':token,'probabilities':dict(zip(CLASSES,dp.tolist())),
                    'colour_probabilities':dict(zip(['red','flat','green'],cp.tolist())),
                    'reference':ref,'lower_price':ref*.9998,'upper_price':ref*1.0002,
                    'ranges':ranges,'target_ms':case['target_ms'],'calculation_ms':(time.perf_counter()-start)*1000,
                    'scope':'one closing-price endpoint only; not future path or touch probability'}

    def reveal(self,token):
        result=super().reveal(token)
        result['range_index']=int(range_labels([result['move_bp']])[0])
        return result


def display_report(report,baseline):
    info=report['models'][report['selected_mode']];prior=direction(np.asarray(baseline['empirical_bin_probabilities']))
    parts={}
    for name,value in info['partitions'].items():
        count=np.asarray(value['primary']['class_counts'])
        parts[name]={'primary':value['primary'],'fit_frequency_baseline':{'log_loss':float(-(count*np.log(prior)).sum()/count.sum())}}
    return {'architecture':'18 price ranges / '+report['selected_mode'],'wall_seconds':report['wall_seconds'],'partitions':parts}


def html(report):
    info=report['models'][report['selected_mode']]['partitions']['locked_test']
    text=old.HTML.replace('Diwali 0.2','Diwali 0.4').replace('DIWALI RESEARCH','Diwali 0.4 research')
    text=text.replace('<h1>Next-candle probabilities</h1>', '<h1>Where could the next candle close?</h1><p>18 learned price ranges describe the target closing price. Direction probabilities below are sums of those same ranges. Each forecast concerns one future closing time; no intervening path is implied.</p>')
    text=text.replace('Three class probabilities cannot define a continuous price cloud or the order in which prices are touched.', 'The separate range forecast below concerns the final close. It does not predict the order in which prices are touched.')
    text=text.replace('w=c.width=1000,h=c.height=300','w=c.width=Math.max(320,Math.round(c.getBoundingClientRect().width)),h=c.height=300')
    text=text.replace('Past candles → next full-minute target after reveal','Past candles / revealed next candle')
    text=text.replace('pos=15+i*15;', 'pos=15+i*(w-30)/Math.max(candles.length-1,1);')
    text=text.replace('ctx.fillRect(pos-4,Math.min(y(o),y(cl)),8,', 'ctx.fillRect(pos-Math.max(2,(w-30)/candles.length*.65)/2,Math.min(y(o),y(cl)),Math.max(2,(w-30)/candles.length*.65),')
    text=text.replace('<strong>In this completed run, every call above 60% confidence was neutral. The 80% group below is confidence in little movement, not bullish or bearish direction.</strong>', '<strong>These confidence groups include neutral outcomes. They are not automatically bullish/bearish trading opportunities.</strong>')
    rows=[]
    for label,part in [('Learned price ranges',info['ranges']),('Past-frequency baseline',info['empirical_range_baseline']),('Past-volatility baseline',info['volatility_range_baseline'])]:
        rows.append(f"<tr><td>{label}</td><td>{part['bin_log_loss']:.5f}</td><td>{part['ranked_probability_score_mean_17_thresholds']:.5f}</td></tr>")
    comparison='<section><h2>Price-range probability errors</h2><p>Lower is better for both scores. These scores assess all 18 ranges; they are different from three-outcome accuracy.</p><table><thead><tr><th>Method</th><th>18-range log loss ↓</th><th>Ordered probability error ↓</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section>'
    text=text.replace('<section><h2>Training result</h2>',comparison+'<section><h2>Direction from those ranges</h2>')
    section='''<section><h2>Closing-price range forecast</h2><p id="range-note">Click Predict to see the learned probabilities. Probabilities across all ranges sum to 100%.</p><div style="overflow:auto"><table><thead><tr><th>Close in this price range</th><th>Probability</th><th>Probability mass</th></tr></thead><tbody id="ranges"></tbody></table></div><p>Each bar represents probability of one price bin, not probability per dollar. The first and last ranges are open-ended. Interior upper bounds are included except the +2 basis-point boundary, which is bullish.</p><label>Combine contiguous price bins: from <select id="lower-range" aria-label="First price range"></select> through <select id="upper-range" aria-label="Last price range"></select></label><p id="combined"></p><small>These are probabilities for the candle’s final close, not whether price touches the range at any earlier time. No density within a bin is assumed.</small></section>'''
    text=text.replace('<section><h2>Were high-confidence calls reliable?</h2>',section+'<section><h2>Were high-confidence calls reliable?</h2>')
    text=text.replace("$('reveal').disabled=false;$('actual').textContent='';draw()", "renderRanges(p);$('reveal').disabled=false;$('actual').textContent='';draw()")
    text=text.replace("$('bars').replaceChildren();$('detail').textContent=''", "$('bars').replaceChildren();clearRanges();$('detail').textContent=''")
    text=text.replace('draw(a)}catch(e){fail(e)}};', 'draw(a);markActualRange(a)}catch(e){fail(e)}};')
    script='''<script>
let priceRanges=[];
function markActualRange(actual){let rows=document.querySelectorAll('#ranges tr');rows.forEach((row,i)=>{row.style.background=i===actual.range_index?'#eee5f8':''});if(priceRanges.length)document.getElementById('range-note').textContent+=' Revealed close landed in the highlighted range, assigned '+(100*priceRanges[actual.range_index].probability).toFixed(2)+'% probability before reveal.'}
function clearRanges(){priceRanges=[];document.getElementById('ranges').replaceChildren();document.getElementById('lower-range').replaceChildren();document.getElementById('upper-range').replaceChildren();document.getElementById('combined').textContent='';document.getElementById('range-note').textContent='Click Predict to load price-range probabilities.'}
function renderRanges(result){clearRanges();priceRanges=result.ranges;document.getElementById('range-note').textContent='Distribution for the close at '+new Date(result.target_ms+60000).toISOString().replace('T',' ').slice(0,19)+' UTC. Input reference $'+result.reference.toFixed(2)+'.';let largest=Math.max(...priceRanges.map(r=>r.probability));priceRanges.forEach((r,i)=>{let label=r.lower_price===null?'Up to $'+r.upper_price.toFixed(2):r.upper_price===null?'Above $'+r.lower_price.toFixed(2):'$'+r.lower_price.toFixed(2)+' to $'+r.upper_price.toFixed(2);let tr=document.createElement('tr'),td=document.createElement('td'),prob=document.createElement('td'),bar=document.createElement('td'),fill=document.createElement('div');td.textContent=label;prob.textContent=(100*r.probability).toFixed(2)+'%';fill.style.width=(100*r.probability/largest)+'%';fill.style.height='15px';fill.style.background='#7953ac';bar.style.minWidth='80px';bar.append(fill);tr.append(td,prob,bar);document.getElementById('ranges').append(tr);for(let id of ['lower-range','upper-range']){let option=document.createElement('option');option.value=i;option.textContent=label;document.getElementById(id).append(option)}});document.getElementById('lower-range').value=6;document.getElementById('upper-range').value=11;combineRanges()}
function combineRanges(){if(!priceRanges.length)return;let lo=Number(document.getElementById('lower-range').value),hi=Number(document.getElementById('upper-range').value);if(lo>hi){document.getElementById('combined').textContent='Choose the lower range first.';return}let mass=priceRanges.slice(lo,hi+1).reduce((sum,r)=>sum+r.probability,0);document.getElementById('combined').textContent='Combined probability: '+(100*mass).toFixed(2)+'%'}
document.getElementById('lower-range').onchange=combineRanges;document.getElementById('upper-range').onchange=combineRanges;
</script>'''
    return text+script


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8744);parser.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.4');a=parser.parse_args();engine=Engine(a.run)
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
    print(f'Diwali0.4 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
