import torch
from torch import nn
import torch.nn.functional as F

CANDLE_SIZE=1440*8
BOOK_SIZE=60*87
WIDTH=CANDLE_SIZE+BOOK_SIZE+60*5


class Diwali(nn.Module):
    def __init__(self,architecture,scales):
        super().__init__();self.architecture=architecture
        self.register_buffer('scales',torch.tensor(scales,dtype=torch.float32))
        if architecture=='mlp':
            self.body=nn.Sequential(nn.Linear(WIDTH,32),nn.GELU(),nn.Linear(32,32),nn.GELU())
        else:
            self.conv=nn.Conv1d(8,16,15,stride=15)
            self.candle_gru=nn.GRU(16,32,batch_first=True)
            self.project=nn.Linear(92,16);self.flow_gru=nn.GRU(16,32,batch_first=True)
            self.body=nn.Sequential(nn.Linear(64,32),nn.GELU())
        self.head=nn.Linear(32,4)
    def forward(self,x):
        if self.architecture=='mlp':z=self.body(x)
        else:
            c=x[:,:CANDLE_SIZE].reshape(-1,1440,8).transpose(1,2)
            c=F.gelu(self.conv(c)).transpose(1,2)
            _,ch=self.candle_gru(c)
            b=x[:,CANDLE_SIZE:CANDLE_SIZE+BOOK_SIZE].reshape(-1,60,87)
            t=x[:,CANDLE_SIZE+BOOK_SIZE:].reshape(-1,60,5)
            _,fh=self.flow_gru(F.gelu(self.project(torch.cat([b,t],dim=2))))
            z=self.body(torch.cat([ch[-1],fh[-1]],dim=1))
        v=self.head(z);o=v[:,0]*self.scales[0];c=v[:,1]*self.scales[3]
        high=torch.maximum(o,c)+F.softplus(v[:,2])*self.scales[1]
        low=torch.minimum(o,c)-F.softplus(v[:,3])*self.scales[2]
        return torch.stack([o,high,low,c],dim=1)
