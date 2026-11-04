"""Measure the frozen model's token allocation on earlier development inputs."""
import argparse
import json
from pathlib import Path

import numpy as np
import torch

from .event_data_exact import ExactEventData
from .event_evaluation import eligible_origins
from .event_model import EventModel
from .event_train import probabilities
from ..market_data.validate_archive import file_hash, save


def main():
    p = argparse.ArgumentParser(); p.add_argument('--study', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True); p.add_argument('--features', type=Path, required=True)
    p.add_argument('--content-audit', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); data = ExactEventData(a.cohort, a.features, a.content_audit)
    torch.set_num_threads(4); result = []
    for fold in ['A', 'B', 'C']:
        eligible, _ = eligible_origins(data.cutoffs, data.starts, fold, 'select')
        choices = np.flatnonzero(eligible); selected = choices[np.linspace(0, len(choices)-1, min(64, len(choices)), dtype=int)]
        for seed in [17, 29]:
            root = a.study/f'{fold}-one_second_temporal_conv-seed{seed}'
            protocol = json.loads((root/'run-protocol.json').read_text()); selection = json.loads((root/'selection.json').read_text())
            if file_hash(root/'weights.pt') != selection['weights_sha256']:
                raise ValueError('Changed development checkpoint')
            model = EventModel(width=protocol['neural_width'], block=protocol['event_block_groups'])
            model.load_state_dict(torch.load(root/'weights.pt', weights_only=True, map_location='cpu')); model.eval()
            transforms = json.loads((root/'fit-transforms.json').read_text())
            calibration = json.loads((root/'calibration.json').read_text())
            attention = []; event_counts = []; outputs = []

            def hook(module, args, output):
                query, context, mask = args
                logits = module.q(query)@module.k(context).transpose(-1, -2)/(context.shape[-1]**.5)
                weight = logits.masked_fill(~mask[:, None, :], -torch.inf).softmax(-1)
                attention.append(weight.cpu().numpy())
                event_counts.append(int(context.shape[1])-98)

            handle = model.read.register_forward_hook(hook)
            with torch.inference_mode():
                for start in range(0, len(selected), 8):
                    args, _ = data.batch(selected[start:start+8], transforms, 'cpu')
                    outputs.append(model(*args).numpy())
            handle.remove(); w = np.concatenate(attention); z = np.concatenate(outputs)
            prob = probabilities(z, calibration['temperatures']); up = prob[:, :, 13:].sum(-1)
            if event_counts != [1]*len(event_counts):
                raise ValueError('Expected the frozen 60-step control to pool into one event token')
            result.append({'fold': fold, 'seed': seed, 'selection_origins': len(selected),
                           'candle_tokens': 96, 'seed_tokens': 1, 'reference_tokens': 1,
                           'event_tokens': 1, 'seconds_per_event_token': 60,
                           'mean_query_attention_to_candles': w[:, :, :96].sum(-1).mean(0).tolist(),
                           'mean_query_attention_to_seed': w[:, :, 96].mean(0).tolist(),
                           'mean_query_attention_to_reference': w[:, :, 97].mean(0).tolist(),
                           'mean_query_attention_to_event_token': w[:, :, 98:].sum(-1).mean(0).tolist(),
                           'final_up_probability_min': float(up[:, -1].min()),
                           'final_up_probability_max': float(up[:, -1].max()),
                           'final_up_probability_std': float(up[:, -1].std()),
                           'weights_sha256': file_hash(root/'weights.pt')})
    save(a.output, {'state': 'complete', 'runs': result,
                    'scope': 'Six already-fitted one-second controls, earlier selection inputs only; no reserved final data or new fitting.',
                    'interpretation': 'Attention weights measure direct read allocation, not causal importance: neighbouring context convolutions mix modalities. One token confirms compression, not proof of lost predictive signal.',
                    'data_hashes': data.hashes, 'source_sha256': file_hash(Path(__file__))})
    for r in result:
        print(r['fold'], r['seed'], 'event attention', round(float(np.mean(r['mean_query_attention_to_event_token'])), 6), 'final up std', round(r['final_up_probability_std'], 6))


if __name__ == '__main__':
    main()
