"""Diwali1.3 historical probability replay with separate actual revelation."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path

import numpy as np
import torch

from . import path_serve as parent,probability_serve as old,fan_serve
from .anchored import AnchoredJoint
from .path import forecast
from .fan import EDGES,direction
from .probability import probabilities,CLASSES
from ..market_data.midpoint import DTYPE,window_features
from ..market_data.midpoint_windows import summaries
import time,uuid
from .net_direction import direction_summary
from ..market_data.validate_archive import file_hash


class Engine(parent.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());self.mode=self.full_report['selected_mode'];self.info=self.full_report['models'][self.mode]
        checkpoint=self.run/f'{self.mode}-17.pt'
        if file_hash(checkpoint)!=self.info['checkpoint_sha256']:raise ValueError('Changed residual checkpoint')
        if file_hash(old.ROOT/'research/diwali/anchored.py')!=self.full_report['protocol']['model_source_sha256']:raise ValueError('Changed model source')
        self.prep=json.loads((old.ROOT/'data/models/diwali0.5/preprocessing.json').read_text());self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.data.manifest['fingerprint']!=self.prep['dataset_fingerprint'] or file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed input contract')
        torch.set_num_threads(4);self.model=AnchoredJoint(checkpoint,self.full_report['protocol']['parent'],self.info['residual_temperatures'],self.info['branch_mode']).eval()
        midroot=old.ROOT/self.full_report['protocol']['midpoint_preparation']['root']
        if file_hash(midroot/'manifest.json')!=self.full_report['protocol']['midpoint_preparation']['manifest_sha256']:raise ValueError('Changed midpoint preparation')
        mid=json.loads((midroot/'manifest.json').read_text());scaler=midroot/'summary-scaler.json'
        if file_hash(scaler)!=mid['artifacts']['summary-scaler.json']:raise ValueError('Changed midpoint scaler')
        self.midpoint_scaler=json.loads(scaler.read_text());path=next(Path(p) for p in mid['inputs'] if p.endswith('/midpoints.bin'))
        if file_hash(path)!=mid['inputs'][str(path)]:raise ValueError('Changed midpoint source')
        self.midpoints=np.memmap(path,dtype=DTYPE,mode='r')
        z=np.load(self.run/f'{self.mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)];self.chains={}

    def predict(self,i):
        with self.lock:
            case=self.case(i);row=self.indices[i];started=time.perf_counter();ref=case['reference'];anchor=self.data.raw[int(row[2])-1,3]
            delta=((ref/anchor-1)*10000-self.prep['delta_mean'])/self.prep['delta_std'];mid=self.midpoints[int(row[3]):int(row[4])]
            if len(mid)!=60 or not mid['valid'].all() or not (mid['time_ns']<int(row[0])*10**6).all():raise ValueError('Unavailable midpoint window')
            raw=summaries(window_features(mid['mid'],anchor)[None])[0];extra=((raw-np.asarray(self.midpoint_scaler['mean']))/np.asarray(self.midpoint_scaler['std'])).astype(np.float32)
            x=np.concatenate([self.data.feature(row),[delta],extra])[None].astype(np.float32);a,t,m,c=forecast(self.model,x,self.info['temperatures'],'cpu');p=m[0];dp=direction(p);cp=probabilities(c[0],self.info['colour_temperature']);bounds=[None]+EDGES.tolist()+[None];fan=[]
            for h in range(15):
                ranges=[{'lower_bp':bounds[j],'upper_bp':bounds[j+1],'lower_price':None if bounds[j] is None else ref*(1+bounds[j]/10000),'upper_price':None if bounds[j+1] is None else ref*(1+bounds[j+1]/10000),'probability':float(v)} for j,v in enumerate(p[h])]
                fan.append({'horizon':h+1,'target_ms':case['target_ms']+h*60000,'close_ms':case['target_ms']+(h+1)*60000,'ranges':ranges,'probabilities':dict(zip(CLASSES,dp[h].tolist()))})
            token=uuid.uuid4().hex;self.requests[token]=(i,p);self.chains[token]=(a,t)
            if len(self.requests)>1000:
                first=next(iter(self.requests));self.requests.pop(first);self.chains.pop(first,None)
            return {'token':token,'fan':fan,'ranges':fan[0]['ranges'],'probabilities':fan[0]['probabilities'],'colour_probabilities':dict(zip(['red','flat','green'],cp.tolist())),'overall_direction':{**direction_summary(p),'reference':ref,'close_ms':fan[-1]['close_ms']},'reference':ref,'lower_price':ref*.9998,'upper_price':ref*1.0002,'target_ms':case['target_ms'],'calculation_ms':(time.perf_counter()-started)*1000,'future_actuals_used':False,'model_calls':3,'scope':'Raw frozen parents plus development-selected correction; coherent15-close bins and final net direction, no intraminute path.'}


def html(report,oldreport):
    text=parent.html(report,oldreport).replace('Diwali 0.6','Diwali 1.3').replace('Diwali0.6 learned joint model','Diwali1.3 selected model')
    text=text.replace('<h2>Future closing-time probability grid</h2>','<h2>Future closing-time probability grid</h2><p><strong>Purple cells = AI probabilities. Black dots = real historical closes, shown only after Reveal outcome.</strong></p>')
    text=text.replace('Training completed in','Experiment completed in').replace('Probabilities adjusted on a separate calibration period.','Raw neural parents; new correction selected before probability calibration. Historical October benchmark already inspected.')
    rows=[]
    for mode,info in report['models'].items():
        p=info['partitions']['locked_test'];name={'confidence_control':'Unregularized control','parent_kl':'Parent KL penalty','epoch0_parent':'Raw parent with matching calibration'}[mode]+(' (selected)' if mode==report['selected_mode'] else '')
        rows.append(f"<tr><td>{name}</td><td>{p['mean15_marginal_bin_log_loss']:.5f}</td><td>{p['joint_log_loss']:.5f}</td><td>{100*p['horizons']['1']['primary']['accuracy']:.2f}%</td></tr>")
    section='<section><h2>Do restrained corrections improve probability quality?</h2><p>The branches use the same midpoint-enabled inputs and network. One adds a training penalty against unsupported changes from the frozen parent distribution; the other has no such penalty. The third row is the unchanged raw parent with matching calibration. Selection uses three-seed development final-direction scores. This is an already-inspected historical benchmark, not fresh confirmation.</p><div style="overflow:auto"><table><thead><tr><th>Method</th><th>Mean closing-range error</th><th>Whole-sequence error</th><th>First-close direction accuracy</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
    text=text.replace('<section><h2>Probability error for the whole sequence</h2>',section+'<section><h2>Probability error for the whole sequence</h2>')
    text=text.replace('<div id="bars"', '<div id="overall-direction" aria-live="polite"><h3>Overall direction at the final forecast close</h3><p>Click Predict to compare the chance of finishing above or below the input reference.</p></div><h3>First future candle only</h3><div id="bars"')
    chart='''<canvas id="price-chart" style="width:100%;height:420px;display:block;border-radius:8px" aria-label="Past candles and discrete future closing-price probability columns; exact probabilities in the table below."></canvas><p id="price-inspect" aria-live="polite">Hover over a future column to inspect its price range. Click to select a closing time.</p><small>Purple intensity represents whole-bin probability, not probability per dollar. Heights use a linear price axis. Infinite tails extend beyond the view; exact probabilities are in the table. Columns describe closes, not intraminute paths. Chart shows40 past candles; model sees1,440. Reveal may expand the axis while keeping predictions unchanged.</small>'''
    text=text.replace('<canvas id="chart"',chart+'<canvas hidden id="chart"')
    text=text.replace('The chart shows observed past candles. The actual next candle appears only after Reveal. The separate range forecast below concerns the final close. It does not predict the order in which prices are touched.','Actuals appear only after Reveal.')
    direction_script='''<script>
const previousRenderFan=renderFan;renderFan=function(result){previousRenderFan(result);let d=result.overall_direction,box=document.getElementById('overall-direction');box.replaceChildren();let title=document.createElement('h3');title.textContent='Overall direction at '+new Date(d.close_ms).toISOString().slice(11,19)+' UTC';let p=document.createElement('p');p.style.cssText='font-size:22px;font-weight:650';p.textContent='Up: '+(100*d.up).toFixed(1)+'% · Down or unchanged: '+(100*d.down_or_unchanged).toFixed(1)+'%';let explanation=document.createElement('p');explanation.textContent='Model favours '+(d.favoured_side==='up'?'up':d.favoured_side==='tie'?'neither side':'down or unchanged')+'. This compares the 15th close with the frozen input reference of $'+d.reference.toFixed(2)+'. It does not mean every candle moves that way. The percentages retain uncertainty; a small difference is a weak preference.';let foot=document.createElement('small');foot.textContent='An exactly unchanged close is included with down because the current price bins do not estimate it separately. This is net displacement, distinct from the ±2-basis-point neutral band below.';box.append(title,p,explanation,foot)};
const previousClearFan=clearFan;clearFan=function(){previousClearFan();document.getElementById('overall-direction').innerHTML='<h3>Overall direction at the final forecast close</h3><p>Click Predict to compare up with down or unchanged.</p>'};
const previousPriceChart=drawPriceChart;drawPriceChart=function(){previousPriceChart();if(!current)return;let canvas=document.getElementById('price-chart'),v=canvas._view,ctx=canvas.getContext('2d');if(!v)return;let y=v.top+(v.high-current.reference)/(v.high-v.low)*(v.bottom-v.top);ctx.strokeStyle='#d3deea';ctx.setLineDash([2,5]);ctx.beginPath();ctx.moveTo(v.left,y);ctx.lineTo(v.right,y);ctx.stroke();ctx.setLineDash([])};
</script>'''
    return text+'<script>'+Path(__file__).with_name('price_chart.js').read_text()+'</script>'+direction_script


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8753);parser.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali1.3');a=parser.parse_args();engine=Engine(a.run)
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
                    r,v=reports();d=fan_serve.display_report(parent.adapted(r,v),json.loads((old.ROOT/'data/models/diwali0.5/baseline-definitions.json').read_text()));d['architecture']='Confidence regularization / '+r['selected_mode'];return self.respond(d)
                if u.path=='/api/full-report':return self.respond(reports()[0])
                if u.path=='/api/status':return self.respond(json.loads((a.run/'status.json').read_text()))
                if u.path=='/api/case':
                    with engine.lock:return self.respond(engine.case(int(parse_qs(u.query).get('id',['0'])[0])))
                self.respond({'error':'Not found'},404)
            except Exception as e:self.respond({'error':str(e)},400)
        def do_POST(self):
            try:
                n=int(self.headers.get('Content-Length',0))
                if not 0<n<4096:raise ValueError('Invalid request')
                b=json.loads(self.rfile.read(n))
                if self.path=='/api/predict':return self.respond(engine.predict(int(b['case_id'])))
                if self.path=='/api/path-range':return self.respond(engine.query(b['token'],int(b['lower_bin']),int(b['upper_bin'])))
                if self.path=='/api/reveal':
                    with engine.lock:return self.respond(engine.reveal(b['token']))
                self.respond({'error':'Not found'},404)
            except Exception as e:self.respond({'error':str(e)},400)
        def log_message(self,*args):pass
    print(f'Diwali1.3 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
