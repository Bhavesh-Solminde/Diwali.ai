"""Pinned, independent forecast wrappers. No broker access or trade sizing."""
import hashlib,json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).parent/'runtime'
PINS={'kronos-small':('NeoQuasar--Kronos-small','901c26c1332695a2a8f243eb2f37243a37bea320'),
      'tokenizer':('NeoQuasar--Kronos-Tokenizer-base','0e0117387f39004a9016484a186a908917e22426'),
      'chronos-2':('amazon--chronos-2','29ec3766d36d6f73f0696f85560a422f50e8498c')}


def verified_checkpoint(name):
    folder,revision=PINS[name]
    manifest=json.loads((ROOT/'checkpoints'/(folder+'-manifest.json')).read_text())
    if manifest['revision']!=revision:raise ValueError('Checkpoint revision changed')
    for f,h in manifest['files'].items():
        if hashlib.sha256((ROOT/'checkpoints'/folder/f).read_bytes()).hexdigest()!=h:
            raise ValueError('Checkpoint file changed')
    return ROOT/'checkpoints'/folder,manifest


def seed_for(symbol,entry_ns):
    return int(hashlib.sha256(f'20261029|{symbol}|{entry_ns}'.encode()).hexdigest()[:8],16)


def context_for(market,entry_ns,length=128):
    at=pd.Timestamp(int(entry_ns),tz='UTC')
    b=market.bars[15]
    context=b.loc[b.index+pd.Timedelta(minutes=15)<=at].tail(length)
    if len(context)!=length or not context['count'].eq(15).all():return None
    times=context.index.tz_convert('UTC').as_unit('ns').asi8
    if not (np.diff(times)==15*60*10**9).all() or times[-1]+15*60*10**9!=at.value:return None
    values=context[['open','high','low','close']].to_numpy(dtype=np.float32)
    if not np.isfinite(values).all() or (values<=0).any():return None
    return values,times


class Forecast:
    def __init__(self,name):
        import torch
        self.torch=torch;self.name=name
        torch.set_num_threads(2);torch.manual_seed(20261029)
        torch.use_deterministic_algorithms(True)
        path,self.provenance=verified_checkpoint(name)
        if name=='kronos-small':
            import subprocess
            source=ROOT/'kronos-source'
            commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
            if commit!='67b630e67f6a18c9e9be918d9b4337c960db1e9a':raise ValueError('Kronos source revision changed')
            if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():raise ValueError('Modified Kronos source')
            sys.path.insert(0,str(source.resolve()))
            from model import Kronos,KronosTokenizer,KronosPredictor
            tokenizer_path,self.tokenizer_provenance=verified_checkpoint('tokenizer')
            model=Kronos.from_pretrained(str(path),local_files_only=True);model.eval()
            tokenizer=KronosTokenizer.from_pretrained(str(tokenizer_path),local_files_only=True);tokenizer.eval()
            self.pipeline=KronosPredictor(model,tokenizer,device='cpu',max_context=512,clip=5)
        elif name=='chronos-2':
            from chronos import Chronos2Pipeline
            self.pipeline=Chronos2Pipeline.from_pretrained(str(path),device_map='cpu',dtype=torch.float32,local_files_only=True)
            self.pipeline.model.eval()
        else:raise ValueError('Choose one model')

    def predict(self,values,times,symbol,entry_ns):
        torch=self.torch
        if values.shape!=(128,4) or times.shape!=(128,) or not np.isfinite(values).all():
            raise ValueError('Expected finite 128x4 OHLC context')
        if times[-1]+15*60*10**9!=entry_ns or not (np.diff(times)==15*60*10**9).all():
            raise ValueError('Future or discontinuous context')
        torch.manual_seed(seed_for(symbol,entry_ns))
        with torch.inference_mode():
            if self.name=='kronos-small':
                df=pd.DataFrame(values,columns=['open','high','low','close'])
                x=pd.Series(pd.to_datetime(times,unit='ns',utc=True).tz_localize(None))
                y=pd.Series(pd.date_range(pd.Timestamp(entry_ns,tz='UTC').tz_localize(None),periods=4,freq='15min'))
                forecast=self.pipeline.predict(df,x,y,pred_len=4,T=1.,top_k=0,top_p=.9,sample_count=1,verbose=False)
                result=forecast.close.to_numpy(dtype=float)
            else:
                x=torch.tensor(values[:,3].copy(),dtype=torch.float32).reshape(1,1,-1)
                quantiles,_=self.pipeline.predict_quantiles(x,prediction_length=4,quantile_levels=[.5],
                    context_length=128,cross_learning=False,batch_size=1)
                result=quantiles[0][0,:,0].cpu().numpy().astype(float)
        if result.shape!=(4,) or not np.isfinite(result).all() or (result<=0).any():
            raise ValueError('Invalid forecast')
        return result
