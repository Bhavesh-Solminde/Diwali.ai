"""End-to-end local event processing with retained context tokens and horizon queries."""
import math
import torch
from torch import nn
from torch.nn import functional as F


class CausalLayer(nn.Module):
    def __init__(self,width,dilation):
        super().__init__();self.conv=nn.Conv1d(width,width,3,dilation=dilation);self.pad=2*dilation;self.norm=nn.LayerNorm(width)
    def forward(self,x,mask):
        y=self.conv(F.pad(x.transpose(1,2),(self.pad,0))).transpose(1,2)
        return self.norm(x+F.gelu(y))*mask[:,:,None]


class Attention(nn.Module):
    def __init__(self,width):
        super().__init__();self.q=nn.Linear(width,width);self.k=nn.Linear(width,width);self.v=nn.Linear(width,width);self.out=nn.Linear(width,width)
    def forward(self,query,context,mask):
        scores=self.q(query)@self.k(context).transpose(-1,-2)/math.sqrt(context.shape[-1]);scores=scores.masked_fill(~mask[:,None,:],-torch.inf)
        return self.out(scores.softmax(-1)@self.v(context))


class EventModel(nn.Module):
    def __init__(self,mode='temporal_conv',features=103,width=64,block=128):
        super().__init__()
        if mode not in ['temporal_conv','attention']:raise ValueError('Unknown event architecture')
        self.mode=mode;self.width=width;self.block=block;self.project=nn.Linear(features,width);self.local=nn.ModuleList([CausalLayer(width,d) for d in [1,4,16]])
        self.pool=nn.Linear(width,1);self.group_score=nn.Linear(width,1);self.candle_project=nn.Linear(8,width);self.candle_missing=nn.Parameter(torch.zeros(width));self.candle_local=CausalLayer(width,4);self.seed_project=nn.Linear(80,width)
        self.modality=nn.Parameter(torch.zeros(3,width));self.horizons=nn.Parameter(torch.randn(15,width)*.02)
        self.context_conv=CausalLayer(width,1)
        self.self_attention=Attention(width) if mode=='attention' else None
        self.context_norm=nn.LayerNorm(width);self.read=Attention(width);self.head=nn.Linear(width,26)
    def event_tokens(self,events,mask,groups):
        b,n,_=events.shape
        if mask.shape!=(b,n) or not mask.any(1).all():raise ValueError('Empty/invalid event mask')
        # Valid events form a prefix. Padding is a batching device, never truncation.
        if (mask[:,1:]&~mask[:,:-1]).any():raise ValueError('Event mask must be a prefix')
        if groups.shape!=mask.shape or (groups[mask]<0).any() or (groups[:,0]!=0).any():raise ValueError('Invalid timestamp groups')
        diff=groups[:,1:]-groups[:,:-1]
        if (((diff<0)|(diff>1))&mask[:,1:]).any():raise ValueError('Timestamp groups must be consecutive')
        # Events at identical availability are a set, not a fabricated sequence.
        # Every row is projected first; learned set pooling is permutation invariant.
        embedded=F.gelu(self.project(events))*mask[:,:,None];ids=groups.clamp_min(0);ng=int(groups[mask].max())+1
        score=self.group_score(embedded).squeeze(-1).masked_fill(~mask,-1e9)
        maxima=score.new_full((b,ng),-1e9);maxima.scatter_reduce_(1,ids,score,reduce='amax',include_self=True)
        weight=(score-maxima.gather(1,ids)).clamp(-80,0).exp()*mask
        totals=score.new_zeros((b,ng));totals.scatter_add_(1,ids,weight);weight=weight/totals.gather(1,ids).clamp_min(1e-12)
        grouped=embedded.new_zeros((b,ng,self.width));grouped.scatter_add_(1,ids[:,:,None].expand(-1,-1,self.width),embedded*weight[:,:,None])
        events=grouped;mask=totals>0;n=ng
        blocks=(n+self.block-1)//self.block;pad=blocks*self.block-n
        x=F.pad(events,(0,0,0,pad)).reshape(b*blocks,self.block,-1);m=F.pad(mask,(0,pad)).reshape(b*blocks,self.block)
        x=x*m[:,:,None]
        for layer in self.local:x=layer(x,m)
        score=self.pool(x).squeeze(-1).masked_fill(~m,-1e9);weight=score.softmax(-1)*m
        weight=weight/weight.sum(-1,keepdim=True).clamp_min(1e-12)
        tokens=(x*weight[:,:,None]).sum(1).reshape(b,blocks,self.width)
        return tokens,m.any(1).reshape(b,blocks)
    def forward(self,events,mask,candles,seed,time_groups,candle_mask):
        if candles.shape[1:]!=(1440,8) or seed.shape[1:]!=(80,):raise ValueError('Invalid candle/seed context')
        e,em=self.event_tokens(events,mask,time_groups)
        if candle_mask.shape!=candles.shape[:2] or candle_mask.dtype!=torch.bool:raise ValueError('Explicit candle validity mask required')
        cm=torch.ones(candles.shape[:2],dtype=torch.bool,device=candles.device)
        known=candles.masked_fill(~candle_mask[:,:,None],0)
        c=self.candle_project(known)+self.candle_missing[None,None]*(~candle_mask[:,:,None])
        c=self.candle_local(c,cm)
        # Candle detail is processed before local15-minute pooling; retain96 tokens.
        c=c.reshape(len(c),96,15,self.width).mean(2)
        context=torch.cat([c+self.modality[0],self.seed_project(seed)[:,None]+self.modality[1],e+self.modality[2]],1)
        valid=torch.cat([torch.ones((len(e),97),dtype=torch.bool,device=e.device),em],1)
        if self.self_attention is None:context=self.context_conv(context,valid)
        else:context=self.context_norm(context+self.self_attention(context,context,valid))*valid[:,:,None]
        query=self.horizons[None].expand(len(e),-1,-1);decoded=query+self.read(query,context,valid)
        return self.head(decoded)
