"""Small causal transformer: continuous candle tokens, one-step density output."""
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

from .data import decode


@dataclass
class Config:
    context: int = 64
    width: int = 32
    heads: int = 4
    layers: int = 2
    dropout: float = 0.1

    def __post_init__(self):
        if self.context < 2 or self.width < 4 or self.heads < 1 or self.width % self.heads:
            raise ValueError("Invalid context/width/attention heads")
        if self.layers < 1 or not 0 <= self.dropout < 1:
            raise ValueError("Invalid layers/dropout")


class CandleTransformer(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.input = nn.Linear(9, config.width)
        self.position = nn.Parameter(torch.randn(config.context, config.width) * 0.02)
        layer = nn.TransformerEncoderLayer(config.width, config.heads,
            dim_feedforward=config.width * 4, dropout=config.dropout,
            batch_first=True, norm_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, config.layers, enable_nested_tensor=False)
        # TransformerEncoder clones its prototype; initialize each layer independently.
        for block in self.encoder.layers:
            for parameter in block.parameters():
                if parameter.ndim > 1:
                    nn.init.xavier_uniform_(parameter)
        self.head = nn.Sequential(nn.LayerNorm(config.width), nn.Linear(config.width, 8))

    def forward(self, x):
        length = x.shape[1]
        if length > self.config.context:
            raise ValueError("Context exceeds positional embedding length")
        mask = torch.triu(torch.ones(length, length, device=x.device, dtype=torch.bool), diagonal=1)
        h = self.encoder(self.input(x) + self.position[:length], mask=mask)
        mean, log_std = self.head(h).chunk(2, dim=-1)
        return mean, log_std.clamp(-5, 3)


def nll(mean, log_std, target):
    return (0.5 * ((target - mean) * torch.exp(-log_std)) ** 2 + log_std
            + 0.5 * np.log(2 * np.pi)).mean()


def sample_candles(mean, log_std, y_mean, y_std, previous_close, samples=1000, seed=42):
    if samples < 100:
        raise ValueError("Use at least 100 generated samples")
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(samples,) + mean.shape) * np.exp(log_std) + mean
    latent = z * y_std + y_mean
    clipped = ((np.abs(latent[..., :2]) > 1000).any(axis=-1)
               | (latent[..., 2:] > 7).any(axis=-1))
    # Negative wick coordinates naturally represent zero-length wicks.
    candles = decode(latent, previous_close)
    return candles, float(clipped.mean())


class Windows(torch.utils.data.Dataset):
    def __init__(self, features, targets, indices, context):
        self.x = torch.as_tensor(features, dtype=torch.float32)
        self.y = torch.as_tensor(targets, dtype=torch.float32)
        self.indices = np.asarray(indices, dtype=np.int64)
        self.context = context
        if len(self.indices) and (self.indices.min() < context + 1 or self.indices.max() >= len(self.x)):
            raise ValueError("Invalid next-candle target index")

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i):
        t = self.indices[i]
        return self.x[t - self.context:t], self.y[t]
