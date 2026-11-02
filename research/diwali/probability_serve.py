"""Local diwali0.2 probability report and checkpoint-backed historical replay."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

import numpy as np
import torch

from .train import Data
from .probability import ProbabilityModel, observed_reference, summarize, probabilities, labels, CLASSES
from ..market_data.build_pilot import WARMUP
from ..market_data.validate_archive import file_hash

ROOT = Path(__file__).resolve().parents[2]


class Engine:
    def __init__(self, run):
        self.run = run; self.model = None; self.lock = threading.Lock(); self.requests = {}

    def ready(self):
        if self.model is not None:return
        self.report = json.loads((self.run/'report.json').read_text())
        self.prep = json.loads((self.run/'preprocessing.json').read_text())
        arch = self.report['architecture']
        checkpoint = self.run/f'{arch}-17.pt'
        if file_hash(checkpoint) != self.report['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        state = torch.load(checkpoint, map_location='cpu', weights_only=True)
        self.data = Data(ROOT/'data/btc-perp/aligned-button-pilot-202610-v1', self.run/'replay-cache')
        if self.data.manifest['fingerprint'] != self.prep['dataset_fingerprint']:raise ValueError('Changed dataset')
        if file_hash(self.data.aligned/'scalers.json') != self.prep['aligned_scaler_sha256']:raise ValueError('Changed scaler')
        # The replay cases use only pre-existing input origins; no outcomes read here.
        idx = np.load(self.data.root/'locked_test-phase15-grace1000-indices.npy')
        eligible = []
        for row in idx:
            try:ref, age = observed_reference(self.data.trades, row)
            except ValueError:continue
            if age <= 2:eligible.append(row)
        eligible = np.asarray(eligible)
        self.indices = eligible[np.linspace(0,len(eligible)-1,10,dtype=int)]
        self.model = ProbabilityModel(arch, state['input_width'])
        self.model.load_state_dict(state['state_dict']); self.model.eval()
        torch.set_num_threads(4)

    def case(self, i):
        self.ready()
        if not 0 <= i < 10:raise ValueError('Invalid case')
        row = self.indices[i]; ci = int(row[2])
        ref, age = observed_reference(self.data.trades, row)
        return {'id':i, 'snapshot_ms':int(row[0]), 'target_ms':int(row[1]),
                'reference':ref, 'reference_age_seconds':age,
                'past':[{'time':int(WARMUP+(ci-60+k)*60000), 'ohlc':self.data.raw[ci-60+k,:4].tolist()} for k in range(60)]}

    def predict(self, i):
        with self.lock:
            case = self.case(i); row = self.indices[i]; started = time.perf_counter()
            ref = case['reference']; old = self.data.raw[int(row[2])-1,3]
            delta = ((ref/old-1)*10000-self.prep['delta_mean'])/self.prep['delta_std']
            x = np.concatenate([self.data.feature(row),[delta]])[None].astype(np.float32)
            if self.report['architecture'] == 'logistic':
                x = ((summarize(x)-self.prep['summary_mean'])/self.prep['summary_std']).astype(np.float32)
            with torch.inference_mode():logits = self.model(torch.from_numpy(x)).numpy()[0]
            p = [probabilities(logits[h],self.report['temperatures'][h]).tolist() for h in range(2)]
            token = uuid.uuid4().hex; self.requests[token] = (i,p[0])
            if len(self.requests)>1000:self.requests.pop(next(iter(self.requests)))
            return {'token':token, 'probabilities':dict(zip(CLASSES,p[0])),
                    'colour_probabilities':dict(zip(['red','flat','green'],p[1])),
                    'reference':ref, 'lower_price':ref*.9998, 'upper_price':ref*1.0002,
                    'calculation_ms':(time.perf_counter()-started)*1000}

    def reveal(self, token):
        if token not in self.requests:raise ValueError('Predict first')
        i,p = self.requests[token]; case = self.case(i)
        actual = self.data.raw[(case['target_ms']-WARMUP)//60000,:4].copy()
        y = int(labels(actual[3],case['reference']))
        return {'time':case['target_ms'], 'ohlc':actual.tolist(), 'outcome':CLASSES[y],
                'move_bp':float((actual[3]/case['reference']-1)*10000),
                'log_loss':float(-np.log(max(p[y],1e-15)))}


HTML = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Diwali 0.2 · Candle probabilities</title><style>
body{margin:0;background:#f3f6f8;color:#192c3b;font:16px system-ui}main{max-width:1060px;margin:auto;padding:30px 20px}h1{font-size:32px;margin-bottom:5px}p{line-height:1.6}section{background:white;border:1px solid #dbe4eb;border-radius:15px;padding:22px;margin:20px 0}button,select{font:inherit;padding:12px;border-radius:8px;border:1px solid #b9c8d5}button{background:#2449bd;color:white;cursor:pointer}button:disabled{opacity:.4}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:11px;border-bottom:1px solid #e4eaef}small{color:#536776}.bars{display:grid;gap:14px}.track{background:#eaf0f5;border-radius:6px;overflow:hidden;height:24px}.fill{height:100%}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}canvas{width:100%;height:300px}#error{color:#a52f3f}a{color:#2449bd}@media(max-width:600px){.cards{grid-template-columns:1fr}section{padding:15px}main{padding:15px}table{font-size:13px}td,th{padding:6px}}
</style><main><small>DIWALI RESEARCH / BTCUSDT PERPETUAL / ONE MINUTE</small><h1>Next-candle probabilities</h1><p>Historical replay using trained weights. The price reference is the last received second’s average trade price. The target is the next full calendar minute.</p>
<p><a href="http://127.0.0.1:8741/">Open the earlier candle-generation experiment</a></p><p id="error" role="alert"></p>
<section><h2>Training result</h2><p id="status">Loading…</p><div style="overflow:auto"><table><thead><tr><th>Period</th><th>Accuracy</th><th>Probability error¹</th><th>Simple baseline¹</th></tr></thead><tbody id="scores"></tbody></table></div><small>¹ Log loss: lower is better. Accuracy covers bearish / neutral / bullish, including neutral predictions. October 24–31 is an already-inspected comparison benchmark. Live accuracy has not been measured.</small></section>
<section><h2>Try a historical example</h2><select id="case" aria-label="Historical example"></select> <button id="predict">Predict probabilities</button> <button id="reveal" disabled>Reveal outcome</button><p id="times"></p><div id="bars" class="bars"></div><p id="detail"></p><canvas id="chart" aria-label="Past candles and separately revealed actual target"></canvas><p id="actual"></p><small>The chart shows observed past candles. The actual next candle appears only after Reveal. Three class probabilities cannot define a continuous price cloud or the order in which prices are touched.</small></section>
<section><h2>Were high-confidence calls reliable?</h2><p>For calls around 80% confidence, the observed success frequency should be close to 80%. Empty groups mean the model did not make those calls.</p><p><strong>In this completed run, every call above 60% confidence was neutral. The 80% group below is confidence in little movement, not bullish or bearish direction.</strong></p><table><thead><tr><th>Claimed confidence</th><th>Examples</th><th>Average claim</th><th>Actual correct</th></tr></thead><tbody id="reliability"></tbody></table><p>High direction probability alone does not establish a good trade: movement size, fees and stop/target ordering still matter.</p></section></main>
<script>
let current,token,report;const $=id=>document.getElementById(id),pct=x=>(x*100).toFixed(1)+'%',date=t=>new Date(t).toISOString().replace('T',' ').slice(0,19)+' UTC';
async function api(path,body){const r=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});const x=await r.json();if(!r.ok)throw Error(x.error);return x}
function draw(real){let c=$('chart'),ctx=c.getContext('2d'),w=c.width=1000,h=c.height=300;ctx.clearRect(0,0,w,h);let candles=[...current.past,...(real?[real]:[])],low=Math.min(...candles.map(x=>x.ohlc[2]),current.reference*.9998),high=Math.max(...candles.map(x=>x.ohlc[1]),current.reference*1.0002),span=Math.max(high-low,1),y=p=>20+(high-p)/span*250;ctx.fillStyle='#536776';ctx.font='14px system-ui';ctx.fillText('Past candles → next full-minute target after reveal',10,15);candles.forEach((x,i)=>{let [o,hi,lo,cl]=x.ohlc,pos=15+i*15;ctx.strokeStyle=ctx.fillStyle=cl>=o?'#128272':'#ba4c60';ctx.beginPath();ctx.moveTo(pos,y(hi));ctx.lineTo(pos,y(lo));ctx.stroke();ctx.fillRect(pos-4,Math.min(y(o),y(cl)),8,Math.max(2,Math.abs(y(o)-y(cl))))});ctx.strokeStyle='#526bb4';ctx.setLineDash([5,5]);ctx.beginPath();ctx.moveTo(0,y(current.reference));ctx.lineTo(w,y(current.reference));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#192c3b';ctx.fillText('Reference $'+current.reference.toFixed(2),10,295)}
async function loadCase(){current=await api('/api/case?id='+$('case').value);token=null;$('reveal').disabled=true;$('actual').textContent='';$('bars').replaceChildren();$('detail').textContent='';$('times').textContent='Input frozen: '+date(current.snapshot_ms)+' · Target starts: '+date(current.target_ms);draw()}
$('case').onchange=()=>loadCase().catch(fail);function fail(e){$('error').textContent=e.message}
$('predict').onclick=async()=>{try{$('predict').disabled=true;let p=await api('/api/predict',{case_id:Number($('case').value)});token=p.token;$('bars').replaceChildren();for(let [name,v] of Object.entries(p.probabilities)){let div=document.createElement('div'),text=document.createElement('span'),track=document.createElement('div'),fill=document.createElement('div');text.textContent=name+': '+pct(v);track.className='track';fill.className='fill';fill.style.width=(v*100)+'%';fill.style.background={bearish:'#ba4c60',neutral:'#8594a4',bullish:'#128272'}[name];track.append(fill);div.append(text,track);$('bars').append(div)}$('detail').textContent='Bullish close ≥ $'+p.upper_price.toFixed(2)+'; bearish close ≤ $'+p.lower_price.toFixed(2)+'. Between them is neutral. Calculation: '+p.calculation_ms.toFixed(1)+' ms. Candle colour probabilities: green '+pct(p.colour_probabilities.green)+', red '+pct(p.colour_probabilities.red)+', flat '+pct(p.colour_probabilities.flat)+'.';$('reveal').disabled=false;$('actual').textContent='';draw()}catch(e){fail(e)}finally{$('predict').disabled=false}};
$('reveal').onclick=async()=>{try{let a=await api('/api/reveal',{token});$('actual').textContent='Actual: '+a.outcome+' · Close $'+a.ohlc[3].toFixed(2)+' · Move '+a.move_bp.toFixed(2)+' basis points';draw(a)}catch(e){fail(e)}};
async function init(){report=await api('/api/report');$('status').textContent='Diwali 0.2 · '+report.architecture+' · Training completed in '+(report.wall_seconds/60).toFixed(1)+' minutes. Probabilities adjusted on a separate calibration period.';for(let [name,v] of Object.entries(report.partitions)){let tr=document.createElement('tr');for(let t of [name,pct(v.primary.accuracy),v.primary.log_loss.toFixed(4),v.fit_frequency_baseline.log_loss.toFixed(4)]){let td=document.createElement('td');td.textContent=t;tr.append(td)}$('scores').append(tr)}for(let b of report.partitions.locked_test.primary.confidence_bins){let tr=document.createElement('tr');for(let t of [pct(b.lower)+'–'+pct(b.upper),b.n,pct(b.mean_confidence),pct(b.observed_accuracy)]){let td=document.createElement('td');td.textContent=t;tr.append(td)}$('reliability').append(tr)}for(let i=0;i<10;i++){let o=document.createElement('option');o.value=i;o.textContent='Historical example '+(i+1);$('case').append(o)}await loadCase()}init().catch(fail);
</script>'''


def main():
    p = argparse.ArgumentParser(); p.add_argument('--port',type=int,default=8742)
    p.add_argument('--run',type=Path,default=ROOT/'data/models/diwali0.2'); a = p.parse_args()
    engine = Engine(a.run)
    class Handler(BaseHTTPRequestHandler):
        def respond(self, obj, code=200):
            payload = json.dumps(obj,allow_nan=False).encode(); self.send_response(code)
            self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
        def do_GET(self):
            from urllib.parse import urlparse, parse_qs
            u = urlparse(self.path)
            try:
                if u.path == '/':
                    payload = HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
                    self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload);return
                if u.path == '/api/status':return self.respond(json.loads((engine.run/'status.json').read_text()))
                if u.path == '/api/report':return self.respond(json.loads((engine.run/'report.json').read_text()))
                if u.path == '/api/case':
                    with engine.lock:return self.respond(engine.case(int(parse_qs(u.query).get('id',['0'])[0])))
                return self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length',0))
                if not 0 < size < 4096:raise ValueError('Invalid request')
                body = json.loads(self.rfile.read(size))
                if self.path == '/api/predict':return self.respond(engine.predict(int(body['case_id'])))
                if self.path == '/api/reveal':
                    with engine.lock:return self.respond(engine.reveal(body['token']))
                return self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def log_message(self,*args):pass
    print(f'Diwali 0.2: http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__ == '__main__':main()
