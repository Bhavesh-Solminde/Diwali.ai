"""Local-only diwali0.1 dashboard and genuine historical model inference."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid
import numpy as np
import torch
from .train import Data
from .model import Diwali
from ..market_data.validate_archive import file_hash

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/'ui/diwali'


class Engine:
    def __init__(self,run):self.run=run;self.data=None;self.model=None;self.lock=threading.Lock();self.requests={}
    def report(self):
        p=self.run/'report.json'
        return json.loads(p.read_text()) if p.exists() else None
    def ready(self):
        if self.model is not None:return
        report=self.report()
        if not report:raise ValueError('Training is still running. Try again shortly.')
        torch.set_num_threads(4)
        self.data=Data(ROOT/'data/btc-perp/aligned-button-pilot-202610-v1',self.run/'ui-cache')
        self.indices=np.load(self.data.root/'locked_test-phase15-grace1000-indices.npy')
        self.case_indices=np.linspace(0,len(self.indices)-1,10,dtype=int)
        checkpoint=self.run/f"{report['architecture']}-17.pt"
        if file_hash(checkpoint)!=report['checkpoint_sha256']:raise ValueError('Model checkpoint checksum changed')
        saved=torch.load(checkpoint,map_location='cpu',weights_only=True)
        self.model=Diwali(saved['architecture'],saved['scales']);self.model.load_state_dict(saved['state_dict']);self.model.eval()
        self.intervals=report['intervals']
    def cases(self):
        self.ready()
        return [{'id':i,'snapshot_ms':int(self.indices[j,0]),'target_ms':int(self.indices[j,1])} for i,j in enumerate(self.case_indices)]
    def case(self,i):
        self.ready()
        if not 0<=i<10:raise ValueError('Choose one of the ten saved examples.')
        row=self.indices[self.case_indices[i]];ci=int(row[2]);anchor=float(self.data.raw[ci-1,3])
        candles=[{'time':0,'ohlc':self.data.raw[ci-90+k,:4].tolist()} for k in range(90)]
        # Use the dataset's UTC warmup constant, independent of target/actual candles.
        from ..market_data.build_pilot import WARMUP
        for k,c in enumerate(candles):c['time']=int(WARMUP+(ci-90+k)*60000)
        return {'id':i,'snapshot_ms':int(row[0]),'target_ms':int(row[1]),'anchor':anchor,'candles':candles,
            'context_count':1440,'book_trade_seconds':60,'mode':'historical replay'},row
    def predict(self,i):
        with self.lock:
            case,row=self.case(i);began=time.perf_counter()
            x=self.data.feature(row);input_sha=hashlib.sha256(x.tobytes()).hexdigest()
            with torch.inference_mode():bp=self.model(torch.from_numpy(x[None])).numpy()[0]
            ms=(time.perf_counter()-began)*1000
            forecast=(case['anchor']*(1+bp/10000)).tolist()
            token=uuid.uuid4().hex;self.requests[token]=(i,forecast)
            if len(self.requests)>1000:self.requests.pop(next(iter(self.requests)))
            return {'token':token,'forecast':forecast,'interval80':[[float(v-case['anchor']*self.intervals['0.8']['radius_bp'][k]/10000),
                float(v+case['anchor']*self.intervals['0.8']['radius_bp'][k]/10000)] for k,v in enumerate(forecast)],
                'calculation_ms':ms,'input_sha256':input_sha,'snapshot_ms':case['snapshot_ms'],'target_ms':case['target_ms'],
                'mode':'historical_replay_calculated_now','model':'diwali0.1',
                'note':'Calculated now from historical inputs; not a prediction published in the past.'}
    def reveal(self,token):
        if token not in self.requests:raise ValueError('Click Predict before revealing the real candle.')
        i,pred=self.requests[token];row=self.indices[self.case_indices[i]]
        from ..market_data.build_pilot import WARMUP
        actual=self.data.raw[(int(row[1])-WARMUP)//60000,:4]
        error=np.asarray(pred)-actual
        return {'actual':actual.tolist(),'absolute_error_usdt':np.abs(error).tolist(),
            'mean_error_usdt':float(np.abs(error).mean()),'candle_colour_correct':bool(np.sign(pred[3]-pred[0])==np.sign(actual[3]-actual[0]))}


def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8741);p.add_argument('--run',type=Path,default=ROOT/'data/models/diwali0.1');a=p.parse_args()
    engine=Engine(a.run)
    class Handler(BaseHTTPRequestHandler):
        def respond(self,obj,status=200):
            content=json.dumps(obj,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            url=urlparse(self.path)
            try:
                if url.path=='/api/status':
                    f=engine.run/'status.json';return self.respond(json.loads(f.read_text()) if f.exists() else {'stage':'Not started'})
                if url.path=='/api/report':return self.respond(engine.report())
                if url.path=='/api/cases':return self.respond(engine.cases())
                if url.path=='/api/case':return self.respond(engine.case(int(parse_qs(url.query).get('id',['0'])[0]))[0])
                name={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(url.path)
                if not name:return self.respond({'error':'Not found'},404)
                f=UI/name;data=f.read_bytes();self.send_response(200);self.send_header('Content-Type',{'html':'text/html','js':'text/javascript','css':'text/css'}[f.suffix[1:]]);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<4096:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(size))
                if self.path=='/api/predict':return self.respond(engine.predict(int(body['case_id'])))
                if self.path=='/api/reveal':return self.respond(engine.reveal(body['token']))
                self.respond({'error':'Not found'},404)
            except Exception as exc:self.respond({'error':str(exc)},400)
        def log_message(self,*args):pass
    print(f'diwali0.1 UI: http://127.0.0.1:{a.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
if __name__=='__main__':main()
