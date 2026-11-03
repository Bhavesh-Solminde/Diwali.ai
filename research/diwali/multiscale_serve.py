"""Diwali0.3 checkpoint-backed replay with explicit controlled comparisons."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

import numpy as np
import torch

from . import probability_serve as old
from .multiscale import MultiModel,context
from .probability import probabilities,CLASSES
from ..market_data.validate_archive import file_hash


class Engine(old.Engine):
    def ready(self):
        if self.model is not None:return
        manifest=json.loads((self.run/'release-manifest.json').read_text())
        for name,expected in manifest['artifact_sha256'].items():
            if file_hash(self.run/name)!=expected:raise ValueError('Changed run artifact: '+name)
        self.full_report=json.loads((self.run/'report.json').read_text())
        self.mode=self.full_report['selected_mode'];details=self.full_report['models'][self.mode]
        self.report={'architecture':self.mode,'temperatures':details['temperatures']}
        self.prep=json.loads((self.run/'preprocessing.json').read_text())
        self.data=old.Data(old.ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'replay-cache')
        if self.prep['dataset_fingerprint']!=self.data.manifest['fingerprint']:raise ValueError('Changed dataset')
        if file_hash(self.data.aligned/'scalers.json')!=self.prep['short_scaler_sha256']:raise ValueError('Changed scalers')
        p=np.load(self.run/f'{self.mode}-locked_test-predictions.npz')
        self.indices=p['indices'][np.linspace(0,len(p['indices'])-1,10,dtype=int)]
        checkpoint=self.run/f'{self.mode}-17.pt'
        if file_hash(checkpoint)!=details['checkpoint_sha256']:raise ValueError('Changed checkpoint')
        state=torch.load(checkpoint,map_location='cpu',weights_only=True)
        self.model=MultiModel(self.mode);self.model.load_state_dict(state['state_dict']);self.model.eval()
        self.prefix=np.load(self.run/'prefix.npy',mmap_mode='r')
        torch.set_num_threads(4)

    def predict(self,i):
        with self.lock:
            case=self.case(i);row=self.indices[i];began=time.perf_counter()
            ref=case['reference'];anchor=self.data.raw[int(row[2])-1,3]
            delta=((ref/anchor-1)*10000-self.prep['delta_mean'])/self.prep['delta_std']
            long=context(self.prefix,int(row[4]),ref)
            x=np.concatenate([self.data.feature(row),[delta],((long-self.prep['long_mean'])/self.prep['long_std']).ravel()])[None].astype(np.float32)
            with torch.inference_mode():logits=self.model(torch.from_numpy(x)).numpy()[0]
            p=[probabilities(logits[h],self.report['temperatures'][h]).tolist() for h in range(2)]
            token=uuid.uuid4().hex;self.requests[token]=(i,p[0])
            if len(self.requests)>1000:self.requests.pop(next(iter(self.requests)))
            return {'token':token,'probabilities':dict(zip(CLASSES,p[0])),
                    'colour_probabilities':dict(zip(['red','flat','green'],p[1])),
                    'reference':ref,'lower_price':ref*.9998,'upper_price':ref*1.0002,
                    'calculation_ms':(time.perf_counter()-began)*1000}


def displayed_report(report):
    details=report['models'][report['selected_mode']]
    partitions={name:{'primary':part['primary'],'fit_frequency_baseline':part['fit_frequency']} for name,part in details['partitions'].items()}
    return {'model':'diwali0.3','architecture':{'multiscale':'longer order history','short_control':'matched short history'}[report['selected_mode']],'wall_seconds':report['wall_seconds'],'partitions':partitions}


def html(report):
    text=old.HTML.replace('Diwali 0.2','Diwali 0.3').replace('DIWALI RESEARCH','Diwali 0.3 research')
    text=text.replace('<h1>Next-candle probabilities</h1>', '<h1>Does longer order history help?</h1><p>Original 60-second inputs plus minute summaries of the past hour and hourly summaries of the past day. Missing history is marked. Observations are one-second samples; finer events and cancellation identities are unavailable in these features.</p>')
    text=text.replace('<strong>In this completed run, every call above 60% confidence was neutral. The 80% group below is confidence in little movement, not bullish or bearish direction.</strong>',
        '<strong>Confidence includes neutral predictions. The comparison section above reports bullish/bearish calls separately.</strong>')
    rows=[]
    base=report['models']['multiscale']['partitions']['locked_test']['diwali0.2']
    for name,part in [('Diwali0.2',base)]+[({'short_control':'Matched short history','multiscale':'Diwali0.3 longer history'}[m],report['models'][m]['partitions']['locked_test']['primary']) for m in ['short_control','multiscale']]:
        rows.append(f"<tr><td>{name}</td><td>{100*part['accuracy']:.2f}%</td><td>{part['log_loss']:.5f}</td><td>{part['brier_score_sum_over_classes']:.5f}</td></tr>")
    direction=report['models']['multiscale']['partitions']['locked_test']['directional']
    calls='; '.join(f"≥{int(float(k)*100)}%: {v['n']} calls" for k,v in direction.items())
    better=report['models']['multiscale']['partitions']['locked_test']['primary']['log_loss']<base['log_loss']
    verdict='Longer history lowered probability error on this benchmark.' if better else 'Longer history did not improve probability error over Diwali0.2 on this benchmark.'
    selected={'multiscale':'longer history','short_control':'matched short history'}[report['selected_mode']]
    comparison='<section><h2>Same historical examples</h2><p><strong>'+verdict+'</strong></p><table><thead><tr><th>Model</th><th>Accuracy</th><th>Log loss ↓</th><th>Brier error ↓</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table><p>Selected before calibration using development results: '+selected+'. Comparisons are descriptive; October was already inspected. Longer-history directional calls: '+calls+'.</p></section>'
    return text.replace('<section><h2>Training result</h2>',comparison+'<section><h2>Training result</h2>')


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8743);p.add_argument('--run',type=Path,default=old.ROOT/'data/models/diwali0.3');a=p.parse_args()
    engine=Engine(a.run)
    class Handler(BaseHTTPRequestHandler):
        def respond(self,obj,status=200):
            b=json.dumps(obj,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            u=urlparse(self.path)
            try:
                if u.path=='/':
                    b=html(json.loads((engine.run/'report.json').read_text())).encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
                if u.path=='/api/report':return self.respond(displayed_report(json.loads((engine.run/'report.json').read_text())))
                if u.path=='/api/full-report':return self.respond(json.loads((engine.run/'report.json').read_text()))
                if u.path=='/api/status':return self.respond(json.loads((engine.run/'status.json').read_text()))
                if u.path=='/api/case':
                    with engine.lock:return self.respond(engine.case(int(parse_qs(u.query).get('id',['0'])[0])))
                return self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length',0))
                if not 0<size<4096:raise ValueError('Invalid request')
                body=json.loads(self.rfile.read(size))
                if self.path=='/api/predict':return self.respond(engine.predict(int(body['case_id'])))
                if self.path=='/api/reveal':
                    with engine.lock:return self.respond(engine.reveal(body['token']))
                return self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def log_message(self,*args):pass
    print(f'Diwali0.3 http://127.0.0.1:{a.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()


if __name__=='__main__':main()
