"""Two frozen networks, one fitted coupling, exact queries and price-aligned display."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path

import numpy as np
import torch

from . import path_serve as parent,probability_serve as old,fan_serve
from .coupled import make_model
from ..market_data.validate_archive import file_hash


class Engine(parent.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());self.mode=self.full_report['selected_mode'];self.info=self.full_report['models'][self.mode]
        definition=self.run/f'{self.mode}-definition.json'
        if file_hash(definition)!=self.info['definition_sha256']:raise ValueError('Changed model definition')
        config=json.loads(definition.read_text())
        if file_hash(old.ROOT/'research/diwali/coupled.py')!=config['coupling_source_sha256']:raise ValueError('Changed coupling source')
        self.prep=json.loads((old.ROOT/'data/models/diwali0.5/preprocessing.json').read_text());self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.data.manifest['fingerprint']!=self.prep['dataset_fingerprint'] or file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed input contract')
        torch.set_num_threads(4);self.model=make_model(config['parents'],config['gamma'],'cpu')
        z=np.load(self.run/f'{self.mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)];self.chains={}

    def predict(self,i):
        result=super().predict(i)
        return {**result,'model_calls':2,'neural_parent_calls':2,'scope':'Two frozen neural parents plus fitted dependence; coherent26-bin distribution over15 candle closes, no intraminute path.'}


def html(report,oldreport):
    text=parent.html(report,oldreport).replace('Diwali 0.6','Diwali 0.8').replace('Diwali0.6 learned joint model','Diwali0.8 coupled model')
    text=text.replace('Training completed in','Experiment completed in').replace('Probabilities adjusted on a separate calibration period.','Frozen parent calibration reused; one dependence coefficient fitted. This is not new neural training.')
    p=report['models'][report['selected_mode']]['partitions']['locked_test'];rows=[]
    for name,info in report['models'].items():
        v=info['partitions']['locked_test'];label={'independent':'Independent closes','unit_dependence':'Unit dependence','fitted_dependence':'Fitted dependence'}[name]+(' (selected)' if name==report['selected_mode'] else '')
        rows.append(f"<tr><td>{label}</td><td>{info['gamma']:.2f}</td><td>{v['joint_log_loss']:.5f}</td><td>{v['mean15_marginal_bin_log_loss']:.5f}</td></tr>")
    section='<section><h2>Linking the price probabilities</h2><p>Diwali 0.8 keeps every individual forecast from 0.5 and links adjacent closing times using the sequence network from 0.7. Two frozen networks; one fitted coefficient. It cannot improve direction accuracy because those individual probabilities stay the same. Selection uses development data.</p><div style="overflow:auto"><table><thead><tr><th>Method</th><th>Dependence</th><th>Whole-sequence error</th><th>Mean closing-range error</th></tr></thead><tbody>'+''.join(rows)+f"</tbody></table></div><p>Diwali 0.7 whole-sequence error: {p['diwali0.7_joint_log_loss']:.5f}. Lower error is better. October is an already-inspected benchmark.</p></section>"
    text=text.replace('<section><h2>Probability error for the whole sequence</h2>',section+'<section><h2>Probability error for the whole sequence</h2>')
    chart='''<canvas id="price-chart" style="width:100%;height:420px;display:block;border-radius:8px" aria-label="Past candles and discrete future closing-price probability columns. Exact probabilities are in the table below."></canvas><p id="price-inspect" aria-live="polite">Hover over a future column to inspect a price range; click to select its closing time.</p><small>Purple intensity shows probability of the whole price bin, not probability per dollar. Bin heights follow a linear price axis. Infinite tails extend beyond the view; their full probabilities remain in the table. Each column is one candle close, not an intraminute path. The chart shows the last 40 past candles; the model receives 1,440. Reveal overlays actual candles and may expand the axis without changing predictions.</small>'''
    text=text.replace('<canvas id="chart"',chart+'<canvas hidden id="chart"')
    # Hide the superseded past-only chart explanation; the new chart explains its own scope.
    text=text.replace('The chart shows observed past candles. The actual next candle appears only after Reveal. The separate range forecast below concerns the final close. It does not predict the order in which prices are touched.','Actuals appear only after Reveal.')
    return text+'<script>'+Path(__file__).with_name('price_chart.js').read_text()+'</script>'


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8748);p.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.8');a=p.parse_args();engine=Engine(a.run)
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
                    r,v=reports();d=fan_serve.display_report(parent.adapted(r,v),json.loads((old.ROOT/'data/models/diwali0.5/baseline-definitions.json').read_text()));d['architecture']='Two frozen networks / one fitted coupling';return self.respond(d)
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
    print(f'Diwali0.8 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
