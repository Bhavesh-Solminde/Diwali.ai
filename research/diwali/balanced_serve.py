"""Diwali0.7 checkpoint replay, reusing the verified exact joint-query interface."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path

import numpy as np
import torch

from . import path_serve as parent
from . import probability_serve as old
from . import fan_serve
from .path import PathModel
from ..market_data.validate_archive import file_hash

NAMES={'joint_control':'Continued sequence training','balanced':'Sequence plus closing-range training'}


class Engine(parent.Engine):
    def ready(self):
        if self.model is not None:return
        self.full_report=json.loads((self.run/'report.json').read_text());self.mode=self.full_report['selected_mode'];self.info=self.full_report['models'][self.mode]
        self.prep=json.loads((old.ROOT/'data/models/diwali0.5/preprocessing.json').read_text());self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.data.manifest['fingerprint']!=self.prep['dataset_fingerprint'] or file_hash(self.data.aligned/'scalers.json')!=self.prep['aligned_scaler_sha256']:raise ValueError('Changed input contract')
        checkpoint=self.run/f'{self.mode}-17.pt'
        if file_hash(checkpoint)!=self.info['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        model=PathModel('markov');model.load_state_dict(torch.load(checkpoint,weights_only=True,map_location='cpu')['state_dict']);self.model=model.eval()
        z=np.load(self.run/f'{self.mode}-locked_test-predictions.npz');self.indices=z['indices'][np.linspace(0,len(z['indices'])-1,10,dtype=int)];self.chains={};torch.set_num_threads(4)


def html(report,oldreport):
    text=parent.html(report,oldreport).replace('Diwali 0.6','Diwali 0.7').replace('Diwali0.6 learned joint model','Diwali0.7 selected model')
    p=report['models'][report['selected_mode']]['partitions']['locked_test'];rows=[]
    for name,info in report['models'].items():
        v=info['partitions']['locked_test'];label=NAMES[name]+(' (selected)' if name==report['selected_mode'] else '');rows.append(f"<tr><td>{label}</td><td>{v['joint_log_loss']:.5f}</td><td>{v['mean15_marginal_bin_log_loss']:.5f}</td><td>{v['joint_plus_marginal_per_step']:.5f}</td></tr>")
    rows.append(f"<tr><td>Diwali0.6</td><td>{p['diwali0.6_joint_log_loss']:.5f}</td><td>{p['diwali0.6_mean15_marginal_bin_log_loss']:.5f}</td><td>{p['diwali0.6_joint_log_loss']/15+p['diwali0.6_mean15_marginal_bin_log_loss']:.5f}</td></tr>")
    section='<section><h2>Did balancing improve both probability tasks?</h2><p>Separate columns show error for the whole sequence and for individual closing-time ranges. Lower is better. The combined score is joint error divided by15 plus mean range error; it must not hide a regression in either component. Model selection used development data; this October benchmark has already been inspected.</p><div style="overflow:auto"><table><thead><tr><th>Method</th><th>Whole-sequence error</th><th>Mean closing-range error</th><th>Combined error</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
    return text.replace('<section><h2>Probability error for the whole sequence</h2>',section+'<section><h2>Probability error for the whole sequence</h2>')


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8747);p.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.7');a=p.parse_args();engine=Engine(a.run)
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
                    r,v=reports();d=fan_serve.display_report(parent.adapted(r,v),json.loads((old.ROOT/'data/models/diwali0.5/baseline-definitions.json').read_text()));d['architecture']='Linked future closes / '+NAMES[r['selected_mode']];return self.respond(d)
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
    print(f'Diwali0.7 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
