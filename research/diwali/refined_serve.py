"""Diwali0.9 historical probability replay with separate actual revelation."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path

import numpy as np
import torch

from . import path_serve as parent,probability_serve as old,fan_serve
from .refined import RefinedJoint
from .net_direction import direction_summary
from ..market_data.validate_archive import file_hash


class Engine(parent.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());self.mode=self.full_report['selected_mode'];self.info=self.full_report['models'][self.mode]
        checkpoint=self.run/f'{self.mode}-17.pt'
        if file_hash(checkpoint)!=self.info['checkpoint_sha256']:raise ValueError('Changed residual checkpoint')
        if file_hash(old.ROOT/'research/diwali/refined.py')!=self.full_report['protocol']['model_source_sha256']:raise ValueError('Changed model source')
        self.prep=json.loads((old.ROOT/'data/models/diwali0.5/preprocessing.json').read_text());self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.data.manifest['fingerprint']!=self.prep['dataset_fingerprint'] or file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed input contract')
        torch.set_num_threads(4);self.model=RefinedJoint(self.mode,checkpoint,self.full_report['protocol']['parents'],self.info['residual_temperatures']).eval()
        z=np.load(self.run/f'{self.mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)];self.chains={}

    def predict(self,i):
        r=super().predict(i)
        p=np.array([[v['probability'] for v in f['ranges']] for f in r['fan']])
        overall={**direction_summary(p),'reference':r['reference'],'close_ms':r['fan'][-1]['close_ms']}
        return {**r,'overall_direction':overall,'model_calls':3,'scope':'Frozen marginal parent, learned recent-candle correction and frozen dependence parent; coherent15-close probabilities, not intraminute paths.'}


def html(report,oldreport):
    text=parent.html(report,oldreport).replace('Diwali 0.6','Diwali 0.9').replace('Diwali0.6 learned joint model','Diwali0.9 selected model')
    text=text.replace('Training completed in','Experiment completed in').replace('Probabilities adjusted on a separate calibration period.','Parent calibration reused; recent-candle correction trained and recalibrated on historical partitions.')
    rows=[]
    for mode,info in report['models'].items():
        p=info['partitions']['locked_test'];name={'grouped':'Grouped recent candles','minute_detail':'Individual recent candles'}[mode]+(' (selected)' if mode==report['selected_mode'] else '')
        rows.append(f"<tr><td>{name}</td><td>{p['mean15_marginal_bin_log_loss']:.5f}</td><td>{p['joint_log_loss']:.5f}</td><td>{100*p['horizons']['1']['primary']['accuracy']:.2f}%</td></tr>")
    section='<section><h2>Does recent candle detail help?</h2><p>Both branches have the same capacity. One sees the last60 candles individually; the control sees four15-minute averages. Each learns a correction to the frozen0.5 forecast. Selection uses three-seed development scores, not this already-inspected benchmark.</p><div style="overflow:auto"><table><thead><tr><th>Method</th><th>Mean closing-range error</th><th>Whole-sequence error</th><th>First-close direction accuracy</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
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
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8749);parser.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.9');a=parser.parse_args();engine=Engine(a.run)
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
                    r,v=reports();d=fan_serve.display_report(parent.adapted(r,v),json.loads((old.ROOT/'data/models/diwali0.5/baseline-definitions.json').read_text()));d['architecture']='Recent-candle correction / '+r['selected_mode'];return self.respond(d)
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
    print(f'Diwali0.9 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
